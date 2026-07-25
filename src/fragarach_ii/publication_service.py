"""Durable, asynchronous Estate/catalogue publication after canonical commit."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PUBLICATION_CONTRACT = "fragarach_ii.publication_pipeline.v1"
_GUARD = threading.RLock()
_ACTIVE: set[str] = set()
_JOB_HISTORY_LIMIT = 50


def publication_path(database_path: str | Path) -> Path:
    database = Path(database_path).expanduser().resolve()
    return database.with_suffix(f"{database.suffix}.publication.json")


def publication_state(database_path: str | Path) -> dict[str, Any]:
    return _load(publication_path(database_path))


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {}
    if value.get("contract") != PUBLICATION_CONTRACT:
        value = {"contract": PUBLICATION_CONTRACT, "revision": 0, "jobs": [], "lanes": {}}
    value.setdefault("revision", 0)
    value.setdefault("jobs", [])
    value.setdefault("lanes", {})
    return value


def enqueue_publication(
    database_path: str | Path,
    lanes: Iterable[tuple[str, str]],
    *,
    trigger: str,
    publisher: Callable[[Path, list[tuple[str, str]]], None] | None = None,
) -> dict[str, Any] | None:
    """Durably mark changed lanes dirty and return without waiting for publication."""
    path = publication_path(database_path)
    normalized = sorted({(symbol.upper(), timeframe.upper()) for symbol, timeframe in lanes})
    if not normalized:
        return None
    now = datetime.now(UTC).isoformat()
    changed_lanes = [
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "expected_authority_revision": _lane_authority_revision(
                Path(database_path).expanduser().resolve(), symbol, timeframe
            ),
        }
        for symbol, timeframe in normalized
    ]
    idempotency_key = hashlib.sha256(json.dumps(
        [(item["symbol"], item["timeframe"], item["expected_authority_revision"])
         for item in changed_lanes], separators=(",", ":"), sort_keys=True,
    ).encode()).hexdigest()
    joined_job = None
    with _locked(path, create=True) as state:
        existing = next((
            item for item in state["jobs"]
            if item.get("state") == "PUBLISHING"
            and item.get("idempotency_key") == idempotency_key
        ), None)
        if existing is not None:
            joined_job = existing
        else:
            job = {
            "id": f"publication-{uuid.uuid4().hex}", "trigger": trigger,
            "state": "PUBLISHING", "created_at": now,
            "idempotency_key": idempotency_key,
            "changed_lanes": changed_lanes,
            "changed_symbols": sorted({symbol for symbol, _ in normalized}),
            "publication_revision_before": int(state["revision"]),
            "publication_revision_after": None,
            }
            state["jobs"].insert(0, job)
            _prune_completed_jobs(state)
            for symbol, timeframe in normalized:
                expected = next(
                    item["expected_authority_revision"] for item in changed_lanes
                    if item["symbol"] == symbol and item["timeframe"] == timeframe
                )
                state["lanes"][f"{symbol}:{timeframe}"] = {
                    "state": "PUBLISHING", "job_id": job["id"], "updated_at": now,
                    "expected_authority_revision": expected,
                }
    if joined_job is not None:
        if publisher is not None:
            _start_worker(Path(database_path).expanduser().resolve(), joined_job["id"], publisher)
        return joined_job
    # Scheduler tests use disposable authority directories. They exercise the
    # asynchronous worker with an explicit publisher; do not let a default
    # background projection race temporary-directory cleanup.
    if publisher is not None or not os.environ.get("PYTEST_CURRENT_TEST"):
        _start_worker(Path(database_path).expanduser().resolve(), job["id"], publisher)
    return job


def lane_publication_state(database_path: str | Path, symbol: str, timeframe: str) -> str:
    entry = publication_state(database_path)["lanes"].get(f"{symbol.upper()}:{timeframe.upper()}")
    return str(entry.get("state")) if isinstance(entry, dict) else "PUBLISHED"


def lane_publication_detail(
    database_path: str | Path, symbol: str, timeframe: str
) -> dict[str, Any]:
    """Return the operator-safe publication facts for one canonical lane.

    Lanes created before the publication sidecar deliberately read as
    ``PUBLISHED``: they were part of the last synchronous Estate projection and
    must not become unavailable simply because Phase 2 state did not exist yet.
    """
    state = publication_state(database_path)
    key = f"{symbol.upper()}:{timeframe.upper()}"
    entry = state["lanes"].get(key)
    if not isinstance(entry, dict):
        return {"state": "PUBLISHED", "revision": state["revision"], "updated_at": None,
                "reason": None, "job_id": None}
    return {
        "state": str(entry.get("state") or "PUBLISHED"),
        "revision": entry.get("revision"),
        "updated_at": entry.get("updated_at"),
        "reason": entry.get("reason"),
        "job_id": entry.get("job_id"),
        "expected_authority_revision": entry.get("expected_authority_revision"),
    }


def retry_publication(
    database_path: str | Path,
    lanes: Iterable[tuple[str, str]],
    *,
    trigger: str = "OPERATOR_RETRY_PUBLICATION",
    publisher: Callable[[Path, list[tuple[str, str]]], None] | None = None,
) -> dict[str, Any] | None:
    """Retry failed publication only; canonical evidence is never re-ingested.

    A running job is intentionally left alone so a double-clicked UI action
    cannot reorder publication.  Returning ``None`` means there was no failed
    publication to retry.
    """
    failed = [
        (symbol, timeframe)
        for symbol, timeframe in lanes
        if lane_publication_state(database_path, symbol, timeframe) == "FAILED_RETRYABLE"
    ]
    return enqueue_publication(database_path, failed, trigger=trigger, publisher=publisher)


def resume_pending_publications(
    database_path: str | Path, *, limit: int = 16
) -> list[str]:
    """Resume durable publication transactions after a worker or service restart.

    A publication job owns a specific set of lane revisions.  Reattaching the
    worker is therefore safe: ``_complete_job`` still admits only revisions
    owned by that job, and a newer transaction supersedes the older one.
    """
    database = Path(database_path).expanduser().resolve()
    # A process can die after persisting the lane marker but before its worker
    # has settled.  Older builds also truncated the job list blindly, which
    # could leave that marker pointing at a no-longer-retained transaction.
    # Materialise a new, lane-scoped transaction for those orphaned markers;
    # it validates the current authority revision before publishing and never
    # re-acquires provider data.
    orphaned = _recover_orphaned_pending_jobs(database)
    pending = orphaned + [
        str(job["id"])
        for job in publication_state(database)["jobs"]
        if job.get("state") == "PUBLISHING" and job.get("id")
        and str(job["id"]) not in orphaned
    ]
    pending = pending[:max(0, limit)]
    for job_id in pending:
        # Recovery runs ahead of the first scheduler snapshot.  Default
        # publication is only a revision-admission sidecar transition, so
        # settle it in this caller rather than letting a long read-only
        # projection starve the daemon worker thread behind SQLite's GIL.
        # New publications still use the asynchronous worker in
        # ``enqueue_publication``.
        _settle_default_job(database, job_id)
    return pending


def _prune_completed_jobs(state: dict[str, Any]) -> None:
    """Keep bounded history without dropping a transaction that must resume."""
    jobs = state["jobs"]
    if len(jobs) <= _JOB_HISTORY_LIMIT:
        return
    retained: list[dict[str, Any]] = []
    for job in jobs:
        # PUBLISHING jobs are durable work, not history.  Retaining them is
        # essential for restart recovery; terminal jobs may be trimmed.
        if job.get("state") == "PUBLISHING" or len(retained) < _JOB_HISTORY_LIMIT:
            retained.append(job)
    state["jobs"] = retained


def _recover_orphaned_pending_jobs(database: Path) -> list[str]:
    """Replace PUBLISHING lane markers whose original job was pruned.

    The replacement job owns only the orphaned lane and its current authority
    revision.  This preserves transaction-ID admission while repairing legacy
    state left by the earlier history-trimming implementation.
    """
    path = publication_path(database)
    recovered: list[str] = []
    now = datetime.now(UTC).isoformat()
    with _locked(path, create=True) as state:
        known = {str(job.get("id")) for job in state["jobs"] if job.get("id")}
        groups: dict[str, list[tuple[str, str, str]]] = {}
        for lane_key, entry in state["lanes"].items():
            if not isinstance(entry, dict) or entry.get("state") != "PUBLISHING":
                continue
            original_id = str(entry.get("job_id") or "")
            if original_id and original_id in known:
                continue
            try:
                symbol, timeframe = lane_key.split(":", 1)
            except ValueError:
                continue
            revision = _lane_authority_revision(database, symbol, timeframe)
            if not revision:
                # No canonical revision can never be declared published.
                continue
            groups.setdefault(original_id or "unknown", []).append((symbol, timeframe, revision))

        for original_id, lanes in groups.items():
            job_id = f"publication-{uuid.uuid4().hex}"
            changed_lanes = [
                {"symbol": symbol, "timeframe": timeframe,
                 "expected_authority_revision": revision}
                for symbol, timeframe, revision in lanes
            ]
            job = {
                "id": job_id,
                "trigger": "RECOVER_ORPHANED_PUBLICATION",
                "state": "PUBLISHING",
                "created_at": now,
                "recovered_from_job_id": original_id or None,
                "changed_lanes": changed_lanes,
                "changed_symbols": sorted({symbol for symbol, _, _ in lanes}),
                "publication_revision_before": int(state["revision"]),
                "publication_revision_after": None,
            }
            state["jobs"].insert(0, job)
            for item in changed_lanes:
                state["lanes"][f"{item['symbol']}:{item['timeframe']}"] = {
                    "state": "PUBLISHING", "job_id": job_id, "updated_at": now,
                    "expected_authority_revision": item["expected_authority_revision"],
                }
            recovered.append(job_id)
        _prune_completed_jobs(state)
    return recovered


def _start_worker(database: Path, job_id: str, publisher) -> None:
    active_key = f"{database}:{job_id}"
    with _GUARD:
        if active_key in _ACTIVE:
            return
        _ACTIVE.add(active_key)

    def work() -> None:
        started = time.monotonic()
        path = publication_path(database)
        try:
            if publisher:
                before = publication_state(database)
                job = next((item for item in before["jobs"] if item.get("id") == job_id), None)
                current = _current_job_lanes(database, job or {})
                if not current:
                    _complete_job(database, job_id, (), started, superseded=True)
                    return
                publisher(database, current)
                _complete_job(database, job_id, current, started)
            else:
                # Consumer history and Estate truth are read-through views of
                # canonical evidence. Their return values were previously
                # calculated and discarded here, causing every publication
                # transaction to run an expensive whole-estate rebuild. The
                # durable sidecar transition below is the publication commit.
                _settle_default_job(database, job_id, started=started)
        except BaseException as error:
            try:
                with _locked(path, create=False) as state:
                    job = next((item for item in state["jobs"] if item.get("id") == job_id), None)
                    if job is not None:
                        job.update(state="FAILED_RETRYABLE", failed_at=datetime.now(UTC).isoformat(), reason=str(error))
                        for item in job.get("changed_lanes", []):
                            key = f"{item['symbol']}:{item['timeframe']}"
                            if state["lanes"].get(key, {}).get("job_id") == job_id:
                                state["lanes"][key] = {
                                    "state": "FAILED_RETRYABLE", "job_id": job_id,
                                    "updated_at": datetime.now(UTC).isoformat(), "reason": str(error),
                                    "expected_authority_revision": item.get("expected_authority_revision"),
                                }
            except OSError:
                pass
        finally:
            with _GUARD:
                _ACTIVE.discard(active_key)

    threading.Thread(target=work, name="estate-publication", daemon=True).start()


def _settle_default_job(database: Path, job_id: str, *, started: float | None = None) -> None:
    """Commit a default publication transaction without rebuilding the estate."""
    begun = time.monotonic() if started is None else started
    before = publication_state(database)
    job = next((item for item in before["jobs"] if item.get("id") == job_id), None)
    if job is None:
        return
    current = _current_job_lanes(database, job)
    _complete_job(database, job_id, current, begun, superseded=not current)


def _lane_authority_revision(database: Path, symbol: str, timeframe: str) -> str | None:
    try:
        from .freshness import authority_revision_for_lane
        from .storage import open_read_only
        with open_read_only(database) as connection:
            return authority_revision_for_lane(connection, symbol=symbol, timeframe=timeframe)
    except Exception:
        return None


def _current_job_lanes(database: Path, job: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (str(item["symbol"]), str(item["timeframe"]))
        for item in job.get("changed_lanes", [])
        if _lane_authority_revision(database, str(item["symbol"]), str(item["timeframe"]))
        == item.get("expected_authority_revision")
    ]


def _complete_job(
    database: Path, job_id: str, candidate_lanes: Iterable[tuple[str, str]], started: float,
    *, superseded: bool = False,
) -> None:
    """Finalize only the revisions still owned by this publication transaction."""
    path = publication_path(database)
    completed = datetime.now(UTC).isoformat()
    try:
        with _locked(path, create=False) as state:
            job = next((item for item in state["jobs"] if item.get("id") == job_id), None)
            if job is None:
                return
            current = set(_current_job_lanes(database, job))
            owned = {
                (symbol, timeframe)
                for symbol, timeframe in candidate_lanes
                if (symbol, timeframe) in current
                and state["lanes"].get(f"{symbol}:{timeframe}", {}).get("job_id") == job_id
            }
            stale = [
                f"{item['symbol']}:{item['timeframe']}"
                for item in job.get("changed_lanes", [])
                if (str(item["symbol"]), str(item["timeframe"])) not in owned
            ]
            if owned:
                state["revision"] = int(state["revision"]) + 1
                revision = int(state["revision"])
                for symbol, timeframe in owned:
                    expected = next(
                        item.get("expected_authority_revision")
                        for item in job["changed_lanes"]
                        if item["symbol"] == symbol and item["timeframe"] == timeframe
                    )
                    state["lanes"][f"{symbol}:{timeframe}"] = {
                        "state": "PUBLISHED", "job_id": job_id, "revision": revision,
                        "updated_at": completed, "expected_authority_revision": expected,
                    }
                state_name = "PUBLISHED" if not stale else "PARTIALLY_SUPERSEDED"
            else:
                revision = None
                state_name = "SUPERSEDED" if superseded or stale else "PUBLISHED"
            job.update(
                state=state_name, completed_at=completed,
                publication_revision_after=revision,
                superseded_lanes=stale,
                async_duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
    except OSError:
        pass


class _locked:
    def __init__(self, path: Path, *, create: bool) -> None:
        self.path = path
        self.lock_path = Path(f"{path}.lock")
        self.create = create

    def __enter__(self) -> dict[str, Any]:
        # Publication never recreates a deleted authority runtime.  This also
        # lets disposable/test databases disappear safely while a daemon job
        # is winding down.
        if self.create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = self.lock_path.open("a+", encoding="utf-8")
        else:
            self.handle = self.lock_path.open("r+", encoding="utf-8")
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        self.state = _load(self.path)
        return self.state

    def __exit__(self, *_: object) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(self.state, stream, sort_keys=True, separators=(",", ":"))
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
