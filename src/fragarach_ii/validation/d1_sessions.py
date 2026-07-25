"""D1 session comparison against explicit versioned calendar expectations."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from fragarach_ii.calendars import CalendarRegistry, ConfigurationError
from fragarach_ii.calendars.sessions import expected_session_dates
from fragarach_ii.storage import open_read_only, registered_writer, transaction
from fragarach_ii.storage.migrations import apply_migrations
from fragarach_ii.lane_commissioning import resolved_calendar_id

from .gaps import classify_missing_sessions, coverage_summaries
from .result import ValidationResult


VALIDATOR_VERSION = "SPEC-003_D1_VALIDATOR_V1"
RESULT_FORMAT = "fragarach_ii.d1_session_validation.v1"
Clock = Callable[[], datetime]


class ValidationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def validate_lane(
    database_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    through_date: str,
    persist: bool = False,
    config_root: str | Path | None = None,
    clock: Clock | None = None,
) -> ValidationResult:
    normalized_symbol = symbol.strip().upper()
    normalized_timeframe = timeframe.strip().upper()
    if normalized_timeframe != "D1":
        raise ValidationError(
            "UNSUPPORTED_TIMEFRAME", "SPEC-003 supports D1 validation only"
        )
    boundary = _parse_date(through_date, "INVALID_THROUGH_DATE")
    try:
        registry = CalendarRegistry(config_root, load_symbol_assignments=False)
        authority = open_read_only(database_path)
        try:
            assignment = authority.execute("SELECT calendar_id,calendar_version,gap_doctrine_id,gap_doctrine_version,asset_class,exchange_name FROM instrument_registrations WHERE asset=? AND timeframe=?",(normalized_symbol,normalized_timeframe)).fetchone()
        finally:
            authority.close()
        if assignment is None:
            raise ValidationError("UNREGISTERED_LANE", f"{normalized_symbol}:{normalized_timeframe}")
        if assignment[2:4] != (registry.gap_doctrine.gap_doctrine_id,registry.gap_doctrine.gap_doctrine_version):
            raise ValidationError("GAP_DOCTRINE_MISMATCH", normalized_symbol)
        effective_calendar=resolved_calendar_id(asset_class=assignment[4],calendar_id=assignment[0],exchange_name=assignment[5],canonical_symbol=normalized_symbol)
        if effective_calendar is None:raise ValidationError("CALENDAR_NOT_CONFIGURED",normalized_symbol)
        calendar = registry.calendar_by_id(effective_calendar)
        if calendar.calendar_version != assignment[1]:
            raise ValidationError("CALENDAR_VERSION_MISMATCH", normalized_symbol)
    except ConfigurationError as error:
        raise ValidationError(error.code, str(error)) from error
    if calendar.timeframe != normalized_timeframe:
        raise ValidationError("CALENDAR_TIMEFRAME_MISMATCH", calendar.calendar_id)
    observed_at = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC).isoformat()
    database = Path(database_path).expanduser().resolve()
    if persist:
        with registered_writer(database) as connection:
            apply_migrations(connection)
            with transaction(connection):
                result = _validate_connection(
                    connection,
                    normalized_symbol,
                    normalized_timeframe,
                    boundary,
                    registry,
                    calendar,
                    observed_at,
                )
                cursor = connection.execute(
                    """
                    UPDATE lane_state SET validation_summary = ?
                    WHERE asset = ? AND timeframe = ?
                    """,
                    (
                        result.lane_summary().as_json(),
                        normalized_symbol,
                        normalized_timeframe,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValidationError(
                        "LANE_STATE_NOT_FOUND", f"no lane state for {normalized_symbol} D1"
                    )
                return result
    connection = open_read_only(database)
    try:
        return _validate_connection(
            connection,
            normalized_symbol,
            normalized_timeframe,
            boundary,
            registry,
            calendar,
            observed_at,
        )
    finally:
        connection.close()


def _validate_connection(
    connection: sqlite3.Connection,
    symbol: str,
    timeframe: str,
    boundary: date,
    registry: CalendarRegistry,
    calendar,
    observed_at: str,
) -> ValidationResult:
    rows = connection.execute(
        """
        SELECT open_time_utc FROM bars
        WHERE asset = ? AND timeframe = ?
        ORDER BY open_time_utc
        """,
        (symbol, timeframe),
    ).fetchall()
    if not rows:
        raise ValidationError("LANE_NOT_FOUND", f"no canonical bars for {symbol} {timeframe}")
    dates = [datetime.fromtimestamp(row[0], UTC).date() for row in rows]
    if len(set(dates)) != len(dates):
        raise ValidationError(
            "MULTIPLE_D1_BARS_FOR_DATE", f"multiple canonical keys resolve to one date for {symbol}"
        )
    present = set(dates)
    earliest = min(present)
    latest = max(present)
    within = {value for value in present if value <= boundary}
    beyond = sorted(present - within)
    expected, overrides = expected_session_dates(earliest, boundary, calendar)
    expected_set = set(expected)
    present_expected = within & expected_set
    missing = tuple(value for value in expected if value not in present_expected)
    outside = sorted(within - expected_set)
    weekly, monthly = coverage_summaries(expected, present_expected)
    empty_weeks = {
        value["iso_week"] for value in weekly if not value["has_present_expected_session"]
    }
    empty_months = {
        value["calendar_month"]
        for value in monthly
        if not value["has_present_expected_session"]
    }
    classifications, material_count, non_material_count = classify_missing_sessions(
        expected,
        present_expected,
        empty_weeks,
        empty_months,
        registry.gap_doctrine,
    )
    latest_expected = expected[-1] if expected else None
    factual = {
        "format": RESULT_FORMAT,
        "symbol": symbol,
        "timeframe": timeframe,
        "calendar_id": calendar.calendar_id,
        "calendar_version": calendar.calendar_version,
        "calendar_checksum": calendar.definition_checksum,
        "calendar_registry_checksum": registry.calendar_registry_checksum,
        "symbol_registry_checksum": registry.symbol_registry_checksum,
        "gap_doctrine_id": registry.gap_doctrine.gap_doctrine_id,
        "gap_doctrine_version": registry.gap_doctrine.gap_doctrine_version,
        "gap_doctrine_checksum": registry.gap_doctrine.doctrine_checksum,
        "validator_version": VALIDATOR_VERSION,
        "through_date": boundary.isoformat(),
        "validation_start_date": earliest.isoformat(),
        "earliest_present": earliest.isoformat(),
        "latest_present": latest.isoformat(),
        "latest_present_within_boundary": _iso(max(within) if within else None),
        "expected_session_count": len(expected),
        "present_expected_session_count": len(present_expected),
        "missing_expected_session_count": len(missing),
        "outside_expected_session_count": len(outside),
        "beyond_declared_boundary_count": len(beyond),
        "first_expected_session": _iso(expected[0] if expected else None),
        "last_expected_session": _iso(latest_expected),
        "latest_expected_session": _iso(latest_expected),
        "latest_expected_session_present": latest_expected in present_expected if latest_expected else False,
        "missing_session_dates": [value.isoformat() for value in missing],
        "missing_session_ranges": _missing_ranges(expected, set(missing)),
        "outside_expected_session_dates": [value.isoformat() for value in outside],
        "beyond_declared_boundary_dates": [value.isoformat() for value in beyond],
        "represented_week_count": len(weekly) - len(empty_weeks),
        "empty_week_count": len(empty_weeks),
        "empty_week_ids": sorted(empty_weeks),
        "represented_month_count": len(monthly) - len(empty_months),
        "empty_month_count": len(empty_months),
        "empty_month_ids": sorted(empty_months),
        "material_gap_count": material_count,
        "non_material_gap_count": non_material_count,
        "weekly_summaries": weekly,
        "monthly_summaries": monthly,
        "gap_classifications": classifications,
        "overrides_applied": list(overrides),
    }
    return ValidationResult(factual=factual, validation_observed_at=observed_at)


def _missing_ranges(
    expected: tuple[date, ...], missing: set[date]
) -> list[dict[str, object]]:
    ranges: list[dict[str, object]] = []
    current: list[date] = []
    for value in expected:
        if value in missing:
            current.append(value)
        elif current:
            ranges.append(_range(current))
            current = []
    if current:
        ranges.append(_range(current))
    return ranges


def _range(values: list[date]) -> dict[str, object]:
    return {
        "start": values[0].isoformat(),
        "end": values[-1].isoformat(),
        "expected_session_count": len(values),
    }


def _parse_date(value: str, code: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValidationError(code, f"invalid ISO date: {value}") from error
    if parsed.isoformat() != value:
        raise ValidationError(code, f"date is not canonical ISO text: {value}")
    return parsed


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None
