from __future__ import annotations

import base64
import json
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.estate_truth_service import estate_truth_state
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.storage import initialize_database, register_instrument


def _register_discovered(db: Path, symbol: str):
    market=discover_market(db,symbol)["markets"][0]
    representation=next(item for item in market["representations"] if item["symbol"]==symbol)
    value=json.loads(base64.urlsafe_b64decode(representation["registration_plan"]["candidate"]))
    candidate=candidate_from_dict(value)
    register_instrument(db,candidate,registered_at_utc=datetime(2026,7,14,tzinfo=UTC).isoformat())
    return candidate


def _d1(db: Path, symbol: str):
    capability=next(item for item in estate_truth_state(db)["timeframe_capabilities"] if item["symbol"]==symbol)
    return capability,capability["timeframes"][0]


def test_stock_no_evidence_is_initial_fetch_eligible_but_not_consumable():
    with tempfile.TemporaryDirectory() as temporary:
        db=Path(temporary)/"authority.sqlite3";initialize_database(db)
        for symbol in ("AAPL","GOOGL"):
            _register_discovered(db,symbol)
            capability,lane=_d1(db,symbol)
            assert lane["evidence_state"]=="NO_EVIDENCE"
            assert lane["initial_fetch_eligible"] is True
            assert lane["consumption_available"] is False
            assert lane["authority_state"]=="REGISTERED_NO_EVIDENCE"
            assert lane["required_operator_action"]=="RESUME_INITIAL_HISTORY"
            assert lane["provider"]=="TWELVE_DATA"
            assert lane["provider_symbol"]==symbol
            assert lane["provider_contract"]=="TWELVE_DATA_TIME_SERIES_D1_V1"
            assert "NASDAQ" in lane["calendar_authority"]
            assert capability["intentionally_deferred_timeframes"]==["H1","M30","M5"]


def test_genuine_mapping_blocker_is_exact_and_non_stock_regression_remains_eligible():
    with tempfile.TemporaryDirectory() as temporary:
        db=Path(temporary)/"authority.sqlite3";initialize_database(db)
        candidate=_register_discovered(db,"GOOGL")
        other=replace(candidate,asset="NOMAP",instrument_family="NOMAP",local_symbol="NOMAP",display_name="Unmapped Stock",provider_id=None,provider_contract=None,provider_symbol=None,provider_instrument_type=None,provider_exchange=None)
        register_instrument(db,other,registered_at_utc=datetime(2026,7,14,tzinfo=UTC).isoformat())
        _,blocked=_d1(db,"NOMAP")
        assert blocked["initial_fetch_eligible"] is False
        assert blocked["initial_fetch_blockers"]==["PROVIDER_SYMBOL_MAPPING_REQUIRED"]
        _,audusd=_d1(db,"AUDUSD")
        assert audusd["initial_fetch_eligible"] is True
        assert audusd["consumption_available"] is False
