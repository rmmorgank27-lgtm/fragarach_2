"""Calendar-driven scheduled acquisition and native monitor contract."""

from __future__ import annotations

import json
import math
import os
import fcntl
import hashlib
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .calendars import CalendarRegistry, ConfigurationError
from .freshness import (
    FRESHNESS_CONTRACT,
    assess_lane_freshness,
    authority_revision_for_lane,
    normalized_utc,
)
from .history_depth import governed_d1_initial_start
from .lane_freshness_service import lane_freshness_report
from .operational_schedule import latest_closed_session_date, schedule_for_lane
from .lane_update_register import LaneUpdateRegister, REGISTER_CONTRACT
from .estate_audit import audit_status, run_estate_audit
from .acquisition_orchestrator import (
    acquisition_capability_projection,
    cached_acquisition_capability_projection,
    acquisition_plan,
    build_rate_budgets,
    classify_failure,
    capability_reconciliation_report,
    create_manual_request,
    credential_map,
    dismiss_manual_request,
    load_provider_profiles,
    provider_monitor_rows,
    resolve_satisfied_manual_requests,
    update_provider_health,
)
from .providers.orchestrated import acquire_from_provider
from .providers.twelve_data import AcquisitionError
from .execution_trace import (
    append_cycle,
    compact_hot_history_only,
    compact_operational_history,
    ensure_trace_identity,
    oldest_queue_age,
    hot_history_needs_compaction,
    record_event,
    record_stop,
    record_timing,
    scheduler_progress_projection,
    trace_for_lane,
)
from .scheduler_integrity import (
    ACTIONABLE_REQUEST_STATES,
    active_universe,
    create_pause,
    effective_pause_sources,
    reconcile_operational_state,
    recover_stale_reservations,
    refresh_pause_states,
    request_lifecycle_counts,
    resume_pause,
)
from .lane_commissioning import (
    commissioned_lane_keys,
    ensure_commissioned_lane,
    ensure_manual_acquisition_lane,
    resolved_calendar_id,
)
from .provider_facts import load_provider_facts, provider_facts_path
from .adaptive_scheduler import (
    POLICIES,
    calculate_throughput,
    normalize_policy,
    policy_label,
    time_triggered_pacing,
)
from .commissioning_authority import (
    operational_market_rank,
    project_required_lanes,
    required_timeframes,
)
from .storage import open_read_only
from .scheduler_state_store import SchedulerStateStore
from .validation.intraday_profiles import expected_opens, profile_for
from .publication_service import (
    enqueue_publication,
    lane_publication_detail,
    publication_path,
    publication_state,
    resume_pending_publications,
    retry_publication,
)


SCHEDULER_CONTRACT = "fragarach_ii.scheduler_monitor.v2"
SCHEDULER_JOURNAL_CONTRACT = "fragarach_ii.scheduler_journal.v4"
SCHEDULER_JOURNAL_V3_CONTRACT = "fragarach_ii.scheduler_journal.v3"
SCHEDULER_JOURNAL_V2_CONTRACT = "fragarach_ii.scheduler_journal.v2"
SCHEDULER_JOURNAL_V1_CONTRACT = "fragarach_ii.scheduler_journal.v1"
_EVENT_LIMIT = 200
MANUAL_RECONCILIATION_CONTRACT = "fragarach_ii.manual_request_reconciliation.v1"
MANUAL_RECONCILIATION_OUTCOMES = {
    "AUTOMATION_RESTORED", "REQUEST_ALREADY_SATISFIED",
    "STILL_NO_ELIGIBLE_PROVIDER", "AUTOMATION_TEMPORARILY_BLOCKED",
    "INSTRUMENT_NO_LONGER_ACTIVE", "LANE_NO_LONGER_COMMISSIONED",
    "REQUEST_DISMISSED",
}
RECONCILABLE_REQUEST_STATES = ACTIONABLE_REQUEST_STATES | {"Waiting"}

# A full scheduler snapshot reconciles the estate and executes SQLite JSON
# projections.  It is intentionally authoritative, but repeating it for a
# past-due manual queue item that cannot dispatch burns multiple cores without
# advancing the queue.  The idle gate polls only authority file revisions and
# is always interrupted by the native command-channel wake event.
_IDLE_NO_WORK_RECONCILIATION_SECONDS = 300.0
_IDLE_INPUT_POLL_SECONDS = 5.0
_DISPATCH_LIVENESS_SECONDS = 5.0
_CATCH_UP_WAKE_SECONDS = 1.0

# The Scheduler is the only normal acquisition authority, but its worker pool
# can legitimately be asked for the same lane twice by two command paths in a
# single process.  Keep the exclusion narrow: different timeframes (including
# those for the same symbol) are independent, while one lane has one writer.
_ACTIVE_LANE_GUARDS: set[tuple[str, str, str]] = set()
_ACTIVE_LANE_GUARDS_LOCK = threading.Lock()


class _DispatchPaused(RuntimeError):
    pass


def _claim_lane_execution(database_path: str | Path, symbol: str, timeframe: str) -> bool:
    key = (str(Path(database_path).expanduser().resolve()), symbol, timeframe)
    with _ACTIVE_LANE_GUARDS_LOCK:
        if key in _ACTIVE_LANE_GUARDS:
            return False
        _ACTIVE_LANE_GUARDS.add(key)
        return True


def _release_lane_execution(database_path: str | Path, symbol: str, timeframe: str) -> None:
    key = (str(Path(database_path).expanduser().resolve()), symbol, timeframe)
    with _ACTIVE_LANE_GUARDS_LOCK:
        _ACTIVE_LANE_GUARDS.discard(key)


