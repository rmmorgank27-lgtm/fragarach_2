from __future__ import annotations
import tempfile
from datetime import UTC,datetime
from pathlib import Path
import base64,json
from contextlib import redirect_stdout
from io import StringIO
from fragarach_ii.market_registry import load_registry,provider_mapping,search_registry
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.commands.register_instrument import main as register_command
from fragarach_ii.commands.register_instrument import _retry_when_writer_busy
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.storage import initialize_database,open_read_only,registered_writer,register_instrument
from fragarach_ii.storage import WriterLockError
from fragarach_ii.storage.migrations import apply_migrations

APPROVED_FOREX_PAIRS = {
    "AUDUSD", "AUDCAD", "AUDNZD", "AUDJPY", "GBPAUD", "GBPUSD", "GBPJPY", "GBPNZD",
    "EURAUD", "EURUSD", "EURGBP", "EURJPY", "AUDCHF", "GBPCHF", "EURCHF", "CHFJPY",
    "NZDJPY", "EURNZD", "NZDUSD", "USDCAD", "USDMXN", "USDSGD", "AUDSGD", "GBPSGD",
    "EURSGD", "USDBRL", "USDSEK", "USDNOK", "USDINR", "USDKRW", "USDDKK",
}
EVIDENCED_FOREX_PAIRS = {"AUDUSD", "EURAUD", "EURGBP", "NZDJPY"}

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

def test_approved_forex_universe_is_exact_ordered_and_fully_discoverable():
    snapshot=load_registry()
    records={r["canonical_symbol"]:r for r in snapshot.records if r["asset_class"]=="FX"}
    assert set(records)==APPROVED_FOREX_PAIRS
    assert all(pair[3:]+pair[:3] not in records for pair in records)
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/"authority.sqlite3";initialize_database(db)
        for pair,record in records.items():
            assert record["base_currency"]==pair[:3]
            assert record["quote_currency"]==pair[3:]
            assert record["canonical_identity"]==f"FX:{pair}"
            assert discover_market(db,pair)["markets"][0]["canonical_identity"]==f"FX:{pair}"

def test_forex_provider_mappings_are_known_only_where_evidenced():
    snapshot=load_registry()
    records=[r for r in snapshot.records if r["asset_class"]=="FX"]
    known={r["canonical_symbol"] for r in records if provider_mapping(snapshot,r["registry_id"])}
    assert known==EVIDENCED_FOREX_PAIRS
    mappings={m["registry_id"]:m for m in snapshot.mappings if m["registry_id"].startswith("fx:")}
    assert len(mappings)==31
    assert all(mappings[r["registry_id"]]["mapping_state"]==("KNOWN_MAPPING" if r["canonical_symbol"] in known else "UNKNOWN") for r in records)
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/"authority.sqlite3";initialize_database(db)
        representation=discover_market(db,"USDMXN")["markets"][0]["representations"][0]
        candidate=json.loads(base64.urlsafe_b64decode(representation["registration_plan"]["candidate"]))
        result=register_instrument(db,candidate_from_dict(candidate),registered_at_utc=datetime.now(UTC).isoformat())
        assert result.registration_status=="REGISTERED_UNMAPPED"

def test_registration_command_migrates_v6_and_preserves_fx_mapping_discovery_outcome():
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/"authority.sqlite3"
        with registered_writer(db) as connection:apply_migrations(connection,target_version=6)
        plan=discover_market(db,"EURUSD")["markets"][0]["representations"][0]["registration_plan"]
        output=StringIO()
        with redirect_stdout(output):exit_code=register_command(["--database",str(db),"--candidate",plan["candidate"],"--json"])
        assert exit_code==0
        receipt=json.loads(output.getvalue())
        assert receipt["registration_status"] in {"REGISTERED_UNMAPPED","REGISTERED_NO_EVIDENCE"}
        with open_read_only(db) as connection:
            assert connection.execute("select max(version) from schema_migrations").fetchone()[0]==10
            provider,status=connection.execute("select provider_id,registration_status from instrument_registrations where asset='EURUSD'").fetchone()
        assert (provider,status)==(None,"REGISTERED_UNMAPPED") or (provider=="TWELVE_DATA" and status=="REGISTERED_NO_EVIDENCE")

def test_registration_command_keeps_mapped_fx_registration_available():
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/"authority.sqlite3";initialize_database(db)
        plan=discover_market(db,"EURAUD")["markets"][0]["representations"][0]["registration_plan"]
        output=StringIO()
        with redirect_stdout(output):exit_code=register_command(["--database",str(db),"--candidate",plan["candidate"],"--json"])
        assert exit_code==0
        assert json.loads(output.getvalue())["registration_status"]=="REGISTERED_NO_EVIDENCE"


def test_registration_retries_short_scheduler_writer_contention() -> None:
    attempts=[]
    def operation():
        attempts.append(1)
        if len(attempts)<3: raise WriterLockError(Path("/tmp/authority.writer.lock"))
        return {"outcome":"INSERTED"}
    assert _retry_when_writer_busy(operation,sleeper=lambda _delay:None)=={"outcome":"INSERTED"}
    assert len(attempts)==3
