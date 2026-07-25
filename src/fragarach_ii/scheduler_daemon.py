"""Persistent, user-scoped Scheduler service and LaunchAgent management.

Operational service state lives beside the Scheduler journal or in the user's
Application Support directory.  Nothing in this module writes canonical market
evidence.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import plistlib
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


SERVICE_LABEL = "com.raymorgan.fragarach-ii.scheduler"
SERVICE_BUILD = os.environ.get("FRAGARACH_SERVICE_BUILD", "0.1.0")
MINIMUM_COMPATIBLE_BUILD = "0.1.0"
STATUS_CONTRACT = "fragarach_ii.scheduler_service_status.v1"
COMMAND_CONTRACT = "fragarach_ii.scheduler_service_command.v1"
MONITOR_CONTRACT = "fragarach_ii.scheduler_monitor.v3"
JOURNAL_FORMAT_VERSION = 4
# A live monitor includes the bounded queue, lane, provider, and diagnostic
# projections. Real authority snapshots can exceed 1 MiB without being
# malformed, so keep a bounded but comfortably larger transport ceiling.
_SOCKET_LIMIT = 8 * 1024 * 1024
_SOCKET_CLIENT_TIMEOUT = 10.0
MUTATION_CONTRACT = "fragarach_ii.scheduler_service_mutation.v1"
MUTATION_TYPES = frozenset({
    "INSTALL", "START", "STOP", "RESTART", "UPDATE", "REPAIR", "ENABLE",
    "DISABLE", "UNINSTALL", "FORCE_RECONCILE",
})
ACTIVE_MUTATION_STATUSES = frozenset({"REQUESTED", "RUNNING", "WAITING"})
TERMINAL_MUTATION_STATUSES = frozenset({
    "COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED", "ABANDONED",
})
STAGE_TIMEOUTS: dict[str, float] = {
    "VALIDATING_INSTALLATION": 10.0,
    "REQUESTING_LAUNCH": 10.0,
    "WAITING_FOR_PROCESS": 10.0,
    "WAITING_FOR_SOCKET": 15.0,
    "WAITING_FOR_HEARTBEAT": 15.0,
    "VERIFYING_SERVICE_GENERATION": 10.0,
    "REQUESTING_GRACEFUL_STOP": 10.0,
    "DRAINING_ACTIVE_WORK": 30.0,
    "WAITING_FOR_PROCESS_EXIT": 15.0,
    "VERIFYING_OWNERSHIP_RELEASE": 10.0,
    "INSPECTING_LAUNCH_AGENT": 10.0,
    "INSPECTING_EXECUTABLE": 10.0,
    "VERIFYING_SIGNATURE": 15.0,
    "VERIFYING_PATHS": 10.0,
    "CHECKING_AUTHORITY": 10.0,
    "CHECKING_JOURNAL": 10.0,
    "CHECKING_SOCKET": 10.0,
    "CHECKING_OWNERSHIP": 10.0,
    "REPAIRING_FILES": 15.0,
    "RELOADING_LAUNCH_AGENT": 15.0,
    "VERIFYING_HEARTBEAT": 15.0,
    "VALIDATING_NEW_BUILD": 10.0,
    "REQUESTING_SERVICE_STOP": 10.0,
    "WAITING_FOR_OWNERSHIP_RELEASE": 10.0,
    "REPLACING_SERVICE": 15.0,
    "UPDATING_LAUNCH_AGENT": 15.0,
    "STARTING_NEW_SERVICE": 10.0,
    "VERIFYING_COMPATIBILITY": 10.0,
    "WRITING_SERVICE_FILES": 15.0,
    "VERIFYING_INSTALLATION": 10.0,
    "REQUESTING_DISABLE": 10.0,
    "REQUESTING_ENABLE": 10.0,
    "REMOVING_LAUNCH_AGENT": 15.0,
    "VERIFYING_REMOVAL": 10.0,
    "INSPECTING_SERVICE_STATE": 10.0,
    "REBUILDING_SERVICE_PROJECTION": 10.0,
}
CANCELLABLE_MUTATION_STAGES = frozenset({
    "VALIDATING_INSTALLATION", "WAITING_FOR_PROCESS", "WAITING_FOR_SOCKET",
    "WAITING_FOR_HEARTBEAT", "INSPECTING_LAUNCH_AGENT", "INSPECTING_EXECUTABLE",
    "VERIFYING_SIGNATURE", "VERIFYING_PATHS", "CHECKING_AUTHORITY",
    "CHECKING_JOURNAL", "CHECKING_SOCKET", "CHECKING_OWNERSHIP",
    "VALIDATING_NEW_BUILD", "INSPECTING_SERVICE_STATE",
})
COMPACT_STATUS_KEYS = (
    "contract", "monitor_contract_version", "command_contract_version",
    "journal_format_version", "minimum_compatible_build", "service_state",
    "service_build", "running_build", "service_instance", "service_generation",
    "service_start_time", "heartbeat_time", "heartbeat_cycle_id",
    "heartbeat_cycle_state", "last_successful_monitor_update",
    "authority_database_identity", "restart_count", "installed",
    "service_location", "authority_database", "operational_journal",
    "automatic_login_start", "credential_source", "live", "generated_at",
    "authority_health", "authority_revision", "authority_change_token", "active_universe_revision",
    "summary", "next_run", "active_activity", "queue_summary",
    "scheduler_progress", "manual_request_count",
    "manual_request_unique_lanes", "manual_request_unique_symbols",
    "operational_health", "scheduler_policy", "scheduler_policy_key",
)
COMPACT_EXECUTION_KEYS = (
    "contract", "cycle_id", "started_at", "completed_at", "duration_ms",
    "cycle_overrun", "cycle_overrun_ms", "selected_count", "deferred_count",
    "failed_count", "active_workers", "available_workers",
    "peak_active_workers", "queue_depth_before", "queue_depth_after",
    "oldest_queue_age_before", "oldest_queue_age_after",
    "throughput_limited_by", "credits_consumed", "credits_remaining",
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def authority_database_identity(database: str | Path) -> str:
    path = Path(database).expanduser().resolve()
    try:
        stat = path.stat()
        source = f"{path}|{stat.st_dev}|{stat.st_ino}"
    except OSError:
        source = str(path)
    return hashlib.sha256(source.encode()).hexdigest()


@dataclass(frozen=True)
class ServicePaths:
    database: Path
    journal: Path
    support: Path
    status: Path
    ownership: Path
    commands: Path
    restart_history: Path
    metadata: Path
    socket: Path
    launch_agent: Path
    stdout_log: Path
    stderr_log: Path
    mutation: Path
    mutation_lock: Path
    mutation_cancel: Path

    @classmethod
    def create(
        cls,
        database: str | Path,
        *,
        journal: str | Path | None = None,
        support: str | Path | None = None,
        home: str | Path | None = None,
    ) -> "ServicePaths":
        database_path = Path(database).expanduser().resolve()
        journal_path = Path(journal).expanduser().resolve() if journal else Path(f"{database_path}.scheduler.json")
        user_home = Path(home).expanduser().resolve() if home else Path.home()
        identity = authority_database_identity(database_path)[:16]
        support_path = (
            Path(support).expanduser().resolve()
            if support
            else user_home / "Library" / "Application Support" / "Fragarach II" / "Scheduler" / identity
        )
        # AF_UNIX paths are short on macOS.  Use a user-private directory in /tmp.
        socket_root = Path(tempfile.gettempdir()) / f"fragarach-scheduler-{os.getuid()}"
        return cls(
            database=database_path,
            journal=journal_path,
            support=support_path,
            status=support_path / "service-status.json",
            ownership=support_path / "acquisition-owner.lock",
            commands=support_path / "command-acknowledgements.json",
            restart_history=support_path / "restart-history.json",
            metadata=support_path / "installation.json",
            socket=socket_root / f"{identity}.sock",
            launch_agent=user_home / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist",
            stdout_log=support_path / "scheduler-service.log",
            stderr_log=support_path / "scheduler-service-error.log",
            mutation=support_path / "service-mutations.json",
            mutation_lock=support_path / "service-mutation.lock",
            mutation_cancel=support_path / "service-mutation-cancel.json",
        )

    def prepare(self) -> None:
        self.support.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.socket.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.support, 0o700)
        os.chmod(self.socket.parent, 0o700)


def _atomic_json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        handle = os.fdopen(descriptor, "w", encoding="utf-8")
        descriptor = -1  # ownership transferred to the file object
        with handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _automatic_login_start(paths: ServicePaths) -> bool:
    metadata = _read_json(paths.metadata, {})
    if isinstance(metadata, dict) and "automatic_login_start" in metadata:
        return bool(metadata["automatic_login_start"])
    return paths.launch_agent.exists()


class AcquisitionOwnership:
    """Lifetime, non-blocking owner lock with inspectable heartbeat metadata."""

    def __init__(self, paths: ServicePaths, *, instance: str, generation: str) -> None:
        self.paths = paths
        self.instance = instance
        self.generation = generation
        self.started_at = utc_now()
        self._handle: Any = None
        self._guard = threading.Lock()

    def acquire(self) -> None:
        self.paths.prepare()
        handle = self.paths.ownership.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            handle.close()
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                raise RuntimeError("SERVICE_OWNS_ACQUISITION") from error
            raise
        self._handle = handle
        self.heartbeat("STARTING")

    def heartbeat(self, phase: str, **facts: Any) -> None:
        if self._handle is None:
            return
        value = {
            "authority_database_identity": authority_database_identity(self.paths.database),
            "authority_database": str(self.paths.database),
            "scheduler_instance_identifier": self.instance,
            "service_build": SERVICE_BUILD,
            "process_id": os.getpid(),
            "process_start_time": self.started_at,
            "heartbeat_time": utc_now(),
            "ownership_generation": self.generation,
            "scheduler_phase": phase,
            **facts,
        }
        payload = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
        with self._guard:
            self._handle.seek(0)
            self._handle.truncate()
            self._handle.write(payload)
            self._handle.flush()
            os.fsync(self._handle.fileno())

    def release(self) -> None:
        if self._handle is None:
            return
        with self._guard:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None
        self.paths.ownership.unlink(missing_ok=True)

    def __enter__(self) -> "AcquisitionOwnership":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


def ownership_is_active(paths: ServicePaths) -> bool:
    paths.prepare()
    handle = paths.ownership.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                return True
            raise
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return False
    finally:
        handle.close()


def _mutation_document(paths: ServicePaths) -> dict[str, Any]:
    value = _read_json(paths.mutation, {})
    if not isinstance(value, dict) or value.get("contract") != MUTATION_CONTRACT:
        value = {
            "contract": MUTATION_CONTRACT,
            "generation": 0,
            "active_mutation": None,
            "last_operation": None,
            "history": [],
            "reconciliation_status": "NO_MUTATION",
        }
    value.setdefault("generation", 0)
    value.setdefault("active_mutation", None)
    value.setdefault("last_operation", None)
    value.setdefault("history", [])
    value.setdefault("reconciliation_status", "NO_MUTATION")
    return value


def _save_mutation_document(paths: ServicePaths, value: dict[str, Any]) -> None:
    value["contract"] = MUTATION_CONTRACT
    value["generation"] = int(value.get("generation", 0)) + 1
    _atomic_json(paths.mutation, value)


def _parse_timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _pid_is_alive(value: object) -> bool:
    try:
        process_id = int(value)
        if process_id <= 0:
            return False
        os.kill(process_id, 0)
        return True
    except (TypeError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True


def _stage_timeout(record: dict[str, Any], overrides: dict[str, float] | None = None) -> float:
    stage = str(record.get("current_stage") or "")
    return float((overrides or {}).get(stage, STAGE_TIMEOUTS.get(stage, 30.0)))


def _record_age(record: dict[str, Any], field: str = "last_progress_at") -> float:
    then = _parse_timestamp(record.get(field))
    return (datetime.now(UTC) - then).total_seconds() if then else float("inf")


def _terminalize_mutation(
    paths: ServicePaths,
    document: dict[str, Any],
    record: dict[str, Any],
    status: str,
    *,
    failure_code: str | None = None,
    failure_detail: str | None = None,
    reconciliation_status: str | None = None,
) -> dict[str, Any]:
    now = utc_now()
    record.update(
        status=status,
        completed_at=now,
        last_progress_at=now,
        cancellable=False,
    )
    if status == "COMPLETED":
        record.update(current_stage="COMPLETED", progress_message="Operation completed")
    record.setdefault("stage_history", []).append({
        "stage": record.get("current_stage"), "at": now,
        "message": record.get("progress_message"), "status": status,
    })
    if failure_code is not None:
        record["failure_code"] = failure_code
    if failure_detail is not None:
        record["failure_detail"] = failure_detail
    document["active_mutation"] = None
    document["last_operation"] = record
    history = document.setdefault("history", [])
    history.insert(0, dict(record))
    del history[50:]
    if reconciliation_status:
        document["reconciliation_status"] = reconciliation_status
    _save_mutation_document(paths, document)
    paths.mutation_cancel.unlink(missing_ok=True)
    return record


def _cached_service_is_healthy(paths: ServicePaths) -> bool:
    cached = _read_json(paths.status, {})
    heartbeat = _parse_timestamp(cached.get("heartbeat_time")) if isinstance(cached, dict) else None
    recent = bool(heartbeat and (datetime.now(UTC) - heartbeat).total_seconds() <= 6)
    return bool(recent and cached.get("service_state") in {"RUNNING", "DEGRADED"})


def _reconcile_mutation_locked(
    paths: ServicePaths,
    document: dict[str, Any],
    *,
    stage_timeouts: dict[str, float] | None = None,
) -> dict[str, Any]:
    record = document.get("active_mutation")
    if not isinstance(record, dict) or record.get("status") not in ACTIVE_MUTATION_STATUSES:
        if record is not None:
            document["active_mutation"] = None
            _save_mutation_document(paths, document)
        document["reconciliation_status"] = "NO_ACTIVE_OPERATION"
        return {"outcome": "NO_ACTIVE_OPERATION", "active_mutation": None}

    operation = str(record.get("operation_type"))
    owner_active = ownership_is_active(paths)
    socket_present = paths.socket.exists()
    healthy = owner_active and socket_present and _cached_service_is_healthy(paths)
    if operation in {"INSTALL", "START", "RESTART", "UPDATE", "REPAIR", "ENABLE"} and healthy:
        completed = _terminalize_mutation(
            paths, document, record, "COMPLETED",
            reconciliation_status="OPERATION_COMPLETED_EXTERNALLY",
        )
        return {"outcome": "OPERATION_COMPLETED_EXTERNALLY", "active_mutation": None, "operation": completed}
    if operation in {"STOP", "DISABLE", "UNINSTALL"} and not owner_active and not socket_present:
        completed = _terminalize_mutation(
            paths, document, record, "COMPLETED",
            reconciliation_status="OPERATION_COMPLETED_EXTERNALLY",
        )
        return {"outcome": "OPERATION_COMPLETED_EXTERNALLY", "active_mutation": None, "operation": completed}

    age = _record_age(record)
    timeout = _stage_timeout(record, stage_timeouts)
    helper_alive = _pid_is_alive(record.get("helper_process_pid"))
    app_alive = _pid_is_alive(record.get("requesting_app_pid"))
    if not helper_alive and not app_alive:
        abandoned = _terminalize_mutation(
            paths, document, record, "ABANDONED",
            failure_code="MUTATION_OWNER_EXITED",
            failure_detail="The requesting app and lifecycle helper are no longer running, and no service transition is active.",
            reconciliation_status="STALE_OPERATION_CLEARED",
        )
        return {"outcome": "STALE_OPERATION_CLEARED", "active_mutation": None, "operation": abandoned}
    if age > timeout:
        timed_out = _terminalize_mutation(
            paths, document, record, "TIMED_OUT",
            failure_code="MUTATION_STAGE_TIMEOUT",
            failure_detail=(
                f"{record.get('operation_type')} did not progress beyond "
                f"{record.get('current_stage')} within {timeout:g} seconds."
            ),
            reconciliation_status="OPERATION_TIMED_OUT",
        )
        return {"outcome": "OPERATION_TIMED_OUT", "active_mutation": None, "operation": timed_out}

    if helper_alive or app_alive or age <= timeout:
        document["reconciliation_status"] = "ACTIVE_OPERATION_CONFIRMED"
        return {
            "outcome": "ACTIVE_OPERATION_CONFIRMED",
            "active_mutation": record,
            "evidence": {
                "requesting_app_alive": app_alive,
                "helper_process_alive": helper_alive,
                "recent_progress": age <= timeout,
                "acquisition_owner_active": owner_active,
                "socket_present": socket_present,
            },
        }

    return {"outcome": "ACTIVE_OPERATION_CONFIRMED", "active_mutation": record}


def reconcile_service_mutation(
    paths: ServicePaths,
    *,
    stage_timeouts: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Reconcile only the service-mutation domain; never alter acquisition ownership."""
    paths.prepare()
    handle = paths.mutation_lock.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EAGAIN}:
                raise
            document = _mutation_document(paths)
            return {
                "outcome": "ACTIVE_OPERATION_CONFIRMED",
                "active_mutation": document.get("active_mutation"),
                "evidence": {"lifecycle_helper_holds_mutation_lock": True},
            }
        return _reconcile_mutation_locked(paths, _mutation_document(paths), stage_timeouts=stage_timeouts)
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()


