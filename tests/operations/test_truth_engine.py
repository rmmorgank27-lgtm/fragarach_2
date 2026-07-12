from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.authority_service import serve_historical_authority
from fragarach_ii.truth_engine import TRUTH_STATE_CONTRACT, truth_state_for_lane, truth_states
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
            self.assertEqual(set(first["explanation"]["components"]), {"authority", "freshness", "coverage", "continuity", "validation", "provider"})
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


if __name__ == "__main__":
    unittest.main()
