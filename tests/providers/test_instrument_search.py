from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from fragarach_ii.providers.http import HttpResponse
from fragarach_ii.providers.instrument_search import InstrumentSearchError,search_instrument
from fragarach_ii.storage import initialize_database,open_read_only,register_instrument

class Transport:
    def __init__(self,rows,status=200):self.rows=rows;self.status=status;self.request=None
    def send(self,request,credential,config):
        self.request=request;return HttpResponse(self.status,"application/json",json.dumps({"data":self.rows}).encode(),request.host)

class InstrumentSearchTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"authority.sqlite3";initialize_database(self.db)
    def tearDown(self):self.tmp.cleanup()
    def test_supported_review_is_read_only_and_deterministic(self):
        before=self.db.read_bytes();transport=Transport([{"symbol":"ETH/USD","instrument_name":"Ethereum / US Dollar","instrument_type":"Digital Currency","exchange":"Coinbase Pro","currency":"USD"}])
        result=search_instrument(str(self.db),"ETHUSD",credential="secret",transport=transport)
        self.assertTrue(result.found);self.assertFalse(result.already_registered);self.assertEqual((result.candidate.asset,result.candidate.calendar_id),("ETHUSD","CRYPTO_D1_V1"));self.assertNotIn("secret",transport.request.target);self.assertEqual(before,self.db.read_bytes())
    def test_unknown_and_unsupported_are_factual(self):
        self.assertFalse(search_instrument(str(self.db),"NOPE",credential="secret",transport=Transport([])).found)
        with self.assertRaisesRegex(InstrumentSearchError,"Calendar unavailable"):
            search_instrument(str(self.db),"AAPL",credential="secret",transport=Transport([{"symbol":"AAPL","instrument_name":"Apple Inc.","instrument_type":"Common Stock","exchange":"NASDAQ","currency":"USD"}]))
    def test_registration_then_existing_search_reports_authority_status(self):
        reviewed=search_instrument(str(self.db),"ETHUSD",credential="secret",transport=Transport([{"symbol":"ETH/USD","instrument_name":"Ethereum / US Dollar","instrument_type":"Digital Currency","exchange":"Coinbase Pro","currency":"USD"}]))
        result=register_instrument(self.db,reviewed.candidate,registered_at_utc="2026-07-11T00:00:00+00:00")
        self.assertEqual((result.outcome,result.registration_status),("INSERTED","REGISTERED_NO_EVIDENCE"))
        existing=search_instrument(str(self.db),"ETHUSD",credential=None);self.assertTrue(existing.already_registered);self.assertEqual(existing.registration_status,"REGISTERED_NO_EVIDENCE")
        c=open_read_only(self.db)
        try:self.assertEqual(c.execute("SELECT count(*) FROM instrument_registrations WHERE asset='ETHUSD'").fetchone()[0],1)
        finally:c.close()

if __name__=="__main__":unittest.main()
