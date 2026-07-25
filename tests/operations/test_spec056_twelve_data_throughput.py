from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import (
    classify_failure,
    load_provider_profiles,
    update_provider_health,
)
from fragarach_ii.execution_trace import trace_for_lane
from fragarach_ii.providers.twelve_data import AcquisitionError, acquire_twelve_data
from fragarach_ii.scheduler_service import (
    SchedulerJournal,
    SchedulerService,
    _dispatch_liveness,
    _fair_bounded_selection,
    _stable_past_due_no_work,
    run_due_acquisitions,
)
from fragarach_ii.twelve_data_credit import TwelveDataCreditAuthority
from fragarach_ii.storage import initialize_database, registered_writer
from tests.operations.test_spec055_execution_trace import AT, _advance_d1
from tests.providers.test_twelve_data import FakeTransport, _fixture, _response
from tests.validation.test_d1_session_validation import _create_lane


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


def authority(tmp_path: Path, clock: MutableClock, credential: str = "fixture") -> TwelveDataCreditAuthority:
    return TwelveDataCreditAuthority(
        credential=credential,
        plan_limit=55,
        operational_limit=50,
        window_seconds=60,
        dispatch_interval_seconds=1.2,
        path=tmp_path / "credit.json",
        clock=clock,
        sleeper=clock.sleep,
    )


def test_shared_atomic_credit_authority_paces_to_50_and_resets(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 7, 15, 0, 0, tzinfo=UTC))
    first = authority(tmp_path, clock)
    second = authority(tmp_path, clock)
    for index in range(50):
        owner = first if index % 2 == 0 else second
        endpoint = "time_series" if index % 2 == 0 else "symbol_search"
        reservation = owner.reserve(1, endpoint=endpoint)
        assert reservation["eligible"]
        owner.dispatch(str(reservation["reservation_id"]))
    state = first.inspect(1)
    assert state["plan_limit"] == 55
    assert state["operational_limit"] == 50
    assert state["credits_consumed"] == 50
    assert state["credits_remaining"] == 0
    assert state["hard_credits_remaining"] == 5
    assert state["requests_last_minute"] == 50
    assert state["eligible"] is False
    assert 58 <= (clock.value - datetime(2026, 7, 15, tzinfo=UTC)).total_seconds() < 60
    clock.value = datetime(2026, 7, 15, 0, 1, tzinfo=UTC)
    reset = second.inspect(1)
    assert reset["credits_consumed"] == 0
    assert reset["credits_remaining"] == 50
    assert reset["eligible"] is True


def test_atomic_reservation_never_exceeds_operational_or_hard_limit(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 7, 15, 0, 0, tzinfo=UTC))
    results: list[bool] = []
    guard = threading.Lock()

    def reserve() -> None:
        result = authority(tmp_path, clock).reserve(1, endpoint="time_series")
        with guard:
            results.append(bool(result["eligible"]))

    workers = [threading.Thread(target=reserve) for _ in range(100)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    state = authority(tmp_path, clock).inspect()
    assert sum(results) == 50
    assert state["credits_reserved"] == 50
    assert state["credits_reserved"] + state["credits_consumed"] <= 50 < 55


def test_active_reservation_survives_credit_window_rollover(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 7, 15, 0, 0, tzinfo=UTC))
    credit = authority(tmp_path, clock)
    reservation = credit.reserve(2, endpoint="time_series")
    assert reservation["eligible"]
    reservation_id = str(reservation["reservation_id"])

    credit.dispatch(reservation_id)
    clock.value = datetime(2026, 7, 15, 0, 1, 1, tzinfo=UTC)
    second = credit.dispatch(reservation_id)

    assert second["dispatched"] == 1
    state = credit.inspect()
    assert state["credits_reserved"] == 0
    assert state["credits_consumed"] == 1
    assert state["active_reservations"] == 0


