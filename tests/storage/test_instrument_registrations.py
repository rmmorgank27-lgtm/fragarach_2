from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.storage import (Alias, RegistrationCandidate, RegistrationError,
    canonical_registration, initialize_database, open_read_only, register_instrument,
    registered_writer, transaction, verify_integrity)
from fragarach_ii.storage.schema import APPLICATION_TABLES, migration_4_checksum
from fragarach_ii.storage.migrations import apply_migrations
from fragarach_ii.ingestion.manual import ingest_manual_file


def candidate(asset="DOWJONES.DJI", local="DJI", aliases=()):
    return RegistrationCandidate(asset=asset,timeframe="D1",instrument_family="DOWJONES",local_symbol=local,
        aliases=aliases,display_name="Dow Jones Industrial Average",instrument_type="CASH_INDEX",asset_class="EQUITY_INDEX",
        representation_type="INDEX",underlying_reference="Dow Jones Industrial Average",trading_currency="USD",
        exchange_name="NASDAQ Global Index Data Service",provider_id="TWELVE_DATA",
        provider_contract="TWELVE_DATA_TIME_SERIES_D1_V1",provider_symbol="DJI",provider_instrument_type="Index",
        calendar_id="US_EQUITY_D1_V1",calendar_version=1,gap_doctrine_id="FRAGARACH_II_D1_GAP_DOCTRINE_V1",gap_doctrine_version=1)


class InstrumentRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/"authority.sqlite3";initialize_database(self.db)
    def tearDown(self): self.tmp.cleanup()

    def test_migration_checksum_eight_tables_and_initial_catalogue(self):
        report=verify_integrity(self.db);self.assertEqual(report.application_tables,APPLICATION_TABLES);self.assertEqual(len(APPLICATION_TABLES),8)
        c=open_read_only(self.db)
        try:
            self.assertEqual(c.execute("SELECT checksum_sha256 FROM schema_migrations WHERE version=4").fetchone()[0],migration_4_checksum())
            self.assertEqual(c.execute("SELECT asset,registration_status FROM instrument_registrations ORDER BY asset").fetchall(),[("AUDUSD","REGISTERED_NO_EVIDENCE"),("BTCUSD","REGISTERED_NO_EVIDENCE"),("XAUUSD","REGISTERED_NO_EVIDENCE")])
        finally:c.close()

    def test_canonical_json_alias_order_and_checksum_are_deterministic(self):
        aliases=(Alias("DJIA","DJIA","COMMON_NAME"),)
        first=canonical_registration(candidate(aliases=aliases));second=canonical_registration(candidate(aliases=aliases))
        self.assertEqual(first,second);self.assertEqual(json.loads(first[0])[0]["normalized_alias"],"DJIA");self.assertEqual(len(first[3]),64)

    def test_registration_idempotence_and_canonical_collision(self):
        c=candidate();one=register_instrument(self.db,c,registered_at_utc="2026-07-11T00:00:00+00:00");two=register_instrument(self.db,c,registered_at_utc="2026-07-12T00:00:00+00:00")
        self.assertEqual((one.outcome,two.outcome),("INSERTED","EXISTING_IDENTICAL"))
        values={name:getattr(c,name) for name in c.__dataclass_fields__};values["display_name"]="Different"
        with self.assertRaisesRegex(RegistrationError,"DOWJONES.DJI"):
            register_instrument(self.db,RegistrationCandidate(**values),registered_at_utc="2026-07-11T00:00:00+00:00")

    def test_sqlite_immutable_delete_provider_and_alias_collisions(self):
        register_instrument(self.db,candidate(aliases=(Alias("DJIA","DJIA","COMMON_NAME"),)),registered_at_utc="2026-07-11T00:00:00+00:00")
        with registered_writer(self.db) as c:
            with self.assertRaises(sqlite3.IntegrityError):c.execute("UPDATE instrument_registrations SET display_name='x' WHERE asset='DOWJONES.DJI'")
            with self.assertRaises(sqlite3.IntegrityError):c.execute("DELETE FROM instrument_registrations WHERE asset='DOWJONES.DJI'")
        other=candidate(asset="OTHER.DJIA",local="DJIA")
        with self.assertRaises(RegistrationError):register_instrument(self.db,other,registered_at_utc="2026-07-11T00:00:00+00:00")

    def test_unregistered_bar_rejected_and_factual_status_transition(self):
        with registered_writer(self.db) as c:
            with self.assertRaises(sqlite3.IntegrityError):c.execute("INSERT INTO bars VALUES('NOPE','D1',1,NULL,'1','1','1','1',NULL,'x','x')")
        register_instrument(self.db,candidate(),registered_at_utc="2026-07-11T00:00:00+00:00")
        with registered_writer(self.db) as c:
            with transaction(c):
                c.execute("INSERT INTO ingest_runs VALUES('r','test','active','2026-07-11T00:00:00+00:00',NULL,NULL,NULL)")
                c.execute("INSERT INTO bars VALUES('DOWJONES.DJI','D1',1,NULL,'1','1','1','1',NULL,'r','r')")
                c.execute("UPDATE instrument_registrations SET registration_status='REGISTERED_WITH_EVIDENCE',evidence_confirmed_at_utc='2026-07-11T00:00:01+00:00' WHERE asset='DOWJONES.DJI'")
                c.execute("UPDATE ingest_runs SET status='committed',finished_at_utc='2026-07-11T00:00:01+00:00' WHERE ingest_run_id='r'")
            with self.assertRaises(sqlite3.IntegrityError):c.execute("UPDATE instrument_registrations SET registration_status='REGISTERED_NO_EVIDENCE',evidence_confirmed_at_utc=NULL WHERE asset='DOWJONES.DJI'")

    def test_constraints_reject_invalid_family_currency_mic_and_futures(self):
        for changes in ({"asset":"lower"},{"trading_currency":"usd"},{"exchange_mic":"bad"},{"representation_type":"FUTURES"}):
            base=candidate();values={name:getattr(base,name) for name in base.__dataclass_fields__};values.update(changes)
            with self.assertRaises(RegistrationError):canonical_registration(RegistrationCandidate(**values))

    def test_migration_four_interruption_rolls_back_to_seven_tables(self):
        path=Path(self.tmp.name)/"interrupted.sqlite3"
        with registered_writer(path) as c:
            apply_migrations(c,target_version=3)
            with self.assertRaisesRegex(RuntimeError,"interruption"):
                apply_migrations(c,target_version=4,fault_migration_version=4,fault_after_statement=2)
            tables={r[0] for r in c.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            self.assertNotIn("instrument_registrations",tables);self.assertEqual(c.execute("SELECT max(version) FROM schema_migrations").fetchone()[0],3)

    def test_manual_unregistered_lane_rejects_before_evidence_mutation(self):
        source=Path(self.tmp.name)/"eur.csv";source.write_text("timestamp,open,high,low,close\n2026-07-10,1,1,1,1\n")
        with self.assertRaisesRegex(ValueError,"UNREGISTERED_LANE"):
            ingest_manual_file(self.db,source,symbol="EURUSD",timeframe="D1")
        c=open_read_only(self.db)
        try:self.assertEqual(tuple(c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("bars","raw_blocks","provenance","ingest_runs","lane_state")),(0,0,0,0,0))
        finally:c.close()

if __name__=="__main__":unittest.main()
