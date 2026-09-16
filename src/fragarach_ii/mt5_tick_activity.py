"""Attributed MT5 tick activity admission and resumable historical backfill."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .mt5_broker_time import POLICY_ID, broker_server_to_utc
from .mt5_catalogue import authorised_lanes
from .mt5_bridge_queue import _atomic_json, bridge_paths, enqueue_request
from .mt5_route_manifest import load_manifest
from .storage import open_read_only


ACTIVITY_KIND = "MT5_TICK_ACTIVITY"
ACTIVITY_SOURCE_LABELS = {
    "FUSION_MARKETS_MT5": "Fusion MT5 tick activity",
    "EIGHTCAP_MT5": "Eightcap MT5 tick activity",
}
# Backward-compatible public name for the original Fusion activity contract.
ACTIVITY_SOURCE_LABEL = ACTIVITY_SOURCE_LABELS["FUSION_MARKETS_MT5"]
BACKFILL_CONTRACT = "fragarach_ii.mt5_tick_activity_backfill.v1"
SCOPE_ASSET_CLASSES = frozenset({"FX", "METALS", "ENERGY", "INDICES", "BROKER_INDEX_CFDS"})
TIMEFRAME_SECONDS = {"D1": 86_400, "H1": 3_600, "M30": 1_800, "M5": 300}
# Each request stays well below the bridge's practical 5,000-bar payload size.
CHUNK_SECONDS = {
    "D1": 365 * 86_400,
    "H1": 30 * 86_400,
    "M30": 14 * 86_400,
    "M5": 2 * 86_400,
}
BACKFILL_PACING_SECONDS = 30


class MT5TickActivityError(RuntimeError):
    """Raised when activity evidence cannot satisfy its explicit contract."""


def activity_paths(support: str | Path) -> dict[str, Path]:
    root = Path(support).expanduser().resolve() / "mt5-bridge" / "activity-backfill"
    return {
        "root": root,
        "state": root / "state.json",
        "pending": root / "pending",
        "receipts": root / "receipts",
        "continuous_state": root / "continuous-state.json",
        "continuous_pending": root / "continuous-pending",
    }


def is_backfill_request(support: str | Path, request_id: str) -> bool:
    return activity_paths(support)["pending"].joinpath(f"{request_id}.json").is_file()


def is_activity_only_request(support: str | Path, request_id: str) -> bool:
    paths = activity_paths(support)
    return (
        paths["pending"].joinpath(f"{request_id}.json").is_file()
        or paths["continuous_pending"].joinpath(f"{request_id}.json").is_file()
    )


def _canonical_open(raw_time: str, timeframe: str) -> int:
    try:
        server = datetime.strptime(raw_time, "%Y.%m.%d %H:%M:%S")
    except ValueError as error:
        raise MT5TickActivityError("INVALID_ACTIVITY_TIMESTAMP") from error
    if timeframe == "D1":
        return int(datetime(server.year, server.month, server.day, tzinfo=UTC).timestamp())
    return int(broker_server_to_utc(raw_time).timestamp())


def _non_negative_integer(value: Any, *, field: str, zero_is_null: bool = False) -> int | None:
    if value is None and zero_is_null:
        return None
    if isinstance(value, bool):
        raise MT5TickActivityError(f"INVALID_{field.upper()}")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise MT5TickActivityError(f"INVALID_{field.upper()}") from error
    if not decimal.is_finite() or decimal < 0 or decimal != decimal.to_integral_value():
        raise MT5TickActivityError(f"INVALID_{field.upper()}")
    integer = int(decimal)
    return None if zero_is_null and integer == 0 else integer


def admit_bridge_activity(
    connection: sqlite3.Connection,
    *,
    response: dict[str, Any],
    request: dict[str, Any],
    route: dict[str, Any],
    bars: list[dict[str, Any]],
    raw_block_id: str,
    admitted_at_utc: str,
) -> dict[str, int | str]:
    """Attach activity only where the canonical price opening already exists.

    The caller invokes this inside the same single-writer transaction that
    retains the raw bridge response.  Missing price openings remain explicit
    alignment outcomes and never manufacture OHLC bars.
    """

    run = connection.execute(
        """SELECT ingest_run_id FROM ingest_runs
           WHERE raw_block_id=? AND status='active'
           ORDER BY rowid DESC LIMIT 1""",
        (raw_block_id,),
    ).fetchone()
    if run is None:
        raise MT5TickActivityError("ACTIVITY_ADMISSION_RUN_UNAVAILABLE")
    admission_run_id = str(run[0])
    symbol = str(request["canonical_symbol"]).upper()
    timeframe = str(request["timeframe"]).upper()
    inserted = already_known = unmatched = 0
    for row_number, bar in enumerate(bars, start=1):
        raw_time = str(bar.get("time") or "")
        opened = _canonical_open(raw_time, timeframe)
        tick_volume = _non_negative_integer(bar.get("tick_volume"), field="tick_volume")
        real_volume = _non_negative_integer(
            bar.get("real_volume"), field="real_volume", zero_is_null=True,
        )
        spread = (
            None if bar.get("spread") is None
            else _non_negative_integer(bar.get("spread"), field="spread")
        )
        if connection.execute(
            "SELECT 1 FROM bars WHERE asset=? AND timeframe=? AND open_time_utc=?",
            (symbol, timeframe, opened),
        ).fetchone() is None:
            unmatched += 1
            continue
        identity = hashlib.sha256(
            f"{response['response_sha256']}:{row_number}".encode("utf-8")
        ).hexdigest()
        before = connection.total_changes
        connection.execute(
            """
            INSERT OR IGNORE INTO market_activity_observations (
                activity_observation_id,asset,timeframe,open_time_utc,
                tick_volume,real_volume,spread,activity_kind,activity_source_label,
                provider,provider_symbol,broker_family,terminal_route,source_route,
                request_id,response_sha256,raw_block_id,admission_run_id,
                source_row_number,source_timestamp_text,timestamp_policy,
                captured_at_utc,admitted_at_utc
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                identity, symbol, timeframe, opened, tick_volume, real_volume, spread,
                ACTIVITY_KIND, ACTIVITY_SOURCE_LABELS.get(
                    str(route["record_provider"]), f"{route['record_provider']} tick activity"
                ), str(route["record_provider"]),
                str(request["provider_symbol"]), str(response["broker_family"]),
                str(response["terminal_route"]), str(response["source_route"]),
                str(response["request_id"]), str(response["response_sha256"]),
                raw_block_id, admission_run_id, row_number, raw_time, POLICY_ID,
                str(response["captured_at_utc"]), admitted_at_utc,
            ),
        )
        if connection.total_changes > before:
            inserted += 1
        else:
            already_known += 1
    return {
        "activity_source_label": ACTIVITY_SOURCE_LABELS.get(
            str(route["record_provider"]), f"{route['record_provider']} tick activity"
        ),
        "activity_rows_received": len(bars),
        "activity_inserted": inserted,
        "activity_already_known": already_known,
        "activity_alignment_unresolved": unmatched,
    }


