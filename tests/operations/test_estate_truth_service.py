from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.estate_truth_service import ESTATE_TRUTH_CONTRACT, EstateTruthCache, estate_truth_state
from fragarach_ii.commands.estate_truth import main
from fragarach_ii.truth_engine import truth_state_for_lane
from tests.validation.test_d1_session_validation import _create_lane


class EstateTruthServiceTests(unittest.TestCase):
    def test_deterministic_stable_complete_read_only_estate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
            before = database.read_bytes()
            first = estate_truth_state(database)
            second = estate_truth_state(database)
            self.assertEqual(first, second)
            self.assertEqual(first["contract"], ESTATE_TRUTH_CONTRACT)
            self.assertEqual([(lane["symbol"], lane["timeframe"]) for lane in first["truth_matrix"]], [("AUDUSD", "D1")])
            self.assertEqual(first["truth_matrix"][0]["truth_state"], truth_state_for_lane(database, symbol="AUDUSD", timeframe="D1"))
            self.assertEqual(before, database.read_bytes())

    def test_metadata_provider_gaps_and_unknowns_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            lane = estate_truth_state(database)["truth_matrix"][0]
            self.assertEqual(lane["search_metadata"]["canonical_symbol"], "AUDUSD")
            self.assertEqual(lane["search_metadata"]["market"], "NOT_RECORDED")
            self.assertEqual(lane["provider_summary"]["entitlement"], "NOT_MEASURED")
            self.assertIn("entitlement", lane["provider_summary"]["unknown_values"])
            self.assertIsNone(lane["gap_summary"]["current_gap_count"])

    def test_estate_aggregation_is_owned_and_reconciles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            state = estate_truth_state(database)
            summary = state["estate_summary"]
            self.assertEqual(summary["overall_truth_score"], state["truth_matrix"][0]["truth_state"]["truth_score"])
            self.assertEqual(summary["total_symbols"], 1)
            self.assertEqual(summary["green_count"] + summary["amber_count"] + summary["red_count"], 1)
            self.assertTrue(summary["aggregation"])

    def test_cache_load_and_manual_refresh_match_live_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            cache = EstateTruthCache(database)
            live = estate_truth_state(database)
            self.assertEqual(cache.load(), live)
            self.assertEqual(cache.load(), live)
            self.assertEqual(cache.refresh(), live)

    def test_json_command_exposes_the_same_estate_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main(["--database", str(database), "--json"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue()), estate_truth_state(database))


if __name__ == "__main__":
    unittest.main()
