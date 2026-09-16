from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.estate_truth_service import ESTATE_TRUTH_CONTRACT, EstateTruthCache, _estate_summary, _overlay_synthetic_m15_products, estate_truth_state
from fragarach_ii.commands.estate_truth import main
from fragarach_ii.truth_engine import truth_state_for_lane
from fragarach_ii.lane_update_register import LaneUpdateRegister
from fragarach_ii.storage import registered_writer
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

    def test_provider_summary_uses_latest_canonical_bar_source_not_legacy_registration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            with registered_writer(database) as connection:
                connection.execute(
                    """INSERT INTO ingest_runs(
                           ingest_run_id,kind,status,started_at_utc,finished_at_utc,detail
                       ) VALUES('current-route-run','test','committed',?,?,?)""",
                    (self.GENERATED.isoformat(), self.GENERATED.isoformat(), json.dumps({
                        "format": "fragarach_ii.ingest_outcome.v1",
                        "source_rows": 1, "staged": 1, "inserted": 0,
                        "corrected": 1, "unchanged": 0,
                        "conflicts_preserved": 0, "rejected": 0, "rejections": [],
                        "provider": "CURRENT_ROUTE",
                        "provider_contract": "CURRENT_ROUTE_D1_V1",
                        "provider_symbol": "AUDUSD.CURRENT",
                    })),
                )
                connection.execute(
                    """UPDATE bars SET updated_by_ingest_run_id='current-route-run'
                       WHERE asset='AUDUSD' AND timeframe='D1'"""
                )

            lane = next(
                item for item in estate_truth_state(database)["truth_matrix"]
                if item["symbol"] == "AUDUSD" and item["timeframe"] == "D1"
            )
            self.assertEqual(lane["provider_summary"]["provider"], "CURRENT_ROUTE")
            self.assertEqual(lane["provider_summary"]["provider_symbol"], "AUDUSD.CURRENT")

    def test_current_synthetic_m15_replaces_retained_legacy_raw_m15_projection(self) -> None:
        source={"symbol":"NAS100","timeframe":"M5","authority_revision":"sha256:source","freshness":{"state":"Current","lag":{"count":0,"unit":"closed_interval"}},"truth_state":{"symbol":"NAS100","timeframe":"M5","authority_state":"GOLD"},"evidence_integrity":{},"acquisition_dimension":{},"provider_summary":{"provider":"FUSION_MARKETS_MT5"},"gap_summary":{}}
        legacy={"symbol":"NAS100","timeframe":"M15","truth_state":{"authority_state":"RED"}}
        product={"id":"NAS100:M15","symbol":"NAS100","target_timeframe":"M15","registration_status":"ACTIVE","status":"Incomplete","immediate_source_symbol":"NAS100","immediate_source_timeframe":"M5","immediate_source_evidence_class":"REAL","source_revision":"sha256:source","synthetic_revision":7,"content_checksum":"sha256:content","latest_synthetic_observation":1784083500,"calendar_authority":"MT5_BROKER_INDEX_CFD_24X5_UTC_V1","aggregation_rule":"MT5_BROKER_INDEX_CFD_M5_TO_M15_UTC_V1"}
        lane=next(item for item in _overlay_synthetic_m15_products([legacy,source],[product]) if item["timeframe"]=="M15")
        self.assertEqual(lane["freshness"]["state"],"Current")
        self.assertEqual(lane["truth_state"]["authority_state"],"GOLD")
        self.assertEqual(lane["provider_summary"]["evidence_class"],"SYNTHETIC")

    def test_scheduler_block_overrides_green_operational_presentation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
            observed = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
            register = LaneUpdateRegister(database)
            register.audit_estate(at=observed, reason="TEST")
            register.block(
                asset="AUDUSD", timeframe="D1",
                reason="LOCAL_PROGRAMMING_ERROR; transient network misclassification",
                at=observed, approved=True,
            )

            lane = next(
                item for item in estate_truth_state(
                    database, clock=lambda: observed
                )["truth_matrix"]
                if item["symbol"] == "AUDUSD" and item["timeframe"] == "D1"
            )

            self.assertEqual(lane["freshness"]["state"], "Current")
            self.assertEqual(lane["truth_state"]["authority_state"], "RED")
            self.assertLessEqual(lane["truth_state"]["truth_score"], 70)
            self.assertEqual(lane["overall_operational_state"], "Critical")
            self.assertEqual(lane["acquisition_dimension"]["state"], "SCHEDULER_BLOCKED")
            self.assertEqual(lane["acquisition_dimension"]["scheduler_state"]["state"], "BLOCKED")
            self.assertIn(
                "SCHEDULER_LANE_BLOCKED",
                lane["truth_state"]["explanation"]["limitations"],
            )

    def test_estate_aggregation_is_owned_and_reconciles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            state = estate_truth_state(database)
            summary = state["estate_summary"]
            scores = [lane["truth_state"]["truth_score"] for lane in state["truth_matrix"]]
            self.assertEqual(summary["overall_truth_score"], round(sum(scores) / len(scores)))
            self.assertEqual(summary["total_symbols"], len({lane["symbol"] for lane in state["truth_matrix"]}))
            self.assertEqual(summary["gold_count"] + summary["green_count"] + summary["amber_count"] + summary["red_count"], len(state["truth_matrix"]))
            self.assertTrue(summary["aggregation"])

    def test_one_critical_lane_does_not_override_a_healthy_estate_score(self) -> None:
        lanes = [
            {"symbol": f"GREEN{index}", "truth_state": {"truth_score": 100, "authority_state": "GREEN", "caodt": "2026-07-14T00:00:00+00:00"}}
            for index in range(9)
        ] + [
            {"symbol": "RED1", "truth_state": {"truth_score": 0, "authority_state": "RED", "caodt": "2026-07-14T00:00:00+00:00"}},
        ]
        summary = _estate_summary(lanes, self.GENERATED.isoformat(), None)
        self.assertEqual(summary["overall_truth_score"], 90)
        self.assertEqual(summary["overall_authority_state"], "GREEN")
        self.assertEqual(summary["red_count"], 1)
        self.assertEqual(summary["aggregation"]["authority_state"], "NO_OPERATIONAL_FINDINGS_THEN_EQUAL_WEIGHT_MEAN_OF_LANE_TRUTH_SCORES")

    def test_low_quality_score_without_operational_findings_is_healthy(self) -> None:
        lanes = [
            {"symbol": "AUDCAD", "truth_state": {"truth_score": 88, "authority_state": "GREEN", "caodt": "2026-07-14T00:00:00+00:00"}},
            {"symbol": "AUDJPY", "truth_state": {"truth_score": 78, "authority_state": "GREEN", "caodt": "2026-07-14T00:00:00+00:00"}},
        ]
        summary = _estate_summary(lanes, self.GENERATED.isoformat(), None)
        self.assertEqual(summary["overall_truth_score"], 83)
        self.assertEqual(summary["overall_authority_state"], "GREEN")

    def test_estate_state_uses_score_threshold_when_no_lane_is_critical(self) -> None:
        lanes = [
            {"symbol": "BTCUSD", "truth_state": {"truth_score": 96, "authority_state": "GREEN", "caodt": "2026-07-14T00:00:00+00:00"}},
            {"symbol": "SOLUSD", "truth_state": {"truth_score": 88, "authority_state": "AMBER", "caodt": "2026-07-14T00:00:00+00:00"}},
        ]
        summary = _estate_summary(lanes, self.GENERATED.isoformat(), None)
        self.assertEqual(summary["overall_truth_score"], 92)
        self.assertEqual(summary["overall_authority_state"], "GREEN")

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
