"""Deterministic full validation result and persisted-summary projection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from fragarach_ii.storage import LaneValidationSummary


@dataclass(frozen=True, slots=True)
class ValidationResult:
    factual: dict[str, Any]
    validation_observed_at: str

    @property
    def result_checksum(self) -> str:
        serialized = json.dumps(
            self.factual, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.factual,
            "result_checksum": self.result_checksum,
            "validation_observed_at": self.validation_observed_at,
        }

    def as_json(self) -> str:
        return json.dumps(
            self.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

    def lane_summary(self) -> LaneValidationSummary:
        value = self.as_dict()
        return LaneValidationSummary(
            symbol=value["symbol"],
            timeframe=value["timeframe"],
            calendar_id=value["calendar_id"],
            calendar_version=value["calendar_version"],
            calendar_checksum=value["calendar_checksum"],
            gap_doctrine_id=value["gap_doctrine_id"],
            gap_doctrine_version=value["gap_doctrine_version"],
            gap_doctrine_checksum=value["gap_doctrine_checksum"],
            validator_version=value["validator_version"],
            through_date=value["through_date"],
            expected_session_count=value["expected_session_count"],
            present_expected_session_count=value["present_expected_session_count"],
            missing_expected_session_count=value["missing_expected_session_count"],
            outside_expected_session_count=value["outside_expected_session_count"],
            empty_week_count=value["empty_week_count"],
            empty_month_count=value["empty_month_count"],
            latest_expected_session=value["latest_expected_session"],
            latest_expected_session_present=value["latest_expected_session_present"],
            material_gap_count=value["material_gap_count"],
            non_material_gap_count=value["non_material_gap_count"],
            result_checksum=value["result_checksum"],
            validation_observed_at=value["validation_observed_at"],
        )
