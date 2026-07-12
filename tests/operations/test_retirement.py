from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from fragarach_ii.estate_truth_service import estate_truth_state
from fragarach_ii.retirement import RetirementError,is_retired,retire_instrument,retirement_impact
from fragarach_ii.storage import open_read_only
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
if __name__=="__main__":unittest.main()
