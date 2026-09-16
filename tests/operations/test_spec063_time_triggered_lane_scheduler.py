from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import (
    ProviderProfile,
    RateBudgetController,
    load_provider_profiles,
)
from fragarach_ii.lane_commissioning import ensure_commissioned_lane
from fragarach_ii.lane_update_register import LaneUpdateRegister
from fragarach_ii.scheduler_service import (
    SchedulerJournal,
    _authority_change_token,
    _credit_window_recovery_required,
    _credit_window_register_recovery_required,
    _fair_bounded_selection,
    _pending_operator_fetches,
    _release_terminal_operator_fetches,
    _retry_delay_seconds,
    _time_triggered_runtime_snapshot,
    run_operator_fetch,
    run_due_acquisitions,
)
from fragarach_ii.providers.twelve_data import AcquisitionError
from fragarach_ii.execution_trace import (
    compact_hot_history_only,
    compact_operational_history,
)
from fragarach_ii.scheduler_daemon import scheduler_operational_health
from fragarach_ii.storage import open_read_only, registered_writer
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


def test_primary_handoff_defers_generic_claim_until_fallback_release(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")
    expires = NOW + timedelta(minutes=30)

    register.defer_provider_handoff(
        asset="AUDUSD",
        timeframe="M5",
        until=expires,
        reason="MT5_BRIDGE_PRIMARY_PENDING:request-1",
        at=NOW,
    )

    assert not any(
        item["asset"] == "AUDUSD" and item["timeframe"] == "M5"
        for item in register.claim_due(at=NOW + timedelta(minutes=5), limit=10)
    )
    register.release_provider_handoff(
        asset="AUDUSD",
        timeframe="M5",
        reason="MT5_BRIDGE_REQUEST_EXPIRED",
        at=NOW + timedelta(minutes=6),
    )
    assert any(
        item["asset"] == "AUDUSD" and item["timeframe"] == "M5"
        for item in register.claim_due(at=NOW + timedelta(minutes=6), limit=10)
    )


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

    # Scheduler claims and retry bookkeeping are operational state, not a
    # canonical Estate change and must not start a full desktop projection.
    register.claim_due(at=NOW, limit=1)
    assert _authority_change_token(database) == token

    register.block(
        asset="AUDUSD", timeframe="M5",
        reason="LOCAL_PROGRAMMING_ERROR; fixture", at=NOW, approved=True,
    )
    blocked_token = _authority_change_token(database)
    assert blocked_token != token

    # A committed ingest advances governed authority and must refresh Estate.
    _add_intraday_bar(
        database, "AUDUSD", "M5",
        "2026-07-14T00:05:00+00:00", "2026-07-14T00:10:00+00:00",
    )
    with registered_writer(database) as connection:
        connection.execute(
            """INSERT INTO lane_state
               (asset,timeframe,high_watermark_open_time_utc,state_version,
                last_ingest_run_id,updated_at_utc)
               VALUES ('AUDUSD','M5',?,1,NULL,?)""",
            (int(datetime(2026, 7, 14, 0, 5, tzinfo=UTC).timestamp()),
             datetime(2026, 7, 14, 0, 6, tzinfo=UTC).isoformat()),
        )
    intraday_token = _authority_change_token(database)
    assert intraday_token != token

    with registered_writer(database) as connection:
        connection.execute(
            """UPDATE lane_state
                  SET state_version=state_version+1,updated_at_utc=?
                WHERE asset='AUDUSD' AND timeframe='D1'""",
            (datetime(2026, 7, 14, 0, 11, tzinfo=UTC).isoformat(),),
        )
    assert _authority_change_token(database) != intraday_token


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
    register.block(asset="AUDUSD", timeframe="M5", reason="AUTHENTICATION_FAILED", at=NOW, approved=True)

    rows = register.blocked_rows(limit=10)

    assert [(row["asset"], row["timeframe"]) for row in rows] == [("AUDUSD", "M5")]
    assert rows[0]["last_outcome"] == "AUTHENTICATION_FAILED; OPERATOR_APPROVED_BLOCK"
    assert "credential is missing, invalid, or rejected" in rows[0]["blocker_reason"]
    assert "Configure and validate" in rows[0]["repair_action"]
    assert rows[0]["flow_impact"] == "Only this lane is held; scheduled acquisition for all other lanes continues."


def test_unapproved_stop_becomes_a_standard_cadence_provider_cycle(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")

    result = register.block(
        asset="AUDUSD", timeframe="M5", reason="NO_ELIGIBLE_PROVIDER", at=NOW,
    )

    assert result["state"] == "RETRY"
    assert result["next_check_at_utc"] == (NOW + timedelta(minutes=5)).isoformat()
    assert register.blocked_rows(limit=10) == []


def test_legacy_dns_programming_block_is_requeued_without_releasing_other_blocks(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")
    register.block(
        asset="AUDUSD", timeframe="D1",
        reason=(
            "LOCAL_PROGRAMMING_ERROR; function=_execute_acquisition; lane=AUDUSD:D1; "
            "provider=BINANCE; underlying_exception=gaierror: [Errno 8] name unavailable"
        ),
        at=NOW, approved=True,
    )
    register.block(
        asset="AUDUSD", timeframe="M5",
        reason="LOCAL_PROGRAMMING_ERROR; underlying_exception=ValueError: invariant",
        at=NOW, approved=True,
    )

    assert register.release_legacy_dns_blocks(at=NOW) == 1
    rows = {(row["asset"], row["timeframe"]): row for row in register.rows()}
    assert rows[("AUDUSD", "D1")]["state"] == "RETRY"
    assert rows[("AUDUSD", "D1")]["next_check_at_utc"] == NOW.isoformat()
    assert rows[("AUDUSD", "M5")]["state"] == "BLOCKED"


def test_blocked_lane_does_not_stop_other_due_lanes(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")
    register.block(asset="AUDUSD", timeframe="M5", reason="AUTHENTICATION_FAILED", at=NOW, approved=True)
    with register._connection() as connection:
        connection.execute(
            """UPDATE lane_update_register
               SET state='READY', next_check_at_utc=?, retry_not_before_utc=NULL
               WHERE asset='AUDUSD' AND timeframe='D1'""",
            (NOW.isoformat(),),
        )

    due = register.claim_due(at=NOW, limit=10)

    assert [(row["asset"], row["timeframe"]) for row in due] == [("AUDUSD", "D1")]


def test_verified_credential_repair_requeues_only_authentication_blocks(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")
    register.block(asset="AUDUSD", timeframe="M5", reason="Waiting for provider credential repair: TWELVE_DATA", at=NOW, approved=True)
    register.block(asset="AUDUSD", timeframe="D1", reason="LOCAL_PROGRAMMING_ERROR; provider route requires repair", at=NOW, approved=True)

    released = register.release_verified_credential_blocks(at=NOW)
    rows = {(row["asset"], row["timeframe"]): row for row in register.rows()}

    assert released == 1
    assert rows[("AUDUSD", "M5")]["state"] == "RETRY"
    assert rows[("AUDUSD", "M5")]["last_outcome"] == "CREDENTIAL_REPAIRED_RETRY_QUEUED"
    assert rows[("AUDUSD", "D1")]["state"] == "BLOCKED"


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


def test_credit_window_recovery_is_one_time_and_does_not_touch_normal_register_wakes(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    journal = SchedulerJournal(database, tmp_path / "scheduler.json")
    assert not _credit_window_recovery_required(journal)

    journal.data["manual_requests"] = [{
        "id": "legacy-credit-window", "status": "Required",
        "providers_considered": [{"provider": "TWELVE_DATA", "reason": "CREDIT_WINDOW"}],
    }]
    assert _credit_window_recovery_required(journal)

    journal.data["credit_window_recovery_revision"] = 1
    assert not _credit_window_recovery_required(journal)
    journal.data["manual_requests"][0]["reconciliation_status"] = "AUTOMATION_RESTORED"
    assert _credit_window_register_recovery_required(journal)
    journal.data["credit_window_register_recovery_revision"] = 1
    assert not _credit_window_register_recovery_required(journal)


def test_automation_recovery_releases_only_named_blocked_lanes(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")
    register.block(asset="AUDUSD", timeframe="M5", reason="NO_ELIGIBLE_PROVIDER", at=NOW, approved=True)
    register.block(asset="AUDUSD", timeframe="D1", reason="NO_ELIGIBLE_PROVIDER", at=NOW, approved=True)

    released = register.release_automation_restored_blocks([("AUDUSD", "M5")], at=NOW)
    rows = {(row["asset"], row["timeframe"]): row for row in register.rows()}

    assert released == 1
    assert rows[("AUDUSD", "M5")]["state"] == "RETRY"
    assert rows[("AUDUSD", "M5")]["last_outcome"] == "CREDIT_WINDOW_RECOVERY_RETRY_QUEUED"
    assert rows[("AUDUSD", "D1")]["state"] == "BLOCKED"


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


def test_terminal_operator_fetch_is_released_and_cannot_preempt_normal_work(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    journal = SchedulerJournal(database, tmp_path / "scheduler.json")
    lane = journal.lane("AUDUSD", "M5")
    lane["operator_fetch_pending"] = {
        "id": "terminal-fetch", "requested_mode": "initial",
        "requested_start": "2025-07-13", "requested_end": "2026-07-13",
        "backfill_from_start": True,
    }
    lane["last_operator_fetch_result"] = {
        "operation_id": "terminal-fetch", "outcome": "FAILED",
    }
    journal.data["acquisition_queue"] = [{
        "lane": "AUDUSD:M5", "work_class": "OPERATOR_FETCH", "operational_state": "Ready",
    }]
    journal.save()

    restored = SchedulerJournal(database, tmp_path / "scheduler.json")
    released = _release_terminal_operator_fetches(restored, at=NOW)

    assert released == [("AUDUSD", "M5")]
    assert "operator_fetch_pending" not in restored.lane("AUDUSD", "M5")
    assert restored.data["acquisition_queue"] == []


def test_historical_operator_fetch_does_not_replace_claimed_current_boundary(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    journal = tmp_path / "scheduler.json"
    LaneUpdateRegister(database).audit_estate(at=NOW, reason="TEST")
    submitted = run_operator_fetch(
        database, symbol="AUDUSD", timeframe="M5", credential="fixture",
        requested_mode="initial", journal_path=journal, at=NOW, defer_dispatch=True,
    )
    calls: list[str] = []
    run_due_acquisitions(
        database, at=NOW, credential="fixture", journal_path=journal,
        acquirer=lambda _database, **kwargs: calls.append(str(kwargs["from_date"])) or {"inserted": 1, "corrected": 0},
        time_triggered=True,
    )
    lane = SchedulerJournal(database, journal).lane("AUDUSD", "M5")
    assert calls and calls[0] != submitted["requested_range"]["start"]
    assert lane["operator_fetch_pending"]["id"] == submitted["operation_id"]
    assert "last_operator_fetch_result" not in lane


def test_credit_window_deferral_retries_instead_of_blocking_a_normal_lane(tmp_path: Path, monkeypatch) -> None:
    database = _m5_lane(tmp_path)
    journal = tmp_path / "scheduler.json"
    LaneUpdateRegister(database).audit_estate(at=NOW, reason="TEST")
    profile = ProviderProfile(
        provider="TEST_PROVIDER", enabled=True,
        supported_asset_classes=("FX",), supported_timeframes=("M5",),
        credential_environment=None, entitlement_state="AVAILABLE",
        request_limit=1, request_window_seconds=60, maximum_rows_per_request=4_000,
        history_limit_days=None, cost_class=0, priority=1, cooldown_seconds=30,
        mappings=({
            "asset": "AUDUSD", "symbol": "AUDUSD", "timeframes": ["M5"],
            "mapping_class": "EXACT_REPRESENTATION", "reviewed_status": "REVIEWED",
            "authority_source": "TEST",
        },),
    )

    def credit_window(_self, *_args, **_kwargs):
        return {
            "eligible": False, "reason": "CREDIT_WINDOW",
            "next_available": "2026-07-14T00:11:00+00:00",
        }

    original_inspect = RateBudgetController.inspect

    def queue_capacity_available(self, *args, **kwargs):
        inspection = original_inspect(self, *args, **kwargs)
        if kwargs.get("work_class") == "QUEUE":
            inspection["queue_available"] = 1
        return inspection

    monkeypatch.setattr(RateBudgetController, "reserve", credit_window)
    monkeypatch.setattr(RateBudgetController, "inspect", queue_capacity_available)
    snapshot = run_due_acquisitions(
        database, at=NOW, credential=None, journal_path=journal,
        acquirer=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not fetch")),
        provider_profiles=(profile,), time_triggered=True,
    )

    row = next(
        item for item in LaneUpdateRegister(database).rows()
        if item["asset"] == "AUDUSD" and item["timeframe"] == "M5"
    )
    assert row["state"] == "RETRY"
    assert "Credit Window" in str(row["last_outcome"])
    assert snapshot["register"]["blocked_count"] == 0


def test_daily_provider_not_ready_retries_after_a_bounded_delay(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "scheduler.json"
    observed = datetime(2026, 7, 14, 22, 10, tzinfo=UTC)
    _create_lane(database, "AUDUSD", ["2026-07-10"])
    register = LaneUpdateRegister(database)
    register.audit_estate(at=observed, reason="TEST")
    with register._connection() as connection:
        connection.execute(
            """UPDATE lane_update_register
               SET state='READY',next_expected_boundary_utc=?,next_check_at_utc=?,retry_not_before_utc=NULL
               WHERE asset='AUDUSD' AND timeframe='D1'""",
            (observed.isoformat(), observed.isoformat()),
        )
    profile = ProviderProfile(
        provider="TWELVE_DATA", enabled=True,
        supported_asset_classes=("FX",), supported_timeframes=("D1",),
        credential_environment=None, entitlement_state="AVAILABLE",
        request_limit=55, request_window_seconds=60, maximum_rows_per_request=4_000,
        history_limit_days=None, cost_class=0, priority=1, cooldown_seconds=0,
        mappings=({
            "asset":"AUDUSD", "symbol":"AUD/USD", "timeframes":["D1"],
            "mapping_class":"EXACT_REPRESENTATION", "reviewed_status":"REVIEWED",
            "authority_source":"TEST",
        },),
        rate_policy_verified=True,
    )

    snapshot = run_due_acquisitions(
        database, at=observed, credential=None, journal_path=journal,
        acquirer=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AcquisitionError("PROVIDER_D1_NOT_READY", "daily aggregate still rolling")
        ),
        provider_profiles=(profile,), time_triggered=True,
    )

    row = next(
        item for item in LaneUpdateRegister(database).rows()
        if item["asset"] == "AUDUSD" and item["timeframe"] == "D1"
    )
    self_state = SchedulerJournal(database, journal).lane("AUDUSD", "D1")
    assert row["state"] == "RETRY"
    assert datetime.fromisoformat(row["retry_not_before_utc"]) == observed.replace(minute=15)
    assert "PROVIDER_D1_NOT_READY" in str(row["last_outcome"])
    assert self_state["result"] == "WAITING"
    assert snapshot["register"]["blocked_count"] == 0
    assert _retry_delay_seconds(2, "PROVIDER_D1_NOT_READY") == 600


def test_daily_provider_not_ready_fails_over_to_an_approved_provider(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "scheduler.json"
    observed = datetime(2026, 7, 14, 22, 10, tzinfo=UTC)
    _create_lane(database, "AUDUSD", ["2026-07-10"])
    register = LaneUpdateRegister(database)
    register.audit_estate(at=observed, reason="TEST")
    with register._connection() as connection:
        connection.execute(
            """UPDATE lane_update_register
               SET state='READY',next_expected_boundary_utc=?,next_check_at_utc=?,retry_not_before_utc=NULL
               WHERE asset='AUDUSD' AND timeframe='D1'""",
            (observed.isoformat(), observed.isoformat()),
        )

    def profile(provider: str, priority: int, symbol: str) -> ProviderProfile:
        return ProviderProfile(
            provider=provider, enabled=True,
            supported_asset_classes=("FX",), supported_timeframes=("D1",),
            credential_environment=None, entitlement_state="AVAILABLE",
            request_limit=55, request_window_seconds=60, maximum_rows_per_request=4_000,
            history_limit_days=None, cost_class=0, priority=priority, cooldown_seconds=0,
            mappings=({
                "asset":"AUDUSD", "symbol":symbol, "timeframes":["D1"],
                "mapping_class":"EXACT_REPRESENTATION", "reviewed_status":"REVIEWED",
                "authority_source":"TEST_APPROVED_FALLBACK",
            },),
            rate_policy_verified=True,
        )

    calls: list[str] = []
    def acquire(_database, **kwargs):
        provider = str(kwargs["provider"])
        calls.append(provider)
        if provider == "TWELVE_DATA":
            raise AcquisitionError("PROVIDER_D1_NOT_READY", "daily aggregate still rolling")
        edge = int(datetime(2026, 7, 14, tzinfo=UTC).timestamp())
        with registered_writer(database) as connection:
            run_id = connection.execute(
                "SELECT created_by_ingest_run_id FROM bars WHERE asset='AUDUSD' LIMIT 1"
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO bars(asset,timeframe,open_time_utc,open,high,low,close,
                                      created_by_ingest_run_id,updated_by_ingest_run_id)
                   VALUES('AUDUSD','D1',?,'1','2','0','1',?,?)""",
                (edge, run_id, run_id),
            )
            connection.execute(
                """UPDATE lane_state SET high_watermark_open_time_utc=?,state_version=state_version+1
                   WHERE asset='AUDUSD' AND timeframe='D1'""",
                (edge,),
            )
        return {"received":1, "staged":1, "inserted":1, "corrected":0, "unchanged":0}

    snapshot = run_due_acquisitions(
        database, at=observed, credential=None, journal_path=journal,
        acquirer=acquire,
        provider_profiles=(
            profile("TWELVE_DATA", 1, "AUD/USD"),
            profile("YAHOO_FINANCE", 2, "AUDUSD=X"),
        ),
        time_triggered=True,
    )

    lane = SchedulerJournal(database, journal).lane("AUDUSD", "D1")
    assert calls == ["TWELVE_DATA", "YAHOO_FINANCE"]
    assert lane["result"] == "SUCCESS"
    assert lane["current_provider"] == "YAHOO_FINANCE"
    assert snapshot["register"]["blocked_count"] == 0


def test_live_us_equity_d1_fallback_symbols_have_reviewed_yahoo_routes() -> None:
    yahoo = next(
        profile for profile in load_provider_profiles()
        if profile.provider == "YAHOO_FINANCE"
    )
    mappings = {
        str(mapping.get("asset")): mapping
        for mapping in yahoo.mappings
    }
    for symbol in ("AMZN", "META", "NVDA", "QQQ", "XOM"):
        mapping = mappings[symbol]
        assert mapping["symbol"] == symbol
        assert mapping["timeframes"] == ["D1"]
        assert mapping["mapping_class"] == "EXACT_REPRESENTATION"
        assert mapping["reviewed_status"] == "REVIEWED"


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


def test_scheduler_audit_save_stages_only_new_immutable_entries(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    path = tmp_path / "scheduler.json"
    journal = SchedulerJournal(database, path)
    journal.append_event({"id": "first", "timestamp": NOW.isoformat(), "event": "FIRST"})
    journal.save()
    with open_read_only(database) as connection:
        first_count = connection.execute("SELECT count(*) FROM scheduler_audit_events").fetchone()[0]

    # The second control-state save has an overlapping hot tail but no new
    # immutable event.  It must not inflate the audit ledger.
    journal.save()
    with open_read_only(database) as connection:
        assert connection.execute("SELECT count(*) FROM scheduler_audit_events").fetchone()[0] == first_count

    journal.append_event({"id": "second", "timestamp": NOW.isoformat(), "event": "SECOND"})
    journal.save()
    with open_read_only(database) as connection:
        assert connection.execute("SELECT count(*) FROM scheduler_audit_events").fetchone()[0] == first_count + 1


def test_scheduler_audit_cache_is_shared_by_fresh_store_facades(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    path = tmp_path / "scheduler.json"
    first = SchedulerJournal(database, path)
    first.append_event({"id": "first", "timestamp": NOW.isoformat(), "event": "FIRST"})
    first.save()

    second = SchedulerJournal(database, path)
    assert second.store._known_audit_event_ids is first.store._known_audit_event_ids
    second.save()

    with open_read_only(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM scheduler_audit_events"
        ).fetchone()[0] == 1


def test_hot_history_compaction_keeps_the_newest_record_for_each_ordering() -> None:
    journal = {
        "events": [{"id": value} for value in range(25, 0, -1)],
        "routing_decisions": [{"id": value} for value in range(3, 0, -1)],
        "execution_trace_events": [{"id": value} for value in range(25)],
        "operation_timing_records": [{"id": value} for value in range(25)],
        "scheduler_cycles": [{"id": value} for value in range(15)],
    }

    assert compact_hot_history_only(journal) is True
    assert [value["id"] for value in journal["events"]] == list(range(25, 5, -1))
    assert [value["id"] for value in journal["routing_decisions"]] == [3]
    assert [value["id"] for value in journal["execution_trace_events"]] == list(range(5, 25))
    assert [value["id"] for value in journal["operation_timing_records"]] == list(range(5, 25))
    assert [value["id"] for value in journal["scheduler_cycles"]] == list(range(5, 15))


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
        "providers_considered": [{"provider": "BINANCE"}],
    }
    assert lane["providers_considered"] == [{"provider": "BINANCE", "eligible": True}]
