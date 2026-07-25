"""Operational Twelve Data representation and timeframe facts for SPEC-048.

The store is deliberately outside the canonical database.  It contains bounded
resolution evidence and classifications, never credentials or full payloads.
"""

from __future__ import annotations

import hashlib
import fcntl
import json
import os
import re
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

from .providers.config import load_provider_config
from .providers.http import BoundedHttpsTransport, HttpRequest, HttpTransport
from .twelve_data_credit import credited_send
from .retirement import is_retired
from .scheduler_integrity import active_universe
from .storage import open_read_only


PROVIDER_FACTS_CONTRACT = "fragarach_ii.provider_facts.v1"
PROVIDER_FACTS_RESOLVER_VERSION = 1
TIMEFRAME_INTERVALS = {"M5": "5min", "M30": "30min", "H1": "1h", "D1": "1day"}
CONTROLLED_OUTCOMES = {
    "RESOLVED_AUTOMATICALLY", "PROVIDER_NOT_FOUND", "PROVIDER_LOOKUP_FAILED",
    "CREDENTIAL_MISSING", "CREDENTIAL_INVALID", "ENTITLEMENT_BLOCKED",
    "REPRESENTATION_AMBIGUOUS", "TIMEFRAME_SUPPORTED", "TIMEFRAME_UNSUPPORTED",
    "RETIRED_NON_ACTIONABLE",
}
MATERIAL_DECISIONS = {"REPRESENTATION_AMBIGUOUS", "DEFERRED"}
REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config/market_registry/registry.v1.json"


class ProviderFactsError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        if code not in CONTROLLED_OUTCOMES and code not in {"INVALID_DECISION", "INVALID_TIMEFRAME"}:
            raise ValueError(f"uncontrolled provider-facts error: {code}")
        self.code = code
        super().__init__(message)


def provider_facts_path(database_path: str | Path) -> Path:
    database = Path(database_path).expanduser().resolve()
    return database.with_suffix(f"{database.suffix}.provider-facts.json")


def load_provider_facts(database_path: str | Path) -> dict[str, object]:
    path = provider_facts_path(database_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    if value.get("contract") != PROVIDER_FACTS_CONTRACT:
        value = {
            "contract": PROVIDER_FACTS_CONTRACT,
            "resolver_version": PROVIDER_FACTS_RESOLVER_VERSION,
            "revision": 0,
            "capability_projection_revision": 0,
            "updated_at": None,
            "credential_state": "Missing",
            "mappings": {},
            "lookup_failures": {},
            "retired_non_actionable": {},
            "reconciliation": None,
        }
    for key in ("mappings", "lookup_failures", "retired_non_actionable"):
        if not isinstance(value.get(key), dict):
            value[key] = {}
    value.setdefault("revision", 0)
    value.setdefault("capability_projection_revision", value["revision"])
    return value


def save_provider_facts(database_path: str | Path, facts: dict[str, object]) -> None:
    path = provider_facts_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                current = {}
            current_revision = int(current.get("revision", 0) or 0)
            expected_revision = int(facts.get("revision", 0) or 0)
            if (
                current_revision > expected_revision
                and _provider_authority_payload(current) != _provider_authority_payload(facts)
            ):
                raise RuntimeError(
                    f"STALE_PROVIDER_FACT_REVISION: expected {expected_revision}, current {current_revision}"
                )
            changed = not path.exists() or _provider_authority_payload(current) != _provider_authority_payload(facts)
            revision = current_revision + 1 if changed else current_revision
            facts["revision"] = revision
            facts["capability_projection_revision"] = revision
            payload = json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _provider_authority_payload(facts: dict[str, object]) -> dict[str, object]:
    """Return only stored facts that can change current provider eligibility."""

    return {
        key: facts.get(key)
        for key in (
            "resolver_version", "credential_state", "mappings", "lookup_failures",
            "retired_non_actionable",
        )
    }


def representation_mapping(
    database_path: str | Path, provider: str, canonical_symbol: str
) -> dict[str, object] | None:
    mapping = load_provider_facts(database_path)["mappings"].get(
        f"{provider.upper()}:{canonical_symbol.upper()}"
    )
    return dict(mapping) if isinstance(mapping, dict) else None


def resolve_exact_fx_mapping_for_admission(
    database_path: str | Path,
    *,
    canonical_symbol: str,
    base_asset: str,
    quote_asset: str,
    instrument_type: str,
    aliases: tuple[str, ...] = (),
    credential: str | None,
    transport: HttpTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object] | None:
    """Resolve one exact FX representation before Estate registration.

    Admission needs an exact provider representation before it can create a
    provider-bound registration.  This is deliberately a bounded *reference*
    lookup (``symbol_search``), never a historical-data acquisition.  Only the
    same base, quote and Physical Currency representation accepted by
    ``_classify_mapping`` is returned to the caller.
    """

    symbol = canonical_symbol.strip().upper()
    base, quote = base_asset.strip().upper(), quote_asset.strip().upper()
    if not symbol or not base or not quote:
        return None
    now = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC)
    facts = load_provider_facts(database_path)
    key = f"TWELVE_DATA:{symbol}"
    existing = facts["mappings"].get(key)
    if (
        isinstance(existing, dict)
        and existing.get("status") == "RESOLVED_AUTOMATICALLY"
        and existing.get("mapping_class") == "EXACT_REPRESENTATION"
        and existing.get("provider_symbol")
    ):
        return dict(existing)
    if not credential:
        # A missing credential is a real operational fact, but is not an
        # admissible provider mapping.  Preserve the registered/unmapped path
        # so the scheduler can retry after credentials become available.
        facts["credential_state"] = "Missing"
        facts["updated_at"] = now.isoformat()
        save_provider_facts(database_path, facts)
        return None

    canonical = {
        "canonical_symbol": symbol,
        "canonical_base_asset": base,
        "canonical_quote_asset": quote,
        "canonical_instrument_type": instrument_type,
        "canonical_representation": "FX_SPOT_PAIR",
        "canonical_asset_class": "FX",
        "canonical_aliases": list(aliases),
        "display_name": symbol,
        "commissioned_timeframes": list(TIMEFRAME_INTERVALS),
        "existing_provider": None,
        "existing_provider_symbol": None,
        "prior_approved_mapping": None,
        "search_candidates": _search_candidates(symbol, base, quote, list(aliases)),
    }
    network = transport or BoundedHttpsTransport()
    try:
        lookup = _reference_lookup(canonical, credential, network, now)
        if lookup["credential_state"] == "Invalid":
            facts["credential_state"] = "Invalid"
            return None
        mapping = _classify_mapping(canonical, lookup, now)
        facts["credential_state"] = "Configured"
        facts["mappings"][key] = mapping
        facts["lookup_failures"].pop(key, None)
    except Exception as error:
        facts["credential_state"] = "Configured"
        facts["lookup_failures"][key] = {
            "canonical_symbol": symbol,
            "provider": "TWELVE_DATA",
            "outcome": "PROVIDER_LOOKUP_FAILED",
            "reason": f"{type(error).__name__}: {error}",
            "last_attempt": now.isoformat(),
            "what_was_tried": [f"symbol_search:{value}" for value in canonical["search_candidates"]],
            "automatic_next_action": "Retry the bounded reference lookup.",
            "operator_action": "Retry Now",
            "available_actions": ["Retry Now"],
        }
        mapping = None
    finally:
        facts["updated_at"] = now.isoformat()
        save_provider_facts(database_path, facts)
    return dict(mapping) if isinstance(mapping, dict) and mapping.get("mapping_class") == "EXACT_REPRESENTATION" else None