def test_actual_429_uses_retry_after_without_marking_provider_unhealthy(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 7, 15, 0, 0, tzinfo=UTC))
    credit = authority(tmp_path, clock)
    state = credit.record_429(
        response_body=b'{"status":"error","code":429}',
        retry_after="17",
        endpoint="time_series",
    )
    assert state["last_429_at"] == clock.value.isoformat()
    assert state["rate_limit_until"] == (clock.value + timedelta(seconds=17)).isoformat()
    assert credit.reserve(1)["reason"] == "PROVIDER_429"

    profile = next(item for item in load_provider_profiles() if item.provider == "TWELVE_DATA")
    health: dict[str, object] = {}
    update_provider_health(health, profile, "TWELVEDATA_RATE_LIMIT_429", clock.value)
    assert health["health"] == "Healthy"
    assert health["cooldown_until"] is None
    assert health["wait_reason"] == "CREDIT_WINDOW_EXHAUSTED"


def test_local_and_sqlite_failures_never_create_provider_cooldown() -> None:
    profile = next(item for item in load_provider_profiles() if item.provider == "TWELVE_DATA")
    for failure in ("LOCAL_PARSE_ERROR", "LOCAL_ADMISSION_ERROR", "SQLITE_LOCKED", "PUBLICATION_ERROR"):
        state: dict[str, object] = {"health": "Healthy", "consecutive_failures": 0}
        update_provider_health(state, profile, failure, AT)
        assert state["health"] == "Healthy"
        assert state["consecutive_failures"] == 0
        assert not state.get("cooldown_until")
    sqlite_error = sqlite3.OperationalError("database is locked")
    assert classify_failure(sqlite_error)[0] == "SQLITE_LOCKED"
    assert classify_failure(ValueError("local invariant"))[0] == "LOCAL_PROGRAMMING_ERROR"


def test_retry_retains_queue_item_trace_and_boundary_identity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRAGARACH_TWELVE_DATA_CREDIT_ROOT", str(tmp_path / "credits"))
    database, journal_path = tmp_path / "authority.sqlite3", tmp_path / "scheduler.json"
    _create_lane(database, "AUDUSD", ["2026-07-13"])

    def upstream_failure(_database, **_kwargs):
        raise AcquisitionError("TWELVEDATA_UPSTREAM_5XX", "Twelve Data HTTP 503", http_status=503)

    first = run_due_acquisitions(
        database, at=AT, credential="fixture", journal_path=journal_path,
        acquirer=upstream_failure,
    )
    item = next(row for row in first["acquisition_queue"] if row["lane"] == "AUDUSD:D1")
    original = (item["id"], item["trace_id"], item["requested_through"])
    assert item["attempt_number"] == 1
    assert item["next_attempt"] == (AT + timedelta(seconds=2)).isoformat()
    assert not first["manual_requests"]
    assert first["providers"][0]["cooldown_until"] is None

    second = run_due_acquisitions(
        database, at=AT + timedelta(days=1), credential="fixture",
        journal_path=journal_path, acquirer=upstream_failure, catch_up=True,
    )
    retried = next(row for row in second["acquisition_queue"] if row["lane"] == "AUDUSD:D1")
    assert (retried["id"], retried["trace_id"]) == original[:2]
    assert retried["attempt_number"] == 2
    assert retried["requested_through"] > original[2]

    def advancing(_database, **_kwargs):
        if _kwargs.get("asset") != "AUDUSD":
            return {"received": 1, "staged": 1, "inserted": 0, "corrected": 0, "unchanged": 1}
        _advance_d1(database)
        edge = int(datetime(2026, 7, 15, tzinfo=UTC).timestamp())
        from fragarach_ii.storage import registered_writer
        with registered_writer(database) as connection:
            run_id = connection.execute(
                "SELECT created_by_ingest_run_id FROM bars WHERE asset='AUDUSD' LIMIT 1"
            ).fetchone()[0]
            connection.execute(
                """INSERT OR IGNORE INTO bars
                   (asset,timeframe,open_time_utc,open,high,low,close,
                    created_by_ingest_run_id,updated_by_ingest_run_id)
                   VALUES ('AUDUSD','D1',?,'1','2','0','1',?,?)""",
                (edge, run_id, run_id),
            )
            connection.execute(
                """UPDATE lane_state SET high_watermark_open_time_utc=?,
                   state_version=state_version+1,updated_at_utc=?
                   WHERE asset='AUDUSD' AND timeframe='D1'""",
                (edge, (AT + timedelta(days=1)).isoformat()),
            )
        return {"received": 1, "staged": 1, "inserted": 1, "corrected": 0, "unchanged": 0}

    completed = run_due_acquisitions(
        database, at=AT + timedelta(days=1, seconds=5), credential="fixture",
        journal_path=journal_path, acquirer=advancing, catch_up=True,
    )
    assert not any(row["lane"] == "AUDUSD:D1" for row in completed["acquisition_queue"])
    trace = trace_for_lane(SchedulerJournal(database, journal_path).data, "AUDUSD", "D1")
    assert trace["trace_id"] == original[1]


