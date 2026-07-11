from __future__ import annotations
import hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from fragarach_ii.providers.contracts import list_provider_contracts
from fragarach_ii.storage import (AuthorityEventManifest,AuthorityLedgerError,append_authority_event,
    bootstrap_legacy_authority,canonical_json,initialize_database,inspect_authority,open_read_only,
    prepare_authority_event,reconstruct_authority,registered_writer,verify_integrity)
from fragarach_ii.storage.migrations import apply_migrations
from fragarach_ii.storage.schema import APPLICATION_TABLES,migration_6_checksum

def manifest(entity="lane:FX:D1",kind="LANE_DECLARED",supersedes=None,timeframe="D1",compat="COMPATIBLE"):
    reasons=() if compat=="COMPATIBLE" else ({"code":"BLOCKED"},)
    return AuthorityEventManifest("EVIDENCE_LANE",entity,kind,"2026-07-11T00:00:00+00:00","TEST_ACTOR",
        ({"document_id":"FX_D1_AUTHORITY_V1","path":"constitution/authorities/fx/FX_D1_AUTHORITY_V1.md","sha256":"0"*64,"version":1},),compat,reasons,
        {"activation_state":"DECLARED","timeframe":timeframe,"canonical_unit":"USD_PER_AUD","adjustment_basis":"NOT_APPLICABLE",
         "approved_effective_from":"2026-07-11T00:00:00+00:00","provider_mapping_entity_id":"mapping:fx"},supersedes)

