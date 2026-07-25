from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.lane_commissioning import ensure_commissioned_lane
from fragarach_ii.lane_update_register import LaneUpdateRegister
from fragarach_ii.scheduler_service import (
    SchedulerJournal,
    _fair_bounded_selection,
    _pending_operator_fetches,
    _time_triggered_runtime_snapshot,
    run_operator_fetch,
    run_due_acquisitions,
)
from fragarach_ii.execution_trace import compact_operational_history
from fragarach_ii.scheduler_daemon import scheduler_operational_health
from fragarach_ii.storage import open_read_only
from tests.operations.test_spec041_scheduler import _add_intraday_bar
from tests.validation.test_d1_session_validation import _create_lane


NOW = datetime(2026, 7, 14, 0, 10, tzinfo=UTC)


def _m5_lane(tmp_path: Path) -> Path:
    database = tmp_path / "authority.sqlite3"
    _create_lane(database, "AUDUSD", ["2026-07-13"])
    ensure_commissioned_lane(database, "AUDUSD", "M5")
    _add_intraday_bar(
        database, "AUDUSD", "M5",
        "2026-07-14T00:00:00+00:00", "2026-07-14T00:05:00+00:00",
    )
    return database


def test_due_query_claims_only_the_exact_closed_boundary(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")

    due = register.claim_due(at=NOW, limit=10)

    assert [(item["asset"], item["timeframe"]) for item in due] == [("AUDUSD", "M5")]
    assert register.claim_due(at=NOW, limit=10) == []


def test_daily_priority_zero_is_preserved_and_due_count_is_indexed(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")

    rows = {(row["asset"], row["timeframe"]): row for row in register.rows()}

    assert rows[("AUDUSD", "D1")]["priority"] == 0
    assert register.due_count(at=NOW) >= 1

    with register._connection() as connection:
        connection.execute("UPDATE lane_update_register SET priority=100 WHERE asset='AUDUSD' AND timeframe='D1'")
        connection.execute("DELETE FROM register_meta WHERE key='priority_revision'")
    repaired = LaneUpdateRegister(database)
    repaired_rows = {(row["asset"], row["timeframe"]): row for row in repaired.rows()}
    assert repaired_rows[("AUDUSD", "D1")]["priority"] == 0


def test_compact_runtime_marks_remaining_due_work_for_catch_up(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")

    snapshot = _time_triggered_runtime_snapshot(
        SchedulerJournal(database, tmp_path / "scheduler.json"), register, {}, at=NOW,
    )

    assert snapshot["dispatch_state"]["next_wake_reason"] == "READY_CAPACITY_CATCH_UP"
    assert snapshot["register"]["due_now_count"] >= 1
    health = scheduler_operational_health(
        snapshot, process_alive=True, heartbeat_time=NOW.isoformat(),
        monitor_state="CONNECTED", now=NOW,
    )
    assert health["overall_operational_health"] == "HEALTHY"


def test_compact_runtime_emits_authority_change_token(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")

    snapshot = _time_triggered_runtime_snapshot(
        SchedulerJournal(database, tmp_path / "scheduler.json"), register, {}, at=NOW,
    )

    token = snapshot["authority_change_token"]
    assert isinstance(token, str)
    assert len(token) == 64


def test_no_change_completes_a_boundary_once_and_sleeps_to_the_next_one(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")
    due = register.claim_due(at=NOW, limit=1)[0]

    completed = register.record_checked(
        asset="AUDUSD", timeframe="M5",
        checked_boundary=str(due["next_expected_boundary_utc"]), at=NOW,
    )

    assert completed["state"] == "READY"
    assert completed["next_check_at_utc"] == "2026-07-14T00:15:00+00:00"
    assert register.claim_due(at=NOW, limit=10) == []


def test_boundary_completion_reuses_the_audited_route_revision(tmp_path: Path, monkeypatch) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")
    before = next(
        row for row in register.rows()
        if row["asset"] == "AUDUSD" and row["timeframe"] == "M5"
    )

    def unexpected_route_ledger_scan(*_args, **_kwargs):
        raise AssertionError("normal completion must not scan the authority-event ledger")

    monkeypatch.setattr(
        "fragarach_ii.lane_update_register.authority_revision_for_lane",
        unexpected_route_ledger_scan,
    )
    register.record_checked(
        asset="AUDUSD", timeframe="M5",
        checked_boundary=str(before["next_expected_boundary_utc"]), at=NOW,
    )

    after = next(
        row for row in register.rows()
        if row["asset"] == "AUDUSD" and row["timeframe"] == "M5"
    )
    assert after["provider_route_revision"] == before["provider_route_revision"]


def test_pause_and_retry_affect_only_the_target_register_row(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")

    register.pause(asset="AUDUSD", timeframe="M5", at=NOW)
    assert register.claim_due(at=NOW, limit=10) == []
    register.resume(asset="AUDUSD", timeframe="M5", at=NOW)
    assert register.summary()["paused_count"] == 0

    register.audit_estate(at=NOW, reason="TEST_RESET")
    register.claim_due(at=NOW, limit=1)
    retry = register.retry(asset="AUDUSD", timeframe="M5", reason="NETWORK", at=NOW)
    assert retry["state"] == "RETRY"
    assert register.summary()["retrying_count"] == 1


def test_blocked_rows_are_available_as_a_bounded_operator_projection(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")
    register.block(asset="AUDUSD", timeframe="M5", reason="AUTHENTICATION_FAILED", at=NOW)

    rows = register.blocked_rows(limit=10)

    assert [(row["asset"], row["timeframe"]) for row in rows] == [("AUDUSD", "M5")]
    assert rows[0]["last_outcome"] == "AUTHENTICATION_FAILED"


def test_normal_wake_uses_register_not_estate_reconciliation(tmp_path: Path, monkeypatch) -> None:
    database = _m5_lane(tmp_path)
    journal = tmp_path / "scheduler.json"
    LaneUpdateRegister(database).audit_estate(at=NOW, reason="TEST")

    def no_estate_scan(*_args, **_kwargs):
        raise AssertionError("normal due work must not reconcile the estate")

    monkeypatch.setattr("fragarach_ii.scheduler_service.reconcile_operational_state", no_estate_scan)
    calls: list[str] = []

    def acquire(_database, **kwargs):
        calls.append(str(kwargs["timeframe"]))
        return {"inserted": 0, "corrected": 0}

    snapshot = run_due_acquisitions(
        database, at=NOW, credential="fixture", journal_path=journal,
        acquirer=acquire, time_triggered=True,
    )

    assert calls == ["M5"]
    assert snapshot["scheduler_mode"] == "TIME_TRIGGERED_REGISTER"
    assert snapshot["next_run"] == "2026-07-14T00:15:00+00:00"
    dashboard = snapshot["schedule_dashboard"]
    assert dashboard == LaneUpdateRegister(database).dashboard_rows(limit=24)
    assert 1 <= len(dashboard) <= 24
    assert {"asset", "timeframe", "state", "next_check_at_utc", "last_outcome"} <= dashboard[0].keys()


def test_time_triggered_wake_dispatches_a_pending_operator_fetch(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    journal = tmp_path / "scheduler.json"
    LaneUpdateRegister(database).audit_estate(at=NOW, reason="TEST")

    submitted = run_operator_fetch(
        database, symbol="AUDUSD", timeframe="M5", credential="fixture",
        requested_mode="force", requested_start="2026-07-13", requested_end="2026-07-14",
        reviewed_historical_range=True, journal_path=journal, at=NOW,
        defer_dispatch=True,
    )
    assert submitted["outcome"] == "QUEUED"
    calls: list[str] = []

    def acquire(_database, **kwargs):
        calls.append(str(kwargs["timeframe"]))
        return {"inserted": 0, "corrected": 0}

    run_due_acquisitions(
        database, at=NOW, credential="fixture", journal_path=journal,
        acquirer=acquire, time_triggered=True,
    )

    assert calls == ["M5"]
    lane = SchedulerJournal(database, journal).lane("AUDUSD", "M5")
    assert lane["last_operator_fetch_result"]["operation_id"] == submitted["operation_id"]
    # A request that did not yet advance canonical evidence remains durable
    # for the next scheduler wake instead of becoming an orphaned queue row.
    assert lane["last_operator_fetch_result"]["outcome"] == "WAITING"
    assert lane["operator_fetch_pending"]["id"] == submitted["operation_id"]


def test_operator_fetch_that_replaces_claimed_normal_work_settles_register_claim(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    journal = tmp_path / "scheduler.json"
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")

    submitted = run_operator_fetch(
        database, symbol="AUDUSD", timeframe="M5", credential="fixture",
        requested_mode="force", requested_start="2026-07-13", requested_end="2026-07-14",
        reviewed_historical_range=True, journal_path=journal, at=NOW, defer_dispatch=True,
    )
    assert submitted["outcome"] == "QUEUED"

    run_due_acquisitions(
        database, at=NOW, credential="fixture", journal_path=journal,
        acquirer=lambda _database, **_kwargs: {"inserted": 0, "corrected": 0},
        time_triggered=True,
    )

    row = next(item for item in register.rows() if item["asset"] == "AUDUSD" and item["timeframe"] == "M5")
    assert row["state"] == "RETRY"
    assert row["last_outcome"] == "OPERATOR_FETCH_SUPERSEDED_NORMAL"


def test_empty_intraday_lane_upgrades_an_operator_update_to_initial_history(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    _create_lane(database, "AUDUSD", ["2026-07-13"])
    ensure_commissioned_lane(database, "AUDUSD", "M5")
    journal = tmp_path / "scheduler.json"

    submitted = run_operator_fetch(
        database, symbol="AUDUSD", timeframe="M5", credential="fixture",
        requested_mode="update", journal_path=journal, at=NOW, defer_dispatch=True,
    )

    assert submitted["outcome"] == "QUEUED"
    pending = SchedulerJournal(database, journal).lane("AUDUSD", "M5")["operator_fetch_pending"]
    assert pending["requested_mode"] == "initial"
    assert pending["requested_start"] == "2025-07-13"
    assert pending["requested_end"] == "2026-07-13"


def test_initial_intraday_history_backfills_behind_a_partial_current_edge(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    journal = tmp_path / "scheduler.json"

    submitted = run_operator_fetch(
        database, symbol="AUDUSD", timeframe="M5", credential="fixture",
        requested_mode="initial", journal_path=journal, at=NOW, defer_dispatch=True,
    )

    assert submitted["outcome"] == "QUEUED"
    assert submitted["requested_range"] == {
        "start": "2025-07-13", "end": "2026-07-13",
    }
    pending = SchedulerJournal(database, journal).lane("AUDUSD", "M5")["operator_fetch_pending"]
    assert pending["backfill_from_start"] is True
    work, _ = _pending_operator_fetches(database, NOW, SchedulerJournal(database, journal))
    assert work[0]["requested_bounds"] == ["2025-07-13", "2026-07-13"]


def test_current_boundary_preempts_historical_operator_fetch(tmp_path: Path) -> None:
    journal = SchedulerJournal(tmp_path / "authority.sqlite3", tmp_path / "scheduler.json")
    crypto_current = {
        "symbol": "BTCUSD", "timeframe": "M5", "asset_class": "CRYPTO",
        "work_class": "NORMAL", "dispatch_priority": "CURRENT_BOUNDARY",
        "expected_edge": "2026-07-14T00:05:00+00:00", "missed_boundaries": 1,
    }
    closed_market_history = {
        "symbol": "AUDUSD", "timeframe": "M5", "asset_class": "FX",
        "work_class": "OPERATOR_FETCH", "dispatch_priority": "OPERATOR_FETCH",
        "expected_edge": "2026-07-11T21:55:00+00:00", "missed_boundaries": 1,
    }

    selected = _fair_bounded_selection([closed_market_history, crypto_current], 1, journal)

    assert selected == [crypto_current]


def test_scheduler_journal_uses_sqlite_state_and_small_compatibility_pointer(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    path = tmp_path / "scheduler.json"
    journal = SchedulerJournal(database, path)
    journal.lane("BTCUSD", "M5").update({
        "queue_state": "Ready",
        "attempt_history": [{"timestamp": NOW.isoformat(), "outcome": "COMPLETE"}],
    })
    journal.append_event({"timestamp": NOW.isoformat(), "event": "QUEUE_COMPLETED"})
    journal.save()

    pointer = json.loads(path.read_text(encoding="utf-8"))
    assert pointer["contract"] == "fragarach_ii.scheduler_journal_pointer.v1"
    assert pointer["storage"] == "SQLITE"
    assert path.stat().st_size < 512
    assert SchedulerJournal(database, path).lane("BTCUSD", "M5")["queue_state"] == "Ready"
    with open_read_only(database) as connection:
        assert connection.execute("SELECT count(*) FROM scheduler_runtime_state").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM scheduler_audit_events").fetchone()[0] >= 2


def test_legacy_scheduler_history_moves_to_sqlite_audit_before_compaction(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    path = tmp_path / "scheduler.json"
    path.write_text(json.dumps({
        "contract": "fragarach_ii.scheduler_journal.v4",
        "lanes": {}, "providers": {}, "manual_requests": [], "acquisition_queue": [],
        "events": [],
        "routing_decisions": [], "request_lifecycle": [],
        "archived_operational_work": [],
        "execution_trace_events": [{"timestamp": NOW.isoformat(), "event": "QUEUE_COMPLETED", "id": index}
                                   for index in range(40)],
        "operation_timing_records": [], "scheduler_cycles": [],
    }), encoding="utf-8")

    journal = SchedulerJournal(database, path)
    assert journal.migration_pending
    journal.save()

    assert len(SchedulerJournal(database, path).data["execution_trace_events"]) == 20
    with open_read_only(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM scheduler_audit_events WHERE category = 'execution_trace_events'"
        ).fetchone()[0] == 40


def test_hot_journal_compacts_completed_boundary_history() -> None:
    journal = {
        "routing_decisions": list(range(30)),
        "request_lifecycle": list(range(120)),
        "archived_operational_work": [{
            "lane": "BTCUSD:M5", "reason": "COMPLETE", "payload": {"large": "x" * 1_000},
        }],
        "manual_requests": [{
            "id": "request-1", "symbol": "BTCUSD", "timeframe": "M5", "status": "Archived",
            "reason": "COMPLETE", "providers_considered": [{"provider": "BINANCE", "capability": {"large": "x" * 1_000}}],
        }],
        "lanes": {
            "BTCUSD:M5": {
                "attempt_history": list(range(25)),
                "providers_considered": [{"provider": "BINANCE", "eligible": True, "capability": {"large": "x" * 1_000}}],
                "provider_attempts_by_boundary": {
                    f"2026-07-14T00:{minute:02d}:00+00:00": ["BINANCE"]
                    for minute in range(40)
                },
            }
        },
    }

    assert compact_operational_history(journal) is True
    lane = journal["lanes"]["BTCUSD:M5"]
    assert len(journal["routing_decisions"]) == 1
    assert len(journal["request_lifecycle"]) == 20
    assert len(lane["attempt_history"]) == 1
    assert len(lane["provider_attempts_by_boundary"]) == 1
    assert journal["archived_operational_work"][0].get("payload") is None
    assert journal["manual_requests"][0] == {
        "id": "request-1", "symbol": "BTCUSD", "timeframe": "M5", "status": "Archived", "reason": "COMPLETE",
    }
    assert lane["providers_considered"] == [{"provider": "BINANCE", "eligible": True}]
