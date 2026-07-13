from __future__ import annotations
import base64,json,tempfile
from datetime import UTC,datetime
from pathlib import Path
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.providers.resolution import acquire_resolved
from fragarach_ii.storage import initialize_database,open_read_only,register_instrument

class FailingTwelve:
    def send(self,*args,**kwargs):raise OSError("forced Twelve Data failure")

def yahoo_payload(symbol="EURUSD=X"):
    return json.dumps({"chart":{"result":[{"meta":{"symbol":symbol},"timestamp":[1783382400,1783468800],"indicators":{"quote":[{"open":[1.1,1.2],"high":[1.2,1.3],"low":[1.0,1.1],"close":[1.15,1.25],"volume":[0,0]}]}}],"error":None}}).encode()

def register(db:Path,symbol:str):
    plan=discover_market(db,symbol)["markets"][0]["representations"][0]["registration_plan"]
    candidate=json.loads(base64.urlsafe_b64decode(plan["candidate"]))
    return register_instrument(db,candidate_from_dict(candidate),registered_at_utc=datetime.now(UTC).isoformat())

def test_first_provider_failure_continues_to_yahoo_and_persists_confirmed_mapping():
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/"authority.sqlite3";initialize_database(db);register(db,"EURUSD")
        result=acquire_resolved(db,asset="EURUSD",from_date="2026-07-01",through_date="2026-07-11",merge_mode="preserve",credential="test",twelve_transport=FailingTwelve(),yahoo_fetch=lambda _:yahoo_payload())
        assert result["provider_id"]=="YAHOO_FINANCE"
        assert [a["result"] for a in result["provider_attempts"]]==["FAILED","SUCCESS"]
        with open_read_only(db) as connection:
            assert connection.execute("select count(*) from bars where asset='EURUSD'").fetchone()[0]==2
            detail=json.loads(connection.execute("select detail from ingest_runs where status='committed' order by finished_at_utc desc limit 1").fetchone()[0])
            assert (detail["provider"],detail["provider_symbol"],detail["mapping_state"])==("YAHOO_FINANCE","EURUSD=X","CONFIRMED_BY_VALID_EVIDENCE")

def test_yahoo_rejects_inverse_or_mismatched_fx_symbol():
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/"authority.sqlite3";initialize_database(db);register(db,"EURUSD")
        try:acquire_resolved(db,asset="EURUSD",from_date="2026-07-01",through_date="2026-07-11",merge_mode="preserve",credential=None,twelve_transport=FailingTwelve(),yahoo_fetch=lambda _:yahoo_payload("USDEUR=X"))
        except Exception as error:assert "No provider returned valid data" in str(error)
        else:raise AssertionError("mismatched inverse evidence was accepted")

def test_unmapped_registration_evidence_confirmation_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/"authority.sqlite3";initialize_database(db);register(db,"EURUSD")
        arguments=dict(database_path=db,asset="EURUSD",from_date="2026-07-01",through_date="2026-07-11",merge_mode="preserve",credential=None,twelve_transport=FailingTwelve(),yahoo_fetch=lambda _:yahoo_payload())
        first=acquire_resolved(**arguments)
        with open_read_only(db) as connection:
            first_confirmation=connection.execute("select evidence_confirmed_at_utc from instrument_registrations where asset='EURUSD' and timeframe='D1'").fetchone()[0]
        second=acquire_resolved(**arguments)
        with open_read_only(db) as connection:
            registration=connection.execute("select registration_status,evidence_confirmed_at_utc from instrument_registrations where asset='EURUSD' and timeframe='D1'").fetchone()
        assert first["provider_symbol"]==second["provider_symbol"]=="EURUSD=X"
        assert second["unchanged"]==2
        assert registration==("REGISTERED_UNMAPPED",first_confirmation)
