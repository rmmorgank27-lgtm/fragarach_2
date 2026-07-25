from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.estate_truth_service import ESTATE_TRUTH_CONTRACT, EstateTruthCache, _estate_summary, estate_truth_state
from fragarach_ii.commands.estate_truth import main
from fragarach_ii.truth_engine import truth_state_for_lane
from tests.validation.test_d1_session_validation import _create_lane


class EstateTruthServiceTests(unittest.TestCase):
    GENERATED = datetime(2026, 7, 14, 3, 0, tzinfo=UTC)

    def test_deterministic_stable_complete_read_only_estate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
            before = database.read_bytes()
            first = estate_truth_state(database, clock=lambda: self.GENERATED)
            second = estate_truth_state(database, clock=lambda: self.GENERATED)
            self.assertEqual(first, second)
            self.assertEqual(first["contract"], ESTATE_TRUTH_CONTRACT)
            lanes = [(lane["symbol"], lane["timeframe"]) for lane in first["truth_matrix"]]
            self.assertIn(("AUDUSD", "D1"), lanes)
            self.assertIn(("BTCUSD", "D1"), lanes)
            audusd = next(lane for lane in first["truth_matrix"] if lane["symbol"] == "AUDUSD")
            btcusd = next(lane for lane in first["truth_matrix"] if lane["symbol"] == "BTCUSD")
            self.assertEqual(audusd["truth_state"], truth_state_for_lane(database, symbol="AUDUSD", timeframe="D1", as_of=self.GENERATED, authority_generated=self.GENERATED.isoformat()))
            self.assertEqual(btcusd["publication_state"], "REGISTERED_NO_EVIDENCE")
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
            scores = [lane["truth_state"]["truth_score"] for lane in state["truth_matrix"]]
            self.assertEqual(summary["overall_truth_score"], round(sum(scores) / len(scores)))
            self.assertEqual(summary["total_symbols"], len({lane["symbol"] for lane in state["truth_matrix"]}))
            self.assertEqual(summary["green_count"] + summary["amber_count"] + summary["red_count"], len(state["truth_matrix"]))
            self.assertTrue(summary["aggregation"])

    def test_estate_state_uses_most_material_active_lane(self) -> None:
        lanes = [
            {"symbol": "BTCUSD", "truth_state": {"truth_score": 100, "authority_state": "GREEN", "caodt": "2026-07-14T00:00:00+00:00"}},
            {"symbol": "SOLUSD", "truth_state": {"truth_score": 0, "authority_state": "RED", "caodt": "2026-07-14T00:00:00+00:00"}},
        ]
        summary = _estate_summary(lanes, self.GENERATED.isoformat(), None)
        self.assertEqual(summary["overall_truth_score"], 50)
        self.assertEqual(summary["overall_authority_state"], "RED")
        self.assertEqual(summary["aggregation"]["authority_state"], "MOST_MATERIAL_ACTIVE_LANE_CONDITION")

    def test_cache_load_and_manual_refresh_match_live_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            cache = EstateTruthCache(database, clock=lambda: self.GENERATED)
            live = estate_truth_state(database, clock=lambda: self.GENERATED)
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
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["contract"], ESTATE_TRUTH_CONTRACT)
            self.assertEqual(payload["truth_matrix"][0]["latest_canonical_observation"], "2026-07-10T00:00:00+00:00")
            self.assertIn("authority_generated", payload)


if __name__ == "__main__":
    unittest.main()
