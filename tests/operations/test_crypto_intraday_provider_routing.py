from __future__ import annotations

import base64
import json
import tempfile
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from fragarach_ii.acquisition_orchestrator import (
    _quote_equivalence_rejection,
    acquisition_plan,
    build_rate_budgets,
    load_provider_profiles,
)
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.onboarding import register_provider_aware_instrument
from fragarach_ii.provider_facts import load_provider_facts, save_provider_facts
from fragarach_ii.providers.binance import (
    acquire_binance,
    admit_binance_chunks,
    prepare_binance_chunk,
)
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.scheduler_service import (
    SchedulerJournal,
    _guard_monitor_snapshot,
    reconcile_manual_requests,
    required_set_acquisition_plan,
    run_operator_fetch,
    scheduler_snapshot,
)
import fragarach_ii.scheduler_service as scheduler_service
import fragarach_ii.providers.binance as binance_provider
from fragarach_ii.acquisition_orchestrator import create_manual_request
from fragarach_ii.lane_commissioning import ensure_commissioned_lane, ensure_manual_acquisition_lane
from fragarach_ii.publication_service import enqueue_publication, lane_publication_state
from fragarach_ii.storage import initialize_database, open_read_only, register_instrument, registered_writer


NOW = datetime(2026, 7, 18, 12, tzinfo=UTC)


def _register(database: Path, symbol: str, *, twelve_data_fx: bool = False) -> None:
    initialize_database(database)
    representations = discover_market(database, symbol)["markets"][0]["representations"]
    representation = next(item for item in representations if item.get("registration_plan"))
    candidate = json.loads(base64.urlsafe_b64decode(representation["registration_plan"]["candidate"]))
    if twelve_data_fx:
        candidate.update(
            provider_id="TWELVE_DATA",
            provider_contract="TWELVE_DATA_TIME_SERIES_D1_V1",
            provider_symbol="GBP/AUD",
            provider_instrument_type="Physical Currency",
        )
    register_instrument(database, candidate_from_dict(candidate), registered_at_utc=NOW.isoformat())


def _twelve_data_eth_fact(database: Path) -> None:
    facts = load_provider_facts(database)
    facts["mappings"]["TWELVE_DATA:ETHUSD"] = {
        "canonical_symbol": "ETHUSD",
        "provider": "TWELVE_DATA",
        "provider_symbol": "ETH/USD",
        "mapping_class": "EXACT_REPRESENTATION",
        "status": "OPERATOR_RESOLVED",
        "timeframe_capabilities": {
            timeframe: {"timeframe": timeframe, "supported": True}
            for timeframe in ("D1", "H1", "M30", "M5")
        },
    }
    save_provider_facts(database, facts)


def _plan(database: Path, symbol: str, timeframe: str) -> dict[str, object]:
    return _plan_with_profiles(database, symbol, timeframe, load_provider_profiles())


def _plan_with_profiles(database: Path, symbol: str, timeframe: str, profiles) -> dict[str, object]:
    budgets = build_rate_budgets(profiles, {}, wall_clock=lambda: NOW, credential="fixture")
    return acquisition_plan(
        database, symbol=symbol, timeframe=timeframe, canonical_edge=None,
        expected_edge=NOW.isoformat(), missing_start="2026-07-17",
        missing_end="2026-07-18", scheduled_boundary=f"test:{symbol}:{timeframe}",
        profiles=profiles, provider_state={}, budgets=budgets,
        credentials={"TWELVE_DATA": "fixture"}, now=NOW,
    )


def _binance_usdt_profile(symbol: str, *, include_exact_usd: bool = False):
    base = next(profile for profile in load_provider_profiles() if profile.provider == "BINANCE")
    asset = symbol.removesuffix("USD")
    equivalent = {
        "asset": symbol, "asset_class": "CRYPTO",
        "canonical_base_asset": asset, "canonical_quote_asset": "USD",
        "symbol": f"{asset}USDT", "provider_base_asset": asset,
        "provider_quote_asset": "USDT", "provider_representation": f"{asset}/USDT",
        "timeframes": ["M5", "M30", "H1", "D1"],
        "mapping_class": "APPROVED_EQUIVALENT_REPRESENTATION",
        "quote_equivalence": "USD_USDT_CRYPTO",
        "conversion_policy": "NO_CONVERSION", "effective_date": "2026-07-18",
        "reviewed_status": "REVIEWED", "authority_source": "TEST_USDT_CRYPTO_EQUIVALENCE",
    }
    if not include_exact_usd:
        return replace(base, mappings=(equivalent,))
    exact = equivalent | {
        "symbol": symbol, "provider_quote_asset": "USD",
        "provider_representation": f"{asset}/USD",
        "mapping_class": "EXACT_REPRESENTATION",
        "quote_equivalence": None,
        "authority_source": "TEST_EXACT_CRYPTO_USD",
    }
    return replace(base, mappings=(equivalent, exact))


