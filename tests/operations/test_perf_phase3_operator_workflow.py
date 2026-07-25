"""Focused Phase 3 operator workflow and publication-recovery coverage."""

from __future__ import annotations

import tempfile
import time
import json
from pathlib import Path

from fragarach_ii.ingestion.manual import ingest_manual_file
from fragarach_ii.publication_service import (
    enqueue_publication,
    lane_publication_detail,
    publication_path,
    retry_publication,
)
from fragarach_ii.scheduler_service import scheduler_snapshot
from tests.operations.test_spec047_unified_acquisition import _registered_gbpaud


def _wait(database: Path, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        from fragarach_ii.publication_service import publication_state

        job = next(item for item in publication_state(database)["jobs"] if item["id"] == job_id)
        if job["state"] != "PUBLISHING":
            return job
        time.sleep(0.01)
    raise AssertionError("publication job did not settle")


def test_failed_publication_is_resumable_without_canonical_reingestion() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"

        def fail(_database: Path, _lanes: list[tuple[str, str]]) -> None:
            raise RuntimeError("temporary projection outage")

        failed = enqueue_publication(
            database, [("AUDUSD", "D1")], trigger="TEST", publisher=fail
        )
        assert failed is not None
        _wait(database, str(failed["id"]))
        detail = lane_publication_detail(database, "AUDUSD", "D1")
        assert detail["state"] == "FAILED_RETRYABLE"
        assert detail["reason"] == "temporary projection outage"

        resumed = retry_publication(
            database, [("AUDUSD", "D1")], publisher=lambda *_: None
        )
        assert resumed is not None
        _wait(database, str(resumed["id"]))
        assert lane_publication_detail(database, "AUDUSD", "D1")["state"] == "PUBLISHED"


def test_manual_import_marks_the_changed_lane_for_async_publication() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database = root / "authority.sqlite3"
        source = root / "AUDUSD_D1.csv"
        source.write_text(
            "timestamp,open,high,low,close,volume\n2026-07-10,1,2,0,1.5,10\n",
            encoding="utf-8",
        )
        result = ingest_manual_file(database, source, symbol="AUDUSD", timeframe="D1")
        assert result.transaction_state == "committed"
        # Pytest deliberately suppresses default publisher threads; the durable
        # dirty marker is the contract under test.
        assert lane_publication_detail(database, "AUDUSD", "D1")["state"] == "PUBLISHING"


def test_scheduler_normalizes_legacy_empty_publication_state_to_published() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_gbpaud(database)
        publication_path(database).write_text(json.dumps({
            "contract": "fragarach_ii.publication_pipeline.v1",
            "revision": 0,
            "jobs": [],
            "lanes": {"GBPAUD:D1": {"state": None}},
        }), encoding="utf-8")
        snapshot = scheduler_snapshot(database)
        lane = next(item for item in snapshot["lanes"] if item["id"] == "GBPAUD:D1")
        assert lane["publication_state"] == "PUBLISHED"
