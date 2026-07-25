from __future__ import annotations

import base64
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from fragarach_ii.acquisition_orchestrator import acquisition_capability_projection, load_provider_profiles, mapping_authority
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.provider_facts import (
    load_provider_facts,
    probe_twelve_data_capability,
    provider_facts_path,
    provider_facts_snapshot,
    resolve_twelve_data_facts,
    save_provider_facts,
)
from fragarach_ii.providers.http import HttpResponse
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.scheduler_integrity import active_universe
from fragarach_ii.scheduler_service import _repair_twelve_data_credential_health
from fragarach_ii.storage import RegistrationCandidate, initialize_database, open_read_only, register_instrument


NOW = datetime(2026, 7, 14, 10, 2, tzinfo=UTC)
PAIRS = ("AUDSGD", "EURUSD", "GBPAUD", "GBPJPY", "USDCAD", "USDCHF")


class FactTransport:
    def __init__(self, *, empty_probe: bool = False, failure: Exception | None = None) -> None:
        self.requests = []
        self.empty_probe = empty_probe
        self.failure = failure

    def send(self, request, credential, config):
        self.requests.append(request)
        if self.failure:
            raise self.failure
        query = parse_qs(urlsplit(request.target).query)
        if request.target.startswith("/symbol_search"):
            symbol = query["symbol"][0].replace("/", "").upper()
            row = {
                "symbol": f"{symbol[:3]}/{symbol[3:]}",
                "instrument_name": f"{symbol[:3]} / {symbol[3:]}",
                "instrument_type": "Physical Currency",
                "exchange": "Forex",
                "currency": symbol[3:],
            }
            return HttpResponse(200, "application/json", json.dumps({"data": [row]}).encode(), request.host, (("api-credits-used", "1"), ("api-credits-left", "54")))
        values = [] if self.empty_probe else [
            {"datetime": "2026-07-14 09:50:00", "open": "1", "high": "2", "low": "0.5", "close": "1.5"},
            {"datetime": "2026-07-14 09:55:00", "open": "1.5", "high": "2", "low": "1", "close": "1.8"},
            {"datetime": "2026-07-14 10:00:00", "open": "1.8", "high": "2", "low": "1.5", "close": "1.9"},
        ]
        payload = {"meta": {"symbol": query["symbol"][0], "interval": query["interval"][0], "type": "Physical Currency"}, "values": values, "status": "ok"}
        return HttpResponse(200, "application/json", json.dumps(payload).encode(), request.host, (("api-credits-used", "1"), ("api-credits-left", "53")))


def _register(db: Path, symbol: str, *, approved_mapping: bool = False) -> None:
    initialize_database(db)
    plan = discover_market(db, symbol)["markets"][0]["representations"][0]["registration_plan"]
    candidate = json.loads(base64.urlsafe_b64decode(plan["candidate"]))
    if approved_mapping:
        candidate.update(
            provider_id="TWELVE_DATA",
            provider_contract="TWELVE_DATA_TIME_SERIES_D1_V1",
            provider_symbol=f"{symbol[:3]}/{symbol[3:]}",
            provider_instrument_type="Physical Currency",
        )
    register_instrument(db, candidate_from_dict(candidate), registered_at_utc=NOW.isoformat())


def test_standard_forex_reference_facts_resolve_once_per_representation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        for symbol in PAIRS:
            _register(db, symbol)
        before = db.read_bytes()
        transport = FactTransport()
        snapshot = resolve_twelve_data_facts(
            db, credential="fixture-secret", transport=transport, clock=lambda: NOW, symbols=PAIRS
        )
        assert db.read_bytes() == before
        assert len(snapshot["resolved_automatically"]) == 6
        assert not snapshot["needs_material_review"]
        assert len(transport.requests) == 6
        assert all("apikey" not in request.target.lower() for request in transport.requests)
        for mapping in snapshot["resolved_automatically"]:
            assert mapping["mapping_class"] == "EXACT_REPRESENTATION"
            assert mapping["provider_base_asset"] == mapping["canonical_base_asset"]
            assert mapping["provider_quote_asset"] == mapping["canonical_quote_asset"]
            assert set(mapping["timeframe_capabilities"]) == {"M5", "M30", "H1", "D1"}
            assert all(item["supported"] for item in mapping["timeframe_capabilities"].values())
        raw = provider_facts_path(db).read_text()
        assert "fixture-secret" not in raw

        restart_transport = FactTransport()
        restarted = resolve_twelve_data_facts(
            db, credential="fixture-secret", transport=restart_transport, clock=lambda: NOW
        )
        assert len(restarted["resolved_automatically"]) >= 6
        repeated = {
            parse_qs(urlsplit(request.target).query)["symbol"][0].replace("/", "").upper()
            for request in restart_transport.requests
        }
        assert repeated.isdisjoint(PAIRS)


