"""Bounded, explicit Estate Audit and operational reconciliation workflow."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .freshness import authority_revision_for_lane, normalized_utc
from .lane_update_register import LaneUpdateRegister, REGISTER_CONTRACT
from .operational_schedule import schedule_for_lane
from .scheduler_integrity import active_universe
from .storage import open_read_only


AUDIT_CONTRACT = "fragarach_ii.estate_audit.v1"
AUDIT_TRIGGERS = frozenset({
    "OPERATOR_REQUEST", "WEEKLY_MAINTENANCE", "SCHEDULER_RECOVERY",
    "REGISTER_RECOVERY", "CALENDAR_OR_SESSION_REVISION",
    "PROVIDER_ROUTE_REVISION", "LIFECYCLE_CHANGE",
})
_MAX_FINDINGS = 250
_DETAIL_LIMIT = 1_500


def run_estate_audit(
    database_path: str | Path,
    *,
    trigger: str = "OPERATOR_REQUEST",
    at: datetime | None = None,
    apply_safe_repairs: bool = True,
) -> dict[str, object]:
    """Audit every active lane without acquiring or mutating canonical evidence."""
    selected_trigger = str(trigger).strip().upper()
    if selected_trigger not in AUDIT_TRIGGERS:
        raise ValueError(f"unsupported audit trigger: {trigger}")
    observed = normalized_utc(at)
    started = time.monotonic()
    register = LaneUpdateRegister(database_path)
    lock_path = register.path.with_suffix(".audit.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("ESTATE_AUDIT_ALREADY_RUNNING") from error
        try:
            return _run_locked(
                database_path, register, selected_trigger, observed,
                apply_safe_repairs=apply_safe_repairs, started=started,
            )
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def audit_status(database_path: str | Path) -> dict[str, object]:
    """Read the bounded latest-audit summary without projecting the estate."""
    register = LaneUpdateRegister(database_path)
    _ensure_tables(register)
    with register._connection() as connection:  # scheduler-side runtime DB
        row = connection.execute(
            """SELECT audit_run_id,trigger,started_at_utc,completed_at_utc,overall_result,
                      finding_counts_json,repair_plan_id,report_checksum,report_bytes
                 FROM estate_audit_runs ORDER BY completed_at_utc DESC,audit_run_id DESC LIMIT 1"""
        ).fetchone()
    if row is None:
        return {"contract": AUDIT_CONTRACT, "state": "NOT_RUN"}
    completed = datetime.fromisoformat(str(row[3]).replace("Z", "+00:00"))
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=UTC)
    return {
        "contract": AUDIT_CONTRACT,
        "state": "COMPLETED",
        "audit_run_id": row[0], "trigger": row[1], "started_at_utc": row[2],
        "completed_at_utc": row[3], "overall_result": row[4],
        "finding_counts": json.loads(row[5]), "repair_plan_id": row[6],
        "report_checksum": row[7], "report_bytes": int(row[8]),
        "next_weekly_audit_at_utc": (completed.astimezone(UTC) + timedelta(days=7)).isoformat(),
    }


def _run_locked(
    database_path: str | Path,
    register: LaneUpdateRegister,
    trigger: str,
    observed: datetime,
    *,
    apply_safe_repairs: bool,
    started: float,
) -> dict[str, object]:
    _ensure_tables(register)
    audit_run_id = f"audit-{uuid.uuid4().hex}"
    universe = active_universe(database_path)
    active = universe["active_lanes"]
    register_rows = {(str(row["asset"]), str(row["timeframe"])): row for row in register.rows()}
    findings: list[dict[str, object]] = []
    safe_repairs: list[dict[str, object]] = []
    review_repairs: list[dict[str, object]] = []
    inspected = 0
    with open_read_only(database_path) as authority:
        for lane_id, lane in sorted(active.items()):
            inspected += 1
            asset, timeframe = str(lane["symbol"]), str(lane["timeframe"])
            key = (asset, timeframe)
            row = register_rows.get(key)
            lane_state, bars = _lane_facts(authority, asset, timeframe)
            if bars["count"] and lane_state is None:
                _finding(findings, "INTEGRITY", "LANE_STATE_MISSING", lane_id,
                         {"bar_count": bars["count"]}, {"lane_state": "present"}, observed,
                         "Review canonical lane state and validation authority")
            elif lane_state is not None and bars["max_open"] is not None and int(lane_state[0] or 0) != int(bars["max_open"]):
                _finding(findings, "INTEGRITY", "LANE_WATERMARK_MISMATCH", lane_id,
                         {"high_watermark_open_time_utc": lane_state[0], "max_open_time_utc": bars["max_open"]},
                         {"high_watermark_open_time_utc": bars["max_open"]}, observed,
                         "Review canonical lane-state authority; no automatic repair")
            if row is None:
                _finding(findings, "REPAIRABLE", "UPDATE_REGISTER_ROW_MISSING", lane_id,
                         {}, {"update_register_row": "present"}, observed,
                         "Rebuild update-register row from approved schedule")
                safe_repairs.append({"class": "CREATE_UPDATE_REGISTER_ROW", "lane": lane_id})
            schedule = schedule_for_lane(authority, symbol=asset, timeframe=timeframe, after=observed)
            if not schedule.get("available") or not schedule.get("next_scheduled_acquisition"):
                _finding(findings, "BLOCKING", "SCHEDULE_UNAVAILABLE", lane_id,
                         {"reason": schedule.get("reason_code")}, {"approved_schedule": "resolves"}, observed,
                         "Review calendar or session authority")
                review_repairs.append({"class": "CALENDAR_OR_SESSION_REVIEW", "lane": lane_id})
                continue
            if row is None:
                continue
            schedule_revision = _schedule_revision(schedule)
            route_revision = authority_revision_for_lane(authority, symbol=asset, timeframe=timeframe)
            if row.get("calendar_or_session_revision") != schedule_revision:
                _finding(findings, "REPAIRABLE", "UPDATE_REGISTER_SCHEDULE_STALE", lane_id,
                         {"register_revision": row.get("calendar_or_session_revision")},
                         {"calendar_or_session_revision": schedule_revision}, observed,
                         "Recompute the next approved boundary")
                safe_repairs.append({"class": "RECOMPUTE_SCHEDULE", "lane": lane_id})
            if row.get("provider_route_revision") != route_revision:
                _finding(findings, "BLOCKING", "PROVIDER_ROUTE_REVISION_CHANGED", lane_id,
                         {"register_revision": row.get("provider_route_revision")},
                         {"provider_route_revision": route_revision}, observed,
                         "Review provider route before resuming normal work")
                review_repairs.append({"class": "PROVIDER_ROUTE_REVIEW", "lane": lane_id})
                register.block(
                    asset=asset, timeframe=timeframe,
                    reason="PROVIDER_ROUTE_REVISION_CHANGED", at=observed,
                )
            if row.get("state") == "RUNNING":
                _finding(findings, "REPAIRABLE", "STALE_RUNNING_REGISTER_ROW", lane_id,
                         {"last_attempted_at_utc": row.get("last_attempted_at_utc")},
                         {"state": "RETRY or BLOCKED"}, observed,
                         "Recover interrupted local runtime state")
                safe_repairs.append({"class": "RECOVER_RUNNING_ROW", "lane": lane_id})
            if row.get("state") in {"RETRY", "BLOCKED", "PAUSED"} and not row.get("last_outcome"):
                _finding(findings, "BLOCKING", "REGISTER_STATE_REASON_MISSING", lane_id,
                         {"state": row.get("state")}, {"last_outcome": "classified reason"}, observed,
                         "Review operational state ownership")
                review_repairs.append({"class": "OPERATIONAL_STATE_REVIEW", "lane": lane_id})

    active_keys = {(str(lane["symbol"]), str(lane["timeframe"])) for lane in active.values()}
    for asset, timeframe in sorted(set(register_rows) - active_keys):
        lane_id = f"{asset}:{timeframe}"
        _finding(findings, "REPAIRABLE", "INACTIVE_UPDATE_REGISTER_ROW", lane_id,
                 {"state": register_rows[(asset, timeframe)].get("state")},
                 {"register_row": "removed"}, observed,
                 "Remove stale operational row")
        safe_repairs.append({"class": "REMOVE_UPDATE_REGISTER_ROW", "lane": lane_id})

    # A rebuild is atomic and operates only on scheduler runtime state. It
    # never changes bars, provenance, registration, validation, or routes.
    repair_report = None
    # Do not acknowledge a changed provider/calendar authority by rebuilding
    # the row beneath a review-required finding.  The affected lane remains
    # visibly blocked until an operator accepts the authority change.
    if apply_safe_repairs and safe_repairs and not review_repairs:
        repair_report = register.audit_estate(at=observed, reason=trigger)
        for repair in safe_repairs:
            repair["applied"] = True
    recovery_count = register.recover_running(at=observed) if apply_safe_repairs else 0
    if recovery_count:
        safe_repairs.append({"class": "RECOVER_RUNNING_ROW", "count": recovery_count, "applied": True})

    finding_counts = {severity: sum(item["severity"] == severity for item in findings)
                      for severity in ("INFO", "WARNING", "REPAIRABLE", "BLOCKING", "INTEGRITY")}
    overall = "INTEGRITY" if finding_counts["INTEGRITY"] else "BLOCKING" if finding_counts["BLOCKING"] else "REPAIRED" if safe_repairs else "HEALTHY"
    plan_id = f"repair-plan-{uuid.uuid4().hex}" if review_repairs else None
    report = {
        "contract": AUDIT_CONTRACT, "audit_run_id": audit_run_id, "trigger": trigger,
        "scope_revision": universe["revision"], "overall_result": overall,
        "finding_ids": [item["finding_id"] for item in findings],
        "finding_counts": finding_counts,
        "safe_repairs_applied": sum(bool(item.get("applied")) for item in safe_repairs),
        "review_required_repairs": len(review_repairs), "lanes_inspected": inspected,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
    }
    report_payload = json.dumps(report, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(report_payload.encode()).hexdigest()
    completed = datetime.now(UTC).isoformat()
    with register._connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """INSERT INTO estate_audit_runs(
                       audit_run_id,trigger,started_at_utc,completed_at_utc,scope_revision,
                       audit_contract,overall_result,finding_counts_json,repair_plan_id,
                       report_checksum,report_json,report_bytes
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (audit_run_id, trigger, observed.isoformat(), completed, str(universe["revision"]),
                 AUDIT_CONTRACT, overall, json.dumps(finding_counts, sort_keys=True), plan_id,
                 checksum, report_payload, len(report_payload.encode())),
            )
            if plan_id:
                connection.execute(
                    "INSERT INTO estate_audit_repair_plans(plan_id,audit_run_id,created_at_utc,repairs_json) VALUES (?,?,?,?)",
                    (plan_id, audit_run_id, completed, json.dumps(review_repairs, sort_keys=True, separators=(",", ":"))),
                )
            for finding in findings:
                connection.execute(
                    """INSERT INTO estate_audit_findings(
                           finding_id,audit_run_id,severity,finding_class,authority_identifier,
                           observed_facts_json,expected_facts_json,detected_at_utc,recommended_action
                       ) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (finding["finding_id"], audit_run_id, finding["severity"], finding["finding_class"],
                     finding["authority_identifier"], json.dumps(finding["observed_facts"], sort_keys=True),
                     json.dumps(finding["expected_facts"], sort_keys=True), finding["detected_at_utc"],
                     finding["recommended_action"]),
                )
            for repair in safe_repairs:
                connection.execute(
                    "INSERT INTO estate_audit_repairs(repair_id,audit_run_id,repair_class,lane,applied_at_utc,detail_json) VALUES (?,?,?,?,?,?)",
                    (f"repair-{uuid.uuid4().hex}", audit_run_id, str(repair["class"]), repair.get("lane"), completed,
                     json.dumps(repair, sort_keys=True, separators=(",", ":"))),
                )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    register.record_audit(at=observed, reason=trigger)
    return {**report, "completed_at_utc": completed, "repair_plan_id": plan_id,
            "report_checksum": checksum, "report_bytes": len(report_payload.encode()),
            "register_repair": repair_report}


def _ensure_tables(register: LaneUpdateRegister) -> None:
    with register._connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS estate_audit_runs (
                audit_run_id TEXT PRIMARY KEY, trigger TEXT NOT NULL, started_at_utc TEXT NOT NULL,
                completed_at_utc TEXT NOT NULL, scope_revision TEXT NOT NULL, audit_contract TEXT NOT NULL,
                overall_result TEXT NOT NULL, finding_counts_json TEXT NOT NULL, repair_plan_id TEXT,
                report_checksum TEXT NOT NULL, report_json TEXT NOT NULL, report_bytes INTEGER NOT NULL
            ) STRICT;
            CREATE TABLE IF NOT EXISTS estate_audit_findings (
                finding_id TEXT PRIMARY KEY, audit_run_id TEXT NOT NULL, severity TEXT NOT NULL,
                finding_class TEXT NOT NULL, authority_identifier TEXT NOT NULL,
                observed_facts_json TEXT NOT NULL, expected_facts_json TEXT NOT NULL,
                detected_at_utc TEXT NOT NULL, recommended_action TEXT NOT NULL,
                FOREIGN KEY(audit_run_id) REFERENCES estate_audit_runs(audit_run_id)
            ) STRICT;
            CREATE TABLE IF NOT EXISTS estate_audit_repair_plans (
                plan_id TEXT PRIMARY KEY, audit_run_id TEXT NOT NULL, created_at_utc TEXT NOT NULL,
                repairs_json TEXT NOT NULL, FOREIGN KEY(audit_run_id) REFERENCES estate_audit_runs(audit_run_id)
            ) STRICT;
            CREATE TABLE IF NOT EXISTS estate_audit_repairs (
                repair_id TEXT PRIMARY KEY, audit_run_id TEXT NOT NULL, repair_class TEXT NOT NULL,
                lane TEXT, applied_at_utc TEXT NOT NULL, detail_json TEXT NOT NULL,
                FOREIGN KEY(audit_run_id) REFERENCES estate_audit_runs(audit_run_id)
            ) STRICT;
            CREATE TRIGGER IF NOT EXISTS estate_audit_runs_no_update BEFORE UPDATE ON estate_audit_runs
                BEGIN SELECT RAISE(ABORT,'estate audit runs are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS estate_audit_runs_no_delete BEFORE DELETE ON estate_audit_runs
                BEGIN SELECT RAISE(ABORT,'estate audit runs are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS estate_audit_findings_no_update BEFORE UPDATE ON estate_audit_findings
                BEGIN SELECT RAISE(ABORT,'estate audit findings are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS estate_audit_findings_no_delete BEFORE DELETE ON estate_audit_findings
                BEGIN SELECT RAISE(ABORT,'estate audit findings are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS estate_audit_repair_plans_no_update BEFORE UPDATE ON estate_audit_repair_plans
                BEGIN SELECT RAISE(ABORT,'estate audit repair plans are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS estate_audit_repair_plans_no_delete BEFORE DELETE ON estate_audit_repair_plans
                BEGIN SELECT RAISE(ABORT,'estate audit repair plans are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS estate_audit_repairs_no_update BEFORE UPDATE ON estate_audit_repairs
                BEGIN SELECT RAISE(ABORT,'estate audit repairs are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS estate_audit_repairs_no_delete BEFORE DELETE ON estate_audit_repairs
                BEGIN SELECT RAISE(ABORT,'estate audit repairs are immutable'); END;
            """
        )


