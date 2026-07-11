from __future__ import annotations
import sqlite3,tempfile,unittest
from pathlib import Path
from fragarach_ii.storage import initialize_database,open_read_only,registered_writer,transaction,verify_integrity
from fragarach_ii.storage.migrations import apply_migrations
from fragarach_ii.storage.schema import APPLICATION_TABLES,migration_5_checksum

class EvidenceLaneFoundationTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"authority.sqlite3";initialize_database(self.db)
    def tearDown(self):self.tmp.cleanup()

    def test_migration_five_backfills_only_existing_d1_lanes_without_registration_change(self):
        report=verify_integrity(self.db);self.assertEqual((len(APPLICATION_TABLES),report.application_tables),(9,APPLICATION_TABLES))
        c=open_read_only(self.db)
        try:
            self.assertEqual(c.execute("SELECT checksum_sha256 FROM schema_migrations WHERE version=5").fetchone()[0],migration_5_checksum())
            self.assertEqual(c.execute("SELECT asset,timeframe,registration_timeframe,lane_contract FROM evidence_lanes ORDER BY asset").fetchall(),[("AUDUSD","D1","D1","EVIDENCE_LANE_V1"),("BTCUSD","D1","D1","EVIDENCE_LANE_V1"),("XAUUSD","D1","D1","EVIDENCE_LANE_V1")])
            self.assertEqual(c.execute("SELECT asset,timeframe,identity_checksum_sha256 FROM instrument_registrations ORDER BY asset").fetchall(),[("AUDUSD","D1","20c0355ae9ca4b6e1ffe6f24f5dc7920d036757e132c3e33e1648d5a86b7730f"),("BTCUSD","D1","f3bbb3d7770a3ae0668d8b2a68e0e224df91123c4cff96e226e0223429a1042b"),("XAUUSD","D1","f296a6ed305bc12146b6ed84a2fee22fcb70f1697889100c6ebaaa06074d136a")])
        finally:c.close()

    def test_lane_is_immutable_registration_backed_and_authorizes_only_its_identity(self):
        with registered_writer(self.db) as c:
            with self.assertRaises(sqlite3.IntegrityError):c.execute("INSERT INTO evidence_lanes VALUES('NOPE','M5','D1','EVIDENCE_LANE_V1',1,'2026-07-11T00:00:00+00:00')")
            c.execute("INSERT INTO evidence_lanes VALUES('AUDUSD','M5','D1','EVIDENCE_LANE_V1',1,'2026-07-11T00:00:00+00:00')")
            with self.assertRaises(sqlite3.IntegrityError):c.execute("UPDATE evidence_lanes SET timeframe='M30' WHERE asset='AUDUSD' AND timeframe='M5'")
            with self.assertRaises(sqlite3.IntegrityError):c.execute("DELETE FROM evidence_lanes WHERE asset='AUDUSD' AND timeframe='M5'")
            with transaction(c):
                c.execute("INSERT INTO ingest_runs VALUES('r','foundation-proof','active','2026-07-11T00:00:00+00:00',NULL,NULL,NULL)")
                c.execute("INSERT INTO bars VALUES('AUDUSD','M5',1,NULL,'1','1','1','1',NULL,'r','r')")
                c.execute("UPDATE ingest_runs SET status='committed',finished_at_utc='2026-07-11T00:00:01+00:00' WHERE ingest_run_id='r'")
            with self.assertRaises(sqlite3.IntegrityError):c.execute("INSERT INTO bars VALUES('AUDUSD','M30',2,NULL,'1','1','1','1',NULL,'r','r')")

    def test_interrupted_migration_rolls_back_table_and_restores_old_bar_guards(self):
        path=Path(self.tmp.name)/"interrupted.sqlite3"
        with registered_writer(path) as c:
            apply_migrations(c,target_version=4)
            with self.assertRaisesRegex(RuntimeError,"injected migration interruption"):
                apply_migrations(c,target_version=5,fault_migration_version=5,fault_after_statement=4)
            self.assertIsNone(c.execute("SELECT 1 FROM sqlite_schema WHERE type='table' AND name='evidence_lanes'").fetchone())
            names={r[0] for r in c.execute("SELECT name FROM sqlite_schema WHERE type='trigger'")}
            self.assertIn("bars_require_registration_insert",names);self.assertNotIn("bars_require_evidence_lane_insert",names)
            self.assertEqual(c.execute("SELECT max(version) FROM schema_migrations").fetchone()[0],4)

if __name__=="__main__":unittest.main()
