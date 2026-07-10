from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.ingestion.manual import IngestionFailure, ingest_manual_file
from fragarach_ii.storage import open_read_only


NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
HEADER = "timestamp,open,high,low,close,volume\n"


class IngestionRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = self.root / "authority.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, name: str, rows: str) -> Path:
        path = self.root / name
        path.write_text(HEADER + rows, encoding="utf-8")
        return path

    def ingest(self, path: Path, **overrides: object):
        arguments = {
            "symbol": "AUDUSD",
            "timeframe": "D1",
            "clock": lambda: NOW,
        }
        arguments.update(overrides)
        return ingest_manual_file(self.database, path, **arguments)

    def test_forced_failure_rolls_back_bars_provenance_and_lane(self) -> None:
        baseline = self.write("baseline.csv", "2026-07-08,1,2,0,1,\n")
        self.ingest(baseline)
        connection = open_read_only(self.database)
        try:
            before = (
                connection.execute("SELECT count(*) FROM bars").fetchone()[0],
                connection.execute("SELECT count(*) FROM provenance").fetchone()[0],
                connection.execute("SELECT state_version FROM lane_state").fetchone()[0],
            )
        finally:
            connection.close()

        incoming = self.write(
            "incoming.csv",
            "2026-07-09,1,2,0,1,\n2026-07-10,1,2,0,1,\n",
        )

        def interrupt(_connection: sqlite3.Connection) -> None:
            raise RuntimeError("forced before commit")

        with self.assertRaisesRegex(IngestionFailure, "forced before commit") as raised:
            self.ingest(incoming, before_commit=interrupt)

        connection = open_read_only(self.database)
        try:
            after = (
                connection.execute("SELECT count(*) FROM bars").fetchone()[0],
                connection.execute("SELECT count(*) FROM provenance").fetchone()[0],
                connection.execute("SELECT state_version FROM lane_state").fetchone()[0],
            )
            self.assertEqual(after, before)
            failed = connection.execute(
                "SELECT status, raw_block_id, detail FROM ingest_runs WHERE ingest_run_id = ?",
                (raised.exception.ingest_run_id,),
            ).fetchone()
            self.assertEqual(failed[:2], ("failed", raised.exception.raw_block_id))
            self.assertIn("forced before commit", failed[2])
        finally:
            connection.close()

    def test_active_readers_keep_snapshot_during_import(self) -> None:
        source = self.write(
            "reader.csv",
            "2026-07-09,1,2,0,1,\n2026-07-10,1,2,0,1,\n",
        )
        # Initialize with a rejected attempt so readers can open an existing database.
        invalid = self.write("invalid.csv", "07/09/26,1,2,0,1,\n")
        self.ingest(invalid)
        readers = [open_read_only(self.database) for _ in range(6)]
        try:
            for reader in readers:
                reader.execute("BEGIN")
                self.assertEqual(reader.execute("SELECT count(*) FROM bars").fetchone()[0], 0)
            self.ingest(source)
            for reader in readers:
                self.assertEqual(reader.execute("SELECT count(*) FROM bars").fetchone()[0], 0)
                reader.commit()
                self.assertEqual(reader.execute("SELECT count(*) FROM bars").fetchone()[0], 2)
        finally:
            for reader in readers:
                reader.close()

    def test_read_only_consumer_cannot_change_bars_or_lane_state(self) -> None:
        source = self.write("readonly.csv", "2026-07-09,1,2,0,1,\n")
        self.ingest(source)
        consumer = open_read_only(self.database)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                consumer.execute("UPDATE bars SET close = '9'")
            with self.assertRaises(sqlite3.OperationalError):
                consumer.execute("UPDATE lane_state SET state_version = 99")
        finally:
            consumer.close()


if __name__ == "__main__":
    unittest.main()

