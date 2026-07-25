from __future__ import annotations

import base64
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from fragarach_ii.acquisition_orchestrator import acquisition_capability_projection
from fragarach_ii.estate_truth_service import estate_truth_state
from fragarach_ii.external_consumer_service import HistoryService
from fragarach_ii.market_discovery import discover_market
import fragarach_ii.market_discovery as market_discovery
from fragarach_ii.lane_update_register import LaneUpdateRegister
from fragarach_ii.onboarding import register_provider_aware_instrument
from fragarach_ii.provider_facts import load_provider_facts, provider_facts_path, representation_mapping, save_provider_facts
from fragarach_ii.providers.instrument_search import candidate_from_dict
import fragarach_ii.scheduler_service as scheduler_service
from fragarach_ii.storage import RegistrationError, initialize_database, open_read_only, register_instrument
import fragarach_ii.commands.register_instrument as register_command


def _plan(database, symbol):
    market = discover_market(database, symbol)["markets"][0]
    representation = next(item for item in market["representations"] if item["symbol"] == symbol)
    assert representation["registration_plan"] is not None
    candidate = json.loads(base64.urlsafe_b64decode(representation["registration_plan"]["candidate"]))
    return market, candidate_from_dict(candidate)


def _cat_plan(database):
    return _plan(database, "CAT")


def _registration(database, symbol="CAT"):
    with open_read_only(database) as connection:
        row = connection.execute(
            """SELECT identity_json,identity_checksum_sha256,registered_at_utc,registration_status
                 FROM instrument_registrations WHERE asset=? AND timeframe='D1'""",
            (symbol,),
        ).fetchone()
        count = connection.execute(
            "SELECT count(*) FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
            (symbol,),
        ).fetchone()[0]
    return row, count


def _registration_count(database, symbol):
    with open_read_only(database) as connection:
        return connection.execute(
            "SELECT count(*) FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
            (symbol,),
        ).fetchone()[0]