def active_representation_symbols(database_path: str | Path) -> set[str]:
    active, _ = _active_representations(database_path)
    return {str(item["canonical_symbol"]) for item in active}


def provider_facts_snapshot(
    database_path: str | Path, *, credential: str | None = None
) -> dict[str, object]:
    facts = load_provider_facts(database_path)
    active, non_actionable = _active_representations(database_path)
    mappings = [dict(value) for value in facts["mappings"].values() if isinstance(value, dict)]
    active_symbols = {item["canonical_symbol"] for item in active}
    resolved = [item for item in mappings if item.get("canonical_symbol") in active_symbols and item.get("status") in {"RESOLVED_AUTOMATICALLY", "OPERATOR_RESOLVED"}]
    reviews = [item for item in mappings if item.get("canonical_symbol") in active_symbols and item.get("status") in MATERIAL_DECISIONS]
    failures = [dict(value) for value in facts["lookup_failures"].values() if isinstance(value, dict) and value.get("canonical_symbol") in active_symbols]
    retired = list(non_actionable.values())
    stored_credential_state = str(facts.get("credential_state") or "Missing")
    credential_state = "Invalid" if stored_credential_state == "Invalid" else "Configured" if credential else stored_credential_state
    if credential_state not in {"Configured", "Missing", "Invalid"}:
        credential_state = "Missing"
    # Provider Facts began as a Twelve Data representation resolver.  The
    # operational console also needs a governed inventory of every configured
    # provider so public fallbacks are visible instead of looking absent.
    from .acquisition_orchestrator import load_provider_profiles
    from .credentials import CredentialAuthority, CredentialState
    authority = CredentialAuthority()
    inventory = []
    contract_profiles = {
        profile.provider: profile
        for profile in load_provider_profiles(apply_runtime_overrides=False)
    }
    for profile in load_provider_profiles():
        contract_profile = contract_profiles[profile.provider]
        resolution = authority.resolve(profile.provider)
        requires_credential = profile.credential_environment is not None
        access = (
            resolution.state.value if requires_credential
            else "Not required"
        )
        inventory.append({
            "provider": profile.provider,
            "enabled": profile.enabled,
            "credential_requirement": "Required" if requires_credential else "Not required",
            "credential_state": access,
            "entitlement": profile.entitlement_state,
            "request_limit": profile.request_limit,
            "operational_limit": int(profile.operational_limit or profile.request_limit),
            "request_window_seconds": profile.request_window_seconds,
            "concurrency_limit": profile.concurrency_limit,
            "maximum_concurrency_limit": contract_profile.concurrency_limit,
            "approved_mappings": len(profile.mappings),
            "supported_asset_classes": list(profile.supported_asset_classes),
            "supported_timeframes": list(profile.supported_timeframes),
            "rate_policy_verified": profile.rate_policy_verified,
        })
    return {
        "contract": PROVIDER_FACTS_CONTRACT,
        "resolver_version": PROVIDER_FACTS_RESOLVER_VERSION,
        "revision": int(facts.get("revision", 0) or 0),
        "capability_projection_revision": int(
            facts.get("capability_projection_revision", facts.get("revision", 0)) or 0
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "credential_state": credential_state,
        "provider_inventory": inventory,
        "resolved_automatically": sorted(resolved, key=lambda item: str(item.get("canonical_symbol"))),
        "needs_material_review": sorted(reviews, key=lambda item: str(item.get("canonical_symbol"))),
        "credential_or_access_issue": None if credential_state == "Configured" else {
            "outcome": "CREDENTIAL_INVALID" if credential_state == "Invalid" else "CREDENTIAL_MISSING",
            "reason": "Twelve Data credential is invalid." if credential_state == "Invalid" else "Twelve Data credential is missing.",
            "available_actions": ["Configure Twelve Data", "Retry Lookup"],
        },
        "provider_lookup_failed": sorted(failures, key=lambda item: str(item.get("canonical_symbol"))),
        "retired_non_actionable": sorted(retired, key=lambda item: str(item.get("canonical_symbol"))),
        "reconciliation": facts.get("reconciliation"),
    }


def resolve_twelve_data_facts(
    database_path: str | Path,
    *,
    credential: str | None,
    transport: HttpTransport | None = None,
    clock: Callable[[], datetime] | None = None,
    symbols: tuple[str, ...] | None = None,
) -> dict[str, object]:
    now = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC)
    facts = load_provider_facts(database_path)
    active, non_actionable = _active_representations(database_path)
    facts["retired_non_actionable"] = non_actionable
    original = _original_review_rows(database_path)
    requested = {item.upper() for item in symbols} if symbols else None
    targets = [item for item in active if requested is None or item["canonical_symbol"] in requested]
    # Reprocess the SPEC-047 review set first; existing reviewed representation facts
    # outside that set remain valid and need no new network lookup.
    review_symbols = {row["symbol"] for row in original}
    if requested is None and review_symbols:
        # SPEC-047 correctly required no operator review where committed D1
        # evidence already proved an exact provider representation.  Those rows
        # still require the SPEC-048 move from lane evidence to representation-
        # scoped facts; excluding them here made accepted authority disappear
        # from the runtime lookup path as soon as any other row needed review.
        migration_symbols = {
            str(item["canonical_symbol"])
            for item in targets
            if item.get("prior_approved_mapping")
        }
        targets = [
            item for item in targets
            if item["canonical_symbol"] in review_symbols | migration_symbols
        ]
    _migrate_confirmed_evidence_mappings(database_path, facts, targets)
    if not credential:
        facts["credential_state"] = "Missing"
        facts["updated_at"] = now.isoformat()
        facts["reconciliation"] = _reconciliation(facts, original, non_actionable)
        save_provider_facts(database_path, facts)
        return provider_facts_snapshot(database_path, credential=None)

    if requested is None:
        terminal_statuses = {"RESOLVED_AUTOMATICALLY", "OPERATOR_RESOLVED", "DEFERRED"}
        targets = [
            item for item in targets
            if not isinstance(facts["mappings"].get(f"TWELVE_DATA:{item['canonical_symbol']}"), dict)
            or facts["mappings"][f"TWELVE_DATA:{item['canonical_symbol']}"].get("status") not in terminal_statuses
        ]
    network = transport or BoundedHttpsTransport()
    facts["credential_state"] = "Configured"
    for canonical in targets:
        symbol = str(canonical["canonical_symbol"])
        key = f"TWELVE_DATA:{symbol}"
        try:
            lookup = _reference_lookup(canonical, credential, network, now)
            if lookup["credential_state"] == "Invalid":
                facts["credential_state"] = "Invalid"
                facts["lookup_failures"][key] = {
                    "canonical_symbol": symbol,
                    "provider": "TWELVE_DATA",
                    "outcome": "CREDENTIAL_INVALID",
                    "reason": "Twelve Data rejected the configured credential.",
                    "last_attempt": now.isoformat(),
                    "available_actions": ["Configure Twelve Data", "Retry Now"],
                }
                break
            mapping = _classify_mapping(canonical, lookup, now)
            facts["mappings"][key] = mapping
            if mapping.get("status") == "PROVIDER_NOT_FOUND":
                facts["lookup_failures"][key] = {
                    "canonical_symbol": symbol,
                    "provider": "TWELVE_DATA",
                    "outcome": "PROVIDER_NOT_FOUND",
                    "reason": "Twelve Data reference search returned no representation candidate.",
                    "last_attempt": now.isoformat(),
                    "what_was_tried": [f"symbol_search:{candidate}" for candidate in canonical["search_candidates"]],
                    "automatic_next_action": "Retry the bounded reference lookup.",
                    "operator_action": "Retry Now",
                    "available_actions": ["Retry Now"],
                }
            else:
                facts["lookup_failures"].pop(key, None)
        except Exception as error:  # transport and bounded response failures are operational facts
            facts["lookup_failures"][key] = {
                "canonical_symbol": symbol,
                "provider": "TWELVE_DATA",
                "outcome": "PROVIDER_LOOKUP_FAILED",
                "reason": f"{type(error).__name__}: {error}",
                "last_attempt": now.isoformat(),
                "what_was_tried": [f"symbol_search:{candidate}" for candidate in canonical["search_candidates"]],
                "automatic_next_action": "Retry the bounded reference lookup.",
                "operator_action": "Retry Now",
                "available_actions": ["Retry Now"],
            }
    facts["updated_at"] = now.isoformat()
    facts["reconciliation"] = _reconciliation(facts, original, non_actionable)
    save_provider_facts(database_path, facts)
    return provider_facts_snapshot(database_path, credential=credential)