class MutationActiveError(RuntimeError):
    def __init__(self, record: dict[str, Any]) -> None:
        self.record = record
        operation = str(record.get("operation_type", "Service mutation")).title()
        stage = str(record.get("current_stage", "Unknown")).replace("_", " ").title()
        super().__init__(f"{operation} is active at {stage}; wait, view details, or cancel when available.")


class MutationCancelled(RuntimeError):
    pass


class MutationStageTimedOut(TimeoutError):
    def __init__(self, stage: str, timeout: float) -> None:
        self.stage = stage
        self.timeout = timeout
        super().__init__(f"{stage} did not complete within {timeout:g} seconds")


class LifecycleFailure(RuntimeError):
    def __init__(self, code: str, detail: str, recommended_action: str) -> None:
        self.code = code
        self.recommended_action = recommended_action
        super().__init__(detail)


class ServiceMutation:
    """A process-owned, inspectable lifecycle mutation with a persisted stage record."""

    def __init__(
        self,
        paths: ServicePaths,
        operation_type: str,
        *,
        app_build: str = "Development",
        app_instance: str | None = None,
        requesting_app_pid: int | None = None,
        target_service_generation: str | None = None,
        stage_timeouts: dict[str, float] | None = None,
    ) -> None:
        operation = operation_type.upper()
        if operation not in MUTATION_TYPES:
            raise ValueError(f"unsupported lifecycle operation: {operation_type}")
        self.paths = paths
        self.operation_type = operation
        self.app_build = app_build
        self.app_instance = app_instance or os.environ.get("FRAGARACH_APP_INSTANCE") or f"pid-{requesting_app_pid or os.getppid()}"
        self.requesting_app_pid = requesting_app_pid or os.getppid()
        self.target_service_generation = target_service_generation
        self.stage_timeouts = dict(STAGE_TIMEOUTS)
        self.stage_timeouts.update(stage_timeouts or {})
        self.handle: Any = None
        self.document: dict[str, Any] = {}
        self.record: dict[str, Any] = {}

    def begin(self) -> dict[str, Any]:
        self.paths.prepare()
        handle = self.paths.mutation_lock.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            handle.close()
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                active = _mutation_document(self.paths).get("active_mutation")
                raise MutationActiveError(active if isinstance(active, dict) else {}) from error
            raise
        self.handle = handle
        self.document = _mutation_document(self.paths)
        reconciled = _reconcile_mutation_locked(
            self.paths, self.document, stage_timeouts=self.stage_timeouts
        )
        active = reconciled.get("active_mutation")
        if isinstance(active, dict):
            self.close()
            raise MutationActiveError(active)
        now = utc_now()
        self.record = {
            "operation_id": str(uuid.uuid4()),
            "operation_type": self.operation_type,
            "status": "REQUESTED",
            "requested_at": now,
            "started_at": now,
            "last_progress_at": now,
            "completed_at": None,
            "requesting_app_pid": self.requesting_app_pid,
            "requesting_app_build": self.app_build,
            "requesting_app_instance": self.app_instance,
            "helper_process_pid": os.getpid(),
            "target_service_generation": self.target_service_generation,
            "current_stage": "REQUESTED",
            "progress_message": f"{self.operation_type.title()} requested",
            "failure_code": None,
            "failure_detail": None,
            "cancellable": False,
            "stage_history": [{"stage": "REQUESTED", "at": now, "message": f"{self.operation_type.title()} requested"}],
        }
        self.document["active_mutation"] = self.record
        self.document["reconciliation_status"] = "ACTIVE_OPERATION_CONFIRMED"
        _save_mutation_document(self.paths, self.document)
        return self.record

    def stage(self, stage: str, message: str, *, waiting: bool = False, cancellable: bool | None = None) -> None:
        self._raise_if_cancelled()
        now = utc_now()
        self.record.update(
            status="WAITING" if waiting else "RUNNING",
            current_stage=stage,
            progress_message=message,
            last_progress_at=now,
            cancellable=(stage in CANCELLABLE_MUTATION_STAGES if cancellable is None else cancellable),
        )
        self.record.setdefault("stage_history", []).append({"stage": stage, "at": now, "message": message})
        self.document["active_mutation"] = self.record
        _save_mutation_document(self.paths, self.document)

    def wait_for(self, predicate: Callable[[], bool], stage: str, message: str) -> None:
        self.stage(stage, message, waiting=True)
        timeout = float(self.stage_timeouts.get(stage, 30.0))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._raise_if_cancelled()
            if predicate():
                return
            time.sleep(min(0.1, max(timeout / 20, 0.01)))
        raise MutationStageTimedOut(stage, timeout)

    def complete(self, detail: dict[str, Any] | None = None) -> dict[str, Any]:
        record = _terminalize_mutation(self.paths, self.document, self.record, "COMPLETED")
        self.close()
        return _mutation_acknowledgement(record, detail=detail)

    def fail(self, error: BaseException) -> dict[str, Any]:
        if isinstance(error, MutationCancelled):
            status, code = "CANCELLED", "MUTATION_CANCELLED"
        elif isinstance(error, MutationStageTimedOut):
            status, code = "TIMED_OUT", "MUTATION_STAGE_TIMEOUT"
        elif isinstance(error, LifecycleFailure):
            status, code = "FAILED", error.code
        else:
            status, code = "FAILED", f"{self.operation_type}_{type(error).__name__.upper()}"
        record = _terminalize_mutation(
            self.paths, self.document, self.record, status,
            failure_code=code, failure_detail=str(error),
            reconciliation_status="OPERATION_TIMED_OUT" if status == "TIMED_OUT" else "OPERATION_FAILED",
        )
        self.close()
        acknowledgement = _mutation_acknowledgement(record)
        if isinstance(error, LifecycleFailure):
            acknowledgement["recommended_action"] = error.recommended_action
        return acknowledgement

    def _raise_if_cancelled(self) -> None:
        request = _read_json(self.paths.mutation_cancel, {})
        if not isinstance(request, dict) or request.get("operation_id") != self.record.get("operation_id"):
            return
        if not self.record.get("cancellable"):
            return
        raise MutationCancelled("The lifecycle operation was cancelled at a safe stage.")

    def close(self) -> None:
        if self.handle is None:
            return
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.handle = None


