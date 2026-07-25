from __future__ import annotations
import tempfile,unittest
import base64,json
from fragarach_ii.fx_orientation import orientation_for,audit_fx_registrations,validate_direct_mapping
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.storage import register_instrument
from datetime import UTC,datetime
from pathlib import Path
from fragarach_ii.market_discovery import MARKET_DISCOVERY_CONTRACT,discover_market
import fragarach_ii.market_discovery as market_discovery
from fragarach_ii.provider_facts import load_provider_facts,save_provider_facts
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
    def test_bhp_provider_candidates_are_representation_aware_and_read_only(self):
        before=self.db.read_bytes()
        result=discover_market(self.db,"BHP")
        self.assertEqual(before,self.db.read_bytes())
        asx=next(m for m in result["markets"] if m["canonical_identity"]=="COMPANY:BHP:ASX")
        nyse=next(m for m in result["markets"] if m["canonical_identity"]=="COMPANY:BHP:NYSE")
        asx_rep=asx["representations"][0];nyse_rep=nyse["representations"][0]
        asx_mapping=asx["provider_discovery"][0];nyse_mapping=nyse["provider_discovery"][0]
        asx_plan=json.loads(base64.urlsafe_b64decode(asx_rep["registration_plan"]["candidate"]))
        nyse_plan=json.loads(base64.urlsafe_b64decode(nyse_rep["registration_plan"]["candidate"]))
        self.assertEqual((asx["recommendation"]["symbol"],asx_rep["symbol"],asx_rep["exchange"]),("ASX:BHP","ASX:BHP","ASX"))
        self.assertEqual((nyse["recommendation"]["symbol"],nyse_rep["symbol"],nyse_rep["exchange"]),("NYSE:BHP","NYSE:BHP","NYSE"))
        self.assertEqual((asx_mapping["provider"],asx_mapping["known_symbol"],asx_mapping["availability"]),("YAHOO_FINANCE","BHP.AX","REVIEW_REQUIRED"))
        self.assertEqual((nyse_mapping["provider"],nyse_mapping["known_symbol"],nyse_mapping["availability"]),("YAHOO_FINANCE","BHP","REVIEW_REQUIRED"))
        self.assertNotEqual(asx_mapping["known_symbol"],"BHP")
        self.assertNotEqual(nyse_mapping["known_symbol"],"BHP.AX")
        self.assertEqual((asx_plan["asset"],asx_plan["selected_representation"],asx_plan["provider_symbol"]),("ASXBHP","ASX:BHP","BHP.AX"))
        self.assertEqual((nyse_plan["asset"],nyse_plan["selected_representation"],nyse_plan["provider_symbol"]),("NYSEBHP","NYSE:BHP","BHP"))
        self.assertEqual(asx_plan["calendar_id"],"AUSTRALIAN_EQUITIES_D1_V1")
        self.assertEqual(nyse_plan["calendar_id"],"US_EQUITIES_D1_V1")
        self.assertEqual(nyse_rep["representation_type"],"DEPOSITARY_RECEIPT")
        self.assertEqual([lane["policy_state"] for lane in asx_rep["timeframe_lanes"]],["REQUIRED","INTENTIONALLY_DEFERRED","INTENTIONALLY_DEFERRED","INTENTIONALLY_DEFERRED"])
        self.assertEqual([lane["policy_state"] for lane in nyse_rep["timeframe_lanes"]],["REQUIRED","INTENTIONALLY_DEFERRED","INTENTIONALLY_DEFERRED","INTENTIONALLY_DEFERRED"])
    def test_yahoo_exchange_suffix_candidates_are_general_and_representation_scoped(self):
        rio=discover_market(self.db,"RIO")
        rio_markets={market["canonical_identity"]:market for market in rio["markets"]}
        self.assertTrue({"COMPANY:RIO:LSE","COMPANY:RIO:NYSE","COMPANY:RIO:ASX"}.issubset(rio_markets))
        cases=(
            (rio_markets["COMPANY:RIO:LSE"],"LSE:RIO","RIO.L","UK_EQUITIES_D1_V1"),
            (rio_markets["COMPANY:RIO:NYSE"],"NYSE:RIO","RIO","US_EQUITIES_D1_V1"),
            (rio_markets["COMPANY:RIO:ASX"],"ASX:RIO","RIO.AX","AUSTRALIAN_EQUITIES_D1_V1"),
        )
        for market,representation_symbol,provider_symbol,calendar in cases:
            representation=next(item for item in market["representations"] if item["symbol"]==representation_symbol)
            mapping=next(item for item in market["provider_discovery"] if item["representation_symbol"]==representation_symbol)
            plan=json.loads(base64.urlsafe_b64decode(representation["registration_plan"]["candidate"]))
            self.assertEqual(mapping["known_symbol"],provider_symbol)
            self.assertEqual(plan["selected_representation"],representation_symbol)
            self.assertEqual(plan["provider_symbol"],provider_symbol)
            self.assertEqual(plan["calendar_id"],calendar)
        self.assertNotEqual(cases[0][0]["provider_discovery"][0]["known_symbol"],"RIO")
        self.assertNotEqual(cases[2][0]["provider_discovery"][0]["known_symbol"],"RIO")
        hsba=discover_market(self.db,"HSBA")
        hsba_market=hsba["markets"][0]
        hsba_rep=hsba_market["representations"][0]
        hsba_plan=json.loads(base64.urlsafe_b64decode(hsba_rep["registration_plan"]["candidate"]))
        self.assertEqual(hsba_market["provider_discovery"][0]["known_symbol"],"HSBA.L")
        self.assertEqual(hsba_plan["selected_representation"],"LSE:HSBA")
        self.assertEqual(hsba_plan["provider_symbol"],"HSBA.L")
        self.assertEqual(hsba_plan["calendar_id"],"UK_EQUITIES_D1_V1")
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
        lanes=self.market("JPYCHF")["representations"][0]["timeframe_lanes"];self.assertEqual([l["timeframe"] for l in lanes],["D1","H1","M30","M5"])
        self.assertEqual(lanes[0]["provider_capability"],"SUPPORTED");self.assertTrue(all(l["provider_capability"]=="SUPPORTED" for l in lanes));self.assertTrue(all(l["registration_state"]=="IMPLEMENTATION_INCOMPATIBILITY" for l in lanes[1:]));self.assertTrue(all(l["authority_state"]=="READY_FOR_LANE_COMMISSIONING" for l in lanes[1:]))
        crypto=self.market("SOLUSD")["representations"][0]["timeframe_lanes"];self.assertTrue(all(l["provider_capability"]=="SUPPORTED_WITH_APPROVED_MAPPING" for l in crypto[1:]));self.assertTrue(all(l["selectable"] for l in crypto[1:]))
        apple=self.market("Apple")["representations"][0]["timeframe_lanes"];self.assertTrue(all(l["provider_capability"]=="INTENTIONALLY_DEFERRED" for l in apple[1:]));self.assertTrue(all(l["policy_state"]=="INTENTIONALLY_DEFERRED" for l in apple[1:]));self.assertTrue(all(not l["selectable"] for l in apple[1:]))
    def test_runtime_exact_fx_mapping_is_available_to_non_estate_discovery(self):
        facts=load_provider_facts(self.db)
        facts["mappings"]["TWELVE_DATA:EURNZD"]={
            "canonical_symbol":"EURNZD","provider":"TWELVE_DATA","provider_symbol":"EUR/NZD",
            "provider_instrument_type":"Physical Currency","mapping_class":"EXACT_REPRESENTATION",
            "status":"RESOLVED_AUTOMATICALLY",
        }
        save_provider_facts(self.db,facts)
        representation=self.market("EURNZD")["representations"][0]
        self.assertEqual((representation["provider_mapping_status"],representation["provider"],representation["provider_symbol"]),("APPROVED_REPRESENTATION","TWELVE_DATA","EUR/NZD"))
        self.assertEqual(representation["acquisition_readiness"],"READY_FOR_REGISTRATION")
    def test_crypto_catalogue_exact_mapping_unlocks_all_required_lanes(self):
        original=market_discovery._twelve_data_crypto_catalogue_mapping
        market_discovery._twelve_data_crypto_catalogue_mapping=lambda record: {
            "provider":"TWELVE_DATA","provider_symbol":"DOGE/USD",
            "provider_instrument_type":"Digital Currency","catalogue_verified":True,
        } if record["canonical_symbol"]=="DOGEUSD" else None
        try:
            representation=discover_market(
                self.db,"DOGEUSD",resolve_crypto_catalogue=True
            )["markets"][0]["representations"][0]
        finally:
            market_discovery._twelve_data_crypto_catalogue_mapping=original
        self.assertEqual(
            (representation["provider"],representation["provider_symbol"],
             representation["provider_mapping_status"],representation["acquisition_readiness"]),
            ("TWELVE_DATA","DOGE/USD","KNOWN_MAPPING","READY_FOR_REGISTRATION"),
        )
        self.assertEqual(
            [(lane["timeframe"],lane["provider_capability"],lane["selectable"]) for lane in representation["timeframe_lanes"]],
            [("D1","SUPPORTED_WITH_APPROVED_MAPPING",True),("H1","SUPPORTED_WITH_APPROVED_MAPPING",True),("M30","SUPPORTED_WITH_APPROVED_MAPPING",True),("M5","SUPPORTED_WITH_APPROVED_MAPPING",True)],
        )
    def test_fx_orientation_is_exact_and_ordered(self):
        direct=self.market("EUR/AUD");inverse=self.market("AUD-EUR");spaced=self.market("AUD EUR")
        self.assertEqual((direct["canonical_identity"],direct["fx_orientation"]["orientation_state"],direct["fx_orientation"]["requested_provider_symbol"]),("FX:EURAUD","DIRECT_PROVIDER_SUPPORTED","EUR/AUD"))
        for market in (inverse,spaced):
            self.assertEqual((market["canonical_identity"],market["fx_orientation"]["base_currency"],market["fx_orientation"]["quote_currency"]),("FX:AUDEUR","AUD","EUR"));self.assertEqual(market["fx_orientation"]["orientation_state"],"INVERSE_ONLY");self.assertIsNone(market["fx_orientation"]["requested_provider_symbol"]);self.assertEqual(market["fx_orientation"]["inverse_pair"],"EURAUD");self.assertIsNotNone(market["representations"][0]["registration_plan"]);self.assertEqual(market["representations"][0]["provider_mapping_status"],"DISCOVERY_REQUIRED");self.assertTrue(all(l["provider_capability"]=="INVERSE_ONLY" for l in market["representations"][0]["timeframe_lanes"]))
        unknown=self.market("CADNZD")["fx_orientation"];self.assertEqual(unknown["orientation_state"],"PROVIDER_CAPABILITY_UNKNOWN");self.assertIsNone(unknown["requested_provider_symbol"])
    def test_mapping_fixture_can_support_both_orientations(self):
        mappings={"EURAUD":"EUR/AUD","AUDEUR":"AUD/EUR"};self.assertEqual(orientation_for("EURAUD",mappings)["orientation_state"],"DIRECT_PROVIDER_SUPPORTED");self.assertEqual(orientation_for("AUDEUR",mappings)["requested_provider_symbol"],"AUD/EUR")
    def test_registration_guard_and_read_only_audit(self):
        with self.assertRaisesRegex(ValueError,"INVERSE_ONLY_NOT_DIRECTLY_REGISTERABLE"):validate_direct_mapping("AUDEUR","TWELVE_DATA","EUR/AUD")
        plan=self.market("EURAUD")["representations"][0]["registration_plan"];value=json.loads(base64.urlsafe_b64decode(plan["candidate"]));value.update(asset="AUDEUR",instrument_family="AUDEUR",local_symbol="AUDEUR",provider_symbol="AUD/EUR",trading_currency="EUR")
        register_instrument(self.db,candidate_from_dict(value),registered_at_utc=datetime.now(UTC).isoformat());before=self.db.read_bytes();audit=audit_fx_registrations(self.db);self.assertEqual(audit["registrations"][0]["audit_state"],"SYNTHETIC_PROVIDER_SYMBOL");self.assertEqual(audit["mutations_performed"],0);self.assertEqual(before,self.db.read_bytes())
if __name__=="__main__":unittest.main()
