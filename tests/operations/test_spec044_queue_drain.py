from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import RateBudgetController
from fragarach_ii.scheduler_service import (
    SchedulerJournal,
    _fair_bounded_selection,
    _scheduled_demand_forecast,
    request_retry,
    request_run_queue,
    run_due_acquisitions,
    update_scheduler_policy,
)
from fragarach_ii.lane_commissioning import ensure_commissioned_lane
from tests.operations.test_spec042_orchestrator import profile
from tests.validation.test_d1_session_validation import _create_lane


class FakeMonotonic:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class Spec044QueueDrainTests(unittest.TestCase):
    def test_twelve_data_queue_ceiling_and_exact_release(self) -> None:
        clock = FakeMonotonic()
        origin = datetime(2026, 7, 14, tzinfo=UTC)
        budget = RateBudgetController(
            limit=55, window_seconds=60, monotonic=clock,
            wall_clock=lambda: origin + timedelta(seconds=clock.value),
        )
        accepted = budget.reserve(44, work_class="QUEUE", queue_percentage=80)
        self.assertTrue(accepted["eligible"])
        self.assertEqual(accepted["queue_ceiling"], 44)
        self.assertEqual(accepted["protected_capacity"], 11)
        blocked = budget.reserve(1, work_class="QUEUE", queue_percentage=80)
        self.assertFalse(blocked["eligible"])
        self.assertEqual(blocked["reason"], "ADAPTIVE_CAPACITY_RESERVED")
        self.assertIsNone(blocked["next_available"])
        normal=budget.reserve(11, work_class="NORMAL");self.assertTrue(normal["eligible"])
        self.assertFalse(budget.reserve(1, work_class="NORMAL")["eligible"])
        budget.dispatch(accepted["reservation_id"],44);budget.dispatch(normal["reservation_id"],11)
        clock.advance(60.001)
        self.assertTrue(budget.reserve(1, work_class="QUEUE", queue_percentage=80)["eligible"])

    def test_multi_request_queue_plan_is_atomic(self) -> None:
        budget = RateBudgetController(limit=55, window_seconds=60, monotonic=lambda: 0.0)
        self.assertTrue(budget.reserve(43, work_class="QUEUE", queue_percentage=80)["eligible"])
        self.assertFalse(budget.reserve(2, work_class="QUEUE", queue_percentage=80)["eligible"])
        state=budget.inspect(work_class="QUEUE", queue_percentage=80)
        self.assertEqual(state["queue_calls_used"],0)
        self.assertEqual(state["queue_calls_reserved"],43)

    def test_policy_persists_and_change_releases_waiting_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            journal = SchedulerJournal(database, journal_path)
            journal.data["acquisition_queue"] = [{
                "id": "AUDUSD:D1:test", "lane": "AUDUSD:D1", "symbol": "AUDUSD", "timeframe": "D1",
                "operational_state": "Waiting for Budget", "next_attempt": "2026-07-14T00:01:00+00:00",
            }]
            journal.save()
            update_scheduler_policy(database, "CONSERVATIVE", journal_path=journal_path)
            changed = update_scheduler_policy(database, "HIGH_THROUGHPUT", journal_path=journal_path)
            self.assertEqual(changed["previous_scheduler_policy"], "Slow")
            restored = SchedulerJournal(database, journal_path)
            self.assertEqual(restored.data["scheduler_policy"], "MAXIMUM_CATCH_UP")
            self.assertNotIn("queue_bandwidth", restored.data)
            self.assertEqual(restored.data["acquisition_queue"][0]["operational_state"], "Ready")
            self.assertIsNone(restored.data["acquisition_queue"][0]["next_attempt"])
            with self.assertRaises(ValueError):
                update_scheduler_policy(database, "FIXED_100_PERCENT", journal_path=journal_path)

    def test_retry_is_deduplicated_and_rebuilds_on_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            now = datetime(2026, 7, 14, 21, tzinfo=UTC)
            first = request_retry(database, lane_id="AUDUSD:D1", journal_path=journal_path, at=now)
            second = request_retry(database, lane_id="AUDUSD:D1", journal_path=journal_path, at=now)
            self.assertEqual(first["outcome"], "RETRY_QUEUED")
            self.assertEqual(second["outcome"], "RETRY_ALREADY_QUEUED")
            lane = SchedulerJournal(database, journal_path).lane("AUDUSD", "D1")
            self.assertTrue(lane["operator_retry_pending"])

    def test_run_queue_releases_waits_without_duplicating_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            journal = SchedulerJournal(database, journal_path)
            item = {
                "id": "AUDUSD:D1:test", "lane": "AUDUSD:D1", "symbol": "AUDUSD", "timeframe": "D1",
                "operational_state": "Waiting for Budget", "next_attempt": "2026-07-15T00:00:00+00:00",
            }
            journal.data["acquisition_queue"] = [item]
            journal.lane("AUDUSD", "D1").update(result="WAITING", provider_attempts_by_boundary={"test": ["TWELVE_DATA"]})
            journal.save()
            request_run_queue(database, journal_path=journal_path, at=datetime(2026, 7, 14, tzinfo=UTC))
            restored = SchedulerJournal(database, journal_path)
            self.assertEqual(len(restored.data["acquisition_queue"]), 1)
            self.assertEqual(restored.data["acquisition_queue"][0]["operational_state"], "Ready")
            self.assertEqual(restored.lane("AUDUSD", "D1")["provider_attempts_by_boundary"], {})

    def test_interrupted_work_recovers_ready_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            payload = SchedulerJournal(database, journal_path).data
            payload["acquisition_queue"] = [{
                "id": "AUDUSD:D1:test", "lane": "AUDUSD:D1", "symbol": "AUDUSD", "timeframe": "D1",
                "operational_state": "Running",
            }]
            journal_path.write_text(json.dumps(payload), encoding="utf-8")
            recovered = SchedulerJournal(database, journal_path)
            self.assertEqual(recovered.data["acquisition_queue"][0]["operational_state"], "Ready")
            self.assertTrue(recovered.data["acquisition_queue"][0]["recovered_after_restart"])
            recovered.save()
            again = SchedulerJournal(database, journal_path)
            self.assertEqual(again.data["acquisition_queue"][0]["operational_state"], "Ready")

    def test_catch_up_boundary_is_attempted_once_across_repeated_drains(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            calls = []

            def acquire(_database, **kwargs):
                calls.append((kwargs["asset"], kwargs["timeframe"]))
                return {"inserted": 1, "corrected": 0}

            provider = (profile("YAHOO_FINANCE", priority=1),)
            first = datetime(2026, 7, 15, 20, tzinfo=UTC)
            run_due_acquisitions(
                database, at=first, credential=None, journal_path=journal_path,
                catch_up=True, acquirer=acquire, provider_profiles=provider,
            )
            run_due_acquisitions(
                database, at=first + timedelta(seconds=1), credential=None,
                journal_path=journal_path, catch_up=True, acquirer=acquire,
                provider_profiles=provider,
            )
            self.assertEqual(calls, [("AUDUSD", "D1")])

    def test_current_and_behind_follow_mandatory_cadence_before_retry(self) -> None:
        class Journal:
            data = {"fairness_cursor": 0}

        def work(lane, timeframe, work_class, retry=False):
            return {
                "symbol": lane, "timeframe": timeframe, "work_class": work_class,
                "retry_due": retry, "missed_boundaries": 5, "expected_edge": "2026-07-14T00:00:00+00:00",
            }

        selected = _fair_bounded_selection([
            work("M5-A", "M5", "QUEUE"), work("M5-B", "M5", "QUEUE"),
            work("H1-A", "H1", "QUEUE"), work("RETRY", "M30", "OPERATOR_RETRY", True),
            work("NORMAL", "D1", "NORMAL"),
        ], None, Journal())
        self.assertEqual([item["symbol"] for item in selected], ["NORMAL"])

    def test_known_m5_boundary_is_forecast_inside_rolling_window(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            journal_path = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            ensure_commissioned_lane(database, "AUDUSD", "M5")
            provider = profile("TWELVE_DATA", priority=1, timeframes=("M5",))
            journal = SchedulerJournal(database, journal_path)
            demand = _scheduled_demand_forecast(
                database, (provider,), datetime(2026, 7, 14, 0, 4, 30, tzinfo=UTC), journal
            )
            self.assertGreaterEqual(demand["TWELVE_DATA"], 1)
            self.assertEqual(journal.providers["TWELVE_DATA"]["next_scheduled_demand"], "2026-07-14T00:05:00+00:00")


if __name__ == "__main__":
    unittest.main()
