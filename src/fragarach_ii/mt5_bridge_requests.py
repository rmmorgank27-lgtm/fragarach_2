"""Schedule governed incremental requests for the outbound Windows MT5 worker."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .external_consumer_service import canonical_database_path
from .mt5_bridge_queue import _atomic_json, bridge_namespaces, bridge_paths, enqueue_request
from .mt5_catalogue import authorised_lanes, authorised_routes
from .mt5_route_manifest import is_mt5_primary_lane
from .replica_publication import ReplicaPaths


CONTRACT = "fragarach_ii.mt5_bridge_request_scheduler.v1"
FAILOVER_CONTRACT = "fragarach_ii.mt5_bridge_failover.v1"
FAILOVER_POLICY_REVISION = 3
# Do not poll faster than a lane can produce a newly completed bar.  The
# previous sub-cadence values repeatedly requested the same closed bar and
# turned a healthy multi-lane bridge into continuous canonical write churn.
MINIMUM_SECONDS = {"D1": 3600, "H1": 3600, "M30": 1800, "M5": 300}
TIMEFRAME_SECONDS = {"D1": 86_400, "H1": 3600, "M30": 1800, "M5": 300}


def _registered_asset_class(database: str | Path, symbol: str) -> str | None:
    try:
        with sqlite3.connect(
            f"file:{Path(database).expanduser().resolve()}?mode=ro", uri=True,
        ) as connection:
            row = connection.execute(
                "SELECT asset_class FROM instrument_registrations "
                "WHERE asset=? AND timeframe='D1'",
                (symbol.strip().upper(),),
            ).fetchone()
    except sqlite3.Error:
        return None
    return str(row[0]).upper() if row is not None else None


def _lane_token(database: str | Path, symbol: str, timeframe: str) -> dict[str, object]:
    try:
        with sqlite3.connect(
            f"file:{Path(database).expanduser().resolve()}?mode=ro", uri=True,
        ) as connection:
            row = connection.execute(
                "SELECT open_time_utc,updated_by_ingest_run_id FROM bars "
                "WHERE asset=? AND timeframe=? ORDER BY open_time_utc DESC LIMIT 1",
                (symbol, timeframe),
            ).fetchone()
    except sqlite3.Error:
        row = None
    return {
        "open_time_utc": int(row[0]) if row is not None else None,
        "ingest_run_id": str(row[1]) if row is not None and row[1] is not None else None,
    }


def failover_state_path(support: str | Path) -> Path:
    return bridge_paths(support)["root"] / "failover-state.json"


def has_reviewed_twelve_data_fallback(
    database: str | Path, *, symbol: str, timeframe: str,
) -> bool:
    """Return whether the exact lane has a reviewed Twelve Data route.

    A provider-order declaration is not representation authority. In
    particular, a cash index, ETF, or similarly named security must never be
    substituted for one of the broker's index CFDs. A fallback grant is useful
    only when provider facts prove both identity and timeframe support.
    """

    from .provider_facts import representation_mapping

    mapping = representation_mapping(database, "TWELVE_DATA", symbol)
    if not isinstance(mapping, dict):
        return False
    if str(mapping.get("status") or "").upper() not in {
        "RESOLVED_AUTOMATICALLY", "OPERATOR_RESOLVED",
    }:
        return False
    if str(mapping.get("mapping_class") or "").upper() not in {
        "EXACT_REPRESENTATION", "APPROVED_PROVIDER_ALIAS",
        "APPROVED_EQUIVALENT_REPRESENTATION",
    } or not mapping.get("provider_symbol"):
        return False
    lane = timeframe.strip().upper()
    capabilities = mapping.get("timeframe_capabilities")
    capability = capabilities.get(lane) if isinstance(capabilities, dict) else None
    if isinstance(capability, dict):
        return capability.get("supported") is True
    # Older reviewed physical-FX facts persisted D1 only even though the
    # approved Twelve Data FX contract covers every standard lane.
    return bool(
        lane in MINIMUM_SECONDS
        and str(mapping.get("provider_asset_class") or "").upper()
            in {"FX", "FOREX", "PHYSICAL CURRENCY"}
        and str(mapping.get("provider_instrument_type") or "").upper()
            == "PHYSICAL CURRENCY"
    )


def active_fallback_grants(
    database: str | Path, support: str | Path,
) -> dict[str, dict[str, object]]:
    """Return grants whose failed MT5 boundary has not yet been replaced."""

    path = failover_state_path(support)
    state = _read_json(path)
    grants = state.get("grants") if state.get("contract") == FAILOVER_CONTRACT else {}
    if not isinstance(grants, dict):
        grants = {}
    active: dict[str, dict[str, object]] = {}
    changed = False
    for lane, grant in grants.items():
        if (
            not isinstance(grant, dict)
            or ":" not in lane
            or int(grant.get("policy_revision") or 0) != FAILOVER_POLICY_REVISION
        ):
            changed = True
            continue
        symbol, timeframe = lane.split(":", 1)
        if not has_reviewed_twelve_data_fallback(
            database, symbol=symbol, timeframe=timeframe,
        ):
            changed = True
            continue
        if _lane_token(database, symbol, timeframe) != grant.get("baseline_lane_token"):
            changed = True
            continue
        active[lane] = grant
    if changed:
        _atomic_json(path, {
            "contract": FAILOVER_CONTRACT,
            "updated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "grants": active,
        })
    return active


def grant_mt5_fallback(
    database: str | Path,
    support: str | Path,
    *,
    symbol: str,
    timeframe: str,
    reason: str,
    request_id: str | None = None,
    at: datetime | None = None,
) -> dict[str, object] | None:
    """Durably permit the second provider after one classified MT5 outcome."""

    canonical = symbol.strip().upper()
    lane = timeframe.strip().upper()
    if not has_reviewed_twelve_data_fallback(
        database, symbol=canonical, timeframe=lane,
    ):
        return None
    provider_symbol = authorised_lanes(support, database=database).get((canonical, lane))
    if not provider_symbol or not is_mt5_primary_lane(
        canonical,
        lane,
        provider_symbol=provider_symbol,
        asset_class=_registered_asset_class(database, canonical),
    ):
        return None
    observed = (at or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    path = failover_state_path(support)
    state = _read_json(path)
    grants = state.get("grants") if state.get("contract") == FAILOVER_CONTRACT else {}
    grants = dict(grants) if isinstance(grants, dict) else {}
    grant = {
        "lane": f"{canonical}:{lane}",
        "reason": reason,
        "request_id": request_id,
        "granted_at_utc": observed.isoformat(),
        "baseline_lane_token": _lane_token(database, canonical, lane),
        "provider_order": ["MT5_BRIDGE", "TWELVE_DATA"],
        "policy_revision": FAILOVER_POLICY_REVISION,
    }
    grants[grant["lane"]] = grant
    _atomic_json(path, {
        "contract": FAILOVER_CONTRACT,
        "updated_at_utc": observed.isoformat(),
        "grants": grants,
    })
    return grant


def fail_pending_primary_requests(
    database: str | Path,
    support: str | Path,
    *,
    reason: str,
    at: datetime,
) -> list[dict[str, object]]:
    """Retire pending primary requests when bridge health is classified failed."""

    from .mt5_tick_activity import is_activity_only_request

    released: list[dict[str, object]] = []
    pending = [
        (paths, path)
        for _, paths in bridge_namespaces(support)
        for path in paths["pending"].glob("*.json")
    ]
    for paths, path in sorted(pending, key=lambda item: item[1].name):
        request = _read_json(path)
        request_id = str(request.get("request_id") or path.stem)
        if is_activity_only_request(support, request_id):
            continue
        grant = grant_mt5_fallback(
            database,
            support,
            symbol=str(request.get("canonical_symbol") or ""),
            timeframe=str(request.get("timeframe") or ""),
            reason=reason,
            request_id=request_id,
            at=at,
        )
        if grant is None:
            continue
        destination = paths["failed"] / path.name
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.replace(path, destination)
        released.append(grant)
    return released


def operator_bridge_route(
    database: str | Path, support: str | Path, *, symbol: str, timeframe: str,
) -> str | None:
    """Return the live catalogue alias for an approved broker-primary lane."""

    canonical_symbol = symbol.strip().upper()
    canonical_timeframe = timeframe.strip().upper()
    try:
        provider_symbol = authorised_lanes(
            support, database=Path(database).expanduser().resolve(),
        ).get((canonical_symbol, canonical_timeframe))
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        return None
    if not provider_symbol or not is_mt5_primary_lane(
        canonical_symbol,
        canonical_timeframe,
        provider_symbol=provider_symbol,
        asset_class=_registered_asset_class(database, canonical_symbol),
    ):
        return None
    return provider_symbol


def enqueue_operator_request(
    database: str | Path,
    support: str | Path,
    *,
    symbol: str,
    timeframe: str,
    start_utc: str,
    end_utc: str,
    at: datetime | None = None,
) -> dict[str, object] | None:
    """Queue one explicit operator request through the approved MT5 route.

    The normal MT5 cadence and a manual force refresh share the same immutable
    lane queue.  Deduplicating by lane keeps an operator click from creating a
    second bridge writer while an earlier request is still in flight.
    """

    db = Path(database).expanduser().resolve()
    canonical_symbol = symbol.strip().upper()
    canonical_timeframe = timeframe.strip().upper()
    provider_symbol = operator_bridge_route(
        db, support, symbol=canonical_symbol, timeframe=canonical_timeframe,
    )
    if provider_symbol is None:
        return None
    observed = (at or datetime.now(UTC)).astimezone(UTC)
    archive_expired_requests(support, at=observed)
    route = authorised_routes(support, database=db).get(
        (canonical_symbol, canonical_timeframe)
    )
    if route is None:
        return None
    node_id = None if route.get("queue_namespace") == "default" else str(route["node_id"])
    for path in bridge_paths(support, node_id)["pending"].glob("*.json"):
        pending = _read_json(path)
        if (
            str(pending.get("canonical_symbol") or "").upper() == canonical_symbol
            and str(pending.get("timeframe") or "").upper() == canonical_timeframe
        ):
            return {
                "contract": "fragarach_ii.mt5_operator_request.v1",
                "work_class": "OPERATOR_FETCH",
                "outcome": "MT5_BRIDGE_REQUEST_ALREADY_PENDING",
                "operation_id": pending.get("request_id"),
                "request_id": pending.get("request_id"),
                "symbol": canonical_symbol,
                "timeframe": canonical_timeframe,
                "provider": "MT5_BRIDGE",
                "provider_symbol": provider_symbol,
                "requested_range": {
                    "start": pending.get("start_utc"), "end": pending.get("end_utc"),
                },
            }
    # CLI custom/update bounds are inclusive calendar dates.  The bridge uses
    # timestamp bounds, so include the complete requested through-date instead
    # of turning a same-day update into an empty/invalid interval.
    normalized_start = start_utc
    normalized_end = end_utc
    if len(start_utc) == 10:
        normalized_start = datetime.fromisoformat(start_utc).replace(
            tzinfo=UTC,
        ).isoformat().replace("+00:00", "Z")
    if len(end_utc) == 10:
        normalized_end = (
            datetime.fromisoformat(end_utc).replace(tzinfo=UTC) + timedelta(days=1)
        ).isoformat().replace("+00:00", "Z")
    request = enqueue_request(
        support,
        database=db,
        symbol=canonical_symbol,
        timeframe=canonical_timeframe,
        start_utc=normalized_start,
        end_utc=normalized_end,
        expires_in_seconds=1800,
    )
    return {
        "contract": "fragarach_ii.mt5_operator_request.v1",
        "work_class": "OPERATOR_FETCH",
        "outcome": "MT5_BRIDGE_QUEUED",
        "operation_id": request["request_id"],
        "request_id": request["request_id"],
        "symbol": canonical_symbol,
        "timeframe": canonical_timeframe,
        "provider": "MT5_BRIDGE",
        "provider_symbol": provider_symbol,
        "requested_range": {"start": request["start_utc"], "end": request["end_utc"]},
    }


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def archive_expired_requests(
    support: str | Path, *, at: datetime | None = None,
) -> list[dict[str, str]]:
    """Retain expired requests while releasing their lanes for a retry.

    A Windows worker must reject expired requests.  Leaving one in ``pending``
    indefinitely therefore turns a temporary worker outage into a permanent
    deadlock for that lane.  Moving the immutable request unchanged to the
    dedicated expiry ledger preserves its request identity and expiry proof.
    """

    observed = (at or datetime.now(UTC)).astimezone(UTC)
    archived: list[dict[str, str]] = []
    pending = [
        (node_id, paths, path)
        for node_id, paths in bridge_namespaces(support)
        for path in paths["pending"].glob("*.json")
    ]
    for node_id, paths, path in sorted(pending, key=lambda item: item[2].name):
        value = _read_json(path)
        try:
            expires_at = datetime.fromisoformat(
                str(value["expires_at_utc"]).replace("Z", "+00:00")
            ).astimezone(UTC)
        except (KeyError, TypeError, ValueError):
            # A malformed pending receipt must remain visible for manual
            # diagnosis; only a proved expiry is eligible for archival.
            continue
        if expires_at > observed:
            continue
        destination = paths["expired"] / path.name
        if destination.exists():
            raise RuntimeError(f"MT5_REQUEST_EXPIRY_RECEIPT_COLLISION:{path.name}")
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.replace(path, destination)
        receipt = {
            "request_id": str(value.get("request_id") or path.stem),
            "lane": f"{value.get('canonical_symbol')}:{value.get('timeframe')}",
        }
        if node_id is not None:
            receipt["node_id"] = str(node_id)
        archived.append(receipt)
    return archived


def enqueue_due_requests(
    database: str | Path,
    support: str | Path,
    state_path: str | Path,
    *,
    at: datetime | None = None,
) -> dict:
    db = Path(database).expanduser().resolve()
    state_file = Path(state_path).expanduser().resolve()
    state = _read_json(state_file)
    now = (at or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    expired = archive_expired_requests(support, at=now)
    from .mt5_tick_activity import is_activity_only_request
    for item in expired:
        request_id = str(item.get("request_id") or "")
        if not request_id or is_activity_only_request(support, request_id):
            continue
        expired_node = str(item.get("node_id") or "")
        namespace_node = None if expired_node in {"", "tradewinds-mt5-bridge"} else expired_node
        request = _read_json(
            bridge_paths(support, namespace_node)["expired"] / f"{request_id}.json"
        )
        grant_mt5_fallback(
            db,
            support,
            symbol=str(request.get("canonical_symbol") or ""),
            timeframe=str(request.get("timeframe") or ""),
            reason="MT5_BRIDGE_REQUEST_EXPIRED",
            request_id=request_id,
            at=now,
        )
    fallback_grants = active_fallback_grants(db, support)
    pending_lanes: dict[tuple[str, str], dict[str, object]] = {}
    all_pending = [
        path
        for _, paths in bridge_namespaces(support)
        for path in paths["pending"].glob("*.json")
    ]
    for path in all_pending:
        value = _read_json(path)
        request_id = str(value.get("request_id") or path.stem)
        if is_activity_only_request(support, request_id):
            continue
        key = (
            str(value.get("canonical_symbol") or "").upper(),
            str(value.get("timeframe") or "").upper(),
        )
        pending_lanes[key] = {
            "request_id": request_id,
            "lane": f"{key[0]}:{key[1]}",
            "expires_at_utc": value.get("expires_at_utc"),
        }
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    queued = []
    try:
        for (symbol, timeframe), provider_symbol in sorted(authorised_lanes(support, database=db).items()):
            if timeframe not in MINIMUM_SECONDS:
                continue
            # Terminal capability is necessary but never sufficient.  The
            # class policy decides whether that approved mapping is primary.
            if not is_mt5_primary_lane(
                symbol,
                timeframe,
                provider_symbol=provider_symbol,
                asset_class=_registered_asset_class(db, symbol),
            ):
                continue
            lane = f"{symbol}:{timeframe}"
            if lane in fallback_grants:
                continue
            if (symbol, timeframe) in pending_lanes:
                continue
            try:
                from .freshness import assess_lane_freshness
                freshness = assess_lane_freshness(
                    connection,
                    symbol=symbol,
                    timeframe=timeframe,
                    as_of=now,
                )
            except (KeyError, ValueError, sqlite3.Error):
                # Small contract tests and pre-foundation databases do not
                # carry the full calendar authority. The range guard below
                # remains the safe compatibility boundary for those stores.
                freshness = None
            if isinstance(freshness, dict) and freshness.get("state") == "Current":
                continue
            previous_text = (state.get("last_enqueued_at") or {}).get(lane)
            previous = datetime.fromisoformat(previous_text) if previous_text else None
            if previous and (now - previous.astimezone(UTC)).total_seconds() < MINIMUM_SECONDS[timeframe]:
                continue
            latest = connection.execute(
                "SELECT MAX(open_time_utc) FROM bars WHERE asset=? AND timeframe=?",
                (symbol, timeframe),
            ).fetchone()[0]
            # The MT5 range is inclusive. Start after the canonical edge so a
            # closed market returns an empty receipt rather than re-admitting
            # and republishing the same bar every cadence.
            start = (
                datetime.fromtimestamp(int(latest) + TIMEFRAME_SECONDS[timeframe], UTC)
                if latest else now - timedelta(days=7)
            )
            if start >= now:
                continue
            request = enqueue_request(
                support, symbol=symbol, timeframe=timeframe,
                start_utc=start.isoformat().replace("+00:00", "Z"),
                end_utc=now.isoformat().replace("+00:00", "Z"),
                expires_in_seconds=1800,
                database=db,
            )
            state.setdefault("last_enqueued_at", {})[lane] = now.isoformat()
            queued.append({
                "request_id": request["request_id"],
                "lane": lane,
                "expires_at_utc": request["expires_at_utc"],
            })
    finally:
        connection.close()
    state.update({"contract": CONTRACT, "updated_at_utc": now.isoformat(), "last_queued_count": len(queued)})
    _atomic_json(state_file, state)
    return {
        "contract": CONTRACT,
        "status": "READY",
        "expired": expired,
        "pending": list(pending_lanes.values()),
        "fallback_grants": list(fallback_grants.values()),
        "queued": queued,
    }


def main() -> int:
    database = canonical_database_path()
    paths = ReplicaPaths.for_database(database)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=database)
    parser.add_argument("--support", type=Path, default=paths.support)
    parser.add_argument("--state", type=Path, default=paths.support / "mt5-bridge" / "scheduler-state.json")
    arguments = parser.parse_args()
    print(json.dumps(enqueue_due_requests(arguments.database, arguments.support, arguments.state), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