def _migrate_confirmed_evidence_mappings(
    database_path: str | Path,
    facts: dict[str, object],
    targets: list[dict[str, object]],
) -> None:
    """Move already-proven FX authority into the representation fact store.

    This is deliberately narrower than provider discovery: it only accepts a
    consistent exact base/quote symbol from immutable committed ingest runs and
    only publishes timeframe capabilities that those runs actually proved.
    """

    target_symbols = {str(item["canonical_symbol"]) for item in targets}
    if not target_symbols:
        return
    placeholders = ",".join("?" for _ in target_symbols)
    with open_read_only(database_path) as connection:
        rows = connection.execute(
            f"""WITH ranked AS (
                   SELECT json_extract(detail,'$.asset') asset,
                          json_extract(detail,'$.timeframe') timeframe,
                          json_extract(detail,'$.provider_symbol') provider_symbol,
                          ingest_run_id,finished_at_utc,
                          row_number() OVER (
                              PARTITION BY json_extract(detail,'$.asset'),
                                           json_extract(detail,'$.timeframe')
                              ORDER BY finished_at_utc DESC,ingest_run_id DESC
                          ) ordinal
                   FROM ingest_runs
                   WHERE status='committed'
                     AND upper(json_extract(detail,'$.provider'))='TWELVE_DATA'
                     AND json_extract(detail,'$.mapping_state')='CONFIRMED_BY_VALID_EVIDENCE'
                     AND json_extract(detail,'$.asset') IN ({placeholders})
               )
               SELECT asset,timeframe,provider_symbol,ingest_run_id,finished_at_utc
               FROM ranked WHERE ordinal=1
               ORDER BY asset,timeframe""",
            tuple(sorted(target_symbols)),
        ).fetchall()
    evidence: dict[str, list[tuple[object, ...]]] = {}
    for row in rows:
        evidence.setdefault(str(row[0]), []).append(tuple(row))
    mappings = facts.setdefault("mappings", {})
    if not isinstance(mappings, dict):
        return
    for canonical in targets:
        symbol = str(canonical["canonical_symbol"])
        key = f"TWELVE_DATA:{symbol}"
        if isinstance(mappings.get(key), dict):
            continue
        if str(canonical.get("canonical_asset_class") or "").upper() != "FX":
            continue
        prior = canonical.get("prior_approved_mapping")
        rows_for_symbol = evidence.get(symbol, [])
        provider_symbols = {str(row[2]).upper() for row in rows_for_symbol if row[2]}
        if not isinstance(prior, dict) or len(provider_symbols) != 1:
            continue
        provider_symbol = next(iter(provider_symbols))
        provider_base, provider_quote = _split_pair(provider_symbol)
        canonical_base = str(canonical.get("canonical_base_asset") or "").upper()
        canonical_quote = str(canonical.get("canonical_quote_asset") or "").upper()
        if (
            not provider_base
            or not provider_quote
            or provider_base != canonical_base
            or provider_quote != canonical_quote
            or _compact(provider_symbol) != symbol
        ):
            continue
        capabilities = {}
        provenance = {}
        for _, timeframe, _, ingest_run_id, finished_at in rows_for_symbol:
            lane = str(timeframe).upper()
            if lane not in TIMEFRAME_INTERVALS:
                continue
            observed_at = str(finished_at)
            capabilities[lane] = {
                "timeframe": lane,
                "provider_interval": TIMEFRAME_INTERVALS[lane],
                "supported": True,
                "history_availability": "CONFIRMED_BY_COMMITTED_EVIDENCE",
                "maximum_rows": 5000,
                "fragarach_request_ceiling": 4000,
                "entitlement": "AVAILABLE",
                "last_verified": observed_at,
                "verification_method": "IMMUTABLE_COMMITTED_EVIDENCE",
                "reason": "TIMEFRAME_SUPPORTED",
            }
            provenance[lane] = {
                "ingest_run_id": str(ingest_run_id),
                "observed_at": observed_at,
            }
        commissioned = {str(item) for item in canonical.get("commissioned_timeframes", [])}
        if not commissioned or not commissioned.issubset(capabilities):
            continue
        last_verified = max(str(row[4]) for row in rows_for_symbol)
        mappings[key] = {
            "canonical_symbol": symbol,
            "canonical_base_asset": canonical_base,
            "canonical_quote_asset": canonical_quote,
            "canonical_instrument_type": canonical.get("canonical_instrument_type"),
            "provider": "TWELVE_DATA",
            "provider_symbol": provider_symbol,
            "provider_base_asset": provider_base,
            "provider_quote_asset": provider_quote,
            "provider_instrument_type": "Physical Currency",
            "provider_asset_class": "FOREX",
            "venue_or_market": "OTC",
            "market_category": "FOREX",
            "supported_intervals": list(TIMEFRAME_INTERVALS.values()),
            "mapping_classification": "CONFIRMED_AUTHORITY",
            "mapping_class": "EXACT_REPRESENTATION",
            "resolution_method": "IMMUTABLE_CONFIRMED_EVIDENCE_MIGRATION",
            "matching_rule": "STANDARD_FOREX_EXACT_CONFIRMED_EVIDENCE",
            "status": "RESOLVED_AUTOMATICALLY",
            "timeframe_capabilities": capabilities,
            "capability_probe_result": None,
            "resolution_evidence": {
                "prior_approved_mapping": prior,
                "confirmed_timeframes": provenance,
            },
            "resolver_version": PROVIDER_FACTS_RESOLVER_VERSION,
            "effective_time": last_verified,
            "last_verified": last_verified,
            "candidates": [],
        }


