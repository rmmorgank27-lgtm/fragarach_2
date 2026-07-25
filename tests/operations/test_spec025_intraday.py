from __future__ import annotations
import json,tempfile,unittest
from datetime import UTC,date,datetime
from pathlib import Path
from fragarach_ii.providers.http import HttpResponse
from fragarach_ii.providers.twelve_data import acquire_twelve_data
from fragarach_ii.providers.twelve_data_adapter import stage_twelve_data_response
from fragarach_ii.storage import RegistrationCandidate,initialize_database,open_read_only,register_instrument,verify_integrity
from fragarach_ii.lane_commissioning import ensure_commissioned_lane,market_policy
from fragarach_ii.truth_engine import truth_state_for_lane
from fragarach_ii.estate_truth_service import estate_truth_state
from fragarach_ii.external_consumer_service import HistoryService,INTRADAY_CONTRACT
from fragarach_ii.estate_timeframe_audit import audit_target_timeframes

NOW=datetime(2026,7,10,16,30,tzinfo=UTC)
class Transport:
    def __init__(self,body):self.body=body;self.requests=[]
    def send(self,request,credential,config):self.requests.append((request,config));return HttpResponse(200,"application/json",self.body,"api.twelvedata.com")

def candidate():return RegistrationCandidate(asset="AUDUSD",timeframe="D1",instrument_family="AUDUSD",local_symbol="AUDUSD",display_name="Australian Dollar / US Dollar",instrument_type="FX_SPOT_PAIR",asset_class="FX",representation_type="FX_SPOT_PAIR",trading_currency="USD",exchange_name="OTC",provider_id="TWELVE_DATA",provider_contract="TWELVE_DATA_TIME_SERIES_D1_V1",provider_symbol="AUD/USD",provider_instrument_type="Physical Currency",calendar_id="FX_D1_V1",calendar_version=1,gap_doctrine_id="FRAGARACH_II_D1_GAP_DOCTRINE_V1",gap_doctrine_version=1)

class Spec025IntradayTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"a.sqlite3";initialize_database(self.db);register_instrument(self.db,candidate(),registered_at_utc="2026-07-10T00:00:00+00:00")
    def tearDown(self):self.tmp.cleanup()
    def test_migration_8_preserves_v1_and_table_boundary(self):
        with open_read_only(self.db) as c:
            self.assertEqual(c.execute("select max(version) from schema_migrations").fetchone()[0],10)
            self.assertEqual(c.execute("select count(*) from sqlite_schema where type='table' and name not like 'sqlite_%'").fetchone()[0],12)
        self.assertTrue(verify_integrity(self.db).ok)
    def test_policy_is_separate_from_lane_state(self):
        self.assertEqual(market_policy("US_EQUITIES","H1"),"INTENTIONALLY_DEFERRED")
        ensure_commissioned_lane(self.db,"AUDUSD","H1",observed_at="2026-07-10T01:00:00+00:00")
        with open_read_only(self.db) as c:self.assertEqual(c.execute("select registration_timeframe from evidence_lanes where asset='AUDUSD' and timeframe='H1'").fetchone()[0],"D1")

    def test_crypto_uses_approved_continuous_authority(self):
        ensure_commissioned_lane(self.db,"BTCUSD","H1",observed_at="2026-07-10T01:00:00+00:00")
        capability=next(x for x in estate_truth_state(self.db)["timeframe_capabilities"] if x["symbol"]=="BTCUSD")
        self.assertEqual(capability["blocked_timeframes"],[])
        self.assertIn("H1",capability["active_timeframes"])

    def test_target_estate_audit_is_registration_derived_and_records_every_lane(self):
        audit=audit_target_timeframes(self.db)
        rows=[row for row in audit["rows"] if row["symbol"]=="BTCUSD"]
        self.assertEqual([row["timeframe"] for row in rows],["D1","H1","M30","M5"])
        self.assertEqual(rows[1]["missing_reason"],"EVIDENCE_LANE_NOT_DECLARED")
    def test_audusd_h1_chain_quarantines_bad_row_and_serves_truth(self):
        ensure_commissioned_lane(self.db,"AUDUSD","H1",observed_at="2026-07-10T01:00:00+00:00")
        body=json.dumps({"status":"ok","meta":{"symbol":"AUD/USD","interval":"1h"},"values":[
          {"datetime":"2026-07-10 09:00:00","open":"1","high":"2","low":"0.5","close":"1.5"},
          {"datetime":"2026-07-10 10:00:00","open":"1.5","high":"1.0","low":"0.5","close":"1.2"},
          {"datetime":"2026-07-10 11:00:00","open":"1.2","high":"2","low":"1","close":"1.8"}]},separators=(",",":")).encode()
        transport=Transport(body)
        result=acquire_twelve_data(self.db,asset="AUDUSD",timeframe="H1",from_date="2026-07-10",through_date="2026-07-10",credential="secret",transport=transport,clock=lambda:NOW,sleeper=lambda _:None)
        self.assertEqual((result.inserted,result.rejected),(2,1));self.assertIn("interval=1h",transport.requests[0][0].target);self.assertIn("timezone=America%2FNew_York",transport.requests[0][0].target)
        with open_read_only(self.db) as c:
            bars=c.execute("select open_time_utc,close_time_utc from bars where timeframe='H1' order by open_time_utc").fetchall();summary=json.loads(c.execute("select validation_summary from lane_state where timeframe='H1'").fetchone()[0])
            self.assertTrue(all(end-open_==3600 for open_,end in bars));self.assertEqual(summary["format"],"fragarach_ii.lane_validation_summary.v2")
        truth=truth_state_for_lane(self.db,symbol="AUDUSD",timeframe="H1");self.assertEqual(truth["caodt"],"2026-07-10T16:00:00+00:00")
        estate=estate_truth_state(self.db);self.assertIn("H1",next(x for x in estate["timeframe_capabilities"] if x["symbol"]=="AUDUSD")["servable_timeframes"])
        history=HistoryService(self.db).get_history("AUDUSD","H1");self.assertEqual((history["contract"],history["status"],history["bar_count"]),(INTRADAY_CONTRACT,"AVAILABLE",2))

    def test_fx_session_rejection_is_distinct_from_interval_alignment(self):
        response={"status":"ok","meta":{"symbol":"AUD/USD","interval":"1h"},"values":[
          {"datetime":"2026-07-12 12:00:00","open":"1","high":"2","low":"0.5","close":"1.5"},
          {"datetime":"2026-07-13 09:30:00","open":"1","high":"2","low":"0.5","close":"1.5"}]}
        batch=stage_twelve_data_response(json.dumps(response).encode(),asset="AUDUSD",provider_symbol="AUD/USD",from_date=date(2026,7,12),through_date=date(2026,7,13),raw_block_id="raw-session",received_at="2026-07-13T15:00:00+00:00",timeframe="H1",asset_class="FX",observed_at=datetime(2026,7,13,15,tzinfo=UTC))
        self.assertEqual([row.code for row in batch.rejections],["OUTSIDE_EXPECTED_SESSION","MISALIGNED_INTERVAL_OPEN"])

if __name__=="__main__":unittest.main()
