from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import RateBudgetController, update_provider_health
from fragarach_ii.retirement import RetirementError, reactivate_instrument, retire_instrument
from fragarach_ii.scheduler_service import (
    SchedulerJournal,
    pause_acquisition,
    request_retry,
    resume_acquisition,
    run_due_acquisitions,
    run_operator_fetch,
    scheduler_snapshot,
)
from fragarach_ii.lane_update_register import LaneUpdateRegister
from fragarach_ii.storage import registered_writer
from tests.operations.test_spec042_orchestrator import profile
from tests.validation.test_d1_session_validation import OBSERVED, _create_lane, _epoch


class Spec046OperationalIntegrityTests(unittest.TestCase):
    def test_incorrect_identity_is_archived_but_evidence_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            journal = SchedulerJournal(database, journal_path)
            journal.data["acquisition_queue"] = [{
                "id": "AUDUSD:D1:old", "lane": "AUDUSD:D1", "symbol": "AUDUSD",
                "timeframe": "D1", "operational_state": "Ready",
            }]
            journal.data["manual_requests"] = [{
                "id": "manual-old", "symbol": "AUDUSD", "timeframe": "D1",
                "status": "Required", "missing_start": "2026-07-14",
                "missing_end": "2026-07-14", "expected_canonical_edge": "2026-07-14T00:00:00+00:00",
            }]
            journal.save()
            receipt = retire_instrument(
                database, "AUDUSD", scope="WHOLE_INSTRUMENT", selected_lanes=("D1",),
                reason="INCORRECT_INSTRUMENT_IDENTITY", operator_note="reviewed",
                typed_confirmation="RETIRE AUDUSD", completed_at="2026-07-14T00:00:00+00:00",
            )
            snapshot = scheduler_snapshot(
                database, journal_path=journal_path,
                clock=lambda: datetime(2026, 7, 14, 20, tzinfo=UTC),
            )
            self.assertEqual(receipt["affected_canonical_bars"], 1)
            self.assertFalse(snapshot["acquisition_queue"])
            self.assertFalse(snapshot["manual_requests"])
            self.assertFalse(any(lane["symbol"] == "AUDUSD" for lane in snapshot["lanes"]))
            reasons = {item["reason"] for item in snapshot["archived_operational_work"]}
            self.assertIn("INCORRECT_INSTRUMENT_IDENTITY", reasons)
            with self.assertRaisesRegex(ValueError, "inactive"):
                request_retry(database, lane_id="AUDUSD:D1", journal_path=journal_path)
            with self.assertRaises(RetirementError):
                reactivate_instrument(database, "AUDUSD")

    def test_reservation_and_dispatch_accounting_are_distinct_and_atomic(self) -> None:
        budget = RateBudgetController(limit=5, window_seconds=60, monotonic=lambda: 0.0)
        reservation = budget.reserve(3)
        self.assertEqual(budget.inspect()["calls_used"], 0)
        self.assertEqual(budget.inspect()["reserved_calls"], 3)
        budget.dispatch(reservation["reservation_id"], 1)
        self.assertEqual(budget.inspect()["calls_used"], 1)
        self.assertEqual(budget.inspect()["reserved_calls"], 2)
        self.assertEqual(budget.release(reservation["reservation_id"]), 2)
        self.assertEqual(budget.inspect()["calls_used"], 1)
        self.assertEqual(budget.inspect()["reserved_calls"], 0)

    def test_cooldown_truth_requires_remote_proof_and_preserves_scope(self) -> None:
        provider = profile("TWELVE_DATA", priority=1)
        now = datetime(2026, 7, 14, tzinfo=UTC)
        timeout_state = {}
        update_provider_health(timeout_state, provider, "TWELVEDATA_TRANSPORT_FAILURE", now, lane="AUDUSD:D1")
        self.assertIsNone(timeout_state.get("cooldown"))
        remote_state = {}
        update_provider_health(remote_state, provider, "TWELVEDATA_RATE_LIMIT_429", now, lane="AUDUSD:D1", request_id="request-1", response_class="HTTP_429")
        self.assertEqual(remote_state["wait_reason"], "CREDIT_WINDOW_EXHAUSTED")
        self.assertEqual(remote_state["wait_scope"], "CREDIT_WINDOW")
        self.assertEqual(remote_state["health"], "Healthy")
        self.assertIsNone(remote_state.get("cooldown"))

    def test_pause_hierarchy_persists_and_cannot_be_bypassed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            group = pause_acquisition(
                database, scope_type="MARKET_OR_GROUP", scope_identifier="Forex",
                journal_path=journal_path,
            )
            symbol = pause_acquisition(
                database, scope_type="SYMBOL", scope_identifier="AUDUSD",
                journal_path=journal_path,
            )
            resume_acquisition(database, pause_identifier=symbol["pause_identifier"], journal_path=journal_path)
            snapshot = scheduler_snapshot(database, journal_path=journal_path)
            lane = next(item for item in snapshot["lanes"] if item["id"] == "AUDUSD:D1")
            self.assertEqual(lane["pause_state"], "Paused")
            self.assertIn(group["pause_identifier"], lane["pause_effective_sources"])
            with self.assertRaisesRegex(ValueError, "pause"):
                request_retry(database, lane_id="AUDUSD:D1", journal_path=journal_path)
            restored = SchedulerJournal(database, journal_path)
            self.assertTrue(any(item["status"] == "PAUSED" for item in restored.data["pause_records"]))

    def test_operator_fetch_identifies_the_pause_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            pause_acquisition(
                database, scope_type="SYMBOL", scope_identifier="AUDUSD",
                journal_path=journal_path,
            )

            with self.assertRaisesRegex(ValueError, "SYMBOL:AUDUSD"):
                run_operator_fetch(
                    database, symbol="AUDUSD", timeframe="D1", credential="fixture",
                    journal_path=journal_path,
                )

    def test_resuming_symbol_pause_does_not_reset_unrelated_blocked_lane(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            now = datetime(2026, 7, 14, 20, tzinfo=UTC)
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            with registered_writer(database) as connection:
                timestamp = _epoch("2026-07-13")
                connection.execute(
                    """INSERT INTO bars
                       (asset,timeframe,open_time_utc,open,high,low,close,
                        created_by_ingest_run_id,updated_by_ingest_run_id)
                       VALUES ('XAUUSD','D1',?,'1','2','0','1','run-1','run-1')""",
                    (timestamp,),
                )
                connection.execute(
                    """INSERT INTO provenance
                       (provenance_event_id,ingest_run_id,raw_block_id,symbol,timeframe,
                        timestamp,source_row_number,merge_action,candidate_open,
                        candidate_high,candidate_low,candidate_close,recorded_at)
                       VALUES ('event-xauusd','run-1','raw-1','XAUUSD','D1',?,2,
                               'INSERT','1','2','0','1',?)""",
                    (timestamp, OBSERVED.isoformat()),
                )
                connection.execute(
                    """INSERT INTO lane_state
                       (asset,timeframe,high_watermark_open_time_utc,state_version,
                        last_ingest_run_id,updated_at_utc)
                       VALUES ('XAUUSD','D1',?,1,'run-1',?)""",
                    (timestamp, OBSERVED.isoformat()),
                )
            register = LaneUpdateRegister(database)
            register.initialize_if_needed(at=now)
            register.block(asset="XAUUSD", timeframe="D1", reason="PROVIDER_REPAIR_REQUIRED", at=now)

            pause = pause_acquisition(
                database, scope_type="SYMBOL", scope_identifier="AUDUSD",
                journal_path=journal_path, at=now,
            )
            resume_acquisition(
                database, pause_identifier=pause["pause_identifier"], journal_path=journal_path, at=now,
            )

            rows = {f"{row['asset']}:{row['timeframe']}": row for row in register.rows()}
            self.assertEqual(rows["AUDUSD:D1"]["state"], "READY")
            self.assertEqual(rows["XAUUSD:D1"]["state"], "BLOCKED")

    def test_pause_drains_dispatched_work_before_becoming_fully_paused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            journal = SchedulerJournal(database, journal_path)
            journal.data["request_lifecycle"] = [{"id": "request-1", "lane": "AUDUSD:D1", "state": "DISPATCHED"}]
            journal.save()
            pause = pause_acquisition(database, scope_type="SYMBOL", scope_identifier="AUDUSD", journal_path=journal_path)
            self.assertEqual(pause["status"], "DRAINING_ACTIVE_WORK")
            journal = SchedulerJournal(database, journal_path)
            journal.data["request_lifecycle"][0]["state"] = "RESPONSE_RECEIVED"
            journal.save()
            snapshot = scheduler_snapshot(database, journal_path=journal_path)
            restored = next(item for item in snapshot["pause_records"] if item["pause_identifier"] == pause["pause_identifier"])
            self.assertEqual(restored["status"], "PAUSED")

    def test_symbol_pause_does_not_stop_an_unpaused_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            pause_acquisition(database, scope_type="SYMBOL", scope_identifier="AUDUSD", journal_path=journal_path)
            calls = []
            run_due_acquisitions(
                database, at=datetime(2026, 7, 14, 21, tzinfo=UTC), credential=None,
                journal_path=journal_path, provider_profiles=(profile("YAHOO_FINANCE", priority=1),),
                acquirer=lambda _database, **kwargs: calls.append(kwargs["asset"]) or {"inserted": 1, "corrected": 0},
            )
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
