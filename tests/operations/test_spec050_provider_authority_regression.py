from __future__ import annotations

import base64
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import create_manual_request
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.provider_facts import (
    load_provider_facts,
    representation_mapping,
    resolve_twelve_data_facts,
)
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.scheduler_service import SchedulerJournal, reconcile_manual_requests
from fragarach_ii.storage import (
    initialize_database,
    register_instrument,
    registered_writer,
    transaction,
)
NOW = datetime(2026, 7, 15, 0, 2, tzinfo=UTC)
TARGET_LANES = (("AUDCAD", "M5"), ("AUDCAD", "M30"), ("AUDJPY", "H1"))


def _register_unmapped_with_confirmed_d1_mapping(database: Path, symbol: str) -> None:
    initialize_database(database)
    plan = discover_market(database, symbol)["markets"][0]["representations"][0]["registration_plan"]
    candidate = json.loads(base64.urlsafe_b64decode(plan["candidate"]))
    register_instrument(
        database, candidate_from_dict(candidate), registered_at_utc=NOW.isoformat()
    )
    with registered_writer(database) as connection:
        with transaction(connection):
            for timeframe in ("M5", "M30", "H1", "D1"):
                connection.execute(
                    """INSERT INTO ingest_runs
                       (ingest_run_id,kind,status,started_at_utc,finished_at_utc,detail)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        f"prior-{symbol.lower()}-{timeframe.lower()}",
                        "provider_twelve_data",
                        "committed",
                        NOW.isoformat(),
                        NOW.isoformat(),
                        json.dumps(
                            {
                                "asset": symbol,
                                "timeframe": timeframe,
                                "provider": "TWELVE_DATA",
                                "provider_symbol": f"{symbol[:3]}/{symbol[3:]}",
                                "mapping_class": "EXACT_REPRESENTATION",
                                "mapping_state": "CONFIRMED_BY_VALID_EVIDENCE",
                            },
                            separators=(",", ":"),
                        ),
                    ),
                )


def _legacy_manual_requests(database: Path, journal_path: Path) -> list[str]:
    journal = SchedulerJournal(database, journal_path)
    # This mixed SPEC-047 result is the regression trigger: once any lane needed
    # review, the old resolver discarded every already-proven representation.
    journal.data["spec047_capability_reconciliation"] = {
        "rows": [
            {
                "lane": f"{symbol}:{timeframe}",
                "required_operator_decision": "NONE",
            }
            for symbol, timeframe in TARGET_LANES
        ]
        + [{"lane": "EURUSD:M5", "required_operator_decision": "REVIEW_PROVIDER_MAPPING"}]
    }
    identifiers = []
    for symbol, timeframe in TARGET_LANES:
        request = create_manual_request(
            journal.manual_requests,
            symbol=symbol,
            timeframe=timeframe,
            missing_start="2026-07-14",
            missing_end="2026-07-14",
            expected_edge="2026-07-14T23:00:00+00:00",
            reason="NO_ELIGIBLE_PROVIDER",
            providers_attempted=[],
            failures=[],
            providers_considered=[
                {
                    "provider": "TWELVE_DATA",
                    "eligible": False,
                    "reason": "NO_APPROVED_MAPPING",
                    "provider_symbol": None,
                    "estimated_request_count": 1,
                }
            ],
            provider_fact_revision=0,
            capability_projection_revision="legacy",
            now=NOW,
        )
        identifiers.append(str(request["id"]))
        journal.lane(symbol, timeframe).update(
            result="FAILED", reason="NO_ELIGIBLE_PROVIDER", manual_request=request["id"]
        )
    journal.save()
    return identifiers


def _preserve_legacy_commission(database: Path, symbol: str, timeframe: str) -> None:
    with registered_writer(database) as connection:
        with transaction(connection):
            connection.execute(
                """INSERT INTO evidence_lanes
                   (asset,timeframe,registration_timeframe,lane_contract,
                    lane_contract_version,created_at_utc)
                   VALUES (?,?,'D1','EVIDENCE_LANE_V1',1,?)""",
                (symbol, timeframe, NOW.isoformat()),
            )


def test_proven_fx_authority_migrates_and_restores_affected_manual_lanes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database = root / "authority.sqlite3"
        journal_path = Path(f"{database}.scheduler.json")
        for symbol in ("AUDCAD", "AUDJPY"):
            _register_unmapped_with_confirmed_d1_mapping(database, symbol)
            for timeframe in ("M5", "M30", "H1"):
                _preserve_legacy_commission(database, symbol, timeframe)
        identifiers = _legacy_manual_requests(database, journal_path)

        resolve_twelve_data_facts(
            database,
            credential=None,
            clock=lambda: NOW,
        )

        facts = load_provider_facts(database)
        for symbol in ("AUDCAD", "AUDJPY"):
            mapping = representation_mapping(database, "TWELVE_DATA", symbol)
            assert mapping is not None
            assert mapping["provider_symbol"] == f"{symbol[:3]}/{symbol[3:]}"
            assert mapping["mapping_class"] == "EXACT_REPRESENTATION"
            assert mapping["resolution_evidence"]["prior_approved_mapping"]["source_scope"] == "D1_COMMITTED_EVIDENCE"
            assert set(mapping["timeframe_capabilities"]) == {"M5", "M30", "H1", "D1"}
            assert all(
                capability["supported"]
                for capability in mapping["timeframe_capabilities"].values()
            )
        assert facts["revision"] > 0

        report = reconcile_manual_requests(
            database,
            credential="secret",
            journal_path=journal_path,
            at=NOW,
            trigger="PROVIDER_FACTS_COMMIT",
        )
        assert report["automation_restored"] == len(TARGET_LANES)
        assert report["queue_items_created"] == len(TARGET_LANES)

        journal = SchedulerJournal(database, journal_path)
        restored = [item for item in journal.manual_requests if item["id"] in identifiers]
        assert {item["status"] for item in restored} == {"Archived"}
        assert {item["reconciliation_status"] for item in restored} == {"AUTOMATION_RESTORED"}
        assert all(item["providers_currently_eligible"] == ["TWELVE_DATA"] for item in restored)
        assert all(
            next(
                provider
                for provider in item["providers_considered"]
                if provider["provider"] == "TWELVE_DATA"
            )["reason"]
            is None
            for item in restored
        )
        assert {item["lane"] for item in journal.data["acquisition_queue"]} == {
            f"{symbol}:{timeframe}" for symbol, timeframe in TARGET_LANES
        }
        assert {item["work_class"] for item in journal.data["acquisition_queue"]} == {"QUEUE"}