def plan_activity_backfill(
    database: str | Path,
    support: str | Path,
    *,
    symbols: set[str] | None = None,
    timeframes: set[str] | None = None,
) -> dict[str, Any]:
    db = Path(database).expanduser().resolve()
    wanted_symbols = {item.upper() for item in symbols} if symbols else None
    wanted_timeframes = {item.upper() for item in timeframes} if timeframes else None
    routes = authorised_lanes(support, database=db)
    with open_read_only(db) as connection:
        registrations = dict(connection.execute(
            "SELECT asset,upper(asset_class) FROM instrument_registrations WHERE timeframe='D1'"
        ).fetchall())
        # The lane-state edge and the bars primary key answer this without a
        # whole-estate GROUP BY over millions of observations.
        rows = connection.execute(
            """SELECT l.asset,l.timeframe,
                      (SELECT min(b.open_time_utc) FROM bars b
                        WHERE b.asset=l.asset AND b.timeframe=l.timeframe),
                      l.high_watermark_open_time_utc
               FROM lane_state l
               JOIN evidence_lanes e ON e.asset=l.asset AND e.timeframe=l.timeframe
               WHERE l.high_watermark_open_time_utc IS NOT NULL
               ORDER BY l.asset,l.timeframe"""
        ).fetchall()
    manifest = load_manifest()
    generated = datetime.now(UTC).replace(microsecond=0).isoformat()
    lanes: dict[str, dict[str, Any]] = {}
    for symbol, timeframe, first, latest in rows:
        symbol, timeframe = str(symbol).upper(), str(timeframe).upper()
        provider_symbol = routes.get((symbol, timeframe))
        asset_class = str(registrations.get(symbol) or "").upper()
        if (
            not provider_symbol or timeframe not in TIMEFRAME_SECONDS
            or asset_class not in SCOPE_ASSET_CLASSES
            or (wanted_symbols is not None and symbol not in wanted_symbols)
            or (wanted_timeframes is not None and timeframe not in wanted_timeframes)
        ):
            continue
        end_exclusive = int(latest) + TIMEFRAME_SECONDS[timeframe]
        lane_id = f"{symbol}:{timeframe}"
        lanes[lane_id] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "asset_class": asset_class,
            "provider_symbol": provider_symbol,
            "planned_start_utc": _epoch_text(int(first)),
            "planned_end_utc": _epoch_text(end_exclusive),
            "next_start_utc": _epoch_text(int(first)),
            "state": "ACTIVE",
            "request_count": 0,
            "activity_rows_received": 0,
            "activity_rows_attached": 0,
            "alignment_unresolved": 0,
        }
    return {
        "contract": BACKFILL_CONTRACT,
        "enabled": False,
        "status": "PLANNED" if lanes else "NO_ELIGIBLE_LANES",
        "generated_at_utc": generated,
        "updated_at_utc": generated,
        "route_manifest_contract": manifest.get("contract"),
        "route_manifest_revision": manifest.get("revision") or manifest.get("version") or "v1",
        "lanes": lanes,
    }