def probe_twelve_data_capability(
    database_path: str | Path,
    *,
    canonical_symbol: str,
    timeframe: str,
    credential: str | None,
    transport: HttpTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    if not credential:
        raise ProviderFactsError("CREDENTIAL_MISSING", "Twelve Data credential is missing")
    symbol, lane = canonical_symbol.strip().upper(), timeframe.strip().upper()
    if lane not in TIMEFRAME_INTERVALS:
        raise ProviderFactsError("INVALID_TIMEFRAME", lane)
    facts = load_provider_facts(database_path)
    mapping = facts["mappings"].get(f"TWELVE_DATA:{symbol}")
    if not isinstance(mapping, dict) or mapping.get("mapping_class") not in {"EXACT_REPRESENTATION", "APPROVED_PROVIDER_ALIAS"}:
        raise ProviderFactsError("REPRESENTATION_AMBIGUOUS", f"Resolve {symbol} representation before probing")
    now = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC)
    config = load_provider_config(timeframe=lane)
    target = "/time_series?" + urlencode({
        "symbol": mapping["provider_symbol"], "interval": TIMEFRAME_INTERVALS[lane],
        "outputsize": 3, "timezone": "UTC", "order": "ASC", "format": "JSON",
    })
    network = transport or BoundedHttpsTransport()
    response = credited_send(
        credential, endpoint="time_series", clock=clock,
        send=lambda: network.send(
            HttpRequest(config.provider_host, target, "Fragarach-II/1 SPEC-048"), credential, config
        ),
    )
    checksum = hashlib.sha256(response.body).hexdigest()
    if response.status in {401, 403}:
        facts["credential_state"] = "Invalid"
        save_provider_facts(database_path, facts)
        raise ProviderFactsError("CREDENTIAL_INVALID", "Twelve Data rejected the configured credential")
    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Malformed capability response") from error
    if isinstance(payload, dict) and payload.get("status") == "error":
        code = int(payload.get("code", 0) or 0)
        if code in {401, 403}:
            raise ProviderFactsError("CREDENTIAL_INVALID", "Twelve Data rejected the configured credential")
        raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", str(payload.get("message") or "Provider error"))
    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
    values = payload.get("values", []) if isinstance(payload, dict) else []
    if not isinstance(meta, dict) or not isinstance(values, list):
        raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Malformed capability response")
    if _compact(str(meta.get("symbol", ""))) != _compact(str(mapping["provider_symbol"])):
        raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Response symbol does not match the resolved representation")
    if str(meta.get("interval")) != TIMEFRAME_INTERVALS[lane]:
        raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Response interval does not match the requested timeframe")
    closed, excluded = _closed_valid_rows(values, lane, now)
    outcome = "TIMEFRAME_SUPPORTED" if closed else "PROVIDER_NOT_FOUND"
    capability = {
        "timeframe": lane,
        "provider_interval": TIMEFRAME_INTERVALS[lane],
        "supported": bool(closed),
        "history_availability": "RECENT_SAMPLE_RETURNED" if closed else "EMPTY_RECENT_SAMPLE",
        "maximum_rows": 5000,
        "fragarach_request_ceiling": 4000,
        "entitlement": "AVAILABLE",
        "last_verified": now.isoformat(),
        "verification_method": "BOUNDED_TIME_SERIES_PROBE",
        "reason": outcome,
        "probe_result": {
            "outcome": outcome,
            "requested_rows": 3,
            "closed_rows": len(closed),
            "open_rows_excluded": excluded,
            "response_checksum": checksum,
            "api_credits_used": _api_credits(response),
            "api_credits_left": _integer(response.header("api-credits-left")),
            "canonical_publication": "NONE",
            "sample_price_range": _price_range(closed),
        },
    }
    mapping.setdefault("timeframe_capabilities", {})[lane] = capability
    mapping["capability_probe_result"] = capability["probe_result"]
    mapping["last_verified"] = now.isoformat()
    facts["credential_state"] = "Configured"
    facts["updated_at"] = now.isoformat()
    save_provider_facts(database_path, facts)
    return {
        "contract": "fragarach_ii.twelve_data_capability_probe.v1",
        "canonical_symbol": symbol,
        "provider": "TWELVE_DATA",
        "provider_symbol": mapping["provider_symbol"],
        **capability,
    }


