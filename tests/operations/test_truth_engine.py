from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.authority_service import serve_historical_authority
from fragarach_ii.truth_engine import TRUTH_STATE_CONTRACT, _calculate, truth_state_for_lane, truth_states
from tests.validation.test_d1_session_validation import _create_lane


class TruthEngineTests(unittest.TestCase):
    def test_truth_state_is_deterministic_explainable_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
            before = database.read_bytes()
            first = truth_state_for_lane(database, symbol="AUDUSD", timeframe="D1")
            second = truth_state_for_lane(database, symbol="AUDUSD", timeframe="D1")
            self.assertEqual(first, second)
            self.assertEqual(first["contract"], TRUTH_STATE_CONTRACT)
            self.assertEqual(set(first["explanation"]["components"]), {"authority", "integrity", "freshness", "historical_depth", "continuity", "provider"})
            self.assertEqual(sum(first["explanation"]["weights"].values()), 100)
            self.assertTrue(first["explanation"]["method"])
            self.assertEqual(before, database.read_bytes())

    def test_unknown_persisted_facts_remain_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            state = truth_state_for_lane(database, symbol="AUDUSD", timeframe="D1")
            self.assertIsNone(state["provider_score"])
            self.assertIsNone(state["freshness_score"])
            self.assertIsNone(state["validation_score"])
            self.assertEqual(state["provider_summary"]["confidence"], "NOT_MEASURED")
            self.assertEqual(state["epoch"], "UNKNOWN")
            self.assertIn("PROVIDER_NOT_MEASURED", state["explanation"]["limitations"])

    def test_authority_service_consumes_engine_state_without_range_dependent_truth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
            complete = serve_historical_authority(database, symbol="AUDUSD", timeframe="D1")
            latest = complete["historical_bars"][-1]["open_time_utc"]
            sliced = serve_historical_authority(database, symbol="AUDUSD", timeframe="D1", start_time_utc=latest)
            engine = truth_state_for_lane(database, symbol="AUDUSD", timeframe="D1")
            self.assertEqual(complete["truth_state"], engine)
            self.assertEqual(sliced["truth_state"], engine)
            self.assertEqual(complete["truth_score"]["score"], engine["truth_score"])

    def test_one_state_per_authoritative_lane_and_no_consumer_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            states = truth_states(database)
            self.assertEqual([(state["symbol"], state["timeframe"]) for state in states], [("AUDUSD", "D1")])
            self.assertNotIn("consumer", copy.deepcopy(states[0]))

    def test_long_history_with_old_non_material_gaps_beats_short_clean_history(self) -> None:
        short = _state("H1", 30, expected=500, present=500)
        long = _state("H1", 1_096, expected=20_000, present=19_000)
        self.assertGreater(long["truth_score"], short["truth_score"])
        self.assertGreater(long["historical_depth_score"], short["historical_depth_score"])
        self.assertGreaterEqual(long["continuity_score"], 90)

    def test_extending_lane_backwards_with_valid_bars_is_monotonic(self) -> None:
        short = _state("M30", 30, expected=1_000, present=1_000)
        extended = _state("M30", 365, expected=12_000, present=12_000)
        self.assertGreaterEqual(extended["truth_score"], short["truth_score"])

    def test_depth_is_normalized_independently_for_each_authorised_timeframe(self) -> None:
        scores = {
            timeframe: _state(timeframe, 365, expected=1_000, present=1_000)["historical_depth_score"]
            for timeframe in ("D1", "H1", "M30", "M5")
        }
        self.assertEqual(set(scores), {"D1", "H1", "M30", "M5"})
        self.assertLess(scores["D1"], scores["H1"])
        self.assertLess(scores["H1"], scores["M30"])
        self.assertLess(scores["M30"], scores["M5"])

    def test_recent_material_gap_lowers_truth(self) -> None:
        clean = _state("H1", 365, expected=6_000, present=6_000)
        gapped = _state("H1", 365, expected=6_000, present=5_999, material=1)
        self.assertLess(gapped["truth_score"], clean["truth_score"])

    def test_rejected_or_conflicting_evidence_cannot_improve_canonical_truth(self) -> None:
        canonical = _state("M5", 90, expected=20_000, present=20_000)
        same_canonical_after_rejection = _state("M5", 90, expected=20_000, present=20_000)
        self.assertEqual(same_canonical_after_rejection, canonical)

    def test_current_edge_freshness_is_the_dominant_component(self) -> None:
        fresh = _state("H1", 30, expected=500, present=500)
        stale = _state("H1", 1_096, expected=20_000, present=19_999, material=1, latest=False)
        self.assertLess(stale["truth_score"], fresh["truth_score"])
        self.assertEqual(fresh["explanation"]["weights"]["freshness"], 30)
        self.assertGreater(fresh["explanation"]["weights"]["freshness"], fresh["explanation"]["weights"]["historical_depth"])


def _state(timeframe: str, span_days: int, *, expected: int, present: int, material: int = 0, latest: bool = True):
    interval = {"D1": 86_400, "H1": 3_600, "M30": 1_800, "M5": 300}[timeframe]
    latest_epoch = 1_800_000_000
    validation = {
        "format": "fragarach_ii.lane_validation_summary.v1" if timeframe == "D1" else "fragarach_ii.lane_validation_summary.v2",
        "expected_session_count" if timeframe == "D1" else "expected_interval_count": expected,
        "present_expected_session_count" if timeframe == "D1" else "present_expected_interval_count": present,
        "missing_expected_session_count" if timeframe == "D1" else "missing_expected_interval_count": expected - present,
        "outside_expected_session_count" if timeframe == "D1" else "outside_expected_interval_count": 0,
        "latest_expected_session_present" if timeframe == "D1" else "latest_expected_closed_interval_present": latest,
        "material_gap_count": material,
        "non_material_gap_count": expected - present - material,
    }
    return _calculate(
        "AUDUSD",
        timeframe,
        ("TWELVE_DATA", "CONTRACT", "AUD/USD", "REGISTERED_WITH_EVIDENCE"),
        (present, latest_epoch - span_days * 86_400 + interval, latest_epoch, latest_epoch + interval),
        validation,
        ("ledger",),
    )


if __name__ == "__main__":
    unittest.main()
