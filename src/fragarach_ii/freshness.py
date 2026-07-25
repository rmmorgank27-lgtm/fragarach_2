"""Canonical, calendar-derived lane freshness authority."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .calendars import CalendarRegistry, ConfigurationError, expected_session_dates
from .lane_commissioning import resolved_calendar_id
from .operational_schedule import latest_closed_session_date
from .validation.intraday_profiles import expected_opens, profile_for


FRESHNESS_CONTRACT = "fragarach_ii.lane_freshness.v1"
AUTHORITY_REVISION_VERSION = 3
_BASIS = (
    "OPERATIONAL_CALENDAR",
    "TIMEFRAME",
    "LATEST_CANONICAL_OBSERVATION",
)
_RUNTIME_OVERRIDE_CACHE: dict[str, tuple[int, int, dict[str, object]]] = {}
_RUNTIME_OVERRIDE_CACHE_LOCK = threading.Lock()


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalized_utc(value: datetime | None = None) -> datetime:
    result = value or utc_now()
    if result.tzinfo is None:
        raise ValueError("authority timestamps must be timezone-aware")
    return result.astimezone(UTC)


def iso_utc_epoch(epoch_seconds: int | None) -> str | None:
    if epoch_seconds is None:
        return None
    return datetime.fromtimestamp(epoch_seconds, UTC).isoformat()


def assess_lane_freshness(
    connection: sqlite3.Connection,
    *,
    symbol: str,
    timeframe: str,
    as_of: datetime | None = None,
    config_root: str | Path | None = None,
) -> dict[str, object]:
    """Assess currency solely from calendar, timeframe, and canonical edge."""

    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()
    observed_at = normalized_utc(as_of)
    registration = connection.execute(
        """
        SELECT r.asset_class,r.calendar_id,r.exchange_name,s.validation_summary
        FROM evidence_lanes l
        JOIN instrument_registrations r
          ON r.asset=l.asset AND r.timeframe=l.registration_timeframe
        LEFT JOIN lane_state s ON s.asset=l.asset AND s.timeframe=l.timeframe
        WHERE l.asset=? AND l.timeframe=?
        """,
        (symbol, timeframe),
    ).fetchone()
    if registration is None:
        return _unavailable(
            symbol, timeframe, observed_at, "EVIDENCE_LANE_NOT_COMMISSIONED"
        )

    # ``bars`` is keyed by ``(asset, timeframe, open_time_utc)``.  The old
    # max/max/count aggregate walked every historical bar for a lane on each
    # normal scheduler wake.  One active M5 lane can hold millions of rows,
    # turning a four-worker catch-up batch into a multi-minute SQLite scan.
    # The final canonical bar is sufficient for freshness and is an indexed
    # reverse lookup on the primary key.
    latest_row = connection.execute(
        """
        SELECT open_time_utc,close_time_utc
        FROM bars WHERE asset=? AND timeframe=?
        ORDER BY open_time_utc DESC LIMIT 1
        """,
        (symbol, timeframe),
    ).fetchone()
    latest_epoch = None
    if latest_row:
        latest_epoch = latest_row[0] if timeframe == "D1" else latest_row[1]

    if timeframe == "D1":
        return _assess_d1(
            symbol=symbol,
            observed_at=observed_at,
            latest_epoch=latest_epoch,
            asset_class=registration[0],
            registered_calendar_id=registration[1],
            exchange_name=registration[2],
            validation_summary=registration[3],
            config_root=config_root,
        )
    return _assess_intraday(
        connection=connection,
        symbol=symbol,
        timeframe=timeframe,
        observed_at=observed_at,
        latest_epoch=latest_epoch,
        asset_class=registration[0],
        config_root=config_root,
    )


def authority_revision_for_lane(
    connection: sqlite3.Connection, *, symbol: str, timeframe: str,
    current_event_ids: list[str] | None = None,
) -> str:
    """Return a stable revision that advances when lane authority is published."""

    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()
    registration = connection.execute(
        """
        SELECT asset,timeframe,instrument_family,local_symbol,asset_class,
               representation_type,provider_id,provider_contract,provider_symbol,
               calendar_id,calendar_version,gap_doctrine_id,gap_doctrine_version,
               registration_status
        FROM instrument_registrations WHERE asset=? AND timeframe='D1'
        """,
        (symbol,),
    ).fetchone()
    lane = connection.execute(
        """
        SELECT asset,timeframe,registration_timeframe,lane_contract,lane_contract_version,
               created_at_utc
        FROM evidence_lanes WHERE asset=? AND timeframe=?
        """,
        (symbol, timeframe),
    ).fetchone()
    publication = connection.execute(
        """SELECT state_version,last_ingest_run_id,updated_at_utc
           FROM lane_state WHERE asset=? AND timeframe=?""",
        (symbol, timeframe),
    ).fetchone()
    events = connection.execute(
        """
        SELECT e.authority_event_id
        FROM authority_events e
        WHERE NOT EXISTS (
            SELECT 1 FROM authority_events successor
            WHERE successor.supersedes_event_id=e.authority_event_id
        ) AND (
            (e.entity_kind='INSTRUMENT_REGISTRATION'
             AND (json_extract(e.canonical_payload,'$.body.asset')=?
                  OR json_extract(e.canonical_payload,'$.body.legacy_key.asset')=?))
            OR
            (e.entity_kind='EVIDENCE_LANE'
             AND (json_extract(e.canonical_payload,'$.body.asset')=?
                  OR json_extract(e.canonical_payload,'$.body.legacy_key.asset')=?)
             AND (json_extract(e.canonical_payload,'$.body.timeframe')=?
                  OR json_extract(e.canonical_payload,'$.body.legacy_key.timeframe')=?))
        )
        ORDER BY e.entity_kind,e.authority_event_id
        """,
        (symbol, symbol, symbol, symbol, timeframe, timeframe),
    ).fetchall() if current_event_ids is None else [(event_id,) for event_id in current_event_ids]
    payload = {
        "authority_revision_version": AUTHORITY_REVISION_VERSION,
        "registration": list(registration) if registration else None,
        "lane": list(lane) if lane else None,
        "publication": list(publication) if publication else None,
        "current_authority_events": [row[0] for row in events],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _assess_d1(
    *,
    symbol: str,
    observed_at: datetime,
    latest_epoch: int | None,
    asset_class: str,
    registered_calendar_id: str,
    exchange_name: str | None,
    validation_summary: str | None,
    config_root: str | Path | None,
) -> dict[str, object]:
    validation_calendar_id = None
    if validation_summary:
        try:
            value = json.loads(validation_summary)
            validation_calendar_id = value.get("calendar_id")
        except (json.JSONDecodeError, TypeError):
            validation_calendar_id = None
    calendar_id = resolved_calendar_id(
        asset_class=asset_class,
        calendar_id=registered_calendar_id,
        exchange_name=exchange_name,
        canonical_symbol=symbol,
    ) or validation_calendar_id
    if not calendar_id:
        return _unavailable(
            symbol,
            "D1",
            observed_at,
            "OPERATIONAL_CALENDAR_UNAVAILABLE",
            latest_epoch=latest_epoch,
            detail="no approved calendar identity resolves for the lane",
        )
    try:
        definition = CalendarRegistry(
            config_root, load_symbol_assignments=False
        ).calendar_by_id(calendar_id)
    except ConfigurationError as error:
        return _unavailable(
            symbol,
            "D1",
            observed_at,
            "OPERATIONAL_CALENDAR_UNAVAILABLE",
            latest_epoch=latest_epoch,
            calendar_id=calendar_id,
            detail=f"{error.code}: {error}",
        )

    expected_date = latest_closed_session_date(definition, observed_at)
    if expected_date is None:
        return _unavailable(
            symbol,
            "D1",
            observed_at,
            "NO_EXPECTED_OPERATIONAL_SESSION",
            latest_epoch=latest_epoch,
            calendar_id=calendar_id,
        )
    expected_epoch = int(datetime.combine(expected_date, datetime.min.time(), UTC).timestamp())
    if latest_epoch is None:
        return _unavailable(
            symbol,
            "D1",
            observed_at,
            "NO_CANONICAL_OBSERVATION",
            expected_epoch=expected_epoch,
            calendar_id=calendar_id,
        )
    latest_date = datetime.fromtimestamp(latest_epoch, UTC).date()
    lag_dates, _ = expected_session_dates(
        max(definition.effective_from, latest_date + timedelta(days=1)),
        expected_date,
        definition,
    )
    policy = _crypto_operational_policy(config_root) if asset_class == "CRYPTO" else {}
    return _available(
        symbol=symbol,
        timeframe="D1",
        observed_at=observed_at,
        latest_epoch=latest_epoch,
        expected_epoch=expected_epoch,
        lag_count=len(lag_dates),
        lag_unit="trading_day",
        calendar_id=calendar_id,
        critical_after=_critical_threshold(policy, "D1"),
    )


def _assess_intraday(
    *,
    connection: sqlite3.Connection,
    symbol: str,
    timeframe: str,
    observed_at: datetime,
    latest_epoch: int | None,
    asset_class: str,
    config_root: str | Path | None,
) -> dict[str, object]:
    try:
        profile = profile_for(asset_class, timeframe)
    except ValueError as error:
        return _unavailable(
            symbol,
            timeframe,
            observed_at,
            "OPERATIONAL_CALENDAR_UNAVAILABLE",
            latest_epoch=latest_epoch,
            detail=str(error),
        )
    policy = _crypto_operational_policy(config_root) if asset_class == "CRYPTO" else {}
    # This is an operational display/scheduling tolerance, not an alteration
    # of canonical evidence.  It is deliberately stored beside the scheduler
    # runtime so an operator can tune an overly-tight M5 boundary without
    # changing a checked-in calendar definition.
    runtime = _runtime_freshness_override(connection, timeframe)
    if runtime:
        policy = {**policy, **runtime}
    publication_delay = int(policy.get("allowed_publication_delay_seconds", 0))
    boundary = int(observed_at.timestamp()) - publication_delay
    lookback = boundary - 14 * 86_400
    lookback -= lookback % profile.seconds
    expected = expected_opens(lookback, boundary, profile)
    if not expected:
        return _unavailable(
            symbol,
            timeframe,
            observed_at,
            "NO_EXPECTED_CLOSED_INTERVAL",
            latest_epoch=latest_epoch,
            calendar_id=profile.calendar_id,
        )
    expected_epoch = expected[-1] + profile.seconds
    if latest_epoch is None:
        return _unavailable(
            symbol,
            timeframe,
            observed_at,
            "NO_CANONICAL_OBSERVATION",
            expected_epoch=expected_epoch,
            calendar_id=profile.calendar_id,
        )
    lag_count = len(expected_opens(latest_epoch, boundary, profile))
    return _available(
        symbol=symbol,
        timeframe=timeframe,
        observed_at=observed_at,
        latest_epoch=latest_epoch,
        expected_epoch=expected_epoch,
        lag_count=lag_count,
        lag_unit="closed_interval",
        calendar_id=profile.calendar_id,
        critical_after=_critical_threshold(policy, timeframe),
    )


def _available(
    *,
    symbol: str,
    timeframe: str,
    observed_at: datetime,
    latest_epoch: int,
    expected_epoch: int,
    lag_count: int,
    lag_unit: str,
    calendar_id: str,
    critical_after: int | None = None,
) -> dict[str, object]:
    current = latest_epoch >= expected_epoch
    critical = not current and critical_after is not None and lag_count >= critical_after
    return {
        "contract": FRESHNESS_CONTRACT,
        "symbol": symbol,
        "timeframe": timeframe,
        "state": "Current" if current else "Behind",
        "severity": "HEALTHY" if current else "CRITICAL" if critical else "ATTENTION",
        "operational_state": "Current" if current else "Critically Behind" if critical else "Behind",
        "latest_canonical_observation": iso_utc_epoch(latest_epoch),
        "expected_latest": iso_utc_epoch(expected_epoch),
        "expected_edge_state": (
            "NO_NEW_COMPLETED_SESSION" if current else "EXPECTED_EDGE_AVAILABLE"
        ),
        "lag": {"count": 0 if current else lag_count, "unit": lag_unit},
        "lag_seconds": max(0, expected_epoch - latest_epoch),
        "critical_after_closed_boundaries": critical_after,
        "reason_code": (
            "LATEST_CANONICAL_OBSERVATION_AT_OR_AHEAD_OF_EXPECTED_LATEST"
            if current
            else "LATEST_CANONICAL_OBSERVATION_BEHIND_EXPECTED_LATEST"
        ),
        "calendar_id": calendar_id,
        "as_of": observed_at.replace(microsecond=0).isoformat(),
        "basis": list(_BASIS),
    }


def _unavailable(
    symbol: str,
    timeframe: str,
    observed_at: datetime,
    reason_code: str,
    *,
    latest_epoch: int | None = None,
    expected_epoch: int | None = None,
    calendar_id: str | None = None,
    detail: str | None = None,
) -> dict[str, object]:
    expected_edge_state = (
        "EXPECTED_EDGE_AVAILABLE" if expected_epoch is not None
        else "INSTRUMENT_CALENDAR_UNRESOLVED"
        if reason_code == "OPERATIONAL_CALENDAR_UNAVAILABLE" and calendar_id is None
        else "CALENDAR_UNAVAILABLE"
        if reason_code == "OPERATIONAL_CALENDAR_UNAVAILABLE"
        else "MARKET_CLOSED"
        if reason_code in {"NO_EXPECTED_OPERATIONAL_SESSION","NO_EXPECTED_CLOSED_INTERVAL"}
        else "CALENDAR_UNAVAILABLE"
    )
    return {
        "contract": FRESHNESS_CONTRACT,
        "symbol": symbol,
        "timeframe": timeframe,
        "state": "Unavailable",
        "severity": "UNAVAILABLE",
        "operational_state": "Unavailable",
        "latest_canonical_observation": iso_utc_epoch(latest_epoch),
        "expected_latest": iso_utc_epoch(expected_epoch),
        "expected_edge_state": expected_edge_state,
        "lag": {"count": None, "unit": None},
        "reason_code": reason_code,
        "reason_detail": detail,
        "calendar_id": calendar_id,
        "as_of": observed_at.replace(microsecond=0).isoformat(),
        "basis": list(_BASIS),
    }


def _crypto_operational_policy(config_root: str | Path | None) -> dict[str, object]:
    root = Path(config_root) if config_root else Path(__file__).resolve().parents[2] / "config/calendars"
    try:
        payload = json.loads((root / "crypto_d1.v1.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if payload.get("continuous_operation") == "24/7" else {}


def _runtime_freshness_override(connection: sqlite3.Connection, timeframe: str) -> dict[str, object]:
    """Read one scheduler-runtime override from the SQLite control authority."""
    try:
        database = next(
            row[2] for row in connection.execute("PRAGMA database_list") if row[1] == "main"
        )
        journal = Path(f"{database}.scheduler.json")
        from .scheduler_state_store import SchedulerStateStore
        payload = SchedulerStateStore(database, journal).load()
        if not isinstance(payload, dict):
            # One-release compatibility for authorities not yet migrated by a
            # SchedulerJournal save.
            stamp = journal.stat()
            key = str(journal.resolve())
            with _RUNTIME_OVERRIDE_CACHE_LOCK:
                cached = _RUNTIME_OVERRIDE_CACHE.get(key)
                if cached and cached[0] == stamp.st_mtime_ns and cached[1] == stamp.st_size:
                    payload = cached[2]
                else:
                    payload = json.loads(journal.read_text(encoding="utf-8"))
                    _RUNTIME_OVERRIDE_CACHE[key] = (stamp.st_mtime_ns, stamp.st_size, payload)
        overrides = payload.get("freshness_overrides", {})
        value = overrides.get(timeframe, {}) if isinstance(overrides, dict) else {}
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, StopIteration, TypeError):
        return {}


def _critical_threshold(policy: dict[str, object], timeframe: str) -> int | None:
    thresholds = policy.get("freshness_thresholds", {})
    row = thresholds.get(timeframe, {}) if isinstance(thresholds, dict) else {}
    try:
        return max(1, int(row["critical_after_closed_boundaries"]))
    except (KeyError, TypeError, ValueError):
        return None
