from __future__ import annotations
import tempfile,unittest
import base64,json
from fragarach_ii.fx_orientation import orientation_for,audit_fx_registrations,validate_direct_mapping
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.storage import register_instrument
from datetime import UTC,datetime
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
    def test_repaired_silver_and_alphabet_catalogue(self):
        for query in ("XAGUSD","XAG/USD"):
            result=discover_market(self.db,query);market=result["markets"][0]
            self.assertEqual(market["underlying_market"],"Silver");self.assertEqual(market["recommendation"]["symbol"],"XAGUSD")
            self.assertNotIn("West Texas",json.dumps(result))
        silver=self.market("Silver");self.assertEqual({"XAGUSD","SI","SLV"}-{r["symbol"] for r in silver["representations"]},set());self.assertTrue(silver["required_operator_decisions"])
        google=self.market("google");self.assertEqual(google["underlying_market"],"Alphabet Inc.");self.assertEqual({r["symbol"] for r in google["representations"]},{"GOOG","GOOGL"});self.assertTrue(google["required_operator_decisions"]);self.assertNotIn('"Gold"',json.dumps(google))
    def test_selection_plan_is_reviewable_deterministic_and_unknown_is_non_mutating(self):
        first=self.market("XAGUSD");second=self.market("XAGUSD");plan=first["representations"][0]["registration_plan"]
        self.assertEqual(plan,second["representations"][0]["registration_plan"]);candidate=json.loads(base64.urlsafe_b64decode(plan["candidate"]))
        self.assertEqual((candidate["asset"],candidate["provider_symbol"]),("XAGUSD","XAG/USD"));self.assertIn("ADD_TO_FRAGARACH",first["available_actions"])
        before=self.db.read_bytes();unknown=discover_market(self.db,"QZXNOTAMARKET");self.assertEqual(unknown["similar_markets"],());self.assertEqual(before,self.db.read_bytes())
    def test_oil_family_is_ambiguous(self):
        result=discover_market(self.db,"OIL");self.assertEqual(result["discovery_status"],"AMBIGUOUS");self.assertEqual({m["canonical_identity"] for m in result["markets"]},{"COMMODITY:WTI","COMMODITY:BRENT"})
        self.assertTrue(all(m["recommendation"]["symbol"]=="" for m in result["markets"]))
        wti=next(m for m in result["markets"] if m["canonical_identity"]=="COMMODITY:WTI");self.assertEqual({"USOIL","CL","USO"}-{r["symbol"] for r in wti["representations"]},set())
    def test_solana_aliases_and_restricted_correction(self):
        for query,symbol in (("SOL",None),("Solana",None),("SOLUSD","SOLUSD"),("SOL/USD","SOLUSD"),("SOLUSDT","SOLUSDT"),("SOL/USDT","SOLUSDT")):
            result=discover_market(self.db,query);self.assertEqual(result["markets"][0]["underlying_market"],"Solana")
            if symbol:self.assertEqual(result["markets"][0]["recommendation"]["symbol"],symbol)
        correction=discover_market(self.db,"solanna");self.assertEqual(correction["discovery_status"],"PARTIAL");self.assertEqual(correction["explanation"],"Did you mean Solana?")
        self.assertEqual(discover_market(self.db,"golanna")["discovery_status"],"UNKNOWN")
    def test_timeframe_capability_is_explicit_and_schema_blocked(self):
        for query in ("JPYCHF","SOLUSD"):
            lanes=self.market(query)["representations"][0]["timeframe_lanes"];self.assertEqual([l["timeframe"] for l in lanes],["D1","H1","M30","M5"])
            self.assertEqual(lanes[0]["provider_capability"],"SUPPORTED");self.assertTrue(all(l["provider_capability"]=="SUPPORTED" for l in lanes));self.assertTrue(all(l["registration_state"]=="IMPLEMENTATION_INCOMPATIBILITY" for l in lanes[1:]));self.assertTrue(all(l["authority_state"]=="IMPLEMENTATION_NARROWER_THAN_RATIFIED_AUTHORITY" for l in lanes[1:]))
        apple=self.market("Apple")["representations"][0]["timeframe_lanes"];self.assertTrue(all(l["provider_capability"]=="CAPABILITY_UNKNOWN" for l in apple[1:]))
    def test_fx_orientation_is_exact_and_ordered(self):
        direct=self.market("EUR/AUD");inverse=self.market("AUD-EUR");spaced=self.market("AUD EUR")
        self.assertEqual((direct["canonical_identity"],direct["fx_orientation"]["orientation_state"],direct["fx_orientation"]["requested_provider_symbol"]),("FX:EURAUD","DIRECT_PROVIDER_SUPPORTED","EUR/AUD"))
        for market in (inverse,spaced):
            self.assertEqual((market["canonical_identity"],market["fx_orientation"]["base_currency"],market["fx_orientation"]["quote_currency"]),("FX:AUDEUR","AUD","EUR"));self.assertEqual(market["fx_orientation"]["orientation_state"],"INVERSE_ONLY");self.assertIsNone(market["fx_orientation"]["requested_provider_symbol"]);self.assertEqual(market["fx_orientation"]["inverse_pair"],"EURAUD");self.assertIsNone(market["representations"][0]["registration_plan"]);self.assertTrue(all(l["provider_capability"]=="INVERSE_ONLY" for l in market["representations"][0]["timeframe_lanes"]))
        unknown=self.market("CADNZD")["fx_orientation"];self.assertEqual(unknown["orientation_state"],"PROVIDER_CAPABILITY_UNKNOWN");self.assertIsNone(unknown["requested_provider_symbol"])
    def test_mapping_fixture_can_support_both_orientations(self):
        mappings={"EURAUD":"EUR/AUD","AUDEUR":"AUD/EUR"};self.assertEqual(orientation_for("EURAUD",mappings)["orientation_state"],"DIRECT_PROVIDER_SUPPORTED");self.assertEqual(orientation_for("AUDEUR",mappings)["requested_provider_symbol"],"AUD/EUR")
    def test_registration_guard_and_read_only_audit(self):
        with self.assertRaisesRegex(ValueError,"INVERSE_ONLY_NOT_DIRECTLY_REGISTERABLE"):validate_direct_mapping("AUDEUR","TWELVE_DATA","EUR/AUD")
        plan=self.market("EURAUD")["representations"][0]["registration_plan"];value=json.loads(base64.urlsafe_b64decode(plan["candidate"]));value.update(asset="AUDEUR",instrument_family="AUDEUR",local_symbol="AUDEUR",provider_symbol="AUD/EUR",trading_currency="EUR")
        register_instrument(self.db,candidate_from_dict(value),registered_at_utc=datetime.now(UTC).isoformat());before=self.db.read_bytes();audit=audit_fx_registrations(self.db);self.assertEqual(audit["registrations"][0]["audit_state"],"SYNTHETIC_PROVIDER_SYMBOL");self.assertEqual(audit["mutations_performed"],0);self.assertEqual(before,self.db.read_bytes())
if __name__=="__main__":unittest.main()
