"""Revisioned operator routing authority for SPEC-067.

The service owns future provider selection only.  It never writes canonical
market evidence and it never edits checked-in provider or MT5 manifests.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .acquisition_orchestrator import credential_map, load_provider_profiles, mapping_authority
from .mt5_catalogue import authorised_routes
from .mt5_route_manifest import approved_route
from .provider_facts import load_provider_facts
from .provider_attempt_ledger import latest_attempts_by_lane
from .scheduler_integrity import active_universe
from .scheduler_state_store import SchedulerStateStore


SNAPSHOT_CONTRACT = "fragarach_ii.routing_snapshot.v2"
CATALOGUE_CONTRACT = "fragarach_ii.provider_catalogue.v2"
REVISION_CONTRACT = "fragarach_ii.routing_revision.v2"
DRAFT_CONTRACT = "fragarach_ii.routing_draft.v2"
ACTIVE_CONTRACT = "fragarach_ii.routing_active.v2"
AUDIT_CONTRACT = "fragarach_ii.routing_activation_receipt.v2"

ESTATE_DEFAULT_ORDER = (
    "MT5_BRIDGE",
    "BINANCE",
    "COINGECKO_DEX",
    "COINGECKO",
    "YAHOO_FINANCE",
    "TWELVE_DATA",
)
DIRECT_MAPPING_CLASSES = {
    "EXACT_REPRESENTATION",
    "APPROVED_PROVIDER_ALIAS",
    "APPROVED_EQUIVALENT_REPRESENTATION",
}
DERIVED_TIMEFRAMES = {"M15"}
DEFAULT_ROOT = Path("~/Library/Application Support/Fragarach II/routing").expanduser()
ACTIVATION_GATE = "FUSION_AUTHORITY_LIVE_RECEIPT_VERIFICATION_REQUIRED"


class RoutingServiceError(ValueError):
    """A controlled route draft or revision error."""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _database_identity(database_path: str | Path) -> str:
    resolved = str(Path(database_path).expanduser().resolve())
    return hashlib.sha256(resolved.encode()).hexdigest()[:16]


def routing_root(database_path: str | Path, root: str | Path | None = None) -> Path:
    configured = os.environ.get("FRAGARACH_ROUTING_ROOT")
    base = Path(root or configured).expanduser() if root or configured else DEFAULT_ROOT
    return base / _database_identity(database_path)


def _paths(database_path: str | Path, root: str | Path | None = None) -> dict[str, Path]:
    base = routing_root(database_path, root)
    return {
        "root": base,
        "revisions": base / "revisions",
        "drafts": base / "drafts",
        "audit": base / "audit",
        "active": base / "active.json",
        "lock": base / "routing.lock",
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _active_revision(database_path: str | Path, root: str | Path | None = None) -> dict[str, Any] | None:
    paths = _paths(database_path, root)
    pointer = _read_json(paths["active"])
    if pointer.get("contract") != ACTIVE_CONTRACT:
        return None
    revision = str(pointer.get("routing_revision") or "")
    value = _read_json(paths["revisions"] / f"{revision}.json")
    return value if value.get("contract") == REVISION_CONTRACT else None


def _seed_revision(database_path: str | Path) -> dict[str, Any]:
    try:
        universe_revision = str(active_universe(database_path)["revision"])
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        # Compatibility databases used by bridge tooling can pre-date the
        # complete Estate schema.  They still inherit the shipped order and
        # must not be made unreadable merely to calculate its seed identity.
        universe_revision = "PRE_ESTATE_SCHEMA"
    revision = hashlib.sha256(
        json.dumps({"database": _database_identity(database_path), "universe": universe_revision,
                    "default": ESTATE_DEFAULT_ORDER}, sort_keys=True).encode()
    ).hexdigest()
    return {
        "contract": REVISION_CONTRACT,
        "routing_revision": revision,
        "parent_revision": None,
        "created_at_utc": None,
        "activated_at_utc": None,
        "operator_reason": "SHIPPED_ESTATE_DEFAULT",
        "estate_default_order": list(ESTATE_DEFAULT_ORDER),
        "lane_overrides": {},
        "source": "SHIPPED_CONFIGURATION_SEED",
    }


def current_revision(database_path: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    return _active_revision(database_path, root) or _seed_revision(database_path)


def _registration_last_sources(database_path: str | Path) -> dict[tuple[str, str], dict[str, Any]]:
    database = Path(database_path).expanduser().resolve()
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        # Ingest history is append-only and can contain hundreds of thousands
        # of rows.  The routing workspace needs an operational hint, not an
        # exhaustive evidence replay, so inspect the bounded recent tail and
        # retain the first committed receipt for each lane.
        rows = connection.execute(
            """SELECT json_extract(detail,'$.asset'),
                      json_extract(detail,'$.timeframe'),
                      json_extract(detail,'$.provider'),
                      json_extract(detail,'$.provider_symbol'),finished_at_utc
               FROM ingest_runs
               WHERE rowid > (SELECT max(rowid)-50000 FROM ingest_runs)
                 AND status='committed'
               ORDER BY rowid DESC"""
        ).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        if "connection" in locals():
            connection.close()
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if row[0] and row[1]:
            result.setdefault((str(row[0]), str(row[1])), {
                "provider": row[2], "provider_symbol": row[3], "receipt_time": row[4],
            })
    return result


def _scheduler_lanes(database_path: str | Path) -> dict[str, dict[str, Any]]:
    database = Path(database_path).expanduser().resolve()
    state = SchedulerStateStore(database, Path(f"{database}.scheduler.json")).load() or {}
    lanes = state.get("lanes")
    return {
        str(key): dict(value) for key, value in lanes.items()
        if isinstance(lanes, dict) and isinstance(value, dict)
    } if isinstance(lanes, dict) else {}


def _registrations(database_path: str | Path) -> dict[str, dict[str, Any]]:
    database = Path(database_path).expanduser().resolve()
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        rows = connection.execute(
            """SELECT asset,asset_class,provider_id,provider_symbol
               FROM instrument_registrations
               WHERE timeframe='D1' AND registration_status='ACTIVE'"""
        ).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        if "connection" in locals():
            connection.close()
    return {
        str(row[0]): {
            "asset_class": row[1], "provider": row[2], "provider_symbol": row[3],
        }
        for row in rows if row[0]
    }


def _mt5_candidates(database_path: str | Path, lanes: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    database = Path(database_path).expanduser().resolve()
    support = Path(f"{database}.read-only-clients")
    try:
        live = authorised_routes(support, database=database)
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        live = {}
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for lane in lanes:
        symbol = str(lane["symbol"])
        timeframe = str(lane["timeframe"])
        reviewed = approved_route(symbol, str(lane["asset_class"]), timeframe)
        if reviewed is None:
            continue
        current = live.get((symbol, timeframe))
        candidates[(symbol, timeframe)] = {
            "provider": "MT5_BRIDGE",
            "provider_symbol": reviewed["provider_symbol"],
            "mapping_class": reviewed["mapping_class"],
            "authority_source": reviewed["authority_source"],
            "capability_state": "AVAILABLE" if current else "UNAVAILABLE",
            "credential_state": "AVAILABLE",
            "entitlement_state": "AVAILABLE",
            "node_id": reviewed.get("node_id"),
            "reviewed": True,
        }
    return candidates


def _candidate_rows(database_path: str | Path, lanes: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    active_keys = {(str(item["symbol"]), str(item["timeframe"])) for item in lanes}
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = {key: {} for key in active_keys}
    profiles = load_provider_profiles()
    registrations = _registrations(database_path)
    facts = load_provider_facts(database_path).get("mappings", {})
    credentials = credential_map()
    for lane in lanes:
        symbol, timeframe = str(lane["symbol"]), str(lane["timeframe"])
        registration = registrations.get(symbol, {})
        for profile in profiles:
            resolved = facts.get(f"{profile.provider}:{symbol}") if isinstance(facts, dict) else None
            mapping = mapping_authority(
                profile, symbol=symbol, timeframe=timeframe,
                primary_provider=registration.get("provider"),
                primary_symbol=registration.get("provider_symbol"),
                resolved_mapping=(dict(resolved) if isinstance(resolved, dict) else None),
            )
            mapping_class = str(mapping.get("mapping_class") or "").upper()
            if (
                not mapping.get("direct_real_eligible")
                or not mapping.get("provider_symbol")
                or mapping_class not in DIRECT_MAPPING_CLASSES
                or mapping.get("timeframe_supported") is False
            ):
                continue
            credential_state = (
                "AVAILABLE"
                if not profile.credential_environment or credentials.get(profile.provider)
                else "CREDENTIAL_REQUIRED"
            )
            capability_state = (
                "PROVIDER_DISABLED" if not profile.enabled
                else "CREDENTIAL_REQUIRED" if credential_state != "AVAILABLE"
                else "AVAILABLE"
            )
            unavailable_reason = None
            if (
                str(lane.get("asset_class") or "").upper() == "CRYPTO"
                and timeframe != "D1"
                and profile.provider == "TWELVE_DATA"
                and not mapping.get("crypto_intraday_approved")
            ):
                capability_state = "UNAVAILABLE"
                unavailable_reason = "CRYPTO_INTRADAY_NOT_APPROVED"
            grouped[(symbol, timeframe)][profile.provider] = {
                "provider": profile.provider,
                "provider_symbol": mapping.get("provider_symbol"),
                "mapping_class": mapping_class,
                "authority_source": mapping.get("authority_source"),
                "capability_state": capability_state,
                "credential_state": credential_state,
                "entitlement_state": profile.entitlement_state,
                "unavailable_reason": unavailable_reason,
                "reviewed": True,
            }
    for key, candidate in _mt5_candidates(database_path, lanes).items():
        grouped.setdefault(key, {})["MT5_BRIDGE"] = candidate
    order_index = {provider: index for index, provider in enumerate(ESTATE_DEFAULT_ORDER)}
    return {
        key: sorted(values.values(), key=lambda item: (order_index.get(str(item["provider"]), 999), str(item["provider"])))
        for key, values in grouped.items()
    }


def _override_for(revision: dict[str, Any], symbol: str, timeframe: str) -> dict[str, Any] | None:
    overrides = revision.get("lane_overrides")
    value = overrides.get(f"{symbol.upper()}:{timeframe.upper()}") if isinstance(overrides, dict) else None
    return dict(value) if isinstance(value, dict) else None


def _ordered_candidates(candidates: list[dict[str, Any]], override: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    by_provider = {str(item["provider"]): dict(item) for item in candidates}
    disabled = {
        str(item).upper() for item in (override or {}).get("disabled_providers", [])
    }
    requested = [
        str(item).upper() for item in (override or {}).get("provider_order", [])
    ] if override else list(ESTATE_DEFAULT_ORDER)
    complete = requested + [item for item in ESTATE_DEFAULT_ORDER if item not in requested]
    complete.extend(sorted(provider for provider in by_provider if provider not in complete))
    ordered = []
    for provider in complete:
        if provider not in by_provider:
            continue
        row = by_provider[provider]
        row["enabled"] = provider not in disabled
        row["order"] = len(ordered) + 1
        ordered.append(row)
    return ordered, sorted(disabled)


def routing_snapshot(database_path: str | Path, *, root: str | Path | None = None) -> dict[str, Any]:
    universe = active_universe(database_path)
    lanes = [dict(item) for _, item in sorted(universe["lanes"].items())]
    candidates = _candidate_rows(
        database_path, [lane for lane in lanes if lane["active"]],
    )
    revision = current_revision(database_path, root)
    last_sources = _registration_last_sources(database_path)
    scheduler_lanes = _scheduler_lanes(database_path)
    ledger_lanes = latest_attempts_by_lane(
        database_path, routing_revision=str(revision["routing_revision"]),
    )
    projected = []
    attention = []
    for lane in lanes:
        symbol, timeframe = str(lane["symbol"]), str(lane["timeframe"])
        active = bool(lane["active"])
        override = _override_for(revision, symbol, timeframe) if active else None
        ordered, disabled = _ordered_candidates(candidates.get((symbol, timeframe), []), override)
        enabled = [
            item for item in ordered
            if item["enabled"] and item.get("capability_state") == "AVAILABLE"
        ]
        derived = timeframe in DERIVED_TIMEFRAMES
        ledger_attempts = ledger_lanes.get(f"{symbol}:{timeframe}", [])
        exhausted = (
            len(ledger_attempts) >= 3
            and str(ledger_attempts[-1].get("outcome") or "") in {
                "MT5_BRIDGE_REQUEST_EXPIRED", "PROVIDER_FAILURE",
                "MT5_BRIDGE_HEALTH_FAILED", "MT5_BRIDGE_FAILED",
            }
        )
        state = (
            "INACTIVE" if not active else "DERIVED" if derived
            else "ATTEMPT_LIMIT_REACHED" if exhausted
            else "EXECUTABLE" if enabled else "NO_PROVIDER_FAIL_CLOSED"
        )
        scheduler_lane = scheduler_lanes.get(f"{symbol}:{timeframe}", {})
        attempts_by_boundary = scheduler_lane.get("provider_attempts_by_boundary", {})
        attempt_boundary = next(reversed(attempts_by_boundary), None) if isinstance(attempts_by_boundary, dict) else None
        attempt_providers = list(attempts_by_boundary.get(attempt_boundary, [])) if attempt_boundary else []
        if ledger_attempts:
            attempt_boundary = str(ledger_attempts[0]["expected_boundary"])
            attempt_providers = [str(item["provider"]) for item in ledger_attempts]
        record = {
            "id": f"{symbol}:{timeframe}",
            "active": active,
            "lifecycle_state": lane.get("lifecycle_state"),
            "ineligibility_reason": lane.get("ineligibility_reason"),
            "symbol": symbol,
            "timeframe": timeframe,
            "asset_class": lane.get("asset_class"),
            "market": lane.get("group"),
            "calendar_identifier": lane.get("calendar_identifier"),
            "derivation_state": "DERIVED_FROM_M5" if derived else "DIRECT",
            "inheritance": "LANE_OVERRIDE" if override else "ESTATE_DEFAULT",
            "operator_reason": override.get("operator_reason") if override else None,
            "override_activated_at_utc": override.get("activated_at_utc") if override else None,
            "candidates": ordered,
            "configured_provider_order": [item["provider"] for item in ordered if item["enabled"]],
            "disabled_providers": disabled,
            "effective_provider_order": [item["provider"] for item in enabled],
            "primary_provider": enabled[0]["provider"] if enabled else None,
            "primary_provider_symbol": enabled[0].get("provider_symbol") if enabled else None,
            "route_state": state,
            "last_used": last_sources.get((symbol, timeframe)),
            "attempt_state": {
                "boundary": attempt_boundary,
                "count": len(attempt_providers),
                "cap": 3,
                "providers": attempt_providers,
                "last_outcome": (
                    ledger_attempts[-1].get("outcome")
                    if ledger_attempts else scheduler_lane.get("result")
                ),
                "next_action": scheduler_lane.get("queue_state") or scheduler_lane.get("reason"),
            },
        }
        projected.append(record)
        if state in {"NO_PROVIDER_FAIL_CLOSED", "ATTEMPT_LIMIT_REACHED"}:
            attention.append({"lane": record["id"], "reason": state})
    return {
        "contract": SNAPSHOT_CONTRACT,
        "routing_revision": revision["routing_revision"],
        "generated_at_utc": _utc_now(),
        "active_revision": {
            "parent": revision.get("parent_revision"),
            "activated_at_utc": revision.get("activated_at_utc"),
            "operator_reason": revision.get("operator_reason"),
        },
        "estate_default_order": list(ESTATE_DEFAULT_ORDER),
        "providers": provider_catalogue_snapshot(database_path, root=root, lane_rows=projected)["providers"],
        "lanes": projected,
        "attention": attention,
        "source_revisions": {"active_universe": universe["revision"]},
    }


def provider_catalogue_snapshot(
    database_path: str | Path, *, root: str | Path | None = None,
    lane_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lanes = lane_rows
    if lanes is None:
        universe = active_universe(database_path)
        lane_facts = [dict(item) for _, item in sorted(universe["active_lanes"].items())]
        candidates = _candidate_rows(database_path, lane_facts)
        revision = current_revision(database_path, root)
        lanes = []
        for lane in lane_facts:
            symbol, timeframe = str(lane["symbol"]), str(lane["timeframe"])
            ordered, disabled = _ordered_candidates(candidates.get((symbol, timeframe), []), _override_for(revision, symbol, timeframe))
            lanes.append({"symbol": symbol, "timeframe": timeframe, "candidates": ordered,
                          "effective_provider_order": [
                              item["provider"] for item in ordered
                              if item["enabled"] and item.get("capability_state") == "AVAILABLE"
                          ],
                          "disabled_providers": disabled})
    profiles = {item.provider: item for item in load_provider_profiles()}
    provider_names = set(ESTATE_DEFAULT_ORDER)
    provider_names.update(
        str(candidate["provider"]) for lane in lanes for candidate in lane.get("candidates", [])
    )
    providers = []
    for provider in sorted(provider_names, key=lambda value: (ESTATE_DEFAULT_ORDER.index(value) if value in ESTATE_DEFAULT_ORDER else 999, value)):
        profile = profiles.get(provider)
        candidate_rows = [
            (lane, candidate) for lane in lanes for candidate in lane.get("candidates", [])
            if candidate.get("provider") == provider
        ]
        symbols = sorted({str(lane["symbol"]) for lane, _ in candidate_rows})
        timeframes = sorted({str(lane["timeframe"]) for lane, _ in candidate_rows})
        primary_count = sum(lane.get("effective_provider_order", [None])[0] == provider for lane, _ in candidate_rows if lane.get("effective_provider_order"))
        enabled_count = sum(provider in lane.get("effective_provider_order", []) for lane, _ in candidate_rows)
        bridge_nodes = []
        if provider == "MT5_BRIDGE":
            node_ids = sorted({str(item.get("node_id")) for _, item in candidate_rows if item.get("node_id")})
            for node_id in node_ids:
                node_rows = [(lane, item) for lane, item in candidate_rows if item.get("node_id") == node_id]
                bridge_nodes.append({
                    "node_id": node_id,
                    "display_name": "Eightcap MT5 - Crypto" if "eightcap" in node_id else "Fusion MT5 - Markets",
                    "current_estate_symbols": sorted({str(lane["symbol"]) for lane, _ in node_rows}),
                    "reviewed_lane_count": len(node_rows),
                    "available_lane_count": sum(item.get("capability_state") == "AVAILABLE" for _, item in node_rows),
                })
        providers.append({
            "provider": provider,
            "enabled": bool(profile.enabled) if profile else True,
            "credential_state": next((item.get("credential_state") for _, item in candidate_rows if item.get("credential_state")), "NOT_REQUIRED"),
            "entitlement_state": next((item.get("entitlement_state") for _, item in candidate_rows if item.get("entitlement_state")), "AVAILABLE"),
            "supported_asset_classes": list(profile.supported_asset_classes) if profile else ["BROKER_REVIEWED_ESTATE"],
            "supported_timeframes": list(profile.supported_timeframes) if profile else sorted(timeframes),
            "current_estate_symbols": symbols,
            "active_primary_lane_count": primary_count,
            "active_fallback_lane_count": max(enabled_count - primary_count, 0),
            "reviewed_candidate_lane_count": len(candidate_rows),
            "operational_limit": int(profile.operational_limit or profile.request_limit) if profile else None,
            "concurrency_limit": profile.concurrency_limit if profile else None,
            "additional_symbols_available": provider in {"MT5_BRIDGE", "BINANCE", "COINGECKO", "COINGECKO_DEX", "TWELVE_DATA"},
            "catalogue_scope": "CURRENT_FRAGARACH_ESTATE_ONLY",
            "bridge_nodes": bridge_nodes,
        })
    return {
        "contract": CATALOGUE_CONTRACT,
        "routing_revision": current_revision(database_path, root)["routing_revision"],
        "generated_at_utc": _utc_now(),
        "freshness_state": "CURRENT",
        "providers": providers,
    }


def effective_provider_order(
    database_path: str | Path, *, symbol: str, timeframe: str,
    root: str | Path | None = None,
) -> tuple[str, ...]:
    revision = current_revision(database_path, root)
    override = _override_for(revision, symbol, timeframe)
    disabled = {str(item).upper() for item in (override or {}).get("disabled_providers", [])}
    requested = [str(item).upper() for item in (override or {}).get("provider_order", [])] if override else list(ESTATE_DEFAULT_ORDER)
    order = requested + [provider for provider in ESTATE_DEFAULT_ORDER if provider not in requested]
    return tuple(provider for provider in order if provider not in disabled)


def _lane_from_snapshot(snapshot: dict[str, Any], symbol: str, timeframe: str) -> dict[str, Any]:
    lane_id = f"{symbol.strip().upper()}:{timeframe.strip().upper()}"
    lane = next((item for item in snapshot["lanes"] if item["id"] == lane_id), None)
    if lane is None:
        raise RoutingServiceError(f"UNKNOWN_ACTIVE_LANE:{lane_id}")
    if not lane.get("active"):
        raise RoutingServiceError(f"INACTIVE_LANE_CANNOT_ROUTE:{lane_id}")
    return lane


def save_draft(
    database_path: str | Path, *, symbol: str, timeframe: str,
    provider_order: Iterable[str], disabled_providers: Iterable[str],
    operator_reason: str, draft_id: str | None = None,
    restore_default: bool = False, root: str | Path | None = None,
) -> dict[str, Any]:
    snapshot = routing_snapshot(database_path, root=root)
    lane = _lane_from_snapshot(snapshot, symbol, timeframe)
    reviewed = {str(item["provider"]) for item in lane["candidates"]}
    requested = [str(item).strip().upper() for item in provider_order if str(item).strip()]
    disabled = sorted({str(item).strip().upper() for item in disabled_providers if str(item).strip()})
    if len(requested) != len(set(requested)):
        raise RoutingServiceError("DUPLICATE_PROVIDER_IN_ORDER")
    unknown = (set(requested) | set(disabled)) - reviewed
    if unknown:
        raise RoutingServiceError(f"UNREVIEWED_LANE_PROVIDER:{','.join(sorted(unknown))}")
    if not restore_default and set(requested) != reviewed:
        missing = reviewed - set(requested)
        requested.extend(provider for provider in ESTATE_DEFAULT_ORDER if provider in missing)
        requested.extend(sorted(missing - set(requested)))
    reason = operator_reason.strip()
    if not reason:
        raise RoutingServiceError("OPERATOR_REASON_REQUIRED")
    identifier = draft_id or f"draft-{uuid.uuid4().hex}"
    payload = {
        "contract": DRAFT_CONTRACT,
        "draft_id": identifier,
        "created_at_utc": _utc_now(),
        "base_revision": snapshot["routing_revision"],
        "lane": lane["id"],
        "symbol": lane["symbol"],
        "timeframe": lane["timeframe"],
        "provider_order": requested,
        "disabled_providers": disabled,
        "operator_reason": reason,
        "restore_default": bool(restore_default),
    }
    _atomic_json(_paths(database_path, root)["drafts"] / f"{identifier}.json", payload)
    return payload


def read_draft(database_path: str | Path, draft_id: str, *, root: str | Path | None = None) -> dict[str, Any]:
    draft = _read_json(_paths(database_path, root)["drafts"] / f"{draft_id}.json")
    if draft.get("contract") != DRAFT_CONTRACT:
        raise RoutingServiceError(f"UNKNOWN_ROUTING_DRAFT:{draft_id}")
    return draft


def validate_draft(database_path: str | Path, draft_id: str, *, root: str | Path | None = None) -> dict[str, Any]:
    draft = read_draft(database_path, draft_id, root=root)
    snapshot = routing_snapshot(database_path, root=root)
    lane = _lane_from_snapshot(snapshot, str(draft["symbol"]), str(draft["timeframe"]))
    reviewed = {str(item["provider"]): item for item in lane["candidates"]}
    issues = []
    if draft.get("base_revision") != snapshot["routing_revision"]:
        issues.append("BASE_ROUTING_REVISION_CHANGED")
    if not draft.get("restore_default"):
        for provider in draft.get("provider_order", []):
            if provider not in reviewed:
                issues.append(f"UNREVIEWED_LANE_PROVIDER:{provider}")
        for provider in draft.get("disabled_providers", []):
            if provider not in reviewed:
                issues.append(f"UNREVIEWED_DISABLED_PROVIDER:{provider}")
    configured = [] if draft.get("restore_default") else [
        provider for provider in draft.get("provider_order", [])
        if provider not in set(draft.get("disabled_providers", []))
    ]
    if draft.get("restore_default"):
        default_candidates, _ = _ordered_candidates(list(lane["candidates"]), None)
        configured = [item["provider"] for item in default_candidates]
    effective = [
        provider for provider in configured
        if reviewed.get(provider, {}).get("capability_state") == "AVAILABLE"
    ]
    warnings = ["LANE_WILL_FAIL_CLOSED"] if not effective and not lane.get("derivation_state", "").startswith("DERIVED") else []
    return {
        "contract": "fragarach_ii.routing_draft_validation.v2",
        "draft_id": draft_id,
        "valid": not issues,
        "activation_gate": ACTIVATION_GATE,
        "issues": issues,
        "warnings": warnings,
        "lane": lane["id"],
        "before_order": lane["effective_provider_order"],
        "after_order": effective,
        "configured_after_order": configured,
        "disabled_providers": draft.get("disabled_providers", []),
        "restore_default": bool(draft.get("restore_default")),
        "affected_lane_count": 1,
    }


def activate_draft(database_path: str | Path, draft_id: str, *, root: str | Path | None = None) -> dict[str, Any]:
    if ACTIVATION_GATE:
        raise RoutingServiceError(ACTIVATION_GATE)
    paths = _paths(database_path, root)
    paths["root"].mkdir(parents=True, exist_ok=True, mode=0o700)
    with paths["lock"].open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        validation = validate_draft(database_path, draft_id, root=root)
        if not validation["valid"]:
            raise RoutingServiceError("ROUTING_DRAFT_INVALID:" + ",".join(validation["issues"]))
        draft = read_draft(database_path, draft_id, root=root)
        current = current_revision(database_path, root)
        overrides = dict(current.get("lane_overrides") or {})
        lane_id = str(draft["lane"])
        activated_at = _utc_now()
        if draft.get("restore_default"):
            overrides.pop(lane_id, None)
        else:
            overrides[lane_id] = {
                "provider_order": list(draft["provider_order"]),
                "disabled_providers": list(draft["disabled_providers"]),
                "operator_reason": draft["operator_reason"],
                "activated_at_utc": activated_at,
            }
        current_snapshot = routing_snapshot(database_path, root=root)
        effective_lane_routes = []
        for lane in current_snapshot["lanes"]:
            lane_override = overrides.get(str(lane["id"]))
            ordered, disabled = _ordered_candidates(
                list(lane.get("candidates", [])),
                dict(lane_override) if isinstance(lane_override, dict) else None,
            )
            effective = [
                item for item in ordered
                if item.get("enabled") and item.get("capability_state") == "AVAILABLE"
            ]
            effective_lane_routes.append({
                "lane": lane["id"],
                "configured_provider_order": [
                    item["provider"] for item in ordered if item.get("enabled")
                ],
                "disabled_providers": disabled,
                "effective_provider_order": [item["provider"] for item in effective],
                "representations": [{
                    "provider": item["provider"],
                    "provider_symbol": item.get("provider_symbol"),
                    "mapping_class": item.get("mapping_class"),
                    "authority_source": item.get("authority_source"),
                    "capability_state": item.get("capability_state"),
                    "node_id": item.get("node_id"),
                } for item in ordered],
            })
        revision_body = {
            "contract": REVISION_CONTRACT,
            "parent_revision": current["routing_revision"],
            "created_at_utc": activated_at,
            "activated_at_utc": activated_at,
            "operator_reason": draft["operator_reason"],
            "estate_default_order": list(ESTATE_DEFAULT_ORDER),
            "lane_overrides": overrides,
            "effective_lane_routes": effective_lane_routes,
            "source_revisions": dict(current_snapshot.get("source_revisions") or {}),
            "source": "OPERATOR_ACTIVATION",
        }
        digest = hashlib.sha256(json.dumps(revision_body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        revision = {**revision_body, "routing_revision": digest, "content_hash": f"sha256:{digest}"}
        _atomic_json(paths["revisions"] / f"{digest}.json", revision)
        _atomic_json(paths["active"], {
            "contract": ACTIVE_CONTRACT,
            "routing_revision": digest,
            "activated_at_utc": activated_at,
            "database_identity": _database_identity(database_path),
        })
        receipt_id = f"activation-{uuid.uuid4().hex}"
        receipt = {
            "contract": AUDIT_CONTRACT,
            "activation_id": receipt_id,
            "operation_id": receipt_id,
            "draft_id": draft_id,
            "routing_revision": digest,
            "parent_revision": current["routing_revision"],
            "activated_at_utc": activated_at,
            "operator_reason": draft["operator_reason"],
            "affected_lanes": [lane_id],
            "restore_default": bool(draft.get("restore_default")),
            "validation": validation,
        }
        _atomic_json(paths["audit"] / f"{receipt_id}.json", receipt)
        return receipt


def restore_estate_default(
    database_path: str | Path, *, symbol: str, timeframe: str,
    operator_reason: str, root: str | Path | None = None,
) -> dict[str, Any]:
    draft = save_draft(
        database_path, symbol=symbol, timeframe=timeframe, provider_order=(),
        disabled_providers=(), operator_reason=operator_reason,
        restore_default=True, root=root,
    )
    return activate_draft(database_path, str(draft["draft_id"]), root=root)


__all__ = [
    "CATALOGUE_CONTRACT", "ESTATE_DEFAULT_ORDER", "RoutingServiceError",
    "activate_draft", "current_revision", "effective_provider_order",
    "provider_catalogue_snapshot", "read_draft", "restore_estate_default",
    "routing_root", "routing_snapshot", "save_draft", "validate_draft",
]
