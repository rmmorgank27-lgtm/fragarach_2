from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.lane_commissioning import ensure_commissioned_lane
from fragarach_ii.lane_freshness_service import lane_freshness_report
from fragarach_ii.storage import open_read_only, registered_writer
from fragarach_ii.truth_engine import truth_state_for_lane
from fragarach_ii.validation import validate_lane
from tests.validation.test_d1_session_validation import _create_lane, _epoch


class Spec040FreshnessTests(unittest.TestCase):
    def test_stale_persisted_validation_cannot_keep_lane_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            validated_at = datetime(2026, 7, 13, 23, 0, tzinfo=UTC)
            result = validate_lane(
                database,
                symbol="AUDUSD",
                timeframe="D1",
                through_date="2026-07-13",
                persist=True,
                clock=lambda: validated_at,
            )
            self.assertTrue(result.as_dict()["latest_expected_session_present"])
            truth = truth_state_for_lane(
                database,
                symbol="AUDUSD",
                timeframe="D1",
                as_of=datetime(2026, 7, 14, 22, 0, tzinfo=UTC),
            )
            self.assertEqual(truth["latest_canonical_observation"], "2026-07-13T00:00:00+00:00")
            self.assertEqual(truth["freshness"]["expected_latest"], "2026-07-14T00:00:00+00:00")
            self.assertEqual(truth["freshness"]["state"], "Behind")
            self.assertEqual(truth["freshness_score"], 0)

    def test_d1_and_intraday_latest_observations_use_the_canonical_edge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "XAUUSD", ["2026-07-13"])
            for timeframe in ("H1", "M30", "M5"):
                ensure_commissioned_lane(
                    database,
                    "XAUUSD",
                    timeframe,
                    observed_at="2026-07-13T00:00:00+00:00",
                )
            observations = {
                "H1": ("2026-07-13T03:00:00+00:00", "2026-07-13T04:00:00+00:00"),
                "M30": ("2026-07-13T03:30:00+00:00", "2026-07-13T04:00:00+00:00"),
                "M5": ("2026-07-13T04:00:00+00:00", "2026-07-13T04:05:00+00:00"),
            }
            with registered_writer(database) as connection:
                for timeframe, (open_text, close_text) in observations.items():
                    open_epoch = int(datetime.fromisoformat(open_text).timestamp())
                    close_epoch = int(datetime.fromisoformat(close_text).timestamp())
                    connection.execute(
                        """INSERT INTO bars
                           (asset,timeframe,open_time_utc,close_time_utc,open,high,low,close,
                            created_by_ingest_run_id,updated_by_ingest_run_id)
                           VALUES ('XAUUSD',?,?,?,'1','2','0','1','run-1','run-1')""",
                        (timeframe, open_epoch, close_epoch),
                    )
            generated = datetime(2026, 7, 13, 4, 5, tzinfo=UTC)
            report = lane_freshness_report(database, clock=lambda: generated)
            rows = {
                row["timeframe"]: row
                for row in report["lanes"]
                if row["symbol"] == "XAUUSD"
            }
            self.assertEqual(rows["D1"]["actual_latest"], "2026-07-13T00:00:00+00:00")
            for timeframe, (_, close_text) in observations.items():
                self.assertEqual(rows[timeframe]["actual_latest"], close_text)
                self.assertEqual(rows[timeframe]["freshness"]["state"], "Current")

    def test_audit_reports_current_behind_and_unavailable_with_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            current_db = Path(directory) / "authority.sqlite3"
            _create_lane(current_db, "AUDUSD", ["2026-07-13"])
            ensure_commissioned_lane(
                current_db,
                "AUDUSD",
                "H1",
                observed_at="2026-07-13T00:00:00+00:00",
            )
            as_of = datetime(2026, 7, 14, 2, 0, tzinfo=UTC)
            report = lane_freshness_report(current_db, clock=lambda: as_of)
            rows = {
                row["timeframe"]: row
                for row in report["lanes"]
                if row["symbol"] == "AUDUSD"
            }
            self.assertEqual(rows["D1"]["freshness"]["state"], "Current")
            self.assertEqual(rows["D1"]["reason"], "CURRENT_AT_APPROVED_OPERATIONAL_EDGE")
            self.assertEqual(rows["H1"]["freshness"]["state"], "Unavailable")
            self.assertEqual(rows["H1"]["reason"], "NO_CANONICAL_OBSERVATION")
            self.assertEqual(report["scheduler"]["state"], "IMPLEMENTED")
            self.assertEqual(
                set(report["summary"]) - {"total"},
                {"Current", "Behind", "Unavailable"},
            )

    def test_freshness_audit_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            before = database.read_bytes()
            lane_freshness_report(
                database,
                clock=lambda: datetime(2026, 7, 14, 2, 0, tzinfo=UTC),
            )
            self.assertEqual(before, database.read_bytes())
            with open_read_only(database) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT max(open_time_utc) FROM bars WHERE asset='AUDUSD' AND timeframe='D1'"
                    ).fetchone()[0],
                    _epoch("2026-07-13"),
                )


if __name__ == "__main__":
    unittest.main()
