from __future__ import annotations
import tempfile
from datetime import UTC,datetime
from pathlib import Path
import base64,json
from fragarach_ii.market_registry import load_registry,search_registry
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.storage import initialize_database,open_read_only,register_instrument

def test_registry_loads_deterministically_with_required_universe_counts():
    first=load_registry();second=load_registry()
    assert first.records==second.records
    assert first.counts["CRYPTO"]>=500 and first.counts["US_EQUITIES"]>=500
    assert first.counts["UK_EQUITIES"]>=100 and first.counts["GERMAN_EQUITIES"]>=100 and first.counts["AUSTRALIAN_EQUITIES"]>=100

def test_registry_resolves_required_examples_and_preserves_distinct_listings():
    assert search_registry("SOL")[0]["underlying_market"]=="Solana"
    assert search_registry("Silver")[0]["canonical_symbol"]=="XAGUSD"
    assert {r["underlying_market"] for r in search_registry("OIL")}=={"West Texas Intermediate Crude Oil","Brent Crude Oil"}
    assert search_registry("SP500")[0]["canonical_symbol"]=="SPX"
    bhp=search_registry("BHP");assert len({r["registry_id"] for r in bhp})>=2

def test_fx_orientation_is_not_invented_and_unmapped_registration_is_operational():
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/"authority.sqlite3";initialize_database(db)
        market=discover_market(db,"USDEUR")["markets"][0];representation=market["representations"][0]
        assert market["canonical_identity"]=="FX:USDEUR" and market["fx_orientation"]["requested_provider_symbol"] is None
        plan=representation["registration_plan"];candidate=json.loads(base64.urlsafe_b64decode(plan["candidate"]))
        result=register_instrument(db,candidate_from_dict(candidate),registered_at_utc=datetime.now(UTC).isoformat())
        assert result.registration_status=="REGISTERED_UNMAPPED"
        with open_read_only(db) as connection:
            row=connection.execute("select provider_id,provider_symbol,registration_status from instrument_registrations where asset='USDEUR'").fetchone()
            assert row==(None,None,"REGISTERED_UNMAPPED")
