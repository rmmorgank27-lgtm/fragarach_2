from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.estate_audit import audit_status, run_estate_audit
from fragarach_ii.lane_update_register import LaneUpdateRegister
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


def test_missing_update_register_row_is_repaired_without_canonical_mutation(tmp_path: Path) -> None:
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
    assert report["safe_repairs_applied"] >= 1
    assert before == after
    assert any(row["asset"] == "AUDUSD" and row["timeframe"] == "M5" for row in register.rows())


def test_route_revision_drift_creates_review_plan_and_blocks_only_that_lane(tmp_path: Path) -> None:
    database = _valid_m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST_SEED")
    with register._connection() as connection:
        connection.execute(
            "UPDATE lane_update_register SET provider_route_revision='stale' WHERE asset='AUDUSD' AND timeframe='M5'"
        )

    report = run_estate_audit(database, at=NOW)
    target = next(row for row in register.rows() if row["asset"] == "AUDUSD" and row["timeframe"] == "M5")

    assert report["finding_counts"]["BLOCKING"] >= 1
    assert report["repair_plan_id"] is not None
    assert target["state"] == "BLOCKED"
