from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fragarach_ii.estate_audit import (
    audit_history, audit_schedule, audit_status, configure_audit_schedule,
    run_estate_audit, weekly_audit_due,
)
from fragarach_ii.lane_update_register import LaneUpdateRegister
from fragarach_ii.freshness import provider_route_revision_for_lane
from fragarach_ii.storage import open_read_only, registered_writer
from tests.operations.test_spec063_time_triggered_lane_scheduler import _m5_lane


NOW = datetime(2026, 7, 14, 0, 10, tzinfo=UTC)


def _valid_m5_lane(tmp_path: Path) -> Path:
    database = _m5_lane(tmp_path)
    watermark = int(datetime(2026, 7, 14, tzinfo=UTC).timestamp())
    with registered_writer(database) as connection:
        connection.execute(
            """INSERT INTO lane_state(asset,timeframe,high_watermark_open_time_utc,state_version,
                                        last_ingest_run_id,updated_at_utc)
               VALUES ('AUDUSD','M5',?,1,'run-1',?)""",
            (watermark, NOW.isoformat()),
        )
    return database


def test_operator_audit_is_immutable_and_never_acquires(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    LaneUpdateRegister(database).audit_estate(at=NOW, reason="TEST_SEED")
    with open_read_only(database) as connection:
        before = connection.execute("SELECT count(*) FROM bars").fetchone()[0]

    first = run_estate_audit(database, at=NOW)
    second = run_estate_audit(database, at=NOW)

    with open_read_only(database) as connection:
        after = connection.execute("SELECT count(*) FROM bars").fetchone()[0]
    assert before == after
    assert first["audit_run_id"] != second["audit_run_id"]
    assert second["overall_result"] == "HEALTHY"
    assert audit_status(database)["audit_run_id"] == second["audit_run_id"]


def test_missing_update_register_row_is_reported_without_runtime_mutation(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST_SEED")
    with register._connection() as connection:
        connection.execute("DELETE FROM lane_update_register WHERE asset='AUDUSD' AND timeframe='M5'")
    with open_read_only(database) as connection:
        before = connection.execute("SELECT count(*) FROM bars").fetchone()[0]

    report = run_estate_audit(database, at=NOW)

    with open_read_only(database) as connection:
        after = connection.execute("SELECT count(*) FROM bars").fetchone()[0]
    assert report["finding_counts"]["REPAIRABLE"] >= 1
    assert report["safe_repairs_applied"] == 0
    assert before == after
    assert not any(row["asset"] == "AUDUSD" and row["timeframe"] == "M5" for row in register.rows())


def test_route_revision_drift_creates_review_plan_without_blocking_lane(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST_SEED")
    with register._connection() as connection:
        connection.execute(
            "UPDATE lane_update_register SET provider_route_revision='stale' WHERE asset='AUDUSD' AND timeframe='M5'"
        )

    report = run_estate_audit(database, at=NOW)
    target = next(row for row in register.rows() if row["asset"] == "AUDUSD" and row["timeframe"] == "M5")

    assert report["finding_counts"]["WARNING"] >= 1
    assert report["overall_result"] == "ATTENTION"
    assert report["repair_plan_id"] is not None
    assert target["state"] == "READY"


def test_route_revision_drift_is_reported_once_per_symbol_with_route_facts(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST_SEED")
    with register._connection() as connection:
        connection.execute(
            "UPDATE lane_update_register SET provider_route_revision='stale' WHERE asset='AUDUSD'"
        )

    report = run_estate_audit(database, at=NOW)
    history = audit_history(database, audit_run_id=str(report["audit_run_id"]))
    route_findings = [
        finding for finding in history["selected_report"]["findings"]
        if finding["finding_class"] == "PROVIDER_ROUTE_REVISION_CHANGED"
    ]

    assert len(route_findings) == 1
    observed = json.loads(route_findings[0]["observed_facts_json"])
    expected = json.loads(route_findings[0]["expected_facts_json"])
    assert observed["affected_lanes"] == ["AUDUSD:D1", "AUDUSD:M5"]
    assert expected["provider_route"]["registration_route"]["asset"] == "AUDUSD"


def test_fingerprint_version_migration_does_not_create_weekly_route_findings(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST_SEED")
    register.block(
        asset="AUDUSD", timeframe="M5", reason="LOCAL_PROGRAMMING_ERROR; fixture", at=NOW, approved=True,
    )
    with register._connection() as connection:
        connection.execute(
            "UPDATE lane_update_register SET provider_route_revision='legacy-format'"
        )
        connection.execute(
            "UPDATE register_meta SET value='1' WHERE key='provider_route_revision_version'"
        )

    migrated = LaneUpdateRegister(database)
    report = run_estate_audit(database, at=NOW)
    target = next(
        row for row in migrated.rows()
        if row["asset"] == "AUDUSD" and row["timeframe"] == "M5"
    )

    assert report["finding_counts"]["WARNING"] == 0
    assert target["state"] == "BLOCKED"
    assert target["last_outcome"].startswith("LOCAL_PROGRAMMING_ERROR")


def test_current_running_lane_is_not_reported_as_interrupted(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST_SEED")
    register.claim_due(at=NOW, limit=1)

    report = run_estate_audit(database, at=NOW + timedelta(minutes=2))

    assert report["finding_counts"]["REPAIRABLE"] == 0


def test_old_running_lane_is_reported_as_interrupted(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST_SEED")
    register.claim_due(at=NOW, limit=1)

    report = run_estate_audit(database, at=NOW + timedelta(minutes=16))

    history = audit_history(database, audit_run_id=str(report["audit_run_id"]))
    assert any(
        finding["finding_class"] == "STALE_RUNNING_REGISTER_ROW"
        for finding in history["selected_report"]["findings"]
    )


def test_reviewed_route_revision_refresh_preserves_blocked_lane_state(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST_SEED")
    register.block(
        asset="AUDUSD", timeframe="M5",
        reason="LOCAL_PROGRAMMING_ERROR; reviewed repair pending", at=NOW, approved=True,
    )
    with register._connection() as connection:
        connection.execute(
            "UPDATE lane_update_register SET provider_route_revision='stale' "
            "WHERE asset='AUDUSD' AND timeframe='M5'"
        )

    result = register.refresh_provider_route_revisions(at=NOW, reason="TEST_REVIEW")
    target = next(
        row for row in register.rows()
        if row["asset"] == "AUDUSD" and row["timeframe"] == "M5"
    )

    assert result["route_revisions_changed"] >= 1
    assert result["lane_states_changed"] == 0
    assert target["state"] == "BLOCKED"
    assert target["last_outcome"].startswith("LOCAL_PROGRAMMING_ERROR")


def test_provider_route_revision_does_not_change_after_normal_publication(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    with open_read_only(database) as connection:
        before = provider_route_revision_for_lane(connection, symbol="AUDUSD", timeframe="M5")
    with registered_writer(database) as connection:
        connection.execute(
            "UPDATE lane_state SET state_version=state_version+1,last_ingest_run_id=NULL,updated_at_utc=? WHERE asset='AUDUSD' AND timeframe='M5'",
            (datetime(2026, 7, 15, tzinfo=UTC).isoformat(),),
        )
    with open_read_only(database) as connection:
        after = provider_route_revision_for_lane(connection, symbol="AUDUSD", timeframe="M5")
    assert after == before


def test_weekly_audit_uses_persisted_brisbane_schedule_and_keeps_manual_runs_separate(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    configured = configure_audit_schedule(database, weekday="SUNDAY", hour=10, minute=30)
    assert configured["timezone"] == "Australia/Brisbane"
    assert configured["local_time"] == "10:30"
    due_at = datetime.fromisoformat(configured["next_scheduled_at_utc"])
    assert weekly_audit_due(database, at=due_at)

    run_estate_audit(database, at=due_at, trigger="OPERATOR_REQUEST")
    assert weekly_audit_due(database, at=due_at)

    weekly = run_estate_audit(database, at=due_at, trigger="WEEKLY_MAINTENANCE")
    assert not weekly_audit_due(database, at=due_at)
    reports = audit_history(database, audit_run_id=weekly["audit_run_id"])
    assert reports["reports"][0]["audit_run_id"] == weekly["audit_run_id"]
    assert reports["selected_report"]["audit_run_id"] == weekly["audit_run_id"]
