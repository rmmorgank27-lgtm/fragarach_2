"""Read-only SPEC-040 estate freshness and scheduled-acquisition audit."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .freshness import (
    assess_lane_freshness,
    authority_revision_for_lane,
    normalized_utc,
)
from .storage import open_read_only


LANE_FRESHNESS_REPORT_CONTRACT = "fragarach_ii.lane_freshness_report.v1"


def lane_freshness_report(
    database_path: str | Path,
    *,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Audit every active commissioned lane without mutating authority or data."""

    authority_generated = normalized_utc(clock() if clock else None)
    connection = open_read_only(database_path)
    try:
        lanes = connection.execute(
            """
            SELECT l.asset,l.timeframe,s.validation_summary
            FROM evidence_lanes l
            LEFT JOIN lane_state s ON s.asset=l.asset AND s.timeframe=l.timeframe
            WHERE NOT EXISTS (
                SELECT 1 FROM authority_events e
                WHERE json_extract(e.canonical_payload,'$.body.asset')=l.asset
                  AND json_extract(e.canonical_payload,'$.body.timeframe')=l.timeframe
                  AND (
                    json_extract(e.canonical_payload,'$.body.lifecycle_state') LIKE 'RETIRED%'
                    OR json_extract(e.canonical_payload,'$.body.lifecycle_state') LIKE 'QUARANTINED%'
                    OR json_extract(e.canonical_payload,'$.body.lifecycle_state')='PERMANENTLY_REMOVED'
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM authority_events successor
                    WHERE successor.supersedes_event_id=e.authority_event_id
                  )
            )
            ORDER BY l.asset,l.timeframe
            """
        ).fetchall()
        event_ids_by_lane = _current_event_ids_by_lane(connection, lanes)
        rows = [
            _audit_lane(
                connection,
                symbol=row[0],
                timeframe=row[1],
                validation_summary=row[2],
                authority_generated=authority_generated,
                current_event_ids=event_ids_by_lane.get((str(row[0]), str(row[1])), []),
            )
            for row in lanes
        ]
    finally:
        connection.close()
    revisions = [row["authority_revision"] for row in rows]
    report_revision = hashlib.sha256(
        json.dumps(revisions, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    counts = {
        state: sum(row["freshness"]["state"] == state for row in rows)
        for state in ("Current", "Behind", "Unavailable")
    }
    return {
        "contract": LANE_FRESHNESS_REPORT_CONTRACT,
        "authority_generated": authority_generated.isoformat(),
        "authority_revision": "sha256:" + report_revision,
        "database": str(Path(database_path).expanduser().resolve()),
        "scheduler": {
            "state": "IMPLEMENTED",
            "operational_windows": "DERIVED_FROM_APPROVED_OPERATIONAL_CALENDARS",
            "reason_code": "SCHEDULED_ACQUISITION_CORE_AVAILABLE",
        },
        "summary": {"total": len(rows), **counts},
        "lanes": rows,
    }


def _current_event_ids_by_lane(connection, lanes) -> dict[tuple[str, str], list[str]]:
    """Project current ledger bindings once instead of scanning them per lane."""
    keys = {(str(row[0]), str(row[1])) for row in lanes}
    by_symbol: dict[str, list[tuple[str, str]]] = {}
    for key in keys:
        by_symbol.setdefault(key[0], []).append(key)
    result = {key: [] for key in keys}
    events = connection.execute(
        """
        SELECT e.authority_event_id,e.entity_kind,e.canonical_payload
        FROM authority_events e
        WHERE NOT EXISTS (
            SELECT 1 FROM authority_events successor
            WHERE successor.supersedes_event_id=e.authority_event_id
        )
        AND e.entity_kind IN ('INSTRUMENT_REGISTRATION','EVIDENCE_LANE')
        """
    ).fetchall()
    for event_id, kind, payload_text in events:
        try:
            body = json.loads(payload_text).get("body", {})
            legacy = body.get("legacy_key", {}) if isinstance(body, dict) else {}
            symbol = str(body.get("asset") or legacy.get("asset") or "").upper()
            timeframe = str(body.get("timeframe") or legacy.get("timeframe") or "").upper()
        except (TypeError, ValueError, AttributeError):
            continue
        if kind == "INSTRUMENT_REGISTRATION":
            for key in by_symbol.get(symbol, []):
                result[key].append(str(event_id))
        elif (symbol, timeframe) in result:
            result[(symbol, timeframe)].append(str(event_id))
    for ids in result.values():
        ids.sort()
    return result


def render_lane_freshness_markdown(report: dict[str, object]) -> str:
    """Render the primary operational monitor as a compact factual table."""

    lines = [
        "# Lane Freshness Audit",
        "",
        f"Authority Generated: `{report['authority_generated']}`",
        "",
        f"Authority Revision: `{report['authority_revision']}`",
        "",
        f"Scheduler: `{report['scheduler']['state']}` — `{report['scheduler']['reason_code']}`",
        "",
        "| Lane | Currency | Expected Latest | Actual Latest | Lag | Reason |",
        "|---|---|---|---|---:|---|",
    ]
    for row in report["lanes"]:
        freshness = row["freshness"]
        lag = freshness["lag"]
        lag_text = "—" if lag["count"] is None else f"{lag['count']} {lag['unit']}"
        values = (
            row["lane"],
            freshness["state"],
            freshness["expected_latest"] or "—",
            freshness["latest_canonical_observation"] or "—",
            lag_text,
            row["reason"],
        )
        lines.append("| " + " | ".join(_markdown_cell(value) for value in values) + " |")
    lines.extend(
        [
            "",
            "The scheduler finding is repository/runtime evidence, not an inference from market timestamps. "
            "Lane currency itself is derived only from the approved operational calendar, timeframe, "
            "and latest canonical observation.",
            "",
        ]
    )
    return "\n".join(lines)


def _audit_lane(
    connection,
    *,
    symbol: str,
    timeframe: str,
    validation_summary: str | None,
    authority_generated: datetime,
    current_event_ids: list[str],
) -> dict[str, object]:
    freshness = assess_lane_freshness(
        connection,
        symbol=symbol,
        timeframe=timeframe,
        as_of=authority_generated,
    )
    revision = authority_revision_for_lane(
        connection, symbol=symbol, timeframe=timeframe, current_event_ids=current_event_ids
    )
    latest_run = connection.execute(
        """
        SELECT kind,status,started_at_utc,finished_at_utc,
               json_extract(detail,'$.provider'),
               coalesce(json_extract(detail,'$.inserted'),0),
               coalesce(json_extract(detail,'$.corrected'),0),
               coalesce(json_extract(detail,'$.unchanged'),0),
               coalesce(json_extract(detail,'$.rejected'),0)
        FROM ingest_runs
        WHERE json_extract(detail,'$.asset')=?
          AND json_extract(detail,'$.timeframe')=?
          AND kind LIKE 'provider_%'
        ORDER BY coalesce(finished_at_utc,started_at_utc) DESC LIMIT 1
        """,
        (symbol, timeframe),
    ).fetchone()
    if latest_run is None:
        provider_request = "NOT_OBSERVED"
        observation_advance = "NOT_OBSERVED"
        last_run = None
    else:
        provider_request = "SUCCEEDED" if latest_run[1] == "committed" else "FAILED"
        observation_advance = (
            "ADVANCED" if latest_run[5] + latest_run[6] > 0 else "UNCHANGED"
        )
        last_run = {
            "kind": latest_run[0],
            "status": latest_run[1],
            "started_at": latest_run[2],
            "finished_at": latest_run[3],
            "provider": latest_run[4],
            "inserted": latest_run[5],
            "corrected": latest_run[6],
            "unchanged": latest_run[7],
            "rejected": latest_run[8],
        }
    validation = json.loads(validation_summary) if validation_summary else None
    validation_state = _validation_state(validation)
    if freshness["state"] == "Behind":
        reason = "SCHEDULED_ACQUISITION_PENDING"
    elif freshness["state"] == "Unavailable":
        reason = freshness["reason_code"]
    else:
        reason = "CURRENT_AT_APPROVED_OPERATIONAL_EDGE"
    return {
        "lane": f"{symbol} {timeframe}",
        "symbol": symbol,
        "timeframe": timeframe,
        "latest_canonical_observation": freshness["latest_canonical_observation"],
        "authority_generated": authority_generated.isoformat(),
        "authority_revision": revision,
        "freshness": freshness,
        "validation": {"state": validation_state, "summary": validation},
        "expected_latest": freshness["expected_latest"],
        "actual_latest": freshness["latest_canonical_observation"],
        "lag": freshness["lag"],
        "reason": reason,
        "scheduled_acquisition_audit": {
            "scheduler_runs": "AVAILABLE_IN_SCHEDULER_JOURNAL",
            "operational_windows_respected": "CALENDAR_DERIVED",
            "provider_request": provider_request,
            "latest_canonical_observation_advance": observation_advance,
            "authority_publication": "ON_DEMAND_PUBLISHED",
            "last_recorded_provider_run": last_run,
        },
    }


def _validation_state(summary: dict[str, object] | None) -> str:
    if summary is None:
        return "NOT_MEASURED"
    outside = summary.get(
        "outside_expected_interval_count",
        summary.get("outside_expected_session_count", 0),
    )
    if summary.get("material_gap_count", 0) or outside:
        return "WARNING"
    return "PASS"


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