def start_activity_backfill(
    database: str | Path,
    support: str | Path,
    *,
    symbols: set[str] | None = None,
    timeframes: set[str] | None = None,
) -> dict[str, Any]:
    state = plan_activity_backfill(
        database, support, symbols=symbols, timeframes=timeframes,
    )
    state["enabled"] = bool(state["lanes"])
    state["status"] = "ACTIVE" if state["lanes"] else "NO_ELIGIBLE_LANES"
    state["started_at_utc"] = datetime.now(UTC).replace(microsecond=0).isoformat()
    _atomic_json(activity_paths(support)["state"], state)
    return state


def queue_activity_backfill_requests(
    database: str | Path, support: str | Path, *, max_requests: int = 1,
) -> dict[str, Any]:
    paths = activity_paths(support)
    state = _read_json(paths["state"])
    if state.get("contract") != BACKFILL_CONTRACT or state.get("enabled") is not True:
        return {"contract": BACKFILL_CONTRACT, "status": "INACTIVE", "queued": []}
    _reconcile_expired_markers(support, state)
    ordinary_pending = []
    for pending in bridge_paths(support)["pending"].glob("*.json"):
        if not is_backfill_request(support, pending.stem):
            ordinary_pending.append(pending)
    # Live completed-bar work always owns bridge capacity before history.
    if ordinary_pending:
        return {"contract": BACKFILL_CONTRACT, "status": "LIVE_PRIORITY", "queued": []}
    if any(paths["pending"].glob("*.json")):
        return {"contract": BACKFILL_CONTRACT, "status": "BACKFILL_PENDING", "queued": []}
    previous_text = state.get("last_backfill_enqueued_at_utc")
    if previous_text:
        elapsed = (datetime.now(UTC) - _parse_utc(str(previous_text))).total_seconds()
        if elapsed < BACKFILL_PACING_SECONDS:
            return {"contract": BACKFILL_CONTRACT, "status": "BACKFILL_PACING", "queued": []}
    queued: list[dict[str, str]] = []
    for lane_id, lane in sorted((state.get("lanes") or {}).items()):
        if len(queued) >= max(1, max_requests):
            break
        if lane.get("state") not in {"ACTIVE", "RETRY"}:
            continue
        timeframe = str(lane["timeframe"])
        start = _parse_utc(str(lane["next_start_utc"]))
        planned_end = _parse_utc(str(lane["planned_end_utc"]))
        if start >= planned_end:
            lane["state"] = "COMPLETE"
            continue
        chunk_end = min(planned_end, start + timedelta(seconds=CHUNK_SECONDS[timeframe]))
        request = enqueue_request(
            support,
            database=database,
            symbol=str(lane["symbol"]),
            timeframe=timeframe,
            start_utc=_datetime_text(start),
            end_utc=_datetime_text(chunk_end),
            expires_in_seconds=3_600,
        )
        marker = {
            "contract": BACKFILL_CONTRACT,
            "request_id": request["request_id"],
            "lane": lane_id,
            "start_utc": request["start_utc"],
            "end_utc": request["end_utc"],
            "queued_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        }
        _atomic_json(paths["pending"] / f"{request['request_id']}.json", marker)
        lane.update({"state": "REQUEST_PENDING", "request_id": request["request_id"]})
        state["last_backfill_enqueued_at_utc"] = datetime.now(UTC).replace(microsecond=0).isoformat()
        queued.append({"request_id": str(request["request_id"]), "lane": lane_id})
    _refresh_backfill_status(state)
    _atomic_json(paths["state"], state)
    return {"contract": BACKFILL_CONTRACT, "status": state["status"], "queued": queued}


def queue_continuous_activity_requests(
    database: str | Path, support: str | Path, *, at: datetime | None = None,
    max_requests: int = 2,
) -> dict[str, Any]:
    """Fill activity-only edges for lanes whose price authority is not MT5."""

    from .mt5_route_manifest import is_mt5_primary_lane

    observed = (at or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    paths = activity_paths(support)
    state = _read_json(paths["continuous_state"])
    backfill = _read_json(paths["state"])
    pending_lanes: set[tuple[str, str]] = set()
    for path in bridge_paths(support)["pending"].glob("*.json"):
        value = _read_json(path)
        pending_lanes.add((
            str(value.get("canonical_symbol") or "").upper(),
            str(value.get("timeframe") or "").upper(),
        ))
    routes = authorised_lanes(support, database=database)
    queued: list[dict[str, str]] = []
    with open_read_only(database) as connection:
        registrations = dict(connection.execute(
            "SELECT asset,upper(asset_class) FROM instrument_registrations WHERE timeframe='D1'"
        ).fetchall())
        for (symbol, timeframe), provider_symbol in sorted(routes.items()):
            if len(queued) >= max(1, max_requests):
                break
            if (
                timeframe not in TIMEFRAME_SECONDS
                or str(registrations.get(symbol) or "").upper() not in SCOPE_ASSET_CLASSES
                or is_mt5_primary_lane(
                    symbol,
                    timeframe,
                    provider_symbol=provider_symbol,
                    asset_class=str(registrations.get(symbol) or ""),
                )
                or (symbol, timeframe) in pending_lanes
            ):
                continue
            plan = (backfill.get("lanes") or {}).get(f"{symbol}:{timeframe}")
            if isinstance(plan, dict) and plan.get("state") != "COMPLETE":
                continue
            price_row = connection.execute(
                "SELECT high_watermark_open_time_utc FROM lane_state WHERE asset=? AND timeframe=?",
                (symbol, timeframe),
            ).fetchone()
            if price_row is None or price_row[0] is None:
                continue
            price_latest = int(price_row[0])
            activity_row = connection.execute(
                "SELECT max(open_time_utc) FROM market_activity_observations WHERE asset=? AND timeframe=?",
                (symbol, timeframe),
            ).fetchone()
            activity_latest = activity_row[0] if activity_row else None
            if activity_latest is not None and int(activity_latest) >= price_latest:
                continue
            lane_id = f"{symbol}:{timeframe}"
            previous_text = (state.get("last_enqueued_at") or {}).get(lane_id)
            previous = _parse_utc(previous_text) if previous_text else None
            if previous is not None and (observed - previous).total_seconds() < 3_600:
                continue
            step = TIMEFRAME_SECONDS[timeframe]
            start_epoch = (
                max(int(activity_latest) + step, price_latest - 7 * step)
                if activity_latest is not None else price_latest
            )
            request = enqueue_request(
                support, database=database, symbol=symbol, timeframe=timeframe,
                start_utc=_epoch_text(start_epoch), end_utc=_epoch_text(price_latest + step),
                expires_in_seconds=1_800,
            )
            _atomic_json(paths["continuous_pending"] / f"{request['request_id']}.json", {
                "contract": "fragarach_ii.mt5_tick_activity_continuous_request.v1",
                "request_id": request["request_id"],
                "lane": lane_id,
                "queued_at_utc": _datetime_text(observed),
            })
            state.setdefault("last_enqueued_at", {})[lane_id] = _datetime_text(observed)
            queued.append({"request_id": str(request["request_id"]), "lane": lane_id})
    state.update({
        "contract": "fragarach_ii.mt5_tick_activity_continuous.v1",
        "updated_at_utc": _datetime_text(observed), "last_queued_count": len(queued),
    })
    _atomic_json(paths["continuous_state"], state)
    return {"contract": state["contract"], "status": "READY", "queued": queued}


def complete_backfill_request(
    support: str | Path, request_id: str, activity_result: dict[str, Any],
) -> None:
    paths = activity_paths(support)
    marker_path = paths["pending"] / f"{request_id}.json"
    if not marker_path.is_file():
        return
    marker = _read_json(marker_path)
    state = _read_json(paths["state"])
    lane = (state.get("lanes") or {}).get(marker.get("lane"))
    if isinstance(lane, dict):
        lane["next_start_utc"] = marker["end_utc"]
        lane["request_count"] = int(lane.get("request_count") or 0) + 1
        lane["activity_rows_received"] = int(lane.get("activity_rows_received") or 0) + int(activity_result.get("activity_rows_received") or 0)
        lane["activity_rows_attached"] = int(lane.get("activity_rows_attached") or 0) + int(activity_result.get("activity_inserted") or 0)
        lane["alignment_unresolved"] = int(lane.get("alignment_unresolved") or 0) + int(activity_result.get("activity_alignment_unresolved") or 0)
        lane.pop("request_id", None)
        lane["state"] = (
            "COMPLETE"
            if _parse_utc(str(lane["next_start_utc"])) >= _parse_utc(str(lane["planned_end_utc"]))
            else "ACTIVE"
        )
    receipt = {
        **marker,
        "completed_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "activity_result": activity_result,
    }
    _atomic_json(paths["receipts"] / marker_path.name, receipt)
    marker_path.unlink(missing_ok=True)
    _refresh_backfill_status(state)
    _atomic_json(paths["state"], state)


def complete_activity_request(support: str | Path, request_id: str, activity_result: dict[str, Any]) -> None:
    """Complete either historical or continuous activity-only ownership."""

    complete_backfill_request(support, request_id, activity_result)
    activity_paths(support)["continuous_pending"].joinpath(
        f"{request_id}.json"
    ).unlink(missing_ok=True)


def fail_backfill_request(support: str | Path, request_id: str, reason: str) -> None:
    paths = activity_paths(support)
    marker_path = paths["pending"] / f"{request_id}.json"
    if not marker_path.is_file():
        return
    marker = _read_json(marker_path)
    state = _read_json(paths["state"])
    lane = (state.get("lanes") or {}).get(marker.get("lane"))
    if isinstance(lane, dict):
        lane.update({"state": "RETRY", "last_error": reason})
        lane.pop("request_id", None)
    marker_path.unlink(missing_ok=True)
    _refresh_backfill_status(state)
    _atomic_json(paths["state"], state)


def fail_activity_request(support: str | Path, request_id: str, reason: str) -> None:
    fail_backfill_request(support, request_id, reason)
    activity_paths(support)["continuous_pending"].joinpath(
        f"{request_id}.json"
    ).unlink(missing_ok=True)


def activity_coverage(database: str | Path) -> dict[str, Any]:
    with open_read_only(database) as connection:
        rows = connection.execute(
            """
            SELECT l.asset,l.timeframe,
                   (SELECT count(DISTINCT a.open_time_utc)
                      FROM market_activity_observations a
                     WHERE a.asset=l.asset AND a.timeframe=l.timeframe),
                   (SELECT min(a.open_time_utc)
                      FROM market_activity_observations a
                     WHERE a.asset=l.asset AND a.timeframe=l.timeframe),
                   (SELECT max(a.open_time_utc)
                      FROM market_activity_observations a
                     WHERE a.asset=l.asset AND a.timeframe=l.timeframe),
                   l.high_watermark_open_time_utc
            FROM lane_state l ORDER BY l.asset,l.timeframe
            """
        ).fetchall()
    lanes = []
    for symbol, timeframe, count, earliest, latest, price_latest in rows:
        state = "UNAVAILABLE" if latest is None else (
            "CURRENT" if int(latest) == int(price_latest) else "BEHIND"
        )
        lanes.append({
            "lane": f"{symbol}:{timeframe}", "symbol": symbol, "timeframe": timeframe,
            "activity_observation_count": int(count),
            "activity_earliest_utc": _epoch_text(earliest) if earliest is not None else None,
            "activity_latest_utc": _epoch_text(latest) if latest is not None else None,
            "price_latest_utc": _epoch_text(price_latest) if price_latest is not None else None,
            "activity_state": state, "activity_source_label": ACTIVITY_SOURCE_LABEL,
        })
    return {"contract": "fragarach_ii.mt5_tick_activity_coverage.v1", "lanes": lanes}


def _reconcile_expired_markers(support: str | Path, state: dict[str, Any]) -> None:
    paths = activity_paths(support)
    bridge = bridge_paths(support)
    for marker_path in list(paths["pending"].glob("*.json")):
        request_id = marker_path.stem
        if bridge["pending"].joinpath(marker_path.name).exists():
            continue
        if not bridge["expired"].joinpath(marker_path.name).exists():
            continue
        marker = _read_json(marker_path)
        lane = (state.get("lanes") or {}).get(marker.get("lane"))
        if isinstance(lane, dict):
            lane.update({"state": "RETRY", "last_error": "REQUEST_EXPIRED"})
            lane.pop("request_id", None)
        marker_path.unlink(missing_ok=True)


def _refresh_backfill_status(state: dict[str, Any]) -> None:
    lanes = list((state.get("lanes") or {}).values())
    if lanes and all(lane.get("state") == "COMPLETE" for lane in lanes):
        state.update({"status": "COMPLETE", "enabled": False})
    elif lanes:
        state["status"] = "ACTIVE"
    else:
        state.update({"status": "NO_ELIGIBLE_LANES", "enabled": False})
    state["updated_at_utc"] = datetime.now(UTC).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _datetime_text(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _epoch_text(value: int) -> str:
    return _datetime_text(datetime.fromtimestamp(int(value), UTC))


__all__ = [
    "ACTIVITY_KIND", "ACTIVITY_SOURCE_LABEL", "BACKFILL_CONTRACT",
    "MT5TickActivityError", "activity_coverage", "activity_paths",
    "admit_bridge_activity", "complete_activity_request", "complete_backfill_request",
    "fail_activity_request", "fail_backfill_request", "is_activity_only_request",
    "is_backfill_request", "plan_activity_backfill",
    "queue_activity_backfill_requests", "queue_continuous_activity_requests",
    "start_activity_backfill",
]
