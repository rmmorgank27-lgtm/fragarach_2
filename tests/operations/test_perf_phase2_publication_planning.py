"""Focused Phase 2 publication-pipeline and authority-cache coverage."""

from __future__ import annotations

import tempfile
import time
import threading
from dataclasses import replace
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import cached_acquisition_capability_projection
from fragarach_ii.authority_cache import AUTHORITY_PREFLIGHT_CACHE
from fragarach_ii.publication_service import (
    enqueue_publication, lane_publication_state, publication_state,
    resume_pending_publications,
)
import fragarach_ii.publication_service as publication_service
from fragarach_ii.provider_facts import load_provider_facts, save_provider_facts
from fragarach_ii.scheduler_service import SchedulerJournal, scheduler_snapshot
from tests.operations.test_spec047_unified_acquisition import _registered_gbpaud
from tests.operations.test_spec060_required_set_acquisition import OBSERVED, _fx_profile


def _wait_for_publication(database: Path, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = next(item for item in publication_state(database)["jobs"] if item["id"] == job_id)
        if job["state"] != "PUBLISHING":
            return job
        time.sleep(0.02)
    raise AssertionError("publication worker did not settle")


def test_publication_is_enqueued_without_blocking_canonical_response() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_gbpaud(database)

        def slow_publisher(_database: Path, _lanes: list[tuple[str, str]]) -> None:
            time.sleep(0.4)

        started = time.monotonic()
        job = enqueue_publication(
            database, [("GBPAUD", "D1")], trigger="TEST", publisher=slow_publisher
        )
        assert job is not None
        assert time.monotonic() - started < 0.15
        assert lane_publication_state(database, "GBPAUD", "D1") == "PUBLISHING"
        settled = _wait_for_publication(database, str(job["id"]))
        assert settled["state"] == "PUBLISHED"
        assert settled["publication_revision_after"] == 1
        assert lane_publication_state(database, "GBPAUD", "D1") == "PUBLISHED"


def test_publication_failure_does_not_rollback_canonical_evidence() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_gbpaud(database)

        def failing_publisher(_database: Path, _lanes: list[tuple[str, str]]) -> None:
            raise RuntimeError("fixture publication failure")

        job = enqueue_publication(
            database, [("GBPAUD", "D1")], trigger="TEST", publisher=failing_publisher
        )
        assert job is not None
        settled = _wait_for_publication(database, str(job["id"]))
        assert settled["state"] == "FAILED_RETRYABLE"
        # The registration/evidence written before publication remains intact.
        assert lane_publication_state(database, "GBPAUD", "D1") == "FAILED_RETRYABLE"


def test_pending_publication_recovers_by_transaction_id_after_restart(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        monkeypatch.setattr(
            publication_service, "_lane_authority_revision",
            lambda _database, _symbol, _timeframe: "revision-1",
        )
        job = enqueue_publication(database, [("GBPAUD", "D1")], trigger="TEST")
        assert job is not None
        # Pytest deliberately does not start a default background worker, which
        # lets this exercise the same durable recovery path used after restart.
        assert lane_publication_state(database, "GBPAUD", "D1") == "PUBLISHING"
        assert resume_pending_publications(database) == [str(job["id"])]
        assert _wait_for_publication(database, str(job["id"]))["state"] == "PUBLISHED"


def test_orphaned_publishing_lane_is_recovered_by_a_replacement_transaction(monkeypatch) -> None:
    """A trimmed legacy job must not leave its lane waiting forever."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        monkeypatch.setattr(
            publication_service, "_lane_authority_revision",
            lambda _database, _symbol, _timeframe: "revision-1",
        )
        publication_service.publication_path(database).write_text(
            '{"contract":"fragarach_ii.publication_pipeline.v1","revision":0,'
            '"jobs":[],"lanes":{"BNBUSD:D1":{"state":"PUBLISHING",'
            '"job_id":"publication-pruned","expected_authority_revision":"revision-1"}}}',
            encoding="utf-8",
        )
        recovered = resume_pending_publications(database)
        assert len(recovered) == 1
        job = _wait_for_publication(database, recovered[0])
        assert job["state"] == "PUBLISHED"
        assert job["recovered_from_job_id"] == "publication-pruned"
        detail = publication_state(database)["lanes"]["BNBUSD:D1"]
        assert detail["state"] == "PUBLISHED"
        assert detail["job_id"] == recovered[0]


def test_active_publications_are_not_pruned_from_recovery_history(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        monkeypatch.setattr(
            publication_service, "_lane_authority_revision",
            lambda _database, symbol, timeframe: f"{symbol}:{timeframe}",
        )
        monkeypatch.setattr(publication_service, "_start_worker", lambda *_: None)
        jobs = [
            enqueue_publication(database, [(f"TEST{index}", "D1")], trigger="TEST")
            for index in range(55)
        ]
        state = publication_state(database)
        retained = {str(job["id"]) for job in state["jobs"]}
        assert all(job is not None and str(job["id"]) in retained for job in jobs)


def test_newer_publication_revision_supersedes_an_older_job_without_lane_blocking(monkeypatch) -> None:
    """Concurrent jobs finalize only the lane revision they were created for."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        revisions = {"GBPAUD:D1": "revision-1"}
        monkeypatch.setattr(
            publication_service, "_lane_authority_revision",
            lambda _database, symbol, timeframe: revisions[f"{symbol}:{timeframe}"],
        )
        started, release = threading.Event(), threading.Event()

        def slow(_database: Path, _lanes: list[tuple[str, str]]) -> None:
            started.set()
            assert release.wait(2)

        first = enqueue_publication(
            database, [("GBPAUD", "D1")], trigger="FIRST", publisher=slow
        )
        assert first is not None and started.wait(2)
        revisions["GBPAUD:D1"] = "revision-2"
        second = enqueue_publication(
            database, [("GBPAUD", "D1")], trigger="SECOND", publisher=lambda *_: None
        )
        assert second is not None and second["id"] != first["id"]
        assert _wait_for_publication(database, str(second["id"]))["state"] == "PUBLISHED"
        release.set()
        stale = _wait_for_publication(database, str(first["id"]))

        detail = publication_state(database)["lanes"]["GBPAUD:D1"]
        assert stale["state"] == "SUPERSEDED"
        assert detail["job_id"] == second["id"]
        assert detail["state"] == "PUBLISHED"
        assert detail["expected_authority_revision"] == "revision-2"


def test_planning_cache_reuses_stable_revision_and_invalidates_credential_revision() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_gbpaud(database)
        AUTHORITY_PREFLIGHT_CACHE.invalidate()
        profile = replace(_fx_profile(), concurrency_limit=2)
        before = AUTHORITY_PREFLIGHT_CACHE.metrics()
        first = cached_acquisition_capability_projection(
            database, profiles=(profile,), credentials={"TWELVE_DATA": "first"}, now=OBSERVED
        )
        second = cached_acquisition_capability_projection(
            database, profiles=(profile,), credentials={"TWELVE_DATA": "first"}, now=OBSERVED
        )
        after_reuse = AUTHORITY_PREFLIGHT_CACHE.metrics()
        changed_credential = cached_acquisition_capability_projection(
            database, profiles=(profile,), credentials={"TWELVE_DATA": "second"}, now=OBSERVED
        )
        after_invalidation = AUTHORITY_PREFLIGHT_CACHE.metrics()
        facts = load_provider_facts(database)
        facts["mappings"]["TWELVE_DATA:GBPAUD"] = {
            "canonical_symbol": "GBPAUD", "provider_symbol": "GBP/AUD",
            "mapping_class": "EXACT_REPRESENTATION", "status": "OPERATOR_RESOLVED",
        }
        save_provider_facts(database, facts)
        cached_acquisition_capability_projection(
            database, profiles=(profile,), credentials={"TWELVE_DATA": "second"}, now=OBSERVED
        )
        after_mapping_change = AUTHORITY_PREFLIGHT_CACHE.metrics()
        assert first["rows"] == second["rows"] == changed_credential["rows"]
        assert after_reuse["hits"] == before["hits"] + 1
        assert after_invalidation["misses"] == after_reuse["misses"] + 1
        assert after_mapping_change["misses"] == after_invalidation["misses"] + 1


def test_monitor_snapshot_has_payload_guard() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal_path = Path(directory) / "scheduler.json"
        _registered_gbpaud(database)
        journal = SchedulerJournal(database, journal_path)
        journal.data["execution_trace_events"] = [
            {"lane_id": "GBPAUD:D1", "trace_id": str(index), "event": "REQUEST_STARTED"}
            for index in range(2_000)
        ]
        journal.save()
        snapshot = scheduler_snapshot(database, journal_path=journal_path, clock=lambda: OBSERVED)
        assert snapshot["monitor_guard"]["payload_bytes"] < 2 * 1024 * 1024
        assert snapshot["monitor_guard"]["within_size_target"] is True