def record_material_decision(
    database_path: str | Path,
    *,
    canonical_symbol: str,
    decision: str,
    candidate_symbol: str,
    decided_at: datetime | None = None,
) -> dict[str, object]:
    controlled = {
        "APPROVE_EXACT": "EXACT_REPRESENTATION",
        "APPROVE_ALIAS": "APPROVED_PROVIDER_ALIAS",
        "MARK_NOT_EQUIVALENT": "NOT_EQUIVALENT",
        "DEFER": None,
    }
    if decision not in controlled:
        raise ProviderFactsError("INVALID_DECISION", decision)
    facts = load_provider_facts(database_path)
    key = f"TWELVE_DATA:{canonical_symbol.strip().upper()}"
    mapping = facts["mappings"].get(key)
    if not isinstance(mapping, dict):
        raise ProviderFactsError("REPRESENTATION_AMBIGUOUS", "No provider candidate is available for review")
    candidates = mapping.get("candidates", [])
    candidate = next((item for item in candidates if item.get("provider_symbol") == candidate_symbol), None)
    if not isinstance(candidate, dict):
        raise ProviderFactsError("REPRESENTATION_AMBIGUOUS", "Selected provider candidate is unavailable")
    now = (decided_at or datetime.now(UTC)).astimezone(UTC)
    if decision == "DEFER":
        mapping["status"] = "DEFERRED"
        mapping["operator_decision"] = {"decision": decision, "decided_at": now.isoformat()}
    else:
        mapping["mapping_class"] = controlled[decision]
        mapping["status"] = "OPERATOR_RESOLVED"
        mapping["provider_symbol"] = candidate_symbol
        mapping["provider_base_asset"] = candidate.get("provider_base_asset")
        mapping["provider_quote_asset"] = candidate.get("provider_quote_asset")
        mapping["provider_instrument_type"] = candidate.get("provider_instrument_type")
        mapping["resolution_method"] = "OPERATOR_MATERIAL_REPRESENTATION_REVIEW"
        mapping["operator_decision"] = {"decision": decision, "decided_at": now.isoformat()}
    facts["updated_at"] = now.isoformat()
    save_provider_facts(database_path, facts)
    return provider_facts_snapshot(database_path)


def approve_reviewed_provider_mapping(
    database_path: str | Path, *, canonical_symbol: str, provider: str,
    provider_symbol: str, timeframe: str, asset_class: str,
    representation_type: str, provider_instrument_type: str,
    decided_at: datetime | None = None,
) -> dict[str, object]:
    """Persist one explicitly selected representation, never a provider guess."""

    canonical = canonical_symbol.strip().upper()
    selected_provider = provider.strip().upper()
    selected_symbol = provider_symbol.strip()
    lane = timeframe.strip().upper()
    if not canonical or not selected_provider or not selected_symbol:
        raise ValueError("REVIEWED_PROVIDER_REPRESENTATION_REQUIRED")
    if lane not in TIMEFRAME_INTERVALS:
        raise ValueError(f"INVALID_TIMEFRAME: {lane}")
    compact = _compact(selected_symbol)
    mapping_class = (
        "EXACT_REPRESENTATION" if compact == canonical
        else "APPROVED_PROVIDER_ALIAS"
    )
    now = (decided_at or datetime.now(UTC)).astimezone(UTC)
    facts = load_provider_facts(database_path)
    key = f"{selected_provider}:{canonical}"
    existing = facts["mappings"].get(key)
    exact_catalogue_crypto=(
        selected_provider=="TWELVE_DATA"
        and asset_class.strip().upper()=="CRYPTO"
        and compact==canonical
    )
    supported_lanes=tuple(TIMEFRAME_INTERVALS) if exact_catalogue_crypto else (lane,)
    capabilities = {
        value: {
            "timeframe": value,
            "provider_interval": TIMEFRAME_INTERVALS[value],
            "supported": True,
            "history_availability": "AVAILABLE_BY_PROVIDER_CONTRACT",
            "maximum_rows": 5000,
            "fragarach_request_ceiling": 5000,
            "entitlement": "AVAILABLE",
            "last_verified": now.isoformat(),
            "verification_method": (
                "TWELVE_DATA_CRYPTO_CATALOGUE_EXACT_REPRESENTATION"
                if exact_catalogue_crypto else "OPERATOR_REVIEWED_DISCOVER_REPRESENTATION"
            ),
            "reason": "TIMEFRAME_SUPPORTED",
        }
        for value in supported_lanes
    }
    mapping = {
        "canonical_symbol": canonical,
        "canonical_base_asset": canonical[:-3] if exact_catalogue_crypto else canonical,
        "canonical_quote_asset": "USD" if exact_catalogue_crypto else None,
        "canonical_instrument_type": representation_type,
        "provider": selected_provider,
        "provider_symbol": selected_symbol,
        "provider_base_asset": canonical[:-3] if exact_catalogue_crypto else canonical,
        "provider_quote_asset": "USD" if exact_catalogue_crypto else None,
        "provider_instrument_type": provider_instrument_type,
        "provider_asset_class": asset_class,
        "venue_or_market": None,
        "market_category": asset_class,
        "supported_intervals": [TIMEFRAME_INTERVALS[value] for value in supported_lanes],
        "mapping_classification": "REVIEWED_AUTHORITY",
        "mapping_class": mapping_class,
        "resolution_method": "OPERATOR_REVIEWED_DISCOVER_REPRESENTATION",
        "matching_rule": "EXACT_SELECTED_PROVIDER_REPRESENTATION",
        "status": "OPERATOR_RESOLVED",
        "timeframe_capabilities": capabilities,
        "capability_probe_result": None,
        "resolution_evidence": {
            "selection_source": "DISCOVER",
            "operator_approved": True,
            "selected_provider": selected_provider,
            "selected_provider_symbol": selected_symbol,
        },
        "operator_decision": {
            "decision": "APPROVE_EXACT" if mapping_class == "EXACT_REPRESENTATION" else "APPROVE_ALIAS",
            "decided_at": now.isoformat(),
        },
        "resolver_version": PROVIDER_FACTS_RESOLVER_VERSION,
        "effective_time": now.isoformat(),
        "last_verified": now.isoformat(),
        "candidates": [],
        "authority_source": (
            "TWELVE_DATA_CRYPTO_CATALOGUE_EXACT_REPRESENTATION"
            if exact_catalogue_crypto else "DISCOVER_REVIEWED_PROVIDER_REPRESENTATION"
        ),
        "crypto_intraday_approved": exact_catalogue_crypto,
    }
    # Preserve the original effective timestamp on an idempotent replay so the
    # provider-fact revision cannot advance without an authority change.
    if isinstance(existing, dict):
        same = all(existing.get(name) == mapping.get(name) for name in (
            "canonical_symbol", "provider", "provider_symbol", "mapping_class", "status"
        )) and bool((existing.get("timeframe_capabilities") or {}).get(lane, {}).get("supported"))
        if same:
            return dict(existing)
    facts["mappings"][key] = mapping
    facts["updated_at"] = now.isoformat()
    save_provider_facts(database_path, facts)
    # Mapping approval can make an already-registered lane operator/actionable
    # and therefore consumer-visible in the catalogue.  Publish every existing
    # lane for this symbol without fabricating a lane that does not exist.
    from .publication_service import enqueue_publication
    with open_read_only(database_path) as connection:
        lanes = [
            (canonical, str(row[0]))
            for row in connection.execute(
                "SELECT timeframe FROM evidence_lanes WHERE asset=?", (canonical,)
            ).fetchall()
        ]
    enqueue_publication(database_path, lanes, trigger="PROVIDER_MAPPING_APPROVAL")
    return mapping