def _lane_facts(connection: sqlite3.Connection, asset: str, timeframe: str):
    lane_state = connection.execute(
        "SELECT high_watermark_open_time_utc,state_version,validation_summary FROM lane_state WHERE asset=? AND timeframe=?",
        (asset, timeframe),
    ).fetchone()
    bars = connection.execute(
        "SELECT count(*),min(open_time_utc),max(open_time_utc) FROM bars WHERE asset=? AND timeframe=?",
        (asset, timeframe),
    ).fetchone()
    return lane_state, {"count": int(bars[0]), "min_open": bars[1], "max_open": bars[2]}


def _schedule_revision(schedule: dict[str, object]) -> str:
    source = json.dumps({key: schedule.get(key) for key in (
        "calendar_id", "timezone", "session_close_rule", "calendar_status"
    )}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(source.encode()).hexdigest()


def _finding(
    findings: list[dict[str, object]], severity: str, finding_class: str,
    identifier: str, observed: dict[str, object], expected: dict[str, object],
    at: datetime, action: str,
) -> None:
    if len(findings) >= _MAX_FINDINGS:
        return
    bounded_observed = _bounded(observed)
    bounded_expected = _bounded(expected)
    findings.append({
        "finding_id": f"finding-{uuid.uuid4().hex}", "severity": severity,
        "finding_class": finding_class, "authority_identifier": identifier,
        "observed_facts": bounded_observed, "expected_facts": bounded_expected,
        "detected_at_utc": at.isoformat(), "recommended_action": action,
    })


def _bounded(value: dict[str, object]) -> dict[str, object]:
    encoded = json.dumps(value, sort_keys=True, default=str)
    return value if len(encoded) <= _DETAIL_LIMIT else {"truncated": True, "sha256": hashlib.sha256(encoded.encode()).hexdigest()}