class SchedulerJournal:
    def __init__(self, database_path: str | Path, path: str | Path | None = None) -> None:
        database = Path(database_path).expanduser().resolve()
        self.path = Path(path) if path else Path(f"{database}.scheduler.json")
        self.store = SchedulerStateStore(database, self.path)
        self.store.ensure()
        self.migration_pending = False
        self._audit_backfill: dict[str, object] | None = None
        self.data = self._load()

    def lane(self, symbol: str, timeframe: str) -> dict[str, object]:
        key = f"{symbol}:{timeframe}"
        lanes = self.data.setdefault("lanes", {})
        return lanes.setdefault(key, {})

    @property
    def providers(self) -> dict[str, object]:
        return self.data.setdefault("providers", {})

    @property
    def manual_requests(self) -> list[dict[str, object]]:
        return self.data.setdefault("manual_requests", [])

    def record_routing(self, plan: dict[str, object]) -> None:
        decisions = self.data.setdefault("routing_decisions", [])
        decisions.insert(0, plan)
        del decisions[_EVENT_LIMIT:]

    def append_event(self, event: dict[str, object]) -> None:
        events = self.data.setdefault("events", [])
        events.insert(0, event)
        del events[_EVENT_LIMIT:]

    def save(self) -> None:
        """Commit live scheduler state to SQLite and write only a JSON pointer.

        Scheduler and manual-import mutations share the registered SQLite
        writer.  The file remains for compatibility and service discovery, but
        it is no longer the mutable scheduling authority.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            current = self.store.load() or {}
            self._merge_external_controls(current)
            self.data["journal_revision"] = max(
                int(self.data.get("journal_revision", 0) or 0),
                int(current.get("journal_revision", 0) or 0),
            ) + 1
            audit_state = self._audit_backfill
            if audit_state is None and hot_history_needs_compaction(self.data):
                # The hot control tail is safe to trim at every save.  Preserve
                # the pre-trim document so SQLite receives every completed
                # event rather than the scheduler carrying it indefinitely.
                audit_state = json.loads(json.dumps(self.data))
                compact_hot_history_only(self.data)
            revision = self.store.save(self.data, audit_state=audit_state)
            self._audit_backfill = None
            payload = json.dumps({
                "contract": "fragarach_ii.scheduler_journal_pointer.v1",
                "storage": "SQLITE",
                "state_key": self.store.state_key,
                "journal_revision": revision,
                "updated_at_utc": datetime.now(UTC).isoformat(),
            }, sort_keys=True, separators=(",", ":")) + "\n"
            descriptor, temporary = tempfile.mkstemp(
                prefix=f".{self.path.name}.", dir=self.path.parent
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            except BaseException:
                Path(temporary).unlink(missing_ok=True)
                raise
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _merge_external_controls(self, current: dict[str, object] | None = None) -> None:
        if current is None:
            current = self.store.load()
        if not isinstance(current, dict):
            # Direct file edits remain readable for one compatibility release.
            try:
                current = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError, AttributeError):
                return
        if not isinstance(current, dict):
            return
        current_manual_generation = int(current.get("manual_reconciliation_generation", 0) or 0)
        own_manual_generation = int(self.data.get("manual_reconciliation_generation", 0) or 0)
        if current_manual_generation > own_manual_generation:
            self.data["manual_reconciliation_generation"] = current_manual_generation
            for key in (
                "manual_request_reconciliation", "manual_request_migration_report",
                "current_provider_fact_revision", "current_capability_projection_revision",
            ):
                if key in current:
                    self.data[key] = current[key]
            external_requests_by_id = {
                str(item.get("id")): item for item in current.get("manual_requests", [])
                if isinstance(item, dict) and item.get("id")
            }
            own_requests_by_id = {
                str(item.get("id")): item for item in self.data.setdefault("manual_requests", [])
                if isinstance(item, dict) and item.get("id")
            }
            own_requests_by_id.update(external_requests_by_id)
            self.data["manual_requests"] = list(own_requests_by_id.values())
            self.data["acquisition_queue"] = list(current.get("acquisition_queue", []))
        current_generation = int(current.get("dispatch_generation", 0))
        own_generation = int(self.data.get("dispatch_generation", 0))
        if current_generation <= own_generation:
            return
        self.data["dispatch_generation"] = current_generation
        for key in (
            "scheduler_policy", "queue_control_updated_at", "run_queue_requested_at",
            "active_universe_revision",
        ):
            if key in current:
                self.data[key] = current[key]
        own_lanes = self.data.setdefault("lanes", {})
        for lane_id, external in current.get("lanes", {}).items():
            if not isinstance(external, dict):
                continue
            lane = own_lanes.setdefault(lane_id, {})
            if external.get("operator_retry_pending") or external.get("operator_fetch_pending"):
                for key in (
                    "operator_retry_pending", "operator_retry_requested_at",
                    "operator_fetch_pending",
                    "queue_state", "reason", "provider_attempts_by_boundary",
                ):
                    if key in external:
                        lane[key] = external[key]
            elif current.get("run_queue_requested_at"):
                lane["provider_attempts_by_boundary"] = external.get("provider_attempts_by_boundary", {})
                if external.get("queue_state") == "Ready":
                    lane["queue_state"] = "Ready"
        external_queue = {
            str(item.get("lane")): item for item in current.get("acquisition_queue", [])
            if isinstance(item, dict) and item.get("lane")
        }
        for item in self.data.get("acquisition_queue", []):
            external = external_queue.get(str(item.get("lane")))
            if external and external.get("operational_state") == "Ready":
                for key in (
                    "work_class", "operational_state", "queue_reason",
                    "waiting_reason", "next_attempt", "budget_wait",
                ):
                    if key in external:
                        item[key] = external[key]
        external_requests = {
            str(item.get("id")): item for item in current.get("manual_requests", [])
            if isinstance(item, dict) and item.get("id")
        }
        for request in self.data.get("manual_requests", []):
            external = external_requests.get(str(request.get("id")))
            if external:
                for key in ("retry_requested_at", "automated_recheck_requested_at", "status", "acknowledged_at", "dismissed_at"):
                    if key in external:
                        request[key] = external[key]
        own_pauses = {
            str(item.get("pause_identifier")): item for item in self.data.setdefault("pause_records", [])
            if isinstance(item, dict) and item.get("pause_identifier")
        }
        for external in current.get("pause_records", []):
            if not isinstance(external, dict) or not external.get("pause_identifier"):
                continue
            identifier = str(external["pause_identifier"])
            if identifier in own_pauses:
                own_pauses[identifier].update(external)
            else:
                own_pauses[identifier] = external
        self.data["pause_records"] = list(own_pauses.values())

    def _load(self) -> dict[str, object]:
        value = self.store.load()
        try:
            if value is None:
                value = json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("contract") in {
                SCHEDULER_JOURNAL_CONTRACT,
                SCHEDULER_JOURNAL_V3_CONTRACT,
                SCHEDULER_JOURNAL_V2_CONTRACT,
                SCHEDULER_JOURNAL_V1_CONTRACT,
            }:
                prior_contract = value.get("contract")
                value["contract"] = SCHEDULER_JOURNAL_CONTRACT
                self.migration_pending = (
                    prior_contract != SCHEDULER_JOURNAL_CONTRACT
                    or self.store.load() is None
                )
                value.setdefault("providers", {})
                value.setdefault("routing_decisions", [])
                value.setdefault("manual_requests", [])
                value.setdefault("acquisition_queue", [])
                if "scheduler_policy" not in value:
                    try:
                        legacy = int(value.get("queue_bandwidth", 80) or 80)
                    except (TypeError, ValueError):
                        legacy = 80
                    value["scheduler_policy"] = (
                        "CONSERVATIVE" if legacy < 55 else
                        "BALANCED" if legacy < 78 else
                        "HIGH_THROUGHPUT" if legacy < 90 else
                        "MAXIMUM_CATCH_UP"
                    )
                if value.get("scheduler_policy") == "HIGH_THROUGHPUT":
                    value["scheduler_policy"] = "MAXIMUM_CATCH_UP"
                    self.migration_pending = True
                value.pop("queue_bandwidth", None)
                value.setdefault("last_dispatch", None)
                value.setdefault("archived_operational_work", [])
                value.setdefault("request_lifecycle", [])
                value.setdefault("execution_trace_events", [])
                value.setdefault("operation_timing_records", [])
                value.setdefault("scheduler_cycles", [])
                value.setdefault("last_completed_cycle", None)
                value.setdefault("pause_records", [])
                value.setdefault("journal_revision", 0)
                value.setdefault("manual_reconciliation_generation", 0)
                if prior_contract != SCHEDULER_JOURNAL_CONTRACT and not value["request_lifecycle"]:
                    for state in value["providers"].values():
                        if isinstance(state, dict) and state.get("rate_events"):
                            state["legacy_unclassified_budget_events"] = state.get("rate_events")
                            state["rate_events"] = []
                            state["active_reservations"] = []
                for item in value["acquisition_queue"]:
                    if not isinstance(item, dict):
                        continue
                    item.setdefault("work_class", "QUEUE")
                    item.setdefault("operational_state", "Ready")
                    item.setdefault("enqueued_at", item.get("created_at"))
                    if item.get("operational_state") == "Running":
                        item["operational_state"] = "Ready"
                        item["queue_reason"] = "Interrupted work recovered after restart"
                        item["waiting_reason"] = None
                        item.pop("active_worker_id", None)
                        item["recovered_after_restart"] = True
                        self.migration_pending = True
                # Preserve completed operational history in SQLite before its
                # live control-plane representation is reduced to a small,
                # restart-safe tail.  A JSON round-trip avoids aliases while
                # deliberately keeping this one-off migration independent of
                # scheduler execution objects.
                audit_before_compaction = json.loads(json.dumps(value))
                if compact_operational_history(value):
                    self._audit_backfill = audit_before_compaction
                    self.migration_pending = True
                return value
        except (OSError, ValueError, AttributeError):
            pass
        return {
            "contract": SCHEDULER_JOURNAL_CONTRACT,
            "lanes": {}, "events": [], "providers": {},
            "routing_decisions": [], "manual_requests": [], "acquisition_queue": [],
            "archived_operational_work": [], "request_lifecycle": [], "pause_records": [],
            "execution_trace_events": [], "scheduler_cycles": [], "last_completed_cycle": None,
            "scheduler_policy": "BALANCED", "last_dispatch": None,
            "journal_revision": 0, "manual_reconciliation_generation": 0,
        }


def reconcile_manual_requests(
    database_path: str | Path,
    *,
    credential: str | None = None,
    journal_path: str | Path | None = None,
    at: datetime | None = None,
    trigger: str = "SCHEDULER",
) -> dict[str, object]:
    """Re-evaluate unresolved manual fallback under the Scheduler mutation lock."""

    journal = SchedulerJournal(database_path, journal_path)
    execution_lock = journal.path.with_suffix(f"{journal.path.suffix}.acquisition.lock")
    execution_lock.parent.mkdir(parents=True, exist_ok=True)
    with execution_lock.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            journal = SchedulerJournal(database_path, journal_path)
            result = _reconcile_manual_requests_loaded(
                database_path, journal, normalized_utc(at), credential=credential,
                trigger=trigger,
            )
            if result["changed"]:
                journal.save()
            return result["report"]
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _has_approved_initial_route(providers: list[dict[str, object]]) -> bool:
    """Whether a no-evidence lane still has a governed fetch route to retry."""
    return any(
        str(item.get("mapping_class") or "") in {
            "EXACT_REPRESENTATION",
            "APPROVED_PROVIDER_ALIAS",
            "APPROVED_EQUIVALENT_REPRESENTATION",
        }
        and item.get("provider_symbol")
        for item in providers
        if isinstance(item, dict)
    )


def _reconcile_manual_requests_loaded(
    database_path: str | Path,
    journal: SchedulerJournal,
    observed: datetime,
    *,
    credential: str | None,
    trigger: str,
    profiles=None,
    budgets=None,
) -> dict[str, object]:
    profiles = tuple(profiles or load_provider_profiles())
    credentials = credential_map(credential)
    if _repair_twelve_data_credential_health(database_path, journal.providers, credentials):
        pass
    selected_budgets = budgets or build_rate_budgets(
        profiles, journal.providers, wall_clock=lambda: observed, credential=credential,
    )
    operational = reconcile_operational_state(database_path, journal.data, at=observed)
    universe = operational["universe"]
    provider_facts = load_provider_facts(database_path)
    provider_revision = int(provider_facts.get("revision", 0) or 0)
    capability_revision = _manual_capability_revision(
        provider_revision, profiles, journal.providers, credentials, universe
    )
    queue_percentage = _queue_percentage(journal)
    protected_demand = _scheduled_demand_forecast(database_path, profiles, observed, journal)
    queue_source = [
        item for item in journal.data.setdefault("acquisition_queue", [])
        if isinstance(item, dict) and item.get("lane")
    ]
    queue_by_lane = {
        str(item.get("lane")): item
        for item in queue_source
    }
    counters = {
        "requests_examined": 0, "requests_already_current": 0,
        "automation_restored": 0, "already_satisfied": 0,
        "still_genuinely_manual": 0, "temporarily_blocked": 0,
        "inactive_or_uncommissioned_archived": 0, "queue_items_created": 0,
        "duplicate_queue_items_prevented": 0,
    }
    counters["duplicate_queue_items_prevented"] = len(queue_source) - len(queue_by_lane)
    changed = bool(operational["changed"]) or bool(counters["duplicate_queue_items_prevented"])

    for request in journal.manual_requests:
        if not isinstance(request, dict):
            continue
        if request.get("status") == "Dismissed" and not request.get("reconciliation_status"):
            request.update(
                reconciliation_status="REQUEST_DISMISSED",
                reconciliation_reason="REQUEST_DISMISSED",
                last_evaluated_at=observed.isoformat(), actionable=False,
            )
            changed = True
            continue
        if request.get("status") not in RECONCILABLE_REQUEST_STATES:
            continue
        counters["requests_examined"] += 1
        before = json.dumps(request, sort_keys=True, default=str)
        _preserve_manual_request_creation(request)
        lane_id = f"{request.get('symbol')}:{request.get('timeframe')}"
        symbol, timeframe = str(request.get("symbol")), str(request.get("timeframe"))
        authority = universe["active_lanes"].get(lane_id)
        if authority is None:
            symbol_active = any(
                item.get("symbol") == symbol for item in universe["active_lanes"].values()
            )
            outcome = "LANE_NO_LONGER_COMMISSIONED" if symbol_active else "INSTRUMENT_NO_LONGER_ACTIVE"
            _archive_reconciled_request(journal, request, lane_id, outcome, observed)
            _finish_manual_evaluation(
                request, provider_revision, capability_revision,
                hashlib.sha256(f"{provider_revision}:{capability_revision}:{outcome}".encode()).hexdigest(),
                observed,
            )
            counters["inactive_or_uncommissioned_archived"] += 1
            queue_by_lane.pop(lane_id, None)
            changed = True
            continue

        with open_read_only(database_path) as connection:
            freshness = assess_lane_freshness(
                connection, symbol=symbol, timeframe=timeframe, as_of=observed
            )
            lane_revision = authority_revision_for_lane(
                connection, symbol=symbol, timeframe=timeframe
            )
        expected_edge = freshness.get("expected_latest")
        current_evaluation = hashlib.sha256(json.dumps({
            "provider": provider_revision, "capability": capability_revision,
            "lane": lane_revision, "status": request.get("status"),
            "minute": observed.replace(second=0, microsecond=0).isoformat()
            if request.get("status") == "Waiting" else None,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if request.get("last_evaluation_revision") == current_evaluation and trigger == "SNAPSHOT":
            counters["requests_already_current"] += 1
            continue

        requested_edge = request.get("expected_canonical_edge")
        if _canonical_reaches_requested_edge(
            freshness.get("latest_canonical_observation"), requested_edge
        ) or (not requested_edge and freshness.get("state") == "Current"):
            request.update(
                status="Resolved", resolved_at=observed.isoformat(), actionable=False,
                reconciliation_status="REQUEST_ALREADY_SATISFIED",
                reconciliation_reason="Canonical evidence satisfies the current expected edge",
                reconciled_at=observed.isoformat(), replacement_queue_identifier=None,
            )
            _finish_manual_evaluation(
                request, provider_revision, capability_revision, current_evaluation, observed
            )
            queue_by_lane.pop(lane_id, None)
            journal.lane(symbol, timeframe).update(
                queue_state=None, result="SATISFIED", reason=None, manual_request=None
            )
            counters["already_satisfied"] += 1
            changed = True
            continue

        if not expected_edge:
            state, detail = "Blocked", "Expected canonical edge is temporarily unavailable"
            plan = {"providers_considered": [], "eligible_providers": [], "selected_provider": None,
                    "estimated_request_count": 0, "missing_range": {"start": request.get("missing_start"), "end": request.get("missing_end")}}
        else:
            try:
                missing_start, missing_end = _acquisition_bounds(
                    database_path, symbol, timeframe, observed
                )
            except ValueError:
                state, detail = "Blocked", "Expected canonical edge is temporarily unavailable"
                plan = {"providers_considered": [], "eligible_providers": [], "selected_provider": None,
                        "estimated_request_count": 0, "missing_range": {"start": request.get("missing_start"), "end": request.get("missing_end")}}
            else:
                plan = acquisition_plan(
                    database_path, symbol=symbol, timeframe=timeframe,
                    canonical_edge=freshness.get("latest_canonical_observation"),
                    expected_edge=str(expected_edge), missing_start=missing_start,
                    missing_end=missing_end,
                    scheduled_boundary=f"RECONCILED:{expected_edge}", profiles=profiles,
                    provider_state=journal.providers, budgets=selected_budgets,
                    credentials=credentials, now=observed, work_class="QUEUE",
                    queue_percentage=queue_percentage, protected_demand=protected_demand,
                    attempted_providers=(
                        set()
                        if freshness.get("latest_canonical_observation") is None
                        or request.get("created_provider_fact_revision") != provider_revision
                        or request.get("created_capability_projection_revision") != capability_revision
                        else set(str(item) for item in request.get("providers_attempted", []))
                    ),
                )
                state = detail = None

        request.update(
            missing_start=plan["missing_range"].get("start") or request.get("missing_start"),
            missing_end=plan["missing_range"].get("end") or request.get("missing_end"),
            expected_canonical_edge=expected_edge or request.get("expected_canonical_edge"),
            providers_considered=list(plan.get("providers_considered", [])),
            providers_rejected=[
                item for item in plan.get("providers_considered", []) if not item.get("eligible")
            ],
            providers_currently_eligible=list(plan.get("eligible_providers", [])),
            providers_currently_ineligible=[
                item for item in plan.get("providers_considered", []) if not item.get("eligible")
            ],
        )
        pauses = effective_pause_sources(
            journal.data, symbol=symbol, group=str(authority["group"])
        )
        if pauses:
            state, detail = "Paused", "Paused by operator"
        temporary = _manual_temporary_block(plan, journal.providers)
        if state is None and temporary:
            state, detail = temporary

        if plan.get("selected_provider") and not pauses:
            queue_id, duplicate = _restore_manual_queue(
                queue_by_lane, request, plan, observed,
                state="Ready", reason="Automation restored from current provider facts",
            )
            request.update(
                status="Archived", actionable=False, archive_reason="AUTOMATION_RESTORED",
                archived_at=observed.isoformat(), reconciled_at=observed.isoformat(),
                reconciliation_status="AUTOMATION_RESTORED",
                reconciliation_reason=f"Automation restored through {plan['selected_provider']}",
                replacement_queue_identifier=queue_id,
                recommended_operator_action="NONE",
            )
            _archive_manual_history(journal, request, lane_id, "AUTOMATION_RESTORED", observed)
            lane = journal.lane(symbol, timeframe)
            lane.pop("last_scheduled_acquisition", None)
            lane.update(
                queue_state="Ready", result="WAITING",
                reason="Automation restored from current provider facts",
                manual_request=None, providers_considered=plan["providers_considered"],
                providers_rejected=request["providers_rejected"],
                routing_decision=plan.get("selection_reason"),
                provider_attempts_by_boundary={},
            )
            journal.append_event({
                "id": f"manual-reconciliation-{request.get('id')}",
                "at": observed.isoformat(), "symbol": symbol, "timeframe": timeframe,
                "result": "AUTOMATION_RESTORED", "observations": 0,
                "duration_seconds": 0.0,
                "reason": f"Automation restored through {plan['selected_provider']}; queued for acquisition",
            })
            counters["automation_restored"] += 1
            counters["queue_items_created"] += 0 if duplicate else 1
            counters["duplicate_queue_items_prevented"] += 1 if duplicate else 0
        elif state is not None:
            queue_id, duplicate = _restore_manual_queue(
                queue_by_lane, request, plan, observed, state=state, reason=str(detail)
            )
            request.update(
                status="Waiting", actionable=False,
                reconciliation_status="AUTOMATION_TEMPORARILY_BLOCKED",
                reconciliation_reason=detail, reconciled_at=observed.isoformat(),
                replacement_queue_identifier=queue_id,
                recommended_operator_action=_temporary_operator_action(state),
            )
            journal.lane(symbol, timeframe).update(
                queue_state=state, result="WAITING", reason=detail, manual_request=None,
                providers_considered=plan.get("providers_considered", []),
                providers_rejected=request["providers_rejected"],
            )
            counters["temporarily_blocked"] += 1
            counters["queue_items_created"] += 0 if duplicate else 1
            counters["duplicate_queue_items_prevented"] += 1 if duplicate else 0
        else:
            prior_status = request.get("status")
            request.update(
                status="Acknowledged" if prior_status == "Acknowledged" else "Required",
                actionable=True, reason="NO_ELIGIBLE_PROVIDER",
                reconciliation_status="STILL_NO_ELIGIBLE_PROVIDER",
                reconciliation_reason="NO_ELIGIBLE_PROVIDER",
                recommended_operator_action=(
                    "FETCH_INITIAL_HISTORY"
                    if freshness.get("latest_canonical_observation") is None
                    and _has_approved_initial_route(plan.get("providers_considered", []))
                    else "IMPORT_REVIEWED_MANUAL_EVIDENCE"
                ),
                replacement_queue_identifier=None,
            )
            queue_by_lane.pop(lane_id, None)
            journal.lane(symbol, timeframe).update(
                queue_state=None, result="FAILED", reason="NO_ELIGIBLE_PROVIDER",
                manual_request=request.get("id"),
                providers_considered=plan.get("providers_considered", []),
                providers_rejected=request["providers_rejected"],
            )
            counters["still_genuinely_manual"] += 1

        _finish_manual_evaluation(
            request, provider_revision, capability_revision, current_evaluation, observed
        )
        changed = changed or before != json.dumps(request, sort_keys=True, default=str)

    journal.data["acquisition_queue"] = list(queue_by_lane.values())
    report = {
        "contract": MANUAL_RECONCILIATION_CONTRACT,
        "trigger": trigger, "reconciled_at": observed.isoformat(),
        "provider_fact_revision": provider_revision,
        "capability_projection_revision": capability_revision,
        **counters,
    }
    journal.data["current_provider_fact_revision"] = provider_revision
    journal.data["current_capability_projection_revision"] = capability_revision
    journal.data["manual_request_reconciliation"] = report
    if not journal.data.get("manual_request_migration_report"):
        journal.data["manual_request_migration_report"] = dict(report)
        changed = True
    if changed:
        journal.data["manual_reconciliation_generation"] = int(
            journal.data.get("manual_reconciliation_generation", 0) or 0
        ) + 1
    return {"changed": changed, "report": report}


def _manual_capability_revision(provider_revision, profiles, provider_state, credentials, universe):
    state = {
        profile.provider: {
            key: (
                provider_state.get(profile.provider, {}).get(key)
                if key != "health" or provider_state.get(profile.provider, {}).get(key) in {
                    "Credential Missing", "Authentication Blocked", "Authentication Failed", "Entitlement Blocked",
                    "Maintenance", "Unavailable",
                }
                else "AVAILABLE"
            )
            for key in ("health", "cooldown_until")
        }
        for profile in profiles
    }
    payload = {
        "provider_fact_revision": provider_revision,
        "profiles": [repr(item) for item in profiles],
        "provider_state": state,
        "credentials": sorted(credentials),
        "universe_revision": universe["revision"],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _canonical_reaches_requested_edge(canonical_edge, requested_edge):
    if not canonical_edge or not requested_edge:
        return False
    try:
        canonical = datetime.fromisoformat(str(canonical_edge))
        requested = datetime.fromisoformat(str(requested_edge))
    except ValueError:
        return False
    if canonical.tzinfo is None:
        canonical = canonical.replace(tzinfo=UTC)
    if requested.tzinfo is None:
        requested = requested.replace(tzinfo=UTC)
    return canonical.astimezone(UTC) >= requested.astimezone(UTC)


def _as_utc_datetime(value: object) -> datetime | None:
    """Parse a journal timestamp for optional timing evidence."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _canonical_edge_advanced(before, after):
    if after is None:
        return False
    if before is None:
        return True
    try:
        prior = datetime.fromisoformat(str(before))
        current = datetime.fromisoformat(str(after))
    except ValueError:
        return str(after) != str(before)
    if prior.tzinfo is None:
        prior = prior.replace(tzinfo=UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(UTC) > prior.astimezone(UTC)


def _completion_edge(work, bounds, expected_edge):
    """Return the edge that completes this queue item, not the estate target."""
    if work.get("work_class") != "OPERATOR_FETCH":
        return expected_edge
    if str(work.get("timeframe")) == "D1":
        return f"{date.fromisoformat(str(bounds[1])).isoformat()}T00:00:00+00:00"
    if str(work.get("operator_fetch_mode") or "").lower() == "initial":
        return expected_edge
    # Intraday operator ranges are date-bounded while canonical edges are exact
    # interval closes. Any factual edge advancement completes the explicit
    # historical operation; routine Scheduler work remains responsible for the
    # current expected boundary.
    return work.get("canonical_edge") or expected_edge


def _execution_reason_code(classification: str) -> str:
    return {
        "TWELVEDATA_TRANSPORT_FAILURE": "REQUEST_TIMEOUT",
        "TWELVEDATA_RATE_LIMIT_429": "BUDGET_UNAVAILABLE",
        "TWELVEDATA_UPSTREAM_5XX": "HTTP_ERROR",
        "TWELVEDATA_INVALID_RESPONSE": "INVALID_RESPONSE",
        "QUOTA_EXCEEDED": "BUDGET_UNAVAILABLE",
        "LOCAL_PARSE_ERROR": "INVALID_RESPONSE",
        "LOCAL_ADMISSION_ERROR": "RAW_EVIDENCE_REJECTED",
        "LOCAL_CANONICAL_ERROR": "INGESTION_FAILED",
        "LOCAL_PROGRAMMING_ERROR": "DISPATCH_REJECTED",
        "SQLITE_BUSY": "INGESTION_FAILED",
        "SQLITE_LOCKED": "INGESTION_FAILED",
        "SQLITE_WRITE_ERROR": "INGESTION_FAILED",
        "SQLITE_COMMIT_ERROR": "INGESTION_FAILED",
        "PUBLICATION_ERROR": "PUBLICATION_FAILED",
        "QUEUE_COMPLETION_ERROR": "QUEUE_COMPLETION_FAILED",
        "INVALID_OHLC": "RAW_EVIDENCE_REJECTED",
        "NO_NEW_DATA": "EMPTY_RESPONSE",
        "AUTHENTICATION_FAILED": "PROVIDER_UNAVAILABLE",
        "CREDENTIAL_MISSING": "PROVIDER_UNAVAILABLE",
    }.get(classification, "HTTP_ERROR")


def _retry_delay_seconds(attempt_number: int) -> int:
    return min(30, 2 ** max(1, attempt_number))


def _retryable_failure(classification: str) -> bool:
    return classification in {
        "TWELVEDATA_RATE_LIMIT_429", "TWELVEDATA_UPSTREAM_5XX",
        "TWELVEDATA_TRANSPORT_FAILURE",
        "TWELVEDATA_INVALID_RESPONSE",
        "LOCAL_PARSE_ERROR", "LOCAL_ADMISSION_ERROR", "LOCAL_CANONICAL_ERROR",
        "SQLITE_BUSY", "SQLITE_LOCKED", "SQLITE_WRITE_ERROR",
        "SQLITE_COMMIT_ERROR", "PUBLICATION_ERROR", "QUEUE_COMPLETION_ERROR",
    }


def _throughput_limiter(cycle: dict[str, object]) -> str:
    failures = cycle.get("requests_failed_by_domain", {})
    domains = set(failures) if isinstance(failures, dict) else set()
    if "TWELVEDATA_RATE_LIMIT_429" in domains:
        return "PROVIDER_429"
    if any(item.startswith("SQLITE_") for item in domains):
        return "DATABASE"
    if any(item in {"TWELVEDATA_UPSTREAM_5XX", "TWELVEDATA_TRANSPORT_FAILURE", "TWELVEDATA_INVALID_RESPONSE"} for item in domains):
        return "UPSTREAM_FAILURE"
    if any(item.startswith("LOCAL_") or item in {"PUBLICATION_ERROR", "QUEUE_COMPLETION_ERROR"} for item in domains):
        return "LOCAL_EXECUTION"
    if int(cycle.get("eligible_count", 0) or 0) == 0:
        return "NO_ELIGIBLE_WORK"
    if int(cycle.get("queue_depth_after", 0) or 0) and int(cycle.get("credits_remaining", 0) or 0) == 0:
        return "CREDIT_WINDOW"
    if int(cycle.get("selected_count", 0) or 0) < int(cycle.get("eligible_count", 0) or 0):
        return "WORKER_CAPACITY"
    return "NONE"


def _file_revision(path: str | Path) -> tuple[str, int | None, int | None]:
    """Return a cheap, content-independent revision for an authority input."""
    resolved = Path(path).expanduser().resolve()
    try:
        status = resolved.stat()
    except OSError:
        return str(resolved), None, None
    return str(resolved), status.st_mtime_ns, status.st_size


def _idle_input_revision(
    database_path: str | Path, journal_path: str | Path | None,
) -> tuple[tuple[str, int | None, int | None], ...]:
    """Fingerprint every persisted input used by a full scheduler snapshot."""
    database = Path(database_path).expanduser().resolve()
    journal = (
        Path(journal_path).expanduser().resolve()
        if journal_path is not None
        else Path(f"{database}.scheduler.json")
    )
    return tuple(
        _file_revision(path)
        for path in (
            database,
            Path(f"{database}-wal"),
            Path(f"{database}-shm"),
            journal,
            provider_facts_path(database),
            publication_path(database),
        )
    )


def _authority_change_token(database_path: str | Path) -> str:
    """Cheaply identify a new authority publication without reading the estate.

    SQLite keeps normal scheduler writes in the WAL, so fingerprint both the
    database and its WAL metadata.  The token is a refresh signal for the
    desktop projection, not a canonical authority revision.
    """
    database = Path(database_path).expanduser().resolve()
    parts: list[str] = []
    for path in (database, Path(f"{database}-wal")):
        try:
            stat = path.stat()
            parts.append(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")
        except OSError:
            parts.append(f"{path.name}:missing")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _stable_past_due_no_work(snapshot: dict[str, object], now: datetime) -> bool:
    """Whether a completed cycle can wait on revisions instead of rebuilding."""
    execution = snapshot.get("execution")
    if not isinstance(execution, dict) or snapshot.get("active_activity"):
        return False
    if str(execution.get("throughput_limited_by")) != "NO_ELIGIBLE_WORK":
        return False
    if any(int(execution.get(key, 0) or 0) for key in (
        "eligible_count", "selected_count", "dispatch_attempted_count",
        "provider_calls_started", "active_workers",
    )):
        return False
    next_run = snapshot.get("next_run")
    if next_run is None:
        return True
    try:
        scheduled = datetime.fromisoformat(str(next_run).replace("Z", "+00:00"))
    except ValueError:
        # Preserve the existing scheduler path for an unexpected timestamp.
        return False
    return normalized_utc(scheduled) <= normalized_utc(now)


def _age_seconds(value: object, now: datetime) -> float | None:
    try:
        return max(0.0, (now - datetime.fromisoformat(str(value))).total_seconds())
    except (TypeError, ValueError):
        return None


def _dispatch_liveness(
    queue_summary: dict[str, object], throughput: dict[str, object],
    execution: dict[str, object], *, active_activity: dict[str, object] | None,
    now: datetime,
) -> dict[str, object]:
    """State the one permitted reason a ready queue is not starting work.

    This is deliberately derived from persisted queue and completed-cycle facts
    rather than the presentation state of the monitor.  It is used both to
    force the next scheduler wake and to make an idle-ready failure explicit.
    """
    ready = int(queue_summary.get("ready_now", 0) or 0)
    running = int(queue_summary.get("running", 0) or 0)
    capacity = int(throughput.get("available_capacity", 0) or 0)
    active_workers = 1 if active_activity else int(execution.get("active_workers", 0) or 0)
    last_attempt = execution.get("last_dispatch_attempt_at") or queue_summary.get("last_dispatch")
    # A cycle that selected nothing has no dispatch timestamp. Its completion
    # is still the liveness clock: after five seconds it must report why it
    # could not allocate a worker rather than remaining "Dispatching" forever.
    liveness_reference = last_attempt or execution.get("completed_at")
    attempt_age = _age_seconds(liveness_reference, now)
    oldest_ready_age = queue_summary.get("oldest_ready_age_seconds")
    base = {
        "ready_now": ready,
        "capacity_available": capacity,
        "workers_active": active_workers,
        "oldest_ready_age_seconds": oldest_ready_age,
        "last_dispatch_attempt": last_attempt,
        "last_scheduler_lock_holder": execution.get("last_scheduler_lock_holder"),
        "last_cycle_overrun_reason": execution.get("cycle_overrun_reason"),
    }
    if active_workers or running:
        return {**base, "state": "Dispatching", "reason": "Workers are active"}
    if ready == 0:
        return {**base, "state": "Idle: no ready work", "reason": "No ready queue items"}
    if int(queue_summary.get("cooling_down", 0) or 0):
        return {**base, "state": "Cooling/backoff", "reason": "Provider cooldown or backoff is active"}
    if int(queue_summary.get("blocked", 0) or 0):
        return {**base, "state": "Blocked by authority", "reason": "Authority blocks ready queue work"}
    if capacity <= 0:
        return {**base, "state": "Waiting for provider budget", "reason": "No dispatchable provider capacity"}
    if attempt_age is not None and attempt_age > _DISPATCH_LIVENESS_SECONDS:
        return {
            **base,
            "state": "BUG: ready work idle",
            "reason": str(execution.get("no_worker_started_reason") or "Ready work had capacity but no worker was started"),
        }
    return {
        **base,
        "state": "Dispatching",
        "reason": "Catch-up dispatch is due within five seconds",
    }


def _preserve_manual_request_creation(request):
    request.setdefault("providers_considered_at_creation", list(request.get("providers_considered", [])))
    request.setdefault("providers_attempted_at_creation", list(request.get("providers_attempted", [])))
    request.setdefault("original_provider_facts", list(request.get("providers_considered", [])))
    request.setdefault("original_rejection_reasons", list(request.get("providers_rejected", [])))
    request.setdefault("original_missing_range", {
        "start": request.get("missing_start"), "end": request.get("missing_end"),
    })
    request.setdefault("created_provider_fact_revision", None)
    request.setdefault("created_capability_projection_revision", None)


def _finish_manual_evaluation(request, provider_revision, capability_revision, evaluation_revision, observed):
    request.update(
        last_evaluated_provider_fact_revision=provider_revision,
        last_evaluated_capability_projection_revision=capability_revision,
        last_evaluated_at=observed.isoformat(),
        last_evaluation_revision=evaluation_revision,
    )


def _manual_temporary_block(plan, provider_state):
    temporary = {
        "RATE_BUDGET_EXHAUSTED": ("Waiting for Budget", "Waiting for local provider budget"),
        "ADAPTIVE_CAPACITY_RESERVED": ("Waiting for Budget", "Waiting for adaptive capacity"),
        "QUEUE_BANDWIDTH_EXHAUSTED": ("Waiting for Budget", "Waiting for adaptive capacity"),
        "PROVIDER_COOLDOWN": ("Cooling Down", "Provider cooldown is active"),
        "CREDENTIAL_MISSING": ("Credential Repair Required", "Provider credential access requires repair"),
        "AUTHENTICATION_BLOCKED": ("Credential Repair Required", "Provider credential access requires repair"),
    }
    direct_mapping = False
    for item in plan.get("providers_considered", []):
        if item.get("mapping_class") in {
            "EXACT_REPRESENTATION", "APPROVED_PROVIDER_ALIAS",
            "APPROVED_EQUIVALENT_REPRESENTATION",
        }:
            direct_mapping = True
        reason = str(item.get("reason") or "")
        if direct_mapping and reason in temporary:
            return temporary[reason]
        state = provider_state.get(str(item.get("provider")), {})
        if direct_mapping and isinstance(state, dict) and state.get("health") in {"Maintenance", "Unavailable"}:
            return "Blocked", "Provider service is temporarily unavailable"
    return None


def _temporary_operator_action(state):
    return {
        "Waiting for Budget": "WAIT_FOR_BUDGET",
        "Cooling Down": "WAIT_FOR_COOLDOWN",
        "Paused": "RESUME_ACQUISITION",
        "Credential Repair Required": "REPAIR_CREDENTIAL",
        "Blocked": "WAIT_FOR_SERVICE_RECOVERY",
    }.get(state, "WAIT")


def _restore_manual_queue(queue_by_lane, request, plan, observed, *, state, reason):
    lane_id = f"{request.get('symbol')}:{request.get('timeframe')}"
    existing = queue_by_lane.get(lane_id)
    queue_id = str(existing.get("id")) if existing else (
        f"{lane_id}:RECONCILED:{request.get('expected_canonical_edge')}"
    )
    queue_by_lane[lane_id] = {
        "id": queue_id, "lane": lane_id, "symbol": request.get("symbol"),
        "timeframe": request.get("timeframe"),
        "missing_range": {
            "start": request.get("missing_start"), "end": request.get("missing_end"),
        },
        "selected_provider": plan.get("selected_provider"),
        "selected_provider_symbol": plan.get("selected_provider_symbol"),
        "selected_mapping_class": plan.get("selected_mapping_class"),
        "fallback_position": 0,
        "queue_reason": reason, "estimated_requests": int(plan.get("estimated_request_count", 0) or 0),
        "budget_wait": None, "next_attempt": None, "missed_boundaries": 1,
        "work_class": "QUEUE", "operational_state": state,
        "waiting_reason": None if state == "Ready" else reason,
        "enqueued_at": (existing or {}).get("enqueued_at") or observed.isoformat(),
        "restored_from_manual_request": request.get("id"),
    }
    return queue_id, existing is not None


def _archive_manual_history(journal, request, lane_id, outcome, observed):
    archive = journal.data.setdefault("archived_operational_work", [])
    fingerprint = f"MANUAL_REQUEST:{request.get('id')}:{outcome}"
    if any(item.get("fingerprint") == fingerprint for item in archive if isinstance(item, dict)):
        return
    archive.insert(0, {
        "id": f"archive-{uuid.uuid4().hex}", "fingerprint": fingerprint,
        "kind": "MANUAL_REQUEST", "source_identifier": request.get("id"),
        "lane": lane_id, "reason": outcome, "archived_at": observed.isoformat(),
        "actionable": False, "payload": dict(request),
    })
    del archive[500:]


def _archive_reconciled_request(journal, request, lane_id, outcome, observed):
    request.update(
        status="Archived", actionable=False, archive_reason=outcome,
        archived_at=observed.isoformat(), reconciled_at=observed.isoformat(),
        reconciliation_status=outcome, reconciliation_reason=outcome,
        replacement_queue_identifier=None, recommended_operator_action="NONE",
    )
    _archive_manual_history(journal, request, lane_id, outcome, observed)
    journal.lane(str(request.get("symbol")), str(request.get("timeframe"))).update(
        queue_state=None, result="ARCHIVED", reason=outcome, manual_request=None
    )


def scheduler_snapshot(
    database_path: str | Path,
    *,
    clock: Callable[[], datetime] | None = None,
    journal_path: str | Path | None = None,
    service_state: str = "Running",
    active_activity: dict[str, object] | None = None,
    credential: str | None = None,
    provider_profiles=None,
) -> dict[str, object]:
    snapshot_started = time.monotonic()
    generated = normalized_utc(clock() if clock else None)
    journal = SchedulerJournal(database_path, journal_path)
    publication = publication_state(database_path)
    reconciliation = reconcile_operational_state(database_path, journal.data, at=generated)
    universe = reconciliation["universe"]
    pauses_changed = refresh_pause_states(journal.data, universe)
    selected_policy = _scheduler_policy(journal)
    profiles = tuple(provider_profiles or load_provider_profiles())
    credentials = credential_map(credential)
    credential_repaired = _repair_twelve_data_credential_health(
        database_path, journal.providers, credentials
    )
    budgets = build_rate_budgets(
        profiles, journal.providers, wall_clock=lambda: generated, credential=credential,
    )
    manual_reconciliation = _reconcile_manual_requests_loaded(
        database_path, journal, generated, credential=credential,
        trigger="SNAPSHOT", profiles=profiles, budgets=budgets,
    )
    capability_projection = cached_acquisition_capability_projection(
        database_path, profiles=profiles, provider_state=journal.providers,
        budgets=budgets, credentials=credentials, now=generated,
    )
    reconciliation_created = "spec047_capability_reconciliation" not in journal.data
    if reconciliation_created:
        journal.data["spec047_capability_reconciliation"] = capability_reconciliation_report(
            capability_projection
        )
    protected_demand = _scheduled_demand_forecast(database_path, profiles, generated, journal)
    queue = list(journal.data.get("acquisition_queue", []))
    throughput = calculate_throughput(
        policy=selected_policy,
        work_items=queue,
        queued_items=queue,
        profiles=profiles,
        provider_state=journal.providers,
        budgets=budgets,
        credentials=credentials,
        scheduled_demand=protected_demand,
        now=generated,
        active_activity=active_activity,
    )
    queue_percentage = int(throughput["target_utilization_percent"])
    dynamic_reserve = {
        str(item["provider"]): int(item["reserved_capacity"])
        for item in throughput["providers"]
    }
    freshness_report = lane_freshness_report(database_path, clock=lambda: generated)
    # Selected-instrument planning must use the same range-aware acquisition
    # authority as Required Set and manual-request reconciliation.  Capability
    # rows answer whether a provider exists; this projection additionally
    # answers whether it can honour the governed request bounds.
    lane_acquisition_plans: dict[str, dict[str, object]] = {}
    for audited in freshness_report["lanes"]:
        symbol, timeframe = str(audited["symbol"]), str(audited["timeframe"])
        authority = universe["lanes"].get(f"{symbol}:{timeframe}")
        if authority is None:
            continue
        try:
            lane_acquisition_plans[f"{symbol}:{timeframe}"] = _required_set_lane_plan(
                database_path,
                journal=journal,
                symbol=symbol,
                asset_class=str(authority["asset_class"]),
                timeframe=timeframe,
                observed=generated,
                profiles=profiles,
                credentials=credentials,
                budgets=budgets,
            )
        except (ValueError, TypeError):
            # The normal lane row continues to expose its precise calendar
            # reason.  A malformed legacy registration must not make the
            # scheduler monitor unavailable for every other lane.
            continue
    changed = resolve_satisfied_manual_requests(
        database_path, journal.manual_requests, generated
    )
    provider_state_before = json.dumps(journal.providers, sort_keys=True, default=str)
    providers, rate_budgets = provider_monitor_rows(
        profiles, journal.providers, budgets, credentials, generated,
        queue_percentage=queue_percentage,
        protected_demand=dynamic_reserve,
        active_requests={
            str(active_activity.get("provider")): 1
            for _ in (0,)
            if active_activity and active_activity.get("provider")
        },
        throughput=throughput,
    )
    for profile in profiles:
        journal.providers.setdefault(profile.provider, {})["rate_events"] = budgets[
            profile.provider
        ].persisted_events()
    commissioning_matrix = _scheduler_commissioning_projection(
        database_path, freshness_report, universe
    )
    rows: list[dict[str, object]] = []
    with open_read_only(database_path) as connection:
        for audited in freshness_report["lanes"]:
            symbol, timeframe = audited["symbol"], audited["timeframe"]
            freshness = audited["freshness"]
            schedule = schedule_for_lane(
                connection,
                symbol=symbol,
                timeframe=timeframe,
                after=generated,
            )
            recorded = journal.lane(symbol, timeframe)
            lane_id = f"{symbol}:{timeframe}"
            # The monitor is also the native planning projection.  It must
            # expose declared manual lanes so their canonical and expected
            # edges can be planned, while scheduler ownership remains limited
            # to active (commissioned) lanes everywhere else.
            lane_authority = universe["lanes"].get(lane_id)
            if lane_authority is None:
                continue
            scheduler_owned = lane_id in universe["active_lanes"]
            pause_sources = effective_pause_sources(
                journal.data, symbol=symbol, group=str(lane_authority["group"])
            )
            lane_capabilities = [
                item for item in capability_projection["rows"]
                if item["canonical_symbol"] == symbol and item["timeframe"] == timeframe
            ]
            # The routine monitor can compact a large snapshot to two provider
            # rows.  Keep actionable reviewed routes ahead of generic rejected
            # providers so the compact view still carries the operator's actual
            # approval path (for example COINGECKO D1 and BINANCE intraday).
            lane_capabilities.sort(key=lambda item: (
                item.get("eligibility") != "ELIGIBLE",
                item.get("mapping_status") not in {
                    "EXACT_REPRESENTATION",
                    "APPROVED_PROVIDER_ALIAS",
                    "APPROVED_EQUIVALENT_REPRESENTATION",
                },
                int(item.get("priority", 999)),
                str(item.get("provider", "")),
            ))
            state = (
                _lane_state(
                    freshness,
                    recorded,
                    active_activity=active_activity,
                    symbol=symbol,
                    timeframe=timeframe,
                )
                if scheduler_owned else "Not Commissioned"
            )
            publication_entry = publication.get("lanes", {}).get(f"{symbol}:{timeframe}", {})
            publication_status = _normalized_publication_state(publication_entry)
            if (
                scheduler_owned
                and freshness.get("latest_canonical_observation") is not None
                and publication_status == "PUBLISHING"
            ):
                state = "Publishing"
            elif scheduler_owned and publication_status == "FAILED_RETRYABLE":
                state = "Failed"
            if scheduler_owned and pause_sources and state not in {"Running", "Current"}:
                state = "Paused"
            rows.append(
                {
                    "id": f"{symbol}:{timeframe}",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "scheduler_state": state,
                    "latest_canonical_observation": freshness.get(
                        "latest_canonical_observation"
                    ),
                    "expected_latest": freshness.get("expected_latest"),
                    "expected_edge_status": freshness.get("expected_edge_state"),
                    "lag": freshness.get("lag"),
                    "freshness_severity": freshness.get("severity"),
                    "operational_state": freshness.get("operational_state"),
                    "next_scheduled_acquisition": schedule.get(
                        "next_scheduled_acquisition"
                    ),
                    "last_acquisition": recorded.get("last_acquisition"),
                    "duration_seconds": recorded.get("duration_seconds"),
                    "result": recorded.get("result"),
                    "reason": recorded.get("reason")
                    or freshness.get("reason_code")
                    or schedule.get("reason_code"),
                    "routing_decision": recorded.get("routing_decision"),
                    "providers_considered": recorded.get("providers_considered", []),
                    "acquisition_plan": lane_acquisition_plans.get(lane_id),
                    "provider_capabilities": lane_capabilities,
                    "providers_rejected": recorded.get("providers_rejected", []),
                    "current_provider": recorded.get("current_provider"),
                    "attempt_history": recorded.get("attempt_history", []),
                    "publication_result": recorded.get("publication_result"),
                    "publication_state": publication_status,
                    "publication_job_id": publication_entry.get("job_id") if isinstance(publication_entry, dict) else None,
                    "manual_request": recorded.get("manual_request"),
                    "market": lane_authority["group"],
                    "lifecycle_state": lane_authority["lifecycle_state"],
                    "pause_state": "Paused" if pause_sources else None,
                    "pause_effective_sources": [item["pause_identifier"] for item in pause_sources],
                    "calendar_diagnostics": {
                        "calendar_identifier": schedule.get("calendar_id") or lane_authority.get("calendar_identifier"),
                        "calendar_status": schedule.get("calendar_status") or ("AVAILABLE" if schedule.get("available") else "UNAVAILABLE"),
                        "timezone": schedule.get("timezone"),
                        "session_close_rule": schedule.get("session_close_rule"),
                        "timeframe": timeframe,
                        "calculation_time": schedule.get("calculation_time") or generated.isoformat(),
                        "exact_failure_reason": schedule.get("reason_detail") or schedule.get("reason_code"),
                    },
                }
            )
    counts = {
        state: sum(row["scheduler_state"] == state for row in rows)
        for state in ("Current", "Waiting", "Running", "Behind", "Unavailable", "Failed", "Paused", "Not Commissioned", "No Evidence")
    }
    next_values = [
        row["next_scheduled_acquisition"]
        for row in rows
        if row["next_scheduled_acquisition"]
    ]
    next_values.extend(
        str(item["next_attempt"])
        for item in queue
        if item.get("next_attempt")
    )
    events = journal.data.get("events", [])
    last_success = next(
        (event["at"] for event in events if event.get("result") == "SUCCESS"), None
    )
    last_failure = next(
        (event["at"] for event in events if event.get("result") == "FAILED"), None
    )
    health = _authority_health(service_state, counts)
    queue_summary = _queue_summary(
        queue, journal.manual_requests, journal.data.get("last_dispatch"), generated,
        throughput=throughput,
    )
    last_cycle = dict(journal.data.get("last_completed_cycle") or {})
    trace_lanes = sorted({
        str(item.get("lane")) for item in queue if item.get("lane")
    } | {
        str(item.get("lane_id"))
        for item in journal.data.get("execution_trace_events", [])
        if isinstance(item, dict) and item.get("lane_id")
    })
    trace_summaries = []
    for lane_id in trace_lanes:
        symbol, _, timeframe = lane_id.partition(":")
        summary = trace_for_lane(journal.data, symbol, timeframe)
        summary.pop("events", None)
        trace_summaries.append(summary)
    execution = {
        **last_cycle,
        "active_workers": 1 if active_activity else int(last_cycle.get("active_workers", 0) or 0),
        "available_workers": 0 if active_activity else int(last_cycle.get("available_workers", 1) or 1),
        "trace_summaries": trace_summaries,
    }
    dispatch_liveness = _dispatch_liveness(
        queue_summary, throughput, execution,
        active_activity=active_activity, now=generated,
    )
    scheduled_next_run = min(next_values) if next_values else None
    if (
        dispatch_liveness["state"] in {"Dispatching", "BUG: ready work idle"}
        and int(dispatch_liveness["ready_now"]) > 0
        and int(dispatch_liveness["capacity_available"]) > 0
        and int(dispatch_liveness["workers_active"]) == 0
    ):
        next_run = (generated + timedelta(seconds=_CATCH_UP_WAKE_SECONDS)).isoformat()
        dispatch_liveness["next_wake_reason"] = "READY_CAPACITY_CATCH_UP"
    else:
        next_run = scheduled_next_run
        dispatch_liveness["next_wake_reason"] = (
            "SCHEDULED_BOUNDARY" if scheduled_next_run else "AWAITING_AUTHORITY_CHANGE"
        )
    dispatch_liveness["next_wake"] = next_run
    progress = scheduler_progress_projection(journal.data, execution, generated)
    snapshot = {
        "contract": SCHEDULER_CONTRACT,
        "generated_at": generated.replace(microsecond=0).isoformat(),
        "service_state": service_state,
        "authority_health": health,
        "authority_revision": freshness_report["authority_revision"],
        "active_universe_revision": universe["revision"],
        "summary": {"total": len(rows), **counts},
        "next_run": next_run,
        "last_successful_acquisition": last_success,
        "last_failure": last_failure,
        "active_activity": dict(active_activity) if active_activity else None,
        "lanes": rows,
        "commissioning_matrix":commissioning_matrix,
        "missing_commissions":[
            row for row in commissioning_matrix if row["missing_commission"]
        ],
        "events": events[:50],
        "providers": providers,
        "acquisition_capability_projection": capability_projection,
        "capability_reconciliation": journal.data.get("spec047_capability_reconciliation"),
        "rate_budgets": rate_budgets,
        "acquisition_queue": queue,
        "routing_decisions": list(journal.data.get("routing_decisions", []))[:100],
        "manual_requests": _manual_request_details(journal.manual_requests, universe, journal.data, generated),
        # These are historical display projections, not authority.  Bounding
        # their wire form keeps monitor liveness independent of journal growth.
        "manual_request_history": list(journal.manual_requests)[:50],
        "archived_operational_work": list(journal.data.get("archived_operational_work", []))[:50],
        "request_lifecycle_counts": request_lifecycle_counts(journal.data.get("request_lifecycle", [])),
        "pause_records": list(journal.data.get("pause_records", [])),
        "pause_effective_sources": {
            row["id"]: row["pause_effective_sources"] for row in rows if row["pause_effective_sources"]
        },
        "manual_request_count": queue_summary["manual_required"],
        "manual_request_unique_lanes": queue_summary["manual_request_unique_lanes"],
        "manual_request_unique_symbols": queue_summary["manual_request_unique_symbols"],
        "unavailable_lane_details": _unavailable_lane_details(rows),
        "exception_filters": _exception_filters(rows, queue, journal.manual_requests),
        "scheduler_policy": policy_label(selected_policy),
        "scheduler_policy_key": selected_policy,
        "throughput": throughput,
        "queue_summary": queue_summary,
        "dispatch_state": dispatch_liveness,
        "execution": execution,
        "scheduler_progress": progress,
        "manual_request_reconciliation": manual_reconciliation["report"],
        "manual_request_migration_report": journal.data.get("manual_request_migration_report"),
        "required_set_active_job": journal.data.get("required_set_active_job"),
        "required_set_jobs": list(journal.data.get("required_set_jobs", []))[:20],
        "current_provider_fact_revision": journal.data.get("current_provider_fact_revision", 0),
        "current_capability_projection_revision": journal.data.get("current_capability_projection_revision"),
        "publication": publication,
    }
    # This is a monitor-only measurement.  It deliberately does not hold the
    # acquisition executor lock or participate in worker allocation.
    execution["estate_snapshot_duration_ms"] = round(
        max(0.0, (time.monotonic() - snapshot_started) * 1000), 3
    )
    _guard_monitor_snapshot(snapshot, started_at=snapshot_started)
    provider_state_changed = provider_state_before != json.dumps(journal.providers, sort_keys=True, default=str)
    if changed or manual_reconciliation["changed"] or reconciliation_created or reconciliation["changed"] or pauses_changed or provider_state_changed or credential_repaired or journal.migration_pending:
        journal.save()
    return snapshot


def _guard_monitor_snapshot(snapshot: dict[str, object], *, started_at: float) -> None:
    """Bound routine monitor payloads without removing authority detail on disk."""
    target_bytes = 2 * 1024 * 1024
    encoded = json.dumps(snapshot, default=str, separators=(",", ":")).encode("utf-8")
    if len(encoded) > target_bytes:
        for lane in snapshot.get("lanes", []):
            if isinstance(lane, dict):
                lane["attempt_history"] = list(lane.get("attempt_history", []))[:3]
                lane["providers_considered"] = list(lane.get("providers_considered", []))[:8]
                lane["provider_capabilities"] = list(lane.get("provider_capabilities", []))[:8]
                _compact_lane_acquisition_plan(lane, 8)
        projection = snapshot.get("acquisition_capability_projection")
        if isinstance(projection, dict) and isinstance(projection.get("rows"), list):
            projection["rows"] = projection["rows"][:500]
            projection["truncated_for_monitor"] = True
        encoded = json.dumps(snapshot, default=str, separators=(",", ":")).encode("utf-8")
    # A large persisted backlog can still exceed the target after lane-level
    # trimming.  The monitor needs enough detail to operate, not the complete
    # durable journal: retain bounded recent copies and make the truncation
    # explicit.  The queue, trace history, and provider facts on disk are
    # untouched and remain available through focused drill-down commands.
    if len(encoded) > target_bytes:
        for lane in snapshot.get("lanes", []):
            if isinstance(lane, dict):
                lane["attempt_history"] = list(lane.get("attempt_history", []))[:1]
                lane["providers_considered"] = list(lane.get("providers_considered", []))[:2]
                lane["providers_rejected"] = list(lane.get("providers_rejected", []))[:2]
                lane["provider_capabilities"] = list(lane.get("provider_capabilities", []))[:2]
                _compact_lane_acquisition_plan(lane, 2)
        projection = snapshot.get("acquisition_capability_projection")
        if isinstance(projection, dict) and isinstance(projection.get("rows"), list):
            projection["rows"] = projection["rows"][:100]
            projection["truncated_for_monitor"] = True
        for key, limit in {
            "acquisition_queue": 100,
            "manual_requests": 50,
            "manual_request_history": 25,
            "archived_operational_work": 25,
            "required_set_jobs": 5,
        }.items():
            value = snapshot.get(key)
            if isinstance(value, list) and len(value) > limit:
                snapshot[key] = value[:limit]
                snapshot[f"{key}_truncated_for_monitor"] = True
        publication = snapshot.get("publication")
        if isinstance(publication, dict) and isinstance(publication.get("jobs"), list):
            publication["jobs"] = publication["jobs"][:20]
            publication["truncated_for_monitor"] = True
        execution = snapshot.get("execution")
        if isinstance(execution, dict) and isinstance(execution.get("trace_summaries"), list):
            execution["trace_summaries"] = execution["trace_summaries"][:50]
        encoded = json.dumps(snapshot, default=str, separators=(",", ":")).encode("utf-8")
    snapshot["monitor_guard"] = {
        "payload_bytes": len(encoded), "target_bytes": target_bytes,
        "within_size_target": len(encoded) < target_bytes,
        "generation_ms": round((time.monotonic() - started_at) * 1000, 3),
        "generation_target_ms": 1000,
    }


def _compact_lane_acquisition_plan(lane: dict[str, object], limit: int) -> None:
    """Keep reviewed executable routes ahead of generic mapping rejections."""
    plan = lane.get("acquisition_plan")
    if not isinstance(plan, dict) or not isinstance(plan.get("providers_considered"), list):
        return
    candidates = [item for item in plan["providers_considered"] if isinstance(item, dict)]
    candidates.sort(key=lambda item: (
        not bool(item.get("eligible")),
        str(item.get("mapping_class") or "") not in {
            "EXACT_REPRESENTATION",
            "APPROVED_PROVIDER_ALIAS",
            "APPROVED_EQUIVALENT_REPRESENTATION",
        },
        int(item.get("fallback_rank") or 999),
        str(item.get("provider") or ""),
    ))
    plan["providers_considered"] = candidates[:limit]


def _repair_twelve_data_credential_health(
    database_path: str | Path,
    provider_state: dict[str, object],
    credentials: dict[str, str],
) -> bool:
    """Clear only stale missing-credential blocks after a verified resolver success."""
    if not credentials.get("TWELVE_DATA"):
        return False
    facts = load_provider_facts(database_path)
    if facts.get("credential_state") != "Configured":
        return False
    state = provider_state.get("TWELVE_DATA")
    if not isinstance(state, dict):
        return False
    stale_local_block = (
        state.get("health") in {
            "Credential Missing", "Authentication Blocked", "Cooling Down",
            "Transient Provider Backoff", "Unavailable", "Degraded",
        }
        and state.get("wait_reason") not in {"CREDENTIAL_MISSING", "AUTHENTICATION_FAILED"}
    )
    invented_cooldown = bool(state.get("cooldown_until")) and not state.get("last_429_at")
    if not stale_local_block and not invented_cooldown:
        return False
    state.update(
        health="Healthy", consecutive_failures=0, cooldown_until=None,
        cooldown=None, wait_reason=None, wait_scope=None,
    )
    return True


def run_due_acquisitions(
    database_path: str | Path,
    **kwargs,
) -> dict[str, object]:
    """Serialize every Scheduler and operator acquisition through one executor."""

    journal = SchedulerJournal(database_path, kwargs.get("journal_path"))
    execution_lock = journal.path.with_suffix(f"{journal.path.suffix}.acquisition.lock")
    execution_lock.parent.mkdir(parents=True, exist_ok=True)
    with execution_lock.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            return _run_due_acquisitions_unlocked(database_path, **kwargs)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _run_due_acquisitions_unlocked(
    database_path: str | Path,
    *,
    at: datetime,
    credential: str | None,
    journal_path: str | Path | None = None,
    catch_up: bool = False,
    acquirer: Callable[..., dict[str, object]] = acquire_from_provider,
    emit: Callable[[dict[str, object]], None] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    provider_profiles=None,
    max_tasks: int | None = None,
    operation_progress: Callable[[str], None] | None = None,
    defer_publication: bool = False,
    time_triggered: bool = False,
) -> dict[str, object]:
    observed = normalized_utc(at)
    # Resume only durable publication transactions before selection.  It does
    # not construct an estate monitor or perform provider I/O; full monitor
    # projection remains out of the dispatch start path.
    resume_pending_publications(database_path)
    cycle_id = str(uuid.uuid4())
    cycle_started_at = datetime.now(UTC)
    cycle_started = monotonic()
    journal = SchedulerJournal(database_path, journal_path)
    update_register = LaneUpdateRegister(database_path) if time_triggered else None
    if update_register is not None:
        # Initial seeding and explicit audits are the only register operations
        # allowed to inspect the estate.  Every later normal wake starts with
        # the indexed due-work claim below.
        update_register.initialize_if_needed(at=observed)
        # This executor waits for every worker before the cycle returns.  A
        # RUNNING row at the start of a new serialized cycle therefore cannot
        # belong to a live worker; it was interrupted after claim and must be
        # retried.  Restricting this to the indexed register avoids turning a
        # routine recovery into an estate reconciliation.
        update_register.recover_running(at=observed)
    queue_before = [
        item for item in journal.data.get("acquisition_queue", [])
        if isinstance(item, dict)
    ]
    cycle: dict[str, object] = {
        "cycle_id": cycle_id,
        "started_at": cycle_started_at.isoformat(),
        "queue_depth_before": len(queue_before),
        "oldest_queue_age_before": oldest_queue_age(queue_before, observed),
        "eligible_count": 0,
        "selected_count": 0,
        "dispatch_attempted_count": 0,
        "worker_allocated_count": 0,
        "request_started_count": 0,
        "request_completed_count": 0,
        "canonical_advanced_count": 0,
        "queue_completed_count": 0,
        "failed_count": 0,
        "deferred_count": 0,
        "active_workers": 0,
        "available_workers": 1,
        "provider_calls_reserved": 0,
        "provider_calls_started": 0,
        "provider_calls_completed": 0,
        "dispatchable_credits": 0,
        "requests_failed_by_domain": {},
        "credits_consumed": 0,
        "credits_remaining": 0,
        "dispatch_rate_per_minute": 0.0,
        "worker_utilisation": 0.0,
        "database_wait_ms": 0.0,
        "scheduler_dispatch_slots_missed_database": 0,
        "throughput_limited_by": "NONE",
        "last_scheduler_lock_holder": f"scheduler-cycle:{cycle_id}",
        "last_dispatch_attempt_at": None,
        "no_worker_started_reason": None,
        "estate_snapshot_duration_ms": 0.0,
        "publication_duration_ms": 0.0,
    }
    recovery_changed = recover_stale_reservations(journal.data, at=observed)
    estate_snapshot_started = monotonic()
    if time_triggered:
        # The register is the normal work index.  Do not rebuild the estate
        # merely to discover ordinary due work.
        reconciliation = {"changed": False, "universe": {"active_lanes": {}}}
        universe = reconciliation["universe"]
        if recovery_changed:
            journal.save()
    else:
        reconciliation = reconcile_operational_state(database_path, journal.data, at=observed)
        universe = reconciliation["universe"]
        if refresh_pause_states(journal.data, universe) or recovery_changed or reconciliation["changed"]:
            journal.save()
    for queued in journal.data.get("acquisition_queue", []):
        authority = universe["active_lanes"].get(str(queued.get("lane")))
        if authority and effective_pause_sources(
            journal.data, symbol=str(authority["symbol"]), group=str(authority["group"])
        ):
            queued.update(
                operational_state="Operator Paused", waiting_reason="OPERATOR_PAUSED",
                queue_reason="Dispatch paused by operator", next_attempt=None, budget_wait=None,
            )
    profiles = tuple(provider_profiles or load_provider_profiles())
    profiles_by_id = {profile.provider: profile for profile in profiles}
    selected_policy = _scheduler_policy(journal)
    time_triggered_pace = time_triggered_pacing(
        selected_policy,
        provider_worker_limit=max((profile.concurrency_limit for profile in profiles), default=1),
    )
    credentials = credential_map(credential)
    budgets = build_rate_budgets(
        profiles, journal.providers, monotonic=monotonic,
        wall_clock=(lambda: datetime.now(UTC)), credential=credential,
        sleeper=(time.sleep if acquirer is acquire_from_provider else (lambda _delay: None)),
    )
    manual_reconciliation = (
        {"changed": False}
        if time_triggered else _reconcile_manual_requests_loaded(
            database_path, journal, observed, credential=credential,
            trigger="DISPATCH", profiles=profiles, budgets=budgets,
        )
    )
    if manual_reconciliation["changed"]:
        journal.save()
    scheduled_demand = (
        {profile.provider: 0 for profile in profiles}
        if time_triggered else _scheduled_demand_forecast(database_path, profiles, observed, journal)
    )
    if time_triggered and update_register is not None:
        due = _due_lanes_from_register(
            database_path, observed, update_register,
            max_tasks=max_tasks or int(time_triggered_pace["claim_limit"]),
        )
        # An operator fetch is a durable, explicit request.  It must not wait
        # for the next ordinary register boundary (which can be hours away),
        # but promoting it must not turn every normal wake into an estate
        # reconciliation.  The narrow authority lookup below runs only while
        # such a request exists.
        operator_due, operator_universe = _pending_operator_fetches(
            database_path, observed, journal,
        )
        if operator_due:
            universe = operator_universe
            merged = {f"{item['symbol']}:{item['timeframe']}": item for item in due}
            # Explicit operator work supersedes an ordinary check for the
            # same lane; a single provider request owns that lane this cycle.
            for item in operator_due:
                lane_id = f"{item['symbol']}:{item['timeframe']}"
                claimed_normal = merged.get(lane_id)
                if claimed_normal is not None and claimed_normal.get("work_class") == "NORMAL":
                    # ``claim_due`` has already moved the normal register row
                    # to RUNNING.  Preserve that ownership while the explicit
                    # fetch takes precedence so its terminal path can settle
                    # the claim instead of leaving a phantom RUNNING lane.
                    item = {
                        **item,
                        "_register_claimed": True,
                    }
                merged[lane_id] = item
            due = list(merged.values())
    else:
        due = _due_lanes(database_path, observed, journal, catch_up=catch_up)
    cycle["estate_snapshot_duration_ms"] = round(
        max(0.0, (monotonic() - estate_snapshot_started) * 1000), 3
    )
    dispatchable_due: list[dict[str, object]] = []
    for item in due:
        pause_sources = effective_pause_sources(
            journal.data,
            symbol=str(item["symbol"]),
            group=str(universe["active_lanes"].get(f"{item['symbol']}:{item['timeframe']}", {}).get("group", "")),
        )
        if not pause_sources:
            dispatchable_due.append(item)
            continue
        # ``claim_due`` has already made this register row RUNNING.  A pause
        # is an explicit operator state, not a reason to abandon the claimed
        # row in phantom-running status.  Preserve it as PAUSED until the
        # control path resumes the target lane.
        if time_triggered and update_register is not None:
            update_register.pause(
                asset=str(item["symbol"]), timeframe=str(item["timeframe"]), at=observed,
            )
    due = dispatchable_due
    cycle["eligible_count"] = len(due)
    queue_by_id = {
        str(item.get("id")): item
        for item in journal.data.get("acquisition_queue", [])
        if isinstance(item, dict) and item.get("id")
    }
    # Journals created before execution tracing can contain deferred queue
    # items that are not eligible for rebuilding this cycle.  Give those
    # items an identity now so the first later retry continues one trace
    # instead of appearing as a newly-created boundary.
    for queue_id, queued_item in queue_by_id.items():
        lane_id = str(queued_item.get("lane") or "")
        if not lane_id:
            continue
        _trace_id, trace_created = ensure_trace_identity(
            queued_item, lane_id=lane_id, now=observed,
        )
        if trace_created:
            record_event(
                journal.data, queued_item, "QUEUE_CREATED", cycle_id=cycle_id,
                timestamp=observed, queue_id=queue_id,
                queue_disposition="ACTIVE",
                requested_start=(queued_item.get("missing_range") or {}).get("start"),
                requested_end=(queued_item.get("missing_range") or {}).get("end"),
            )
    _prune_satisfied_queue(database_path, observed, queue_by_id, journal)
    throughput = calculate_throughput(
        policy=selected_policy,
        work_items=due,
        queued_items=list(queue_by_id.values()),
        profiles=profiles,
        provider_state=journal.providers,
        budgets=budgets,
        credentials=credentials,
        scheduled_demand=scheduled_demand,
        now=observed,
    )
    queue_percentage = int(throughput["target_utilization_percent"])
    protected_demand = {
        str(item["provider"]): int(item["reserved_capacity"])
        for item in throughput["providers"]
    }
    journal.data["last_throughput_decision"] = throughput
    for work in due:
        symbol, timeframe, scheduled_for = work["symbol"], work["timeframe"], work["scheduled_boundary"]
        recorded = journal.lane(symbol, timeframe)
        recorded.update(queue_state="Ready", reason=work["queue_reason"])
        proposed_queue_id = f"{symbol}:{timeframe}:{scheduled_for}"
        lane_id = f"{symbol}:{timeframe}"
        prior_item = next((
            existing for existing in queue_by_id.values()
            if existing.get("lane") == lane_id
        ), None)
        queue_id = str(prior_item.get("id")) if prior_item else proposed_queue_id
        for existing_id, existing in list(queue_by_id.items()):
            if existing.get("lane") == lane_id and existing_id != queue_id:
                queue_by_id.pop(existing_id)
        queued_item = {
            "id": queue_id,
            "lane": lane_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "asset_class":work.get("asset_class"),
            "missing_range": work["missing_range"],
            "selected_provider": None,
            "fallback_position": 0,
            "queue_reason": work["queue_reason"],
            "estimated_requests": 0,
            "budget_wait": None,
            "next_attempt": work.get("next_attempt"),
            "missed_boundaries": work["missed_boundaries"],
            "work_class": work["work_class"],
            "dispatch_priority":work["dispatch_priority"],
            "operational_state": "Ready",
            "waiting_reason": None,
            "enqueued_at": (prior_item or queue_by_id.get(queue_id, {})).get("enqueued_at") or observed.isoformat(),
            "required_boundary": (prior_item or {}).get("required_boundary") or work.get("expected_edge"),
            "requested_through": max(
                str((prior_item or {}).get("requested_through") or ""),
                str(work.get("expected_edge") or ""),
            ) or None,
            "scheduled_boundary": scheduled_for,
        }
        _trace_id, trace_created = ensure_trace_identity(
            queued_item, lane_id=lane_id, now=observed, prior=prior_item,
        )
        queue_by_id[queue_id] = queued_item
        work["_queue_id"] = queue_id
        if trace_created:
            record_event(
                journal.data, queued_item, "QUEUE_CREATED", cycle_id=cycle_id,
                timestamp=observed, queue_id=queue_id, queue_disposition="ACTIVE",
                canonical_edge_before=work.get("canonical_edge"),
                requested_start=work["missing_range"].get("start"),
                requested_end=work["missing_range"].get("end"),
            )
        record_event(
            journal.data, queued_item, "PRIORITY_CALCULATED", cycle_id=cycle_id,
            timestamp=observed, dispatch_priority=work["dispatch_priority"],
            queue_id=queue_id,
        )
        record_event(
            journal.data, queued_item, "ELIGIBILITY_EVALUATED", cycle_id=cycle_id,
            timestamp=observed, queue_id=queue_id,
        )
    dispatchable_credits = sum(
        int(budgets[profile.provider].inspect(work_class="QUEUE").get("queue_available", 0) or 0)
        for profile in profiles
    )
    cycle["dispatchable_credits"] = dispatchable_credits
    adaptive_limit = min(len(due), dispatchable_credits)
    selection_limit = (
        min(adaptive_limit, int(throughput["batch_size"]))
        if time_triggered else adaptive_limit
    )
    if max_tasks is not None:
        selection_limit = min(max_tasks, selection_limit)
    selected_due = _fair_bounded_selection(due, selection_limit, journal)
    if time_triggered and update_register is not None:
        selected_ids = {id(item) for item in selected_due}
        for work in due:
            # Only claimed register work owns a register row.  An unselected
            # operator fetch remains durably pending in the journal and is
            # reconsidered on the next service wake.
            if id(work) not in selected_ids and work["work_class"] == "NORMAL":
                update_register.retry(
                    asset=str(work["symbol"]), timeframe=str(work["timeframe"]),
                    reason="CAPACITY_DEFERRED", at=observed,
                    not_before=observed + timedelta(seconds=5),
                )
    cycle["selected_count"] = len(selected_due)
    if due and not selected_due:
        cycle["no_worker_started_reason"] = (
            "Provider capacity unavailable" if dispatchable_credits <= 0
            else "Ready work was not selected by the dispatcher"
        )
    selected_keys = {str(item["_queue_id"]) for item in selected_due}
    for queue_id in selected_keys:
        item = queue_by_id[queue_id]
        record_event(
            journal.data, item, "SELECTED", cycle_id=cycle_id,
            timestamp=observed, queue_id=queue_id,
            dispatch_priority=item.get("dispatch_priority"),
        )
    deferred_until = (observed + timedelta(seconds=1)).isoformat()
    for work in (item for item in due if item not in selected_due):
        item = queue_by_id[str(work["_queue_id"])]
        item.update(
            queue_reason="Adaptive batch complete; immediate capacity re-evaluation queued",
            budget_wait=None,
            next_attempt=deferred_until,
            operational_state="Ready",
        )
        reason = "CYCLE_CAPACITY_EXHAUSTED" if len(selected_due) >= selection_limit else "NOT_SELECTED"
        record_stop(
            journal.data, item, cycle_id=cycle_id,
            current_stage="ELIGIBILITY_EVALUATED", reason_code=reason,
            retryable=True, next_eligible_at=deferred_until, timestamp=observed,
        )
        cycle["deferred_count"] = int(cycle["deferred_count"]) + 1
    journal.data["acquisition_queue"] = list(queue_by_id.values())
    journal.save()
    if emit and not time_triggered:
        emit(scheduler_snapshot(database_path, clock=lambda: observed, journal_path=journal_path, credential=credential, provider_profiles=profiles))

    worker_limit = (
        int(time_triggered_pace["worker_limit"])
        if time_triggered
        else max(1, max((profile.concurrency_limit for profile in profiles), default=1))
    )
    # The journal/state critical sections remain serialized below, but provider
    # work is deliberately outside that lock.  Do not special-case injected
    # acquirers: deterministic sleep-based tests and local adapters must follow
    # the same bounded execution path as the real provider.
    concurrent_execution = len(selected_due) > 1 and worker_limit > 1
    state_lock = threading.RLock()
    publication_lanes: list[tuple[str, str]] = []
    provider_execution_slots = {
        profile.provider: threading.BoundedSemaphore(max(1, profile.concurrency_limit))
        for profile in profiles
    }

    def execute_selected_work(
        work: dict[str, object], *, lock_wait_ms: float,
    ) -> None:
        symbol, timeframe, scheduled_for = work["symbol"], work["timeframe"], work["scheduled_boundary"]
        queue_id = str(work["_queue_id"])
        started_at = datetime.now(UTC)
        started = monotonic()
        recorded = journal.lane(symbol, timeframe)
        trace_item = queue_by_id[queue_id]
        trace_item["attempt_number"] = int(trace_item.get("attempt_number", 0) or 0) + 1
        cycle["dispatch_attempted_count"] = int(cycle["dispatch_attempted_count"]) + 1
        cycle["last_dispatch_attempt_at"] = started_at.isoformat()
        record_event(
            journal.data, trace_item, "DISPATCH_STARTED", cycle_id=cycle_id,
            timestamp=started_at, queue_id=queue_id,
        )
        worker_id = f"scheduler:{cycle_id}:{symbol}:{timeframe}"
        trace_item["active_worker_id"] = worker_id
        cycle["worker_allocated_count"] = int(cycle["worker_allocated_count"]) + 1
        cycle["active_workers"] = int(cycle["active_workers"]) + 1
        cycle["available_workers"] = max(0, worker_limit - int(cycle["active_workers"]))
        cycle["peak_active_workers"] = max(
            int(cycle.get("peak_active_workers", 0) or 0), int(cycle["active_workers"])
        )
        record_event(
            journal.data, trace_item, "WORKER_ALLOCATED", cycle_id=cycle_id,
            timestamp=started_at, worker_id=worker_id,
        )
        recorded.update(
            queue_state="Running",
            last_scheduled_acquisition=scheduled_for,
            last_acquisition=started_at.isoformat(),
            reason=None,
        )
        queue_by_id[queue_id]["operational_state"] = "Running"
        queue_by_id[queue_id]["waiting_reason"] = None
        journal.data["last_dispatch"] = started_at.isoformat()
        journal.save()
        activity = {
            "symbol": symbol,
            "timeframe": timeframe,
            "stage": "Downloading",
            "started_at": started_at.isoformat(),
            "work_class": work["work_class"],
            "trace_id": trace_item["trace_id"],
            "attempt_number": trace_item["attempt_number"],
        }
        if emit and not time_triggered:
            emit(
                scheduler_snapshot(
                    database_path,
                    clock=lambda: observed,
                    journal_path=journal_path,
                    active_activity=activity,
                    credential=credential,
                    provider_profiles=profiles,
                )
            )
        outcome = "FAILED"
        observations = 0
        final_reason: str | None = None
        failures: list[dict[str, object]] = []
        attempted: set[str] = set()
        provider_started_at: datetime | None = None
        provider_finished_at: datetime | None = None
        canonical_commit_started_at: datetime | None = None
        canonical_commit_finished_at: datetime | None = None
        publication_started_at: datetime | None = None
        locked_before_provider_ms = 0.0
        locked_after_provider_started: float | None = None
        reservation_wait_ms = 0.0
        recorded.setdefault("provider_attempts_by_boundary", {})
        requested_bounds = work.get("requested_bounds")
        diagnostic_bounds = _diagnostic_request_bounds(requested_bounds)
        bounds = diagnostic_bounds
        canonical_edge = work.get("canonical_edge")
        expected_edge = str(work.get("expected_edge") or "UNRESOLVED")
        try:
            _operator_progress(operation_progress, "planning")
            bounds = (
                _operator_request_bounds(requested_bounds)
                if requested_bounds is not None
                else _acquisition_bounds(database_path, symbol, timeframe, observed)
            )
            expected_edge = str(work["expected_edge"])

            def progress(stage: str) -> None:
                operator_stage = "publishing" if stage == "ingesting" else stage
                _operator_progress(
                    operation_progress, operator_stage,
                    provider=activity.get("provider"),
                    fallback_position=len(attempted),
                )
                activity["stage"] = {
                    "requesting": "Downloading",
                    "validating": "Validating",
                    "ingesting": "Publishing",
                }.get(stage, stage.replace("_", " ").title())
                if emit and not time_triggered:
                    emit(
                        scheduler_snapshot(
                            database_path,
                            clock=lambda: observed,
                            journal_path=journal_path,
                            active_activity=activity,
                            credential=credential,
                            provider_profiles=profiles,
                        )
                    )

            while True:
                plan = acquisition_plan(
                    database_path,
                    symbol=symbol, timeframe=timeframe,
                    canonical_edge=canonical_edge, expected_edge=expected_edge,
                    missing_start=bounds[0], missing_end=bounds[1],
                    scheduled_boundary=scheduled_for, profiles=profiles,
                    provider_state=journal.providers, budgets=budgets,
                    credentials=credentials, now=observed,
                    attempted_providers=attempted,
                    work_class=work["work_class"],
                    queue_percentage=queue_percentage,
                    protected_demand=protected_demand if work["work_class"] != "NORMAL" else {},
                )
                journal.record_routing(plan)
                recorded.update(
                    routing_decision=plan.get("selection_reason"),
                    providers_considered=plan["providers_considered"],
                    providers_rejected=[item for item in plan["providers_considered"] if not item["eligible"]],
                    current_provider=plan.get("selected_provider"),
                )
                queued = queue_by_id[queue_id]
                queued.update(
                    selected_provider=plan.get("selected_provider"),
                    estimated_requests=plan.get("estimated_request_count", 0),
                    fallback_position=len(attempted) + 1,
                )
                journal.data["acquisition_queue"] = list(queue_by_id.values())
                journal.save()
                provider = plan.get("selected_provider")
                if provider:
                    _operator_progress(
                        operation_progress, "contacting_provider",
                        provider=provider, fallback_position=len(attempted) + 1,
                        fallback_count=len(plan.get("fallback_sequence", [])) + len(attempted),
                    )
                if not provider:
                    temporary = list(plan.get("temporary_ineligibility", []))
                    if temporary and not attempted:
                        waits = []
                        for item in temporary:
                            profile = profiles_by_id[str(item["provider"])]
                            budget_wait = budgets[profile.provider].inspect(
                                int(item["estimated_request_count"]),
                                work_class=work["work_class"],
                                queue_percentage=queue_percentage,
                                protected_normal_demand=(protected_demand.get(profile.provider, 0) if work["work_class"] != "NORMAL" else 0),
                                safety_reserve=profile.safety_reserve,
                            ).get("next_available")
                            cooldown = journal.providers.get(profile.provider, {}).get("cooldown_until")
                            if budget_wait: waits.append(str(budget_wait))
                            if cooldown: waits.append(str(cooldown))
                        next_attempt = min(waits) if waits else None
                        reasons = {str(item.get("reason")) for item in temporary}
                        if reasons == {"PROVIDER_COOLDOWN"}:
                            wait_reasons = {
                                str(journal.providers.get(str(item.get("provider")), {}).get("wait_reason") or "TRANSIENT_PROVIDER_BACKOFF")
                                for item in temporary
                            }
                            controlled = sorted(wait_reasons)[0]
                            state = controlled.replace("_", " ").title()
                            detail = _waiting_detail(temporary, next_attempt, controlled.replace("_", " ").lower())
                        elif reasons.issubset({"CREDENTIAL_MISSING", "AUTHENTICATION_BLOCKED", "AUTHENTICATION_FAILED"}):
                            state = "Credential Repair Required"
                            detail = _waiting_detail(temporary, None, "provider credential repair")
                        else:
                            state, detail = "Waiting for Local Budget", _waiting_detail(temporary, next_attempt, "local provider budget")
                        queued.update(queue_reason=detail, waiting_reason=detail, operational_state=state, budget_wait=next_attempt, next_attempt=next_attempt)
                        recorded.update(queue_state=state, result="WAITING", reason=detail)
                        final_reason = str(recorded["reason"])
                        reason_code = (
                            "PROVIDER_COOLDOWN" if reasons == {"PROVIDER_COOLDOWN"}
                            else "PROVIDER_UNAVAILABLE" if reasons.issubset({"CREDENTIAL_MISSING", "AUTHENTICATION_BLOCKED", "AUTHENTICATION_FAILED"})
                            else "BUDGET_UNAVAILABLE"
                        )
                        record_stop(
                            journal.data, queued, cycle_id=cycle_id,
                            current_stage="ELIGIBILITY_EVALUATED",
                            reason_code=reason_code, retryable=True,
                            next_eligible_at=next_attempt, detail=detail,
                        )
                        cycle["deferred_count"] = int(cycle["deferred_count"]) + 1
                        _operator_progress(operation_progress, "waiting_for_budget")
                        break
                    if attempted and failures and all(
                        bool(item.get("retryable")) for item in failures
                    ):
                        next_attempt = max(
                            (
                                str(item.get("next_eligible_at"))
                                for item in failures if item.get("next_eligible_at")
                            ),
                            default=(observed + timedelta(seconds=_retry_delay_seconds(
                                int(queued.get("attempt_number", 1) or 1)
                            ))).isoformat(),
                        )
                        classification = str(failures[-1]["reason"])
                        diagnostic = str(failures[-1].get("detail") or classification)
                        detail = (
                            f"{diagnostic}; retained for deterministic item retry"
                            if classification == "LOCAL_PROGRAMMING_ERROR"
                            else f"{classification}; retained for deterministic item retry"
                        )
                        queued.update(
                            queue_reason=detail, waiting_reason=detail,
                            operational_state="Ready", next_attempt=next_attempt,
                            budget_wait=None,
                        )
                        recorded.update(queue_state="Ready", result="WAITING", reason=detail)
                        outcome, final_reason = "WAITING", detail
                        record_stop(
                            journal.data, queued, cycle_id=cycle_id,
                            current_stage=str(queued.get("current_stage") or "REQUEST_STARTED"),
                            reason_code=_execution_reason_code(classification), retryable=True,
                            next_eligible_at=next_attempt, detail=detail,
                        )
                        cycle["deferred_count"] = int(cycle["deferred_count"]) + 1
                        break
                    reason = "ALL_PROVIDERS_EXHAUSTED" if attempted else "NO_ELIGIBLE_PROVIDER"
                    request = create_manual_request(
                        journal.manual_requests,
                        symbol=symbol, timeframe=timeframe,
                        missing_start=bounds[0], missing_end=bounds[1],
                        expected_edge=expected_edge, reason=reason,
                        providers_attempted=sorted(attempted), failures=failures,
                        providers_considered=list(recorded.get("providers_considered", [])),
                        provider_fact_revision=int(journal.data.get("current_provider_fact_revision", 0) or 0),
                        capability_projection_revision=journal.data.get("current_capability_projection_revision"),
                        now=observed,
                    )
                    _operator_progress(operation_progress, "manual_evidence_required")
                    outcome = "FAILED"
                    final_reason = reason
                    recorded.update(
                        queue_state=None, result=outcome, reason=reason,
                        manual_request=request["id"], current_provider=None,
                    )
                    record_stop(
                        journal.data, queued, cycle_id=cycle_id,
                        current_stage="ELIGIBILITY_EVALUATED",
                        reason_code="PROVIDER_UNAVAILABLE", retryable=False,
                        detail=reason,
                    )
                    cycle["failed_count"] = int(cycle["failed_count"]) + 1
                    queue_by_id.pop(queue_id, None)
                    break
                provider = str(provider)
                activity["provider"] = provider
                profile = profiles_by_id[provider]
                request_count = int(plan["estimated_request_count"])
                protected = protected_demand.get(provider, 0) if work["work_class"] != "NORMAL" else 0
                lifecycle = _planned_request_records(
                    journal, provider=provider, lane=f"{symbol}:{timeframe}",
                    scheduled_boundary=scheduled_for, request_count=request_count,
                    now=observed,
                )
                reservation = budgets[provider].reserve(
                    request_count,
                    work_class=work["work_class"],
                    queue_percentage=queue_percentage,
                    protected_normal_demand=protected,
                    safety_reserve=profile.safety_reserve,
                )
                if not reservation["eligible"]:
                    next_attempt = reservation.get("next_available")
                    reason = str(reservation.get("reason") or "RATE_BUDGET_EXHAUSTED")
                    detail = f"{reason.replace('_', ' ').title()} — waiting for {provider} budget"
                    if next_attempt:
                        detail += f" until {next_attempt}"
                    queued.update(queue_reason=detail, waiting_reason=detail, operational_state="Waiting for Local Budget", budget_wait=next_attempt, next_attempt=next_attempt)
                    recorded.update(queue_state="Waiting for Local Budget", result="WAITING", reason=detail)
                    final_reason = reason
                    record_stop(
                        journal.data, queued, cycle_id=cycle_id,
                        current_stage="BUDGET_RESERVED",
                        reason_code="BUDGET_RESERVATION_FAILED", retryable=True,
                        next_eligible_at=next_attempt, detail=detail,
                    )
                    cycle["deferred_count"] = int(cycle["deferred_count"]) + 1
                    _operator_progress(
                        operation_progress, "waiting_for_budget",
                        provider=provider, fallback_position=len(attempted) + 1,
                    )
                    break
                reservation_id = str(reservation["reservation_id"])
                cycle["provider_calls_reserved"] = int(cycle["provider_calls_reserved"]) + request_count
                record_event(
                    journal.data, queued, "BUDGET_RESERVED", cycle_id=cycle_id,
                    provider=provider, requested_start=bounds[0], requested_end=bounds[1],
                )
                record_event(
                    journal.data, queued, "PROVIDER_SELECTED", cycle_id=cycle_id,
                    provider=provider, requested_start=bounds[0], requested_end=bounds[1],
                )
                for record in lifecycle:
                    record.update(state="RESERVED", reservation_id=reservation_id, reserved_at=observed.isoformat())
                provider_state = journal.providers.setdefault(provider, {})
                provider_state["rate_events"] = budgets[provider].persisted_events()
                provider_state["active_reservations"] = budgets[provider].persisted_reservations()
                journal.save()
                attempt_started = monotonic()
                attempt_started_at = datetime.now(UTC)
                record_timing(
                    journal.data, operation_id=str(trace_item["trace_id"]),
                    symbol=str(symbol), timeframe=str(timeframe),
                    intent=str(work["work_class"]), provider=provider,
                    step_name="planning_and_reservation", started_at=started_at,
                    ended_at=attempt_started_at,
                )
                attempted.add(provider)
                recorded["provider_attempts_by_boundary"][scheduled_for] = sorted(attempted)
                try:
                    asset_class = _asset_class(database_path, symbol)
                    def dispatched(index: int) -> None:
                        latest = SchedulerJournal(database_path, journal_path)
                        latest_authority = None
                        if not time_triggered:
                            latest_reconciliation = reconcile_operational_state(database_path, latest.data)
                            latest_authority = latest_reconciliation["universe"]["active_lanes"].get(f"{symbol}:{timeframe}")
                        if latest_authority and effective_pause_sources(
                            latest.data, symbol=symbol, group=str(latest_authority["group"])
                        ):
                            journal.data["pause_records"] = latest.data.get("pause_records", [])
                            raise _DispatchPaused("OPERATOR_PAUSED")
                        budgets[provider].dispatch(reservation_id, 1)
                        with state_lock:
                            cycle["request_started_count"] = int(cycle["request_started_count"]) + 1
                            cycle["provider_calls_started"] = int(cycle["provider_calls_started"]) + 1
                            record_event(
                                journal.data, queued, "REQUEST_STARTED", cycle_id=cycle_id,
                                provider=provider, requested_start=bounds[0], requested_end=bounds[1],
                            )
                            lifecycle[index].update(state="DISPATCHED", dispatched_at=datetime.now(UTC).isoformat())
                            state = journal.providers.setdefault(provider, {})
                            state["rate_events"] = budgets[provider].persisted_events()
                            state["active_reservations"] = budgets[provider].persisted_reservations()
                            journal.save()

                    def responded(index: int, succeeded: bool) -> None:
                        with state_lock:
                            lifecycle[index].update(
                                state="RESPONSE_RECEIVED" if succeeded else "FAILED_AFTER_DISPATCH",
                                completed_at=datetime.now(UTC).isoformat(),
                            )
                            cycle["request_completed_count"] = int(cycle["request_completed_count"]) + 1
                            cycle["provider_calls_completed"] = int(cycle["provider_calls_completed"]) + 1
                            record_event(
                                journal.data, queued, "RESPONSE_RECEIVED", cycle_id=cycle_id,
                                result="SUCCESS" if succeeded else "FAILED",
                                reason_code=None if succeeded else "HTTP_ERROR",
                                provider=provider, requested_start=bounds[0], requested_end=bounds[1],
                            )
                            _operator_progress(
                                operation_progress, "response_received",
                                provider=provider, fallback_position=len(attempted),
                            )

                    # Provider I/O, payload parsing, and candidate preparation
                    # must run without the scheduler's shared-state mutex.  The
                    # following re-acquire is the short canonical/status phase.
                    locked_before_provider_ms += max(0.0, (monotonic() - started) * 1000)
                    state_lock.release()
                    provider_slot = provider_execution_slots[provider]
                    reservation_wait_started = monotonic()
                    provider_slot.acquire()
                    reservation_wait_ms += max(
                        0.0, (monotonic() - reservation_wait_started) * 1000
                    )
                    provider_started_at = datetime.now(UTC)
                    try:
                        result = _execute_acquisition(
                            acquirer, database_path,
                            provider=provider,
                            provider_symbol=str(plan["selected_provider_symbol"]),
                            mapping_class=str(plan["selected_mapping_class"]),
                            provider_api_base_url=plan.get("selected_provider_api_base_url"),
                            asset_class=asset_class,
                            asset=symbol, timeframe=timeframe,
                            from_date=bounds[0], through_date=bounds[1],
                            merge_mode="preserve", credential=credentials.get(provider),
                            progress=progress, request_count=request_count,
                            maximum_rows=profile.maximum_rows_per_request,
                            on_dispatch=dispatched, on_response=responded,
                            credit_authority_managed=(provider == "TWELVE_DATA"),
                            expected_edge=expected_edge,
                            canonical_edge_reader=lambda: _canonical_edge(database_path, symbol, timeframe),
                            continue_from_canonical=(
                                work["work_class"] == "OPERATOR_FETCH"
                                and str(work.get("operator_fetch_mode") or "").lower() == "update"
                                and timeframe != "D1"
                            ),
                            continuation_context={
                                "function": "_execute_acquisition",
                                "lane": f"{symbol}:{timeframe}",
                                "provider": provider,
                                "operator_fetch_mode": work.get("operator_fetch_mode"),
                            },
                        )
                    finally:
                        provider_slot.release()
                        state_lock.acquire()
                        locked_after_provider_started = monotonic()
                        provider_finished_at = datetime.now(UTC)
                    canonical_commit_started_at = provider_finished_at
                    record_timing(
                        journal.data, operation_id=str(trace_item["trace_id"]),
                        symbol=str(symbol), timeframe=str(timeframe),
                        intent=str(work["work_class"]), provider=provider,
                        step_name="provider_execution_and_admission",
                        started_at=attempt_started_at, ended_at=datetime.now(UTC),
                        rows_read=int(result.get("received", 0) or 0),
                        rows_written=(int(result.get("inserted", 0) or 0) + int(result.get("corrected", 0) or 0)),
                        provider_calls=request_count,
                    )
                    sqlite_write = result.get("sqlite_write")
                    if isinstance(sqlite_write, dict):
                        wait_ms = float(sqlite_write.get("lock_wait_ms", 0) or 0)
                        cycle["database_wait_ms"] = round(
                            float(cycle["database_wait_ms"]) + wait_ms, 3
                        )
                        cycle["last_sqlite_write"] = dict(sqlite_write)
                    unused = budgets[provider].release(reservation_id)
                    if unused:
                        for record in lifecycle:
                            if record.get("state") == "RESERVED":
                                record.update(state="CANCELLED", completed_at=datetime.now(UTC).isoformat(), failure_reason="ROUTING_ESTIMATE_UNUSED")
                    received = int(result.get("received", 0) or 0)
                    admitted = int(result.get("staged", received) or 0)
                    advanced = int(result.get("inserted", 0)) + int(result.get("corrected", 0))
                    edge_after = _canonical_edge(database_path, symbol, timeframe)
                    record_event(
                        journal.data, queued, "RAW_EVIDENCE_STORED", cycle_id=cycle_id,
                        provider=provider, observations_received=received,
                        requested_start=bounds[0], requested_end=bounds[1],
                    )
                    record_event(
                        journal.data, queued, "INGESTION_COMPLETED", cycle_id=cycle_id,
                        provider=provider, observations_received=received,
                        observations_admitted=admitted,
                    )
                    canonical_commit_finished_at = datetime.now(UTC)
                    record_event(
                        journal.data, queued, "CANONICAL_EDGE_EVALUATED", cycle_id=cycle_id,
                        provider=provider, canonical_edge_before=canonical_edge,
                        canonical_edge_after=edge_after,
                    )
                    completion_edge = _completion_edge(work, bounds, expected_edge)
                    edge_advanced = _canonical_edge_advanced(canonical_edge, edge_after)
                    historical_range_satisfied = (
                        work["work_class"] == "OPERATOR_FETCH"
                        and advanced
                        and _canonical_reaches_requested_edge(edge_after, completion_edge)
                    )
                    if not advanced or (not edge_advanced and not historical_range_satisfied):
                        if time_triggered and work["work_class"] == "NORMAL" and update_register is not None:
                            # A provider's valid no-change response completes
                            # this boundary.  Re-checking it in a minute would
                            # be the reconciliation loop SPEC-063 removes.
                            update_register.record_checked(
                                asset=str(symbol), timeframe=str(timeframe),
                                checked_boundary=str(work["scheduled_boundary"]), at=observed,
                                outcome="NO_CHANGE",
                            )
                            recorded.update(queue_state=None, result="SUCCESS", reason="NO_CHANGE")
                            queue_by_id.pop(queue_id, None)
                            cycle["queue_completed_count"] = int(cycle["queue_completed_count"]) + 1
                            outcome, final_reason = "SUCCESS", "NO_CHANGE"
                            break
                        next_attempt = (observed + timedelta(seconds=60)).isoformat()
                        detail = "Provider response admitted no observation beyond the canonical edge"
                        queued.update(
                            queue_reason=detail, waiting_reason=detail,
                            operational_state="Ready", next_attempt=next_attempt,
                        )
                        recorded.update(queue_state="Ready", result="WAITING", reason="CANONICAL_UNCHANGED")
                        outcome, final_reason = "WAITING", "CANONICAL_UNCHANGED"
                        record_stop(
                            journal.data, queued, cycle_id=cycle_id,
                            current_stage="CANONICAL_EDGE_EVALUATED",
                            reason_code="CANONICAL_UNCHANGED", retryable=True,
                            next_eligible_at=next_attempt, detail=detail,
                        )
                        cycle["deferred_count"] = int(cycle["deferred_count"]) + 1
                        break
                    if edge_advanced:
                        record_event(
                            journal.data, queued, "CANONICAL_EDGE_ADVANCED", cycle_id=cycle_id,
                            provider=provider, canonical_edge_before=canonical_edge,
                            canonical_edge_after=edge_after,
                        )
                    else:
                        record_event(
                            journal.data, queued, "CANONICAL_HISTORY_EXPANDED", cycle_id=cycle_id,
                            provider=provider, canonical_edge_before=canonical_edge,
                            canonical_edge_after=edge_after,
                        )
                    cycle["canonical_advanced_count"] = int(cycle["canonical_advanced_count"]) + 1
                    observations = int(result.get("inserted", 0))
                    outcome = "SUCCESS"
                    _operator_progress(
                        operation_progress, "completed",
                        provider=provider, fallback_position=len(attempted),
                    )
                    update_provider_health(
                        journal.providers.setdefault(provider, {}), profile, outcome, observed,
                        lane=f"{symbol}:{timeframe}", request_id=lifecycle[-1]["id"] if lifecycle else None,
                        response_class="SUCCESS",
                    )
                    recorded.update(
                        queue_state=None, result=outcome, reason=None,
                        current_provider=provider,
                        publication_result={
                            "provider": provider, "inserted": int(result.get("inserted", 0)),
                            "corrected": int(result.get("corrected", 0)), "result": "PUBLISHING",
                            "provider_symbol": plan.get("selected_provider_symbol"),
                            "mapping_class": plan.get("selected_mapping_class"),
                            "authority_source": plan.get("selected_mapping_authority_source"),
                        },
                    )
                    publication_started_at = datetime.now(UTC)
                    publication_lanes.append((str(symbol), str(timeframe)))
                    record_event(
                        journal.data, queued, "PUBLICATION_ENQUEUED", cycle_id=cycle_id,
                        provider=provider, canonical_edge_before=canonical_edge,
                        canonical_edge_after=edge_after, publication_edge=edge_after,
                    )
                    if _canonical_reaches_requested_edge(edge_after, completion_edge):
                        record_event(
                            journal.data, queued, "QUEUE_COMPLETED", cycle_id=cycle_id,
                            provider=provider, canonical_edge_before=canonical_edge,
                            canonical_edge_after=edge_after, publication_edge=edge_after,
                            queue_disposition="REMOVED",
                        )
                        if _canonical_reaches_requested_edge(edge_after, expected_edge):
                            record_event(
                                journal.data, queued, "LANE_CURRENT", cycle_id=cycle_id,
                                provider=provider, canonical_edge_before=canonical_edge,
                                canonical_edge_after=edge_after, publication_edge=edge_after,
                                queue_disposition="REMOVED",
                            )
                            recorded["lifecycle_execution_state"] = "CURRENT"
                        else:
                            recorded["lifecycle_execution_state"] = "BEHIND"
                        queue_by_id.pop(queue_id, None)
                        cycle["queue_completed_count"] = int(cycle["queue_completed_count"]) + 1
                    else:
                        next_attempt = (observed + timedelta(seconds=1)).isoformat()
                        detail = "Canonical edge advanced but remains behind the requested boundary"
                        queued.update(
                            queue_reason=detail, waiting_reason=detail,
                            operational_state="Ready", next_attempt=next_attempt,
                        )
                        recorded.update(queue_state="Ready", result="WAITING", reason="QUEUE_COMPLETION_FAILED")
                        outcome, final_reason = "WAITING", "QUEUE_COMPLETION_FAILED"
                        record_stop(
                            journal.data, queued, cycle_id=cycle_id,
                            current_stage="PUBLICATION_ENQUEUED",
                            reason_code="QUEUE_COMPLETION_FAILED", retryable=True,
                            next_eligible_at=next_attempt, detail=detail,
                        )
                        cycle["deferred_count"] = int(cycle["deferred_count"]) + 1
                    break
                except BaseException as error:
                    classification, _ = classify_failure(error)
                    edge_after_failure = _canonical_edge(database_path, symbol, timeframe)
                    partial_advanced = _canonical_edge_advanced(canonical_edge, edge_after_failure)
                    if partial_advanced:
                        queued["evidence_committed"] = True
                        record_event(
                            journal.data, queued, "CANONICAL_EDGE_ADVANCED",
                            cycle_id=cycle_id, provider=provider,
                            canonical_edge_before=canonical_edge,
                            canonical_edge_after=edge_after_failure,
                        )
                        canonical_edge = edge_after_failure
                        bounds = _resume_bounds_from_canonical(
                            asset_class, timeframe, bounds, edge_after_failure
                        )
                    released = budgets[provider].release(reservation_id)
                    if released:
                        for record in lifecycle:
                            if record.get("state") == "RESERVED":
                                record.update(
                                    state="FAILED_BEFORE_DISPATCH", completed_at=datetime.now(UTC).isoformat(),
                                    failure_reason=classification,
                                )
                    if isinstance(error, _DispatchPaused):
                        for record in lifecycle:
                            if record.get("state") in {"PLANNED", "RESERVED", "FAILED_BEFORE_DISPATCH"}:
                                record.update(state="CANCELLED", completed_at=datetime.now(UTC).isoformat(), failure_reason="OPERATOR_PAUSED")
                        queued.update(
                            operational_state="Operator Paused", waiting_reason="OPERATOR_PAUSED",
                            queue_reason="Dispatch paused by operator", next_attempt=None, budget_wait=None,
                        )
                        recorded.update(queue_state="Operator Paused", result="WAITING", reason="OPERATOR_PAUSED")
                        outcome, final_reason = "WAITING", "OPERATOR_PAUSED"
                        record_stop(
                            journal.data, queued, cycle_id=cycle_id,
                            current_stage="REQUEST_STARTED", reason_code="DISPATCH_REJECTED",
                            retryable=True, detail="OPERATOR_PAUSED",
                        )
                        cycle["deferred_count"] = int(cycle["deferred_count"]) + 1
                        break
                    detail = _execution_failure_detail(
                        classification, error, function="_execute_acquisition",
                        lane=f"{symbol}:{timeframe}", provider=provider,
                        bounds=bounds, expected_edge=expected_edge,
                        canonical_edge_before=work.get("canonical_edge"),
                        canonical_edge_after=edge_after_failure,
                    )
                    if bool(getattr(error, "evidence_committed", False)):
                        queued["evidence_committed"] = True
                    if classification == "TWELVEDATA_RATE_LIMIT_429" and hasattr(budgets[provider], "record_429"):
                        budget_state = budgets[provider].record_429(
                            response_body=bytes(getattr(error, "response_body", b"") or b""),
                            retry_after=getattr(error, "retry_after", None), endpoint="time_series",
                        )
                        journal.providers.setdefault(provider, {})["last_429_at"] = budget_state.get("last_429_at")
                    if classification.startswith("TWELVEDATA_") or classification in {
                        "CREDENTIAL_MISSING", "AUTHENTICATION_FAILED", "QUOTA_EXCEEDED",
                        "ENTITLEMENT_BLOCKED",
                    }:
                        update_provider_health(
                            journal.providers.setdefault(provider, {}), profile, classification, observed,
                            lane=f"{symbol}:{timeframe}", request_id=lifecycle[-1]["id"] if lifecycle else None,
                            response_class=classification,
                        )
                    domain_counts = cycle["requests_failed_by_domain"]
                    assert isinstance(domain_counts, dict)
                    domain_counts[classification] = int(domain_counts.get(classification, 0)) + 1
                    retry_at = (
                        budgets[provider].inspect().get("rate_limit_until")
                        if classification == "TWELVEDATA_RATE_LIMIT_429" else None
                    ) or (observed + timedelta(seconds=_retry_delay_seconds(
                        int(queued.get("attempt_number", 1) or 1)
                    ))).isoformat()
                    retryable = _retryable_failure(classification) or partial_advanced
                    failure = {
                        "provider": provider, "result": _structured_provider_result(classification), "reason": classification,
                        "detail": detail, "at": datetime.now(UTC).isoformat(),
                        "duration_seconds": round(monotonic() - attempt_started, 3),
                        "retryable": retryable, "next_eligible_at": retry_at if retryable else None,
                        "request_bounds": {"start": bounds[0], "end": bounds[1]},
                        "canonical_edge_before": work.get("canonical_edge"),
                        "canonical_edge_after": edge_after_failure,
                    }
                    failures.append(failure)
                    record_stop(
                        journal.data, queued, cycle_id=cycle_id,
                        current_stage="REQUEST_STARTED",
                        reason_code=_execution_reason_code(classification),
                        retryable=retryable,
                        next_eligible_at=retry_at if retryable else None,
                        detail=detail,
                    )
                    history = recorded.setdefault("attempt_history", [])
                    history.insert(0, failure)
                    del history[_EVENT_LIMIT:]
                    next_plan = acquisition_plan(
                        database_path, symbol=symbol, timeframe=timeframe,
                        canonical_edge=canonical_edge, expected_edge=expected_edge,
                        missing_start=bounds[0], missing_end=bounds[1],
                        scheduled_boundary=scheduled_for, profiles=profiles,
                        provider_state=journal.providers, budgets=budgets,
                        credentials=credentials, now=observed,
                        attempted_providers=attempted,
                        work_class=work["work_class"],
                        queue_percentage=queue_percentage,
                        protected_demand=protected_demand if work["work_class"] != "NORMAL" else {},
                    )
                    _operator_progress(
                        operation_progress, "failed_over",
                        provider=provider,
                        next_provider=next_plan.get("selected_provider"),
                        fallback_position=len(attempted) + 1,
                    )
                    journal.append_event({
                        "id": f"failover:{symbol}:{timeframe}:{provider}:{datetime.now(UTC).isoformat()}",
                        "at": datetime.now(UTC).isoformat(), "symbol": symbol,
                        "timeframe": timeframe, "scheduled_boundary": scheduled_for,
                        "provider": provider, "result": "FAILED", "reason": classification,
                        "next_provider": next_plan.get("selected_provider"),
                        "duration_seconds": failure["duration_seconds"], "observations": 0,
                    })
                    if retryable:
                        continue
                    if classification == "TWELVEDATA_INVALID_RESPONSE":
                        continue
                    final_reason = detail if classification == "LOCAL_PROGRAMMING_ERROR" else classification
                    recorded.update(queue_state=None, result="FAILED", reason=final_reason)
                    queue_by_id.pop(queue_id, None)
                    cycle["failed_count"] = int(cycle["failed_count"]) + 1
                    break
        except BaseException as error:
            classification, _detail = classify_failure(error)
            retryable = _retryable_failure(classification)
            outcome = "WAITING" if retryable else "FAILED"
            detail = _execution_failure_detail(
                classification, error, function="scheduler_preflight",
                lane=f"{symbol}:{timeframe}", provider=str(activity.get("provider") or "NONE"),
                bounds=bounds, expected_edge=expected_edge,
                canonical_edge_before=work.get("canonical_edge"),
                canonical_edge_after=_canonical_edge(database_path, symbol, timeframe),
            )
            final_reason = detail if classification == "LOCAL_PROGRAMMING_ERROR" else classification
            next_attempt = (
                observed + timedelta(seconds=_retry_delay_seconds(
                    int(trace_item.get("attempt_number", 1) or 1)
                ))
            ).isoformat() if retryable else None
            recorded.update(
                queue_state="Ready" if retryable else None,
                result=outcome, reason=final_reason,
            )
            failures.append({
                "provider": None,
                "result": _structured_provider_result(classification),
                "reason": classification,
                "detail": detail,
                "at": datetime.now(UTC).isoformat(),
                "duration_seconds": round(monotonic() - started, 3),
                "retryable": retryable,
                "next_eligible_at": next_attempt,
                "request_bounds": {"start": bounds[0], "end": bounds[1]},
                "canonical_edge_before": work.get("canonical_edge"),
                "canonical_edge_after": _canonical_edge(database_path, symbol, timeframe),
            })
            if retryable:
                trace_item.update(
                    operational_state="Ready", waiting_reason=classification,
                    queue_reason=classification, next_attempt=next_attempt,
                    evidence_committed=bool(getattr(error, "evidence_committed", False)),
                )
            record_stop(
                journal.data, trace_item, cycle_id=cycle_id,
                current_stage=str(trace_item.get("current_stage") or "DISPATCH_STARTED"),
                reason_code=_execution_reason_code(classification), retryable=retryable,
                next_eligible_at=next_attempt,
                detail=detail,
            )
            domain_counts = cycle["requests_failed_by_domain"]
            assert isinstance(domain_counts, dict)
            domain_counts[classification] = int(domain_counts.get(classification, 0)) + 1
            if retryable:
                cycle["deferred_count"] = int(cycle["deferred_count"]) + 1
            else:
                cycle["failed_count"] = int(cycle["failed_count"]) + 1
                queue_by_id.pop(queue_id, None)
        recorded["duration_seconds"] = round(monotonic() - started, 3)
        completed_timestamp = datetime.now(UTC)
        locked_after_provider_ms = (
            max(0.0, (monotonic() - locked_after_provider_started) * 1000)
            if locked_after_provider_started is not None else 0.0
        )
        provider_duration_ms = (
            max(0.0, (provider_finished_at - provider_started_at).total_seconds() * 1000)
            if provider_started_at and provider_finished_at else 0.0
        )
        publication_duration_ms = (
            max(0.0, (completed_timestamp - publication_started_at).total_seconds() * 1000)
            if publication_started_at else 0.0
        )
        record_timing(
            journal.data, operation_id=str(trace_item["trace_id"]),
            symbol=str(symbol), timeframe=str(timeframe),
            intent=str(work["work_class"]), provider=activity.get("provider"),
            step_name="lane_execution", started_at=started_at, ended_at=completed_timestamp,
            blocking_reason=str(recorded.get("reason") or final_reason) if (recorded.get("reason") or final_reason) else None,
            rows_written=observations,
            queued_at=_as_utc_datetime(trace_item.get("enqueued_at")),
            provider_started_at=provider_started_at,
            provider_finished_at=provider_finished_at,
            canonical_commit_started_at=canonical_commit_started_at,
            canonical_commit_finished_at=canonical_commit_finished_at,
            completed_at=completed_timestamp,
            duration_total_ms=max(0.0, (completed_timestamp - started_at).total_seconds() * 1000),
            duration_provider_ms=provider_duration_ms,
            duration_locked_ms=locked_before_provider_ms + locked_after_provider_ms,
            duration_publication_ms=publication_duration_ms,
            worker_id=worker_id,
            lock_wait_ms=lock_wait_ms,
            reservation_wait_ms=reservation_wait_ms,
        )
        event = {
            "id": f"{symbol}:{timeframe}:{started_at.isoformat()}",
            "at": datetime.now(UTC).isoformat(),
            "symbol": symbol,
            "timeframe": timeframe,
            "result": outcome,
            "observations": observations,
            "duration_seconds": recorded["duration_seconds"],
            "reason": recorded.get("reason") or final_reason,
            "work_class": work["work_class"],
        }
        if work["work_class"] == "OPERATOR_FETCH":
            operator_outcome = "MANUAL_REQUIRED" if recorded.get("manual_request") else outcome
            recorded["last_operator_fetch_result"] = {
                "operation_id": work.get("operator_fetch_id"),
                "work_class": "OPERATOR_FETCH",
                "requested_range": {"start": bounds[0], "end": bounds[1]},
                "canonical_edge_before": work.get("canonical_edge"),
                "canonical_edge_after": _canonical_edge(database_path, symbol, timeframe),
                "expected_edge": work.get("expected_edge"),
                "providers_considered": recorded.get("providers_considered", []),
                "providers_attempted": sorted(attempted),
                "provider_results": failures + ([recorded.get("publication_result")] if recorded.get("publication_result") else []),
                "published_observations": observations,
                "authority_revision": _lane_revision(database_path, symbol, timeframe),
                "freshness_result": _lane_freshness(database_path, symbol, timeframe, observed),
                "manual_request_created": recorded.get("manual_request"),
                "outcome": operator_outcome,
                "reason": recorded.get("reason") or final_reason,
                "completed_at": datetime.now(UTC).isoformat(),
            }
            # A credit-window or transient provider wait is not a completed
            # operator request.  Keep its durable intent so the next normal
            # service wake can promote the same request again.  Removing this
            # marker left a queue row with no dispatch owner and made initial
            # M5 history appear permanently "in progress".
            if outcome == "SUCCESS" or not time_triggered:
                recorded.pop("operator_fetch_pending", None)
        if time_triggered and update_register is not None and (
            work["work_class"] == "NORMAL" or bool(work.get("_register_claimed"))
        ):
            try:
                if work["work_class"] != "NORMAL":
                    # The explicit fetch replaced an already claimed normal
                    # boundary. It may be historical and therefore cannot
                    # prove that boundary complete; make the original claim
                    # immediately eligible for its own bounded check.
                    update_register.retry(
                        asset=str(symbol), timeframe=str(timeframe),
                        reason="OPERATOR_FETCH_SUPERSEDED_NORMAL",
                        at=observed, not_before=observed,
                    )
                elif outcome == "SUCCESS":
                    update_register.record_checked(
                        asset=str(symbol), timeframe=str(timeframe),
                        checked_boundary=str(work["scheduled_boundary"]), at=observed,
                        outcome="CANONICAL_ADVANCED" if observations else "NO_CHANGE",
                    )
                elif outcome == "WAITING":
                    wait = _as_utc_datetime(trace_item.get("next_attempt"))
                    update_register.retry(
                        asset=str(symbol), timeframe=str(timeframe),
                        reason=str(recorded.get("reason") or final_reason or "RETRY"),
                        at=observed, not_before=wait,
                    )
                else:
                    update_register.block(
                        asset=str(symbol), timeframe=str(timeframe),
                        reason=str(recorded.get("reason") or final_reason or "FAILED"), at=observed,
                    )
            except (KeyError, ValueError):
                # A concurrently requested Audit may have retired a lane.
                # Keep canonical work safe and let the explicit audit report it.
                pass
        journal.append_event(event)
        trace_item.pop("active_worker_id", None)
        cycle["active_workers"] = max(0, int(cycle["active_workers"]) - 1)
        cycle["available_workers"] = max(0, worker_limit - int(cycle["active_workers"]))
        journal.data["acquisition_queue"] = list(queue_by_id.values())
        for profile in profiles:
            journal.providers.setdefault(profile.provider, {})["rate_events"] = budgets[profile.provider].persisted_events()
            journal.providers.setdefault(profile.provider, {})["active_reservations"] = budgets[profile.provider].persisted_reservations()
        journal.save()
        if emit and not time_triggered:
            emit(scheduler_snapshot(database_path, clock=lambda: observed, journal_path=journal_path, credential=credential, provider_profiles=profiles))

    def guarded_execute(work: dict[str, object]) -> None:
        symbol, timeframe = str(work["symbol"]), str(work["timeframe"])
        if not _claim_lane_execution(database_path, symbol, timeframe):
            # A duplicate has attached to the existing lane execution rather
            # than creating a second canonical writer.
            return
        lock_wait_started = monotonic()
        state_lock.acquire()
        try:
            execute_selected_work(
                work, lock_wait_ms=max(0.0, (monotonic() - lock_wait_started) * 1000),
            )
        finally:
            state_lock.release()
            _release_lane_execution(database_path, symbol, timeframe)

    if concurrent_execution:
        with ThreadPoolExecutor(
            max_workers=worker_limit, thread_name_prefix="scheduler-acquisition"
        ) as executor:
            list(executor.map(guarded_execute, selected_due))
    else:
        for work in selected_due:
            guarded_execute(work)
    # Enqueue the publication delta after provider workers complete.  Full
    # estate/status projection remains outside worker allocation.
    publication_started = monotonic()
    publication_job = None if defer_publication else enqueue_publication(
        database_path, publication_lanes, trigger="SCHEDULER_CYCLE"
    )
    cycle["publication_duration_ms"] = round(
        max(0.0, (monotonic() - publication_started) * 1000), 3
    )
    if publication_job:
        publication_enqueued_at = datetime.now(UTC)
        for symbol, timeframe in publication_lanes:
            journal.lane(symbol, timeframe).setdefault("publication_result", {}).update(
                state="PUBLISHING", publication_job_id=publication_job["id"],
                publication_revision_before=publication_job["publication_revision_before"],
            )
        record_timing(
            journal.data, operation_id=str(publication_job["id"]), symbol=None,
            timeframe=None, intent="PUBLICATION", step_name="publication_enqueued",
            started_at=publication_enqueued_at, ended_at=datetime.now(UTC),
            publication_revision=str(publication_job["publication_revision_before"]),
            rows_written=len(publication_lanes),
            trigger="SCHEDULER_CYCLE",
            changed_lanes=[f"{symbol}:{timeframe}" for symbol, timeframe in publication_lanes],
            changed_symbols=list(publication_job["changed_symbols"]),
            publication_revision_before=int(publication_job["publication_revision_before"]),
            sync_blocking_ms=0.0,
        )
    completed_at = datetime.now(UTC)
    queue_after = [
        item for item in journal.data.get("acquisition_queue", [])
        if isinstance(item, dict)
    ]
    next_intended = cycle_started_at + timedelta(seconds=5)
    elapsed_seconds = max(0.0, monotonic() - cycle_started)
    overrun_ms = max(0.0, (elapsed_seconds - 5.0) * 1000)
    cycle.update({
        "completed_at": completed_at.isoformat(),
        "duration_ms": round(elapsed_seconds * 1000, 3),
        "next_intended_cycle": next_intended.isoformat(),
        "cycle_overrun": overrun_ms > 0,
        "cycle_overrun_ms": round(overrun_ms, 3),
        "queue_depth_after": len(queue_after),
        "oldest_queue_age_after": oldest_queue_age(queue_after, completed_at),
        "oldest_ready_item_age_seconds": oldest_queue_age(
            [item for item in queue_after if item.get("operational_state") == "Ready"], completed_at
        ),
        "provider_budget_remaining": sum(
            int(budgets[profile.provider].inspect(work_class="NORMAL")["calls_available"])
            for profile in profiles if profile.budget_unit == "requests"
        ),
    })
    twelve_budget = budgets.get("TWELVE_DATA")
    twelve_state = twelve_budget.inspect() if twelve_budget is not None else {}
    cycle["credits_consumed"] = int(twelve_state.get("credits_consumed", twelve_state.get("calls_used", 0)) or 0)
    cycle["credits_remaining"] = int(twelve_state.get("credits_remaining", twelve_state.get("calls_available", 0)) or 0)
    cycle["dispatch_rate_per_minute"] = float(twelve_state.get("dispatch_rate_per_minute", 0) or 0)
    cycle["worker_utilisation"] = round(
        min(1.0, int(cycle["worker_allocated_count"]) / max(1, int(cycle["selected_count"]))), 3
    )
    cycle["scheduler_dispatch_slots_missed_database"] = math.floor(
        float(cycle["database_wait_ms"]) / 1200.0
    )
    cycle["throughput_limited_by"] = _throughput_limiter(cycle)
    if int(cycle["worker_allocated_count"]) == 0 and not cycle["no_worker_started_reason"]:
        cycle["no_worker_started_reason"] = (
            "No eligible queue work" if int(cycle["eligible_count"]) == 0
            else "No dispatch attempt was made"
        )
    if bool(cycle["cycle_overrun"]):
        cycle["cycle_overrun_reason"] = (
            "Cycle exceeded the five-second liveness interval; catch-up dispatch scheduled"
        )
    record_timing(
        journal.data, operation_id=cycle_id, symbol=None, timeframe=None,
        intent="SCHEDULER_CYCLE", step_name="cycle_total",
        started_at=cycle_started_at, ended_at=completed_at,
        provider_calls=int(cycle["provider_calls_started"]),
        rows_written=int(cycle["canonical_advanced_count"]),
    )
    append_cycle(journal.data, cycle)
    journal.save()
    if time_triggered and update_register is not None:
        return _time_triggered_runtime_snapshot(journal, update_register, cycle, at=observed)
    return scheduler_snapshot(database_path, clock=lambda: observed, journal_path=journal_path, credential=credential, provider_profiles=profiles)


class SchedulerService:
    def __init__(
        self,
        database_path: str | Path,
        *,
        credential: str | None,
        journal_path: str | Path | None = None,
        clock: Callable[[], datetime] | None = None,
        credential_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self.database_path = database_path
        self.credential = credential
        self.credential_provider = credential_provider
        self.journal_path = journal_path
        self.clock = clock or (lambda: datetime.now(UTC))
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()
        self.wake_event.set()

    def wake(self) -> None:
        self.wake_event.set()

    def current_credential(self) -> str | None:
        if self.credential_provider is not None:
            self.credential = self.credential_provider()
        return self.credential

    def run_forever(self, emit: Callable[[dict[str, object]], None]) -> None:
        # Dispatch leads monitoring.  A full estate/status projection can take
        # materially longer than a scheduler cadence on a large estate, so it
        # must never sit in front of the first ready-queue worker allocation.
        idle_revision: tuple[tuple[str, int | None, int | None], ...] | None = None
        idle_refresh_at = 0.0
        startup_recovery_pending = True
        while not self.stop_event.is_set():
            if idle_revision is not None:
                # Do not turn a past-due, non-dispatchable queue item into a
                # full estate reconciliation loop.  Commands wake immediately;
                # independent authority writers are noticed by the cheap stat
                # fingerprint within the existing five-second poll interval.
                remaining = max(0.0, idle_refresh_at - time.monotonic())
                self.wake_event.wait(min(_IDLE_INPUT_POLL_SECONDS, remaining))
                was_woken = self.wake_event.is_set()
                self.wake_event.clear()
                if self.stop_event.is_set():
                    break
                if (
                    not was_woken
                    and time.monotonic() < idle_refresh_at
                    and _idle_input_revision(self.database_path, self.journal_path) == idle_revision
                ):
                    continue
                idle_revision = None
            credential = self.current_credential()
            register = LaneUpdateRegister(self.database_path)
            if startup_recovery_pending:
                # A new service instance owns acquisition before it reaches
                # this loop, so RUNNING rows belong to an interrupted prior
                # instance and are safe to make retryable.
                register.recover_running(at=self.clock())
                startup_recovery_pending = False
            if register.audit_due(at=self.clock()):
                # Weekly maintenance is intentionally the one recurring
                # full-estate audit.  Routine wakes below remain indexed.
                run_estate_audit(
                    self.database_path, at=self.clock(), trigger="WEEKLY_MAINTENANCE",
                )
            # The register-driven executor returns a compact runtime summary;
            # provider work therefore never waits behind an estate monitor
            # projection.
            snapshot = run_due_acquisitions(
                self.database_path,
                at=self.clock(),
                credential=credential,
                journal_path=self.journal_path,
                catch_up=True,
                emit=None,
                time_triggered=True,
            )
            emit(snapshot)
            if _stable_past_due_no_work(snapshot, self.clock()):
                idle_revision = _idle_input_revision(self.database_path, self.journal_path)
                idle_refresh_at = time.monotonic() + _IDLE_NO_WORK_RECONCILIATION_SECONDS
                continue
            if snapshot["next_run"] is None:
                # Provider-fact files are a separate atomic authority. Polling is
                # the fallback wake path for writers outside the native command channel.
                self.wake_event.wait(5.0)
                self.wake_event.clear()
                continue
            next_run = datetime.fromisoformat(snapshot["next_run"])
            delay = (next_run - normalized_utc(self.clock())).total_seconds()
            if delay <= 0 and not snapshot.get("active_activity"):
                dispatch = snapshot.get("dispatch_state")
                if isinstance(dispatch, dict) and (
                    dispatch.get("next_wake_reason") == "READY_CAPACITY_CATCH_UP"
                    or snapshot.get("next_due_check")
                ):
                    # Cycle overrun and ready work are catch-up conditions, not
                    # permission to fall back to a passive cadence sleep.
                    delay = float(time_triggered_pacing(
                        snapshot.get("scheduler_policy_key", "BALANCED"),
                        provider_worker_limit=1,
                    )["catch_up_delay_seconds"])
                else:
                    # A malformed/stale schedule still needs a bounded retry,
                    # but it cannot spin the service.
                    delay = 30.0
            else:
                delay = max(0.0, delay)
            self.wake_event.wait(delay)
            self.wake_event.clear()

    def run_monitor_only(self, emit: Callable[[dict[str, object]], None]) -> None:
        """Signed acceptance mode: live monitor/control refresh with no dispatch."""
        while not self.stop_event.is_set():
            credential = self.current_credential()
            emit(scheduler_snapshot(
                self.database_path, clock=self.clock, journal_path=self.journal_path,
                credential=credential, service_state="Running",
            ))
            self.wake_event.wait(5.0)
            self.wake_event.clear()


def _scheduler_commissioning_projection(database_path,freshness_report,universe):
    active_lanes=universe["active_lanes"]
    registrations={
        (str(row["symbol"]),str(row["asset_class"]))
        for row in active_lanes.values() if row["timeframe"] == "D1"
    }
    commissioned={
        (str(row["symbol"]),str(row["timeframe"]))
        for row in active_lanes.values()
    }
    with open_read_only(database_path) as connection:
        counts={
            (str(row[0]),str(row[1])):int(row[2])
            for row in connection.execute(
                "SELECT l.asset,l.timeframe,(SELECT count(*) FROM bars b WHERE b.asset=l.asset AND b.timeframe=l.timeframe) FROM evidence_lanes l"
            ).fetchall()
        }
    states={
        (str(row["symbol"]),str(row["timeframe"])):str(row["freshness"]["state"])
        for row in freshness_report["lanes"]
    }
    operational={key for key in commissioned if counts.get(key,0) > 0}
    return project_required_lanes(
        sorted(registrations),commissioned,evidence_counts=counts,
        operational_states=states,operational_lanes=operational,
    )


def audit_estate(
    database_path: str | Path,
    *,
    at: datetime | None = None,
    reason: str = "OPERATOR_REQUEST",
) -> dict[str, object]:
    """Explicitly reconcile scheduler runtime state with the active estate.

    This is deliberately separate from ``run_due_acquisitions`` so normal
    upkeep cannot accidentally turn an ordinary wake into an estate scan.
    """
    return run_estate_audit(database_path, at=at, trigger=reason)


def _due_lanes_from_register(
    database_path: str | Path,
    observed: datetime,
    register: LaneUpdateRegister,
    *,
    max_tasks: int,
) -> list[dict[str, object]]:
    """Build acquisition facts for the already-selected, due register rows."""
    claimed = register.claim_due(at=observed, limit=max(1, int(max_tasks)))
    result: list[dict[str, object]] = []
    with open_read_only(database_path) as connection:
        for entry in claimed:
            symbol, timeframe = str(entry["asset"]), str(entry["timeframe"])
            registration = connection.execute(
                "SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
                (symbol,),
            ).fetchone()
            if registration is None:
                register.block(asset=symbol, timeframe=timeframe, reason="REGISTRATION_UNAVAILABLE", at=observed)
                continue
            freshness = assess_lane_freshness(
                connection, symbol=symbol, timeframe=timeframe, as_of=observed
            )
            expected = freshness.get("expected_latest")
            if not expected:
                register.block(
                    asset=symbol, timeframe=timeframe,
                    reason=str(freshness.get("reason_code") or "EXPECTED_EDGE_UNAVAILABLE"), at=observed,
                )
                continue
            boundary = str(entry.get("next_expected_boundary_utc") or entry["next_check_at_utc"])
            result.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "asset_class": str(registration[0]),
                "scheduled_boundary": boundary,
                "canonical_edge": freshness.get("latest_canonical_observation"),
                "expected_edge": expected,
                "missing_range": {
                    "start": freshness.get("latest_canonical_observation"),
                    "end": expected,
                },
                "missed_boundaries": 1,
                "retry_due": entry["state"] == "RETRY",
                "work_class": "NORMAL",
                "operator_fetch_id": None,
                "operator_fetch_mode": None,
                "requested_bounds": None,
                "next_attempt": entry.get("retry_not_before_utc"),
                "enqueued_at": entry.get("last_attempted_at_utc") or observed.isoformat(),
                "queue_age_seconds": 0.0,
                "dispatch_priority": "CURRENT_BOUNDARY",
                "queue_reason": "Time-triggered approved boundary due",
                "register_state": entry["state"],
            })
    return result


def _pending_operator_fetches(
    database_path: str | Path,
    observed: datetime,
    journal: SchedulerJournal,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Promote explicit fetch requests without scanning ordinary due work.

    The time-triggered scheduler normally consults only ``LaneUpdateRegister``.
    Operator Fetch intentionally takes a separate, narrow path: its request is
    already durable in the journal, and this function reads authority only when
    at least one such request exists to confirm that its lane is still active.
    """
    pending = [
        (str(lane_id), state, state.get("operator_fetch_pending"))
        for lane_id, state in journal.data.get("lanes", {}).items()
        if isinstance(state, dict) and isinstance(state.get("operator_fetch_pending"), dict)
    ]
    if not pending:
        return [], {"active_lanes": {}}

    universe = active_universe(database_path)
    active = universe["active_lanes"]
    result: list[dict[str, object]] = []
    with open_read_only(database_path) as connection:
        for lane_id, _recorded, request in pending:
            if not isinstance(request, dict) or ":" not in lane_id:
                continue
            symbol, timeframe = lane_id.rsplit(":", 1)
            authority = active.get(lane_id)
            if authority is None:
                # Operator work is never allowed to revive a retired or
                # uncommissioned lane.  Reconciliation/audit owns archival.
                continue
            start, end = request.get("requested_start"), request.get("requested_end")
            if not isinstance(start, str) or not start or not isinstance(end, str) or not end:
                continue
            freshness = assess_lane_freshness(
                connection, symbol=symbol, timeframe=timeframe, as_of=observed
            )
            requested_start: object = start
            if (
                str(request.get("requested_mode") or "").lower() == "initial"
                and timeframe != "D1"
                and freshness.get("latest_canonical_observation")
                and not request.get("backfill_from_start", False)
            ):
                requested_start = _advance_start_bound(
                    str(authority["asset_class"]), timeframe, requested_start,
                    freshness.get("latest_canonical_observation"),
                )
            result.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "asset_class": str(authority["asset_class"]),
                "scheduled_boundary": f"OPERATOR_FETCH:{request.get('id')}",
                "canonical_edge": freshness.get("latest_canonical_observation"),
                "expected_edge": freshness.get("expected_latest"),
                "missing_range": {"start": requested_start, "end": end},
                "missed_boundaries": int((freshness.get("lag") or {}).get("count") or 1),
                "retry_due": False,
                "work_class": "OPERATOR_FETCH",
                "operator_fetch_id": request.get("id"),
                "operator_fetch_mode": request.get("requested_mode"),
                "requested_bounds": [requested_start, end],
                "next_attempt": None,
                "enqueued_at": request.get("requested_at") or observed.isoformat(),
                "queue_age_seconds": 0.0,
                "dispatch_priority": "OPERATOR_FETCH",
                "queue_reason": "Operator Fetch requested",
                "register_state": None,
            })
    return sorted(result, key=_operational_dispatch_key), universe


def _time_triggered_runtime_snapshot(
    journal: SchedulerJournal,
    register: LaneUpdateRegister,
    cycle: dict[str, object],
    *,
    at: datetime,
) -> dict[str, object]:
    """Compact monitor payload for normal scheduler wakes.

    It is sourced from the register and bounded runtime summaries, not a
    freshness projection or decoded estate journal.
    """
    register_summary = register.summary()
    due_now = register.due_count(at=at)
    selected_policy = _scheduler_policy(journal)
    register_summary = {**register_summary, "due_now_count": due_now}
    dashboard = register.dashboard_rows(limit=24)
    running = next((row for row in dashboard if row.get("state") == "RUNNING"), None)
    # A freshly seeded register can have due work before its first completed
    # cycle. Its current indexed dispatch plan is meaningful progress, not a
    # stalled worker pool.
    last_progress = cycle.get("completed_at") or cycle.get("started_at") or at.isoformat()
    progress = {
        "contract": "fragarach_ii.scheduler_progress.v1",
        "actionable_queue_depth": due_now,
        "blocked_queue_depth": int(register_summary["blocked_count"]),
        "total_queue_depth": (
            due_now + int(register_summary["blocked_count"])
            + int(register_summary["running_count"])
        ),
        "oldest_actionable_age_seconds": None,
        "active_workers": int(cycle.get("active_workers", 0) or 0),
        "available_workers": int(cycle.get("available_workers", 0) or 0),
        "permitted_progress_window_seconds": max(
            45.0, float(cycle.get("duration_ms", 0) or 0) / 1000.0 * 2.0,
        ),
        "last_meaningful_progress": last_progress,
        "last_meaningful_progress_age_seconds": 0.0 if last_progress else None,
        "stalled": False,
        "current_lane": (
            f"{running['asset']}:{running['timeframe']}" if running else None
        ),
        "current_trace_id": None,
        "current_stage": "REGISTER_CATCH_UP" if due_now or running else None,
        "current_stop_reason": None,
    }
    queue = [item for item in journal.data.get("acquisition_queue", []) if isinstance(item, dict)]
    queue_depths = {
        "normal": int(register_summary["ready_count"]) + int(register_summary["retrying_count"]),
        "repair": sum(item.get("work_class") in {"QUEUE", "OPERATOR_RETRY"} for item in queue),
        "historical_backfill": sum(item.get("dispatch_priority") == "HISTORICAL_CATCH_UP" for item in queue),
        "operator_fetch": sum(item.get("work_class") == "OPERATOR_FETCH" for item in queue),
    }
    return {
        "contract": SCHEDULER_CONTRACT,
        "scheduler_mode": "TIME_TRIGGERED_REGISTER",
        "register_contract": REGISTER_CONTRACT,
        "authority_change_token": _authority_change_token(register.database_path),
        "next_run": register_summary["next_due_check"],
        "next_due_check": register_summary["next_due_check"],
        "queue_depths": queue_depths,
        "register": register_summary,
        "scheduler_policy": policy_label(selected_policy),
        "scheduler_policy_key": selected_policy,
        # A fixed small horizon restores operational schedule visibility
        # without reintroducing the old full-estate monitor projection.
        "schedule_dashboard": dashboard,
        # A separate bounded indexed read lets operators inspect every
        # concrete lane behind the Overview's blocked count.
        "blocked_schedule_dashboard": register.blocked_rows(limit=100),
        "audit": audit_status(register.database_path),
        "execution": dict(cycle),
        "scheduler_progress": progress,
        "dispatch_state": {
            "next_wake_reason": "READY_CAPACITY_CATCH_UP" if due_now else "REGISTER_NEXT_DUE",
            "due_now_count": due_now,
        },
        "active_activity": None,
    }


def _due_lanes(database_path, observed, journal, *, catch_up):
    result = []
    prior = observed - timedelta(microseconds=1)
    with open_read_only(database_path) as connection:
        commissioned=commissioned_lane_keys(connection)
        lanes = connection.execute(
            """SELECT l.asset,l.timeframe,r.asset_class
               FROM evidence_lanes l
               JOIN instrument_registrations r
                 ON r.asset=l.asset AND r.timeframe=l.registration_timeframe
               ORDER BY l.asset,l.timeframe"""
        ).fetchall()
        for symbol, timeframe, asset_class in lanes:
            freshness = assess_lane_freshness(
                connection, symbol=symbol, timeframe=timeframe, as_of=observed
            )
            schedule = schedule_for_lane(
                connection, symbol=symbol, timeframe=timeframe, after=prior
            )
            scheduled_for = schedule.get("next_scheduled_acquisition")
            if not scheduled_for:
                continue
            boundary = datetime.fromisoformat(scheduled_for)
            missing_edge = freshness.get("expected_latest") and (
                freshness["state"] == "Behind"
                or freshness.get("latest_canonical_observation") is None
            )
            boundary_due = boundary <= observed
            recorded = journal.lane(symbol, timeframe)
            operator_fetch = recorded.get("operator_fetch_pending")
            if not isinstance(operator_fetch, dict):
                operator_fetch = None
            if (str(symbol),str(timeframe)) not in commissioned and not operator_fetch:
                continue
            operator_retry = bool(recorded.get("operator_retry_pending", False))
            if (not missing_edge and not operator_fetch) or (
                not catch_up and not boundary_due and not operator_retry and not operator_fetch
            ):
                continue
            attempt_key = (
                scheduled_for
                if boundary_due
                else f"CATCH_UP:{freshness['expected_latest']}"
            )
            if operator_retry:
                attempt_key = f"OPERATOR_RETRY:{freshness['expected_latest']}"
            if operator_fetch:
                attempt_key = f"OPERATOR_FETCH:{operator_fetch['id']}"
            if (
                recorded.get("last_scheduled_acquisition") == attempt_key
                and recorded.get("result") != "WAITING"
                and not operator_retry and not operator_fetch
            ):
                continue
            lag = freshness.get("lag") or {}
            missed = int(lag.get("count") or 1)
            retry_due = bool(recorded.get("result") in {"FAILED", "WAITING"})
            if operator_retry:
                recorded.pop("operator_retry_pending", None)
                recorded.setdefault("provider_attempts_by_boundary", {}).pop(attempt_key, None)
            next_attempt = next(
                (
                    item.get("next_attempt")
                    for item in journal.data.get("acquisition_queue", [])
                    if item.get("lane") == f"{symbol}:{timeframe}"
                ),
                None,
            )
            enqueued_at = next(
                (
                    item.get("enqueued_at")
                    for item in journal.data.get("acquisition_queue", [])
                    if item.get("lane") == f"{symbol}:{timeframe}"
                ),
                None,
            )
            if next_attempt and not operator_retry and not operator_fetch:
                try:
                    if datetime.fromisoformat(str(next_attempt)) > observed:
                        continue
                except ValueError:
                    pass
            priority_name = (
                "OPERATOR_FETCH" if operator_fetch else
                "CURRENT_BOUNDARY" if boundary_due and missed <= 1 and not retry_due and not operator_retry else
                "RETRY_QUEUE" if retry_due or operator_retry else
                "BEHIND_COMMISSIONED" if boundary_due else
                "HISTORICAL_CATCH_UP"
            )
            queue_age = 0.0
            if enqueued_at:
                try:
                    queue_age = max(0.0, (observed - datetime.fromisoformat(str(enqueued_at))).total_seconds())
                except ValueError:
                    pass
            if queue_age >= 8 * 3600 and priority_name not in {"OPERATOR_FETCH", "CURRENT_BOUNDARY"}:
                priority_name = "STARVATION_RELIEF"
            requested_start = (
                operator_fetch.get("requested_start")
                if operator_fetch else freshness.get("latest_canonical_observation")
            )
            requested_end = (
                operator_fetch.get("requested_end")
                if operator_fetch else freshness["expected_latest"]
            )
            if (
                operator_fetch
                and str(operator_fetch.get("requested_mode") or "").lower() == "initial"
                and str(timeframe) != "D1"
                and freshness.get("latest_canonical_observation")
                and not operator_fetch.get("backfill_from_start", False)
            ):
                requested_start = _advance_start_bound(
                    str(asset_class), str(timeframe), requested_start,
                    freshness.get("latest_canonical_observation"),
                )
            result.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "asset_class":asset_class,
                "scheduled_boundary": attempt_key,
                "canonical_edge": freshness.get("latest_canonical_observation"),
                "expected_edge": freshness["expected_latest"],
                "missing_range": {
                    "start": requested_start,
                    "end": requested_end,
                },
                "missed_boundaries": missed,
                "retry_due": retry_due,
                "work_class": "OPERATOR_RETRY" if operator_retry else (
                    "OPERATOR_FETCH" if operator_fetch else
                    "NORMAL" if boundary_due and missed <= 1 and not retry_due else "QUEUE"
                ),
                "operator_fetch_id": operator_fetch.get("id") if operator_fetch else None,
                "operator_fetch_mode": operator_fetch.get("requested_mode") if operator_fetch else None,
                "requested_bounds": (
                    [requested_start, requested_end]
                    if operator_fetch else None
                ),
                "next_attempt": next_attempt,
                "enqueued_at": enqueued_at,
                "queue_age_seconds": queue_age,
                "dispatch_priority": priority_name,
                "queue_reason": "Operator Fetch requested" if operator_fetch else "Operator retry requested" if operator_retry else (
                    "Retry boundary due" if retry_due else f"{missed} missed commissioned boundaries"
                ),
            })
    return sorted(
        result,
        key=_operational_dispatch_key,
    )


def _fair_bounded_selection(due, max_tasks, journal):
    limit = len(due) if max_tasks is None else min(max_tasks, len(due))
    remaining = sorted(due,key=_operational_dispatch_key)
    protected=[item for item in remaining if _operational_priority_group(item)[0] < 3]
    operational=[item for item in remaining if _operational_priority_group(item)[0] == 3]
    if operational:
        active_market=min(operational_market_rank(item.get("asset_class")) for item in operational)
        active_operational=[
            item for item in operational
            if operational_market_rank(item.get("asset_class")) == active_market
        ]
        eligible=protected+active_operational
        # Preserve the market/priority gate, but do not let a set made solely
        # of per-item retries hide unrelated catch-up work from the same market.
        if active_operational and all(
            _dispatch_priority(item) == "RETRY_QUEUE" for item in active_operational
        ):
            eligible += [
                item for item in remaining
                if _operational_priority_group(item)[0] == 4
                and operational_market_rank(item.get("asset_class")) == active_market
            ]
    else:
        historical=[item for item in remaining if _operational_priority_group(item)[0] == 4]
        eligible=protected+historical
    # Cadence is a strict release gate, not a rotating fairness dimension.
    # Operator work leads the batch. Ordinary work is released from exactly
    # one timeframe tier, so lower cadences cannot start while a higher tier
    # remains eligible. Queue age only orders peers inside that tier.
    ordered=sorted(eligible,key=_operational_dispatch_key)
    # A current, calendar-approved boundary is the Scheduler's core upkeep
    # obligation.  Explicit operator fetches are important but often request
    # historical depth; letting those consume every worker can freeze a
    # continuously-open crypto lane behind closed-market work over a weekend.
    # Reserve the first available slots for normal current-boundary work.
    current=[item for item in ordered if _dispatch_priority(item) == "CURRENT_BOUNDARY"]
    selected=current[:limit]
    capacity=limit-len(selected)
    if capacity <= 0:
        return selected
    selected_ids={id(item) for item in selected}
    operator=[
        item for item in ordered
        if _cadence_phase(item) == 0 and id(item) not in selected_ids
    ]
    selected.extend(operator[:capacity])
    capacity=limit-len(selected)
    if capacity <= 0:
        return selected
    ordinary=[
        item for item in ordered
        if _cadence_phase(item) == 1 and id(item) not in selected_ids
    ]
    candidates=ordinary or [item for item in ordered if _cadence_phase(item) == 2]
    if not candidates:
        return selected
    active_timeframe=min(_timeframe_rank(str(item.get("timeframe") or "")) for item in candidates)
    selected.extend(
        item for item in candidates
        if _timeframe_rank(str(item.get("timeframe") or "")) == active_timeframe
    )
    return selected[:limit]


def _operational_priority_group(item):
    priority=_dispatch_priority(item)
    if priority == "OPERATOR_FETCH":
        return (0,0,0)
    if priority == "CURRENT_BOUNDARY":
        return (1,0,0)
    if priority in {"STARVATION_RELIEF","AGED_BACKLOG"}:
        return (2,0,0)
    if priority == "HISTORICAL_CATCH_UP":
        return (4,operational_market_rank(item.get("asset_class")),0)
    work_rank={
        "BEHIND_COMMISSIONED":0,
        "RETRY_QUEUE":1,
        "ROUTINE_MAINTENANCE":2,
    }.get(priority,3)
    return (3,operational_market_rank(item.get("asset_class")),work_rank)


def _operational_dispatch_key(item):
    return (
        _cadence_phase(item),
        _timeframe_rank(str(item.get("timeframe") or "")),
        *_operational_priority_group(item),
        -float(item.get("queue_age_seconds",0) or 0),
        -int(item.get("missed_boundaries",0) or 0),
        str(item.get("expected_edge") or ""),
        f"{item.get('symbol','')}:{item.get('timeframe','')}",
    )


def _cadence_phase(item):
    priority = _dispatch_priority(item)
    if priority == "OPERATOR_FETCH":
        return 0
    if priority == "HISTORICAL_CATCH_UP":
        return 2
    return 1


def _dispatch_priority(item):
    explicit = item.get("dispatch_priority")
    if explicit:
        return explicit
    if item.get("work_class") == "OPERATOR_FETCH":
        return "OPERATOR_FETCH"
    if item.get("work_class") == "NORMAL":
        return "CURRENT_BOUNDARY"
    if item.get("work_class") == "OPERATOR_RETRY" or item.get("retry_due"):
        return "RETRY_QUEUE"
    return "BEHIND_COMMISSIONED"


def _acquisition_bounds(database_path, symbol, timeframe, observed):
    with open_read_only(database_path) as connection:
        freshness = assess_lane_freshness(
            connection, symbol=symbol, timeframe=timeframe, as_of=observed
        )
        latest = freshness.get("latest_canonical_observation")
        expected = freshness.get("expected_latest")
        if not expected:
            raise ValueError("EXPECTED_CANONICAL_EDGE_UNAVAILABLE")
        expected_value = datetime.fromisoformat(expected)
        if timeframe == "D1":
            start = (
                datetime.fromisoformat(latest).date() + timedelta(days=1)
                if latest
                else governed_d1_initial_start(expected_value.date())
            )
            return start.isoformat(), expected_value.date().isoformat()
        registration = connection.execute(
            "SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
            (symbol,),
        ).fetchone()
        profile = profile_for(registration[0], timeframe)
        zone = ZoneInfo(profile.timezone)
        start_value = datetime.fromisoformat(latest) if latest else expected_value
        return (
            start_value.astimezone(zone).date().isoformat(),
            expected_value.astimezone(zone).date().isoformat(),
        )


def _request_start_from_canonical_edge(
    asset_class: str, timeframe: str, canonical_edge: object
) -> str | None:
    if not canonical_edge:
        return None
    try:
        value = datetime.fromisoformat(str(canonical_edge))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if timeframe == "D1":
        return (value.astimezone(UTC).date() + timedelta(days=1)).isoformat()
    profile = profile_for(asset_class, timeframe)
    return value.astimezone(ZoneInfo(profile.timezone)).date().isoformat()


def _advance_start_bound(
    asset_class: str, timeframe: str, current_start: object, canonical_edge: object
) -> object:
    resumed = _request_start_from_canonical_edge(asset_class, timeframe, canonical_edge)
    if not resumed:
        return current_start
    if not current_start:
        return resumed
    try:
        return resumed if date.fromisoformat(resumed) > date.fromisoformat(str(current_start)) else current_start
    except ValueError:
        return resumed


def _resume_bounds_from_canonical(
    asset_class: str, timeframe: str, bounds: tuple[object, object], canonical_edge: object
) -> tuple[object, object]:
    return (
        _advance_start_bound(asset_class, timeframe, bounds[0], canonical_edge),
        bounds[1],
    )


def _operator_request_bounds(value: object) -> tuple[str, str]:
    """Read the durable operator bounds without treating mapping keys as values."""
    if isinstance(value, dict):
        start, end = value.get("start"), value.get("end")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        start, end = value
    else:
        raise ValueError("OPERATOR_REQUEST_BOUNDS_INVALID: expected start and end values")
    if not isinstance(start, str) or not start or not isinstance(end, str) or not end:
        raise ValueError("OPERATOR_REQUEST_BOUNDS_INVALID: start and end must be non-empty strings")
    return start, end


def _diagnostic_request_bounds(value: object) -> tuple[object, object]:
    """Keep invalid preflight inputs inspectable without making evidence writable."""
    try:
        return _operator_request_bounds(value)
    except ValueError:
        return "UNRESOLVED", "UNRESOLVED"


def _execution_failure_detail(
    classification: str,
    error: BaseException,
    *,
    function: str,
    lane: str,
    provider: str,
    bounds: tuple[object, object],
    expected_edge: object,
    canonical_edge_before: object,
    canonical_edge_after: object,
) -> str:
    invariant = str(error) or type(error).__name__
    return (
        f"{classification}; function={function}; lane={lane}; provider={provider}; "
        f"request_bounds={bounds[0]}..{bounds[1]}; expected_edge={expected_edge}; "
        f"canonical_edge_before={canonical_edge_before}; "
        f"canonical_edge_after={canonical_edge_after}; invariant={invariant}; "
        f"underlying_exception={type(error).__name__}: {error}"
    )


def _asset_class(database_path, symbol):
    with open_read_only(database_path) as connection:
        row = connection.execute(
            "SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
            (symbol,),
        ).fetchone()
    if not row:
        raise ValueError(f"UNREGISTERED_INSTRUMENT: {symbol}")
    return row[0]


def _execute_acquisition(
    acquirer, database_path, *, request_count, maximum_rows,
    from_date, through_date, timeframe, on_dispatch=None, on_response=None,
    expected_edge=None, canonical_edge_reader=None,
    continue_from_canonical: bool = False, continuation_context=None, **kwargs,
):
    """Execute bounded chunks, admitting a lane once and in deterministic order."""
    first, last = datetime.fromisoformat(from_date).date(), datetime.fromisoformat(through_date).date()
    rows_per_day = {"D1": 1, "H1": 24, "M30": 48, "M5": 288}[timeframe]
    days_per_request = max(1, maximum_rows // rows_per_day)
    if (
        kwargs.get("provider") == "BINANCE"
        and request_count > 1
    ):
        return _execute_parallel_binance_history(
            database_path,
            first=first,
            last=last,
            days_per_request=days_per_request,
            timeframe=timeframe,
            on_dispatch=on_dispatch,
            on_response=on_response,
            **kwargs,
        )
    cursor = first
    index = 0
    context = dict(continuation_context or {})
    aggregate: dict[str, object] = {
        "inserted": 0, "corrected": 0, "unchanged": 0, "received": 0,
    }
    while cursor <= last:
        if index >= request_count:
            lane = context.get("lane") or f"{kwargs.get('asset')}:{timeframe}"
            provider = context.get("provider") or kwargs.get("provider")
            raise ValueError(
                "INITIAL_HISTORY_CONTINUATION_REQUEST_BUDGET_EXHAUSTED: "
                f"function=_execute_acquisition lane={lane} provider={provider} "
                f"request_bounds={from_date}..{through_date} next_start={cursor.isoformat()} "
                f"expected_edge={expected_edge} maximum_rows={maximum_rows} "
                f"reserved_requests={request_count}"
            )
        remaining_days = (last - cursor).days + 1
        end = cursor + timedelta(days=min(days_per_request, remaining_days) - 1)
        chunk_start, chunk_end = cursor.isoformat(), end.isoformat()
        if on_dispatch:
            on_dispatch(index)
        try:
            result = acquirer(
                database_path, timeframe=timeframe, from_date=chunk_start,
                through_date=chunk_end, **kwargs,
            )
        except BaseException:
            if on_response:
                on_response(index, False)
            raise
        if on_response:
            on_response(index, True)
        for field in ("inserted", "corrected", "unchanged", "received"):
            aggregate[field] = int(aggregate[field]) + int(result.get(field, 0))
        aggregate.update({
            key: value for key, value in result.items()
            if key not in {"inserted", "corrected", "unchanged", "received"}
        })
        aggregate.setdefault("chunk_ranges", []).append({"start": chunk_start, "end": chunk_end})
        if (
            continue_from_canonical
            and canonical_edge_reader is not None
            and (edge_after := canonical_edge_reader())
        ):
            aggregate["canonical_edge_after"] = edge_after
            if expected_edge and _canonical_reaches_requested_edge(edge_after, expected_edge):
                index += 1
                break
            resumed = _request_start_from_canonical_edge(
                str(kwargs.get("asset_class") or ""), timeframe, edge_after
            )
            if resumed:
                try:
                    resumed_date = date.fromisoformat(resumed)
                except ValueError:
                    resumed_date = None
                if resumed_date and resumed_date > cursor:
                    cursor = resumed_date
                    index += 1
                    continue
        cursor = end + timedelta(days=1)
        index += 1
    aggregate["request_count"] = index
    return aggregate


def _execute_parallel_binance_history(
    database_path, *, first, last, days_per_request, timeframe,
    on_dispatch=None, on_response=None, **kwargs,
):
    """Download Binance history concurrently; admit all chunks in one commit.

    Binance limits a kline response to 1,000 rows.  A three-year H1 initial
    history is therefore 27 requests.  Serially downloading *and committing*
    every response made the job take minutes.  The chunks remain independently
    evidenced, but their canonical merge is one deterministic transaction.
    """
    from .providers.binance import admit_binance_chunks, prepare_binance_chunk

    ranges: list[tuple[str, str]] = []
    cursor = first
    while cursor <= last:
        remaining_days = (last - cursor).days + 1
        end = cursor + timedelta(days=min(days_per_request, remaining_days) - 1)
        ranges.append((cursor.isoformat(), end.isoformat()))
        cursor = end + timedelta(days=1)

    # Binance's governed 600 request/minute budget easily covers this bounded
    # burst.  Eight workers keeps initial-history latency low without allowing
    # an unbounded fan-out across scheduler operations.
    worker_count = min(8, len(ranges))
    prepared: dict[int, object] = {}
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="binance-history") as executor:
        futures = {}
        for index, (chunk_start, chunk_end) in enumerate(ranges):
            if on_dispatch:
                on_dispatch(index)
            future = executor.submit(
                prepare_binance_chunk,
                asset=str(kwargs["asset"]),
                timeframe=timeframe,
                provider_symbol=str(kwargs["provider_symbol"]),
                from_date=chunk_start,
                through_date=chunk_end,
                api_base_url=kwargs.get("provider_api_base_url"),
                progress=kwargs.get("progress"),
            )
            futures[future] = index
        for future, index in sorted(
            ((future, index) for future, index in futures.items()), key=lambda item: item[1]
        ):
            try:
                prepared[index] = future.result()
            except BaseException:
                if on_response:
                    on_response(index, False)
                raise
            if on_response:
                on_response(index, True)

    result = admit_binance_chunks(
        database_path,
        asset=str(kwargs["asset"]),
        timeframe=timeframe,
        provider_symbol=str(kwargs["provider_symbol"]),
        chunks=tuple(prepared[index] for index in range(len(ranges))),
        merge_mode=str(kwargs.get("merge_mode") or "preserve"),
        mapping_class=str(kwargs.get("mapping_class") or "EXACT_REPRESENTATION"),
        from_date=ranges[0][0],
        through_date=ranges[-1][1],
    )
    result["request_count"] = len(ranges)
    result["chunk_ranges"] = [
        {"start": chunk_start, "end": chunk_end}
        for chunk_start, chunk_end in ranges
    ]
    return result


REQUIRED_SET_PLAN_CONTRACT = "fragarach_ii.required_set_acquisition_plan.v1"
REQUIRED_SET_RESULT_CONTRACT = "fragarach_ii.required_set_acquisition_result.v1"
_INITIAL_HISTORY_YEARS = {"D1": 10, "H1": 3, "M30": 2, "M5": 1}


def required_set_acquisition_plan(
    database_path: str | Path,
    *,
    symbol: str,
    credential: str | None = None,
    journal_path: str | Path | None = None,
    at: datetime | None = None,
    provider_profiles=None,
) -> dict[str, object]:
    """Plan the complete doctrine-required timeframe set for one symbol."""

    observed = normalized_utc(at)
    canonical_symbol = symbol.strip().upper()
    asset_class = _asset_class(database_path, canonical_symbol)
    required = tuple(required_timeframes(asset_class))
    journal = SchedulerJournal(database_path, journal_path)
    profiles = tuple(provider_profiles or load_provider_profiles())
    credentials = credential_map(credential)
    budgets = build_rate_budgets(
        profiles, journal.providers, wall_clock=lambda: observed,
        credential=credential,
    )
    lanes = [
        _required_set_lane_plan(
            database_path,
            journal=journal,
            symbol=canonical_symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            observed=observed,
            profiles=profiles,
            credentials=credentials,
            budgets=budgets,
        )
        for timeframe in required
    ]
    return {
        "contract": REQUIRED_SET_PLAN_CONTRACT,
        "symbol": canonical_symbol,
        "asset_class": asset_class,
        "required_timeframes": list(required),
        "lanes": lanes,
        "executable": any(bool(item.get("executable")) for item in lanes),
        "strict_all_or_nothing": False,
        "planned_at": observed.isoformat(),
    }


def queue_estate_admission_initial_fetch(
    database_path: str | Path,
    *,
    symbol: str,
    credential: str | None = None,
    journal_path: str | Path | None = None,
    at: datetime | None = None,
    provider_profiles=None,
) -> dict[str, object]:
    """Durably queue initial history after an instrument enters the Estate.

    Adding an approved discovery representation is the operator's admission
    decision.  This queues every executable enabled timeframe without making
    the registration/UI request wait for provider I/O.  Scheduler dispatch,
    provider budgets, and the manual Required Set action remain unchanged.
    """
    observed = normalized_utc(at)
    canonical_symbol = symbol.strip().upper()
    plan = required_set_acquisition_plan(
        database_path, symbol=canonical_symbol, credential=credential,
        journal_path=journal_path, at=observed, provider_profiles=provider_profiles,
    )
    _supersede_legacy_required_set_job(
        database_path,
        journal_path=journal_path,
        symbol=canonical_symbol,
        current_plan=plan,
        observed=observed,
    )
    queued_timeframes: list[str] = []
    skipped: list[dict[str, object]] = []
    for lane in plan["lanes"]:
        timeframe = str(lane["timeframe"])
        if not lane.get("executable"):
            skipped.append({
                "timeframe": timeframe,
                "reason": lane.get("blocking_reason") or "NOT_EXECUTABLE",
            })
            continue
        bounds = dict(lane.get("request_bounds") or {})
        if not bounds.get("start") or not bounds.get("end"):
            skipped.append({"timeframe": timeframe, "reason": "REQUEST_BOUNDS_UNAVAILABLE"})
            continue
        submitted = run_operator_fetch(
            database_path,
            symbol=canonical_symbol,
            timeframe=timeframe,
            credential=credential,
            requested_mode=str(lane.get("intent") or "initial"),
            requested_start=str(bounds["start"]),
            requested_end=str(bounds["end"]),
            reviewed_historical_range=True,
            operator_reason="ESTATE_ADMISSION_AUTO_INITIAL_HISTORY",
            merge_mode="preserve",
            journal_path=journal_path,
            at=observed,
            provider_profiles=provider_profiles,
            defer_dispatch=True,
        )
        if submitted.get("outcome") in {"QUEUED", "DEDUPLICATED_ACTIVE_WORK"}:
            queued_timeframes.append(timeframe)
        else:
            skipped.append({
                "timeframe": timeframe,
                "reason": submitted.get("outcome") or "QUEUE_REJECTED",
            })
    return {
        "contract": "fragarach_ii.estate_admission_initial_queue.v1",
        "outcome": "INITIAL_HISTORY_QUEUED" if queued_timeframes else "NO_INITIAL_HISTORY_QUEUED",
        "symbol": canonical_symbol,
        "queued_timeframes": queued_timeframes,
        "skipped": skipped,
        "plan": plan,
    }


def _supersede_legacy_required_set_job(
    database_path: str | Path,
    *,
    journal_path: str | Path | None,
    symbol: str,
    current_plan: dict[str, object],
    observed: datetime,
) -> bool:
    """Finish a pre-admission Required Set job whose lane ownership changed.

    Required Set jobs are transaction records, not lane locks.  Before estate
    admission became the commissioning decision, a job could remain ``RUNNING``
    with an uncommissioned snapshot even after its lanes were commissioned and
    queued by the Scheduler.  Retaining that transaction as active makes the
    operator UI describe historical ownership instead of the live lane state.
    Only that provably obsolete shape is superseded; a normal active Required
    Set job remains active and continues to own its own transaction.
    """
    journal = SchedulerJournal(database_path, journal_path)
    active = journal.data.get("required_set_active_job")
    if not isinstance(active, dict):
        return False
    if str(active.get("symbol") or "").upper() != symbol:
        return False
    if str(active.get("status") or "").upper() != "RUNNING":
        return False

    prior_plan = active.get("plan")
    prior_lanes = prior_plan.get("lanes", []) if isinstance(prior_plan, dict) else []
    current_lanes = current_plan.get("lanes", [])
    current_commissioned = {
        str(lane.get("timeframe")): bool(lane.get("commissioned"))
        for lane in current_lanes
        if isinstance(lane, dict)
    }
    superseded_lanes = sorted({
        str(lane.get("timeframe"))
        for lane in prior_lanes
        if isinstance(lane, dict)
        and lane.get("commissioned") is False
        and current_commissioned.get(str(lane.get("timeframe"))) is True
    })
    if not superseded_lanes:
        return False

    job_id = str(active.get("id") or "")
    completed_at = observed.isoformat()
    update = {
        "status": "SUPERSEDED",
        "completed_at": completed_at,
        "superseded_at": completed_at,
        "superseded_by": "ESTATE_ADMISSION_AUTOMATION",
        "superseded_reason": "LEGACY_UNCOMMISSIONED_LANE_SNAPSHOT",
        "superseded_lanes": superseded_lanes,
    }
    active.update(update)
    for job in journal.data.setdefault("required_set_jobs", []):
        if isinstance(job, dict) and str(job.get("id") or "") == job_id:
            job.update(update)
            break
    journal.data.pop("required_set_active_job", None)
    journal.save()
    return True


def run_required_set_fetch(
    database_path: str | Path,
    *,
    symbol: str,
    credential: str | None,
    merge_mode: str = "preserve",
    operator_reason: str = "REQUIRED_TIMEFRAME_SET",
    journal_path: str | Path | None = None,
    at: datetime | None = None,
    acquirer: Callable[..., dict[str, object]] = acquire_from_provider,
    provider_profiles=None,
    emit: Callable[[dict[str, object]], None] | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Execute the doctrine-required lanes for one symbol as one operator job."""

    if merge_mode != "preserve":
        raise ValueError("REQUIRED_SET_FETCH_REQUIRES_IMMUTABLE_PRESERVE_MODE")
    observed = normalized_utc(at)
    canonical_symbol = symbol.strip().upper()
    job_id = f"required-set-{uuid.uuid4().hex}"
    plan = required_set_acquisition_plan(
        database_path,
        symbol=canonical_symbol,
        credential=credential,
        journal_path=journal_path,
        at=observed,
        provider_profiles=provider_profiles,
    )
    _record_required_set_job(
        database_path,
        journal_path=journal_path,
        job={
            "id": job_id,
            "symbol": canonical_symbol,
            "asset_class": plan["asset_class"],
            "status": "RUNNING",
            "started_at": observed.isoformat(),
            "current_lane": None,
            "plan": plan,
            "lane_results": [],
            "progress_timeline": [{
                "at": observed.isoformat(), "stage": "PLANNING",
                "current_lanes": [], "completed_lanes": [],
                "blocked_lanes": [str(item["timeframe"]) for item in plan["lanes"] if item.get("blocking_reason")],
                "failed_lanes": [], "provider": None,
                "publication_state": "PENDING_PUBLICATION",
            }],
        },
    )
    completed: list[str] = []
    remaining: list[str] = [
        str(item["timeframe"]) for item in plan["lanes"] if item.get("executable")
    ]
    partial_failures: list[dict[str, object]] = []
    provider_used: list[str] = []
    last_published_edge: dict[str, object] = {}
    lane_results: list[dict[str, object]] = []

    queued_lanes: list[dict[str, object]] = []
    for lane in plan["lanes"]:
        timeframe = str(lane["timeframe"])
        _commission_lane_after_evidence(database_path, canonical_symbol, timeframe, observed)
        if not lane.get("executable"):
            continue
        remaining = [item for item in remaining if item != timeframe]
        bounds = lane.get("request_bounds") or {}
        try:
            submitted = run_operator_fetch(
                database_path,
                symbol=canonical_symbol,
                timeframe=timeframe,
                credential=credential,
                requested_mode=str(lane.get("intent") or "update"),
                requested_start=str(bounds.get("start")) if bounds.get("start") else None,
                requested_end=str(bounds.get("end")) if bounds.get("end") else None,
                reviewed_historical_range=True,
                operator_reason=f"{operator_reason}:{job_id}",
                merge_mode=merge_mode,
                journal_path=journal_path,
                at=observed,
                acquirer=acquirer,
                provider_profiles=provider_profiles,
                defer_dispatch=True,
            )
        except BaseException as error:
            failure = {
                "timeframe": timeframe, "outcome": "FAILED",
                "reason": str(error), "retryable": False,
            }
            partial_failures.append(failure)
            lane_results.append({"timeframe": timeframe, **failure})
            continue
        if submitted.get("outcome") == "QUEUED":
            queued_lanes.append(lane)
        else:
            lane_results.append({"timeframe": timeframe, "outcome": submitted.get("outcome"), "result": submitted})

    # Queue preparation is short and serial; provider work is dispatched in
    # bounded two-lane waves.  The Scheduler's per-provider reservation and
    # lane guard remain the authority for each individual lane.
    for offset in range(0, len(queued_lanes), 2):
        wave = queued_lanes[offset:offset + 2]
        _record_required_set_job(
            database_path,
            journal_path=journal_path,
            job_update={
                "id": job_id, "status": "RUNNING",
                "current_lane": ",".join(str(item["timeframe"]) for item in wave),
                "completed_lanes": completed,
                "remaining_lanes": [str(item["timeframe"]) for item in queued_lanes[offset:]],
                "partial_failures": partial_failures,
                "provider_used": provider_used,
                "last_published_edge": last_published_edge,
                "progress_event": {
                    "at": datetime.now(UTC).isoformat(), "stage": "FETCHING",
                    "current_lanes": [str(item["timeframe"]) for item in wave],
                    "completed_lanes": completed,
                    "blocked_lanes": [str(item["timeframe"]) for item in plan["lanes"] if item.get("blocking_reason")],
                    "failed_lanes": [str(item["timeframe"]) for item in partial_failures],
                    "provider": None, "publication_state": "PENDING_PUBLICATION",
                },
            },
        )
        run_due_acquisitions(
            database_path, at=observed, credential=credential,
            journal_path=journal_path, catch_up=True, acquirer=acquirer,
            provider_profiles=provider_profiles, max_tasks=min(2, len(wave)),
            defer_publication=True,
        )

    restored = SchedulerJournal(database_path, journal_path)
    for lane in queued_lanes:
        timeframe = str(lane["timeframe"])
        result = restored.lane(canonical_symbol, timeframe).get("last_operator_fetch_result")
        if not isinstance(result, dict):
            result = {"outcome": "WAITING", "reason": "Lane remains queued after bounded dispatch"}
        outcome = str(result.get("outcome") or "UNKNOWN")
        edge_after = _canonical_edge(database_path, canonical_symbol, timeframe)
        if edge_after:
            last_published_edge[timeframe] = edge_after
        attempted = [str(item) for item in result.get("providers_attempted", []) if item]
        if not attempted:
            attempted = [
                str(item.get("provider")) for item in result.get("provider_results", [])
                if isinstance(item, dict) and item.get("provider")
            ]
        for provider in attempted:
            if provider not in provider_used:
                provider_used.append(provider)
        commission_error = None
        if edge_after:
            try:
                ensure_commissioned_lane(
                    database_path, canonical_symbol, timeframe,
                    observed_at=observed.isoformat(),
                )
            except ValueError as error:
                commission_error = str(error)
                partial_failures.append({
                    "timeframe": timeframe, "outcome": "COMMISSIONING_BLOCKED",
                    "reason": commission_error, "retryable": False,
                })
        if outcome in {"SUCCESS", "NO_NEW_DATA"} and commission_error is None:
            completed.append(timeframe)
        elif outcome in {"WAITING", "DEDUPLICATED_ACTIVE_WORK"}:
            partial_failures.append({
                "timeframe": timeframe, "outcome": outcome,
                "reason": result.get("reason") or "Lane reached a stable partial state",
                "retryable": True,
            })
        else:
            partial_failures.append({
                "timeframe": timeframe, "outcome": outcome,
                "reason": result.get("reason") or result.get("manual_request_created") or "Lane did not complete",
                "retryable": outcome != "MANUAL_REQUIRED",
            })
        lane_results.append({
            "timeframe": timeframe, "outcome": outcome, "provider_used": attempted,
            "last_published_edge": edge_after,
            "commissioning_error": commission_error, "result": result,
        })

    final_plan = required_set_acquisition_plan(
        database_path,
        symbol=canonical_symbol,
        credential=credential,
        journal_path=journal_path,
        at=observed,
        provider_profiles=provider_profiles,
    )
    final_states = {
        str(item["timeframe"]): str(item.get("eligibility") or "")
        for item in final_plan["lanes"]
    }
    current = [
        timeframe for timeframe, state in final_states.items()
        if state in {"CURRENT", "NO_NEW_DATA"}
    ]
    blocked = [
        item for item in final_plan["lanes"]
        if item.get("blocking_reason")
    ]
    executable_remaining = [
        str(item["timeframe"]) for item in final_plan["lanes"] if item.get("executable")
    ]
    outcome = (
        "SUCCESS" if len(current) == len(final_plan["lanes"]) else
        "NO_EXECUTABLE_LANES" if not plan.get("executable") else
        "PARTIAL"
    )
    # A resumed group never re-fetches a lane with canonical evidence merely
    # because its projection failed.  It retries the failed projection first;
    # freshly completed lanes are batched into the same grouped publication.
    retryable_publication_lanes = [
        (canonical_symbol, str(item["timeframe"]))
        for item in final_plan["lanes"]
        if item.get("canonical_edge")
        and str(item.get("publication", {}).get("state")) == "FAILED_RETRYABLE"
    ]
    publication_job = retry_publication(
        database_path, retryable_publication_lanes,
        trigger="REQUIRED_SET_RESUME_PUBLICATION",
    )
    if publication_job is None:
        publication_job = enqueue_publication(
            database_path,
            [(canonical_symbol, timeframe) for timeframe in completed],
            trigger="REQUIRED_SET_JOB",
        )
    completed_at = datetime.now(UTC).isoformat()
    result = {
        "contract": REQUIRED_SET_RESULT_CONTRACT,
        "work_class": "OPERATOR_FETCH_REQUIRED_SET",
        "job_id": job_id,
        "symbol": canonical_symbol,
        "asset_class": plan["asset_class"],
        "required_timeframes": plan["required_timeframes"],
        "outcome": outcome,
        "plan": final_plan,
        "lanes": final_plan["lanes"],
        "current_lane": None,
        "completed_lanes": sorted(set(completed) | set(current), key=_timeframe_rank),
        "remaining_lanes": executable_remaining,
        "partial_failures": partial_failures,
        "provider_used": provider_used,
        "last_published_edge": last_published_edge,
        "blocked_lanes": blocked,
        "lane_results": lane_results,
        "publication_job": publication_job,
        "publication_retry_lanes": [timeframe for _, timeframe in retryable_publication_lanes],
        "completed_at": completed_at,
    }
    _record_required_set_job(
        database_path,
        journal_path=journal_path,
        job_update={
            "id": job_id,
            "status": outcome,
            "current_lane": None,
            "completed_lanes": result["completed_lanes"],
            "remaining_lanes": result["remaining_lanes"],
            "partial_failures": partial_failures,
            "lane_results": lane_results,
            "provider_used": provider_used,
            "last_published_edge": last_published_edge,
            "plan": final_plan,
            "completed_at": completed_at,
            "progress_event": {
                "at": completed_at,
                "stage": "PUBLISHING" if publication_job else "COMPLETE",
                "current_lanes": [], "completed_lanes": result["completed_lanes"],
                "blocked_lanes": [str(item["timeframe"]) for item in blocked],
                "failed_lanes": [str(item["timeframe"]) for item in partial_failures],
                "provider": ",".join(provider_used) or None,
                "publication_state": "PUBLISHING" if publication_job else "PUBLISHED",
            },
        },
    )
    return result


def resume_required_set_fetch(
    database_path: str | Path,
    *,
    symbol: str,
    credential: str | None,
    **kwargs,
) -> dict[str, object]:
    """Resume a grouped symbol job from canonical edges and failed publication.

    ``run_required_set_fetch`` already plans update bounds from each lane's
    canonical edge.  Naming the entry point makes that safe recovery workflow
    available to CLI and UI callers without a separate state machine.
    """
    kwargs.pop("operator_reason", None)
    return run_required_set_fetch(
        database_path, symbol=symbol, credential=credential,
        operator_reason="RESUME_REQUIRED_TIMEFRAME_SET", **kwargs,
    )


def _required_set_lane_plan(
    database_path: str | Path,
    *,
    journal: SchedulerJournal,
    symbol: str,
    asset_class: str,
    timeframe: str,
    observed: datetime,
    profiles,
    credentials: dict[str, str],
    budgets,
) -> dict[str, object]:
    canonical_edge, freshness, lane_exists, commissioned = _required_lane_state(
        database_path, symbol, timeframe, observed
    )
    expected_edge = freshness.get("expected_latest")
    expected_status = freshness.get("expected_edge_state")
    reason = freshness.get("reason_code") or freshness.get("reason_detail")
    base = {
        "timeframe": timeframe,
        "provider": None,
        "provider_symbol": None,
        "intent": None,
        "canonical_edge": canonical_edge,
        "expected_edge": expected_edge,
        "expected_edge_status": expected_status,
        "request_bounds": None,
        "historical_depth_target": _historical_depth_target(timeframe),
        "eligibility": None,
        "blocking_reason": None,
        "executable": False,
        "lane_exists": lane_exists,
        "commissioned": commissioned,
        "providers_considered": [],
        "expected_freshness": freshness,
        "publication": lane_publication_detail(database_path, symbol, timeframe),
    }
    if _lane_has_running_work(journal, symbol, timeframe):
        return base | {
            "eligibility": "BLOCKED",
            "blocking_reason": "LANE_ACQUISITION_ALREADY_RUNNING",
        }
    if freshness.get("state") == "Current":
        return base | {
            "intent": "current",
            "eligibility": "CURRENT",
            "blocking_reason": None,
            "resume_action": (
                "RETRY_PUBLICATION"
                if base["publication"]["state"] == "FAILED_RETRYABLE" else None
            ),
        }
    if not expected_edge:
        return base | {
            "eligibility": "BLOCKED",
            "blocking_reason": str(reason or "EXPECTED_CANONICAL_EDGE_UNAVAILABLE"),
        }
    intent = "initial" if not canonical_edge else "update"
    try:
        bounds = (
            _initial_bounds_for_lane(asset_class, timeframe, str(expected_edge))
            if intent == "initial"
            else _acquisition_bounds(database_path, symbol, timeframe, observed)
        )
    except (ValueError, TypeError) as error:
        return base | {
            "intent": intent,
            "eligibility": "BLOCKED",
            "blocking_reason": str(error),
        }
    plan = acquisition_plan(
        database_path,
        symbol=symbol,
        timeframe=timeframe,
        canonical_edge=canonical_edge,
        expected_edge=str(expected_edge),
        missing_start=str(bounds[0]),
        missing_end=str(bounds[1]),
        scheduled_boundary=f"REQUIRED_SET:{expected_edge}",
        profiles=profiles,
        provider_state=journal.providers,
        budgets=budgets,
        credentials=credentials,
        now=observed,
        work_class="OPERATOR_FETCH",
    )
    provider = plan.get("selected_provider")
    if not provider:
        blocker = _plan_blocking_reason(plan)
        return base | {
            "intent": intent,
            "request_bounds": {"start": bounds[0], "end": bounds[1]},
            "eligibility": "BLOCKED",
            "blocking_reason": blocker,
            "providers_considered": plan.get("providers_considered", []),
        }
    return base | {
        "provider": provider,
        "provider_symbol": plan.get("selected_provider_symbol"),
        "intent": intent,
        "request_bounds": {"start": bounds[0], "end": bounds[1]},
        "eligibility": "EXECUTABLE",
        "blocking_reason": None,
        "executable": True,
        "providers_considered": plan.get("providers_considered", []),
        "estimated_request_count": plan.get("estimated_request_count", 0),
        "fallback_sequence": plan.get("fallback_sequence", []),
    }


def _required_lane_state(database_path, symbol, timeframe, observed):
    with open_read_only(database_path) as connection:
        lane_exists = connection.execute(
            "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",
            (symbol, timeframe),
        ).fetchone() is not None
        commissioned = (symbol, timeframe) in commissioned_lane_keys(connection)
        if lane_exists:
            freshness = assess_lane_freshness(
                connection, symbol=symbol, timeframe=timeframe, as_of=observed
            )
        else:
            asset_class = connection.execute(
                "SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
                (symbol,),
            ).fetchone()
            if asset_class is None:
                raise ValueError(f"UNREGISTERED_INSTRUMENT: {symbol}")
            expected, status, reason = _expected_edge_from_registration(
                connection,
                symbol=symbol,
                asset_class=str(asset_class[0]),
                timeframe=timeframe,
                observed=observed,
            )
            freshness = {
                "contract": FRESHNESS_CONTRACT,
                "symbol": symbol,
                "timeframe": timeframe,
                "state": "Not Commissioned",
                "severity": "ATTENTION" if expected else "UNAVAILABLE",
                "operational_state": "Not Commissioned",
                "latest_canonical_observation": _canonical_edge(database_path, symbol, timeframe),
                "expected_latest": expected,
                "expected_edge_state": status,
                "lag": {"count": None, "unit": None},
                "reason_code": reason or "EVIDENCE_LANE_NOT_COMMISSIONED",
                "as_of": observed.replace(microsecond=0).isoformat(),
            }
    return freshness.get("latest_canonical_observation"), freshness, lane_exists, commissioned


def _expected_edge_from_registration(
    connection,
    *,
    symbol: str,
    asset_class: str,
    timeframe: str,
    observed: datetime,
) -> tuple[str | None, str, str | None]:
    if timeframe == "D1":
        row = connection.execute(
            """SELECT calendar_id,exchange_name
               FROM instrument_registrations
               WHERE asset=? AND timeframe='D1'""",
            (symbol,),
        ).fetchone()
        if not row:
            return None, "INSTRUMENT_CALENDAR_UNRESOLVED", "UNREGISTERED_INSTRUMENT"
        calendar_id = resolved_calendar_id(
            asset_class=asset_class,
            calendar_id=row[0],
            exchange_name=row[1],
            canonical_symbol=symbol,
        )
        if not calendar_id:
            return None, "INSTRUMENT_CALENDAR_UNRESOLVED", "OPERATIONAL_CALENDAR_UNAVAILABLE"
        try:
            definition = CalendarRegistry(
                load_symbol_assignments=False
            ).calendar_by_id(calendar_id)
        except ConfigurationError as error:
            return None, "CALENDAR_UNAVAILABLE", f"{error.code}: {error}"
        expected_date = latest_closed_session_date(definition, observed)
        if expected_date is None:
            return None, "MARKET_CLOSED", "NO_EXPECTED_OPERATIONAL_SESSION"
        return (
            datetime.combine(expected_date, datetime.min.time(), UTC).isoformat(),
            "EXPECTED_EDGE_AVAILABLE",
            "EVIDENCE_LANE_NOT_COMMISSIONED",
        )
    try:
        profile = profile_for(asset_class, timeframe)
    except ValueError as error:
        return None, "CALENDAR_UNAVAILABLE", str(error)
    boundary = int(observed.timestamp())
    lookback = boundary - 14 * 86_400
    lookback -= lookback % profile.seconds
    expected = expected_opens(lookback, boundary, profile)
    if not expected:
        return None, "MARKET_CLOSED", "NO_EXPECTED_CLOSED_INTERVAL"
    edge = expected[-1] + profile.seconds
    return (
        datetime.fromtimestamp(edge, UTC).isoformat(),
        "EXPECTED_EDGE_AVAILABLE",
        "EVIDENCE_LANE_NOT_COMMISSIONED",
    )


def _initial_bounds_for_lane(asset_class: str, timeframe: str, expected_edge: str) -> tuple[str, str]:
    expected = datetime.fromisoformat(expected_edge)
    if expected.tzinfo is None:
        expected = expected.replace(tzinfo=UTC)
    if timeframe == "D1":
        end = expected.astimezone(UTC).date()
        return governed_d1_initial_start(end).isoformat(), end.isoformat()
    profile = profile_for(asset_class, timeframe)
    end = expected.astimezone(ZoneInfo(profile.timezone)).date()
    years = _INITIAL_HISTORY_YEARS.get(timeframe, 1)
    return _subtract_years(end, years).isoformat(), end.isoformat()


def _subtract_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year - years)


def _historical_depth_target(timeframe: str) -> str:
    years = _INITIAL_HISTORY_YEARS.get(timeframe, 1)
    return "1 year" if years == 1 else f"{years} years"


def _plan_blocking_reason(plan: dict[str, object]) -> str:
    reasons = [
        str(item.get("reason"))
        for item in plan.get("providers_considered", [])
        if isinstance(item, dict) and item.get("reason")
    ]
    return reasons[0] if reasons else "NO_ELIGIBLE_PROVIDER"


def _lane_has_running_work(journal: SchedulerJournal, symbol: str, timeframe: str) -> bool:
    lane_id = f"{symbol}:{timeframe}"
    return any(
        isinstance(item, dict)
        and item.get("lane") == lane_id
        and item.get("operational_state") == "Running"
        for item in journal.data.get("acquisition_queue", [])
    )


def _commission_lane_after_evidence(
    database_path: str | Path, symbol: str, timeframe: str, observed: datetime
) -> bool:
    if not _canonical_edge(database_path, symbol, timeframe):
        return False
    try:
        ensure_commissioned_lane(
            database_path, symbol, timeframe, observed_at=observed.isoformat()
        )
    except ValueError:
        return False
    return True


def _record_required_set_job(
    database_path: str | Path,
    *,
    journal_path: str | Path | None,
    job: dict[str, object] | None = None,
    job_update: dict[str, object] | None = None,
) -> None:
    journal = SchedulerJournal(database_path, journal_path)
    jobs = journal.data.setdefault("required_set_jobs", [])
    if job is not None:
        jobs.insert(0, job)
        del jobs[50:]
        journal.data["required_set_active_job"] = job
        journal.save()
        return
    if not job_update:
        return
    identifier = str(job_update.get("id"))
    existing = next(
        (item for item in jobs if isinstance(item, dict) and item.get("id") == identifier),
        None,
    )
    if existing is None:
        existing = {"id": identifier}
        jobs.insert(0, existing)
    existing.update(job_update)
    progress_event = job_update.get("progress_event")
    if isinstance(progress_event, dict):
        timeline = existing.setdefault("progress_timeline", [])
        if isinstance(timeline, list):
            timeline.append(progress_event)
            del timeline[:-40]
    if existing.get("status") == "RUNNING":
        journal.data["required_set_active_job"] = existing
    else:
        journal.data.pop("required_set_active_job", None)
    journal.save()


def run_operator_fetch(
    database_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    credential: str | None,
    requested_mode: str = "update",
    requested_start: str | None = None,
    requested_end: str | None = None,
    reviewed_historical_range: bool = False,
    operator_reason: str = "OPERATOR_FETCH",
    merge_mode: str = "preserve",
    journal_path: str | Path | None = None,
    at: datetime | None = None,
    acquirer: Callable[..., dict[str, object]] = acquire_from_provider,
    provider_profiles=None,
    emit: Callable[[dict[str, object]], None] | None = None,
    progress: Callable[[str], None] | None = None,
    defer_dispatch: bool = False,
) -> dict[str, object]:
    """Submit one deduplicated operator request to the Scheduler executor."""

    if merge_mode != "preserve":
        raise ValueError("OPERATOR_FETCH_REQUIRES_IMMUTABLE_PRESERVE_MODE")
    mode = requested_mode.strip().lower()
    if mode not in {"initial", "update", "force", "custom"}:
        raise ValueError(f"unsupported operator fetch mode: {requested_mode}")
    observed = normalized_utc(at)
    canonical_symbol = symbol.strip().upper()
    canonical_timeframe = timeframe.strip().upper()
    journal = SchedulerJournal(database_path, journal_path)
    reconciliation = reconcile_operational_state(database_path, journal.data, at=observed)
    requested_authority = reconciliation["universe"]["active_lanes"].get(
        f"{canonical_symbol}:{canonical_timeframe}"
    )
    registration_authority = reconciliation["universe"]["active_lanes"].get(
        f"{canonical_symbol}:D1"
    )
    if registration_authority is None:
        raise ValueError(f"inactive registration: {canonical_symbol}")
    authority=requested_authority or registration_authority
    was_commissioned=requested_authority is not None
    pause_sources = effective_pause_sources(
        journal.data, symbol=canonical_symbol, group=str(authority["group"])
    )
    if pause_sources:
        labels = ", ".join(
            f"{record.get('scope_type')}:{record.get('scope_identifier') or 'ALL'}"
            for record in pause_sources
        )
        raise ValueError(f"operator fetch cannot bypass acquisition pause: {labels}")
    with open_read_only(database_path) as connection:
        lane_exists=connection.execute(
            "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",
            (canonical_symbol,canonical_timeframe),
        ).fetchone() is not None
        freshness = (
            assess_lane_freshness(
                connection, symbol=canonical_symbol, timeframe=canonical_timeframe, as_of=observed
            )
            if lane_exists else {
                "state":"Not Commissioned","latest_canonical_observation":None,
                "expected_latest":None,"reason_code":"EVIDENCE_LANE_NOT_COMMISSIONED",
            }
        )
        edge_before = freshness.get("latest_canonical_observation")
        revision_before = authority_revision_for_lane(
            connection, symbol=canonical_symbol, timeframe=canonical_timeframe
        )
    # A lane without canonical evidence cannot perform an Update.  Treat the
    # narrow operator action as an initial-history request so its bounded
    # depth is selected from the approved timeframe policy.
    if mode == "update" and not edge_before:
        mode = "initial"
    if mode == "update" and freshness.get("state") == "Current":
        return {
            "contract": "fragarach_ii.acquisition_result.v1",
            "work_class": "OPERATOR_FETCH", "outcome": "NO_NEW_DATA",
            "symbol": canonical_symbol, "timeframe": canonical_timeframe,
            "requested_range": None, "canonical_edge_before": edge_before,
            "canonical_edge_after": edge_before, "expected_edge": freshness.get("expected_latest"),
            "providers_considered": [], "providers_attempted": [], "provider_results": [],
            "published_observations": 0, "authority_revision": revision_before,
            "freshness_result": freshness, "manual_request_created": None,
        }
    if mode in {"initial", "force"} and canonical_timeframe == "D1":
        if not requested_end:
            expected_edge = freshness.get("expected_latest")
            if not expected_edge:
                raise ValueError("initial D1 acquisition requires a completed boundary")
            requested_end = datetime.fromisoformat(str(expected_edge)).date().isoformat()
        governed_start = governed_d1_initial_start(
            datetime.fromisoformat(str(requested_end)).date()
        ).isoformat()
        if (
            not requested_start
            or datetime.fromisoformat(str(requested_start)).date() > date.fromisoformat(governed_start)
        ):
            requested_start = governed_start
        reviewed_historical_range = True
    generated_initial_history_bounds = False
    if (
        mode == "initial"
        and canonical_timeframe != "D1"
        and not requested_start
        and not requested_end
    ):
        expected_edge = freshness.get("expected_latest")
        if not expected_edge:
            raise ValueError("initial intraday acquisition requires a completed boundary")
        requested_start, requested_end = _initial_bounds_for_lane(
            str(authority["asset_class"]), canonical_timeframe, str(expected_edge)
        )
        reviewed_historical_range = True
        generated_initial_history_bounds = True
    if reviewed_historical_range:
        if not requested_start or not requested_end:
            raise ValueError("reviewed historical range requires start and end")
        if datetime.fromisoformat(requested_end).date() < datetime.fromisoformat(requested_start).date():
            raise ValueError("requested end precedes requested start")
        bounds = (requested_start, requested_end)
    else:
        if not lane_exists:
            raise ValueError(
                "an uncommissioned lane requires an explicit reviewed acquisition range"
            )
        bounds = _acquisition_bounds(
            database_path, canonical_symbol, canonical_timeframe, observed
        )
    if (
        mode == "initial"
        and canonical_timeframe != "D1"
        and edge_before
        and not generated_initial_history_bounds
    ):
        resume_start = _advance_start_bound(
            _asset_class(database_path, canonical_symbol),
            canonical_timeframe,
            bounds[0],
            edge_before,
        )
        if resume_start != bounds[0]:
            bounds = (str(resume_start), bounds[1])
        if date.fromisoformat(str(bounds[0])) > date.fromisoformat(str(bounds[1])):
            bounds = (bounds[1], bounds[1])
    if not lane_exists:
        projection=acquisition_capability_projection(
            database_path,symbol=canonical_symbol,timeframe=canonical_timeframe,
            profiles=tuple(provider_profiles or load_provider_profiles()),
            provider_state=journal.providers,credentials=credential_map(credential),
            now=observed,requested_start=bounds[0],requested_end=bounds[1],
        )
        rows=list(projection["rows"])
        if not any(row.get("eligibility")=="ELIGIBLE" for row in rows):
            reasons=sorted({
                str(row.get("rejection_reason") or "NO_ELIGIBLE_PROVIDER")
                for row in rows
            })
            raise ValueError(
                "manual acquisition unavailable: "+", ".join(reasons)
            )
        ensure_manual_acquisition_lane(
            database_path,canonical_symbol,canonical_timeframe,
            observed_at=observed.isoformat(),
        )
        with open_read_only(database_path) as connection:
            freshness=assess_lane_freshness(
                connection,symbol=canonical_symbol,timeframe=canonical_timeframe,as_of=observed
            )
            revision_before=authority_revision_for_lane(
                connection,symbol=canonical_symbol,timeframe=canonical_timeframe
            )
    operation_id = f"operator-fetch-{uuid.uuid4().hex}"
    recorded = journal.lane(canonical_symbol, canonical_timeframe)
    existing = recorded.get("operator_fetch_pending")
    if isinstance(existing, dict):
        if mode == "initial" and existing.get("requested_mode") != "initial":
            # Upgrade a previously queued empty-lane Update in place.  This
            # preserves its queue identity and avoids making the operator
            # click through a duplicate request after the initial plan is
            # known to be required.
            existing.update(
                requested_mode="initial",
                requested_start=bounds[0],
                requested_end=bounds[1],
                backfill_from_start=generated_initial_history_bounds,
                operator_reason=operator_reason,
                requested_at=observed.isoformat(),
            )
            journal.save()
            return {
                "contract": "fragarach_ii.acquisition_result.v1",
                "work_class": "OPERATOR_FETCH", "outcome": "UPGRADED_TO_INITIAL_HISTORY",
                "operation_id": existing.get("id"), "symbol": canonical_symbol,
                "timeframe": canonical_timeframe,
                "requested_range": {"start": bounds[0], "end": bounds[1]},
            }
        return {
            "contract": "fragarach_ii.acquisition_result.v1",
            "work_class": "OPERATOR_FETCH", "outcome": "DEDUPLICATED_ACTIVE_WORK",
            "operation_id": existing.get("id"), "symbol": canonical_symbol,
            "timeframe": canonical_timeframe, "requested_range": {
                "start": existing.get("requested_start"), "end": existing.get("requested_end")
            },
        }
    recorded["operator_fetch_pending"] = {
        "id": operation_id, "requested_mode": mode,
        "requested_start": bounds[0], "requested_end": bounds[1],
        "backfill_from_start": generated_initial_history_bounds,
        "operator_reason": operator_reason, "requested_at": observed.isoformat(),
    }
    recorded.setdefault("provider_attempts_by_boundary", {}).pop(
        f"OPERATOR_FETCH:{operation_id}", None
    )
    journal.data["dispatch_generation"] = int(journal.data.get("dispatch_generation", 0)) + 1
    journal.save()
    if defer_dispatch:
        # Required Set uses this to submit several independently-deduplicated
        # lanes before one bounded Scheduler batch dispatches them.  Submission
        # is still durable and canonical admission remains in run_due_acquisitions.
        return {
            "contract": "fragarach_ii.acquisition_result.v1",
            "work_class": "OPERATOR_FETCH", "outcome": "QUEUED",
            "operation_id": operation_id, "symbol": canonical_symbol,
            "timeframe": canonical_timeframe,
            "requested_range": {"start": bounds[0], "end": bounds[1]},
        }
    run_due_acquisitions(
        database_path, at=observed, credential=credential, journal_path=journal_path,
        catch_up=True, acquirer=acquirer, emit=emit,
        provider_profiles=provider_profiles, max_tasks=1, operation_progress=progress,
    )
    restored = SchedulerJournal(database_path, journal_path)
    result = restored.lane(canonical_symbol, canonical_timeframe).get("last_operator_fetch_result")
    def finish_manual_only(payload:dict[str,object])->dict[str,object]:
        if was_commissioned:
            return payload
        cleanup=SchedulerJournal(database_path,journal_path)
        cleanup.data.setdefault("lanes",{}).pop(
            f"{canonical_symbol}:{canonical_timeframe}",None
        )
        cleanup.data["acquisition_queue"]=[
            item for item in cleanup.data.get("acquisition_queue",[])
            if not (
                item.get("lane")==f"{canonical_symbol}:{canonical_timeframe}"
                and item.get("work_class")=="OPERATOR_FETCH"
            )
        ]
        cleanup.save()
        return payload
    if isinstance(result, dict) and result.get("operation_id") == operation_id:
        return finish_manual_only({"contract": "fragarach_ii.acquisition_result.v1", "symbol": canonical_symbol,
                "timeframe": canonical_timeframe, **result})
    queued = next((
        item for item in restored.data.get("acquisition_queue", [])
        if item.get("lane") == f"{canonical_symbol}:{canonical_timeframe}"
        and item.get("work_class") == "OPERATOR_FETCH"
    ), None)
    return finish_manual_only({
        "contract": "fragarach_ii.acquisition_result.v1", "work_class": "OPERATOR_FETCH",
        "operation_id": operation_id, "symbol": canonical_symbol,
        "timeframe": canonical_timeframe, "outcome": "WAITING",
        "requested_range": {"start": bounds[0], "end": bounds[1]},
        "canonical_edge_before": edge_before,
        "canonical_edge_after": _canonical_edge(database_path, canonical_symbol, canonical_timeframe),
        "expected_edge": freshness.get("expected_latest"),
        "providers_considered": recorded.get("providers_considered", []),
        "providers_attempted": [], "provider_results": [], "published_observations": 0,
        "authority_revision": revision_before, "freshness_result": freshness,
        "manual_request_created": None, "queue_state": queued,
    })


def _canonical_edge(database_path: str | Path, symbol: str, timeframe: str) -> str | None:
    with open_read_only(database_path) as connection:
        row = connection.execute(
            "SELECT max(open_time_utc),max(close_time_utc) FROM bars WHERE asset=? AND timeframe=?",
            (symbol, timeframe),
        ).fetchone()
    if not row or row[0] is None:
        return None
    return datetime.fromtimestamp(row[0] if timeframe == "D1" else row[1], UTC).isoformat()


def _lane_revision(database_path: str | Path, symbol: str, timeframe: str) -> str:
    with open_read_only(database_path) as connection:
        return authority_revision_for_lane(connection, symbol=symbol, timeframe=timeframe)


def _lane_freshness(
    database_path: str | Path, symbol: str, timeframe: str, observed: datetime
) -> dict[str, object]:
    with open_read_only(database_path) as connection:
        return assess_lane_freshness(
            connection, symbol=symbol, timeframe=timeframe, as_of=observed
        )


def _operator_progress(callback, stage: str, **facts: object) -> None:
    if callback is None:
        return
    try:
        callback(stage, **{key: value for key, value in facts.items() if value is not None})
    except TypeError:
        # Compatibility for existing one-argument progress observers.
        callback(stage)


def update_manual_request(
    database_path: str | Path,
    *,
    request_id: str,
    action: str,
    journal_path: str | Path | None = None,
    at: datetime | None = None,
) -> dict[str, object]:
    journal = SchedulerJournal(database_path, journal_path)
    now = normalized_utc(at)
    if action == "dismiss":
        request = dismiss_manual_request(journal.manual_requests, request_id, now)
    elif action == "acknowledge":
        request = next((item for item in journal.manual_requests if item.get("id") == request_id), None)
        if request is None:
            raise ValueError(f"unknown manual acquisition request: {request_id}")
        if request.get("status") != "Required":
            raise ValueError("only required requests may be acknowledged")
        request["status"] = "Acknowledged"
        request["acknowledged_at"] = now.isoformat()
    else:
        raise ValueError(f"unsupported manual request action: {action}")
    journal.save()
    return dict(request)


def update_scheduler_policy(
    database_path: str | Path,
    policy: str,
    *,
    journal_path: str | Path | None = None,
    at: datetime | None = None,
) -> dict[str, object]:
    """Persist an operator policy; the controller still selects utilization."""
    selected = normalize_policy(policy)
    journal = SchedulerJournal(database_path, journal_path)
    old = _scheduler_policy(journal)
    journal.data["scheduler_policy"] = selected
    journal.data.pop("queue_bandwidth", None)
    for item in journal.data.get("acquisition_queue", []):
        if item.get("operational_state") in {"Waiting for Budget", "Waiting for Local Budget"}:
            item.update(
                operational_state="Ready",
                queue_reason="Scheduler policy changed; adaptive capacity re-evaluation requested",
                waiting_reason=None,
                next_attempt=None,
                budget_wait=None,
            )
            journal.lane(str(item.get("symbol")), str(item.get("timeframe"))).update(
                queue_state="Ready",
                reason="Scheduler policy changed; adaptive capacity re-evaluation requested",
            )
    journal.data["queue_control_updated_at"] = normalized_utc(at).isoformat()
    journal.data["dispatch_generation"] = int(journal.data.get("dispatch_generation", 0)) + 1
    journal.save()
    return {
        "scheduler_policy": policy_label(selected),
        "scheduler_policy_key": selected,
        "previous_scheduler_policy": policy_label(old),
    }


def update_freshness_override(
    database_path: str | Path,
    *, timeframe: str, publication_delay_seconds: int,
    critical_after_closed_boundaries: int,
    journal_path: str | Path | None = None,
    at: datetime | None = None,
) -> dict[str, object]:
    """Persist a bounded runtime freshness tolerance and wake due dispatch."""
    normalized = timeframe.strip().upper()
    if normalized != "M5":
        raise ValueError("only M5 runtime freshness is operator-configurable")
    delay = int(publication_delay_seconds)
    critical = int(critical_after_closed_boundaries)
    if not 0 <= delay <= 3_600:
        raise ValueError("M5 publication grace must be between 0 and 3600 seconds")
    if not 1 <= critical <= 288:
        raise ValueError("M5 critical boundary threshold must be between 1 and 288")
    journal = SchedulerJournal(database_path, journal_path)
    overrides = journal.data.setdefault("freshness_overrides", {})
    previous = dict(overrides.get(normalized, {}))
    overrides[normalized] = {
        "allowed_publication_delay_seconds": delay,
        "freshness_thresholds": {
            normalized: {"critical_after_closed_boundaries": critical}
        },
        "updated_at": normalized_utc(at).isoformat(),
    }
    journal.data["run_queue_requested_at"] = normalized_utc(at).isoformat()
    journal.data["dispatch_generation"] = int(journal.data.get("dispatch_generation", 0)) + 1
    journal.save()
    return {"timeframe": normalized, "publication_delay_seconds": delay,
            "critical_after_closed_boundaries": critical, "previous": previous}


def update_queue_bandwidth(
    database_path: str | Path,
    percentage: int,
    **kwargs,
) -> dict[str, object]:
    """Compatibility adapter for older native clients; no percentage is stored."""
    value = int(percentage)
    if not 10 <= value <= 90:
        raise ValueError("legacy queue bandwidth must be between 10 and 90 percent")
    selected = (
        "CONSERVATIVE" if value < 55 else
        "BALANCED" if value < 78 else
        "HIGH_THROUGHPUT" if value < 90 else
        "MAXIMUM_CATCH_UP"
    )
    result = update_scheduler_policy(database_path, selected, **kwargs)
    result["legacy_percentage_ignored"] = value
    return result


def pause_acquisition(
    database_path: str | Path,
    *,
    scope_type: str,
    scope_identifier: str | None = None,
    reason: str = "OPERATOR_MAINTENANCE",
    temporary: bool = False,
    related_ingestion_session: str | None = None,
    journal_path: str | Path | None = None,
    at: datetime | None = None,
) -> dict[str, object]:
    journal = SchedulerJournal(database_path, journal_path)
    reconciliation = reconcile_operational_state(database_path, journal.data, at=at)
    record = create_pause(
        database_path, journal.data, scope_type=scope_type,
        scope_identifier=scope_identifier, reason=reason, temporary=temporary,
        related_ingestion_session=related_ingestion_session, at=at,
    )
    universe = reconciliation["universe"]
    for item in journal.data.get("acquisition_queue", []):
        lane = universe["active_lanes"].get(str(item.get("lane")))
        if lane and effective_pause_sources(journal.data, symbol=str(lane["symbol"]), group=str(lane["group"])):
            item.update(
                operational_state="Operator Paused", waiting_reason="OPERATOR_PAUSED",
                queue_reason="Dispatch paused by operator", next_attempt=None, budget_wait=None,
            )
    update_register = LaneUpdateRegister(database_path)
    for lane in universe["active_lanes"].values():
        if effective_pause_sources(
            journal.data, symbol=str(lane["symbol"]), group=str(lane["group"])
        ):
            try:
                update_register.pause(
                    asset=str(lane["symbol"]), timeframe=str(lane["timeframe"]), at=at,
                )
            except KeyError:
                # The first explicit pause can precede scheduler cutover.  Its
                # lane will be included by the next migration/audit instead.
                pass
    journal.data["dispatch_generation"] = int(journal.data.get("dispatch_generation", 0)) + 1
    journal.save()
    return dict(record)


def resume_acquisition(
    database_path: str | Path,
    *,
    pause_identifier: str | None = None,
    scope_type: str | None = None,
    scope_identifier: str | None = None,
    related_ingestion_session: str | None = None,
    journal_path: str | Path | None = None,
    at: datetime | None = None,
) -> dict[str, object]:
    """Resume matching records, then force canonical bounds to be rebuilt."""
    journal = SchedulerJournal(database_path, journal_path)
    changed = resume_pause(
        journal.data, pause_identifier=pause_identifier, scope_type=scope_type,
        scope_identifier=scope_identifier, related_ingestion_session=related_ingestion_session,
        at=at,
    )
    reconciliation = reconcile_operational_state(database_path, journal.data, at=at)
    universe = reconciliation["universe"]
    released_lane_ids = {
        lane_id
        for lane_id, lane in universe["active_lanes"].items()
        if any(_pause_scope_matches_lane(record, lane) for record in changed)
        and not effective_pause_sources(
            journal.data, symbol=str(lane["symbol"]), group=str(lane["group"])
        )
    }
    for item in list(journal.data.get("acquisition_queue", [])):
        lane = universe["active_lanes"].get(str(item.get("lane")))
        if lane and str(item.get("lane")) in released_lane_ids:
            item.update(
                operational_state="Ready", waiting_reason=None, next_attempt=None,
                budget_wait=None, queue_reason="Pause released; canonical bounds will be recalculated",
            )
    update_register = LaneUpdateRegister(database_path)
    for lane_id, lane in universe["active_lanes"].items():
        if lane_id in released_lane_ids:
            try:
                update_register.resume(
                    asset=str(lane["symbol"]), timeframe=str(lane["timeframe"]), at=at,
                )
            except KeyError:
                pass
    queue_by_id = {
        str(item.get("id")): item for item in journal.data.get("acquisition_queue", []) if item.get("id")
    }
    _prune_satisfied_queue(database_path, normalized_utc(at), queue_by_id, journal)
    journal.data["acquisition_queue"] = list(queue_by_id.values())
    journal.data["run_queue_requested_at"] = normalized_utc(at).isoformat()
    journal.data["dispatch_generation"] = int(journal.data.get("dispatch_generation", 0)) + 1
    journal.save()
    return {"outcome": "ACQUISITION_RESUMED", "resumed": [dict(item) for item in changed]}


def _pause_scope_matches_lane(pause: dict[str, object], lane: dict[str, object]) -> bool:
    """Whether a just-resumed pause previously controlled this active lane."""
    scope = str(pause.get("scope_type") or "").upper()
    identifier = str(pause.get("scope_identifier") or "")
    if scope == "ALL":
        return True
    if scope == "MARKET_OR_GROUP":
        return identifier == str(lane.get("group") or "")
    return scope == "SYMBOL" and identifier == str(lane.get("symbol") or "")


def request_run_queue(
    database_path: str | Path,
    *,
    journal_path: str | Path | None = None,
    at: datetime | None = None,
    credential: str | None = None,
) -> dict[str, object]:
    """Request a full canonical re-evaluation and immediate permitted drain."""
    now = normalized_utc(at)
    manual_report = reconcile_manual_requests(
        database_path, credential=credential, journal_path=journal_path,
        at=now, trigger="RUN_QUEUE_NOW",
    )
    journal = SchedulerJournal(database_path, journal_path)
    reconciliation = reconcile_operational_state(database_path, journal.data, at=now)
    universe = reconciliation["universe"]
    for lane in journal.data.setdefault("lanes", {}).values():
        if not isinstance(lane, dict):
            continue
        if lane.get("result") in {"FAILED", "WAITING"} or lane.get("manual_request"):
            lane["provider_attempts_by_boundary"] = {}
            lane["queue_state"] = "Ready"
    for request in journal.manual_requests:
        if request.get("status") in {"Required", "Acknowledged"}:
            request["automated_recheck_requested_at"] = now.isoformat()
    for item in journal.data.get("acquisition_queue", []):
        authority = universe["active_lanes"].get(str(item.get("lane")))
        paused = authority and effective_pause_sources(
            journal.data, symbol=str(authority["symbol"]), group=str(authority["group"])
        )
        if paused:
            item.update(operational_state="Operator Paused", waiting_reason="OPERATOR_PAUSED")
            continue
        if item.get("operational_state") == "Credential Repair Required":
            continue
        if item.get("operational_state") != "Running":
            item.update(
                operational_state="Ready", waiting_reason=None,
                next_attempt=None, budget_wait=None,
            )
    journal.data["run_queue_requested_at"] = now.isoformat()
    journal.data["dispatch_generation"] = int(journal.data.get("dispatch_generation", 0)) + 1
    journal.save()
    return {
        "outcome": "QUEUE_REEVALUATION_REQUESTED", "requested_at": now.isoformat(),
        "manual_request_reconciliation": manual_report,
    }


def reconcile_provider_setup_recovery(
    database_path: str | Path, *, symbol: str, timeframe: str,
    journal_path: str | Path | None = None, at: datetime | None = None,
    credential: str | None = None,
) -> dict[str, object]:
    """Queue one governed Update after a legacy provider mapping is approved."""
    observed = normalized_utc(at)
    canonical, lane_timeframe = symbol.strip().upper(), timeframe.strip().upper()
    journal = SchedulerJournal(database_path, journal_path)
    universe = reconcile_operational_state(database_path, journal.data, at=observed)["universe"]
    lane_id = f"{canonical}:{lane_timeframe}"
    authority = universe["active_lanes"].get(lane_id)
    if authority is None:
        return {"outcome": "LANE_NOT_AUTOMATION_ELIGIBLE", "lane": lane_id}
    with open_read_only(database_path) as connection:
        freshness = assess_lane_freshness(connection, symbol=canonical, timeframe=lane_timeframe, as_of=observed)
    canonical_edge, expected_edge = freshness.get("latest_canonical_observation"), freshness.get("expected_latest")
    if not canonical_edge:
        return {"outcome": "NO_CANONICAL_EDGE", "lane": lane_id}
    if not expected_edge or str(canonical_edge) >= str(expected_edge):
        return {"outcome": "ALREADY_CURRENT", "lane": lane_id, "canonical_edge": canonical_edge, "expected_edge": expected_edge}
    missing_start, missing_end = _acquisition_bounds(database_path, canonical, lane_timeframe, observed)
    profiles = tuple(load_provider_profiles())
    credentials = credential_map(credential)
    budgets = build_rate_budgets(profiles, journal.providers, wall_clock=lambda: observed, credential=credential)
    plan = acquisition_plan(
        database_path, symbol=canonical, timeframe=lane_timeframe,
        canonical_edge=str(canonical_edge), expected_edge=str(expected_edge),
        missing_start=missing_start, missing_end=missing_end,
        scheduled_boundary=f"PROVIDER_SETUP:{expected_edge}", profiles=profiles,
        provider_state=journal.providers, budgets=budgets, credentials=credentials,
        now=observed, work_class="QUEUE",
    )
    if not plan.get("selected_provider"):
        return {"outcome": "NO_ELIGIBLE_PROVIDER", "lane": lane_id, "providers_considered": plan.get("providers_considered", [])}
    queue = journal.data.setdefault("acquisition_queue", [])
    existing = next((item for item in queue if isinstance(item, dict) and item.get("lane") == lane_id), None)
    queue_id = str(existing.get("id")) if existing else f"{lane_id}:PROVIDER_SETUP:{expected_edge}"
    paused = effective_pause_sources(journal.data, symbol=canonical, group=str(authority.get("group", "")))
    item = {
        "id": queue_id, "lane": lane_id, "symbol": canonical, "timeframe": lane_timeframe,
        "asset_class": authority.get("asset_class"), "missing_range": {"start": missing_start, "end": missing_end},
        "selected_provider": plan["selected_provider"], "fallback_position": 0,
        "queue_reason": "Provider setup approved; governed Update queued",
        "estimated_requests": int(plan.get("estimated_request_count", 0) or 0),
        "budget_wait": None, "next_attempt": None, "missed_boundaries": 1, "work_class": "QUEUE",
        "dispatch_priority": (existing or {}).get("dispatch_priority", 0),
        "operational_state": "Operator Paused" if paused else "Ready",
        "waiting_reason": "OPERATOR_PAUSED" if paused else None,
        "enqueued_at": (existing or {}).get("enqueued_at") or observed.isoformat(),
        "required_boundary": (existing or {}).get("required_boundary") or expected_edge,
        "requested_through": max(str((existing or {}).get("requested_through") or ""), str(expected_edge)),
        "scheduled_boundary": f"PROVIDER_SETUP:{expected_edge}",
    }
    _trace_id, trace_created = ensure_trace_identity(item, lane_id=lane_id, now=observed, prior=existing)
    if existing is None: queue.append(item)
    else: queue[queue.index(existing)] = item
    journal.lane(canonical, lane_timeframe).update(
        queue_state=item["operational_state"], result="WAITING", reason=item["queue_reason"], manual_request=None,
        providers_considered=plan["providers_considered"], providers_rejected=[entry for entry in plan["providers_considered"] if not entry.get("eligible")],
        routing_decision=plan.get("selection_reason"), provider_attempts_by_boundary={},
    )
    if trace_created:
        record_event(journal.data, item, "QUEUE_CREATED", cycle_id="provider-setup-recovery", timestamp=observed, queue_id=queue_id, queue_disposition="ACTIVE", canonical_edge_before=canonical_edge, requested_start=missing_start, requested_end=missing_end)
    journal.data["dispatch_generation"] = int(journal.data.get("dispatch_generation", 0) or 0) + 1
    journal.save()
    return {"outcome": "UPDATE_QUEUED" if existing is None else "UPDATE_QUEUE_RESTORED", "lane": lane_id, "queue_identifier": queue_id, "canonical_edge": canonical_edge, "expected_edge": expected_edge, "request_start": missing_start, "request_end": missing_end, "selected_provider": plan["selected_provider"]}


def request_retry(
    database_path: str | Path,
    *,
    lane_id: str | None = None,
    request_id: str | None = None,
    journal_path: str | Path | None = None,
    at: datetime | None = None,
    credential: str | None = None,
) -> dict[str, object]:
    """Deduplicate an operator retry and defer all authority checks to dispatch."""
    if bool(lane_id) == bool(request_id):
        raise ValueError("exactly one lane id or manual request id is required")
    now = normalized_utc(at)
    if request_id:
        reconcile_manual_requests(
            database_path, credential=credential, journal_path=journal_path,
            at=now, trigger="RETRY_NOW",
        )
    journal = SchedulerJournal(database_path, journal_path)
    reconciliation = reconcile_operational_state(database_path, journal.data, at=now)
    if request_id:
        request = next((item for item in journal.manual_requests if item.get("id") == request_id), None)
        if request is None:
            raise ValueError(f"unknown manual acquisition request: {request_id}")
        if request.get("reconciliation_status") == "AUTOMATION_RESTORED":
            return {
                "outcome": "AUTOMATION_RESTORED_AND_QUEUED",
                "lane": f"{request['symbol']}:{request['timeframe']}",
                "queue_identifier": request.get("replacement_queue_identifier"),
            }
        if request.get("reconciliation_status") == "REQUEST_ALREADY_SATISFIED":
            return {"outcome": "ALREADY_SATISFIED", "lane": f"{request['symbol']}:{request['timeframe']}"}
        if request.get("reconciliation_status") == "AUTOMATION_TEMPORARILY_BLOCKED":
            return {
                "outcome": str(request.get("reconciliation_reason") or "AUTOMATION_TEMPORARILY_BLOCKED"),
                "lane": f"{request['symbol']}:{request['timeframe']}",
            }
        if request.get("reconciliation_status") == "STILL_NO_ELIGIBLE_PROVIDER":
            return {
                "outcome": "STILL_MANUAL_NO_ELIGIBLE_PROVIDER",
                "lane": f"{request['symbol']}:{request['timeframe']}",
            }
        if request.get("status") not in {"Required", "Acknowledged"}:
            raise ValueError("retry is available only for unresolved manual requests")
        lane_id = f"{request['symbol']}:{request['timeframe']}"
        request["retry_requested_at"] = request.get("retry_requested_at") or now.isoformat()
    try:
        symbol, timeframe = str(lane_id).split(":", 1)
    except ValueError as error:
        raise ValueError("lane id must be SYMBOL:TIMEFRAME") from error
    authority = reconciliation["universe"]["active_lanes"].get(str(lane_id))
    if authority is None:
        raise ValueError("retry is unavailable for an inactive or uncommissioned lane")
    pauses = effective_pause_sources(
        journal.data, symbol=symbol, group=str(authority["group"])
    )
    if pauses:
        raise ValueError("retry cannot bypass an effective acquisition pause")
    with open_read_only(database_path) as connection:
        freshness = assess_lane_freshness(connection, symbol=symbol, timeframe=timeframe, as_of=now)
    if freshness.get("state") == "Current":
        journal.data["acquisition_queue"] = [
            item for item in journal.data.get("acquisition_queue", [])
            if item.get("lane") != lane_id
        ]
        lane = journal.lane(symbol, timeframe)
        lane.update(queue_state=None, result="SATISFIED", reason="Canonical evidence already satisfies the expected edge")
        journal.save()
        return {"outcome": "ALREADY_SATISFIED", "lane": lane_id}
    lane = journal.lane(symbol, timeframe)
    already_pending = bool(lane.get("operator_retry_pending"))
    lane["operator_retry_pending"] = True
    lane["operator_retry_requested_at"] = lane.get("operator_retry_requested_at") or now.isoformat()
    lane["queue_state"] = "Ready"
    lane["reason"] = "Operator retry queued for canonical re-evaluation"
    if not already_pending:
        lane["provider_attempts_by_boundary"] = {}
    for item in journal.data.get("acquisition_queue", []):
        if item.get("lane") == lane_id:
            item.update(
                work_class="OPERATOR_RETRY", operational_state="Ready",
                queue_reason="Operator retry requested", waiting_reason=None,
                next_attempt=None, budget_wait=None,
            )
    update_register = LaneUpdateRegister(database_path)
    if not update_register.is_seeded():
        update_register.initialize_if_needed(at=now)
    update_register.retry(
        asset=symbol, timeframe=timeframe, reason="OPERATOR_RETRY", at=now,
        not_before=now,
    )
    journal.data["dispatch_generation"] = int(journal.data.get("dispatch_generation", 0)) + 1
    journal.save()
    return {
        "outcome": "RETRY_ALREADY_QUEUED" if already_pending else "RETRY_QUEUED",
        "lane": lane_id,
        "requested_at": lane["operator_retry_requested_at"],
    }


def _scheduler_policy(journal: SchedulerJournal) -> str:
    try:
        return normalize_policy(journal.data.get("scheduler_policy", "BALANCED"))
    except ValueError:
        return "BALANCED"


def _queue_percentage(journal: SchedulerJournal) -> int:
    """Maximum eligibility ceiling used only before a live pressure decision."""
    return round(float(POLICIES[_scheduler_policy(journal)]["maximum"]) * 100)


def _queue_summary(queue, manual_requests, last_dispatch, now, *, throughput=None):
    states = [str(item.get("operational_state", "Ready")) for item in queue]
    ages = []
    ready_ages = []
    for item in queue:
        try:
            age = max(0.0, (now - datetime.fromisoformat(str(item.get("enqueued_at")))).total_seconds())
            ages.append(age)
            if str(item.get("operational_state", "Ready")) == "Ready":
                ready_ages.append(age)
        except (TypeError, ValueError):
            continue
    estimated_requests = sum(max(1, int(item.get("estimated_requests", 1) or 1)) for item in queue)
    ready = states.count("Ready")
    if throughput is not None:
        estimate = throughput.get("estimated_completion_seconds") if (ready or states.count("Running")) else None
    else:
        estimate = None if not queue else max(1, estimated_requests) * 60
    actionable = [item for item in manual_requests if item.get("status") in ACTIONABLE_REQUEST_STATES]
    return {
        "total_queued": len(queue),
        "ready_now": ready,
        "running": states.count("Running"),
        "waiting_for_budget": states.count("Waiting for Budget") + states.count("Waiting for Local Budget"),
        "cooling_down": sum(state in {"Cooling Down", "Remote Rate Limited", "Transient Provider Backoff", "Provider Unavailable"} for state in states),
        "blocked": states.count("Blocked"),
        "manual_required": len(actionable),
        "manual_request_unique_lanes": len({f"{item.get('symbol')}:{item.get('timeframe')}" for item in actionable}),
        "manual_request_unique_symbols": len({str(item.get("symbol")) for item in actionable}),
        "oldest_queued_age_seconds": max(ages) if ages else None,
        "oldest_ready_age_seconds": max(ready_ages) if ready_ages else None,
        "last_dispatch": last_dispatch,
        "estimated_clear_time_seconds": estimate,
        "estimated_clear_time_label": (
            "Waiting for dispatchable provider capacity"
            if queue and estimate is None else
            "Estimate based on adaptive policy and current safe provider capacity"
        ),
    }


def _waiting_detail(temporary, next_attempt, category):
    providers = ", ".join(sorted(str(item.get("provider")) for item in temporary))
    detail = f"Waiting for {category}: {providers}"
    return f"{detail} until {next_attempt}" if next_attempt else detail


def _structured_provider_result(classification: str) -> str:
    return {
        "NO_NEW_DATA": "NO_NEW_DATA", "TIMEFRAME_UNSUPPORTED": "TIMEFRAME_UNSUPPORTED",
        "NO_APPROVED_MAPPING": "NO_APPROVED_MAPPING", "RANGE_UNAVAILABLE": "RANGE_UNAVAILABLE",
        "TWELVEDATA_RATE_LIMIT_429": "REMOTE_RATE_LIMITED", "RATE_BUDGET_EXHAUSTED": "WAITING_FOR_LOCAL_BUDGET",
        "ADAPTIVE_CAPACITY_RESERVED": "WAITING_FOR_LOCAL_BUDGET",
        "QUEUE_BANDWIDTH_EXHAUSTED": "WAITING_FOR_LOCAL_BUDGET",
        "TWELVEDATA_TRANSPORT_FAILURE": "TRANSIENT_PROVIDER_FAILURE",
        "TWELVEDATA_UPSTREAM_5XX": "TRANSIENT_PROVIDER_FAILURE",
        "TWELVEDATA_INVALID_RESPONSE": "INVALID_EVIDENCE",
        "CREDENTIAL_MISSING": "CREDENTIAL_MISSING", "AUTHENTICATION_FAILED": "AUTHENTICATION_FAILED", "ENTITLEMENT_BLOCKED": "ENTITLEMENT_BLOCKED",
        "INVALID_RESPONSE": "INVALID_EVIDENCE", "INVALID_CHRONOLOGY": "INVALID_EVIDENCE",
        "INVALID_OHLC": "INVALID_EVIDENCE", "ORIENTATION_MISMATCH": "INVALID_EVIDENCE",
        "LOCAL_PROGRAMMING_ERROR": "LOCAL_PROGRAMMING_ERROR",
    }.get(classification, "TRANSIENT_PROVIDER_FAILURE")


def _planned_request_records(journal, *, provider, lane, scheduled_boundary, request_count, now):
    records = journal.data.setdefault("request_lifecycle", [])
    result = []
    for index in range(request_count):
        identifier = f"request:{lane}:{scheduled_boundary}:{provider}:{index}"
        record = next((item for item in records if item.get("id") == identifier), None)
        if record is None or record.get("state") in {"FAILED_BEFORE_DISPATCH", "FAILED_AFTER_DISPATCH", "CANCELLED"}:
            identifier = f"{identifier}:{uuid.uuid4().hex[:8]}" if record else identifier
            record = {
                "id": identifier, "provider": provider, "lane": lane,
                "scheduled_boundary": scheduled_boundary, "request_index": index,
                "state": "PLANNED", "planned_at": now.isoformat(),
            }
            records.append(record)
        result.append(record)
    del records[:-1000]
    return result


def _unavailable_lane_details(rows):
    details = []
    for row in rows:
        if row.get("scheduler_state") != "Unavailable":
            continue
        diagnostics = row.get("calendar_diagnostics") or {}
        reason = str(row.get("reason") or "EXPECTED_EDGE_UNAVAILABLE")
        if reason == "EXPECTED_CANONICAL_EDGE_UNAVAILABLE":
            reason = "EXPECTED_EDGE_UNAVAILABLE"
        if reason == "OPERATIONAL_CALENDAR_UNAVAILABLE":
            reason = "CALENDAR_UNAVAILABLE"
        details.append({
            "id": row["id"], "symbol": row["symbol"], "timeframe": row["timeframe"],
            "market": row.get("market"),
            "latest_canonical_edge": row.get("latest_canonical_observation"),
            "expected_edge": row.get("expected_latest"), "structured_reason": reason,
            "calendar_identifier": diagnostics.get("calendar_identifier"), "provider_eligibility": row.get("providers_considered", []),
            "calendar_status": diagnostics.get("calendar_status"),
            "timezone": diagnostics.get("timezone"),
            "session_close_rule": diagnostics.get("session_close_rule"),
            "calculation_time": diagnostics.get("calculation_time"),
            "exact_failure_reason": diagnostics.get("exact_failure_reason"),
            "last_successful_acquisition": row.get("last_acquisition"),
            "recommended_action": "Open Calendar Detail" if "CALENDAR" in reason or "SESSION" in reason else "Open Lane Detail",
        })
    return details


def _manual_request_details(requests, universe, journal, now):
    result = []
    for raw in requests:
        if raw.get("status") not in ACTIONABLE_REQUEST_STATES:
            continue
        item = dict(raw)
        lane_id = f"{item.get('symbol')}:{item.get('timeframe')}"
        authority = universe["active_lanes"].get(lane_id)
        sources = effective_pause_sources(
            journal, symbol=str(item.get("symbol")), group=str((authority or {}).get("group", ""))
        ) if authority else []
        try:
            age = max(0.0, (now - datetime.fromisoformat(str(item.get("created_at")))).total_seconds())
        except (TypeError, ValueError):
            age = None
        failures = list(item.get("provider_failure_summaries", []))
        item.update(
            request_age_seconds=age,
            latest_failure=failures[-1] if failures else None,
            instrument_lifecycle_state=(authority or {}).get("lifecycle_state", "INACTIVE"),
            lane_commissioning_state="ACTIVE" if authority else "NOT_COMMISSIONED",
            pause_state="OPERATOR_PAUSED" if sources else None,
        )
        result.append(item)
    return result


def _exception_filters(rows, queue, manual_requests):
    actionable = [item for item in manual_requests if item.get("status") in ACTIONABLE_REQUEST_STATES]
    return {
        "Total Queued": [str(item.get("id")) for item in queue],
        "Ready Now": [str(item.get("id")) for item in queue if item.get("operational_state", "Ready") == "Ready"],
        "Running": [str(item.get("id")) for item in queue if item.get("operational_state") == "Running"],
        "Waiting for Budget": [str(item.get("id")) for item in queue if item.get("operational_state") == "Waiting for Local Budget"],
        "Cooling or Backoff": [str(item.get("id")) for item in queue if item.get("operational_state") in {"Remote Rate Limited", "Transient Provider Backoff"}],
        "Blocked": [str(item.get("id")) for item in queue if item.get("operational_state") == "Blocked"],
        "Manual Required": [str(item.get("id")) for item in actionable],
        "Current": [str(item["id"]) for item in rows if item.get("scheduler_state") == "Current"],
        "Behind": [str(item["id"]) for item in rows if item.get("scheduler_state") == "Behind"],
        "Unavailable": [str(item["id"]) for item in rows if item.get("scheduler_state") == "Unavailable"],
        "Paused": [str(item["id"]) for item in rows if item.get("pause_state")],
    }


def _timeframe_rank(timeframe: str) -> int:
    return {"D1": 0, "H1": 1, "M30": 2, "M5": 3}.get(timeframe, 99)


def _prune_satisfied_queue(database_path, observed, queue_by_id, journal):
    with open_read_only(database_path) as connection:
        for queue_id, item in list(queue_by_id.items()):
            try:
                freshness = assess_lane_freshness(
                    connection, symbol=str(item["symbol"]), timeframe=str(item["timeframe"]), as_of=observed
                )
            except (KeyError, ValueError):
                continue
            if freshness.get("state") == "Current":
                queue_by_id.pop(queue_id, None)
                journal.lane(str(item["symbol"]), str(item["timeframe"])).update(
                    queue_state=None, result="SATISFIED", reason=None
                )


def _scheduled_demand_forecast(database_path, profiles, observed, journal):
    """Count commissioned boundaries expected before each rolling budget releases."""
    demand = {profile.provider: 0 for profile in profiles}
    next_demand: dict[str, str] = {}
    with open_read_only(database_path) as connection:
        lanes = connection.execute("SELECT asset,timeframe FROM evidence_lanes ORDER BY asset,timeframe").fetchall()
        for symbol, timeframe in lanes:
            schedule = schedule_for_lane(connection, symbol=symbol, timeframe=timeframe, after=observed)
            raw = schedule.get("next_scheduled_acquisition")
            if not raw:
                continue
            boundary = datetime.fromisoformat(str(raw))
            for profile in profiles:
                if timeframe not in profile.supported_timeframes:
                    continue
                current = next_demand.get(profile.provider)
                if current is None or raw < current:
                    next_demand[profile.provider] = str(raw)
                if boundary <= observed + timedelta(seconds=profile.request_window_seconds):
                    demand[profile.provider] += 1
    for profile in profiles:
        journal.providers.setdefault(profile.provider, {})["next_scheduled_demand"] = next_demand.get(profile.provider)
    return demand


def _lane_state(freshness, recorded, *, active_activity, symbol, timeframe):
    if active_activity and active_activity.get("symbol") == symbol and active_activity.get("timeframe") == timeframe:
        return "Running"
    if recorded.get("queue_state") in {"Ready", "Waiting for Budget", "Waiting for Local Budget", "Cooling Down", "Remote Rate Limited", "Transient Provider Backoff", "Provider Unavailable", "Operator Paused", "Blocked", "Manual Required"}:
        return str(recorded["queue_state"])
    if freshness["state"] == "Current":
        return "Current"
    if recorded.get("result") == "FAILED":
        return "Failed"
    if freshness.get("latest_canonical_observation") is None:
        return "No Evidence"
    if freshness.get("expected_latest") is None:
        return "Unavailable"
    return "Behind"


def _normalized_publication_state(entry: object) -> str:
    """Project every publication sidecar spelling to the one UI contract."""
    raw = str(entry.get("state") or "") if isinstance(entry, dict) else ""
    state = raw.strip().upper()
    if state in {"PENDING", "QUEUED", "PUBLISHING"}:
        return "PUBLISHING"
    if state in {"FAILED", "FAILED_RETRYABLE"}:
        return "FAILED_RETRYABLE"
    return "PUBLISHED"


def _authority_health(service_state, counts):
    if service_state != "Running":
        return {"state": "CRITICAL", "detail": "Scheduler stopped"}
    degraded = counts["Behind"] + counts["Unavailable"] + counts["Failed"]
    if degraded:
        return {"state": "DEGRADED", "detail": f"{degraded} lanes require attention"}
    return {"state": "HEALTHY", "detail": "All commissioned lanes are current"}
