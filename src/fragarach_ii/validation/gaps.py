"""Published V1 gap classification over missing expected sessions."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from fragarach_ii.calendars.models import GapDoctrine


def classify_missing_sessions(
    expected: tuple[date, ...],
    present_expected: set[date],
    empty_weeks: set[str],
    empty_months: set[str],
    doctrine: GapDoctrine,
) -> tuple[list[dict[str, object]], int, int]:
    missing = [value for value in expected if value not in present_expected]
    latest_present = max(present_expected) if present_expected else None
    edge = {
        value for value in missing if latest_present is None or value > latest_present
    }
    classifications: list[dict[str, object]] = []
    material_count = non_material_count = 0
    for value in missing:
        iso = value.isocalendar()
        week_id = f"{iso.year:04d}-W{iso.week:02d}"
        month_id = value.strftime("%Y-%m")
        reasons = []
        if value in edge:
            reasons.append("CURRENT_EDGE_MISSING")
        if week_id in empty_weeks:
            reasons.append("EMPTY_EXPECTED_WEEK")
        if month_id in empty_months:
            reasons.append("EMPTY_EXPECTED_MONTH")
        reasons = [reason for reason in doctrine.material_classes if reason in reasons]
        if reasons:
            classification = doctrine.material_wording
            material_count += 1
        else:
            reasons = ["ISOLATED_EXPECTED_SESSION_MISSING"]
            classification = doctrine.non_material_wording
            non_material_count += 1
        classifications.append(
            {
                "date": value.isoformat(),
                "classification": classification,
                "reasons": reasons,
            }
        )
    return classifications, material_count, non_material_count


def coverage_summaries(
    expected: tuple[date, ...], present_expected: set[date]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    weeks: dict[str, list[date]] = defaultdict(list)
    months: dict[str, list[date]] = defaultdict(list)
    for value in expected:
        iso = value.isocalendar()
        weeks[f"{iso.year:04d}-W{iso.week:02d}"].append(value)
        months[value.strftime("%Y-%m")].append(value)
    return (
        [_coverage_item(key, values, present_expected, "iso_week") for key, values in sorted(weeks.items())],
        [_coverage_item(key, values, present_expected, "calendar_month") for key, values in sorted(months.items())],
    )


def _coverage_item(
    key: str, expected: list[date], present: set[date], identity_key: str
) -> dict[str, object]:
    present_count = sum(value in present for value in expected)
    return {
        identity_key: key,
        "expected_session_count": len(expected),
        "present_expected_session_count": present_count,
        "missing_expected_session_count": len(expected) - present_count,
        "has_present_expected_session": present_count > 0,
    }
