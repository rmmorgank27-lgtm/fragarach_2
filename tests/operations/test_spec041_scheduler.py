from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.freshness import authority_revision_for_lane
from fragarach_ii.authority_service import serve_historical_authority
from fragarach_ii.lane_commissioning import ensure_commissioned_lane
from fragarach_ii.scheduler_service import run_due_acquisitions, scheduler_snapshot
from fragarach_ii.storage import open_read_only, register_instrument, registered_writer
from tests.operations.test_spec025_intraday import candidate
from tests.validation.test_d1_session_validation import _create_lane


def _epoch(text: str) -> int:
    return int(datetime.fromisoformat(text).timestamp())


def _add_intraday_bar(database: Path, symbol: str, timeframe: str, opened: str, closed: str) -> None:
    with registered_writer(database) as connection:
        connection.execute(
            """INSERT INTO bars
               (asset,timeframe,open_time_utc,close_time_utc,open,high,low,close,
                created_by_ingest_run_id,updated_by_ingest_run_id)
               VALUES (?,?,?,?, '1','2','0','1','run-1','run-1')""",
            (symbol, timeframe, _epoch(opened), _epoch(closed)),
        )
        connection.execute(
            """UPDATE lane_state SET high_watermark_open_time_utc=?,
               state_version=state_version+1,updated_at_utc=?
               WHERE asset=? AND timeframe=?""",
            (_epoch(opened), closed, symbol, timeframe),
        )


