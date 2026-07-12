from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.ingestion.manual import ingest_manual_file
from fragarach_ii.storage import open_read_only, verify_integrity


FIXED_NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
HEADER = "timestamp,open,high,low,close,volume\n"


class ManualIngestionTests(unittest.TestCase):
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
            "clock": lambda: FIXED_NOW,
        }
        arguments.update(overrides)
        return ingest_manual_file(self.database, path, **arguments)

    def test_clean_import_raw_bars_provenance_run_and_lane_agree(self) -> None:
        source = self.write(
            "AUDUSD_D1.csv",
            "2026-07-08,1,2,0,1.5,10\n2026-07-09,1.5,3,1,2,11\n",
        )
        payload = source.read_bytes()
        result = self.ingest(source)
        self.assertEqual(result.transaction_state, "committed")
        self.assertEqual((result.source_rows, result.staged, result.accepted), (2, 2, 2))
        self.assertEqual((result.inserted, result.canonical_count), (2, 2))
        connection = open_read_only(self.database)
        try:
            raw = connection.execute(
                "SELECT payload, byte_length FROM raw_blocks WHERE raw_block_id = ?",
                (result.raw_block_id,),
            ).fetchone()
            self.assertEqual(raw, (payload, len(payload)))
            self.assertEqual(connection.execute("SELECT count(*) FROM bars").fetchone()[0], 2)
            self.assertEqual(
                connection.execute(
                    "SELECT merge_action FROM provenance ORDER BY timestamp"
                ).fetchall(),
                [("INSERT",), ("INSERT",)],
            )
            run = connection.execute(
                "SELECT status, raw_block_id, detail FROM ingest_runs WHERE ingest_run_id = ?",
                (result.ingest_run_id,),
            ).fetchone()
            self.assertEqual(run[:2], ("committed", result.raw_block_id))
            self.assertEqual(json.loads(run[2])["inserted"], 2)
            lane = connection.execute(
                """
                SELECT high_watermark_open_time_utc, state_version, last_ingest_run_id
                FROM lane_state WHERE asset = 'AUDUSD' AND timeframe = 'D1'
                """
            ).fetchone()
            self.assertEqual(lane[1:], (1, result.ingest_run_id))
        finally:
            connection.close()
        self.assertTrue(verify_integrity(self.database).ok)

    def test_identical_bytes_and_different_filename_are_idempotent(self) -> None:
        first = self.write("first.csv", "2026-07-09,1,2,0,1,\n")
        second = self.root / "renamed.csv"
        second.write_bytes(first.read_bytes())
        initial = self.ingest(first)
        repeated = self.ingest(second)
        self.assertEqual(initial.raw_block_id, repeated.raw_block_id)
        self.assertFalse(initial.raw_block_reused)
        self.assertTrue(repeated.raw_block_reused)
        self.assertEqual((repeated.inserted, repeated.unchanged), (0, 1))
        self.assertNotEqual(initial.ingest_run_id, repeated.ingest_run_id)
        connection = open_read_only(self.database)
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM raw_blocks").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM bars").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM ingest_runs").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT count(*) FROM provenance").fetchone()[0], 2)
        finally:
            connection.close()

    def test_overlapping_and_shallow_tails_never_truncate_history(self) -> None:
        deep = self.write(
            "deep.csv",
            "2026-07-06,1,2,0,1,\n"
            "2026-07-07,1,2,0,1,\n"
            "2026-07-08,1,2,0,1,\n",
        )
        tail = self.write(
            "tail.csv",
            "2026-07-08,1,2,0,1,\n2026-07-09,1,2,0,1,\n",
        )
        self.ingest(deep)
        result = self.ingest(tail)
        self.assertEqual((result.inserted, result.unchanged, result.canonical_count), (1, 1, 4))
        connection = open_read_only(self.database)
        try:
            dates = connection.execute(
                "SELECT open_time_utc FROM bars ORDER BY open_time_utc"
            ).fetchall()
            self.assertEqual(len(dates), 4)
        finally:
            connection.close()

    def test_preserved_conflict_then_explicit_correction_has_full_lineage(self) -> None:
        original = self.write("original.csv", "2026-07-09,1,2,0,1,10\n")
        changed = self.write("changed.csv", "2026-07-09,1,2,0,1.5,11\n")
        initial = self.ingest(original)
        preserved = self.ingest(changed)
        self.assertEqual(preserved.conflicts_preserved, 1)
        connection = open_read_only(self.database)
        try:
            self.assertEqual(connection.execute("SELECT close FROM bars").fetchone()[0], "1")
        finally:
            connection.close()

        corrected = self.ingest(changed, merge_mode="correct")
        self.assertEqual(corrected.corrected, 1)
        connection = open_read_only(self.database)
        try:
            self.assertEqual(connection.execute("SELECT close FROM bars").fetchone()[0], "1.5")
            events = connection.execute(
                """
                SELECT merge_action, candidate_close, prior_close, supersedes_event_id,
                       provenance_event_id
                FROM provenance ORDER BY rowid
                """
            ).fetchall()
            self.assertEqual([row[0] for row in events], ["INSERT", "CONFLICT_PRESERVED", "CORRECTED"])
            self.assertEqual(events[1][1:3], ("1.5", "1"))
            self.assertEqual(events[2][1:3], ("1.5", "1"))
            self.assertEqual(events[2][3], events[0][4])
            self.assertNotEqual(initial.ingest_run_id, corrected.ingest_run_id)
        finally:
            connection.close()

    def test_duplicate_and_invalid_rows_reject_without_canonical_contamination(self) -> None:
        conflicting = self.write(
            "duplicates.csv",
            "2026-07-09,1,2,0,1,\n2026-07-09,1,2,0,1.5,\n",
        )
        result = self.ingest(conflicting)
        self.assertEqual(result.transaction_state, "failed")
        self.assertEqual(result.duplicate_conflicting, 1)
        invalid = self.write("invalid.csv", "07/09/26,1,0,2,1,-1\n")
        invalid_result = self.ingest(invalid)
        self.assertEqual(invalid_result.transaction_state, "failed")
        connection = open_read_only(self.database)
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM bars").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(*) FROM raw_blocks").fetchone()[0], 2)
            self.assertEqual(
                connection.execute("SELECT status FROM ingest_runs ORDER BY started_at_utc").fetchall(),
                [("failed",), ("failed",)],
            )
        finally:
            connection.close()

    def test_exact_duplicate_rows_collapse_deterministically(self) -> None:
        source = self.write(
            "exact.csv",
            "2026-07-09,1.0,2,0,1,\n2026-07-09,1,2.0,0.0,1.0,\n",
        )
        result = self.ingest(source)
        self.assertEqual(result.duplicate_identical, 1)
        self.assertEqual((result.source_rows, result.staged, result.inserted), (2, 1, 1))

    def test_valid_rows_commit_while_invalid_row_is_quarantined(self) -> None:
        source = self.write(
            "partial.csv",
            "2026-07-07,1,2,0,1.5,10\n"
            "2026-07-08,2,3,1.6,1.5,11\n"
            "2026-07-09,1.5,3,1,2,12\n",
        )
        payload=source.read_bytes();result=self.ingest(source)
        self.assertEqual(result.transaction_state,"COMPLETED_WITH_WARNINGS")
        self.assertEqual((result.source_rows,result.staged,result.accepted,result.inserted,result.rejected),(3,2,2,2,1))
        self.assertEqual(result.rejections,({"source_row_number":3,"code":"INVALID_OHLC","message":"low is above close"},))
        with open_read_only(self.database) as connection:
            self.assertEqual(connection.execute("select payload from raw_blocks where raw_block_id=?",(result.raw_block_id,)).fetchone()[0],payload)
            status,detail=connection.execute("select status,detail from ingest_runs where ingest_run_id=?",(result.ingest_run_id,)).fetchone()
            self.assertEqual(status,"committed")
            self.assertEqual(json.loads(detail)["rejections"],[{"code":"INVALID_OHLC","message":"low is above close","source_row_number":3}])

    def test_restart_preserves_all_evidence_and_history(self) -> None:
        source = self.write("restart.csv", "2026-07-09,1,2,0,1,10\n")
        result = self.ingest(source)
        connection = open_read_only(self.database)
        connection.close()
        reopened = open_read_only(self.database)
        try:
            self.assertEqual(reopened.execute("SELECT count(*) FROM bars").fetchone()[0], 1)
            self.assertEqual(reopened.execute("SELECT count(*) FROM provenance").fetchone()[0], 1)
            self.assertEqual(
                reopened.execute(
                    "SELECT status FROM ingest_runs WHERE ingest_run_id = ?",
                    (result.ingest_run_id,),
                ).fetchone()[0],
                "committed",
            )
            self.assertEqual(reopened.execute("SELECT count(*) FROM raw_blocks").fetchone()[0], 1)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
