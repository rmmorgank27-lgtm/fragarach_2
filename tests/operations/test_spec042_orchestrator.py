from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import (
    ProviderProfile,
    RateBudgetController,
    acquisition_plan,
    build_rate_budgets,
    classify_failure,
    create_manual_request,
    dismiss_manual_request,
    resolve_satisfied_manual_requests,
    update_provider_health,
)
from fragarach_ii.providers.twelve_data import AcquisitionError
from fragarach_ii.scheduler_service import SchedulerJournal, run_due_acquisitions
from fragarach_ii.storage import registered_writer
from tests.validation.test_d1_session_validation import _create_lane


class FakeMonotonic:
    def __init__(self) -> None: self.value = 0.0
    def __call__(self) -> float: return self.value
    def advance(self, seconds: float) -> None: self.value += seconds


def profile(
    provider: str, *, priority: int, cost: int = 0,
    mapping: bool = True, credential: bool = False,
    timeframes=("D1",), asset_classes=("FX",), limit: int = 55,
) -> ProviderProfile:
    return ProviderProfile(
        provider=provider, enabled=True,
        supported_asset_classes=tuple(asset_classes),
        supported_timeframes=tuple(timeframes),
        credential_environment=(f"{provider}_API_KEY" if credential else None),
        entitlement_state="AVAILABLE", request_limit=limit,
        request_window_seconds=60, maximum_rows_per_request=4000,
        history_limit_days=None, cost_class=cost, priority=priority,
        cooldown_seconds=120,
        mappings=(({"asset": "AUDUSD", "symbol": "AUDUSD=X", "timeframes": ["D1"]},) if mapping else ()),
        operational_limit=50 if provider == "TWELVE_DATA" else limit,
        dispatch_interval_seconds=1.2 if provider == "TWELVE_DATA" else 0,
    )


