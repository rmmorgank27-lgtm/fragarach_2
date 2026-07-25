from __future__ import annotations

import base64
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fragarach_ii.acquisition_orchestrator import create_manual_request
from fragarach_ii.lane_commissioning import ensure_commissioned_lane
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.provider_facts import load_provider_facts, save_provider_facts
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.scheduler_service import (
    SchedulerJournal,
    reconcile_manual_requests,
    scheduler_snapshot,
)
from fragarach_ii.storage import initialize_database, register_instrument
from tests.validation.test_d1_session_validation import _create_lane


NOW = datetime(2026, 7, 14, 10, 2, tzinfo=UTC)
TIMEFRAMES = ("M5", "M30", "H1", "D1")


def _register_audnzd(database: Path) -> None:
    initialize_database(database)
    plan = discover_market(database, "AUDNZD")["markets"][0]["representations"][0]["registration_plan"]
    candidate = json.loads(base64.urlsafe_b64decode(plan["candidate"]))
    candidate.update(
        provider_id="TWELVE_DATA",
        provider_contract="TWELVE_DATA_TIME_SERIES_D1_V1",
        provider_symbol="AUD/NZD",
        provider_instrument_type="Physical Currency",
    )
    register_instrument(
        database, candidate_from_dict(candidate), registered_at_utc=NOW.isoformat()
    )
    for timeframe in TIMEFRAMES[:-1]:
        ensure_commissioned_lane(database, "AUDNZD", timeframe, observed_at=NOW.isoformat())


def _approve_twelve_data(database: Path) -> int:
    facts = load_provider_facts(database)
    facts["credential_state"] = "Configured"
    facts["updated_at"] = NOW.isoformat()
    facts["mappings"]["TWELVE_DATA:AUDNZD"] = {
        "canonical_symbol": "AUDNZD",
        "canonical_base_asset": "AUD",
        "canonical_quote_asset": "NZD",
        "provider": "TWELVE_DATA",
        "provider_symbol": "AUD/NZD",
        "provider_base_asset": "AUD",
        "provider_quote_asset": "NZD",
        "mapping_class": "EXACT_REPRESENTATION",
        "status": "RESOLVED_AUTOMATICALLY",
        "resolution_method": "PROVIDER_REFERENCE_EXACT_BASE_QUOTE_AND_INSTRUMENT_CLASS",
        "effective_time": NOW.isoformat(),
        "timeframe_capabilities": {
            timeframe: {
                "timeframe": timeframe, "supported": True,
                "reason": "TIMEFRAME_SUPPORTED", "last_verified": NOW.isoformat(),
            }
            for timeframe in TIMEFRAMES
        },
    }
    save_provider_facts(database, facts)
    return int(facts["revision"])


def _stale_requests(database: Path, journal_path: Path) -> list[str]:
    journal = SchedulerJournal(database, journal_path)
    identifiers = []
    for timeframe in TIMEFRAMES:
        request = create_manual_request(
            journal.manual_requests, symbol="AUDNZD", timeframe=timeframe,
            missing_start="2026-07-10", missing_end="2026-07-13",
            expected_edge="2026-07-13T00:00:00+00:00",
            reason="NO_ELIGIBLE_PROVIDER", providers_attempted=[], failures=[],
            providers_considered=[{
                "provider": "TWELVE_DATA", "eligible": False,
                "reason": "NO_APPROVED_MAPPING", "provider_symbol": None,
                "estimated_request_count": 1,
            }],
            provider_fact_revision=0, capability_projection_revision="legacy",
            now=NOW,
        )
        identifiers.append(str(request["id"]))
        journal.lane("AUDNZD", timeframe).update(
            result="FAILED", reason="NO_ELIGIBLE_PROVIDER", manual_request=request["id"]
        )
    journal.save()
    return identifiers


