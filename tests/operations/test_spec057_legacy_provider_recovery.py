from __future__ import annotations

import base64
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fragarach_ii.estate_truth_service import estate_truth_state
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.onboarding import register_provider_aware_instrument
from fragarach_ii.provider_facts import load_provider_facts, provider_facts_path, representation_mapping
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.scheduler_service import SchedulerJournal
from fragarach_ii.storage import open_read_only


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "data/runtime/spec002_real_evidence_acceptance.sqlite3"
NOW = datetime(2026, 7, 16, 3, 0, tzinfo=UTC)


def _legacy_fdx(tmp_path: Path) -> tuple[Path, Path]:
    database = tmp_path / "authority.sqlite3"
    journal = Path(f"{database}.scheduler.json")
    # The native runtime is WAL-backed.  SQLite's online backup includes the
    # current WAL state, unlike a raw file copy while the app is running.
    with sqlite3.connect(RUNTIME) as source, sqlite3.connect(database) as destination:
        source.backup(destination)
    facts = provider_facts_path(RUNTIME)
    if facts.exists():
        shutil.copy2(facts, provider_facts_path(database))
    return database, journal


def _fdx_candidate(database: Path):
    market = discover_market(database, "FDX")["markets"][0]
    representation = next(item for item in market["representations"] if item["symbol"] == "FDX")
    assert representation["acquisition_readiness"] == "PROVIDER_SETUP_INCOMPLETE"
    assert representation["registration_plan"] is not None
    payload = base64.urlsafe_b64decode(representation["registration_plan"]["candidate"])
    return candidate_from_dict(json.loads(payload))


def _registration_and_evidence(database: Path) -> tuple[tuple[object, ...], tuple[int, int, int]]:
    with open_read_only(database) as connection:
        registration = connection.execute(
            """SELECT identity_json, registered_at_utc, registration_status
                 FROM instrument_registrations WHERE asset='FDX' AND timeframe='D1'"""
        ).fetchone()
        evidence = connection.execute(
            """SELECT count(*), (SELECT count(*) FROM provenance WHERE symbol='FDX' AND timeframe='D1'),
                      (SELECT count(*) FROM ingest_runs WHERE json_extract(detail,'$.asset')='FDX')
                 FROM bars WHERE asset='FDX' AND timeframe='D1'"""
        ).fetchone()
    assert registration is not None
    return tuple(registration), tuple(int(value) for value in evidence)


def test_legacy_fdx_remains_servable_and_requires_provider_setup(tmp_path: Path) -> None:
    database, _ = _legacy_fdx(tmp_path)
    estate = estate_truth_state(database, clock=lambda: NOW)
    fdx = next(item for item in estate["timeframe_capabilities"] if item["symbol"] == "FDX")
    lane = next(item for item in fdx["timeframes"] if item["timeframe"] == "D1")

    assert lane["evidence_state"] == "PRESENT"
    assert lane["authority_state"] == "ACTIVE_PUBLISHED"
    assert lane["consumption_available"] is True
    assert lane["servable"] is True
    assert lane["automation_eligible"] is False
    assert lane["required_operator_action"] == "COMPLETE_PROVIDER_SETUP"
    assert lane["reason_codes"] == ["PROVIDER_SETUP_REQUIRED"]
    assert "D1" in fdx["active_timeframes"]
    assert "D1" in fdx["servable_timeframes"]
    assert "D1" not in fdx["blocked_timeframes"]


def test_fdx_provider_recovery_preserves_evidence_and_queues_one_update(tmp_path: Path) -> None:
    database, journal = _legacy_fdx(tmp_path)
    before_registration, before_evidence = _registration_and_evidence(database)
    candidate = _fdx_candidate(database)
    assert (candidate.provider_id, candidate.provider_symbol, candidate.timeframe) == (
        "YAHOO_FINANCE", "FDX", "D1"
    )

    receipt = register_provider_aware_instrument(
        database, candidate, registered_at_utc=NOW.isoformat()
    )
    after_registration, after_evidence = _registration_and_evidence(database)
    mapping = representation_mapping(database, "YAHOO_FINANCE", "FDX")
    queue = [
        item for item in SchedulerJournal(database, journal).data["acquisition_queue"]
        if item.get("lane") == "FDX:D1"
    ]

    assert receipt["outcome"] == "PROVIDER_SETUP_COMPLETED"
    assert before_registration == after_registration
    assert before_evidence == after_evidence
    assert mapping is not None and mapping["provider_symbol"] == "FDX"
    assert mapping["status"] == "OPERATOR_RESOLVED"
    assert receipt["scheduler_reconciliation"]["outcome"] == "UPDATE_QUEUED"
    assert len(queue) == 1
    assert queue[0]["selected_provider"] == "YAHOO_FINANCE"
    assert queue[0]["missing_range"]["start"] >= "2026-07-13"
    assert queue[0]["missing_range"]["end"] <= "2026-07-15"

    revision = load_provider_facts(database)["revision"]
    replay = register_provider_aware_instrument(
        database, candidate, registered_at_utc="2026-07-16T03:01:00+00:00"
    )
    queue_after_replay = [
        item for item in SchedulerJournal(database, journal).data["acquisition_queue"]
        if item.get("lane") == "FDX:D1"
    ]
    assert replay["outcome"] == "PROVIDER_SETUP_COMPLETED"
    assert load_provider_facts(database)["revision"] == revision
    assert len(queue_after_replay) == 1


def test_failed_legacy_mapping_write_leaves_the_lane_unchanged(tmp_path: Path) -> None:
    database, _ = _legacy_fdx(tmp_path)
    before_registration, before_evidence = _registration_and_evidence(database)
    candidate = _fdx_candidate(database)
    original_facts = provider_facts_path(database).read_bytes()

    with pytest.raises(OSError, match="not writable"):
        register_provider_aware_instrument(
            database, candidate, registered_at_utc=NOW.isoformat(),
            mapping_writer=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("not writable")),
        )

    assert _registration_and_evidence(database) == (before_registration, before_evidence)
    assert provider_facts_path(database).read_bytes() == original_facts
    assert representation_mapping(database, "YAHOO_FINANCE", "FDX") is None