class Spec042OrchestratorTests(unittest.TestCase):
    def test_deterministic_routing_rejects_unsupported_before_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            profiles = (
                profile("UNSUPPORTED", priority=1, timeframes=("H1",)),
                profile("EXPENSIVE", priority=10, cost=3),
                profile("CHEAP", priority=10, cost=0),
            )
            budgets = build_rate_budgets(profiles, {}, monotonic=lambda: 1.0, wall_clock=lambda: datetime(2026, 7, 14, tzinfo=UTC))
            kwargs = dict(
                database_path=database, symbol="AUDUSD", timeframe="D1",
                canonical_edge="2026-07-13T00:00:00+00:00",
                expected_edge="2026-07-14T00:00:00+00:00",
                missing_start="2026-07-14", missing_end="2026-07-14",
                scheduled_boundary="2026-07-14T21:00:00+00:00",
                profiles=profiles, provider_state={}, budgets=budgets,
                credentials={}, now=datetime(2026, 7, 14, 21, tzinfo=UTC),
            )
            first = acquisition_plan(**kwargs); second = acquisition_plan(**kwargs)
            self.assertEqual(first, second)
            self.assertEqual(first["selected_provider"], "CHEAP")
            rejected = {item["provider"]: item["reason"] for item in first["providers_considered"]}
            self.assertEqual(rejected["UNSUPPORTED"], "TIMEFRAME_UNSUPPORTED")

    def test_twelve_data_budget_never_exceeds_55_and_reports_exact_time(self) -> None:
        clock = FakeMonotonic()
        wall = datetime(2026, 7, 14, 0, 0, tzinfo=UTC)
        controller = RateBudgetController(limit=55, window_seconds=60, monotonic=clock, wall_clock=lambda: wall + timedelta(seconds=clock.value))
        reservation=controller.reserve(54);self.assertTrue(reservation["eligible"])
        controller.dispatch(reservation["reservation_id"],54)
        blocked = controller.reserve(2)
        self.assertFalse(blocked["eligible"])
        self.assertEqual(blocked["calls_used"], 54)
        self.assertEqual(blocked["next_available"], "2026-07-14T00:01:00+00:00")
        clock.advance(60.001)
        replacement=controller.reserve(2);self.assertTrue(replacement["eligible"])
        controller.dispatch(replacement["reservation_id"],2)
        self.assertLessEqual(controller.inspect()["calls_used"], 55)

    def test_retryable_failure_fails_over_sequentially(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"; journal = Path(directory) / "scheduler.json"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            profiles = (
                profile("TWELVE_DATA", priority=10, credential=True, mapping=False),
                profile("YAHOO_FINANCE", priority=20),
            )
            calls=[]
            def acquire(_database, **kwargs):
                calls.append(kwargs["provider"])
                if kwargs["provider"] == "TWELVE_DATA":
                    raise AcquisitionError("PROVIDER_TIMEOUT", "timed out")
                edge=int(datetime(2026,7,14,tzinfo=UTC).timestamp())
                with registered_writer(database) as connection:
                    run_id=connection.execute("SELECT created_by_ingest_run_id FROM bars WHERE asset='AUDUSD' LIMIT 1").fetchone()[0]
                    connection.execute("INSERT OR IGNORE INTO bars(asset,timeframe,open_time_utc,open,high,low,close,created_by_ingest_run_id,updated_by_ingest_run_id) VALUES('AUDUSD','D1',?,'1','2','0','1',?,?)",(edge,run_id,run_id))
                    connection.execute("UPDATE lane_state SET high_watermark_open_time_utc=?,state_version=state_version+1 WHERE asset='AUDUSD' AND timeframe='D1'",(edge,))
                return {"inserted": 1, "corrected": 0}
            snapshot=run_due_acquisitions(
                database, at=datetime(2026,7,14,21,tzinfo=UTC), credential="fixture",
                journal_path=journal, acquirer=acquire, provider_profiles=profiles,
            )
            self.assertEqual(calls,["TWELVE_DATA","YAHOO_FINANCE"])
            audusd=next(event for event in snapshot["events"] if event.get("symbol")=="AUDUSD" and event.get("id","").startswith("AUDUSD"))
            self.assertEqual(audusd["result"],"SUCCESS")
            failover=next(event for event in snapshot["events"] if event.get("provider")=="TWELVE_DATA")
            self.assertEqual(failover["next_provider"],"YAHOO_FINANCE")

    def test_no_eligible_provider_creates_one_restart_safe_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database=Path(directory)/"authority.sqlite3";journal_path=Path(directory)/"scheduler.json"
            _create_lane(database,"AUDUSD",["2026-07-13"])
            profiles=(profile("NONE",priority=1,mapping=False),)
            for _ in range(2):
                run_due_acquisitions(database,at=datetime(2026,7,14,21,tzinfo=UTC),credential=None,journal_path=journal_path,provider_profiles=profiles)
            journal=SchedulerJournal(database,journal_path)
            audusd=[request for request in journal.manual_requests if request["symbol"]=="AUDUSD"]
            self.assertEqual(len(audusd),1)
            self.assertEqual(audusd[0]["status"],"Required")

    def test_provider_health_and_manual_status_transitions(self) -> None:
        now=datetime(2026,7,14,tzinfo=UTC);provider=profile("TWELVE_DATA",priority=1)
        state={}
        for _ in range(3): update_provider_health(state,provider,"TWELVEDATA_TRANSPORT_FAILURE",now)
        self.assertEqual(state["health"],"Degraded")
        self.assertIsNone(state.get("cooldown_until"))
        self.assertIsNone(state["wait_reason"])
        update_provider_health(state,provider,"SUCCESS",now+timedelta(minutes=3))
        self.assertEqual(state["health"],"Healthy")
        requests=[]
        first=create_manual_request(requests,symbol="AUDUSD",timeframe="D1",missing_start="2026-07-14",missing_end="2026-07-14",expected_edge="2026-07-14T00:00:00+00:00",reason="NO_ELIGIBLE_PROVIDER",providers_attempted=[],failures=[],now=now)
        second=create_manual_request(requests,symbol="AUDUSD",timeframe="D1",missing_start="2026-07-14",missing_end="2026-07-14",expected_edge="2026-07-14T00:00:00+00:00",reason="NO_ELIGIBLE_PROVIDER",providers_attempted=[],failures=[],now=now)
        self.assertEqual(first["id"],second["id"])
        dismiss_manual_request(requests,first["id"],now)
        self.assertEqual(first["status"],"Dismissed")

    def test_manual_request_resolves_only_after_canonical_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database=Path(directory)/"authority.sqlite3";_create_lane(database,"AUDUSD",["2026-07-13"])
            now=datetime(2026,7,14,21,tzinfo=UTC);requests=[]
            request=create_manual_request(requests,symbol="AUDUSD",timeframe="D1",missing_start="2026-07-14",missing_end="2026-07-14",expected_edge="2026-07-14T00:00:00+00:00",reason="ALL_PROVIDERS_EXHAUSTED",providers_attempted=["TWELVE_DATA"],failures=[],now=now)
            self.assertFalse(resolve_satisfied_manual_requests(database,requests,now))
            self.assertEqual(request["status"],"Required")
            edge=int(datetime(2026,7,14,tzinfo=UTC).timestamp())
            with registered_writer(database) as connection:
                run_id=connection.execute("SELECT created_by_ingest_run_id FROM bars WHERE asset='AUDUSD' LIMIT 1").fetchone()[0]
                connection.execute("INSERT INTO bars(asset,timeframe,open_time_utc,open,high,low,close,created_by_ingest_run_id,updated_by_ingest_run_id) VALUES('AUDUSD','D1',?,'1','2','0','1',?,?)",(edge,run_id,run_id))
                connection.execute("UPDATE lane_state SET high_watermark_open_time_utc=?,state_version=state_version+1 WHERE asset='AUDUSD' AND timeframe='D1'",(edge,))
            self.assertTrue(resolve_satisfied_manual_requests(database,requests,now))
            self.assertEqual(request["status"],"Resolved")

    def test_failure_classification_is_structured(self) -> None:
        self.assertEqual(classify_failure(AcquisitionError("RATE_LIMITED","429"))[0],"TWELVEDATA_RATE_LIMIT_429")
        self.assertEqual(classify_failure(AcquisitionError("MISSING_CREDENTIAL","absent"))[0],"CREDENTIAL_MISSING")


if __name__ == "__main__": unittest.main()