def _insert_canonical_bar(database: Path, *, symbol: str, timeframe: str, opened: int, seconds: int) -> None:
    run_id = f"test-{symbol.lower()}-{timeframe.lower()}"
    with registered_writer(database) as connection:
        connection.execute(
            """INSERT INTO ingest_runs(ingest_run_id,kind,status,started_at_utc,finished_at_utc,detail)
               VALUES(?,'test','committed',?,?,?)""",
            (run_id, NOW.isoformat(), NOW.isoformat(), json.dumps({"asset": symbol, "timeframe": timeframe})),
        )
        connection.execute(
            """INSERT INTO bars(asset,timeframe,open_time_utc,close_time_utc,open,high,low,close,
                                 created_by_ingest_run_id,updated_by_ingest_run_id)
               VALUES(?,?,?,?, '1','2','0','1',?,?)""",
            (symbol, timeframe, opened, opened + seconds, run_id, run_id),
        )


def test_crypto_intraday_prefers_binance_over_twelve_data_and_keeps_d1_independent() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _register(database, "ETHUSD")
        _twelve_data_eth_fact(database)

        d1 = _plan(database, "ETHUSD", "D1")
        assert d1["selected_provider"] == "TWELVE_DATA"
        assert d1["selected_provider_symbol"] == "ETH/USD"

        for timeframe in ("H1", "M30", "M5"):
            plan = _plan(database, "ETHUSD", timeframe)
            considered = {row["provider"]: row for row in plan["providers_considered"]}
            assert plan["selected_provider"] == "BINANCE"
            assert plan["selected_provider_symbol"] == "ETHUSD"
            assert plan["selected_fallback_rank"] == 1
            assert plan["routing_policy"] == "CRYPTO_INTRADAY_V1"
            assert considered["BINANCE"]["provider_representation"] == "ETH/USD"
            assert considered["BINANCE"]["representation_type"] == "EXACT_REPRESENTATION"
            assert considered["BINANCE"]["fallback_rank"] == 1
            assert considered["TWELVE_DATA"]["reason"] == "CRYPTO_INTRADAY_NOT_APPROVED"
            assert considered["COINGECKO"]["reason"] == "TIMEFRAME_UNSUPPORTED"
            assert considered["YAHOO_FINANCE"]["reason"] == "ASSET_CLASS_UNSUPPORTED"