class Spec041SchedulerTests(unittest.TestCase):
    def test_startup_snapshot_loads_every_lane_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            snapshot = scheduler_snapshot(
                database, clock=lambda: datetime(2026, 7, 14, 20, tzinfo=UTC)
            )
            self.assertEqual(snapshot["contract"], "fragarach_ii.scheduler_monitor.v2")
            self.assertEqual(snapshot["service_state"], "Running")
            self.assertGreaterEqual(snapshot["summary"]["total"], 1)
            audusd = next(row for row in snapshot["lanes"] if row["id"] == "AUDUSD:D1")
            self.assertEqual(audusd["scheduler_state"], "Current")

    def test_m5_close_acquires_only_due_m5_lane(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            for timeframe in ("M5", "H1"):
                ensure_commissioned_lane(database, "AUDUSD", timeframe)
            _add_intraday_bar(database, "AUDUSD", "M5", "2026-07-14T00:00:00+00:00", "2026-07-14T00:05:00+00:00")
            _add_intraday_bar(database, "AUDUSD", "H1", "2026-07-14T00:00:00+00:00", "2026-07-14T01:00:00+00:00")
            calls = []

            def acquire(_database, **kwargs):
                calls.append((kwargs["asset"], kwargs["timeframe"]))
                return {"inserted": 1, "corrected": 0}

            run_due_acquisitions(
                database,
                at=datetime(2026, 7, 14, 0, 10, tzinfo=UTC),
                credential="fixture",
                journal_path=journal,
                acquirer=acquire,
            )
            self.assertEqual(calls, [("AUDUSD", "M5")])

    def test_h1_and_d1_use_their_approved_close_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            ensure_commissioned_lane(database, "AUDUSD", "H1")
            _add_intraday_bar(database, "AUDUSD", "H1", "2026-07-14T00:00:00+00:00", "2026-07-14T01:00:00+00:00")
            calls = []

            def acquire(_database, **kwargs):
                calls.append(kwargs["timeframe"])
                return {"inserted": 1, "corrected": 0}

            run_due_acquisitions(
                database,
                at=datetime(2026, 7, 14, 2, 0, tzinfo=UTC),
                credential="fixture",
                journal_path=journal,
                acquirer=acquire,
            )
            self.assertEqual(calls, ["H1"])
            calls.clear()
            run_due_acquisitions(
                database,
                at=datetime(2026, 7, 14, 21, 0, tzinfo=UTC),
                credential="fixture",
                journal_path=journal,
                acquirer=acquire,
            )
            self.assertIn("D1", calls)

    def test_lane_failure_is_isolated_and_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            register_instrument(
                database,
                replace(
                    candidate(),
                    asset="EURUSD",
                    instrument_family="EURUSD",
                    local_symbol="EURUSD",
                    display_name="Euro / US Dollar",
                    provider_symbol="EUR/USD",
                ),
                registered_at_utc="2026-07-13T00:00:00+00:00",
            )
            with registered_writer(database) as connection:
                edge = _epoch("2026-07-13T00:00:00+00:00")
                connection.execute(
                    """INSERT INTO bars
                       (asset,timeframe,open_time_utc,open,high,low,close,
                        created_by_ingest_run_id,updated_by_ingest_run_id)
                       VALUES ('EURUSD','D1',?,'1','2','0','1','run-1','run-1')""",
                    (edge,),
                )
                connection.execute(
                    """INSERT INTO lane_state
                       (asset,timeframe,high_watermark_open_time_utc,state_version,
                        last_ingest_run_id,updated_at_utc)
                       VALUES ('EURUSD','D1',?,1,'run-1','2026-07-13T00:00:00+00:00')""",
                    (edge,),
                )
            for symbol in ("AUDUSD", "EURUSD"):
                ensure_commissioned_lane(database, symbol, "M5")
                _add_intraday_bar(database, symbol, "M5", "2026-07-14T00:00:00+00:00", "2026-07-14T00:05:00+00:00")
            calls = []

            def acquire(_database, **kwargs):
                calls.append(kwargs["asset"])
                if kwargs["asset"] == "AUDUSD":
                    raise RuntimeError("provider unavailable")
                return {"inserted": 1, "corrected": 0}

            snapshot = run_due_acquisitions(
                database,
                at=datetime(2026, 7, 14, 0, 10, tzinfo=UTC),
                credential="fixture",
                journal_path=journal,
                acquirer=acquire,
            )
            self.assertEqual(calls, ["AUDUSD", "EURUSD"])
            states = {row["symbol"]: row["scheduler_state"] for row in snapshot["lanes"] if row["timeframe"] == "M5"}
            self.assertEqual(states["AUDUSD"], "Behind")
            self.assertEqual(
                next(row for row in snapshot["acquisition_queue"] if row["lane"] == "AUDUSD:M5")["stop_reason"],
                "DISPATCH_REJECTED",
            )
            self.assertEqual(snapshot["last_failure"] is not None, True)

    def test_success_advances_publication_revision_and_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            with open_read_only(database) as connection:
                before = authority_revision_for_lane(connection, symbol="AUDUSD", timeframe="D1")

            def acquire(_database, **_kwargs):
                _kwargs["progress"]("requesting")
                _kwargs["progress"]("validating")
                _kwargs["progress"]("ingesting")
                with registered_writer(database) as connection:
                    edge = _epoch("2026-07-14T00:00:00+00:00")
                    connection.execute(
                        """INSERT INTO bars
                           (asset,timeframe,open_time_utc,open,high,low,close,
                            created_by_ingest_run_id,updated_by_ingest_run_id)
                           VALUES ('AUDUSD','D1',?,'1','2','0','1','run-1','run-1')""",
                        (edge,),
                    )
                    connection.execute(
                        """UPDATE lane_state SET high_watermark_open_time_utc=?,
                           state_version=state_version+1,updated_at_utc=?
                           WHERE asset='AUDUSD' AND timeframe='D1'""",
                        (edge, "2026-07-14T21:00:00+00:00"),
                    )
                return {"inserted": 1, "corrected": 0}

            emitted = []
            snapshot = run_due_acquisitions(
                database,
                at=datetime(2026, 7, 14, 21, 0, tzinfo=UTC),
                credential="fixture",
                journal_path=journal,
                acquirer=acquire,
                emit=emitted.append,
            )
            with open_read_only(database) as connection:
                after = authority_revision_for_lane(connection, symbol="AUDUSD", timeframe="D1")
            self.assertNotEqual(before, after)
            audusd = next(row for row in snapshot["lanes"] if row["id"] == "AUDUSD:D1")
            self.assertEqual(audusd["scheduler_state"], "Current")
            self.assertIn(snapshot["authority_health"]["state"], {"HEALTHY", "DEGRADED"})
            stages = [value["active_activity"]["stage"] for value in emitted if value["active_activity"] and value["active_activity"]["symbol"] == "AUDUSD"]
            self.assertEqual(stages, ["Downloading", "Downloading", "Validating", "Publishing"])
            published = serve_historical_authority(database, symbol="AUDUSD", timeframe="D1")
            self.assertEqual(published["latest_canonical_observation"], "2026-07-14T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
