"""SPEC-046 operational integrity projections for the acquisition scheduler.

The canonical database remains authoritative.  This module only projects its
current registration/lane lifecycle into the operational scheduler journal.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from .freshness import normalized_utc
from .lane_commissioning import commissioned_lane_keys,resolved_calendar_id
from .market_registry import load_registry
from .storage import open_read_only


ACTIONABLE_REQUEST_STATES = {"Required", "Acknowledged"}
ACTIVE_PAUSE_STATES = {"PAUSE_REQUESTED", "DRAINING_ACTIVE_WORK", "PAUSED"}
CONTROLLED_GROUPS = {"Forex", "Metals", "Energy", "Indices", "Stocks", "Crypto"}
CONTROLLED_PAUSE_REASONS = {
    "MANUAL_INGESTION", "OPERATOR_MAINTENANCE", "PROVIDER_CONFIGURATION",
    "ESTATE_REPAIR", "OTHER_OPERATOR_REASON",
}
TERMINAL_REQUEST_STATES = {
    "RESPONSE_RECEIVED", "FAILED_BEFORE_DISPATCH", "FAILED_AFTER_DISPATCH", "CANCELLED",
}


def active_universe(database_path: str | Path) -> dict[str, object]:
    """Return the canonical current Estate projection without mutating authority."""
    with open_read_only(database_path) as connection:
        registrations = connection.execute(
            """SELECT asset,asset_class,registration_status,calendar_id,exchange_name,identity_json
               FROM instrument_registrations WHERE timeframe='D1' ORDER BY asset"""
        ).fetchall()
        lane_rows = connection.execute(
            "SELECT asset,timeframe FROM evidence_lanes ORDER BY asset,timeframe"
        ).fetchall()
        commissioned_lanes = commissioned_lane_keys(connection)
        events = connection.execute(
            """SELECT authority_event_id,supersedes_event_id,recorded_at_utc,canonical_payload
               FROM authority_events ORDER BY recorded_at_utc,authority_event_id"""
        ).fetchall()

    lifecycle = _lifecycle_projection(events)
    active_registry_symbols = {
        str(record["canonical_symbol"])
        for record in load_registry().records
        if record.get("active")
    }
    registration_by_symbol = {str(row[0]): row for row in registrations}
    lanes: dict[str, dict[str, object]] = {}
    revision_facts: list[object] = []
    for raw_symbol, raw_timeframe in lane_rows:
        symbol, timeframe = str(raw_symbol), str(raw_timeframe)
        commissioned = (symbol, timeframe) in commissioned_lanes
        lane_id = f"{symbol}:{timeframe}"
        registration = registration_by_symbol.get(symbol)
        leaf = lifecycle.get((symbol, timeframe)) or lifecycle.get((symbol, None))
        reason: str | None = None
        lifecycle_state = str((leaf or {}).get("lifecycle_state") or "ACTIVE")
        retirement_reason = str((leaf or {}).get("reason") or "")
        try:
            registration_identity = json.loads(registration[5]) if registration and registration[5] else {}
        except (TypeError, ValueError):
            registration_identity = {}
        if lifecycle_state == "PERMANENTLY_REMOVED":
            reason = "REGISTRATION_SUPERSEDED"
        elif lifecycle_state.startswith(("RETIRED", "QUARANTINED")):
            reason = (
                "INCORRECT_INSTRUMENT_IDENTITY"
                if retirement_reason == "INCORRECT_INSTRUMENT_IDENTITY"
                or lifecycle_state == "RETIRED_INCORRECT_IDENTITY"
                else "INSTRUMENT_RETIRED"
            )
        elif registration is None or not str(registration[2]).startswith("REGISTERED_"):
            reason = "INSTRUMENT_INACTIVE"
        elif (
            str(registration_identity.get("instrument_type") or "").upper() == "CFD"
            and symbol not in active_registry_symbols
        ):
            reason = "INSTRUMENT_RETIRED"
            lifecycle_state = "RETIRED_NON_ACTIONABLE"
        asset_class = str(registration[1]) if registration else "UNKNOWN"
        group = estate_group(asset_class)
        calendar = (
            resolved_calendar_id(
                asset_class=asset_class,
                calendar_id=str(registration[3] or ""),
                exchange_name=registration[4],
                canonical_symbol=symbol,
            )
            if registration else None
        )
        lanes[lane_id] = {
            "id": lane_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "asset_class": asset_class,
            "group": group,
            "calendar_identifier": calendar,
            "lifecycle_state": lifecycle_state,
            "retirement_reason": retirement_reason or None,
            # A declared manual lane remains visible to read-only planning,
            # but never becomes scheduler-owned until its commissioning event
            # supersedes the explicit NOT_COMMISSIONED declaration.
            "active": reason is None and commissioned,
            "ineligibility_reason": reason or (None if commissioned else "NOT_COMMISSIONED"),
        }
        revision_facts.append((lane_id, registration[2] if registration else None, lifecycle_state, commissioned, (leaf or {}).get("event_id")))
    revision = hashlib.sha256(
        json.dumps(revision_facts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    active = {key: value for key, value in lanes.items() if value["active"]}
    return {"revision": revision, "lanes": lanes, "active_lanes": active}


def reconcile_operational_state(
    database_path: str | Path,
    journal: dict[str, object],
    *,
    at: datetime | None = None,
) -> dict[str, object]:
    """Archive journal work that no longer resolves into the active Estate."""
    now = normalized_utc(at)
    universe = active_universe(database_path)
    active = universe["active_lanes"]
    changed = journal.get("active_universe_revision") != universe["revision"]
    journal["active_universe_revision"] = universe["revision"]
    archive = journal.setdefault("archived_operational_work", [])

    def archive_item(kind: str, identifier: str, lane_id: str, payload: object) -> None:
        nonlocal changed
        reason = _archive_reason(universe, lane_id)
        fingerprint = f"{kind}:{identifier}:{reason}"
        if any(item.get("fingerprint") == fingerprint for item in archive if isinstance(item, dict)):
            return
        archive.insert(0, {
            "id": f"archive-{uuid.uuid4().hex}", "fingerprint": fingerprint,
            "kind": kind, "source_identifier": identifier, "lane": lane_id,
            "reason": reason, "archived_at": now.isoformat(), "actionable": False,
            "payload": payload,
        })
        del archive[500:]
        changed = True

    queue = journal.setdefault("acquisition_queue", [])
    retained_queue = []
    for item in queue:
        lane_id = str(item.get("lane") or f"{item.get('symbol')}:{item.get('timeframe')}")
        if lane_id in active:
            retained_queue.append(item)
        else:
            archive_item("QUEUE", str(item.get("id") or lane_id), lane_id, dict(item))
    if len(retained_queue) != len(queue):
        journal["acquisition_queue"] = retained_queue
        changed = True

    for lane_id, state in list(journal.setdefault("lanes", {}).items()):
        if lane_id in active or not isinstance(state, dict):
            continue
        actionable = any(state.get(key) for key in ("operator_retry_pending", "manual_request", "queue_state"))
        if actionable:
            archive_item("LANE_CONTROL", lane_id, lane_id, dict(state))
        for key in ("operator_retry_pending", "operator_retry_requested_at", "manual_request"):
            state.pop(key, None)
        state.update(
            queue_state=None, result="ARCHIVED", reason=_archive_reason(universe, lane_id),
            actionable=False, archived_at=state.get("archived_at") or now.isoformat(),
        )

    for request in journal.setdefault("manual_requests", []):
        if not isinstance(request, dict) or request.get("status") not in ACTIONABLE_REQUEST_STATES:
            continue
        lane_id = f"{request.get('symbol')}:{request.get('timeframe')}"
        if lane_id not in active:
            archive_item("MANUAL_REQUEST", str(request.get("id")), lane_id, dict(request))
            request.update(
                status="Archived", archive_reason=_archive_reason(universe, lane_id),
                archived_at=now.isoformat(), actionable=False,
            )
            changed = True

    for pause in journal.setdefault("pause_records", []):
        if not isinstance(pause, dict) or pause.get("status") not in ACTIVE_PAUSE_STATES:
            continue
        if pause.get("scope_type") == "SYMBOL":
            symbol = str(pause.get("scope_identifier"))
            if not any(item["symbol"] == symbol for item in active.values()):
                archive_item("PAUSE", str(pause.get("pause_identifier")), f"{symbol}:*", dict(pause))
                pause.update(status="ARCHIVED", resumed_time=now.isoformat(), active_work_remaining=0)
                changed = True

    journal["archived_operational_work"] = archive
    return {"changed": changed, "universe": universe}


def recover_stale_reservations(journal: dict[str, object], *, at: datetime | None = None) -> bool:
    """Release reservations that a recovered process can prove were undispatched."""
    now = normalized_utc(at).isoformat()
    changed = False
    records = journal.setdefault("request_lifecycle", [])
    stale_ids = set()
    for record in records:
        if isinstance(record, dict) and record.get("state") in {"PLANNED", "RESERVED"}:
            record.update(state="FAILED_BEFORE_DISPATCH", completed_at=now, failure_reason="RESTART_RECOVERY_UNDISPATCHED")
            stale_ids.add(record.get("reservation_id"))
            changed = True
    for state in journal.setdefault("providers", {}).values():
        if not isinstance(state, dict):
            continue
        reservations = state.get("active_reservations", [])
        if reservations:
            state["active_reservations"] = []
            changed = True
    return changed


def create_pause(
    database_path: str | Path,
    journal: dict[str, object],
    *,
    scope_type: str,
    scope_identifier: str | None,
    reason: str,
    temporary: bool = False,
    related_ingestion_session: str | None = None,
    at: datetime | None = None,
) -> dict[str, object]:
    scope = scope_type.strip().upper()
    if scope not in {"ALL", "MARKET_OR_GROUP", "SYMBOL"}:
        raise ValueError(f"unsupported pause scope: {scope_type}")
    if reason not in CONTROLLED_PAUSE_REASONS:
        raise ValueError(f"unsupported pause reason: {reason}")
    universe = active_universe(database_path)
    identifier = "ALL" if scope == "ALL" else str(scope_identifier or "").strip()
    if scope == "MARKET_OR_GROUP":
        active_groups = {str(item["group"]) for item in universe["active_lanes"].values()}
        if identifier not in CONTROLLED_GROUPS or identifier not in active_groups:
            raise ValueError(f"unknown controlled Estate group: {identifier}")
    if scope == "SYMBOL":
        identifier = identifier.upper()
        if not any(lane["symbol"] == identifier for lane in universe["active_lanes"].values()):
            raise ValueError(f"symbol is not in the active Estate: {identifier}")
    existing = next((
        item for item in journal.setdefault("pause_records", [])
        if item.get("scope_type") == scope and item.get("scope_identifier") == identifier
        and item.get("status") in ACTIVE_PAUSE_STATES
        and item.get("related_ingestion_session") == related_ingestion_session
    ), None)
    if existing:
        return existing
    now = normalized_utc(at)
    active_count = _active_work_count(journal, scope, identifier, universe)
    record = {
        "pause_identifier": f"pause-{uuid.uuid4().hex}",
        "scope_type": scope, "scope_identifier": identifier, "reason": reason,
        "created_time": now.isoformat(), "temporary": bool(temporary),
        "related_ingestion_session": related_ingestion_session,
        "status": "DRAINING_ACTIVE_WORK" if active_count else "PAUSED",
        "active_work_remaining": active_count, "resumed_time": None,
    }
    journal["pause_records"].append(record)
    return record


def resume_pause(
    journal: dict[str, object],
    *,
    pause_identifier: str | None = None,
    scope_type: str | None = None,
    scope_identifier: str | None = None,
    related_ingestion_session: str | None = None,
    at: datetime | None = None,
) -> list[dict[str, object]]:
    now = normalized_utc(at).isoformat()
    changed = []
    for record in journal.setdefault("pause_records", []):
        if not isinstance(record, dict) or record.get("status") not in ACTIVE_PAUSE_STATES:
            continue
        matches = (
            (pause_identifier and record.get("pause_identifier") == pause_identifier)
            or (related_ingestion_session and record.get("related_ingestion_session") == related_ingestion_session)
            or (
                scope_type and record.get("scope_type") == scope_type.upper()
                and record.get("scope_identifier") == ("ALL" if scope_type.upper() == "ALL" else scope_identifier)
            )
        )
        if matches:
            record.update(status="RESUMED", active_work_remaining=0, resumed_time=now)
            changed.append(record)
    if not changed:
        raise ValueError("no matching active pause")
    return changed


def refresh_pause_states(journal: dict[str, object], universe: dict[str, object]) -> bool:
    changed = False
    for record in journal.setdefault("pause_records", []):
        if not isinstance(record, dict) or record.get("status") not in ACTIVE_PAUSE_STATES:
            continue
        count = _active_work_count(
            journal, str(record.get("scope_type")), str(record.get("scope_identifier")), universe
        )
        status = "DRAINING_ACTIVE_WORK" if count else "PAUSED"
        if record.get("active_work_remaining") != count or record.get("status") != status:
            record.update(active_work_remaining=count, status=status)
            changed = True
    return changed


def effective_pause_sources(
    journal: dict[str, object], *, symbol: str, group: str
) -> list[dict[str, object]]:
    sources = []
    for record in journal.setdefault("pause_records", []):
        if not isinstance(record, dict) or record.get("status") not in ACTIVE_PAUSE_STATES:
            continue
        scope, identifier = record.get("scope_type"), record.get("scope_identifier")
        if scope == "ALL" or (scope == "MARKET_OR_GROUP" and identifier == group) or (scope == "SYMBOL" and identifier == symbol):
            sources.append(record)
    return sources


def request_lifecycle_counts(records: list[object]) -> dict[str, int]:
    states = (
        "PLANNED", "RESERVED", "DISPATCHED", "RESPONSE_RECEIVED",
        "FAILED_BEFORE_DISPATCH", "FAILED_AFTER_DISPATCH", "CANCELLED",
    )
    return {state: sum(isinstance(item, dict) and item.get("state") == state for item in records) for state in states}


def estate_group(asset_class: str) -> str:
    value = asset_class.upper()
    if value == "FX":
        return "Forex"
    if value == "METALS":
        return "Metals"
    if value == "ENERGY":
        return "Energy"
    if value == "INDICES":
        return "Indices"
    if value == "CRYPTO":
        return "Crypto"
    if "EQUIT" in value or value in {"STOCK", "STOCKS"}:
        return "Stocks"
    return value.title()


def _lifecycle_projection(rows: list[object]) -> dict[tuple[str, str | None], dict[str, object]]:
    superseded = {str(row[1]) for row in rows if row[1]}
    leaves = []
    for row in rows:
        if str(row[0]) in superseded:
            continue
        try:
            payload = json.loads(row[3])
            body = payload.get("body", {})
        except (TypeError, ValueError):
            continue
        if body.get("asset") and body.get("lifecycle_state"):
            leaves.append((row, body))
    result: dict[tuple[str, str | None], dict[str, object]] = {}
    for row, body in leaves:
        key = (str(body["asset"]), str(body["timeframe"]) if body.get("timeframe") else None)
        candidate = {"event_id": row[0], "recorded_at": row[2], **body}
        prior = result.get(key)
        if prior is None or (str(candidate["recorded_at"]), str(candidate["event_id"])) > (str(prior["recorded_at"]), str(prior["event_id"])):
            result[key] = candidate
    return result


def _archive_reason(universe: dict[str, object], lane_id: str) -> str:
    if lane_id.endswith(":*"):
        symbol = lane_id[:-2]
        matches = [lane for lane in universe["lanes"].values() if lane["symbol"] == symbol]
        return str(matches[0].get("ineligibility_reason") or "LANE_REMOVED_FROM_ESTATE") if matches else "LANE_REMOVED_FROM_ESTATE"
    lane = universe["lanes"].get(lane_id)
    return str(lane.get("ineligibility_reason") or "LANE_REMOVED_FROM_ESTATE") if lane else "LANE_NO_LONGER_COMMISSIONED"


def _active_work_count(journal: dict[str, object], scope: str, identifier: str, universe: dict[str, object]) -> int:
    active = 0
    for request in journal.setdefault("request_lifecycle", []):
        if not isinstance(request, dict) or request.get("state") != "DISPATCHED":
            continue
        lane = universe["lanes"].get(str(request.get("lane")))
        if lane and _scope_matches(scope, identifier, lane):
            active += 1
    return active


def _scope_matches(scope: str, identifier: str, lane: dict[str, object]) -> bool:
    return (
        scope == "ALL"
        or (scope == "MARKET_OR_GROUP" and lane.get("group") == identifier)
        or (scope == "SYMBOL" and lane.get("symbol") == identifier)
    )
