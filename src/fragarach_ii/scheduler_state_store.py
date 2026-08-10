"""SQLite authority for scheduler control state and immutable audit history."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .storage import initialize_database, open_read_only, registered_writer, transaction


STATE_CONTRACT = "fragarach_ii.scheduler_state_store.v1"
_AUDIT_ID_CACHE_LOCK = threading.Lock()
_AUDIT_ID_CACHE: dict[tuple[str, int | None, int | None, str], set[str]] = {}
_AUDIT_ID_CACHE_INITIALIZED: set[tuple[str, int | None, int | None, str]] = set()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SchedulerStateStore:
    """Persist a scheduler's live dispatch state under the registered writer.

    ``state_key`` intentionally includes the requested journal path.  Production
    uses the default key, while tests and operator sandboxes can still use an
    explicitly separate journal without sharing control state accidentally.
    """

    def __init__(self, database_path: str | Path, journal_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        journal = Path(journal_path).expanduser().resolve()
        digest = hashlib.sha256(str(journal).encode("utf-8")).hexdigest()
        self.state_key = f"SCHEDULER_V1:{digest}"
        self._bind_audit_cache()

    def _bind_audit_cache(self) -> None:
        try:
            identity = self.database_path.stat()
            device, inode = identity.st_dev, identity.st_ino
        except OSError:
            device, inode = None, None
        self._audit_cache_key = (
            str(self.database_path), device, inode, self.state_key,
        )
        # A scheduler save can happen at several stages of one provider
        # request.  The journal's hot history deliberately overlaps between
        # those saves, so repeatedly issuing an ON CONFLICT probe for every
        # already-persisted event turns an append-only audit into a large
        # random-index workload. Keep one cache per database identity and state
        # key for the entire process—not per SchedulerStateStore instance,
        # because each scheduler cycle constructs a fresh journal facade.
        with _AUDIT_ID_CACHE_LOCK:
            self._known_audit_event_ids = _AUDIT_ID_CACHE.setdefault(
                self._audit_cache_key, set()
            )

    def ensure(self) -> None:
        initialize_database(self.database_path)
        # A new test/operator database may not have existed at construction.
        # Bind again after creation so subsequent journal facades share its
        # stable filesystem identity rather than the pre-creation placeholder.
        if self._audit_cache_key[1] is None:
            self._bind_audit_cache()

    def load(self) -> dict[str, object] | None:
        try:
            with open_read_only(self.database_path) as connection:
                row = connection.execute(
                    "SELECT state_json FROM scheduler_runtime_state WHERE state_key = ?",
                    (self.state_key,),
                ).fetchone()
        except Exception:
            return None
        if row is None:
            return None
        try:
            value = json.loads(str(row[0]))
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def save(
        self, state: dict[str, object], *, audit_state: dict[str, object] | None = None
    ) -> int:
        """Atomically replace live state and append deduplicated audit events."""

        payload = _canonical(state)
        audit_events = tuple(_audit_events(self.state_key, audit_state or state))
        self._initialize_known_audit_event_ids(audit_events)
        with _AUDIT_ID_CACHE_LOCK:
            pending_audit_events = tuple(
                event for event in audit_events
                if event[0] not in self._known_audit_event_ids
            )
        now = _utc_now()
        with registered_writer(self.database_path) as connection:
            with transaction(connection):
                row = connection.execute(
                    "SELECT state_revision FROM scheduler_runtime_state WHERE state_key = ?",
                    (self.state_key,),
                ).fetchone()
                revision = int(row[0]) + 1 if row is not None else 1
                connection.execute(
                    """
                    INSERT INTO scheduler_runtime_state
                        (state_key, state_json, state_revision, updated_at_utc)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(state_key) DO UPDATE SET
                        state_json = excluded.state_json,
                        state_revision = excluded.state_revision,
                        updated_at_utc = excluded.updated_at_utc
                    """,
                    (self.state_key, payload, revision, now),
                )
                if pending_audit_events:
                    connection.executemany(
                        """
                        INSERT INTO scheduler_audit_events
                            (event_id, state_key, category, lane_id, occurred_at_utc,
                             payload_json, payload_sha256)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(event_id) DO NOTHING
                        """,
                        pending_audit_events,
                    )
                with _AUDIT_ID_CACHE_LOCK:
                    self._known_audit_event_ids.update(
                        event[0] for event in pending_audit_events
                    )
        return revision

    def _initialize_known_audit_event_ids(
        self, audit_events: tuple[tuple[str, str, str, str | None, str, str, str], ...],
    ) -> None:
        """Prime the cache without probing the multi-gigabyte audit index.

        Runtime state and its projected audit events are committed by ``save``
        in one SQLite transaction. Therefore, if the runtime row already
        exists, every event represented by that loaded state was committed
        with it. A fresh database has no runtime row and correctly leaves the
        cache empty so the initial events are inserted.
        """
        with _AUDIT_ID_CACHE_LOCK:
            if self._audit_cache_key in _AUDIT_ID_CACHE_INITIALIZED:
                return
            with open_read_only(self.database_path) as connection:
                runtime_exists = connection.execute(
                    "SELECT 1 FROM scheduler_runtime_state WHERE state_key=?",
                    (self.state_key,),
                ).fetchone() is not None
            if runtime_exists:
                self._known_audit_event_ids.update(
                    event[0] for event in audit_events
                )
            _AUDIT_ID_CACHE_INITIALIZED.add(self._audit_cache_key)


def _audit_events(
    state_key: str, state: dict[str, object]
) -> Iterable[tuple[str, str, str, str | None, str, str, str]]:
    """Project completed dispatch history into an append-only SQLite ledger."""

    history_keys = (
        "events", "execution_trace_events", "operation_timing_records",
        "scheduler_cycles", "routing_decisions", "request_lifecycle",
        "archived_operational_work",
    )
    for category in history_keys:
        records = state.get(category)
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict):
                    yield _audit_event(state_key, category, record)
    requests = state.get("manual_requests")
    if isinstance(requests, list):
        for request in requests:
            if isinstance(request, dict) and request.get("status") in {
                "Archived", "Resolved", "Dismissed",
            }:
                yield _audit_event(state_key, "manual_request_history", request)
    lanes = state.get("lanes")
    if isinstance(lanes, dict):
        for lane_id, lane in lanes.items():
            if not isinstance(lane, dict):
                continue
            attempts = lane.get("attempt_history")
            if isinstance(attempts, list):
                for attempt in attempts:
                    if isinstance(attempt, dict):
                        yield _audit_event(state_key, "lane_attempt", attempt, str(lane_id))
            by_boundary = lane.get("provider_attempts_by_boundary")
            if isinstance(by_boundary, dict):
                for boundary, attempt in by_boundary.items():
                    if isinstance(attempt, dict):
                        entry = {"boundary": boundary, **attempt}
                        yield _audit_event(state_key, "provider_attempt", entry, str(lane_id))


def _audit_event(
    state_key: str, category: str, record: dict[str, object], lane_id: str | None = None
) -> tuple[str, str, str, str | None, str, str, str]:
    lane = lane_id or str(record.get("lane_id") or record.get("lane") or "") or None
    occurred = str(
        record.get("timestamp") or record.get("completed_at") or record.get("archived_at")
        or record.get("created_at") or record.get("recorded_at") or _utc_now()
    )
    # Older records occasionally use a non-ISO marker.  The audit timestamp is
    # always valid UTC while the original value remains inside payload_json.
    try:
        parsed = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
        occurred = parsed.astimezone(UTC).isoformat()
    except (TypeError, ValueError):
        occurred = _utc_now()
    payload = _canonical({
        "contract": STATE_CONTRACT, "state_key": state_key,
        "category": category, "record": record,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return (digest, state_key, category, lane, occurred, payload, digest)
