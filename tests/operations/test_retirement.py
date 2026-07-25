from __future__ import annotations
import base64,json,tempfile,unittest
from datetime import UTC,datetime
from pathlib import Path
from fragarach_ii.estate_truth_service import estate_truth_state
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.retirement import (RetirementError,is_permanently_removed,is_retired,
    permanent_removal_impact,permanently_remove_instrument,reactivate_instrument,
    retire_instrument,retirement_impact)
from fragarach_ii.storage import initialize_database,open_read_only,register_instrument
from fragarach_ii.truth_engine import TruthEngineError,truth_state_for_lane
from fragarach_ii.providers import AcquisitionError,acquire_twelve_data
from tests.validation.test_d1_session_validation import _create_lane

class RetirementTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"authority.sqlite3";_create_lane(self.db,"AUDUSD",["2026-07-01","2026-07-02"])
    def tearDown(self):self.tmp.cleanup()
    def counts(self):
        c=open_read_only(self.db)
        try:return tuple(c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("instrument_registrations","evidence_lanes","bars","raw_blocks","provenance","ingest_runs","authority_events"))
        finally:c.close()
    def test_plan_is_read_only_and_high_impact_requires_confirmation(self):
        before=self.db.read_bytes();plan=retirement_impact(self.db,"AUDUSD");self.assertEqual((plan["canonical_bars"],plan["active_timeframe_lanes"]),(2,("D1",)));self.assertEqual(plan["required_confirmation"],"RETIRE AUDUSD");self.assertEqual(before,self.db.read_bytes())
        with self.assertRaisesRegex(RetirementError,"RETIRE AUDUSD"):retire_instrument(self.db,"AUDUSD",scope="WHOLE_INSTRUMENT",selected_lanes=("D1",),reason="INCORRECT_INSTRUMENT_IDENTITY",operator_note="",typed_confirmation="AUDUSD")
    def test_retirement_preserves_history_and_excludes_active_truth(self):
        before=self.counts();receipt=retire_instrument(self.db,"AUDUSD",scope="WHOLE_INSTRUMENT",selected_lanes=("D1",),reason="INCORRECT_INSTRUMENT_IDENTITY",operator_note="operator reviewed",typed_confirmation="RETIRE AUDUSD",completed_at="2026-07-12T04:00:00+00:00");after=self.counts()
        self.assertEqual(receipt["outcome"],"RETIRED");self.assertTrue(is_retired(self.db,"AUDUSD","D1"));self.assertEqual(after[:6],before[:6]);self.assertEqual(after[6],before[6]+4);self.assertNotIn("AUDUSD",[x["symbol"] for x in estate_truth_state(self.db)["truth_matrix"]])
        with self.assertRaises(TruthEngineError) as raised:truth_state_for_lane(self.db,symbol="AUDUSD",timeframe="D1")
        self.assertEqual(raised.exception.code,"RETIRED_LANE")
        class NoTransport:
            requests=[]
            def send(self,*_):self.requests.append(1);raise AssertionError("provider called")
        transport=NoTransport()
        with self.assertRaises(AcquisitionError) as blocked:acquire_twelve_data(self.db,asset="AUDUSD",timeframe="D1",from_date="2026-07-01",through_date="2026-07-02",credential="secret",transport=transport)
        self.assertEqual(blocked.exception.code,"INSTRUMENT_RETIRED");self.assertEqual(transport.requests,[]);self.assertEqual(self.counts(),after)
        repeat=retire_instrument(self.db,"AUDUSD",scope="WHOLE_INSTRUMENT",selected_lanes=("D1",),reason="INCORRECT_INSTRUMENT_IDENTITY",operator_note="operator reviewed",typed_confirmation="RETIRE AUDUSD",completed_at="2026-07-12T04:00:00+00:00");self.assertEqual(repeat["outcome"],"ALREADY_RETIRED_IDENTICAL")
    def test_reason_and_other_note_are_controlled(self):
        with self.assertRaises(RetirementError):retire_instrument(self.db,"AUDUSD",scope="WHOLE_INSTRUMENT",selected_lanes=("D1",),reason="",operator_note="",typed_confirmation="RETIRE AUDUSD")
        with self.assertRaises(RetirementError):retire_instrument(self.db,"AUDUSD",scope="WHOLE_INSTRUMENT",selected_lanes=("D1",),reason="OTHER_REVIEWED_REASON",operator_note="",typed_confirmation="RETIRE AUDUSD")
    def test_reactivation_preserves_evidence_and_restores_truth(self):
        before=self.counts();retire_instrument(self.db,"AUDUSD",scope="WHOLE_INSTRUMENT",selected_lanes=("D1",),reason="OTHER_REVIEWED_REASON",operator_note="temporary retirement",typed_confirmation="RETIRE AUDUSD",completed_at="2026-07-12T04:00:00+00:00")
        receipt=reactivate_instrument(self.db,"AUDUSD",reactivated_at="2026-07-13T04:00:00+00:00")
        self.assertEqual((receipt["outcome"],receipt["new_authority_state"]),("REACTIVATED","ACTIVE"));self.assertFalse(is_retired(self.db,"AUDUSD","D1"));self.assertEqual(self.counts()[:6],before[:6]);self.assertEqual(truth_state_for_lane(self.db,symbol="AUDUSD",timeframe="D1")["symbol"],"AUDUSD")
    def test_permanent_removal_refuses_immutable_evidence(self):
        retire_instrument(self.db,"AUDUSD",scope="WHOLE_INSTRUMENT",selected_lanes=("D1",),reason="OTHER_REVIEWED_REASON",operator_note="temporary retirement",typed_confirmation="RETIRE AUDUSD")
        impact=permanent_removal_impact(self.db,"AUDUSD");self.assertFalse(impact["removable"])
        with self.assertRaisesRegex(RetirementError,"immutable"):permanently_remove_instrument(self.db,"AUDUSD",typed_confirmation="PERMANENTLY REMOVE AUDUSD")

class EvidenceFreeRemovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"authority.sqlite3";initialize_database(self.db)
        representation=next(r for r in discover_market(self.db,"XAGUSD")["markets"][0]["representations"] if r["symbol"]=="XAGUSD")
        payload=json.loads(base64.urlsafe_b64decode(representation["registration_plan"]["candidate"]));self.candidate=candidate_from_dict(payload)
        register_instrument(self.db,self.candidate,registered_at_utc="2026-07-13T00:00:00+00:00")
    def tearDown(self):self.tmp.cleanup()
    def test_explicit_removal_then_fresh_registration_without_duplicates(self):
        retire_instrument(self.db,"XAGUSD",scope="WHOLE_INSTRUMENT",selected_lanes=("D1",),reason="ERRONEOUS_OPERATOR_REGISTRATION",operator_note="test registration",typed_confirmation="")
        before=open_read_only(self.db)
        try:registration_count=before.execute("SELECT count(*) FROM instrument_registrations WHERE asset='XAGUSD'").fetchone()[0]
        finally:before.close()
        with self.assertRaisesRegex(RetirementError,"PERMANENTLY REMOVE XAGUSD"):permanently_remove_instrument(self.db,"XAGUSD",typed_confirmation="REMOVE XAGUSD")
        receipt=permanently_remove_instrument(self.db,"XAGUSD",typed_confirmation="PERMANENTLY REMOVE XAGUSD")
        self.assertEqual(receipt["outcome"],"PERMANENTLY_REMOVED");self.assertTrue(is_permanently_removed(self.db,"XAGUSD","D1"));self.assertEqual(discover_market(self.db,"XAGUSD")["markets"][0]["available_actions"],("ADD_TO_FRAGARACH",))
        class NoTransport:
            requests=[]
            def send(self,*_):self.requests.append(1);raise AssertionError("provider called")
        transport=NoTransport()
        with self.assertRaises(AcquisitionError) as blocked:acquire_twelve_data(self.db,asset="XAGUSD",timeframe="D1",from_date="2026-07-01",through_date="2026-07-02",credential="secret",transport=transport)
        self.assertEqual(blocked.exception.code,"INSTRUMENT_REMOVED");self.assertEqual(transport.requests,[])
        result=register_instrument(self.db,self.candidate,registered_at_utc="2026-07-15T05:00:00+00:00")
        self.assertEqual(result.outcome,"REREGISTERED_AFTER_REMOVAL");self.assertFalse(is_permanently_removed(self.db,"XAGUSD","D1"));self.assertFalse(is_retired(self.db,"XAGUSD","D1"))
        after=open_read_only(self.db)
        try:self.assertEqual(after.execute("SELECT count(*) FROM instrument_registrations WHERE asset='XAGUSD'").fetchone()[0],registration_count)
        finally:after.close()
if __name__=="__main__":unittest.main()