def test_committed_evidence_is_not_requested_again_after_local_publication_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRAGARACH_TWELVE_DATA_CREDIT_ROOT", str(tmp_path / "credits"))
    database, journal_path = tmp_path / "authority.sqlite3", tmp_path / "scheduler.json"
    _create_lane(database, "AUDUSD", ["2026-07-13"])
    calls = 0

    def committed_then_failed(_database, **_kwargs):
        nonlocal calls
        if _kwargs.get("asset") != "AUDUSD":
            return {"received": 1, "staged": 1, "inserted": 0, "corrected": 0, "unchanged": 1}
        calls += 1
        _advance_d1(database)
        raise AcquisitionError(
            "POST_INGEST_VALIDATION_FAILED", "validation failed",
            evidence_committed=True,
        )

    first = run_due_acquisitions(
        database, at=AT, credential="fixture", journal_path=journal_path,
        acquirer=committed_then_failed,
    )
    assert calls == 1
    assert first["acquisition_queue"][0]["evidence_committed"] is True
    second = run_due_acquisitions(
        database, at=AT + timedelta(seconds=3), credential="fixture",
        journal_path=journal_path, acquirer=committed_then_failed, catch_up=True,
    )
    assert calls == 1
    assert not any(item["lane"] == "AUDUSD:D1" for item in second["acquisition_queue"])


def test_sqlite_write_path_reports_timing_rows_result_and_writer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRAGARACH_TWELVE_DATA_CREDIT_ROOT", str(tmp_path / "credits"))
    database = tmp_path / "authority.sqlite3"
    _create_lane(database, "AUDUSD", ["2026-07-09"])
    result = acquire_twelve_data(
        database, asset="AUDUSD", timeframe="D1",
        from_date="2026-07-09", through_date="2026-07-10",
        credential="sqlite-fixture",
        transport=FakeTransport(_response(_fixture("audusd_d1_2026-07-09_2026-07-10.json"))),
        sleeper=lambda _delay: None,
    )
    metrics = result.sqlite_write
    assert metrics["transaction_started_at"]
    assert metrics["lock_wait_ms"] >= 0
    assert metrics["write_duration_ms"] >= 0
    assert metrics["commit_duration_ms"] >= 0
    assert metrics["rows_inserted"] == result.inserted + result.corrected
    assert metrics["rows_unchanged"] == result.unchanged
    assert metrics["sqlite_result_code"] == "SQLITE_OK"
    assert str(metrics["writer_identity"]).startswith("pid=")


def test_credit_state_and_trace_are_secret_redacted(tmp_path: Path) -> None:
    secret = "never-persist-this-secret"
    clock = MutableClock(datetime(2026, 7, 15, tzinfo=UTC))
    credit = authority(tmp_path, clock, credential=secret)
    reservation = credit.reserve(1, endpoint="credential_validation")
    credit.dispatch(str(reservation["reservation_id"]))
    persisted = credit.path.read_text(encoding="utf-8")
    assert secret not in persisted
    assert "apikey" not in persisted.lower()
    parsed = json.loads(persisted)
    assert parsed["credits_consumed"] == 1


