from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fragarach_ii.identity_resolver import IDENTITY_CONTRACT, resolve_instrument
from fragarach_ii.storage import initialize_database
from tests.validation.test_d1_session_validation import _create_lane


class IdentityResolverTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"authority.sqlite3";initialize_database(self.db)
    def tearDown(self):self.tmp.cleanup()

    def test_currency_pair_and_alias_resolution_are_deterministic(self):
        first=resolve_instrument(self.db,"AUD/JPY");second=resolve_instrument(self.db,"AUD/JPY")
        self.assertEqual(first,second);self.assertEqual(first.contract,IDENTITY_CONTRACT)
        self.assertEqual((first.identity_status,first.matches[0].canonical_symbol,first.confidence),("KNOWN","AUDJPY",99))
        gold=resolve_instrument(self.db,"Gold");self.assertEqual((gold.matches[0].canonical_symbol,gold.confidence),("XAUUSD",98))

    def test_company_partial_and_ambiguous_identity(self):
        apple=resolve_instrument(self.db,"Apple");self.assertEqual(apple.matches[0].canonical_symbol,"NASDAQ:AAPL");self.assertGreaterEqual(apple.confidence,95)
        bhp=resolve_instrument(self.db,"BHP");self.assertEqual(bhp.identity_status,"AMBIGUOUS");self.assertEqual([m.canonical_symbol for m in bhp.matches],["ASX:BHP","NYSE:BHP"])

    def test_index_crypto_commodity_and_preliminary_metadata(self):
        self.assertEqual(resolve_instrument(self.db,"Dow").matches[0].asset_class,"INDICES")
        eth=resolve_instrument(self.db,"ETH").matches[0];self.assertEqual((eth.base_currency,eth.quote_currency),("ETH","USD"))
        gold=resolve_instrument(self.db,"Gold").matches[0];self.assertEqual((gold.market,gold.known_exchange,gold.timezone),("OTC","OTC","UTC"))

    def test_unknown_is_helpful_and_does_not_create_authority(self):
        before=self.db.read_bytes();result=resolve_instrument(self.db,"Unobtainium Futures")
        self.assertEqual(result.identity_status,"UNKNOWN");self.assertEqual(result.matches,())
        self.assertTrue(result.suggested_searches);self.assertTrue(result.suggested_providers);self.assertTrue(result.suggested_aliases)
        self.assertEqual(before,self.db.read_bytes())

    def test_existing_registration_returns_truth_without_mutation(self):
        self.tmp.cleanup();self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"authority.sqlite3"
        _create_lane(self.db,"AUDUSD",["2026-07-10"]);before=self.db.read_bytes()
        result=resolve_instrument(self.db,"AUD/USD");match=result.matches[0]
        self.assertEqual(match.registration_state,"REGISTERED");self.assertIsNotNone(match.current_truth_score);self.assertIsNotNone(match.current_caodt)
        self.assertEqual(before,self.db.read_bytes())


if __name__=="__main__":unittest.main()