def _active_representations(database_path: str | Path) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    universe = active_universe(database_path)
    active_registry = _active_registry_records()
    active_lanes = universe["active_lanes"]
    with open_read_only(database_path) as connection:
        rows = connection.execute(
            """SELECT asset,asset_class,representation_type,registration_status,
                      provider_id,provider_symbol,identity_json
               FROM instrument_registrations WHERE timeframe='D1' ORDER BY asset"""
        ).fetchall()
        prior_rows = connection.execute(
            """WITH ranked AS (
                   SELECT json_extract(detail,'$.asset') asset,
                          json_extract(detail,'$.provider') provider,
                          json_extract(detail,'$.provider_symbol') provider_symbol,
                          ingest_run_id,finished_at_utc,
                          row_number() OVER (
                              PARTITION BY json_extract(detail,'$.asset')
                              ORDER BY finished_at_utc DESC,ingest_run_id DESC
                          ) ordinal
                   FROM ingest_runs
                   WHERE status='committed'
                     AND json_extract(detail,'$.timeframe')='D1'
                     AND json_extract(detail,'$.mapping_state')='CONFIRMED_BY_VALID_EVIDENCE'
               )
               SELECT asset,provider,provider_symbol,ingest_run_id,finished_at_utc
               FROM ranked WHERE ordinal=1"""
        ).fetchall()
    prior_by_symbol = {str(item[0]): item for item in prior_rows if item[0]}
    result, non_actionable = [], {}
    for row in rows:
        symbol = str(row[0])
        commissioned = sorted(key.split(":", 1)[1] for key in active_lanes if key.startswith(f"{symbol}:"))
        identity = json.loads(row[6]) if row[6] else {}
        registry = active_registry.get(symbol)
        prior = prior_by_symbol.get(symbol)
        inactive_reason = None
        if is_retired(database_path, symbol):
            inactive_reason = "RETIRED_AUTHORITY"
        elif not commissioned:
            inactive_reason = "NO_ACTIVE_COMMISSIONED_LANE"
        elif registry is None and str(identity.get("instrument_type") or "").upper() == "CFD":
            inactive_reason = "NOT_IN_ACTIVE_ESTATE_REGISTRY"
        elif not str(row[3]).startswith("REGISTERED_"):
            inactive_reason = "REGISTRATION_INACTIVE"
        if inactive_reason:
            non_actionable[symbol] = {
                "canonical_symbol": symbol,
                "provider": "TWELVE_DATA",
                "outcome": "RETIRED_NON_ACTIONABLE",
                "reason": inactive_reason,
                "preservation": "REGISTRATION_HISTORY_AND_EVIDENCE_RETAINED",
                "available_actions": ["View Retired History"],
            }
            continue
        registry_facts = registry or {}
        quote = registry_facts.get("quote_currency") or registry_facts.get("currency") or identity.get("trading_currency")
        base = registry_facts.get("base_currency")
        if not base and quote and symbol.endswith(str(quote)):
            base = symbol[:-len(str(quote))]
        result.append({
            "canonical_symbol": symbol,
            "canonical_base_asset": base,
            "canonical_quote_asset": quote,
            "canonical_instrument_type": registry_facts.get("instrument_type") or identity.get("instrument_type"),
            "canonical_representation": registry_facts.get("representation_type") or row[2],
            "canonical_asset_class": row[1],
            "canonical_aliases": registry_facts.get("aliases", []),
            "display_name": registry_facts.get("display_name") or identity.get("display_name") or symbol,
            "commissioned_timeframes": commissioned,
            "search_candidates": _search_candidates(symbol, base, quote, registry_facts.get("aliases")),
            "existing_provider": row[4] or (prior[1] if prior else None),
            "existing_provider_symbol": row[5] or (prior[2] if prior else None),
            "prior_approved_mapping": (
                {
                    "source_scope": "D1_REGISTRATION" if row[4] and row[5] else "D1_COMMITTED_EVIDENCE",
                    "provider": row[4] or (prior[1] if prior else None),
                    "provider_symbol": row[5] or (prior[2] if prior else None),
                    "ingest_run_id": prior[3] if prior else "NOT_APPLICABLE",
                    "observed_at": prior[4] if prior else "REGISTRATION_AUTHORITY",
                    "preservation": "MIGRATED_TO_REPRESENTATION_SCOPE",
                }
                if (row[4] and row[5]) or prior
                else None
            ),
        })
    return result, non_actionable


def _active_registry_records() -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(item["canonical_symbol"]): item
        for item in payload.get("records", [])
        if isinstance(item, dict) and item.get("active") and item.get("canonical_symbol")
    }


def _reference_lookup(
    canonical: dict[str, object], credential: str, transport: HttpTransport, now: datetime
) -> dict[str, object]:
    config = load_provider_config(timeframe="D1")
    candidates, checksums, usages = [], [], []
    for search in canonical["search_candidates"]:
        target = "/symbol_search?" + urlencode({"symbol": search, "outputsize": 30})
        response = credited_send(
            credential, endpoint="symbol_search",
            send=lambda target=target: transport.send(
                HttpRequest(config.provider_host, target, "Fragarach-II/1 SPEC-048"), credential, config
            ),
        )
        checksums.append(hashlib.sha256(response.body).hexdigest())
        usages.append(_api_credits(response))
        if response.status in {401, 403}:
            return {"credential_state": "Invalid", "candidates": [], "response_checksums": checksums}
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Malformed symbol-search response") from error
        if isinstance(payload, dict) and payload.get("status") == "error":
            code = int(payload.get("code", 0) or 0)
            if code in {401, 403}:
                return {"credential_state": "Invalid", "candidates": [], "response_checksums": checksums}
            raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", str(payload.get("message") or "Provider error"))
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Malformed symbol-search results")
        for raw in rows:
            candidate = _provider_candidate(raw)
            if candidate and not any(item["provider_symbol"] == candidate["provider_symbol"] for item in candidates):
                candidates.append(candidate)
        # Exact compact symbol in the first provider result makes the fallback
        # spelling unnecessary and preserves API budget.
        if any(_compact(str(item["provider_symbol"])) == str(canonical["canonical_symbol"]) for item in candidates):
            break
    return {
        "credential_state": "Configured",
        "candidates": _rank_provider_candidates(canonical, candidates)[:12],
        "provider_response_time": now.isoformat(),
        "response_checksums": checksums,
        "api_credits_used": sum(value for value in usages if value is not None),
        "api_usage_accounting": "PROVIDER_RESPONSE_HEADER" if all(value is not None for value in usages) else "ENDPOINT_CONTRACT_WEIGHT",
    }