def _mutation_acknowledgement(record: dict[str, Any], *, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    status = str(record.get("status"))
    action = {
        "COMPLETED": "REFRESH_STATUS",
        "FAILED": "REPAIR_SERVICE",
        "TIMED_OUT": "FORCE_RECONCILE",
        "CANCELLED": "RETRY_OPERATION",
        "ABANDONED": "FORCE_RECONCILE",
    }.get(status, "VIEW_OPERATION")
    return {
        "contract": COMMAND_CONTRACT,
        "operation_id": record.get("operation_id"),
        "operation_status": status,
        "operation_stage": record.get("current_stage"),
        "retryable": status in {"FAILED", "TIMED_OUT", "CANCELLED", "ABANDONED"},
        "recommended_action": action,
        "failure_code": record.get("failure_code"),
        "failure_detail": record.get("failure_detail"),
        "detail": detail or {},
    }


def cancel_service_mutation(paths: ServicePaths, operation_id: str | None = None) -> dict[str, Any]:
    document = _mutation_document(paths)
    record = document.get("active_mutation")
    if not isinstance(record, dict):
        return {"outcome": "NO_ACTIVE_OPERATION", "cancelled": False}
    if operation_id and record.get("operation_id") != operation_id:
        return {"outcome": "OPERATION_NOT_FOUND", "cancelled": False}
    if not record.get("cancellable"):
        return {
            "outcome": "CANCELLATION_DEFERRED",
            "cancelled": False,
            "operation_id": record.get("operation_id"),
            "message": "Cancellation will be available after the current protected stage completes.",
        }
    _atomic_json(paths.mutation_cancel, {
        "operation_id": record.get("operation_id"),
        "requested_at": utc_now(),
        "requesting_process_id": os.getpid(),
    })
    return {"outcome": "CANCELLATION_REQUESTED", "cancelled": True, "operation_id": record.get("operation_id")}


def compatibility(app_build: str | None, service_build: str = SERVICE_BUILD) -> str:
    if not app_build or app_build == "Development" or app_build == service_build:
        return "Compatible"
    try:
        app_major = int(app_build.split(".", 1)[0])
        service_major = int(service_build.split(".", 1)[0])
    except ValueError:
        return "Compatible"
    if app_major > service_major:
        return "Service Update Required"
    if app_major < service_major:
        return "App Update Required"
    return "Service Update Available" if app_build > service_build else "Compatible"


def _recommended_service_actions(status: dict[str, Any], record: dict[str, Any] | None) -> list[str]:
    if record and record.get("status") in ACTIVE_MUTATION_STATUSES:
        actions = ["VIEW_DETAILS", "OPEN_DIAGNOSTICS"]
        if record.get("cancellable"):
            actions.insert(1, "CANCEL_OPERATION")
        return actions
    if record and record.get("status") in {"FAILED", "TIMED_OUT", "ABANDONED"}:
        operation = str(record.get("operation_type", "START"))
        retry = f"RETRY_{operation}" if operation in MUTATION_TYPES else "RETRY_OPERATION"
        return [retry, "REPAIR_SERVICE", "FORCE_RECONCILE", "OPEN_DIAGNOSTICS"]
    if status.get("live"):
        return ["OPEN_DIAGNOSTICS"]
    if status.get("acquisition_owner_active"):
        return ["RETRY_CONNECTION", "REPAIR_MONITOR", "OPEN_DIAGNOSTICS"]
    if not status.get("installed"):
        return ["INSTALL_SERVICE", "OPEN_DIAGNOSTICS"]
    return ["RETRY_CONNECTION", "START_SERVICE", "REPAIR_SERVICE", "OPEN_DIAGNOSTICS"]


def _extend_status_with_mutation(paths: ServicePaths, status: dict[str, Any]) -> dict[str, Any]:
    reconciliation = reconcile_service_mutation(paths)
    document = _mutation_document(paths)
    active = document.get("active_mutation")
    last = document.get("last_operation")
    visible = active if isinstance(active, dict) else last if isinstance(last, dict) else None
    owner_active = ownership_is_active(paths)
    status.update(
        active_mutation=active if isinstance(active, dict) else None,
        last_mutation=last if isinstance(last, dict) else None,
        mutation_status=visible.get("status") if visible else None,
        mutation_stage=visible.get("current_stage") if visible else None,
        mutation_started_at=visible.get("started_at") if visible else None,
        mutation_last_progress_at=visible.get("last_progress_at") if visible else None,
        mutation_cancellable=bool(visible and visible.get("cancellable")),
        mutation_failure=(
            {"code": visible.get("failure_code"), "detail": visible.get("failure_detail")}
            if visible and visible.get("failure_code") else None
        ),
        reconciliation_status=reconciliation.get("outcome") or document.get("reconciliation_status"),
        acquisition_owner_active=owner_active,
    )
    if not status.get("live") and owner_active:
        status["reconciliation_status"] = "ACQUISITION_OWNER_STILL_ACTIVE"
    elif not status.get("live") and paths.socket.exists():
        status["reconciliation_status"] = "SERVICE_STATE_INCONSISTENT"
    status["recommended_actions"] = _recommended_service_actions(status, visible)
    return status


def enrich_monitor(
    snapshot: dict[str, Any],
    paths: ServicePaths,
    *,
    instance: str,
    generation: str,
    started_at: str,
    service_state: str = "RUNNING",
    restart_count: int = 0,
) -> dict[str, Any]:
    now = utc_now()
    result = dict(snapshot)
    result.update(
        contract=MONITOR_CONTRACT,
        monitor_contract_version=3,
        command_contract_version=1,
        journal_format_version=JOURNAL_FORMAT_VERSION,
        minimum_compatible_build=MINIMUM_COMPATIBLE_BUILD,
        service_state=service_state,
        service_build=SERVICE_BUILD,
        running_build=SERVICE_BUILD,
        service_instance=instance,
        service_generation=generation,
        service_start_time=started_at,
        heartbeat_time=now,
        last_successful_monitor_update=now,
        authority_database_identity=authority_database_identity(paths.database),
        restart_count=restart_count,
        installed=paths.launch_agent.exists() and paths.metadata.exists(),
        service_location=str(paths.support),
        authority_database=str(paths.database),
        operational_journal=str(paths.journal),
        automatic_login_start=_automatic_login_start(paths),
        credential_source="macOS Keychain / approved credential chain",
        live=True,
    )
    # Keep restart-history.json intact, but never present an old process
    # failure as an error of this healthy service instance.
    result.pop("last_exit_reason", None)
    result["operational_health"] = scheduler_operational_health(
        result, process_alive=True, heartbeat_time=now,
        monitor_state="LISTENING",
    )
    return result


def scheduler_operational_health(
    snapshot: dict[str, Any], *, process_alive: bool,
    heartbeat_time: object, monitor_state: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One service-owned health projection; monitor transport is independent."""

    observed = now or datetime.now(UTC)
    heartbeat = _parse_timestamp(heartbeat_time)
    heartbeat_age = (
        max(0.0, (observed - heartbeat).total_seconds()) if heartbeat else None
    )
    progress = snapshot.get("scheduler_progress") or {}
    actionable = int(progress.get("actionable_queue_depth", 0) or 0)
    active = int(progress.get("active_workers", 0) or 0)
    progress_time = _parse_timestamp(progress.get("last_meaningful_progress"))
    progress_age = (
        max(0.0, (observed - progress_time).total_seconds()) if progress_time else None
    )
    progress_window = float(progress.get("permitted_progress_window_seconds", 45) or 45)
    stalled = bool(
        (actionable or active)
        and (progress_age is None or progress_age > progress_window)
    )
    if not process_alive:
        overall = "UNAVAILABLE"
    elif heartbeat_age is None or heartbeat_age > 6:
        overall = "DEGRADED"
    elif stalled:
        overall = "STALLED"
    elif not actionable and not active:
        overall = "IDLE"
    else:
        overall = "HEALTHY"

    def stage(last_key: str, *, active_stage: str | None = None) -> dict[str, Any]:
        current = str(progress.get("current_stage") or "")
        if not process_alive:
            state = "UNAVAILABLE"
        elif overall == "STALLED" and active_stage and current == active_stage:
            state = "STALLED"
        elif progress.get(last_key):
            state = "HEALTHY"
        else:
            state = "IDLE"
        return {"state": state, "last_progress": progress.get(last_key)}

    return {
        "contract": "fragarach_ii.scheduler_operational_health.v1",
        "overall_operational_health": overall,
        "process": {"state": "ALIVE" if process_alive else "NOT_RUNNING"},
        "heartbeat": {
            "state": "CURRENT" if heartbeat_age is not None and heartbeat_age <= 6 else "LATE",
            "at": heartbeat.isoformat() if heartbeat else None,
            "age_seconds": heartbeat_age,
        },
        "monitor_transport": {"state": monitor_state},
        "selection_loop": stage("last_selection", active_stage="SELECTED"),
        "worker_pool": {
            "state": "UNAVAILABLE" if not process_alive else "STALLED" if overall == "STALLED" and actionable and not active else "HEALTHY" if active else "IDLE",
            "active_workers": active,
            "available_workers": int(progress.get("available_workers", 0) or 0),
        },
        "provider_dispatch": stage("last_provider_request", active_stage="REQUEST_STARTED"),
        "provider_response": stage("last_provider_response", active_stage="REQUEST_STARTED"),
        "evidence_admission": stage("last_evidence_admission", active_stage="RAW_EVIDENCE_STORED"),
        "publication": stage("last_canonical_publication", active_stage="PUBLICATION_COMPLETED"),
        "queue_progress": stage("last_queue_progress"),
        "actionable_queue_depth": actionable,
        "blocked_queue_depth": int(progress.get("blocked_queue_depth", 0) or 0),
        "total_queue_depth": int(progress.get("total_queue_depth", 0) or 0),
        "oldest_actionable_age_seconds": progress.get("oldest_actionable_age_seconds"),
        "last_meaningful_progress": progress.get("last_meaningful_progress"),
        "last_meaningful_progress_age_seconds": progress_age,
        "permitted_progress_window_seconds": progress_window,
        "current_trace_id": progress.get("current_trace_id"),
        "current_lane": progress.get("current_lane"),
        "current_stage": progress.get("current_stage"),
        "current_stop_reason": progress.get("current_stop_reason"),
    }


def _compact_status(value: dict[str, Any]) -> dict[str, Any]:
    """Persist liveness without rewriting the full monitor projection."""

    compact = {key: value[key] for key in COMPACT_STATUS_KEYS if key in value}
    execution = value.get("execution")
    if isinstance(execution, dict):
        compact["execution"] = {
            key: execution[key] for key in COMPACT_EXECUTION_KEYS if key in execution
        }
    return compact


class SchedulerCommandServer:
    def __init__(self, paths: ServicePaths, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.paths = paths
        self.handler = handler
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self._socket: socket.socket | None = None
        self._clients_lock = threading.Lock()
        self._clients: set[socket.socket] = set()
        self._workers: set[threading.Thread] = set()

    def start(self) -> None:
        self.paths.prepare()
        self.paths.socket.unlink(missing_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.paths.socket))
        os.chmod(self.paths.socket, 0o600)
        server.listen(8)
        server.settimeout(0.5)
        self._socket = server
        self.thread = threading.Thread(target=self._serve, name="scheduler-command-server", daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        assert self._socket is not None
        while not self.stop_event.is_set():
            try:
                connection, _ = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                if self.stop_event.is_set():
                    break
                # A transient accept failure is a monitor fault, not authority
                # to terminate the listener or the Scheduler process.
                time.sleep(0.05)
                continue
            connection.settimeout(_SOCKET_CLIENT_TIMEOUT)
            worker = threading.Thread(
                target=self._serve_client,
                args=(connection,),
                name="scheduler-command-client",
                daemon=True,
            )
            with self._clients_lock:
                self._clients.add(connection)
                self._workers.add(worker)
            worker.start()

    def _serve_client(self, connection: socket.socket) -> None:
        try:
            with connection:
                try:
                    data = b""
                    while b"\n" not in data and len(data) <= _SOCKET_LIMIT:
                        chunk = connection.recv(65536)
                        if not chunk:
                            break
                        data += chunk
                    if not data:
                        return
                    if len(data) > _SOCKET_LIMIT:
                        raise ValueError("command exceeds size limit")
                    request = json.loads(data.split(b"\n", 1)[0])
                    response = self.handler(request)
                except socket.timeout:
                    # A client that connects without completing a bounded
                    # request must not monopolize the monitor accept loop.
                    return
                except BaseException as error:
                    response = {
                        "contract": COMMAND_CONTRACT,
                        "result": "failed",
                        "reason": str(error),
                    }
                try:
                    encoded = json.dumps(
                        response, sort_keys=True, separators=(",", ":")
                    ).encode() + b"\n"
                    connection.sendall(encoded)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    # Bounded monitor callers may close while a large snapshot
                    # is encoded or written. Their disconnect is client-local.
                    return
        finally:
            current = threading.current_thread()
            with self._clients_lock:
                self._clients.discard(connection)
                self._workers.discard(current)

    def stop(self) -> None:
        self.stop_event.set()
        if self._socket is not None:
            self._socket.close()
        with self._clients_lock:
            clients = list(self._clients)
            workers = list(self._workers)
        for connection in clients:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        if self.thread is not None:
            self.thread.join(timeout=2)
        for worker in workers:
            worker.join(timeout=2)
        self.paths.socket.unlink(missing_ok=True)


def send_service_request(paths: ServicePaths, request: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(str(paths.socket))
        client.sendall(json.dumps(request, sort_keys=True, separators=(",", ":")).encode() + b"\n")
        data = b""
        while b"\n" not in data and len(data) <= _SOCKET_LIMIT:
            chunk = client.recv(65536)
            if not chunk:
                break
            data += chunk
        if len(data) > _SOCKET_LIMIT:
            raise ValueError("service response exceeds size limit")
        if not data or b"\n" not in data:
            raise ValueError("incomplete service response frame")
        value = json.loads(data.split(b"\n", 1)[0])
        if not isinstance(value, dict):
            raise ValueError("service response is not an object")
        return value
    finally:
        client.close()


def service_status(paths: ServicePaths, *, app_build: str | None = None) -> dict[str, Any]:
    try:
        response = send_service_request(paths, {"contract": STATUS_CONTRACT, "request": "status", "app_build": app_build})
        response["compatibility"] = compatibility(app_build, str(response.get("service_build", SERVICE_BUILD)))
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(str(response["heartbeat_time"]))).total_seconds()
        except (KeyError, TypeError, ValueError):
            age = 999.0
        response["liveness"] = "Healthy" if age <= 6 else "Heartbeat Late"
        if age > 6 and response.get("service_state") == "RUNNING":
            response["service_state"] = "DEGRADED"
        response["operational_health"] = scheduler_operational_health(
            response, process_alive=True,
            heartbeat_time=response.get("heartbeat_time"),
            monitor_state="CONNECTED",
        )
        return _extend_status_with_mutation(paths, response)
    except (OSError, ValueError, TimeoutError):
        cached = _read_json(paths.status, {})
        metadata = _read_json(paths.metadata, {})
        installed = paths.launch_agent.exists() and paths.metadata.exists()
        state = "STOPPED" if installed else "NOT_INSTALLED"
        if cached and installed:
            cached_state = str(cached.get("service_state", ""))
            state = cached_state if cached_state in {"STOPPED", "CRASH_LOOP_PROTECTED", "REPAIR_REQUIRED"} else "UNREACHABLE"
        cached.update(
            contract=STATUS_CONTRACT,
            service_state=state,
            live=False,
            installed=installed,
            service_build=metadata.get("installed_build") or cached.get("service_build"),
            last_successful_monitor_update=cached.get("heartbeat_time"),
            compatibility=compatibility(app_build, str(cached.get("service_build", SERVICE_BUILD))),
            service_location=str(paths.support),
            authority_database=str(paths.database),
            operational_journal=str(paths.journal),
            credential_source="macOS Keychain / approved credential chain",
            automatic_login_start=_automatic_login_start(paths),
            liveness="Unreachable",
        )
        cached["operational_health"] = scheduler_operational_health(
            cached, process_alive=ownership_is_active(paths),
            heartbeat_time=cached.get("heartbeat_time"),
            monitor_state="MONITOR_DISCONNECTED",
        )
        return _extend_status_with_mutation(paths, cached)


def make_command(
    command_type: str,
    *,
    app_build: str = "Development",
    target_generation: str | None = None,
    scope: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    command_identifier: str | None = None,
) -> dict[str, Any]:
    return {
        "contract": COMMAND_CONTRACT,
        "command_identifier": command_identifier or str(uuid.uuid4()),
        "command_type": command_type,
        "issued_time": utc_now(),
        "app_build": app_build,
        "target_service_generation": target_generation,
        "scope": scope or {},
        "payload": payload or {},
    }


class PersistentSchedulerRuntime:
    def __init__(self, paths: ServicePaths, *, credential: str | None, monitor_only: bool = False, credential_provider: Callable[[], str | None] | None = None) -> None:
        from .scheduler_service import SchedulerService

        self.paths = paths
        self.instance = str(uuid.uuid4())
        self.generation = str(uuid.uuid4())
        self.started_at = utc_now()
        self.credential = credential
        self.credential_provider = credential_provider
        self.scheduler = SchedulerService(paths.database, credential=credential, journal_path=paths.journal, credential_provider=credential_provider)
        self.monitor_only = monitor_only
        self.ownership = AcquisitionOwnership(paths, instance=self.instance, generation=self.generation)
        self.server = SchedulerCommandServer(paths, self._handle_request)
        self._snapshot: dict[str, Any] = {}
        self._snapshot_lock = threading.Lock()
        self._command_lock = threading.Lock()
        self._heartbeat_stop = threading.Event()
        self._monitor_repair_requested = threading.Event()
        self._monitor_lock = threading.Lock()
        self._monitor_generation = str(uuid.uuid4())
        self._heartbeat_thread: threading.Thread | None = None
        self._admission_failure: str | None = None
        self._state = "STARTING"

    def run(self) -> None:
        from .scheduler_service import SchedulerJournal

        self.paths.prepare()
        self.ownership.acquire()
        self._state = "RUNNING"
        # Accept control before doing any estate projection.  A full monitor
        # snapshot can be slow on a large estate and is never allowed to delay
        # ready-queue dispatch or the Run Queue Now wake path.
        self._refresh_credential()
        # Create the tiny durable control journal eagerly so commands and
        # monitor-only service health have a stable authority document without
        # paying for an estate snapshot.
        journal = SchedulerJournal(self.paths.database, self.paths.journal)
        if not self.paths.journal.exists() or journal.migration_pending:
            journal.save()
        self.server.start()
        # Estate admission repairs only a pre-register legacy estate.  Once
        # the durable register is seeded, new registrations commission their
        # lanes atomically during onboarding, so replaying this migration on
        # every service restart would repeatedly rebuild capability projections
        # across the entire historical ingest ledger.
        from .lane_update_register import LaneUpdateRegister
        if not LaneUpdateRegister(self.paths.database).is_seeded():
            admission_thread = threading.Thread(
                target=self._run_estate_admission,
                name="scheduler-estate-admission", daemon=True,
            )
            admission_thread.start()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name="scheduler-heartbeat", daemon=True)
        self._heartbeat_thread.start()
        try:
            runner = self.scheduler.run_monitor_only if self.monitor_only else self.scheduler.run_forever
            runner(self._publish)
        finally:
            self._state = "STOPPING"
            self._write_current_status()
            self.server.stop()
            self._heartbeat_stop.set()
            if self._heartbeat_thread:
                self._heartbeat_thread.join(timeout=3)
            self.ownership.release()
            self._state = "STOPPED"
            self._write_current_status(live=False)

    def _run_estate_admission(self) -> None:
        """Run non-critical estate admission without taking down dispatch."""
        from .onboarding import activate_existing_estate_admission

        try:
            activate_existing_estate_admission(self.paths.database)
        except Exception as error:
            # A concurrent lifecycle teardown can remove a temporary authority
            # database.  Preserve the service and expose the bounded reason in
            # its status rather than leaking an unhandled worker exception.
            self._admission_failure = str(error)

    def _publish(self, snapshot: dict[str, Any]) -> None:
        value = enrich_monitor(
            snapshot, self.paths, instance=self.instance, generation=self.generation,
            started_at=self.started_at, service_state=self._state,
            restart_count=len(_read_json(self.paths.restart_history, [])),
        )
        with self._snapshot_lock:
            self._snapshot = value
        _atomic_json(self.paths.status, value)

    def _current_status(self, *, live: bool = True) -> dict[str, Any]:
        with self._snapshot_lock:
            value = dict(self._snapshot)
        value.update(
            contract=MONITOR_CONTRACT,
            monitor_contract_version=value.get("monitor_contract_version", 3),
            command_contract_version=value.get("command_contract_version", 1),
            journal_format_version=value.get("journal_format_version", JOURNAL_FORMAT_VERSION),
            minimum_compatible_build=value.get("minimum_compatible_build", MINIMUM_COMPATIBLE_BUILD),
            service_state=self._state,
            service_build=SERVICE_BUILD,
            service_instance=self.instance,
            service_generation=self.generation,
            service_start_time=self.started_at,
            heartbeat_time=utc_now(),
            heartbeat_cycle_id=(value.get("execution") or {}).get("cycle_id"),
            heartbeat_cycle_state=(
                "ACTIVE" if value.get("active_activity")
                else "COMPLETED" if (value.get("execution") or {}).get("completed_at")
                else "STARTING"
            ),
            installed=self.paths.launch_agent.exists() and self.paths.metadata.exists(),
            service_location=str(self.paths.support),
            authority_database=str(self.paths.database),
            operational_journal=str(self.paths.journal),
            automatic_login_start=_automatic_login_start(self.paths),
            credential_source="macOS Keychain / approved credential chain",
            live=live,
        )
        if self._admission_failure:
            value["estate_admission_warning"] = self._admission_failure
        value["operational_health"] = scheduler_operational_health(
            value, process_alive=live,
            heartbeat_time=value.get("heartbeat_time"),
            monitor_state="LISTENING" if live else "MONITOR_DISCONNECTED",
        )
        return value

    def _write_current_status(self, *, live: bool = True, compact: bool = False) -> dict[str, Any]:
        value = self._current_status(live=live)
        _atomic_json(self.paths.status, _compact_status(value) if compact else value)
        return value

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(2.0):
            if self._monitor_repair_requested.is_set():
                self._rebuild_monitor_transport()
            value = self._write_current_status(compact=True)
            self.ownership.heartbeat(
                self._state,
                next_wake=value.get("next_run"),
                active_task_count=1 if value.get("active_activity") else 0,
                journal_generation=value.get("authority_revision"),
            )

    def request_monitor_repair(self) -> None:
        """Request only a listener rebuild; scheduler ownership is untouched."""
        self._monitor_repair_requested.set()

    def _rebuild_monitor_transport(self) -> None:
        with self._monitor_lock:
            self._monitor_repair_requested.clear()
            prior = self.server
            prior.stop()
            self.server = SchedulerCommandServer(self.paths, self._handle_request)
            self.server.start()
            self._monitor_generation = str(uuid.uuid4())

    def _handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("contract") == STATUS_CONTRACT and request.get("request") == "ping":
            return {
                "contract": STATUS_CONTRACT,
                "request": "ping",
                "result": "ok",
                "process_id": os.getpid(),
                "service_generation": self.generation,
                "monitor_generation": self._monitor_generation,
                "heartbeat_time": utc_now(),
            }
        if request.get("contract") == STATUS_CONTRACT and request.get("request") == "status":
            value = self._current_status()
            value["contract"] = STATUS_CONTRACT
            value["compatibility"] = compatibility(request.get("app_build"))
            return value
        if request.get("contract") != COMMAND_CONTRACT:
            return {"contract": COMMAND_CONTRACT, "result": "incompatible", "reason": "unsupported contract"}
        required = {"command_identifier", "command_type", "issued_time", "app_build", "target_service_generation", "scope", "payload"}
        if not required.issubset(request):
            return {"contract": COMMAND_CONTRACT, "result": "rejected", "reason": "malformed command"}
        target = request.get("target_service_generation")
        if target and target != self.generation:
            return {"contract": COMMAND_CONTRACT, "result": "rejected", "reason": "stale service generation"}
        if compatibility(str(request.get("app_build"))) in {"App Update Required", "Incompatible"}:
            return {"contract": COMMAND_CONTRACT, "result": "incompatible", "reason": "app/service build mismatch"}
        identifier = str(request["command_identifier"])
        with self._command_lock:
            records = _read_json(self.paths.commands, {})
            if identifier in records:
                prior = dict(records[identifier])
                prior["result"] = "already applied"
                return prior
            semantic_source = json.dumps(
                [request["command_type"], request.get("scope") or {}, request.get("payload") or {}],
                sort_keys=True, separators=(",", ":"),
            )
            fingerprint = hashlib.sha256(semantic_source.encode()).hexdigest()
            now = datetime.now(UTC)
            for prior_value in records.values():
                if not isinstance(prior_value, dict) or prior_value.get("semantic_fingerprint") != fingerprint:
                    continue
                try:
                    age = (now - datetime.fromisoformat(str(prior_value["applied_time"]))).total_seconds()
                except (KeyError, TypeError, ValueError):
                    continue
                if age <= 5 and prior_value.get("result") == "accepted":
                    prior = dict(prior_value)
                    prior.update(command_identifier=identifier, result="already applied")
                    records[identifier] = prior
                    _atomic_json(self.paths.commands, records)
                    return prior
            try:
                detail = self._apply_command(str(request["command_type"]), request.get("scope") or {}, request.get("payload") or {})
                acknowledgement = {
                    "contract": COMMAND_CONTRACT,
                    "command_identifier": identifier,
                    "result": "accepted",
                    "applied_time": utc_now(),
                    "service_generation": self.generation,
                    "semantic_fingerprint": fingerprint,
                    "detail": detail,
                }
            except (ValueError, RuntimeError) as error:
                acknowledgement = {
                    "contract": COMMAND_CONTRACT,
                    "command_identifier": identifier,
                    "result": "rejected",
                    "applied_time": utc_now(),
                    "service_generation": self.generation,
                    "semantic_fingerprint": fingerprint,
                    "reason": str(error),
                }
            records[identifier] = acknowledgement
            if len(records) > 500:
                records = dict(list(records.items())[-500:])
            _atomic_json(self.paths.commands, records)
        self.scheduler.wake()
        return acknowledgement

    def _apply_command(self, command: str, scope: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        from .scheduler_service import (
            pause_acquisition,
            request_retry,
            request_run_queue,
            resume_acquisition,
            run_operator_fetch,
            run_required_set_fetch,
            update_manual_request,
            update_queue_bandwidth,
            update_scheduler_policy,
            update_freshness_override,
        )

        self._refresh_credential()
        common = {"journal_path": self.paths.journal}
        if command == "PAUSE":
            return pause_acquisition(
                self.paths.database,
                scope_type=str(scope.get("scope_type", "ALL")),
                scope_identifier=scope.get("scope_identifier"),
                reason=str(payload.get("reason", "OPERATOR_MAINTENANCE")),
                temporary=bool(payload.get("temporary", False)),
                related_ingestion_session=payload.get("ingestion_session"),
                **common,
            )
        if command == "RESUME":
            return resume_acquisition(
                self.paths.database,
                pause_identifier=payload.get("pause_identifier"),
                scope_type=scope.get("scope_type"),
                scope_identifier=scope.get("scope_identifier"),
                related_ingestion_session=payload.get("ingestion_session"),
                **common,
            )
        if command == "RETRY_NOW":
            return request_retry(self.paths.database, lane_id=payload.get("lane_id"), request_id=payload.get("request_id"), credential=self.credential, **common)
        if command == "RUN_QUEUE_NOW":
            return request_run_queue(self.paths.database, credential=self.credential, **common)
        if command == "QUEUE_BANDWIDTH":
            return update_queue_bandwidth(self.paths.database, int(payload["percentage"]), **common)
        if command == "SCHEDULER_POLICY":
            return update_scheduler_policy(self.paths.database, str(payload["policy"]), **common)
        if command == "M5_FRESHNESS":
            return update_freshness_override(
                self.paths.database, timeframe="M5",
                publication_delay_seconds=int(payload["publication_delay_seconds"]),
                critical_after_closed_boundaries=int(payload["critical_after_closed_boundaries"]),
                **common,
            )
        if command == "MANUAL_REQUEST":
            return update_manual_request(self.paths.database, request_id=str(payload["request_id"]), action=str(payload["action"]), **common)
        if command == "OPERATOR_FETCH":
            return run_operator_fetch(
                self.paths.database,
                symbol=str(payload["symbol"]),
                timeframe=str(payload["timeframe"]),
                credential=self.credential,
                requested_mode=str(payload.get("requested_mode", "update")),
                requested_start=payload.get("requested_start"),
                requested_end=payload.get("requested_end"),
                reviewed_historical_range=bool(payload.get("reviewed_historical_range", False)),
                operator_reason=str(payload.get("operator_reason", "OPERATOR_FETCH")),
                merge_mode=str(payload.get("merge_mode", "preserve")),
                defer_dispatch=True,
                **common,
            )
        if command == "OPERATOR_FETCH_REQUIRED_SET":
            return run_required_set_fetch(
                self.paths.database,
                symbol=str(payload["symbol"]),
                credential=self.credential,
                merge_mode=str(payload.get("merge_mode", "preserve")),
                operator_reason=str(payload.get("operator_reason", "REQUIRED_TIMEFRAME_SET")),
                **common,
            )
        if command == "CREDENTIAL_VALIDATE":
            from .credentials import CredentialAuthority
            return CredentialAuthority().validate(str(payload.get("provider", "TWELVE_DATA")))
        if command in {"PROVIDER_FACT_REFRESH", "CREDENTIAL_REFRESH", "AUTHORITY_RELOAD"}:
            return {"outcome": f"{command}_REQUESTED"}
        if command == "STOP_SERVICE":
            self._state = "STOPPING"
            self.scheduler.stop()
            return {"outcome": "GRACEFUL_STOP_REQUESTED"}
        raise ValueError(f"unsupported service command: {command}")

    def _refresh_credential(self) -> str | None:
        if self.credential_provider is not None:
            self.credential = self.credential_provider()
            self.scheduler.credential = self.credential
        return self.credential


def launch_agent_definition(
    paths: ServicePaths,
    *,
    python: str,
    repository: str | Path,
    monitor_only: bool = False,
) -> dict[str, Any]:
    arguments = [
        str(Path(python).expanduser().resolve()),
        "-m", "fragarach_ii.commands.scheduler",
        "--database", str(paths.database),
        "--journal", str(paths.journal),
        "--support-dir", str(paths.support),
        "--repository", str(Path(repository).expanduser().resolve()),
        "--mode", "service-run",
    ]
    if monitor_only:
        arguments.append("--monitor-only")
    return {
        "Label": SERVICE_LABEL,
        "ProgramArguments": arguments,
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 30,
        "ProcessType": "Background",
        "WorkingDirectory": str(Path(repository).expanduser().resolve()),
        "EnvironmentVariables": {"PYTHONPATH": str(Path(repository).expanduser().resolve() / "src")},
        "StandardOutPath": str(paths.stdout_log),
        "StandardErrorPath": str(paths.stderr_log),
    }


def install_service(
    paths: ServicePaths,
    *,
    python: str,
    repository: str | Path,
    enable: bool = True,
    launchctl: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    paths.prepare()
    paths.launch_agent.parent.mkdir(parents=True, exist_ok=True)
    definition = launch_agent_definition(paths, python=python, repository=repository)
    payload = plistlib.dumps(definition, fmt=plistlib.FMT_XML, sort_keys=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{paths.launch_agent.name}.", dir=paths.launch_agent.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, paths.launch_agent)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    metadata = {
        "contract": "fragarach_ii.scheduler_service_installation.v1",
        "installed_at": utc_now(),
        "installed_build": SERVICE_BUILD,
        "service_location": str(paths.support),
        "authority_database": str(paths.database),
        "operational_journal": str(paths.journal),
        "automatic_login_start": True,
        "credential_source": "macOS Keychain / approved credential chain",
        "launch_agent": str(paths.launch_agent),
    }
    _atomic_json(paths.metadata, metadata)
    if enable:
        domain = f"gui/{os.getuid()}"
        launchctl(["launchctl", "bootout", domain, str(paths.launch_agent)], check=False, capture_output=True)
        launchctl(["launchctl", "bootstrap", domain, str(paths.launch_agent)], check=True, capture_output=True)
    return metadata


def service_action(
    paths: ServicePaths,
    action: str,
    *,
    launchctl: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    domain = f"gui/{os.getuid()}"
    service = f"{domain}/{SERVICE_LABEL}"
    if action == "start":
        launchctl(["launchctl", "kickstart", "-k", service], check=True, capture_output=True)
    elif action == "restart":
        try:
            send_service_request(paths, make_command("STOP_SERVICE"), timeout=10)
        except OSError:
            pass
        deadline = time.monotonic() + 30
        while ownership_is_active(paths) and time.monotonic() < deadline:
            time.sleep(0.1)
        launchctl(["launchctl", "kickstart", "-k", service], check=True, capture_output=True)
    elif action == "stop":
        try:
            acknowledgement = send_service_request(paths, make_command("STOP_SERVICE"), timeout=10)
        except OSError:
            acknowledgement = {"result": "already applied"}
        deadline = time.monotonic() + 30
        while ownership_is_active(paths) and time.monotonic() < deadline:
            time.sleep(0.1)
        if ownership_is_active(paths):
            launchctl(["launchctl", "kill", "SIGTERM", service], check=False, capture_output=True)
        return acknowledgement
    elif action == "disable":
        launchctl(["launchctl", "disable", service], check=True, capture_output=True)
        launchctl(["launchctl", "bootout", domain, str(paths.launch_agent)], check=False, capture_output=True)
    elif action == "enable":
        launchctl(["launchctl", "enable", service], check=True, capture_output=True)
        launchctl(["launchctl", "bootstrap", domain, str(paths.launch_agent)], check=False, capture_output=True)
    elif action == "uninstall":
        launchctl(["launchctl", "bootout", domain, str(paths.launch_agent)], check=False, capture_output=True)
        paths.launch_agent.unlink(missing_ok=True)
        paths.metadata.unlink(missing_ok=True)
    else:
        raise ValueError(f"unsupported service action: {action}")
    return {"outcome": f"SERVICE_{action.upper()}_REQUESTED", "service_state": service_status(paths).get("service_state")}


def repair_service(paths: ServicePaths) -> dict[str, Any]:
    try:
        definition = plistlib.loads(paths.launch_agent.read_bytes())
    except (OSError, ValueError, TypeError):
        definition = {}
    arguments = definition.get("ProgramArguments", []) if isinstance(definition, dict) else []
    executable = Path(arguments[0]) if arguments else None
    executable_present = bool(executable and executable.is_file() and os.access(executable, os.X_OK))
    signature_valid = executable_present
    if signature_valid and sys.platform == "darwin":
        signature_valid = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict", str(executable)],
            check=False, capture_output=True,
        ).returncode == 0
    from .credentials import resolve_scheduler_credential
    _credential, credential_source = resolve_scheduler_credential()
    checks = []
    for name, ok, why in (
        ("LaunchAgent installed", paths.launch_agent.exists(), "LaunchAgent plist is missing"),
        ("LaunchAgent enabled", bool(definition.get("RunAtLoad")), "Automatic login start is disabled"),
        ("Service executable present", executable_present, "Configured service executable is missing or not executable"),
        ("Signature valid", signature_valid, "Configured service executable failed strict signature verification"),
        ("Authority path valid", paths.database.is_file(), "Authority database is unavailable"),
        ("Journal path writable", os.access(paths.journal.parent, os.W_OK), "Operational journal directory is not writable"),
        ("Credential access available", credential_source == "Available", "Credential Authority does not report an available provider credential"),
        ("Ownership lock valid", True, "Acquisition ownership is reported separately and never cleared by Repair"),
        ("Monitor channel available", paths.socket.exists(), "Live monitor channel is unavailable"),
        ("App/service compatibility", True, "App and service builds are incompatible"),
    ):
        # Acquisition ownership is an independent safety domain. A stale-looking
        # metadata file is reported, never removed by service-management repair.
        checks.append({
            "check": name,
            "passed": ok,
            "why": None if ok else why,
            "failure_code": None if ok else name.upper().replace(" ", "_"),
            "repair_performed": None,
            "remaining_operator_action": None if ok else (
                "Retry the monitor connection; do not clear acquisition ownership"
                if name == "Ownership lock valid" else "Reinstall or start the Scheduler Service"
            ),
        })
    return {"contract": "fragarach_ii.scheduler_service_repair.v1", "checks": checks, "repair_required": any(not item["passed"] for item in checks)}


def service_diagnostics(paths: ServicePaths, *, app_build: str = "Development") -> dict[str, Any]:
    """Return credential-free, operator-facing service recovery evidence."""
    try:
        definition = plistlib.loads(paths.launch_agent.read_bytes())
    except (OSError, ValueError, TypeError):
        definition = {}
    arguments = definition.get("ProgramArguments", []) if isinstance(definition, dict) else []
    executable = Path(str(arguments[0])) if arguments else None
    executable_present = bool(executable and executable.is_file() and os.access(executable, os.X_OK))
    integrity = executable_present
    if integrity and sys.platform == "darwin":
        integrity = subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict", str(executable)],
            check=False, capture_output=True,
        ).returncode == 0
    owner_active = ownership_is_active(paths)
    ownership = _read_json(paths.ownership, {})
    cached = _read_json(paths.status, {})
    heartbeat = _parse_timestamp(cached.get("heartbeat_time")) if isinstance(cached, dict) else None
    heartbeat_age = (datetime.now(UTC) - heartbeat).total_seconds() if heartbeat else None
    socket_present = paths.socket.exists()
    socket_permissions = None
    if socket_present:
        try:
            socket_permissions = oct(paths.socket.stat().st_mode & 0o777)
        except OSError:
            pass
    socket_reachable = False
    if socket_present:
        try:
            response = send_service_request(
                paths, {"contract": STATUS_CONTRACT, "request": "ping", "app_build": app_build},
                timeout=2.0,
            )
            socket_reachable = response.get("result") == "ok"
        except (OSError, ValueError, TimeoutError):
            pass
    from .credentials import resolve_scheduler_credential
    _credential, credential_source = resolve_scheduler_credential()
    document = _mutation_document(paths)
    active = document.get("active_mutation")

    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, state: Any, code: str, explanation: str, repair: str) -> None:
        checks.append({
            "check": name,
            "passed": passed,
            "state": state,
            "failure_code": None if passed else code,
            "explanation": None if passed else explanation,
            "recommended_repair": None if passed else repair,
        })

    installed = paths.launch_agent.exists() and paths.metadata.exists()
    add("LaunchAgent installed", installed, installed, "LAUNCH_AGENT_NOT_INSTALLED", "The per-user LaunchAgent files are incomplete.", "Install or Repair Service")
    add("LaunchAgent enabled", bool(definition.get("RunAtLoad")), bool(definition.get("RunAtLoad")), "LAUNCH_AGENT_DISABLED", "Automatic login start is disabled in the installed definition.", "Enable Service")
    add("LaunchAgent load state", owner_active or socket_reachable, "loaded" if owner_active else "not confirmed", "LAUNCH_AGENT_NOT_RUNNING", "No active Scheduler generation was found.", "Start Service")
    add("Service executable present", executable_present, str(executable) if executable else None, "SERVICE_EXECUTABLE_MISSING", "The configured runtime executable is unavailable.", "Repair Service")
    add("Service executable integrity", integrity, "valid" if integrity else "unverified", "SERVICE_EXECUTABLE_INTEGRITY", "Strict executable verification did not pass.", "Update or Repair Service")
    add("Service process state", owner_active, "alive" if owner_active else "stopped", "SERVICE_PROCESS_STOPPED", "No Scheduler owns acquisition for this authority.", "Start Service")
    add("Acquisition owner state", True, "active" if owner_active else "not active", "STALE_ACQUISITION_METADATA", "Acquisition ownership could not be reconciled.", "Open Diagnostics; acquisition ownership is never cleared by mutation repair")
    add("Socket path", socket_present, str(paths.socket), "SERVICE_SOCKET_MISSING", "The monitor socket does not exist.", "Retry Connection or Repair Monitor")
    add("Socket permissions", socket_permissions in {None, "0o600"} if not socket_present else socket_permissions == "0o600", socket_permissions, "SERVICE_SOCKET_PERMISSIONS", "The monitor socket is not user-only.", "Repair Monitor")
    add("Socket reachability", socket_reachable, socket_reachable, "SERVICE_SOCKET_UNREACHABLE", "The monitor endpoint did not answer a bounded status request.", "Retry Connection or Repair Monitor")
    add("Heartbeat state", heartbeat_age is not None and heartbeat_age <= 6, {"at": heartbeat.isoformat() if heartbeat else None, "age_seconds": heartbeat_age}, "SERVICE_HEARTBEAT_LATE", "No current service heartbeat is available.", "Retry Connection, then Repair Service")
    add("Journal writability", os.access(paths.journal.parent, os.W_OK), str(paths.journal), "JOURNAL_NOT_WRITABLE", "The operational journal directory is not writable.", "Repair directory permissions")
    add("Credential state", credential_source == "Available", credential_source, "CREDENTIAL_UNAVAILABLE", "Credential Authority does not report an available provider credential.", "Configure the credential through Credential Authority")
    running_build = str(cached.get("service_build", SERVICE_BUILD)) if isinstance(cached, dict) else SERVICE_BUILD
    compatible = compatibility(app_build, running_build)
    add("App/service compatibility", compatible == "Compatible", compatible, "APP_SERVICE_INCOMPATIBLE", "The app and service builds require reconciliation.", "Update Service")
    add("Active mutation", not isinstance(active, dict), active, "SERVICE_MUTATION_ACTIVE", "A lifecycle operation is still active.", "View operation details or cancel at a safe stage")

    return {
        "contract": "fragarach_ii.scheduler_service_diagnostics.v1",
        "generated_at": utc_now(),
        "authority_database_identity": authority_database_identity(paths.database),
        "service_generation": cached.get("service_generation") if isinstance(cached, dict) else None,
        "acquisition_owner_generation": ownership.get("ownership_generation") if isinstance(ownership, dict) else None,
        "active_mutation": active if isinstance(active, dict) else None,
        "mutation_age_seconds": _record_age(active) if isinstance(active, dict) else None,
        "checks": checks,
        "credentials_included": False,
    }


def repair_monitor_transport(paths: ServicePaths, *, timeout: float = 10.0) -> dict[str, Any]:
    """Rebuild only the socket listener in the existing Scheduler generation."""

    if not ownership_is_active(paths):
        raise RuntimeError("SCHEDULER_PROCESS_NOT_RUNNING")
    ownership = _read_json(paths.ownership, {})
    process_id = int(ownership.get("process_id", 0) or 0)
    generation = str(ownership.get("ownership_generation") or "")
    if process_id <= 0 or not generation:
        raise RuntimeError("SCHEDULER_OWNERSHIP_IDENTITY_UNAVAILABLE")
    if not hasattr(signal, "SIGUSR2"):
        raise RuntimeError("MONITOR_REPAIR_SIGNAL_UNAVAILABLE")
    os.kill(process_id, signal.SIGUSR2)
    deadline = time.monotonic() + timeout
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            response = send_service_request(
                paths, {"contract": STATUS_CONTRACT, "request": "ping"}, timeout=1.0,
            )
            if (
                response.get("result") == "ok"
                and int(response.get("process_id", 0) or 0) == process_id
                and str(response.get("service_generation") or "") == generation
            ):
                return {
                    "contract": "fragarach_ii.scheduler_monitor_repair.v1",
                    "outcome": "MONITOR_REPAIRED",
                    "process_id": process_id,
                    "service_generation": generation,
                    "monitor_generation": response.get("monitor_generation"),
                    "scheduler_restarted": False,
                    "ownership_changed": False,
                    "queue_changed": False,
                }
        except (OSError, ValueError, TimeoutError) as error:
            last_error = error
        time.sleep(0.1)
    raise RuntimeError(f"MONITOR_REPAIR_TIMED_OUT: {last_error or 'listener did not answer'}")


def manage_service_lifecycle(
    paths: ServicePaths,
    operation_type: str,
    *,
    python: str = sys.executable,
    repository: str | Path = ".",
    app_build: str = "Development",
    app_instance: str | None = None,
    requesting_app_pid: int | None = None,
    launchctl: Callable[..., Any] = subprocess.run,
    stage_timeouts: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Execute one serialized, staged, bounded service lifecycle operation."""
    mutation = ServiceMutation(
        paths, operation_type, app_build=app_build, app_instance=app_instance,
        requesting_app_pid=requesting_app_pid, stage_timeouts=stage_timeouts,
    )
    try:
        mutation.begin()
    except MutationActiveError as error:
        record = error.record
        return {
            "contract": COMMAND_CONTRACT,
            "operation_id": record.get("operation_id"),
            "operation_status": record.get("status", "RUNNING"),
            "operation_stage": record.get("current_stage"),
            "retryable": False,
            "recommended_action": "VIEW_ACTIVE_OPERATION",
            "reason": str(error),
            "active_operation": record,
        }

    operation = operation_type.upper()
    domain = f"gui/{os.getuid()}"
    service = f"{domain}/{SERVICE_LABEL}"

    def command(arguments: list[str], *, required: bool = True) -> Any:
        try:
            result = launchctl(arguments, check=required, capture_output=True)
        except subprocess.CalledProcessError as error:
            stderr = error.stderr or b""
            detail = stderr.decode(errors="replace") if isinstance(stderr, bytes) else str(stderr)
            raise LifecycleFailure("LAUNCH_AGENT_COMMAND_FAILED", detail or str(error), "REPAIR_SERVICE") from error
        if required and getattr(result, "returncode", 0) != 0:
            stderr = getattr(result, "stderr", b"")
            detail = stderr.decode(errors="replace") if isinstance(stderr, bytes) else str(stderr)
            raise LifecycleFailure("LAUNCH_AGENT_COMMAND_FAILED", detail or "LaunchAgent command failed.", "REPAIR_SERVICE")
        return result

    def request_stop() -> None:
        mutation.stage("REQUESTING_GRACEFUL_STOP", "Requesting a graceful Scheduler stop", cancellable=False)
        try:
            send_service_request(paths, make_command("STOP_SERVICE"), timeout=10)
        except OSError:
            command(["launchctl", "kill", "SIGTERM", service], required=False)
        mutation.wait_for(lambda: not ownership_is_active(paths), "DRAINING_ACTIVE_WORK", "Draining active work and waiting for acquisition ownership release")
        mutation.stage("WAITING_FOR_PROCESS_EXIT", "Scheduler process exited", cancellable=False)
        mutation.wait_for(lambda: not ownership_is_active(paths), "VERIFYING_OWNERSHIP_RELEASE", "Verifying acquisition ownership release")

    def request_start() -> None:
        mutation.stage("VALIDATING_INSTALLATION", "Validating the installed Scheduler service")
        if not paths.launch_agent.exists():
            raise LifecycleFailure("LAUNCH_AGENT_NOT_INSTALLED", "The Scheduler LaunchAgent is not installed.", "INSTALL_SERVICE")
        if not _automatic_login_start(paths):
            raise LifecycleFailure("LAUNCH_AGENT_DISABLED", "The Scheduler LaunchAgent is installed but disabled.", "ENABLE_SERVICE")
        if ownership_is_active(paths):
            if paths.socket.exists() and _cached_service_is_healthy(paths):
                return
            raise LifecycleFailure(
                "SERVICE_PROCESS_ALIVE_MONITOR_UNREACHABLE",
                "Scheduler process is alive but monitor connection is unavailable.",
                "REPAIR_MONITOR",
            )
        mutation.stage("REQUESTING_LAUNCH", "Requesting LaunchAgent start")
        command(["launchctl", "kickstart", "-k", service])
        mutation.wait_for(lambda: ownership_is_active(paths), "WAITING_FOR_PROCESS", "Waiting for Scheduler process")
        mutation.wait_for(lambda: paths.socket.exists(), "WAITING_FOR_SOCKET", "Waiting for service monitor socket")
        mutation.wait_for(lambda: _cached_service_is_healthy(paths), "WAITING_FOR_HEARTBEAT", "Waiting for service heartbeat")
        mutation.stage("VERIFYING_SERVICE_GENERATION", "Verifying the live service generation")

    def verify_started_service() -> None:
        mutation.wait_for(lambda: ownership_is_active(paths), "WAITING_FOR_PROCESS", "Waiting for Scheduler process")
        mutation.wait_for(lambda: paths.socket.exists(), "WAITING_FOR_SOCKET", "Waiting for service monitor socket")
        mutation.wait_for(lambda: _cached_service_is_healthy(paths), "WAITING_FOR_HEARTBEAT", "Waiting for service heartbeat")

    try:
        detail: dict[str, Any] = {}
        if operation == "INSTALL":
            mutation.stage("VALIDATING_INSTALLATION", "Validating installation paths")
            mutation.stage("WRITING_SERVICE_FILES", "Writing the user-scoped service definition", cancellable=False)
            detail = install_service(paths, python=python, repository=repository, enable=False, launchctl=launchctl)
            mutation.stage("UPDATING_LAUNCH_AGENT", "Installing the LaunchAgent definition", cancellable=False)
            command(["launchctl", "bootout", domain, str(paths.launch_agent)], required=False)
            mutation.stage("REQUESTING_LAUNCH", "Loading the installed LaunchAgent")
            command(["launchctl", "bootstrap", domain, str(paths.launch_agent)])
            verify_started_service()
            mutation.stage("VERIFYING_INSTALLATION", "Installation completed")
        elif operation == "START":
            request_start()
        elif operation == "STOP":
            if ownership_is_active(paths):
                request_stop()
            mutation.stage("VERIFYING_OWNERSHIP_RELEASE", "Scheduler is stopped and acquisition ownership is released", cancellable=False)
        elif operation == "RESTART":
            if ownership_is_active(paths):
                request_stop()
            mutation.stage("REQUESTING_LAUNCH", "Starting a replacement Scheduler generation")
            request_start()
        elif operation == "UPDATE":
            mutation.stage("VALIDATING_NEW_BUILD", "Validating the replacement service build")
            if ownership_is_active(paths):
                mutation.stage("REQUESTING_SERVICE_STOP", "Stopping the current service for update", cancellable=False)
                request_stop()
            mutation.stage("WAITING_FOR_OWNERSHIP_RELEASE", "Acquisition ownership is released", cancellable=False)
            mutation.stage("REPLACING_SERVICE", "Replacing service files", cancellable=False)
            detail = install_service(paths, python=python, repository=repository, enable=False, launchctl=launchctl)
            mutation.stage("UPDATING_LAUNCH_AGENT", "Updating the LaunchAgent definition", cancellable=False)
            command(["launchctl", "bootout", domain, str(paths.launch_agent)], required=False)
            command(["launchctl", "bootstrap", domain, str(paths.launch_agent)])
            mutation.stage("STARTING_NEW_SERVICE", "Replacement generation requested")
            verify_started_service()
            mutation.stage("VERIFYING_COMPATIBILITY", "Replacement service build installed")
        elif operation == "REPAIR":
            for stage, message in (
                ("INSPECTING_LAUNCH_AGENT", "Inspecting LaunchAgent installation"),
                ("INSPECTING_EXECUTABLE", "Inspecting configured service executable"),
                ("VERIFYING_SIGNATURE", "Verifying service executable integrity"),
                ("VERIFYING_PATHS", "Verifying service paths"),
                ("CHECKING_AUTHORITY", "Checking canonical authority access"),
                ("CHECKING_JOURNAL", "Checking operational journal access"),
                ("CHECKING_SOCKET", "Checking monitor socket"),
                ("CHECKING_OWNERSHIP", "Checking acquisition ownership without changing it"),
            ):
                mutation.stage(stage, message)
            if ownership_is_active(paths) and not paths.socket.exists():
                raise LifecycleFailure(
                    "SERVICE_PROCESS_ALIVE_MONITOR_UNREACHABLE",
                    "Scheduler process is alive but monitor connection is unavailable.",
                    "REPAIR_MONITOR",
                )
            detail = repair_service(paths)
            mutation.stage("REPAIRING_FILES", "Repair checks completed", cancellable=False)
            if paths.launch_agent.exists() and not ownership_is_active(paths):
                mutation.stage("RELOADING_LAUNCH_AGENT", "Reloading the repaired LaunchAgent", cancellable=False)
                command(["launchctl", "bootout", domain, str(paths.launch_agent)], required=False)
                command(["launchctl", "bootstrap", domain, str(paths.launch_agent)])
                verify_started_service()
            mutation.stage("VERIFYING_HEARTBEAT", "Repair state reconciled")
        elif operation == "ENABLE":
            mutation.stage("REQUESTING_ENABLE", "Enabling automatic Scheduler launch")
            command(["launchctl", "enable", service])
            command(["launchctl", "bootstrap", domain, str(paths.launch_agent)], required=False)
            metadata = _read_json(paths.metadata, {})
            if isinstance(metadata, dict):
                metadata["automatic_login_start"] = True
                _atomic_json(paths.metadata, metadata)
            verify_started_service()
            mutation.stage("VERIFYING_INSTALLATION", "LaunchAgent is enabled")
        elif operation == "DISABLE":
            mutation.stage("REQUESTING_DISABLE", "Disabling automatic Scheduler launch", cancellable=False)
            command(["launchctl", "disable", service])
            command(["launchctl", "bootout", domain, str(paths.launch_agent)], required=False)
            metadata = _read_json(paths.metadata, {})
            if isinstance(metadata, dict):
                metadata["automatic_login_start"] = False
                _atomic_json(paths.metadata, metadata)
            if ownership_is_active(paths):
                mutation.wait_for(lambda: not ownership_is_active(paths), "WAITING_FOR_PROCESS_EXIT", "Waiting for Scheduler process exit")
            mutation.stage("VERIFYING_OWNERSHIP_RELEASE", "Automatic launch is disabled", cancellable=False)
        elif operation == "UNINSTALL":
            if ownership_is_active(paths):
                request_stop()
            mutation.stage("REMOVING_LAUNCH_AGENT", "Removing the user-scoped LaunchAgent", cancellable=False)
            command(["launchctl", "bootout", domain, str(paths.launch_agent)], required=False)
            paths.launch_agent.unlink(missing_ok=True)
            paths.metadata.unlink(missing_ok=True)
            mutation.stage("VERIFYING_REMOVAL", "Verifying service removal")
        elif operation == "FORCE_RECONCILE":
            mutation.stage("INSPECTING_SERVICE_STATE", "Inspecting LaunchAgent, process, ownership, socket, heartbeat, and mutation state")
            detail = service_diagnostics(paths, app_build=app_build)
            if ownership_is_active(paths) and not paths.socket.exists():
                detail["reconciliation_outcome"] = "ACQUISITION_OWNER_STILL_ACTIVE"
                detail["recommended_action"] = "REPAIR_MONITOR"
            elif _cached_service_is_healthy(paths):
                detail["reconciliation_outcome"] = "ACTIVE_OPERATION_CONFIRMED"
                detail["recommended_action"] = "RETRY_CONNECTION"
            elif paths.launch_agent.exists():
                detail["reconciliation_outcome"] = "STALE_OPERATION_CLEARED"
                detail["recommended_action"] = "START_SERVICE"
            else:
                detail["reconciliation_outcome"] = "SERVICE_STATE_INCONSISTENT"
                detail["recommended_action"] = "INSTALL_SERVICE"
            mutation.stage("REBUILDING_SERVICE_PROJECTION", "Rebuilding the native service projection", cancellable=False)
        else:
            raise ValueError(f"unsupported lifecycle operation: {operation}")
        return mutation.complete(detail)
    except BaseException as error:
        return mutation.fail(error)


def force_reconcile_service_state(
    paths: ServicePaths,
    *,
    app_build: str = "Development",
    app_instance: str | None = None,
    requesting_app_pid: int | None = None,
    stage_timeouts: dict[str, float] | None = None,
) -> dict[str, Any]:
    return manage_service_lifecycle(
        paths, "FORCE_RECONCILE", app_build=app_build, app_instance=app_instance,
        requesting_app_pid=requesting_app_pid, stage_timeouts=stage_timeouts,
    )


def record_restart(paths: ServicePaths, reason: str) -> dict[str, Any]:
    history = _read_json(paths.restart_history, [])
    history.append({"at": utc_now(), "reason": reason})
    history = history[-20:]
    _atomic_json(paths.restart_history, history)
    now = datetime.now(UTC)
    recent = []
    for item in history[-5:]:
        try:
            if (now - datetime.fromisoformat(str(item["at"]))).total_seconds() <= 600:
                recent.append(item)
        except (KeyError, TypeError, ValueError):
            continue
    state = "CRASH_LOOP_PROTECTED" if len(recent) >= 5 else "DEGRADED_RESTARTING"
    status = _read_json(paths.status, {})
    status.update(
        contract=STATUS_CONTRACT,
        service_state=state,
        live=False,
        restart_count=len(history),
        last_exit_reason=reason,
        last_successful_monitor_update=status.get("heartbeat_time"),
    )
    _atomic_json(paths.status, status)
    return {"restart_count": len(history), "service_state": state}