def test_ethusd_m5_utc_operator_bounds_attempt_binance_without_twelve_data() -> None:
    """UTC bounds must survive scheduler preflight and reach the crypto adapter."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal = Path(directory) / "scheduler.json"
        _register(database, "ETHUSD")
        _twelve_data_eth_fact(database)
        profiles = tuple(
            replace(profile, maximum_rows_per_request=200_000)
            if profile.provider == "BINANCE" else profile
            for profile in load_provider_profiles()
        )
        calls: list[dict[str, object]] = []

        def provider_without_evidence(_database: Path, **kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            assert kwargs["provider"] == "BINANCE"
            assert kwargs["provider_symbol"] == "ETHUSD"
            return {"inserted": 0, "corrected": 0, "unchanged": 0, "received": 0}

        result = run_operator_fetch(
            database,
            symbol="ETHUSD",
            timeframe="M5",
            credential="fixture",
            requested_mode="initial",
            requested_start="2025-07-18T02:15:00Z",
            requested_end="2026-07-18T02:15:00Z",
            reviewed_historical_range=True,
            journal_path=journal,
            at=datetime(2026, 7, 18, 2, 15, tzinfo=UTC),
            acquirer=provider_without_evidence,
            provider_profiles=profiles,
        )

        considered = {row["provider"]: row for row in result["providers_considered"]}
        assert [call["provider"] for call in calls] == ["BINANCE"]
        assert result["providers_attempted"] == ["BINANCE"]
        assert considered["BINANCE"]["eligible"] is True
        assert considered["TWELVE_DATA"]["eligible"] is False
        assert considered["TWELVE_DATA"]["reason"] == "CRYPTO_INTRADAY_NOT_APPROVED"
        with open_read_only(database) as connection:
            assert connection.execute(
                "SELECT count(*) FROM bars WHERE asset='ETHUSD' AND timeframe='M5'"
            ).fetchone()[0] == 0


def test_ethusd_m5_force_history_refresh_is_not_suppressed_when_lane_is_current() -> None:
    """A current edge must not hide the governed history-repair operation."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal = Path(directory) / "scheduler.json"
        _register(database, "ETHUSD")
        _twelve_data_eth_fact(database)
        observed = datetime(2026, 7, 18, 2, 45, tzinfo=UTC)
        ensure_manual_acquisition_lane(database, "ETHUSD", "M5", observed_at="2026-07-18T02:40:00+00:00")
        _insert_canonical_bar(
            database, symbol="ETHUSD", timeframe="M5",
            opened=int(datetime(2026, 7, 18, 2, 40, tzinfo=UTC).timestamp()), seconds=300,
        )
        profiles = tuple(
            replace(profile, maximum_rows_per_request=200_000)
            if profile.provider == "BINANCE" else profile
            for profile in load_provider_profiles()
        )
        calls: list[dict[str, object]] = []

        def provider_without_evidence(_database: Path, **kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            return {"inserted": 0, "corrected": 0, "unchanged": 0, "received": 0}

        result = run_operator_fetch(
            database, symbol="ETHUSD", timeframe="M5", credential="fixture",
            requested_mode="force", requested_start="2025-07-18T02:45:00Z",
            requested_end="2026-07-18T02:45:00Z", reviewed_historical_range=True,
            journal_path=journal, at=observed, acquirer=provider_without_evidence,
            provider_profiles=profiles,
        )

        assert calls and calls[0]["provider"] == "BINANCE"
        assert result["requested_range"] == {
            "start": "2025-07-18T02:45:00Z", "end": "2026-07-18T02:45:00Z",
        }
        assert result["outcome"] != "NO_NEW_DATA"


def test_onboarding_snapshot_projects_manual_crypto_evidence_without_granting_scheduler_ownership() -> None:
    """Manual evidence remains plannable before it becomes scheduler-owned."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _register(database, "ETHUSD")
        _twelve_data_eth_fact(database)
        observed = datetime(2026, 7, 18, 2, 47, tzinfo=UTC)
        ensure_manual_acquisition_lane(database, "ETHUSD", "M5", observed_at="2026-07-18T02:30:00+00:00")
        opened = int(datetime(2026, 7, 18, 2, 35, tzinfo=UTC).timestamp())
        _insert_canonical_bar(database, symbol="ETHUSD", timeframe="M5", opened=opened, seconds=300)

        def lane() -> dict[str, object]:
            return next(item for item in scheduler_snapshot(
                database, clock=lambda: observed, credential="fixture"
            )["lanes"] if item["id"] == "ETHUSD:M5")

        manual = lane()
        assert manual["scheduler_state"] == "Not Commissioned"
        assert manual["latest_canonical_observation"] == "2026-07-18T02:40:00+00:00"
        assert manual["expected_latest"] == "2026-07-18T02:45:00+00:00"
        assert manual["expected_edge_status"] == "EXPECTED_EDGE_AVAILABLE"
        assert manual["publication_state"] == "PUBLISHING"
        eligible = {row["provider"] for row in manual["provider_capabilities"] if row["eligibility"] == "ELIGIBLE"}
        assert eligible == {"BINANCE"}

        enqueue_publication(
            database, [("ETHUSD", "M5")], trigger="TEST_PUBLISHED", publisher=lambda *_args: None
        )
        for _ in range(50):
            if lane_publication_state(database, "ETHUSD", "M5") == "PUBLISHED":
                break
            time.sleep(0.01)
        assert lane_publication_state(database, "ETHUSD", "M5") == "PUBLISHED"

        ensure_commissioned_lane(database, "ETHUSD", "M5", observed_at=observed.isoformat())
        enqueue_publication(
            database, [("ETHUSD", "M5")], trigger="TEST_BEHIND", publisher=lambda *_args: None
        )
        for _ in range(50):
            if lane_publication_state(database, "ETHUSD", "M5") == "PUBLISHED":
                break
            time.sleep(0.01)
        assert lane()["scheduler_state"] == "Behind"
        current = scheduler_snapshot(
            database, clock=lambda: datetime(2026, 7, 18, 2, 41, tzinfo=UTC), credential="fixture"
        )
        assert next(item for item in current["lanes"] if item["id"] == "ETHUSD:M5")["scheduler_state"] == "Current"
        enqueue_publication(database, [("ETHUSD", "M5")], trigger="TEST_PENDING")
        assert lane()["scheduler_state"] == "Publishing"

        def failing_publisher(*_args: object) -> None:
            raise RuntimeError("test publication failure")

        enqueue_publication(
            database, [("ETHUSD", "M5")], trigger="TEST_FAILED", publisher=failing_publisher
        )
        for _ in range(50):
            if lane_publication_state(database, "ETHUSD", "M5") == "FAILED_RETRYABLE":
                break
            time.sleep(0.01)
        assert lane_publication_state(database, "ETHUSD", "M5") == "FAILED_RETRYABLE"
        assert lane()["scheduler_state"] == "Failed"


def test_late_fx_and_d1_stock_onboarding_expose_calendar_edges_and_explicit_no_evidence() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        fx_database, stock_database = root / "fx.sqlite3", root / "stock.sqlite3"
        _register(fx_database, "GBPAUD", twelve_data_fx=True)
        _register(stock_database, "CAT")
        fx_now = datetime(2026, 7, 15, 14, 2, tzinfo=UTC)
        ensure_manual_acquisition_lane(fx_database, "GBPAUD", "M30", observed_at=fx_now.isoformat())
        opened = int(datetime(2026, 7, 15, 13, 30, tzinfo=UTC).timestamp())
        _insert_canonical_bar(fx_database, symbol="GBPAUD", timeframe="M30", opened=opened, seconds=1800)
        fx_lane = next(item for item in scheduler_snapshot(
            fx_database, clock=lambda: fx_now, credential="fixture"
        )["lanes"] if item["id"] == "GBPAUD:M30")
        assert (fx_lane["scheduler_state"], fx_lane["expected_latest"]) == (
            "Not Commissioned", "2026-07-15T14:00:00+00:00"
        )
        assert {item["provider"] for item in fx_lane["provider_capabilities"] if item["eligibility"] == "ELIGIBLE"} == {"TWELVE_DATA"}

        stock_now = datetime(2026, 7, 15, 14, 0, tzinfo=UTC)
        stock_lane = next(item for item in scheduler_snapshot(
            stock_database, clock=lambda: stock_now, credential="fixture"
        )["lanes"] if item["id"] == "CAT:D1")
        assert stock_lane["scheduler_state"] == "No Evidence"
        assert stock_lane["latest_canonical_observation"] is None
        assert stock_lane["expected_latest"] == "2026-07-14T00:00:00+00:00"


def test_fx_routing_and_stock_required_set_are_unchanged() -> None:
    with tempfile.TemporaryDirectory() as directory:
        fx_database = Path(directory) / "fx.sqlite3"
        stock_database = Path(directory) / "stock.sqlite3"
        _register(fx_database, "GBPAUD", twelve_data_fx=True)
        _register(stock_database, "AAPL")

        fx = _plan(fx_database, "GBPAUD", "H1")
        assert fx["selected_provider"] == "TWELVE_DATA"
        assert fx["routing_policy"] == "DEFAULT_PROVIDER_PRIORITY_V1"

        stocks = required_set_acquisition_plan(stock_database, symbol="AAPL", at=NOW)
        assert stocks["required_timeframes"] == ["D1"]


def test_crypto_required_set_makes_all_intraday_lanes_executable_with_routing_rejections() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _register(database, "ETHUSD")
        _twelve_data_eth_fact(database)

        required_set = required_set_acquisition_plan(database, symbol="ETHUSD", at=NOW)
        lanes = {lane["timeframe"]: lane for lane in required_set["lanes"]}
        for timeframe in ("H1", "M30", "M5"):
            lane = lanes[timeframe]
            assert lane["executable"] is True
            assert lane["provider"] == "BINANCE"
            rejected = {row["provider"]: row["reason"] for row in lane["providers_considered"]}
            assert rejected["TWELVE_DATA"] == "CRYPTO_INTRADAY_NOT_APPROVED"


def test_crypto_usdt_quote_equivalence_routes_eth_and_sol_without_changing_canonical_lanes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        for symbol in ("ETHUSD", "SOLUSD"):
            database = Path(directory) / f"{symbol}.sqlite3"
            _register(database, symbol)
            plan = _plan_with_profiles(database, symbol, "H1", (_binance_usdt_profile(symbol),))

            assert plan["lane"] == f"{symbol}:H1"
            assert plan["selected_provider"] == "BINANCE"
            assert plan["selected_provider_symbol"] == f"{symbol.removesuffix('USD')}USDT"
            assert plan["selected_mapping_class"] == "APPROVED_EQUIVALENT_REPRESENTATION"
            decision = plan["providers_considered"][0]
            assert decision["quote_equivalence"] == "USD_USDT_CRYPTO"
            assert decision["quote_equivalence_reason"] == "CRYPTO_USD_USDT_QUOTE_EQUIVALENCE"
            assert decision["fallback_rank"] == 1


def test_hype_onboarding_uses_reviewed_twelve_data_usdt_for_d1_and_intraday(monkeypatch) -> None:
    """The verified Twelve Data catalogue unlocks HYPE without a Binance spot pair."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        initialize_database(database)
        monkeypatch.setattr(
            "fragarach_ii.acquisition_orchestrator.credential_map",
            lambda _value=None: {"TWELVE_DATA": "fixture"},
        )
        monkeypatch.setattr(
            scheduler_service, "credential_map", lambda _value=None: {"TWELVE_DATA": "fixture"},
        )

        market = discover_market(database, "HYPE")["markets"][0]
        representation = next(item for item in market["representations"] if item["symbol"] == "HYPEUSD")
        candidate = candidate_from_dict(json.loads(base64.urlsafe_b64decode(
            representation["registration_plan"]["candidate"]
        )))

        assert market["available_actions"] == ("ADD_TO_FRAGARACH",)
        assert (candidate.provider_id, candidate.provider_symbol) == ("TWELVE_DATA", "HYPE/USDT")

        receipt = register_provider_aware_instrument(
            database, candidate, registered_at_utc=NOW.isoformat()
        )
        assert receipt["commissioned_timeframes"] == ["D1", "H1", "M30", "M5"]

        for timeframe in ("D1", "H1", "M30", "M5"):
            plan = _plan(database, "HYPEUSD", timeframe)
            twelve = next(item for item in plan["providers_considered"] if item["provider"] == "TWELVE_DATA")
            assert plan["selected_provider"] == "TWELVE_DATA"
            assert plan["selected_provider_symbol"] == "HYPE/USDT"
            assert twelve["eligible"] is True
            assert twelve["mapping_class"] == "APPROVED_EQUIVALENT_REPRESENTATION"
            assert twelve["quote_equivalence"] == "USD_USDT_CRYPTO"


def test_bnb_onboarding_offers_reviewed_coingecko_d1_and_binance_usdt_intraday() -> None:
    """BNB discovery is actionable before registration; routing unlocks after it."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        initialize_database(database)
        market = discover_market(database, "BNB")["markets"][0]
        representation = next(item for item in market["representations"] if item["symbol"] == "BNBUSD")

        assert market["canonical_identity"] == "REGISTRY:crypto:coingecko:binancecoin:usd"
        assert market["available_actions"] == ("ADD_TO_FRAGARACH",)
        assert representation["acquisition_readiness"] == "READY_FOR_REGISTRATION"
        assert representation["provider_mapping_status"] == "KNOWN_MAPPING"
        assert representation["registration_plan"]["provider_mappings"] == (
            {"provider": "BINANCE", "symbol": "BNBUSDT", "state": "SELECTED_FOR_REVIEW"},
        )
        lanes = {item["timeframe"]: item for item in representation["timeframe_lanes"]}
        assert lanes["D1"]["provider_capability"] == "SUPPORTED_WITH_APPROVED_MAPPING"
        assert lanes["M5"]["provider_capability"] == "SUPPORTED_WITH_APPROVED_MAPPING"

        candidate = candidate_from_dict(json.loads(base64.urlsafe_b64decode(
            representation["registration_plan"]["candidate"]
        )))
        receipt = register_provider_aware_instrument(
            database, candidate, registered_at_utc=NOW.isoformat()
        )
        assert receipt["symbol"] == "BNBUSD"
        assert receipt["provider"] == "BINANCE"
        assert receipt["provider_symbol"] == "BNBUSDT"
        assert receipt["commissioned_timeframes"] == ["D1", "H1", "M30", "M5"]
        assert receipt["scheduler_reconciliation"]["queued_timeframes"] == ["D1", "H1", "M30", "M5"]

        selected_lane = next(item for item in scheduler_snapshot(
            database, clock=lambda: NOW, credential="fixture"
        )["lanes"] if item["id"] == "BNBUSD:D1")
        selected_plan = selected_lane["acquisition_plan"]
        candidates = {item["provider"]: item for item in selected_plan["providers_considered"]}
        assert selected_plan["intent"] == "initial"
        assert selected_plan["provider"] == "BINANCE"
        assert selected_plan["provider_symbol"] == "BNBUSDT"
        assert selected_plan["request_bounds"] == {
            "start": "2016-07-17", "end": "2026-07-17",
        }
        assert candidates["BINANCE"]["eligible"] is True
        assert candidates["COINGECKO"]["reason"] == "RANGE_UNAVAILABLE"

        for timeframe in ("M5", "M30", "H1"):
            plan = _plan(database, "BNBUSD", timeframe)
            considered = {row["provider"]: row for row in plan["providers_considered"]}
            assert plan["selected_provider"] == "BINANCE"
            assert plan["selected_provider_symbol"] == "BNBUSDT"
            assert plan["selected_mapping_class"] == "APPROVED_EQUIVALENT_REPRESENTATION"
            assert considered["BINANCE"]["quote_equivalence"] == "USD_USDT_CRYPTO"
            assert considered["COINGECKO"]["reason"] == "TIMEFRAME_UNSUPPORTED"

        required_set = required_set_acquisition_plan(
            database, symbol="BNBUSD", credential="fixture", at=NOW
        )
        required_lanes = {item["timeframe"]: item for item in required_set["lanes"]}
        assert required_lanes["D1"]["provider"] == "BINANCE"
        assert {item["provider"] for item in required_lanes["D1"]["providers_considered"]} >= {
            "BINANCE", "COINGECKO",
        }
        for timeframe in ("H1", "M30", "M5"):
            assert required_lanes[timeframe]["provider"] == "BINANCE"
            assert required_lanes[timeframe]["commissioned"] is True

        d1 = _plan(database, "BNBUSD", "D1")
        d1_considered = {row["provider"]: row for row in d1["providers_considered"]}
        assert d1["selected_provider"] == "BINANCE"
        assert d1["selected_provider_api_base_url"] == "https://api.binance.com"
        assert d1_considered["BINANCE"]["api_base_url"] == "https://api.binance.com"
        assert d1_considered["COINGECKO"]["eligible"] is True
        assert d1_considered["COINGECKO"]["provider_symbol"] == "binancecoin"

        opened = int(datetime(2026, 7, 17, tzinfo=UTC).timestamp())
        _insert_canonical_bar(
            database, symbol="BNBUSD", timeframe="D1", opened=opened, seconds=86_400
        )
        enqueue_publication(
            database, [("BNBUSD", "D1")], trigger="TEST_BNB_PUBLICATION", publisher=lambda *_args: None
        )
        for _ in range(50):
            if lane_publication_state(database, "BNBUSD", "D1") == "PUBLISHED":
                break
            time.sleep(0.01)
        published = next(item for item in scheduler_snapshot(
            database, clock=lambda: NOW, credential="fixture"
        )["lanes"] if item["id"] == "BNBUSD:D1")
        assert lane_publication_state(database, "BNBUSD", "D1") == "PUBLISHED"
        assert published["scheduler_state"] == "Current"
        assert published["latest_canonical_observation"] == "2026-07-17T00:00:00+00:00"


def test_xrpusd_full_non_live_onboarding_and_initial_planning() -> None:
    """XRP follows the approved crypto USD/USDT and D1 fallback doctrine."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        initialize_database(database)
        market = discover_market(database, "XRP")["markets"][0]
        representation = next(item for item in market["representations"] if item["symbol"] == "XRPUSD")
        assert market["canonical_identity"] == "REGISTRY:crypto:coingecko:ripple:usd"
        assert representation["registration_plan"]["provider_mappings"] == (
            {"provider": "BINANCE", "symbol": "XRPUSDT", "state": "SELECTED_FOR_REVIEW"},
        )

        receipt = register_provider_aware_instrument(
            database,
            candidate_from_dict(json.loads(base64.urlsafe_b64decode(
                representation["registration_plan"]["candidate"]
            ))),
            registered_at_utc=NOW.isoformat(),
        )
        assert (receipt["symbol"], receipt["provider"], receipt["provider_symbol"]) == (
            "XRPUSD", "BINANCE", "XRPUSDT",
        )
        assert receipt["commissioned_timeframes"] == ["D1", "H1", "M30", "M5"]
        assert receipt["scheduler_reconciliation"]["queued_timeframes"] == ["D1", "H1", "M30", "M5"]

        required = required_set_acquisition_plan(
            database, symbol="XRPUSD", credential="fixture", at=NOW
        )
        lanes = {item["timeframe"]: item for item in required["lanes"]}
        d1 = {item["provider"]: item for item in lanes["D1"]["providers_considered"]}
        assert (lanes["D1"]["intent"], lanes["D1"]["provider"], lanes["D1"]["provider_symbol"]) == (
            "initial", "BINANCE", "XRPUSDT",
        )
        assert d1["BINANCE"]["eligible"] is True
        assert d1["COINGECKO"]["reason"] == "RANGE_UNAVAILABLE"
        for timeframe in ("H1", "M30", "M5"):
            assert (lanes[timeframe]["provider"], lanes[timeframe]["provider_symbol"]) == (
                "BINANCE", "XRPUSDT",
            )
            assert lanes[timeframe]["commissioned"] is True

        snapshot_lane = next(item for item in scheduler_snapshot(
            database, clock=lambda: NOW, credential="fixture"
        )["lanes"] if item["id"] == "XRPUSD:D1")
        selected = snapshot_lane["acquisition_plan"]
        assert selected["provider"] == "BINANCE"
        assert [item["provider"] for item in selected["providers_considered"] if item["provider"] in {"BINANCE", "COINGECKO"}] == [
            "BINANCE", "COINGECKO",
        ]


def test_adausd_discovery_exposes_binance_initial_history_route() -> None:
    """A newly reviewed crypto is actionable before any provider acquisition."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        initialize_database(database)
        market = discover_market(database, "ADAUSD")["markets"][0]
        representation = next(item for item in market["representations"] if item["symbol"] == "ADAUSD")

        assert market["canonical_identity"] == "REGISTRY:crypto:coingecko:cardano:usd"
        assert market["available_actions"] == ("ADD_TO_FRAGARACH",)
        assert representation["acquisition_readiness"] == "READY_FOR_REGISTRATION"
        lanes = {item["timeframe"]: item for item in representation["timeframe_lanes"]}
        assert all(
            lanes[timeframe]["provider_capability"] == "SUPPORTED_WITH_APPROVED_MAPPING"
            for timeframe in ("D1", "H1", "M30", "M5")
        )

        candidate = candidate_from_dict(json.loads(base64.urlsafe_b64decode(
            representation["registration_plan"]["candidate"]
        )))
        assert (candidate.provider_id, candidate.provider_symbol) == ("BINANCE", "ADAUSDT")
        receipt = register_provider_aware_instrument(
            database, candidate, registered_at_utc=NOW.isoformat()
        )
        assert receipt["commissioned_timeframes"] == ["D1", "H1", "M30", "M5"]
        assert receipt["scheduler_reconciliation"]["queued_timeframes"] == ["D1", "H1", "M30", "M5"]

        required = required_set_acquisition_plan(
            database, symbol="ADAUSD", credential="fixture", at=NOW
        )
        lanes = {item["timeframe"]: item for item in required["lanes"]}
        assert (lanes["D1"]["provider"], lanes["D1"]["provider_symbol"]) == ("BINANCE", "ADAUSDT")
        d1_candidates = {item["provider"]: item for item in lanes["D1"]["providers_considered"]}
        assert d1_candidates["COINGECKO"]["reason"] == "RANGE_UNAVAILABLE"
        for timeframe in ("H1", "M30", "M5"):
            assert (lanes[timeframe]["provider"], lanes[timeframe]["provider_symbol"]) == (
                "BINANCE", "ADAUSDT",
            )


def test_bnb_initial_manual_request_restores_approved_binance_history_queue() -> None:
    """A prior empty attempt cannot hide a reviewed route for a no-evidence lane."""
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal_path = Path(directory) / "scheduler.json"
        _register(database, "BNBUSD")
        # Establish the current reconciliation revisions before modelling the
        # exact legacy request that previously got stranded as manual-required.
        scheduler_snapshot(database, clock=lambda: NOW, journal_path=journal_path, credential="fixture")
        journal = SchedulerJournal(database, journal_path)
        request = create_manual_request(
            journal.manual_requests,
            symbol="BNBUSD", timeframe="D1",
            missing_start="2016-07-18", missing_end="2026-07-17",
            expected_edge="2026-07-17T00:00:00+00:00",
            reason="ALL_PROVIDERS_EXHAUSTED", providers_attempted=["BINANCE"],
            failures=[{"provider": "BINANCE", "reason": "NO_NEW_DATA", "retryable": False}],
            providers_considered=[{
                "provider": "BINANCE", "provider_symbol": "BNBUSDT",
                "mapping_class": "APPROVED_EQUIVALENT_REPRESENTATION", "eligible": False,
                "reason": "PROVIDER_ALREADY_ATTEMPTED",
            }],
            provider_fact_revision=journal.data["current_provider_fact_revision"],
            capability_projection_revision=journal.data["current_capability_projection_revision"],
            now=NOW,
        )
        journal.lane("BNBUSD", "D1").update(
            result="FAILED", reason="ALL_PROVIDERS_EXHAUSTED", manual_request=request["id"]
        )
        journal.save()

        report = reconcile_manual_requests(
            database, journal_path=journal_path, credential="fixture", at=NOW,
            trigger="SCHEDULER_RESTART",
        )

        repaired = SchedulerJournal(database, journal_path)
        restored = next(item for item in repaired.manual_requests if item["id"] == request["id"])
        queued = next(item for item in repaired.data["acquisition_queue"] if item["lane"] == "BNBUSD:D1")
        assert report["automation_restored"] == 1
        assert restored["status"] == "Archived"
        assert restored["providers_currently_eligible"] == ["BINANCE"]
        assert queued["selected_provider"] == "BINANCE"
        assert queued["selected_provider_symbol"] == "BNBUSDT"
        assert queued["missing_range"] == {"start": "2016-07-17", "end": "2026-07-17"}


def test_monitor_compaction_keeps_approved_bnb_routes_visible() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _register(database, "BNBUSD")
        lane = next(item for item in scheduler_snapshot(
            database, clock=lambda: NOW, credential="fixture"
        )["lanes"] if item["id"] == "BNBUSD:D1")
        compacted = {"lanes": [lane], "padding": "x" * (3 * 1024 * 1024)}
        _guard_monitor_snapshot(compacted, started_at=0)
        assert [item["provider"] for item in compacted["lanes"][0]["provider_capabilities"]] == [
            "BINANCE", "COINGECKO",
        ]
        assert [item["provider"] for item in compacted["lanes"][0]["acquisition_plan"]["providers_considered"]] == [
            "BINANCE", "COINGECKO",
        ]


def test_exact_crypto_usd_mapping_outranks_approved_usdt_equivalence() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _register(database, "ETHUSD")

        plan = _plan_with_profiles(
            database, "ETHUSD", "M5", (_binance_usdt_profile("ETHUSD", include_exact_usd=True),)
        )
        assert plan["selected_provider_symbol"] == "ETHUSD"
        assert plan["selected_mapping_class"] == "EXACT_REPRESENTATION"


def test_usd_usdt_quote_equivalence_is_rejected_outside_crypto() -> None:
    mapping = {"quote_equivalence": "USD_USDT_CRYPTO"}
    assert _quote_equivalence_rejection("CRYPTO", mapping) is None
    assert _quote_equivalence_rejection("FX", mapping) == "CRYPTO_QUOTE_EQUIVALENCE_NOT_APPLICABLE"
    assert _quote_equivalence_rejection("US_EQUITIES", mapping) == "CRYPTO_QUOTE_EQUIVALENCE_NOT_APPLICABLE"


def test_binance_ethusd_h1_accepts_zulu_initial_history_bounds_without_parse_evidence() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _register(database, "ETHUSD")
        ensure_commissioned_lane(database, "ETHUSD", "H1", observed_at=NOW.isoformat())
        opened = int(datetime(2023, 7, 18, 1, tzinfo=UTC).timestamp() * 1000)
        payload = json.dumps([
            [opened, "1", "2", "0", "1", "10", opened + 3_600_000 - 1],
        ]).encode()
        requests: list[str] = []

        result = acquire_binance(
            database, asset="ETHUSD", timeframe="H1", provider_symbol="ETHUSD",
            from_date="2023-07-18T01:00:00Z", through_date="2023-07-18T02:00:00Z",
            fetch=lambda url: requests.append(url) or payload,
            clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        )

        query = parse_qs(urlparse(requests[0]).query)
        assert query["startTime"] == [str(opened)]
        assert query["endTime"] == [str(opened + 3_600_000 - 1)]
        assert result["inserted"] == 1
        with open_read_only(database) as connection:
            assert connection.execute(
                "SELECT count(*) FROM bars WHERE asset='ETHUSD' AND timeframe='H1'"
            ).fetchone()[0] == 1


def test_bnbusdt_uses_its_reviewed_binance_global_venue_without_live_io() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _register(database, "BNBUSD")
        opened = int(datetime(2026, 7, 17, tzinfo=UTC).timestamp() * 1000)
        payload = json.dumps([
            [opened, "1", "2", "0", "1", "10", opened + 86_400_000 - 1],
        ]).encode()
        requests: list[str] = []

        result = acquire_binance(
            database, asset="BNBUSD", timeframe="D1", provider_symbol="BNBUSDT",
            from_date="2026-07-17", through_date="2026-07-17",
            api_base_url="https://api.binance.com",
            fetch=lambda url: requests.append(url) or payload,
            clock=lambda: NOW,
        )

        assert requests[0].startswith("https://api.binance.com/api/v3/klines?")
        assert parse_qs(urlparse(requests[0]).query)["symbol"] == ["BNBUSDT"]
        assert result["inserted"] == 1


def test_binance_history_chunks_admit_once_while_retaining_each_raw_response() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _register(database, "BNBUSD")
        ensure_commissioned_lane(database, "BNBUSD", "H1", observed_at=NOW.isoformat())

        def payload_for(hour: int) -> bytes:
            opened = int(datetime(2026, 7, 17, hour, tzinfo=UTC).timestamp() * 1000)
            return json.dumps([
                [opened, "1", "2", "0", "1", "10", opened + 3_600_000 - 1],
            ]).encode()

        chunks = tuple(
            prepare_binance_chunk(
                asset="BNBUSD", timeframe="H1", provider_symbol="BNBUSDT",
                from_date=f"2026-07-17T{hour:02d}:00:00Z",
                through_date=f"2026-07-17T{hour + 1:02d}:00:00Z",
                api_base_url="https://api.binance.com",
                fetch=lambda _url, body=payload_for(hour): body,
                clock=lambda: NOW,
            )
            for hour in (0, 1)
        )
        result = admit_binance_chunks(
            database, asset="BNBUSD", timeframe="H1", provider_symbol="BNBUSDT",
            chunks=chunks, mapping_class="APPROVED_EQUIVALENT_REPRESENTATION",
            from_date="2026-07-17", through_date="2026-07-17",
        )

        assert result["inserted"] == 2
        assert result["chunk_count"] == 2
        with open_read_only(database) as connection:
            assert connection.execute("SELECT count(*) FROM raw_blocks").fetchone()[0] == 2
            assert connection.execute(
                "SELECT count(*) FROM ingest_runs WHERE kind = 'provider_acquisition'"
            ).fetchone()[0] == 1


def test_binance_history_downloads_chunks_concurrently_before_single_admission(monkeypatch) -> None:
    active = 0
    maximum_active = 0
    lock = threading.Lock()
    dispatched: list[int] = []
    responded: list[tuple[int, bool]] = []

    def prepare(**kwargs):
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return kwargs["from_date"]

    def admit(_database, **kwargs):
        assert kwargs["chunks"] == ("2026-07-17", "2026-07-18", "2026-07-19")
        return {"received": 3, "inserted": 3}

    monkeypatch.setattr(binance_provider, "prepare_binance_chunk", prepare)
    monkeypatch.setattr(binance_provider, "admit_binance_chunks", admit)

    result = scheduler_service._execute_acquisition(
        lambda *_args, **_kwargs: pytest.fail("serial acquirer must not run"),
        "unused.sqlite3", provider="BINANCE", provider_symbol="BNBUSDT",
        mapping_class="APPROVED_EQUIVALENT_REPRESENTATION", asset="BNBUSD",
        timeframe="H1", from_date="2026-07-17", through_date="2026-07-19",
        merge_mode="preserve", request_count=3, maximum_rows=24,
        on_dispatch=dispatched.append,
        on_response=lambda index, success: responded.append((index, success)),
    )

    assert maximum_active >= 2
    assert dispatched == [0, 1, 2]
    assert responded == [(0, True), (1, True), (2, True)]
    assert result["request_count"] == 3


def test_binance_bound_parse_failure_writes_no_evidence() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _register(database, "ETHUSD")
        with open_read_only(database) as connection:
            before = connection.execute("SELECT count(*) FROM raw_blocks").fetchone()[0]

        with pytest.raises(ValueError, match="Invalid isoformat string"):
            acquire_binance(
                database, asset="ETHUSD", timeframe="H1", provider_symbol="ETHUSD",
                from_date="not-a-timestamp", through_date="2023-07-18T02:00:00Z",
                fetch=lambda _: pytest.fail("fetch must not start after bound parse failure"),
            )

        with open_read_only(database) as connection:
            after = connection.execute("SELECT count(*) FROM raw_blocks").fetchone()[0]
        assert after == before