def test_persistent_executor_dispatches_before_any_full_monitor_snapshot(monkeypatch) -> None:
    import fragarach_ii.scheduler_service as scheduler_module

    service = SchedulerService("authority.sqlite3", credential="fixture")
    due_calls: list[dict[str, object]] = []

    def snapshot(*_args, **_kwargs):
        raise AssertionError("a startup estate snapshot must not precede dispatch")

    def run_due(*_args, **kwargs):
        due_calls.append(kwargs)
        service.stop()
        return {"next_run": None, "execution": {"cycle_id": "completed"}}

    monkeypatch.setattr(scheduler_module, "scheduler_snapshot", snapshot)
    monkeypatch.setattr(scheduler_module, "run_due_acquisitions", run_due)
    emitted: list[dict[str, object]] = []
    service.run_forever(emitted.append)

    assert due_calls[0]["emit"] is None
    assert [item["execution"]["cycle_id"] for item in emitted] == ["completed"]


def test_stable_past_due_no_work_uses_revision_wait_instead_of_reconciliation(monkeypatch) -> None:
    """A stale manual queue timestamp must not repeatedly rebuild the estate."""
    import fragarach_ii.scheduler_service as scheduler_module

    observed = datetime(2026, 7, 18, 2, tzinfo=UTC)
    service = SchedulerService("authority.sqlite3", credential="fixture", clock=lambda: observed)
    due_calls = 0
    waits: list[float] = []

    class StopOnIdleWait:
        def __init__(self) -> None:
            self.flagged = False

        def wait(self, timeout: float | None = None) -> bool:
            waits.append(float(timeout or 0))
            self.flagged = True
            service.stop_event.set()
            return True

        def is_set(self) -> bool:
            return self.flagged

        def clear(self) -> None:
            self.flagged = False

        def set(self) -> None:
            self.flagged = True

    # `stop()` only needs wake_event.set(); keep the event otherwise deterministic.
    idle_event = StopOnIdleWait()
    service.wake_event = idle_event  # type: ignore[assignment]

    def snapshot(*_args, **_kwargs):
        return {"next_run": None, "execution": {"cycle_id": "initial"}}

    def run_due(*_args, **_kwargs):
        nonlocal due_calls
        due_calls += 1
        return {
            "next_run": "2026-07-18T01:23:06Z",
            "active_activity": None,
            "execution": {
                "cycle_id": "idle", "eligible_count": 0, "selected_count": 0,
                "dispatch_attempted_count": 0, "provider_calls_started": 0,
                "active_workers": 0, "throughput_limited_by": "NO_ELIGIBLE_WORK",
            },
        }

    monkeypatch.setattr(scheduler_module, "scheduler_snapshot", snapshot)
    monkeypatch.setattr(scheduler_module, "run_due_acquisitions", run_due)
    service.run_forever(lambda _snapshot: None)

    assert due_calls == 1
    assert waits


def test_no_work_revision_wait_requires_a_past_due_or_missing_next_run() -> None:
    execution = {
        "eligible_count": 0, "selected_count": 0, "dispatch_attempted_count": 0,
        "provider_calls_started": 0, "active_workers": 0,
        "throughput_limited_by": "NO_ELIGIBLE_WORK",
    }
    now = datetime(2026, 7, 18, 2, tzinfo=UTC)
    assert _stable_past_due_no_work(
        {"next_run": "2026-07-18T01:23:06Z", "execution": execution}, now
    )
    assert not _stable_past_due_no_work(
        {"next_run": "2026-07-18T02:05:00Z", "execution": execution}, now
    )


