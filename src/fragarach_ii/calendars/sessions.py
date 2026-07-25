"""Expected-session generation from an explicit calendar definition."""

from __future__ import annotations

from datetime import date, timedelta

from .models import CalendarDefinition
from .rules import australian_equities_holidays,good_friday,uk_equities_holidays,us_equities_holidays


def session_classification(
    value: date, definition: CalendarDefinition
) -> tuple[bool, dict[str, str] | None]:
    if value < definition.effective_from or (
        definition.effective_to is not None and value > definition.effective_to
    ):
        return False, None
    for override in definition.overrides:
        if override.date == value:
            return (
                override.classification == "EXPECTED_OVERRIDE",
                {
                    "date": value.isoformat(),
                    "classification": override.classification,
                    "reason": override.reason,
                },
            )
    if value.isoweekday() not in definition.weekdays_expected:
        return False, None
    for closure in definition.recurring_full_day_closures:
        if (value.month, value.day) == (closure.month, closure.day):
            return False, None
    if "GOOD_FRIDAY" in definition.calculated_closures and value == good_friday(value.year):
        return False, None
    if "US_EQUITIES_HOLIDAYS" in definition.calculated_closures and value in us_equities_holidays(value.year):
        return False, None
    if "AUSTRALIAN_EQUITIES_HOLIDAYS" in definition.calculated_closures and value in australian_equities_holidays(value.year):
        return False, None
    if "UK_EQUITIES_HOLIDAYS" in definition.calculated_closures and value in uk_equities_holidays(value.year):
        return False, None
    return True, None


def expected_session_dates(
    start: date, end: date, definition: CalendarDefinition
) -> tuple[tuple[date, ...], tuple[dict[str, str], ...]]:
    if end < start:
        return (), ()
    sessions: list[date] = []
    overrides: list[dict[str, str]] = []
    current = start
    while current <= end:
        expected, override = session_classification(current, definition)
        if expected:
            sessions.append(current)
        if override is not None:
            overrides.append(override)
        current += timedelta(days=1)
    return tuple(sessions), tuple(overrides)
