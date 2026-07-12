from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from fragarach_ii.market_discovery import MARKET_DISCOVERY_CONTRACT,discover_market
from fragarach_ii.storage import initialize_database
from tests.validation.test_d1_session_validation import _create_lane

class MarketDiscoveryTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"authority.sqlite3";initialize_database(self.db)
    def tearDown(self):self.tmp.cleanup()
    def market(self,query):return discover_market(self.db,query)["markets"][0]
    def test_dow_aliases_and_multiple_representations(self):
        for query,symbol,kind in (("US30","US30","CFD"),("DJI","DJI","INDEX"),("DIA","DIA","ETF"),("YM","YM","FUTURES"),("Dow","DJI","INDEX")):
            result=discover_market(self.db,query);self.assertEqual(result["contract"],MARKET_DISCOVERY_CONTRACT);market=result["markets"][0];self.assertEqual(market["recommendation"]["symbol"],symbol);self.assertEqual(market["recommendation"]["representation_type"],kind);self.assertGreaterEqual(len(market["representations"]),5)
    def test_sp500_commodity_currency_and_company_aliases(self):
        self.assertEqual(self.market("SPX500")["recommendation"]["representation_type"],"CFD")
        self.assertEqual(self.market("WTI")["asset_class"],"ENERGY")
        self.assertEqual(self.market("Gold")["recommendation"]["symbol"],"XAUUSD")
        self.assertEqual(self.market("AUDJPY")["market_type"],"FOREIGN_EXCHANGE")
        self.assertEqual(self.market("Tesla")["recommendation"]["symbol"],"TSLA")
    def test_provider_discovery_and_recommendation_are_informational(self):
        before=self.db.read_bytes();market=self.market("DIA");mapping=next(p for p in market["provider_discovery"] if p["representation_symbol"]=="DIA")
        self.assertEqual((mapping["provider"],mapping["availability"],mapping["supported_timeframes"],mapping["entitlement"]),("TWELVE_DATA","KNOWN_MAPPING",("D1",),"NOT_MEASURED"));self.assertEqual(before,self.db.read_bytes())
    def test_bhp_remains_ambiguous(self):
        result=discover_market(self.db,"BHP");self.assertEqual(result["discovery_status"],"AMBIGUOUS");self.assertEqual([m["canonical_identity"] for m in result["markets"]],["COMPANY:BHP:ASX","COMPANY:BHP:NYSE"])
    def test_existing_registration_and_truth_are_exposed(self):
        self.tmp.cleanup();self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"authority.sqlite3";_create_lane(self.db,"XAUUSD",["2026-07-10"]);before=self.db.read_bytes();market=self.market("Gold")
        self.assertEqual(market["acquisition_readiness"],"OPEN_EXISTING");existing=market["existing_registrations"][0];self.assertIsNotNone(existing["truth_score"]);self.assertIsNotNone(existing["caodt"]);self.assertEqual(before,self.db.read_bytes())
    def test_unknown_is_final_and_helpful(self):
        result=discover_market(self.db,"Unobtainium");self.assertEqual(result["discovery_status"],"UNKNOWN");self.assertTrue(result["suggested_searches"]);self.assertTrue(result["operator_guidance"])
if __name__=="__main__":unittest.main()