def test_audnzd_current_facts_restore_four_deduplicated_queue_lanes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database, journal_path = root / "authority.sqlite3", root / "scheduler.json"
        _register_audnzd(database)
        identifiers = _stale_requests(database, journal_path)
        canonical_before = database.read_bytes()
        revision = _approve_twelve_data(database)

        report = reconcile_manual_requests(
            database, credential="secret", journal_path=journal_path,
            at=NOW, trigger="PROVIDER_FACTS_COMMIT",
        )
        assert database.read_bytes() == canonical_before
        assert report["requests_examined"] == 4
        assert report["automation_restored"] == 4
        assert report["queue_items_created"] == 4

        journal = SchedulerJournal(database, journal_path)
        restored = [item for item in journal.manual_requests if item["id"] in identifiers]
        assert {item["status"] for item in restored} == {"Archived"}
        assert {item["reconciliation_status"] for item in restored} == {"AUTOMATION_RESTORED"}
        assert all(item["last_evaluated_provider_fact_revision"] == revision for item in restored)
        assert all(item["original_rejection_reasons"][0]["reason"] == "NO_APPROVED_MAPPING" for item in restored)
        assert all(item["providers_currently_eligible"] == ["TWELVE_DATA"] for item in restored)
        assert len(journal.data["acquisition_queue"]) == 4
        assert {item["lane"] for item in journal.data["acquisition_queue"]} == {
            f"AUDNZD:{timeframe}" for timeframe in TIMEFRAMES
        }
        assert {item["work_class"] for item in journal.data["acquisition_queue"]} == {"QUEUE"}

        second = reconcile_manual_requests(
            database, credential="secret", journal_path=journal_path,
            at=NOW, trigger="SCHEDULER_RESTART",
        )
        assert second["automation_restored"] == 0
        assert len(SchedulerJournal(database, journal_path).data["acquisition_queue"]) == 4
        snapshot = scheduler_snapshot(
            database, clock=lambda: NOW, journal_path=journal_path, credential="secret"
        )
        assert snapshot["manual_request_count"] == 0
        assert len(snapshot["manual_request_history"]) == 4


def test_credential_block_is_operational_wait_then_restores_without_duplication() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database, journal_path = root / "authority.sqlite3", root / "scheduler.json"
        _register_audnzd(database)
        _stale_requests(database, journal_path)
        _approve_twelve_data(database)

        first = reconcile_manual_requests(
            database, credential=None, journal_path=journal_path,
            at=NOW, trigger="CREDENTIAL_STATE_CHANGED",
        )
        journal = SchedulerJournal(database, journal_path)
        assert first["temporarily_blocked"] == 4
        assert not [item for item in journal.manual_requests if item["status"] in {"Required", "Acknowledged"}]
        assert {item["operational_state"] for item in journal.data["acquisition_queue"]} == {
            "Credential Repair Required"
        }

        repaired = reconcile_manual_requests(
            database, credential="secret", journal_path=journal_path,
            at=NOW, trigger="CREDENTIAL_REPAIRED",
        )
        journal = SchedulerJournal(database, journal_path)
        assert repaired["automation_restored"] == 4
        assert len(journal.data["acquisition_queue"]) == 4
        assert {item["operational_state"] for item in journal.data["acquisition_queue"]} == {"Ready"}


def test_request_already_satisfied_resolves_without_queue_work() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database, journal_path = root / "authority.sqlite3", root / "scheduler.json"
        _create_lane(database, "AUDUSD", ["2026-07-13"])
        journal = SchedulerJournal(database, journal_path)
        request = create_manual_request(
            journal.manual_requests, symbol="AUDUSD", timeframe="D1",
            missing_start="2026-07-13", missing_end="2026-07-13",
            expected_edge="2026-07-13T00:00:00+00:00", reason="NO_ELIGIBLE_PROVIDER",
            providers_attempted=[], failures=[], now=NOW,
        )
        journal.save()

        report = reconcile_manual_requests(
            database, journal_path=journal_path, at=NOW, trigger="CANONICAL_ADVANCED"
        )
        journal = SchedulerJournal(database, journal_path)
        resolved = next(item for item in journal.manual_requests if item["id"] == request["id"])
        assert report["already_satisfied"] == 1
        assert resolved["status"] == "Resolved"
        assert resolved["reconciliation_status"] == "REQUEST_ALREADY_SATISFIED"
        assert journal.data["acquisition_queue"] == []


def test_stale_provider_fact_writer_cannot_overwrite_newer_authority() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        initialize_database(database)
        first = load_provider_facts(database)
        save_provider_facts(database, first)
        writer_one = load_provider_facts(database)
        writer_two = load_provider_facts(database)
        writer_one["credential_state"] = "Configured"
        save_provider_facts(database, writer_one)
        writer_two["credential_state"] = "Invalid"
        with pytest.raises(RuntimeError, match="STALE_PROVIDER_FACT_REVISION"):
            save_provider_facts(database, writer_two)
        assert load_provider_facts(database)["credential_state"] == "Configured"
