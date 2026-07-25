"""Deterministic acquisition eligibility derived from approved calendars."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .calendars import CalendarRegistry, ConfigurationError, expected_session_dates
from .lane_commissioning import resolved_calendar_id
from .validation.intraday_profiles import is_expected_open, profile_for


def session_close_at(owner_date: date, definition) -> datetime:
    """Return the approved acquisition instant for one D1 owner date."""

    close_date = owner_date + timedelta(
        days=definition.session_close_owner_day_offset
    )
    local = datetime.combine(
        close_date,
        definition.session_close_local,
        ZoneInfo(definition.session_timezone),
    )
    return local.astimezone(UTC) + timedelta(
        seconds=definition.acquisition_delay_seconds
    )


def latest_closed_session_date(definition, observed_at: datetime) -> date | None:
    observed = _utc(observed_at)
    local_date = observed.astimezone(ZoneInfo(definition.session_timezone)).date()
    search_start = max(definition.effective_from, local_date - timedelta(days=370))
    sessions, _ = expected_session_dates(search_start, local_date, definition)
    eligible = [value for value in sessions if session_close_at(value, definition) <= observed]
    return eligible[-1] if eligible else None


def next_d1_acquisition_at(definition, after: datetime) -> datetime | None:
    observed = _utc(after)
    local_date = observed.astimezone(ZoneInfo(definition.session_timezone)).date()
    search_start = max(definition.effective_from, local_date - timedelta(days=1))
    sessions, _ = expected_session_dates(
        search_start, local_date + timedelta(days=370), definition
    )
    for owner_date in sessions:
        boundary = session_close_at(owner_date, definition)
        if boundary > observed:
            return boundary
    return None


def next_intraday_acquisition_at(asset_class: str, timeframe: str, after: datetime) -> datetime:
    observed = _utc(after)
    profile = profile_for(asset_class, timeframe)
    seconds = profile.seconds
    epoch = int(observed.timestamp())
    candidate_close = epoch - (epoch % seconds) + seconds
    for _ in range((14 * 86_400) // seconds):
        interval_open = candidate_close - seconds
        if is_expected_open(interval_open, profile):
            return datetime.fromtimestamp(candidate_close, UTC)
        candidate_close += seconds
    raise ValueError(f"NO_EXPECTED_CLOSED_INTERVAL: {asset_class}:{timeframe}")


def schedule_for_lane(
    connection: sqlite3.Connection,
    *,
    symbol: str,
    timeframe: str,
    after: datetime,
    config_root: str | Path | None = None,
) -> dict[str, object]:
    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()
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
        return {"available": False, "reason_code": "EVIDENCE_LANE_NOT_COMMISSIONED"}
    if timeframe != "D1":
        try:
            profile = profile_for(registration[0], timeframe)
            boundary = next_intraday_acquisition_at(registration[0], timeframe, after)
        except ValueError as error:
            return {
                "available": False,
                "reason_code": "OPERATIONAL_CALENDAR_UNAVAILABLE",
                "reason_detail": str(error),
                "calendar_status": "UNAVAILABLE", "calculation_time": after.isoformat(),
            }
        return {
            "available": True,
            "next_scheduled_acquisition": boundary.isoformat(),
            "calendar_id": profile.calendar_id,
            "calendar_status": "AVAILABLE",
            "timezone": profile.timezone,
            "session_close_rule": profile.session_profile_id,
            "calculation_time": after.isoformat(),
        }

    validation_calendar_id = None
    if registration[3]:
        try:
            validation_calendar_id = json.loads(registration[3]).get("calendar_id")
        except (TypeError, ValueError):
            pass
    calendar_id = resolved_calendar_id(
        asset_class=registration[0],
        calendar_id=registration[1],
        exchange_name=registration[2],
        canonical_symbol=symbol,
    ) or validation_calendar_id
    if not calendar_id:
        return {"available": False, "reason_code": "OPERATIONAL_CALENDAR_UNAVAILABLE", "calendar_status": "UNAVAILABLE", "calculation_time": after.isoformat()}
    try:
        definition = CalendarRegistry(
            config_root, load_symbol_assignments=False
        ).calendar_by_id(calendar_id)
        boundary = next_d1_acquisition_at(definition, after)
    except ConfigurationError as error:
        return {
            "available": False,
            "reason_code": "OPERATIONAL_CALENDAR_UNAVAILABLE",
            "reason_detail": f"{error.code}: {error}",
            "calendar_id": calendar_id, "calendar_status": "UNAVAILABLE", "calculation_time": after.isoformat(),
        }
    return {
        "available": boundary is not None,
        "next_scheduled_acquisition": boundary.isoformat() if boundary else None,
        "calendar_id": calendar_id,
        "reason_code": None if boundary else "NO_FUTURE_OPERATIONAL_SESSION",
        "calendar_status": "AVAILABLE" if boundary is not None else "EXPECTED_EDGE_UNAVAILABLE",
        "timezone": definition.session_timezone,
        "session_close_rule": f"{definition.session_close_local.isoformat()} owner-day offset {definition.session_close_owner_day_offset}; delay {definition.acquisition_delay_seconds}s",
        "calculation_time": after.isoformat(),
    }


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("schedule timestamps must be timezone-aware")
    return value.astimezone(UTC)
