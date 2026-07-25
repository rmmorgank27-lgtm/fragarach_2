"""Read-only-safe execution tracing for the one Scheduler authority.

Trace data is operational journal state.  It deliberately uses a fixed field
allow-list so provider credentials and request secrets cannot be persisted.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any


TRACE_CONTRACT = "fragarach_ii.execution_trace.v1"
CYCLE_CONTRACT = "fragarach_ii.scheduler_cycle.v1"
# These records live in the scheduler's hot-path JSON journal.  Keeping tens
# of thousands of rich diagnostic records makes every service heartbeat parse
# and rewrite tens of megabytes, which can starve normal lane dispatch.  The
# bounded tail below still gives operators enough recent, lane-level context
# while keeping the live control plane responsive.
TRACE_EVENT_LIMIT = 1_000
CYCLE_LIMIT = 250
TIMING_RECORD_LIMIT = 1_000
# The live journal is a control plane, not an unlimited audit store.  These
# lower hot-path limits retain enough context for the native monitor while
# preventing a long catch-up session from making every scheduler wake parse
# and rewrite megabytes of stale diagnostics.
HOT_TRACE_EVENT_LIMIT = 20
HOT_EVENT_LIMIT = 20
HOT_CYCLE_LIMIT = 10
HOT_TIMING_RECORD_LIMIT = 20
HOT_ROUTING_DECISION_LIMIT = 1
HOT_REQUEST_LIFECYCLE_LIMIT = 20
HOT_ARCHIVE_LIMIT = 20
HOT_MANUAL_HISTORY_LIMIT = 20
HOT_LANE_ATTEMPT_HISTORY_LIMIT = 1
HOT_LANE_PROVIDER_BOUNDARY_LIMIT = 1

_COMPACT_PROVIDER_ROW_FIELDS = (
    "provider", "eligible", "reason", "rejection_reason", "mapping_class",
    "mapping_status", "provider_symbol", "estimated_request_count", "result",
    "state", "inserted", "corrected", "publication_job_id",
)
_ARCHIVED_MANUAL_REQUEST_FIELDS = (
    "id", "symbol", "timeframe", "status", "reason", "archive_reason",
    "missing_start", "missing_end", "expected_canonical_edge", "created_at",
    "archived_at", "reconciled_at",
)

REQUIRED_EVENTS = (
    "QUEUE_CREATED", "PRIORITY_CALCULATED", "ELIGIBILITY_EVALUATED",
    "SELECTED", "DISPATCH_STARTED", "WORKER_ALLOCATED", "BUDGET_RESERVED",
    "PROVIDER_SELECTED", "REQUEST_STARTED", "RESPONSE_RECEIVED",
    "RAW_EVIDENCE_STORED", "INGESTION_COMPLETED",
    "CANONICAL_EDGE_EVALUATED", "CANONICAL_EDGE_ADVANCED",
    "PUBLICATION_COMPLETED", "QUEUE_COMPLETED", "LANE_CURRENT",
)

STOP_REASONS = {
    "NOT_ELIGIBLE", "NOT_SELECTED", "CYCLE_CAPACITY_EXHAUSTED",
    "WORKER_UNAVAILABLE", "BUDGET_UNAVAILABLE", "BUDGET_RESERVATION_FAILED",
    "PROVIDER_UNAVAILABLE", "PROVIDER_COOLDOWN", "DISPATCH_REJECTED",
    "REQUEST_NOT_STARTED", "REQUEST_TIMEOUT", "HTTP_ERROR", "EMPTY_RESPONSE",
    "INVALID_RESPONSE", "RAW_EVIDENCE_REJECTED", "INGESTION_FAILED",
    "CANONICAL_UNCHANGED", "PUBLICATION_FAILED", "QUEUE_COMPLETION_FAILED",
    "STALE_WRITER_REJECTED",
}

_BASE_FIELDS = {
    "trace_id", "lane_id", "symbol", "timeframe", "attempt_number", "event",
    "timestamp", "result", "reason_code", "duration_ms", "scheduler_cycle_id",
}
_DETAIL_FIELDS = {
    "provider", "requested_start", "requested_end", "http_status",
    "observations_received", "observations_admitted", "canonical_edge_before",
    "canonical_edge_after", "publication_edge", "queue_disposition",
    "current_stage", "retryable", "next_eligible_at", "worker_id",
    "dispatch_priority", "queue_id", "detail",
}
_ALLOWED_FIELDS = _BASE_FIELDS | _DETAIL_FIELDS

# This deliberately has a separate contract from state-transition events.
# A transition tells an operator *what* happened; a timing record tells them
# where wall time went without retaining request headers, credentials, or raw
# provider payloads.
TIMING_CONTRACT = "fragarach_ii.operation_timing.v1"
_TIMING_FIELDS = {
    "contract", "operation_id", "symbol", "timeframe", "intent", "provider",
    "step_name", "started_at", "ended_at", "duration_ms", "blocking_reason",
    "rows_read", "rows_written", "provider_calls", "publication_revision",
    # Phase 1 lane-throughput evidence.  These fields deliberately describe
    # scheduling boundaries only; raw provider request/response data remains
    # outside the operational journal.
    "queued_at", "provider_started_at", "provider_finished_at",
    "canonical_commit_started_at", "canonical_commit_finished_at",
    "completed_at", "duration_total_ms", "duration_provider_ms",
    "duration_locked_ms", "duration_publication_ms", "worker_id",
    "lock_wait_ms", "reservation_wait_ms",
    "trigger", "changed_lanes", "changed_symbols",
    "publication_revision_before", "publication_revision_after",
    "sync_blocking_ms", "async_duration_ms",
}


def compact_operational_history(journal: dict[str, Any]) -> bool:
    """Trim legacy oversized trace history before it reaches the hot path.

    Older journal versions used much larger limits.  Compacting on load makes
    the migration effective on the first normal save, without touching
    canonical evidence or any current queue/lane state.
    """

    changed = False
    for key, limit in (
        ("execution_trace_events", HOT_TRACE_EVENT_LIMIT),
        ("operation_timing_records", HOT_TIMING_RECORD_LIMIT),
        ("scheduler_cycles", HOT_CYCLE_LIMIT),
        ("routing_decisions", HOT_ROUTING_DECISION_LIMIT),
        ("request_lifecycle", HOT_REQUEST_LIFECYCLE_LIMIT),
        ("archived_operational_work", HOT_ARCHIVE_LIMIT),
    ):
        records = journal.get(key)
        if isinstance(records, list) and len(records) > limit:
            del records[:-limit]
            changed = True

    requests = journal.get("manual_requests")
    if isinstance(requests, list):
        # Actionable requests remain durable.  Completed/archived request
        # history is bounded because its detailed evidence already lives in
        # the immutable operational trace and authority stores.
        historical = [
            item for item in requests
            if isinstance(item, dict) and item.get("status") in {
                "Archived", "Resolved", "Dismissed",
            }
        ]
        if len(historical) > HOT_MANUAL_HISTORY_LIMIT:
            retained = historical[-HOT_MANUAL_HISTORY_LIMIT:]
            retained_ids = {id(item) for item in retained}
            journal["manual_requests"] = [
                item for item in requests
                if not isinstance(item, dict)
                or item.get("status") not in {"Archived", "Resolved", "Dismissed"}
                or id(item) in retained_ids
            ]
            changed = True
        for request in journal["manual_requests"]:
            if not isinstance(request, dict):
                continue
            if request.get("status") in {"Archived", "Resolved", "Dismissed"}:
                compact = {
                    key: request[key] for key in _ARCHIVED_MANUAL_REQUEST_FIELDS
                    if key in request
                }
                if compact != request:
                    request.clear()
                    request.update(compact)
                    changed = True
            elif _compact_provider_details(request):
                changed = True

    archive = journal.get("archived_operational_work")
    if isinstance(archive, list):
        for record in archive:
            if not isinstance(record, dict):
                continue
            # The envelope already contains the archive identifier, lane,
            # reason and timestamp.  Retaining a second full request/plan
            # payload here made the hot journal grow faster than the data it
            # was coordinating.
            if "payload" in record:
                record.pop("payload", None)
                changed = True

    lanes = journal.get("lanes")
    if isinstance(lanes, dict):
        for lane in lanes.values():
            if not isinstance(lane, dict):
                continue
            attempts = lane.get("attempt_history")
            if isinstance(attempts, list) and len(attempts) > HOT_LANE_ATTEMPT_HISTORY_LIMIT:
                del attempts[:-HOT_LANE_ATTEMPT_HISTORY_LIMIT]
                changed = True
            by_boundary = lane.get("provider_attempts_by_boundary")
            if isinstance(by_boundary, dict) and len(by_boundary) > HOT_LANE_PROVIDER_BOUNDARY_LIMIT:
                # Dict insertion order is the attempt order.  Retaining the
                # tail preserves the active/recent retry boundary without
                # carrying every completed M5 check forever.
                lane["provider_attempts_by_boundary"] = dict(
                    list(by_boundary.items())[-HOT_LANE_PROVIDER_BOUNDARY_LIMIT:]
                )
                changed = True
            if _compact_provider_details(lane):
                changed = True
            if _compact_last_operator_result(lane):
                changed = True

    reconciliation = journal.get("spec047_capability_reconciliation")
    if isinstance(reconciliation, dict) and isinstance(reconciliation.get("rows"), list):
        actionable = [
            row for row in reconciliation["rows"]
            if isinstance(row, dict) and row.get("required_operator_decision") != "NONE"
        ]
        if actionable != reconciliation["rows"]:
            reconciliation["rows"] = actionable
            reconciliation["compacted_to_actionable_rows"] = True
            changed = True
    return changed


def compact_hot_history_only(journal: dict[str, Any]) -> bool:
    """Bound append-only monitor histories on every scheduler save.

    This deliberately excludes lane and queue fields: those can be part of an
    in-flight retry decision and are compacted only during restart recovery.
    The records removed here have already been projected into the SQLite audit
    ledger by ``SchedulerJournal.save``.
    """

    changed = False
    for key, limit in _hot_history_limits():
        records = journal.get(key)
        if isinstance(records, list) and len(records) > limit:
            del records[limit:]
            changed = True
    return changed


def hot_history_needs_compaction(journal: dict[str, Any]) -> bool:
    """Whether an append-only monitor tail needs archival before persistence."""

    return any(
        isinstance(journal.get(key), list) and len(journal[key]) > limit
        for key, limit in _hot_history_limits()
    )


def _hot_history_limits() -> tuple[tuple[str, int], ...]:
    return (
        ("events", HOT_EVENT_LIMIT),
        ("execution_trace_events", HOT_TRACE_EVENT_LIMIT),
        ("operation_timing_records", HOT_TIMING_RECORD_LIMIT),
        ("scheduler_cycles", HOT_CYCLE_LIMIT),
        ("routing_decisions", HOT_ROUTING_DECISION_LIMIT),
        ("archived_operational_work", HOT_ARCHIVE_LIMIT),
    )


def _compact_provider_details(value: dict[str, Any]) -> bool:
    """Keep the routing decision, not repeated full capability projections."""
    changed = False
    for key in (
        "providers_considered", "providers_rejected", "providers_considered_at_creation",
        "providers_currently_eligible", "providers_currently_ineligible",
        "original_provider_facts", "original_rejection_reasons", "provider_results",
    ):
        rows = value.get(key)
        if not isinstance(rows, list):
            continue
        compact_rows = [
            {
                field: row[field] for field in _COMPACT_PROVIDER_ROW_FIELDS
                if field in row
            }
            if isinstance(row, dict) else row
            for row in rows
        ][:2]
        if compact_rows != rows:
            value[key] = compact_rows
            changed = True
    result = value.get("last_operator_fetch_result")
    if isinstance(result, dict) and _compact_provider_details(result):
        changed = True
    return changed


def _compact_last_operator_result(lane: dict[str, Any]) -> bool:
    result = lane.get("last_operator_fetch_result")
    if not isinstance(result, dict):
        return False
    keep = {
        "contract", "operation_id", "symbol", "timeframe", "work_class", "outcome",
        "reason", "completed_at", "canonical_edge_before", "canonical_edge_after",
        "expected_edge", "providers_attempted", "published_observations", "provider_results",
    }
    compact = {key: value for key, value in result.items() if key in keep}
    if compact == result:
        return False
    lane["last_operator_fetch_result"] = compact
    return True


def utc_text(value: datetime | None = None) -> str:
    observed = value or datetime.now(UTC)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    return observed.astimezone(UTC).isoformat()


def timing_record(
    *,
    operation_id: str,
    symbol: str | None,
    timeframe: str | None,
    intent: str,
    step_name: str,
    started_at: datetime,
    ended_at: datetime,
    provider: str | None = None,
    blocking_reason: str | None = None,
    rows_read: int | None = None,
    rows_written: int | None = None,
    provider_calls: int | None = None,
    publication_revision: str | None = None,
    queued_at: datetime | None = None,
    provider_started_at: datetime | None = None,
    provider_finished_at: datetime | None = None,
    canonical_commit_started_at: datetime | None = None,
    canonical_commit_finished_at: datetime | None = None,
    completed_at: datetime | None = None,
    duration_total_ms: float | None = None,
    duration_provider_ms: float | None = None,
    duration_locked_ms: float | None = None,
    duration_publication_ms: float | None = None,
    worker_id: str | None = None,
    lock_wait_ms: float | None = None,
    reservation_wait_ms: float | None = None,
    trigger: str | None = None,
    changed_lanes: list[str] | None = None,
    changed_symbols: list[str] | None = None,
    publication_revision_before: int | None = None,
    publication_revision_after: int | None = None,
    sync_blocking_ms: float | None = None,
    async_duration_ms: float | None = None,
) -> dict[str, Any]:
    """Build one operator-readable and redacted timing record.

    Callers may return the record in a command result or persist it in the
    scheduler journal through :func:`record_timing`.  Keeping construction
    side-effect free makes the same contract usable by manual ingestion.
    """

    started = utc_text(started_at)
    ended = utc_text(ended_at)
    duration = max(0.0, (ended_at.astimezone(UTC) - started_at.astimezone(UTC)).total_seconds() * 1000)
    value: dict[str, Any] = {
        "contract": TIMING_CONTRACT,
        "operation_id": operation_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "intent": intent,
        "provider": provider,
        "step_name": step_name,
        "started_at": started,
        "ended_at": ended,
        "duration_ms": round(duration, 3),
        "blocking_reason": blocking_reason,
        "rows_read": rows_read,
        "rows_written": rows_written,
        "provider_calls": provider_calls,
        "publication_revision": publication_revision,
        "queued_at": utc_text(queued_at) if queued_at else None,
        "provider_started_at": utc_text(provider_started_at) if provider_started_at else None,
        "provider_finished_at": utc_text(provider_finished_at) if provider_finished_at else None,
        "canonical_commit_started_at": (
            utc_text(canonical_commit_started_at) if canonical_commit_started_at else None
        ),
        "canonical_commit_finished_at": (
            utc_text(canonical_commit_finished_at) if canonical_commit_finished_at else None
        ),
        "completed_at": utc_text(completed_at) if completed_at else None,
        "duration_total_ms": duration_total_ms,
        "duration_provider_ms": duration_provider_ms,
        "duration_locked_ms": duration_locked_ms,
        "duration_publication_ms": duration_publication_ms,
        "worker_id": worker_id,
        "lock_wait_ms": lock_wait_ms,
        "reservation_wait_ms": reservation_wait_ms,
        "trigger": trigger,
        "changed_lanes": changed_lanes,
        "changed_symbols": changed_symbols,
        "publication_revision_before": publication_revision_before,
        "publication_revision_after": publication_revision_after,
        "sync_blocking_ms": sync_blocking_ms,
        "async_duration_ms": async_duration_ms,
    }
    return {key: value[key] for key in _TIMING_FIELDS if value.get(key) is not None}


def record_timing(journal: dict[str, Any], **details: Any) -> dict[str, Any]:
    """Append one bounded timing record to the durable scheduler journal."""

    # Match transition tracing's last-boundary redaction behavior: callers may
    # accidentally include a request detail, but only the timing contract can
    # cross into durable operator-visible state.
    record = timing_record(**{
        key: value for key, value in details.items()
        if key in _TIMING_FIELDS - {"contract"}
    })
    records = journal.setdefault("operation_timing_records", [])
    records.append(record)
    if len(records) > TIMING_RECORD_LIMIT:
        del records[:-TIMING_RECORD_LIMIT]
    return record


def ensure_trace_identity(
    item: dict[str, Any], *, lane_id: str, now: datetime,
    prior: dict[str, Any] | None = None,
) -> tuple[str, bool]:
    """Attach one stable trace identity, preserving it across queue-key changes."""

    source = prior or item
    trace_id = str(source.get("trace_id") or "")
    created = not trace_id
    if created:
        trace_id = str(uuid.uuid4())
    item["trace_id"] = trace_id
    item["attempt_number"] = int(source.get("attempt_number", 0) or 0)
    item["enqueued_at"] = source.get("enqueued_at") or utc_text(now)
    item["lane"] = lane_id
    return trace_id, created


def record_event(
    journal: dict[str, Any], item: dict[str, Any], event: str, *,
    cycle_id: str, result: str = "SUCCESS", reason_code: str | None = None,
    timestamp: datetime | None = None, duration_ms: float = 0.0, **details: Any,
) -> dict[str, Any]:
    """Append a chronological, redacted trace event to the operational journal."""

    lane_id = str(item.get("lane") or f"{item.get('symbol')}:{item.get('timeframe')}")
    symbol, _, timeframe = lane_id.partition(":")
    value: dict[str, Any] = {
        "trace_id": str(item["trace_id"]),
        "lane_id": lane_id,
        "symbol": str(item.get("symbol") or symbol),
        "timeframe": str(item.get("timeframe") or timeframe),
        "attempt_number": int(item.get("attempt_number", 0) or 0),
        "event": event,
        "timestamp": utc_text(timestamp),
        "result": result,
        "reason_code": reason_code,
        "duration_ms": round(max(0.0, float(duration_ms)), 3),
        "scheduler_cycle_id": cycle_id,
    }
    for key, detail in details.items():
        if key in _DETAIL_FIELDS and detail is not None:
            value[key] = detail
    # Rebuild through the allow-list even though callers are internal.  This is
    # the last boundary before journal persistence and guarantees redaction.
    value = {key: value.get(key) for key in _ALLOWED_FIELDS if key in value}
    events = journal.setdefault("execution_trace_events", [])
    events.append(value)
    if len(events) > TRACE_EVENT_LIMIT:
        del events[:-TRACE_EVENT_LIMIT]
    item["current_stage"] = event
    item["last_transition_at"] = value["timestamp"]
    if result == "SUCCESS":
        item["last_successful_stage"] = event
        item["stop_reason"] = None
    elif reason_code:
        item["stop_reason"] = reason_code
    return value


def record_stop(
    journal: dict[str, Any], item: dict[str, Any], *, cycle_id: str,
    current_stage: str, reason_code: str, retryable: bool,
    next_eligible_at: str | None = None, detail: str | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    return record_event(
        journal, item, "ATTEMPT_DEFERRED" if retryable else "ATTEMPT_FAILED",
        cycle_id=cycle_id, result="DEFERRED" if retryable else "FAILED",
        reason_code=reason_code, timestamp=timestamp, current_stage=current_stage,
        retryable=retryable, next_eligible_at=next_eligible_at, detail=detail,
        queue_disposition="RETAINED" if retryable else "REMOVED",
    )


def trace_for_lane(journal: dict[str, Any], symbol: str, timeframe: str) -> dict[str, Any]:
    lane_id = f"{symbol.strip().upper()}:{timeframe.strip().upper()}"
    queue = next((
        item for item in journal.get("acquisition_queue", [])
        if isinstance(item, dict) and item.get("lane") == lane_id
    ), None)
    lane_events = [
        event for event in journal.get("execution_trace_events", [])
        if isinstance(event, dict) and event.get("lane_id") == lane_id
    ]
    trace_id = str(queue.get("trace_id")) if queue and queue.get("trace_id") else (
        str(lane_events[-1]["trace_id"]) if lane_events else None
    )
    events = [event for event in lane_events if event.get("trace_id") == trace_id]
    lane = journal.get("lanes", {}).get(lane_id, {})
    first = events[0] if events else {}
    last = events[-1] if events else {}
    successful = [event for event in events if event.get("result") == "SUCCESS"]
    stop = next((event for event in reversed(events) if event.get("reason_code")), None)
    terminal_success = last.get("event") in {"QUEUE_COMPLETED", "LANE_CURRENT"}
    stop_reason = None if terminal_success else (
        queue.get("stop_reason") if queue and queue.get("stop_reason")
        else stop.get("reason_code") if stop else None
    )
    if queue:
        if queue.get("operational_state") == "Running" and queue.get("active_worker_id"):
            final_lane_state = "DOWNLOADING"
        elif stop_reason or queue.get("next_attempt"):
            final_lane_state = "BEHIND"
        else:
            final_lane_state = "QUEUED"
    else:
        final_lane_state = (
            lane.get("lifecycle_execution_state") or lane.get("queue_state")
            or lane.get("result")
        )
    queue_age = None
    enqueued_at = queue.get("enqueued_at") if queue else first.get("timestamp")
    if enqueued_at:
        try:
            queue_age = max(0.0, (datetime.now(UTC) - datetime.fromisoformat(str(enqueued_at))).total_seconds())
        except ValueError:
            pass
    return {
        "contract": TRACE_CONTRACT,
        "lane": lane_id,
        "trace_id": trace_id,
        "queue_age_seconds": queue_age,
        "current_stage": queue.get("current_stage") if queue else last.get("event"),
        "last_successful_stage": successful[-1].get("event") if successful else None,
        "stop_reason": stop_reason,
        "attempt_count": max((int(event.get("attempt_number", 0) or 0) for event in events), default=0),
        "provider": next((event.get("provider") for event in reversed(events) if event.get("provider")), lane.get("current_provider")),
        "canonical_edge_before": next((event.get("canonical_edge_before") for event in events if event.get("canonical_edge_before") is not None), None),
        "canonical_edge_after": next((event.get("canonical_edge_after") for event in reversed(events) if event.get("canonical_edge_after") is not None), None),
        "queue_disposition": last.get("queue_disposition") or ("ACTIVE" if queue else "REMOVED"),
        "final_lane_state": final_lane_state,
        "events": events,
    }


def oldest_queue_age(queue: list[dict[str, Any]], now: datetime) -> float | None:
    ages: list[float] = []
    for item in queue:
        try:
            queued = datetime.fromisoformat(str(item.get("enqueued_at")))
            if queued.tzinfo is None:
                queued = queued.replace(tzinfo=UTC)
            ages.append(max(0.0, (now.astimezone(UTC) - queued.astimezone(UTC)).total_seconds()))
        except (TypeError, ValueError):
            continue
    return max(ages) if ages else None


def append_cycle(journal: dict[str, Any], cycle: dict[str, Any]) -> None:
    cycle = {"contract": CYCLE_CONTRACT, **cycle}
    journal["last_completed_cycle"] = cycle
    cycles = journal.setdefault("scheduler_cycles", [])
    cycles.append(cycle)
    if len(cycles) > CYCLE_LIMIT:
        del cycles[:-CYCLE_LIMIT]


_PROGRESS_EVENTS = {
    "selection": {"SELECTED"},
    "provider_request": {"REQUEST_STARTED"},
    "provider_response": {"RESPONSE_RECEIVED"},
    "evidence_admission": {"RAW_EVIDENCE_STORED", "INGESTION_COMPLETED"},
    "canonical_publication": {"CANONICAL_EDGE_ADVANCED", "PUBLICATION_COMPLETED"},
    "queue_progress": {"QUEUE_COMPLETED", "LANE_CURRENT"},
}


def scheduler_progress_projection(
    journal: dict[str, Any], execution: dict[str, Any], now: datetime,
) -> dict[str, Any]:
    """Project liveness from durable progress without inventing queue authority."""

    events = [
        value for value in journal.get("execution_trace_events", [])
        if isinstance(value, dict)
    ]
    latest: dict[str, dict[str, Any] | None] = {}
    for name, names in _PROGRESS_EVENTS.items():
        latest[name] = next(
            (value for value in reversed(events) if value.get("event") in names), None
        )

    latest_by_trace: dict[str, dict[str, Any]] = {}
    for event in events:
        trace_id = str(event.get("trace_id") or "")
        if trace_id:
            latest_by_trace[trace_id] = event

    actionable: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for item in journal.get("acquisition_queue", []):
        if not isinstance(item, dict):
            continue
        state = str(item.get("operational_state") or item.get("state") or "Ready").upper()
        next_attempt = item.get("next_attempt")
        due = True
        if next_attempt:
            try:
                candidate = datetime.fromisoformat(str(next_attempt))
                if candidate.tzinfo is None:
                    candidate = candidate.replace(tzinfo=UTC)
                due = candidate.astimezone(UTC) <= now.astimezone(UTC)
            except ValueError:
                due = False
        terminal = latest_by_trace.get(str(item.get("trace_id") or ""), {})
        terminal_failure = (
            terminal.get("event") == "ATTEMPT_FAILED"
            and terminal.get("retryable") is False
        )
        if state in {"READY", "RUNNING", "DOWNLOADING"} and due and not terminal_failure:
            actionable.append(item)
        else:
            blocked.append(item)

    active_workers = int(execution.get("active_workers", 0) or 0)
    cycle_seconds = float(execution.get("duration_seconds", 0) or 0)
    # The window follows observed service/cycle cost and active capacity.  It is
    # deliberately not a fixed UI timer and never changes scheduling cadence.
    permitted_window = max(30.0, min(900.0, max(2.0 * cycle_seconds, 30.0) + 15.0 * max(1, active_workers)))
    meaningful = [value for value in latest.values() if value and value.get("timestamp")]
    last = max(meaningful, key=lambda value: str(value.get("timestamp")), default=None)
    progress_age = None
    if last:
        try:
            observed = datetime.fromisoformat(str(last["timestamp"]))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            progress_age = max(0.0, (now.astimezone(UTC) - observed.astimezone(UTC)).total_seconds())
        except ValueError:
            pass
    stalled = bool(actionable and not active_workers and (progress_age is None or progress_age > permitted_window))
    current = actionable[0] if actionable else blocked[0] if blocked else None
    current_trace = latest_by_trace.get(str(current.get("trace_id") or ""), {}) if current else {}

    return {
        "contract": "fragarach_ii.scheduler_progress.v1",
        "actionable_queue_depth": len(actionable),
        "blocked_queue_depth": len(blocked),
        "total_queue_depth": len(actionable) + len(blocked),
        "oldest_actionable_age_seconds": oldest_queue_age(actionable, now),
        "active_workers": active_workers,
        "available_workers": int(execution.get("available_workers", 0) or 0),
        "permitted_progress_window_seconds": permitted_window,
        "last_meaningful_progress": last.get("timestamp") if last else None,
        "last_meaningful_progress_age_seconds": progress_age,
        "stalled": stalled,
        "current_lane": current.get("lane") if current else None,
        "current_trace_id": current.get("trace_id") if current else None,
        "current_stage": current.get("current_stage") if current else current_trace.get("event"),
        "current_stop_reason": current.get("stop_reason") if current else current_trace.get("reason_code"),
        **{
            f"last_{name}": value.get("timestamp") if value else None
            for name, value in latest.items()
        },
    }