def _provider_candidate(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    symbol = str(raw.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    base, quote = _split_pair(symbol)
    return {
        "provider_symbol": symbol,
        "provider_description": str(raw.get("instrument_name") or raw.get("name") or symbol),
        "provider_instrument_type": str(raw.get("instrument_type") or raw.get("type") or "UNKNOWN"),
        "provider_asset_class": _provider_asset_class(str(raw.get("instrument_type") or raw.get("type") or "")),
        "provider_base_asset": base,
        "provider_quote_asset": quote or str(raw.get("currency") or "").upper() or None,
        "venue_or_market": str(raw.get("exchange") or raw.get("country") or "OTC"),
        "market_category": str(raw.get("country") or raw.get("exchange") or "UNKNOWN"),
        "supported_intervals": list(TIMEFRAME_INTERVALS.values()),
        "sample_price_range": None,
        "mapping_classification": "CANDIDATE",
    }


def _classify_mapping(
    canonical: dict[str, object], lookup: dict[str, object], now: datetime
) -> dict[str, object]:
    candidates = list(lookup.get("candidates", []))
    exact = [candidate for candidate in candidates if _automatic_exact(canonical, candidate)]
    common = {
        "canonical_symbol": canonical["canonical_symbol"],
        "canonical_base_asset": canonical["canonical_base_asset"],
        "canonical_quote_asset": canonical["canonical_quote_asset"],
        "canonical_instrument_type": canonical["canonical_instrument_type"],
        "provider": "TWELVE_DATA",
        "resolution_evidence": {
            "provider_response_time": lookup.get("provider_response_time"),
            "response_checksums": lookup.get("response_checksums", []),
            "api_credits_used": lookup.get("api_credits_used"),
            "api_usage_accounting": lookup.get("api_usage_accounting"),
            "prior_approved_mapping": (
                canonical.get("prior_approved_mapping")
                if str(canonical.get("existing_provider") or "").upper() == "TWELVE_DATA"
                and canonical.get("existing_provider_symbol")
                else None
            ),
        },
        "resolver_version": PROVIDER_FACTS_RESOLVER_VERSION,
        "effective_time": now.isoformat(),
        "last_verified": now.isoformat(),
        "candidates": candidates,
    }
    if exact:
        chosen = sorted(exact, key=lambda item: str(item["provider_symbol"]))[0]
        capabilities = {
            timeframe: {
                "timeframe": timeframe,
                "provider_interval": interval,
                "supported": True,
                "history_availability": "AVAILABLE_BY_PROVIDER_CONTRACT",
                "maximum_rows": 5000,
                "fragarach_request_ceiling": 4000,
                "entitlement": "AVAILABLE",
                "last_verified": now.isoformat(),
                "verification_method": "APPROVED_TWELVE_DATA_INTERVAL_CONTRACT",
                "reason": "TIMEFRAME_SUPPORTED",
            }
            for timeframe, interval in TIMEFRAME_INTERVALS.items()
        }
        return {
            **common,
            **chosen,
            "mapping_class": "EXACT_REPRESENTATION",
            "resolution_method": "PROVIDER_REFERENCE_EXACT_BASE_QUOTE_AND_INSTRUMENT_CLASS",
            "matching_rule": "STANDARD_FOREX_EXACT" if canonical["canonical_asset_class"] == "FX" else "STANDARD_PRECIOUS_METAL_EXACT",
            "status": "RESOLVED_AUTOMATICALLY",
            "timeframe_capabilities": capabilities,
            "capability_probe_result": None,
        }
    if not candidates:
        return {
            **common,
            "provider_symbol": None,
            "provider_base_asset": None,
            "provider_quote_asset": None,
            "provider_instrument_type": None,
            "mapping_class": None,
            "resolution_method": "PROVIDER_REFERENCE_LOOKUP",
            "matching_rule": None,
            "status": "PROVIDER_NOT_FOUND",
            "timeframe_capabilities": {},
            "available_actions": ["Retry Now"],
        }
    return {
        **common,
        "provider_symbol": None,
        "provider_base_asset": None,
        "provider_quote_asset": None,
        "provider_instrument_type": None,
        "mapping_class": None,
        "resolution_method": "PROVIDER_REFERENCE_MATERIAL_REVIEW_REQUIRED",
        "matching_rule": None,
        "status": "REPRESENTATION_AMBIGUOUS",
        "reason": "Provider candidates do not prove identical economic representation.",
        "timeframe_capabilities": {},
        "available_actions": ["Review Candidates", "Defer"],
    }


def _automatic_exact(canonical: dict[str, object], candidate: dict[str, object]) -> bool:
    if candidate.get("provider_base_asset") != canonical.get("canonical_base_asset"):
        return False
    if candidate.get("provider_quote_asset") != canonical.get("canonical_quote_asset"):
        return False
    canonical_type = str(canonical.get("canonical_instrument_type") or "").upper()
    provider_type = str(candidate.get("provider_instrument_type") or "").upper()
    if any(word in canonical_type for word in ("CFD", "FUTURE", "ETF")):
        return False
    if canonical.get("canonical_asset_class") == "FX":
        return provider_type == "PHYSICAL CURRENCY"
    if canonical.get("canonical_asset_class") == "METALS":
        return provider_type in {"PRECIOUS METAL", "PHYSICAL CURRENCY"}
    return False


def _closed_valid_rows(values: list[object], timeframe: str, now: datetime) -> tuple[list[dict[str, object]], int]:
    seconds = {"M5": 300, "M30": 1800, "H1": 3600, "D1": 86400}[timeframe]
    result, excluded = [], 0
    for raw in values:
        if not isinstance(raw, dict):
            raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Non-object observation")
        timestamp = _provider_datetime(str(raw.get("datetime") or ""))
        if timestamp + timedelta(seconds=seconds) > now:
            excluded += 1
            continue
        try:
            opened, high, low, closed = (Decimal(str(raw[key])) for key in ("open", "high", "low", "close"))
        except (KeyError, InvalidOperation) as error:
            raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Invalid OHLC observation") from error
        if high < max(opened, closed) or low > min(opened, closed) or high < low:
            raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Invalid OHLC relationship")
        result.append({**raw, "_timestamp": timestamp})
    if any(result[index]["_timestamp"] >= result[index + 1]["_timestamp"] for index in range(len(result) - 1)):
        raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Non-increasing observation timestamps")
    return result, excluded


def _price_range(rows: list[dict[str, object]]) -> dict[str, str] | None:
    if not rows:
        return None
    return {
        "low": str(min(Decimal(str(row["low"])) for row in rows)),
        "high": str(max(Decimal(str(row["high"])) for row in rows)),
    }


def _provider_datetime(value: str) -> datetime:
    for candidate in (value, value.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except ValueError:
            continue
    raise ProviderFactsError("PROVIDER_LOOKUP_FAILED", "Invalid provider timestamp")


def _reconciliation(facts: dict[str, object], original: list[dict[str, str]], non_actionable: dict[str, object]) -> dict[str, object]:
    original_symbols = {row["symbol"] for row in original}
    retired_rows = sum(1 for row in original if row["symbol"] in non_actionable)
    mappings = [value for value in facts["mappings"].values() if isinstance(value, dict) and value.get("canonical_symbol") in original_symbols]
    verified = sum(
        1 for mapping in mappings
        for capability in mapping.get("timeframe_capabilities", {}).values()
        if capability.get("supported")
    )
    return {
        "contract": "fragarach_ii.spec048_reconciliation.v1",
        "lane_rows_originally_flagged": len(original),
        "retired_rows_removed": retired_rows,
        "representation_mappings_automatically_resolved": sum(mapping.get("status") == "RESOLVED_AUTOMATICALLY" and mapping.get("mapping_class") == "EXACT_REPRESENTATION" for mapping in mappings),
        "timeframe_capabilities_verified": verified,
        "credential_access_failures": 1 if facts.get("credential_state") in {"Missing", "Invalid"} else 0,
        "provider_lookup_failures": sum(value.get("outcome") == "PROVIDER_LOOKUP_FAILED" for value in facts["lookup_failures"].values() if isinstance(value, dict)),
        "genuine_operator_decisions_remaining": sum(mapping.get("status") in MATERIAL_DECISIONS for mapping in mappings),
        "decision_keys": sorted(f"{mapping.get('canonical_symbol')}×TWELVE_DATA" for mapping in mappings if mapping.get("status") in MATERIAL_DECISIONS),
    }


def _original_review_rows(database_path: str | Path) -> list[dict[str, str]]:
    journal = Path(database_path).expanduser().resolve().with_suffix(f"{Path(database_path).suffix}.scheduler.json")
    from .scheduler_state_store import SchedulerStateStore
    payload = SchedulerStateStore(database_path, journal).load()
    if not isinstance(payload, dict):
        try:
            payload = json.loads(journal.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
    rows = payload.get("spec047_capability_reconciliation", {}).get("rows", [])
    result = []
    for row in rows:
        if not isinstance(row, dict) or row.get("required_operator_decision") == "NONE":
            continue
        lane = str(row.get("lane") or "")
        if ":" not in lane:
            continue
        symbol, timeframe = lane.rsplit(":", 1)
        result.append({"symbol": symbol, "timeframe": timeframe})
    return result


def _search_candidates(symbol: str, base: object, quote: object, aliases: object = None) -> list[str]:
    candidates: list[str] = []
    if base and quote:
        candidates.append(f"{str(base).upper()}/{str(quote).upper()}")
    candidates.append(symbol)
    if isinstance(aliases, list):
        for alias in aliases:
            normalized = str(alias).strip().upper()
            if not normalized:
                continue
            if quote and len(_compact(normalized)) <= 6:
                candidates.append(f"{normalized}/{str(quote).upper()}")
            candidates.append(normalized)
    return list(dict.fromkeys(candidates))


def _rank_provider_candidates(
    canonical: dict[str, object], candidates: list[dict[str, object]]
) -> list[dict[str, object]]:
    aliases = {_compact(str(canonical.get("canonical_symbol") or ""))}
    aliases.update(_compact(str(value)) for value in canonical.get("canonical_aliases", []) if value)
    quote = _compact(str(canonical.get("canonical_quote_asset") or ""))
    asset_class = str(canonical.get("canonical_asset_class") or "").upper()

    def score(candidate: dict[str, object]) -> tuple[int, str]:
        symbol = _compact(str(candidate.get("provider_symbol") or ""))
        base = _compact(str(candidate.get("provider_base_asset") or ""))
        candidate_quote = _compact(str(candidate.get("provider_quote_asset") or ""))
        provider_type = str(candidate.get("provider_instrument_type") or "").upper()
        value = 100 if symbol == _compact(str(canonical.get("canonical_symbol") or "")) else 90 if symbol in aliases else 0
        if base in aliases and quote and candidate_quote == quote:
            value += 80
        if asset_class == "ENERGY" and any(word in provider_type for word in ("COMMODITY", "RESOURCE", "CFD", "FUTURE")):
            value += 40
        if asset_class == "INDICES" and "INDEX" in provider_type:
            value += 40
        if asset_class == "FX" and provider_type == "PHYSICAL CURRENCY":
            value += 40
        return value, str(candidate.get("provider_symbol") or "")

    return sorted(candidates, key=lambda item: (-score(item)[0], score(item)[1]))


def _split_pair(symbol: str) -> tuple[str | None, str | None]:
    parts = symbol.upper().split("/")
    if len(parts) == 2 and all(parts):
        return parts[0], parts[1]
    return None, None


def _provider_asset_class(provider_type: str) -> str:
    value = provider_type.upper()
    if value == "PHYSICAL CURRENCY":
        return "FOREX"
    if value == "PRECIOUS METAL":
        return "PRECIOUS_METAL"
    if "INDEX" in value:
        return "INDEX"
    if "FUTURE" in value:
        return "FUTURES"
    if "ETF" in value:
        return "ETF"
    return value or "UNKNOWN"


def _compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _integer(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _api_credits(response: object) -> int | None:
    header = response.header("api-credits-used")  # type: ignore[attr-defined]
    return _integer(header) if header is not None else 1