def test_de_discover_approval_add_commissions_d1_and_defers_stock_intraday(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    market, candidate = _plan(database, "DE")
    representation = next(item for item in market["representations"] if item["symbol"] == "DE")
    discovery_mapping = market["provider_discovery"][0]
    d1_lane = next(item for item in representation["timeframe_lanes"] if item["timeframe"] == "D1")

    assert market["underlying_market"] == "DEERE & CO"
    assert discovery_mapping["provider"] == "YAHOO_FINANCE"
    assert discovery_mapping["known_symbol"] == "DE"
    assert discovery_mapping["availability"] == "REVIEW_REQUIRED"
    assert representation["provider_mapping_status"] == "REVIEW_REQUIRED"
    assert d1_lane["provider_mapping"] == "REVIEW_REQUIRED"
    assert d1_lane["acquisition_readiness"] == "REVIEW_REQUIRED"
    assert candidate.provider_id == "YAHOO_FINANCE"
    assert candidate.provider_symbol == "DE"

    receipt = register_provider_aware_instrument(
        database, candidate, registered_at_utc="2026-07-17T00:00:00+00:00"
    )
    row, count = _registration(database, "DE")
    mapping = representation_mapping(database, "YAHOO_FINANCE", "DE")
    state = estate_truth_state(database)
    capability = next(item for item in state["timeframe_capabilities"] if item["symbol"] == "DE")
    d1 = next(item for item in capability["timeframes"] if item["timeframe"] == "D1")
    commissioning = next(item for item in state["commissioning_matrix"] if item["symbol"] == "DE" and item["timeframe"] == "D1")
    replay = register_provider_aware_instrument(
        database, candidate, registered_at_utc="2026-07-17T00:01:00+00:00"
    )

    assert receipt["outcome"] == "INSERTED"
    assert receipt["symbol"] == "DE"
    assert receipt["canonical_identity"] == "REGISTRY:equity:us:sec-cik-315189"
    assert receipt["representation"] == "DE"
    assert receipt["provider"] == "YAHOO_FINANCE"
    assert receipt["provider_symbol"] == "DE"
    assert receipt["mapping_status"] == "APPROVED_REPRESENTATION"
    assert receipt["registration_event"] == "INSERTED"
    assert receipt["commissioned_timeframes"] == ["D1"]
    assert receipt["operator_action"] == "APPROVE_PROVIDER_MAPPING_AND_ADD"
    assert receipt["timestamp"] == "2026-07-17T00:00:00+00:00"
    assert count == 1
    assert json.loads(row[0])["provider_symbol"] == "DE"
    assert mapping["status"] == "OPERATOR_RESOLVED"
    assert mapping["mapping_class"] == "EXACT_REPRESENTATION"
    assert d1["authority_state"] == "REGISTERED_ACQUIRING_HISTORY"
    assert d1["required_operator_action"] is None
    assert receipt["scheduler_reconciliation"]["queued_timeframes"] == ["D1"]
    assert d1["initial_fetch_eligible"] is True
    assert d1["provider_mapping_state"] == "EXACT_REPRESENTATION"
    assert d1["provider"] == "YAHOO_FINANCE"
    assert d1["provider_symbol"] == "DE"
    assert commissioning["commissioned"] is True
    assert capability["intentionally_deferred_timeframes"] == ["H1", "M30", "M5"]
    assert replay["outcome"] == "EXISTING_IDENTICAL"
    assert replay["registration_count"] == 1


def test_fx_estate_admission_auto_commissions_and_queues_enabled_timeframes(tmp_path, monkeypatch):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    _, candidate = _plan(database, "GBPAUD")
    candidate = replace(
        candidate,
        provider_id="TWELVE_DATA",
        provider_contract="TWELVE_DATA_TIME_SERIES_D1_V1",
        provider_symbol="GBP/AUD",
        provider_instrument_type="Physical Currency",
    )
    monkeypatch.setattr(scheduler_service, "credential_map", lambda _value=None: {"TWELVE_DATA": "fixture"})

    receipt = register_provider_aware_instrument(
        database, candidate, registered_at_utc="2026-07-17T00:00:00+00:00"
    )

    assert receipt["commissioned_timeframes"] == ["D1", "H1", "M30", "M5"]
    assert receipt["commissioning_skips"] == []
    assert receipt["scheduler_reconciliation"]["queued_timeframes"] == ["D1", "H1", "M30", "M5"]
    registered_timeframes = {
        row["timeframe"] for row in LaneUpdateRegister(database).rows()
        if row["asset"] == "GBPAUD"
    }
    assert registered_timeframes == {"D1", "H1", "M30", "M5"}


def test_unmapped_fx_registers_for_provider_discovery_but_never_opens_stock_bypass(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    _, eurnzd = _plan(database, "EURNZD")
    _, stock = _plan(database, "CAT")

    receipt = register_provider_aware_instrument(
        database, eurnzd, registered_at_utc="2026-07-18T00:00:00+00:00",
        exact_fx_mapping_resolver=lambda *_args, **_kwargs: None,
    )

    assert receipt["registration_status"] == "REGISTERED_UNMAPPED"
    assert receipt["provider_setup_status"] == "MAPPING_DISCOVERY_PENDING"
    assert receipt["mapping_status"] == "MAPPING_REQUIRED"
    assert receipt["commissioned_timeframes"] == ["D1"]
    assert receipt["scheduler_reconciliation"]["queued_timeframes"] == []
    capability = next(
        item for item in estate_truth_state(database)["timeframe_capabilities"]
        if item["symbol"] == "EURNZD"
    )
    d1 = next(item for item in capability["timeframes"] if item["timeframe"] == "D1")
    assert d1["authority_state"] == "REGISTERED_NO_EVIDENCE"
    assert d1["evidence_state"] == "NO_EVIDENCE"
    assert d1["provider"] is None
    assert d1["initial_fetch_eligible"] is False
    assert d1["required_operator_action"] == "WAIT_FOR_PROVIDER_MAPPING_DISCOVERY"
    assert d1["reason_codes"] == ["MAPPING_DISCOVERY_PENDING"]
    # The mapping is representation-scoped: an intraday provider's own
    # timeframe limitation must not turn the same unresolved FX mapping into
    # a failed registration state on the remaining lanes.
    assert all(
        item["authority_state"] == "REGISTERED_NO_EVIDENCE"
        and item["provider"] is None
        and item["reason_codes"] == ["MAPPING_DISCOVERY_PENDING"]
        for item in capability["timeframes"]
    )
    with pytest.raises(RegistrationError) as rejected:
        register_provider_aware_instrument(
            database,
            replace(
                stock,
                provider_id=None,
                provider_contract=None,
                provider_symbol=None,
                provider_instrument_type=None,
            ),
            registered_at_utc="2026-07-18T00:00:00+00:00",
        )
    assert rejected.value.code == "REVIEWED_PROVIDER_REPRESENTATION_REQUIRED"


def test_exact_fx_reference_mapping_is_admitted_and_queued_without_a_second_operator_step(tmp_path, monkeypatch):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    _, eurnzd = _plan(database, "EURNZD")
    monkeypatch.setattr(scheduler_service, "credential_map", lambda _value=None: {"TWELVE_DATA": "fixture"})

    resolved = {
        "canonical_symbol": "EURNZD", "provider": "TWELVE_DATA",
        "provider_symbol": "EUR/NZD", "provider_instrument_type": "Physical Currency",
        "mapping_class": "EXACT_REPRESENTATION", "status": "RESOLVED_AUTOMATICALLY",
        "timeframe_capabilities": {
            lane: {"supported": True} for lane in ("D1", "H1", "M30", "M5")
        },
    }
    def resolve_and_record(*_args, **_kwargs):
        facts = load_provider_facts(database)
        facts["mappings"]["TWELVE_DATA:EURNZD"] = resolved
        save_provider_facts(database, facts)
        return resolved

    receipt = register_provider_aware_instrument(
        database, eurnzd, registered_at_utc="2026-07-18T00:00:00+00:00",
        exact_fx_mapping_resolver=resolve_and_record,
    )

    mapping = representation_mapping(database, "TWELVE_DATA", "EURNZD")
    assert receipt["registration_status"] == "REGISTERED_NO_EVIDENCE"
    assert receipt["provider"] == "TWELVE_DATA"
    assert receipt["provider_symbol"] == "EUR/NZD"
    assert receipt["commissioned_timeframes"] == ["D1", "H1", "M30", "M5"]
    assert receipt["scheduler_reconciliation"]["queued_timeframes"] == ["D1", "H1", "M30", "M5"]
    assert mapping is not None
    assert mapping["status"] == "RESOLVED_AUTOMATICALLY"
    assert mapping["mapping_class"] == "EXACT_REPRESENTATION"


def test_catalogue_verified_exact_crypto_auto_commissions_all_required_lanes(tmp_path, monkeypatch):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    monkeypatch.setattr(
        market_discovery,
        "_twelve_data_crypto_catalogue_mapping",
        lambda record: {
            "provider": "TWELVE_DATA",
            "provider_symbol": "DOGE/USD",
            "provider_instrument_type": "Digital Currency",
            "catalogue_verified": True,
        } if record["canonical_symbol"] == "DOGEUSD" else None,
    )
    representation = discover_market(
        database, "DOGEUSD", resolve_crypto_catalogue=True
    )["markets"][0]["representations"][0]
    candidate = candidate_from_dict(json.loads(base64.urlsafe_b64decode(
        representation["registration_plan"]["candidate"]
    )))
    monkeypatch.setattr(
        scheduler_service, "credential_map", lambda _value=None: {"TWELVE_DATA": "fixture"}
    )

    receipt = register_provider_aware_instrument(
        database, candidate, registered_at_utc="2026-07-18T00:00:00+00:00"
    )
    projection = acquisition_capability_projection(database, symbol="DOGEUSD")
    rows = [
        item for item in projection["rows"]
        if item["provider"] == "TWELVE_DATA" and item["eligibility"] == "ELIGIBLE"
    ]

    assert receipt["commissioned_timeframes"] == ["D1", "H1", "M30", "M5"]
    assert receipt["scheduler_reconciliation"]["queued_timeframes"] == ["D1", "H1", "M30", "M5"]
    assert {item["timeframe"] for item in rows} == {"D1", "H1", "M30", "M5"}
    assert all(item["mapping_class"] == "EXACT_REPRESENTATION" for item in rows)


def test_estate_admission_supersedes_only_legacy_uncommissioned_required_set_job(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    journal = scheduler_service.SchedulerJournal(database)
    legacy_job = {
        "id": "required-set-legacy-bnb",
        "symbol": "BNBUSD",
        "status": "RUNNING",
        "plan": {"lanes": [{"timeframe": "M5", "commissioned": False}]},
    }
    journal.data["required_set_active_job"] = legacy_job
    journal.data["required_set_jobs"] = [legacy_job]
    journal.save()

    superseded = scheduler_service._supersede_legacy_required_set_job(
        database,
        journal_path=journal.path,
        symbol="BNBUSD",
        current_plan={"lanes": [{"timeframe": "M5", "commissioned": True}]},
        observed=datetime(2026, 7, 18, tzinfo=UTC),
    )
    updated = scheduler_service.SchedulerJournal(database, journal.path)

    assert superseded is True
    assert "required_set_active_job" not in updated.data
    assert updated.data["required_set_jobs"][0]["status"] == "SUPERSEDED"
    assert updated.data["required_set_jobs"][0]["superseded_by"] == "ESTATE_ADMISSION_AUTOMATION"


def test_estate_admission_preserves_current_required_set_transaction(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    journal = scheduler_service.SchedulerJournal(database)
    current_job = {
        "id": "required-set-current-bnb",
        "symbol": "BNBUSD",
        "status": "RUNNING",
        "plan": {"lanes": [{"timeframe": "M5", "commissioned": True}]},
    }
    journal.data["required_set_active_job"] = current_job
    journal.data["required_set_jobs"] = [current_job]
    journal.save()

    superseded = scheduler_service._supersede_legacy_required_set_job(
        database,
        journal_path=journal.path,
        symbol="BNBUSD",
        current_plan={"lanes": [{"timeframe": "M5", "commissioned": True}]},
        observed=datetime(2026, 7, 18, tzinfo=UTC),
    )
    updated = scheduler_service.SchedulerJournal(database, journal.path)

    assert superseded is False
    assert updated.data["required_set_active_job"]["id"] == "required-set-current-bnb"


def test_bhp_asx_and_nyse_onboarding_are_representation_scoped_and_idempotent(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    asx_market, asx_candidate = _plan(database, "ASX:BHP")
    nyse_market, nyse_candidate = _plan(database, "NYSE:BHP")

    asx_rep = next(item for item in asx_market["representations"] if item["symbol"] == "ASX:BHP")
    nyse_rep = next(item for item in nyse_market["representations"] if item["symbol"] == "NYSE:BHP")
    asx_mapping = next(item for item in asx_market["provider_discovery"] if item["representation_symbol"] == "ASX:BHP")
    nyse_mapping = next(item for item in nyse_market["provider_discovery"] if item["representation_symbol"] == "NYSE:BHP")

    assert asx_mapping["provider"] == nyse_mapping["provider"] == "YAHOO_FINANCE"
    assert asx_mapping["known_symbol"] == "BHP.AX"
    assert nyse_mapping["known_symbol"] == "BHP"
    assert asx_candidate.asset == "ASXBHP"
    assert asx_candidate.selected_representation == "ASX:BHP"
    assert asx_candidate.provider_symbol == "BHP.AX"
    assert asx_candidate.calendar_id == "AUSTRALIAN_EQUITIES_D1_V1"
    assert nyse_candidate.asset == "NYSEBHP"
    assert nyse_candidate.selected_representation == "NYSE:BHP"
    assert nyse_candidate.provider_symbol == "BHP"
    assert nyse_candidate.calendar_id == "US_EQUITIES_D1_V1"
    assert nyse_rep["representation_type"] == "DEPOSITARY_RECEIPT"
    assert all(item["provider_mapping_status"] == "REVIEW_REQUIRED" for item in (asx_rep, nyse_rep))

    asx_receipt = register_provider_aware_instrument(
        database, asx_candidate, registered_at_utc="2026-07-17T00:00:00+00:00"
    )
    asx_replay = register_provider_aware_instrument(
        database, asx_candidate, registered_at_utc="2026-07-17T00:01:00+00:00"
    )
    state_after_asx = estate_truth_state(database)
    asx_capability = next(item for item in state_after_asx["timeframe_capabilities"] if item["symbol"] == "ASXBHP")
    asx_d1 = next(item for item in asx_capability["timeframes"] if item["timeframe"] == "D1")

    assert asx_receipt["outcome"] == "INSERTED"
    assert asx_receipt["canonical_identity"] == "COMPANY:BHP:ASX"
    assert asx_receipt["representation"] == "ASX:BHP"
    assert asx_receipt["provider"] == "YAHOO_FINANCE"
    assert asx_receipt["provider_symbol"] == "BHP.AX"
    assert asx_receipt["mapping_status"] == "APPROVED_REPRESENTATION"
    assert asx_receipt["registration_event"] == "INSERTED"
    assert asx_receipt["commissioned_timeframes"] == ["D1"]
    assert asx_receipt["operator_action"] == "APPROVE_PROVIDER_MAPPING_AND_ADD"
    assert asx_receipt["timestamp"] == "2026-07-17T00:00:00+00:00"
    assert asx_replay["outcome"] == "EXISTING_IDENTICAL"
    assert _registration_count(database, "ASXBHP") == 1
    assert _registration_count(database, "NYSEBHP") == 0
    assert representation_mapping(database, "YAHOO_FINANCE", "ASXBHP")["provider_symbol"] == "BHP.AX"
    assert representation_mapping(database, "YAHOO_FINANCE", "NYSEBHP") is None
    assert asx_d1["provider"] == "YAHOO_FINANCE"
    assert asx_d1["provider_symbol"] == "BHP.AX"
    assert asx_d1["initial_fetch_eligible"] is True
    assert asx_capability["intentionally_deferred_timeframes"] == ["H1", "M30", "M5"]

    refreshed = discover_market(database, "BHP")
    refreshed_asx = next(m for m in refreshed["markets"] if m["canonical_identity"] == "COMPANY:BHP:ASX")
    refreshed_nyse = next(m for m in refreshed["markets"] if m["canonical_identity"] == "COMPANY:BHP:NYSE")
    assert refreshed_asx["representations"][0]["registration_status"] == "REGISTERED_NO_EVIDENCE"
    assert refreshed_nyse["representations"][0]["registration_status"] == "NOT_REGISTERED"

    nyse_receipt = register_provider_aware_instrument(
        database, nyse_candidate, registered_at_utc="2026-07-17T00:02:00+00:00"
    )
    nyse_replay = register_provider_aware_instrument(
        database, nyse_candidate, registered_at_utc="2026-07-17T00:03:00+00:00"
    )
    state_after_nyse = estate_truth_state(database)
    nyse_capability = next(item for item in state_after_nyse["timeframe_capabilities"] if item["symbol"] == "NYSEBHP")
    nyse_d1 = next(item for item in nyse_capability["timeframes"] if item["timeframe"] == "D1")

    assert nyse_receipt["outcome"] == "INSERTED"
    assert nyse_receipt["canonical_identity"] == "COMPANY:BHP:NYSE"
    assert nyse_receipt["representation"] == "NYSE:BHP"
    assert nyse_receipt["provider_symbol"] == "BHP"
    assert nyse_receipt["commissioned_timeframes"] == ["D1"]
    assert nyse_replay["outcome"] == "EXISTING_IDENTICAL"
    assert _registration_count(database, "ASXBHP") == 1
    assert _registration_count(database, "NYSEBHP") == 1
    assert representation_mapping(database, "YAHOO_FINANCE", "ASXBHP")["provider_symbol"] == "BHP.AX"
    assert representation_mapping(database, "YAHOO_FINANCE", "NYSEBHP")["provider_symbol"] == "BHP"
    assert nyse_d1["provider"] == "YAHOO_FINANCE"
    assert nyse_d1["provider_symbol"] == "BHP"
    assert nyse_d1["initial_fetch_eligible"] is True
    assert nyse_capability["intentionally_deferred_timeframes"] == ["H1", "M30", "M5"]


def test_asx_cba_registered_without_publication_remains_recoverable_visible(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    market, candidate = _plan(database, "ASX:CBA")

    assert market["underlying_market"] == "Commonwealth Bank"
    assert candidate.asset == "ASXCBA"
    assert candidate.selected_representation == "ASX:CBA"
    assert candidate.provider_id == "YAHOO_FINANCE"
    assert candidate.provider_symbol == "CBA.AX"

    receipt = register_provider_aware_instrument(
        database, candidate, registered_at_utc="2026-07-17T02:00:00+00:00"
    )
    assert receipt["outcome"] == "INSERTED"

    refreshed = discover_market(database, "CBA")["markets"][0]
    representation = refreshed["representations"][0]
    assert representation["registration_status"] == "REGISTERED_NO_EVIDENCE"
    assert representation["acquisition_readiness"] == "OPEN_EXISTING"

    state = estate_truth_state(database)
    cba = next(item for item in state["truth_matrix"] if item["symbol"] == "ASXCBA")
    cba_capability = next(item for item in state["timeframe_capabilities"] if item["symbol"] == "ASXCBA")
    cba_d1 = next(item for item in cba_capability["timeframes"] if item["timeframe"] == "D1")
    catalogue_symbol = next(item for item in HistoryService(database).get_catalogue()["symbols"] if item["symbol"] == "ASXCBA")

    assert cba["publication_state"] == "REGISTERED_ACQUIRING_HISTORY"
    assert cba["truth_state"]["coverage"]["row_count"] == 0
    assert cba["truth_state"]["authority_state"] == "AMBER"
    assert cba["search_metadata"]["asset_class"] == "AUSTRALIAN_EQUITIES"
    assert cba_d1["authority_state"] == "REGISTERED_ACQUIRING_HISTORY"
    assert cba_d1["required_operator_action"] is None
    assert catalogue_symbol["availability"] == "UNAVAILABLE"
    assert catalogue_symbol["histories"][0]["governed"] is False
    assert catalogue_symbol["histories"][0]["bar_count"] == 0

    Path(f"{database}.scheduler.json").write_text(
        json.dumps({
            "contract": "fragarach_ii.scheduler_journal.v4",
            "lanes": {
                "ASXCBA:D1": {
                    "result": "FAILED",
                    "reason": "CANONICAL_UNCHANGED",
                    "last_operator_fetch_result": {
                        "outcome": "FAILED",
                        "reason": "CANONICAL_UNCHANGED",
                    },
                }
            },
            "manual_requests": [],
            "acquisition_queue": [],
        }),
        encoding="utf-8",
    )

    failed_state = estate_truth_state(database)
    failed_cba = next(item for item in failed_state["truth_matrix"] if item["symbol"] == "ASXCBA")
    failed_capability = next(item for item in failed_state["timeframe_capabilities"] if item["symbol"] == "ASXCBA")
    failed_d1 = next(item for item in failed_capability["timeframes"] if item["timeframe"] == "D1")

    assert failed_cba["publication_state"] == "REGISTERED_FAILED_RECOVERABLE"
    assert failed_cba["truth_state"]["authority_state"] == "RED"
    assert failed_d1["authority_state"] == "REGISTERED_FAILED_RECOVERABLE"
    assert failed_d1["required_operator_action"] == "RESUME_INITIAL_HISTORY"


def test_lse_rio_onboarding_uses_suffix_mapping_and_only_selected_representation(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    lse_market, lse_candidate = _plan(database, "LSE:RIO")
    nyse_market, nyse_candidate = _plan(database, "NYSE:RIO")
    asx_market, asx_candidate = _plan(database, "ASX:RIO")

    lse_mapping = next(item for item in lse_market["provider_discovery"] if item["representation_symbol"] == "LSE:RIO")
    nyse_mapping = next(item for item in nyse_market["provider_discovery"] if item["representation_symbol"] == "NYSE:RIO")
    asx_mapping = next(item for item in asx_market["provider_discovery"] if item["representation_symbol"] == "ASX:RIO")

    assert lse_mapping["known_symbol"] == "RIO.L"
    assert nyse_mapping["known_symbol"] == "RIO"
    assert asx_mapping["known_symbol"] == "RIO.AX"
    assert lse_candidate.asset == "LSERIO"
    assert lse_candidate.selected_representation == "LSE:RIO"
    assert lse_candidate.provider_symbol == "RIO.L"
    assert lse_candidate.calendar_id == "UK_EQUITIES_D1_V1"
    assert nyse_candidate.asset == "NYSERIO"
    assert nyse_candidate.provider_symbol == "RIO"
    assert asx_candidate.asset == "ASXRIO"
    assert asx_candidate.provider_symbol == "RIO.AX"

    receipt = register_provider_aware_instrument(
        database, lse_candidate, registered_at_utc="2026-07-17T01:00:00+00:00"
    )
    replay = register_provider_aware_instrument(
        database, lse_candidate, registered_at_utc="2026-07-17T01:01:00+00:00"
    )
    state = estate_truth_state(database)
    capability = next(item for item in state["timeframe_capabilities"] if item["symbol"] == "LSERIO")
    d1 = next(item for item in capability["timeframes"] if item["timeframe"] == "D1")

    assert receipt["outcome"] == "INSERTED"
    assert receipt["canonical_identity"] == "COMPANY:RIO:LSE"
    assert receipt["representation"] == "LSE:RIO"
    assert receipt["provider"] == "YAHOO_FINANCE"
    assert receipt["provider_symbol"] == "RIO.L"
    assert receipt["commissioned_timeframes"] == ["D1"]
    assert replay["outcome"] == "EXISTING_IDENTICAL"
    assert _registration_count(database, "LSERIO") == 1
    assert _registration_count(database, "NYSERIO") == 0
    assert _registration_count(database, "ASXRIO") == 0
    assert representation_mapping(database, "YAHOO_FINANCE", "LSERIO")["provider_symbol"] == "RIO.L"
    assert representation_mapping(database, "YAHOO_FINANCE", "NYSERIO") is None
    assert representation_mapping(database, "YAHOO_FINANCE", "ASXRIO") is None
    assert d1["provider"] == "YAHOO_FINANCE"
    assert d1["provider_symbol"] == "RIO.L"
    assert d1["initial_fetch_eligible"] is True
    assert capability["intentionally_deferred_timeframes"] == ["H1", "M30", "M5"]


def test_reviewed_cat_onboarding_is_atomic_visible_and_idempotent(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    market, candidate = _cat_plan(database)
    assert market["available_actions"] == ("ADD_TO_FRAGARACH",)
    assert candidate.provider_id == "YAHOO_FINANCE"
    assert candidate.provider_symbol == "CAT"

    receipt = register_provider_aware_instrument(
        database, candidate, registered_at_utc="2026-07-16T03:00:00+00:00"
    )
    row, count = _registration(database)
    mapping = representation_mapping(database, "YAHOO_FINANCE", "CAT")
    capability = acquisition_capability_projection(database, symbol="CAT", timeframe="D1")
    yahoo = next(item for item in capability["rows"] if item["provider"] == "YAHOO_FINANCE")

    assert receipt["outcome"] == "INSERTED"
    assert receipt["provider_setup_status"] == "COMPLETE"
    assert receipt["registration_count"] == count == 1
    assert json.loads(row[0])["provider_symbol"] == "CAT"
    assert mapping["provider_symbol"] == "CAT"
    assert mapping["mapping_class"] == "EXACT_REPRESENTATION"
    assert yahoo["mapping_status"] == "EXACT_REPRESENTATION"
    assert yahoo["eligibility"] == "ELIGIBLE"

    revision = load_provider_facts(database)["revision"]
    replay = register_provider_aware_instrument(
        database, candidate, registered_at_utc="2026-07-16T03:01:00+00:00"
    )
    assert replay["outcome"] == "EXISTING_IDENTICAL"
    assert replay["registration_count"] == 1
    assert load_provider_facts(database)["revision"] == revision


def test_existing_unmapped_cat_completes_without_recreation(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    _, mapped_candidate = _cat_plan(database)
    values = {name: getattr(mapped_candidate, name) for name in mapped_candidate.__dataclass_fields__}
    values.update(
        provider_id=None,
        provider_contract=None,
        provider_symbol=None,
        provider_instrument_type=None,
        provider_exchange=None,
        provider_country=None,
    )
    unmapped_candidate = type(mapped_candidate)(**values)
    register_instrument(
        database, unmapped_candidate, registered_at_utc="2026-07-16T02:18:01.950622+00:00"
    )
    before, before_count = _registration(database)

    incomplete, completion_candidate = _cat_plan(database)
    assert incomplete["acquisition_readiness"] == "PROVIDER_SETUP_INCOMPLETE"
    assert incomplete["available_actions"] == ("COMPLETE_PROVIDER_SETUP",)

    receipt = register_provider_aware_instrument(
        database, completion_candidate, registered_at_utc="2026-07-16T03:00:00+00:00"
    )
    after, after_count = _registration(database)
    repaired = discover_market(database, "CAT")["markets"][0]

    assert receipt["outcome"] == "PROVIDER_SETUP_COMPLETED"
    assert before_count == after_count == 1
    assert after == before
    assert repaired["acquisition_readiness"] == "OPEN_EXISTING"
    assert repaired["available_actions"] == ("OPEN_EXISTING",)
    assert representation_mapping(database, "YAHOO_FINANCE", "CAT")["provider_symbol"] == "CAT"


def test_failed_mapping_write_leaves_no_registration_or_provider_fact(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    _, candidate = _cat_plan(database)

    def fail_mapping(*args, **kwargs):
        raise OSError("provider facts not writable")

    with pytest.raises(OSError, match="not writable"):
        register_provider_aware_instrument(
            database,
            candidate,
            registered_at_utc=datetime.now(UTC).isoformat(),
            mapping_writer=fail_mapping,
        )
    row, count = _registration(database)
    assert row is None and count == 0
    assert representation_mapping(database, "YAHOO_FINANCE", "CAT") is None


def test_failed_registration_rolls_back_provider_fact(tmp_path, monkeypatch):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    _, candidate = _cat_plan(database)
    original = provider_facts_path(database).read_bytes() if provider_facts_path(database).exists() else None

    def fail_registration(*args, **kwargs):
        raise RegistrationError("REGISTRATION_NOT_WRITABLE", "fixture")

    monkeypatch.setattr("fragarach_ii.onboarding.register_instrument", fail_registration)
    with pytest.raises(RegistrationError, match="fixture"):
        register_provider_aware_instrument(
            database, candidate, registered_at_utc="2026-07-16T03:00:00+00:00"
        )

    row, count = _registration(database)
    assert row is None and count == 0
    path = provider_facts_path(database)
    assert (path.read_bytes() if path.exists() else None) == original
    assert representation_mapping(database, "YAHOO_FINANCE", "CAT") is None


def test_unreviewed_registration_is_rejected_without_orphan(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    _, mapped_candidate = _cat_plan(database)
    values = {name: getattr(mapped_candidate, name) for name in mapped_candidate.__dataclass_fields__}
    values.update(
        provider_id=None,
        provider_contract=None,
        provider_symbol=None,
        provider_instrument_type=None,
    )

    with pytest.raises(RegistrationError) as failure:
        register_provider_aware_instrument(
            database,
            type(mapped_candidate)(**values),
            registered_at_utc="2026-07-16T03:00:00+00:00",
        )
    row, count = _registration(database)
    assert failure.value.code == "REVIEWED_PROVIDER_REPRESENTATION_REQUIRED"
    assert row is None and count == 0
    assert representation_mapping(database, "YAHOO_FINANCE", "CAT") is None


def test_registration_notifies_live_scheduler_to_refresh_and_drain_queue(tmp_path, monkeypatch):
    socket = tmp_path / "scheduler.socket"
    socket.touch()
    commands: list[str] = []

    monkeypatch.setattr(
        register_command.ServicePaths,
        "create",
        staticmethod(lambda _database: SimpleNamespace(socket=socket)),
    )
    monkeypatch.setattr(
        register_command,
        "send_service_request",
        lambda _paths, command, timeout: commands.append(command["command_type"]),
    )

    register_command._notify_scheduler(tmp_path / "authority.sqlite3")

    assert commands == ["PROVIDER_FACT_REFRESH", "RUN_QUEUE_NOW"]
