"""Canonical lane validation-summary contract introduced by SPEC-003A."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime


VALIDATION_SUMMARY_FORMAT = "fragarach_ii.lane_validation_summary.v1"
_CHECKSUM = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class LaneValidationSummary:
    symbol: str
    timeframe: str
    calendar_id: str
    calendar_version: int
    calendar_checksum: str
    gap_doctrine_id: str
    gap_doctrine_version: int
    gap_doctrine_checksum: str
    validator_version: str
    through_date: str
    expected_session_count: int
    present_expected_session_count: int
    missing_expected_session_count: int
    outside_expected_session_count: int
    empty_week_count: int
    empty_month_count: int
    latest_expected_session: str | None
    latest_expected_session_present: bool
    material_gap_count: int
    non_material_gap_count: int
    result_checksum: str
    validation_observed_at: str

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol != self.symbol.strip().upper():
            raise ValueError("symbol must be a normalized non-empty identity")
        if not self.timeframe or self.timeframe != self.timeframe.strip().upper():
            raise ValueError("timeframe must be a normalized non-empty identity")
        for name in ("calendar_id", "gap_doctrine_id", "validator_version"):
            if not getattr(self, name):
                raise ValueError(f"{name} must not be empty")
        for name in ("calendar_version", "gap_doctrine_version"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("calendar_checksum", "gap_doctrine_checksum", "result_checksum"):
            if not _CHECKSUM.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        _require_iso_date(self.through_date, "through_date")
        if self.latest_expected_session is not None:
            _require_iso_date(self.latest_expected_session, "latest_expected_session")
        try:
            observed = datetime.fromisoformat(self.validation_observed_at)
        except ValueError as error:
            raise ValueError("validation_observed_at must be ISO 8601") from error
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("validation_observed_at must include an offset")
        count_names = (
            "expected_session_count",
            "present_expected_session_count",
            "missing_expected_session_count",
            "outside_expected_session_count",
            "empty_week_count",
            "empty_month_count",
            "material_gap_count",
            "non_material_gap_count",
        )
        for name in count_names:
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if (
            self.present_expected_session_count + self.missing_expected_session_count
            != self.expected_session_count
        ):
            raise ValueError("present plus missing must equal expected sessions")
        if not isinstance(self.latest_expected_session_present, bool):
            raise ValueError("latest_expected_session_present must be boolean")

    def as_dict(self) -> dict[str, object]:
        return {"format": VALIDATION_SUMMARY_FORMAT, **asdict(self)}

    def as_json(self) -> str:
        """Return deterministic canonical JSON for the complete summary."""

        return json.dumps(
            self.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )


def _require_iso_date(value: str, name: str) -> None:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO calendar date") from error
    if parsed.isoformat() != value:
        raise ValueError(f"{name} must use canonical ISO calendar-date text")