def test_one_mapping_serves_all_timeframes_and_projection_refreshes(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        _register(db, "EURUSD", approved_mapping=True)
        resolve_twelve_data_facts(db, credential="secret", transport=FactTransport(), clock=lambda: NOW, symbols=("EURUSD",))
        profile = next(item for item in load_provider_profiles() if item.provider == "TWELVE_DATA")
        fact = load_provider_facts(db)["mappings"]["TWELVE_DATA:EURUSD"]
        assert fact["resolution_evidence"]["prior_approved_mapping"] == {
            "source_scope": "D1_REGISTRATION",
            "provider": "TWELVE_DATA",
            "provider_symbol": "EUR/USD",
            "ingest_run_id": "NOT_APPLICABLE",
            "observed_at": "REGISTRATION_AUTHORITY",
            "preservation": "MIGRATED_TO_REPRESENTATION_SCOPE",
        }
        mappings = [mapping_authority(profile, symbol="EURUSD", timeframe=timeframe, primary_provider=None, primary_symbol=None, resolved_mapping=fact) for timeframe in ("M5", "M30", "H1", "D1")]
        assert {item["provider_symbol"] for item in mappings} == {"EUR/USD"}
        assert {item["mapping_class"] for item in mappings} == {"EXACT_REPRESENTATION"}
        projection = acquisition_capability_projection(db, symbol="EURUSD", credentials={"TWELVE_DATA": "secret"}, now=NOW)
        rows = [row for row in projection["rows"] if row["provider"] == "TWELVE_DATA"]
        assert {row["timeframe"] for row in rows} == {"M5", "M30", "H1", "D1"}
        assert all(row["capability_state"] == "SUPPORTED" for row in rows)
        assert all(row["mapping_status"] == "EXACT_REPRESENTATION" for row in rows)
        monkeypatch.setenv("TWELVE_DATA_API_KEY", "secret")
        discovered = discover_market(db, "EURUSD")
        representation = next(item for item in discovered["markets"][0]["representations"] if item["symbol"] == "EURUSD")
        lanes = {item["timeframe"]: item for item in representation["timeframe_lanes"]}
        assert lanes["M5"]["provider_capability"] == "SUPPORTED"
        assert "EXACT_REPRESENTATION" in lanes["M5"]["provider_mapping"]


def test_bounded_probe_excludes_open_bar_accounts_usage_and_never_publishes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        _register(db, "EURUSD")
        transport = FactTransport()
        resolve_twelve_data_facts(db, credential="secret", transport=transport, clock=lambda: NOW, symbols=("EURUSD",))
        before = db.read_bytes()
        probe = probe_twelve_data_capability(db, canonical_symbol="EURUSD", timeframe="M5", credential="secret", transport=transport, clock=lambda: NOW)
        assert db.read_bytes() == before
        assert probe["reason"] == "TIMEFRAME_SUPPORTED"
        assert probe["probe_result"]["closed_rows"] == 2
        assert probe["probe_result"]["open_rows_excluded"] == 1
        assert probe["probe_result"]["api_credits_used"] == 1
        assert probe["probe_result"]["canonical_publication"] == "NONE"


def test_empty_probe_is_structured_without_invalidating_mapping() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        _register(db, "EURUSD")
        resolve_twelve_data_facts(db, credential="secret", transport=FactTransport(), clock=lambda: NOW, symbols=("EURUSD",))
        probe = probe_twelve_data_capability(db, canonical_symbol="EURUSD", timeframe="M30", credential="secret", transport=FactTransport(empty_probe=True), clock=lambda: NOW)
        assert probe["reason"] == "PROVIDER_NOT_FOUND"
        fact = load_provider_facts(db)["mappings"]["TWELVE_DATA:EURUSD"]
        assert fact["mapping_class"] == "EXACT_REPRESENTATION"
        assert fact["timeframe_capabilities"]["M30"]["supported"] is False


def test_transport_failure_has_retry_and_does_not_create_review() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        _register(db, "EURUSD")
        snapshot = resolve_twelve_data_facts(db, credential="secret", transport=FactTransport(failure=TimeoutError("bounded timeout")), clock=lambda: NOW, symbols=("EURUSD",))
        assert not snapshot["needs_material_review"]
        assert snapshot["provider_lookup_failed"][0]["outcome"] == "PROVIDER_LOOKUP_FAILED"
        assert snapshot["provider_lookup_failed"][0]["available_actions"] == ["Retry Now"]


def test_provider_not_found_has_retry_and_does_not_create_review() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        _register(db, "EURUSD")
        transport = FactTransport()
        transport.send = lambda request, credential, config: HttpResponse(
            200, "application/json", b'{"data":[]}', request.host, (("api-credits-used", "1"),)
        )
        snapshot = resolve_twelve_data_facts(
            db, credential="secret", transport=transport, clock=lambda: NOW, symbols=("EURUSD",)
        )
        assert not snapshot["needs_material_review"]
        assert snapshot["provider_lookup_failed"][0]["outcome"] == "PROVIDER_NOT_FOUND"
        assert snapshot["provider_lookup_failed"][0]["available_actions"] == ["Retry Now"]


def test_missing_credential_is_access_issue_not_mapping_review() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        _register(db, "EURUSD")
        snapshot = resolve_twelve_data_facts(db, credential=None, clock=lambda: NOW, symbols=("EURUSD",))
        assert snapshot["credential_state"] == "Missing"
        assert snapshot["credential_or_access_issue"]["outcome"] == "CREDENTIAL_MISSING"
        assert not snapshot["needs_material_review"]


def test_verified_credential_clears_stale_scheduler_auth_block() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        _register(db, "EURUSD")
        facts = load_provider_facts(db)
        facts["credential_state"] = "Configured"
        save_provider_facts(db, facts)
        state = {"TWELVE_DATA": {"health": "Credential Missing", "wait_reason": "AUTHENTICATION_BLOCKED"}}
        assert _repair_twelve_data_credential_health(db, state, {"TWELVE_DATA": "secret"})
        assert state["TWELVE_DATA"]["health"] == "Healthy"
        facts["credential_state"] = "Invalid"
        save_provider_facts(db, facts)
        state["TWELVE_DATA"]["health"] = "Authentication Blocked"
        assert not _repair_twelve_data_credential_health(db, state, {"TWELVE_DATA": "invalid"})


def test_cfd_outside_active_registry_is_retired_non_actionable() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        register_instrument(db, RegistrationCandidate(
            asset="XAGUSDCFD", timeframe="D1", instrument_family="XAGUSDCFD", local_symbol="XAGUSDCFD",
            display_name="Silver CFD", instrument_type="CFD", asset_class="METALS", representation_type="CFD",
            trading_currency="USD", exchange_name="OTC", provider_id=None, provider_contract=None, provider_symbol=None,
            provider_instrument_type=None, calendar_id="METALS_D1_V1", calendar_version=1,
            gap_doctrine_id="FRAGARACH_II_D1_GAP_DOCTRINE_V1", gap_doctrine_version=1,
        ), registered_at_utc=NOW.isoformat())
        before = db.read_bytes()
        snapshot = resolve_twelve_data_facts(db, credential="secret", transport=FactTransport(), clock=lambda: NOW, symbols=("XAGUSDCFD",))
        assert db.read_bytes() == before
        assert not snapshot["resolved_automatically"]
        assert not snapshot["needs_material_review"]
        item = next(item for item in snapshot["retired_non_actionable"] if item["canonical_symbol"] == "XAGUSDCFD")
        assert item["outcome"] == "RETIRED_NON_ACTIONABLE"
        universe = active_universe(db)
        assert "XAGUSDCFD:D1" not in universe["active_lanes"]
        assert universe["lanes"]["XAGUSDCFD:D1"]["lifecycle_state"] == "RETIRED_NON_ACTIONABLE"


def test_unresolved_index_candidate_creates_one_material_decision_not_lane_rows() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "authority.sqlite3"
        _register(db, "DJI")
        transport = FactTransport()
        # Override the generic response with an index candidate.
        def send(request, credential, config):
            transport.requests.append(request)
            row = {"symbol": "DJI", "instrument_name": "Dow Jones Industrial Average", "instrument_type": "Index", "exchange": "United States", "currency": "USD"}
            return HttpResponse(200, "application/json", json.dumps({"data": [row]}).encode(), request.host, (("api-credits-used", "1"),))
        transport.send = send
        snapshot = resolve_twelve_data_facts(db, credential="secret", transport=transport, clock=lambda: NOW, symbols=("DJI",))
        assert len(snapshot["needs_material_review"]) == 1
        assert snapshot["needs_material_review"][0]["canonical_symbol"] == "DJI"
        assert snapshot["needs_material_review"][0]["status"] == "REPRESENTATION_AMBIGUOUS"
