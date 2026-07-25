"""Focused regression coverage for Phase 1 concurrent lane execution."""

from __future__ import annotations

import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path

from fragarach_ii.scheduler_service import SchedulerJournal, run_operator_fetch, run_required_set_fetch
from tests.operations.test_spec060_required_set_acquisition import (
    OBSERVED,
    _fx_profile,
    _publish_terminal_bar,
)
from tests.operations.test_spec047_unified_acquisition import _registered_gbpaud


def test_required_set_overlaps_two_provider_lanes_and_records_timing() -> None:
    """Two slow lanes run together; canonical writes remain independently safe."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal = Path(directory) / "scheduler.json"
        _registered_gbpaud(database)
        profile = replace(_fx_profile(), concurrency_limit=2)
        active = 0
        peak_active = 0
        guard = threading.Lock()

        def slow_acquirer(_database, **kwargs):
            nonlocal active, peak_active
            with guard:
                active += 1
                peak_active = max(peak_active, active)
            try:
                time.sleep(0.35)
                return _publish_terminal_bar(database, **kwargs)
            finally:
                with guard:
                    active -= 1

        started = time.monotonic()
        result = run_required_set_fetch(
            database, symbol="GBPAUD", credential=None, journal_path=journal,
            provider_profiles=(profile,), acquirer=slow_acquirer, at=OBSERVED,
        )
        elapsed = time.monotonic() - started

        assert result["outcome"] == "SUCCESS"
        assert peak_active == 2
        # Four lanes execute in two bounded waves, rather than four serial calls.
        assert elapsed < 1.2
        timings = [
            item for item in SchedulerJournal(database, journal).data["operation_timing_records"]
            if item.get("step_name") == "lane_execution"
        ]
        assert len(timings) == 4
        assert all(item.get("provider_started_at") for item in timings)
        assert all(item.get("provider_finished_at") for item in timings)
        assert all(item.get("worker_id") for item in timings)


def test_same_lane_operator_request_attaches_to_existing_execution() -> None:
    """A second request cannot create a concurrent writer for one lane."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal = Path(directory) / "scheduler.json"
        _registered_gbpaud(database)
        profile = replace(_fx_profile(timeframes=("D1",)), concurrency_limit=2)
        provider_entered = threading.Event()
        release_provider = threading.Event()
        calls = 0

        def slow_acquirer(_database, **kwargs):
            nonlocal calls
            calls += 1
            provider_entered.set()
            assert release_provider.wait(2)
            return _publish_terminal_bar(database, **kwargs)

        first_result: dict[str, object] = {}

        def first_request() -> None:
            first_result.update(run_operator_fetch(
                database, symbol="GBPAUD", timeframe="D1", credential=None,
                requested_mode="initial", requested_start="2026-07-01",
                requested_end="2026-07-14", reviewed_historical_range=True,
                journal_path=journal, provider_profiles=(profile,),
                acquirer=slow_acquirer, at=OBSERVED,
            ))

        worker = threading.Thread(target=first_request)
        worker.start()
        assert provider_entered.wait(2)
        duplicate = run_operator_fetch(
            database, symbol="GBPAUD", timeframe="D1", credential=None,
            requested_mode="initial", requested_start="2026-07-01",
            requested_end="2026-07-14", reviewed_historical_range=True,
            journal_path=journal, provider_profiles=(profile,),
            acquirer=slow_acquirer, at=OBSERVED,
        )
        release_provider.set()
        worker.join(3)

        assert not worker.is_alive()
        assert first_result["outcome"] == "SUCCESS"
        assert duplicate["outcome"] == "DEDUPLICATED_ACTIVE_WORK"
        assert calls == 1