def test_registered_writer_serializes_workers_and_measures_local_wait(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    measurement: dict[str, object] = {}

    def first_writer() -> None:
        with registered_writer(database):
            first_entered.set()
            assert release_first.wait(2)

    def second_writer() -> None:
        assert first_entered.wait(2)
        with registered_writer(database, measurement=measurement):
            second_entered.set()

    first = threading.Thread(target=first_writer)
    second = threading.Thread(target=second_writer)
    first.start()
    assert first_entered.wait(2)
    second.start()
    time.sleep(0.05)
    assert not second_entered.is_set()
    release_first.set()
    first.join(2)
    second.join(2)
    assert not first.is_alive() and not second.is_alive()
    assert second_entered.is_set()
    assert float(measurement["lock_wait_ms"]) >= 40


def test_retry_lane_clears_before_lower_cadence_historical_work() -> None:
    journal = type("Journal", (), {"data": {"fairness_cursor": 0}})()
    due = [
        {
            "symbol": "AUDUSD", "timeframe": "D1", "asset_class": "FX",
            "dispatch_priority": "RETRY_QUEUE", "queue_age_seconds": 30,
        },
        {
            "symbol": "EURUSD", "timeframe": "M5", "asset_class": "FX",
            "dispatch_priority": "HISTORICAL_CATCH_UP", "queue_age_seconds": 30,
        },
    ]
    selected = _fair_bounded_selection(due, 50, journal)
    assert [item["symbol"] for item in selected] == ["AUDUSD"]


def test_scheduler_releases_cadence_in_strict_timeframe_order() -> None:
    journal = type("Journal", (), {"data": {"fairness_cursor": 3}})()
    due = [
        {
            "symbol": f"LANE-{timeframe}", "timeframe": timeframe, "asset_class": "FX",
            "dispatch_priority": "BEHIND_COMMISSIONED", "queue_age_seconds": age,
        }
        for timeframe, age in (("M5", 86_400), ("M30", 3_600), ("H1", 60), ("D1", 0))
    ]

    released = []
    remaining = list(due)
    while remaining:
        selected = _fair_bounded_selection(remaining, 4, journal)
        released.extend(item["timeframe"] for item in selected)
        remaining = [item for item in remaining if item not in selected]

    assert released == ["D1", "H1", "M30", "M5"]


def test_ready_queue_with_capacity_is_catch_up_woken_then_explicitly_reported() -> None:
    now = datetime(2026, 7, 20, 0, 0, tzinfo=UTC)
    facts = _dispatch_liveness(
        {
            "ready_now": 68, "running": 0, "waiting_for_budget": 0,
            "cooling_down": 0, "blocked": 0, "oldest_ready_age_seconds": 87,
            "last_dispatch": (now - timedelta(seconds=6)).isoformat(),
        },
        {"available_capacity": 105},
        {
            "active_workers": 0,
            "last_dispatch_attempt_at": (now - timedelta(seconds=6)).isoformat(),
            "no_worker_started_reason": "Ready work was not selected by the dispatcher",
            "last_scheduler_lock_holder": "scheduler-cycle:fixture",
            "cycle_overrun_reason": "Cycle exceeded the five-second liveness interval; catch-up dispatch scheduled",
        },
        active_activity=None, now=now,
    )
    assert facts["state"] == "BUG: ready work idle"
    assert facts["oldest_ready_age_seconds"] == 87
    assert facts["last_scheduler_lock_holder"] == "scheduler-cycle:fixture"


def test_ready_queue_with_capacity_starts_in_the_five_second_liveness_window() -> None:
    now = datetime(2026, 7, 20, 0, 0, tzinfo=UTC)
    facts = _dispatch_liveness(
        {"ready_now": 1, "running": 0, "cooling_down": 0, "blocked": 0, "last_dispatch": None},
        {"available_capacity": 1}, {"active_workers": 0},
        active_activity=None, now=now,
    )
    assert facts["state"] == "Dispatching"
    assert facts["reason"] == "Catch-up dispatch is due within five seconds"