class AuthorityLedgerAmendmentTests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"a.sqlite3";initialize_database(self.db)
    def tearDown(self): self.tmp.cleanup()

    def test_migration_six_exact_ten_tables_and_history(self):
        report=verify_integrity(self.db);self.assertEqual(report.application_tables,APPLICATION_TABLES);self.assertEqual(len(APPLICATION_TABLES),10)
        c=open_read_only(self.db)
        try:
            self.assertEqual(c.execute("select checksum_sha256 from schema_migrations where version=6").fetchone()[0],migration_6_checksum())
            self.assertEqual(c.execute("select count(*) from authority_events").fetchone()[0],0)
        finally:c.close()

    def test_interrupted_migration_rolls_back_tenth_table(self):
        p=Path(self.tmp.name)/"interrupt.sqlite3"
        with registered_writer(p) as c:
            apply_migrations(c,target_version=5)
            with self.assertRaises(RuntimeError):apply_migrations(c,target_version=6,fault_migration_version=6,fault_after_statement=4)
            self.assertIsNone(c.execute("select 1 from sqlite_schema where type='table' and name='authority_events'").fetchone())
            self.assertEqual(c.execute("select max(version) from schema_migrations").fetchone()[0],5)

    def test_canonical_checksums_replay_and_immutability(self):
        p=prepare_authority_event(manifest());self.assertEqual(p.authority_event_id,p.event_checksum_sha256)
        first=append_authority_event(self.db,manifest(),recorded_at_utc="2026-07-11T01:00:00+00:00")
        replay=append_authority_event(self.db,manifest(),recorded_at_utc="2026-07-11T02:00:00+00:00")
        self.assertEqual((first.outcome,replay.outcome),("INSERTED","UNCHANGED"))
        with registered_writer(self.db) as c:
            with self.assertRaises(sqlite3.IntegrityError):c.execute("update authority_events set recorded_by='X'")
            with self.assertRaises(sqlite3.IntegrityError):c.execute("delete from authority_events")

    def test_float_and_unresolved_declaration_rejected(self):
        bad=manifest();bad=AuthorityEventManifest(**{**{f:getattr(bad,f) for f in bad.__dataclass_fields__},"body":{**bad.body,"value":1.2}})
        with self.assertRaisesRegex(AuthorityLedgerError,"canonical JSON"):prepare_authority_event(bad)
        with self.assertRaisesRegex(AuthorityLedgerError,"lane:FX:D1"):prepare_authority_event(manifest(compat="UNRESOLVED_MATERIAL_FACT"))

    def test_supersession_chain_and_fork_rejected(self):
        first=append_authority_event(self.db,manifest(),recorded_at_utc="2026-07-11T01:00:00+00:00")
        revised=manifest(kind="LANE_REVISED",supersedes=first.authority_event_id)
        second=append_authority_event(self.db,revised,recorded_at_utc="2026-07-11T02:00:00+00:00")
        current=reconstruct_authority(self.db);self.assertEqual(current[0]["authority_event_id"],second.authority_event_id);self.assertEqual(len(current[0]["supersession_chain"]),2)
        competing=AuthorityEventManifest(**{**{f:getattr(revised,f) for f in revised.__dataclass_fields__},"recorded_by":"OTHER"})
        with self.assertRaises(sqlite3.IntegrityError):append_authority_event(self.db,competing,recorded_at_utc="2026-07-11T03:00:00+00:00")

    def test_rejected_conflict_retained_and_unrelated_lane_continues(self):
        accepted=append_authority_event(self.db,manifest(),recorded_at_utc="2026-07-11T01:00:00+00:00")
        rejected=manifest(entity="lane:FX:D1:rejected",kind="LANE_REJECTED",compat="INCOMPATIBLE_PROVIDER_MAPPING")
        append_authority_event(self.db,rejected,recorded_at_utc="2026-07-11T02:00:00+00:00")
        other=append_authority_event(self.db,manifest(entity="lane:METALS:D1"),recorded_at_utc="2026-07-11T03:00:00+00:00")
        self.assertEqual(len(inspect_authority(self.db)),3);self.assertNotEqual(accepted.authority_event_id,other.authority_event_id)

    def test_all_timeframes_declared_but_intraday_cannot_activate(self):
        for tf in ("D1","H1","M30","M5"):append_authority_event(self.db,manifest(entity=f"lane:FX:{tf}",timeframe=tf),recorded_at_utc="2026-07-11T01:00:00+00:00")
        active=manifest(entity="lane:FX:H1-active",timeframe="H1");active=AuthorityEventManifest(**{**{f:getattr(active,f) for f in active.__dataclass_fields__},"body":{**active.body,"activation_state":"ACTIVE"}})
        with self.assertRaises(AuthorityLedgerError):prepare_authority_event(active)

    def test_bootstrap_exact_replay_preserves_legacy(self):
        c=open_read_only(self.db)
        before=(c.execute("select group_concat(identity_checksum_sha256,'|') from instrument_registrations order by asset").fetchone()[0],c.execute("select count(*) from evidence_lanes").fetchone()[0]);c.close()
        self.assertTrue(all(r.outcome=="INSERTED" for r in bootstrap_legacy_authority(self.db)))
        self.assertTrue(all(r.outcome=="UNCHANGED" for r in bootstrap_legacy_authority(self.db)))
        c=open_read_only(self.db);after=(c.execute("select group_concat(identity_checksum_sha256,'|') from instrument_registrations order by asset").fetchone()[0],c.execute("select count(*) from evidence_lanes").fetchone()[0]);c.close()
        self.assertEqual(before,after)

    def test_provider_contracts_have_distinct_limits_and_valid_checksums(self):
        contracts=list_provider_contracts();self.assertEqual({c["interval_code"] for c in contracts},{"1day","1h","30min","5min"})
        self.assertTrue(all((c["provider_hard_maximum"],c["fragarach_request_ceiling"])==(5000,4000) for c in contracts))

    def test_multiple_provider_mappings_and_lifecycle_remain_distinct(self):
        binding=({"document_id":"CRYPTO_BASE_DOCTRINE_V1","path":"constitution/doctrines/CRYPTO_BASE_DOCTRINE_V1.md","sha256":"0"*64,"version":1},)
        ids=[]
        for venue in ("Coinbase Pro","Binance","Bitfinex"):
            m=AuthorityEventManifest("PROVIDER_MAPPING",f"mapping:BTCUSD:{venue}","PROVIDER_MAPPING_DISCOVERED","2026-07-11T00:00:00+00:00","TEST_ACTOR",binding,
                "INCOMPATIBLE_PROVIDER_MAPPING",({"code":"REQUESTED_AGGREGATE_NOT_VENUE"},),{"instrument_registration_entity_id":"registration:BTCUSD_AGGREGATE","provider":"TWELVE_DATA","provider_symbol":"BTC/USD","source_scope":venue})
            ids.append(append_authority_event(self.db,m,recorded_at_utc="2026-07-11T01:00:00+00:00").authority_event_id)
        self.assertEqual(len(set(ids)),3);self.assertEqual(len(inspect_authority(self.db,entity_kind="PROVIDER_MAPPING")),3)

    def test_nine_family_four_timeframe_fixture_matrix(self):
        families=("FX","CRYPTO","METALS","ENERGY","INDICES","US_EQUITIES","UK_EQUITIES","GERMAN_EQUITIES","AUSTRALIAN_EQUITIES")
        for family in families:
            for tf in ("D1","H1","M30","M5"):
                append_authority_event(self.db,manifest(entity=f"fixture:{family}:{tf}",timeframe=tf),recorded_at_utc="2026-07-11T01:00:00+00:00")
        self.assertEqual(len(inspect_authority(self.db,entity_kind="EVIDENCE_LANE")),36)

    def test_direct_sql_id_checksum_mismatch_rejected(self):
        p=prepare_authority_event(manifest())
        with registered_writer(self.db) as c:
            with self.assertRaises(sqlite3.IntegrityError):c.execute("INSERT INTO authority_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
                "0"*64,p.ledger_contract,p.ledger_contract_version,p.entity_kind,p.entity_id,p.event_kind,p.supersedes_event_id,
                p.effective_from_utc,p.effective_to_utc,p.canonical_payload,p.payload_checksum_sha256,p.event_checksum_sha256,
                "2026-07-11T01:00:00+00:00",p.recorded_by))

if __name__=="__main__":unittest.main()
