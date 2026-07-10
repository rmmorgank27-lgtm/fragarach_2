from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.storage import (
    Rejection,
    backup_database,
    canonical_ingest_outcome,
    open_read_only,
    registered_writer,
    verify_integrity,
)
from fragarach_ii.storage.migrations import apply_migrations
from fragarach_ii.storage.schema import APPLICATION_TABLES, migration_2_checksum


NOW = "2026-07-10T00:00:00+00:00"


def _insert_raw(connection: sqlite3.Connection, block_id: str = "raw-1") -> None:
    payload = b"timestamp,open,high,low,close\n2026-07-09,1,2,0,1\n"
    connection.execute(
        """
        INSERT INTO raw_blocks
            (raw_block_id, sha256, source_name, source_locator, media_type,
             received_at_utc, byte_length, payload)
        VALUES (?, ?, 'fixture.csv', '/proof/fixture.csv', 'text/csv', ?, ?, ?)
        """,
        (block_id, hashlib.sha256(payload).hexdigest(), NOW, len(payload), payload),
    )


def _create_spec_001_database(path: Path) -> None:
    with registered_writer(path) as connection:
        apply_migrations(connection, target_version=1)
        _insert_raw(connection)
        connection.execute(
            """
            INSERT INTO ingest_runs
                (ingest_run_id, kind, status, started_at_utc, detail)
            VALUES ('legacy-run', 'proof', 'active', ?, 'legacy factual detail')
            """,
            (NOW,),
        )
        connection.execute(
            """
            INSERT INTO bars
                (asset, timeframe, open_time_utc, open, high, low, close, volume,
                 created_by_ingest_run_id, updated_by_ingest_run_id)
            VALUES ('AUDUSD', 'D1', 1783555200, '1.0', '1.2', '0.9', '1.1',
                    '10', 'legacy-run', 'legacy-run')
            """
        )
        connection.execute(
            """
            INSERT INTO provenance
                (asset, timeframe, open_time_utc, raw_block_id,
                 source_record_ref, observed_at_utc, ingest_run_id)
            VALUES ('AUDUSD', 'D1', 1783555200, 'raw-1', 'line:2', ?, 'legacy-run')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE ingest_runs
            SET status = 'committed', finished_at_utc = ?
            WHERE ingest_run_id = 'legacy-run'
            """,
            (NOW,),
        )


def _insert_event(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    run_id: str,
    action: str,
    candidate: tuple[str, str, str, str, str | None],
    prior: tuple[str, str, str, str, str | None] | None = None,
    supersedes: str | None = None,
    source_row: int = 2,
) -> None:
    prior_values = prior or (None, None, None, None, None)
    connection.execute(
        """
        INSERT INTO provenance (
            provenance_event_id, ingest_run_id, raw_block_id, symbol, timeframe,
            timestamp, source_row_number, merge_action,
            candidate_open, candidate_high, candidate_low, candidate_close,
            candidate_volume, prior_open, prior_high, prior_low, prior_close,
            prior_volume, supersedes_event_id, recorded_at
        ) VALUES (?, ?, 'raw-1', 'AUDUSD', 'D1', 1783555200, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            run_id,
            source_row,
            action,
            *candidate,
            *prior_values,
            supersedes,
            NOW,
        ),
    )


class ProvenanceAmendmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_existing_spec_001_data_survives_forward_migration(self) -> None:
        database = self.root / "legacy.sqlite3"
        _create_spec_001_database(database)
        with registered_writer(database) as connection:
            apply_migrations(connection)

        connection = open_read_only(database)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall(),
                [(1,), (2,), (3,)],
            )
            self.assertEqual(connection.execute("SELECT count(*) FROM raw_blocks").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM bars").fetchone()[0], 1)
            run = connection.execute(
                "SELECT raw_block_id, detail FROM ingest_runs WHERE ingest_run_id = 'legacy-run'"
            ).fetchone()
            self.assertEqual(run[0], "raw-1")
            self.assertEqual(json.loads(run[1])["rejections"][0]["code"], "LEGACY_DETAIL")
            event = connection.execute(
                """
                SELECT merge_action, source_row_number, candidate_open,
                       candidate_close, prior_open
                FROM provenance
                """
            ).fetchone()
            self.assertEqual(event, ("INSERT", 2, "1.0", "1.1", None))
            self.assertEqual(
                {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_schema "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    )
                },
                APPLICATION_TABLES,
            )
        finally:
            connection.close()
        self.assertTrue(verify_integrity(database).ok)

    def test_interrupted_migration_leaves_spec_001_usable(self) -> None:
        database = self.root / "interrupted.sqlite3"
        _create_spec_001_database(database)
        with registered_writer(database) as connection:
            with self.assertRaisesRegex(RuntimeError, "injected migration interruption"):
                apply_migrations(connection, fault_after_statement=8)
            self.assertEqual(
                connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall(),
                [(1,)],
            )
            ingest_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(ingest_runs)")
            }
            provenance_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(provenance)")
            }
            self.assertNotIn("raw_block_id", ingest_columns)
            self.assertIn("source_record_ref", provenance_columns)
            self.assertEqual(connection.execute("SELECT count(*) FROM bars").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            apply_migrations(connection)
        self.assertTrue(verify_integrity(database).ok)

    def test_repeated_runs_and_distinct_events_share_raw_evidence(self) -> None:
        database = self.root / "repeat.sqlite3"
        with registered_writer(database) as connection:
            apply_migrations(connection)
            _insert_raw(connection)
            for run_id in ("run-a", "run-b"):
                connection.execute(
                    """
                    INSERT INTO ingest_runs
                        (ingest_run_id, kind, status, started_at_utc, raw_block_id)
                    VALUES (?, 'manual_file', 'registered', ?, 'raw-1')
                    """,
                    (run_id, NOW),
                )
            connection.execute(
                """
                INSERT INTO bars
                    (asset, timeframe, open_time_utc, open, high, low, close,
                     created_by_ingest_run_id, updated_by_ingest_run_id)
                VALUES ('AUDUSD', 'D1', 1783555200, '1', '2', '0', '1',
                        'run-a', 'run-a')
                """
            )
            _insert_event(
                connection,
                event_id="event-a",
                run_id="run-a",
                action="INSERT",
                candidate=("1", "2", "0", "1", None),
            )
            _insert_event(
                connection,
                event_id="event-b",
                run_id="run-b",
                action="UNCHANGED",
                candidate=("1", "2", "0", "1", None),
                prior=("1", "2", "0", "1", None),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT count(DISTINCT ingest_run_id) FROM provenance"
                ).fetchone()[0],
                2,
            )

    def test_correction_and_preserved_conflict_retain_both_states(self) -> None:
        database = self.root / "lineage.sqlite3"
        with registered_writer(database) as connection:
            apply_migrations(connection)
            _insert_raw(connection)
            for run_id in ("original", "conflict", "correction"):
                connection.execute(
                    """
                    INSERT INTO ingest_runs
                        (ingest_run_id, kind, status, started_at_utc, raw_block_id)
                    VALUES (?, 'manual_file', 'registered', ?, 'raw-1')
                    """,
                    (run_id, NOW),
                )
            connection.execute(
                """
                INSERT INTO bars
                    (asset, timeframe, open_time_utc, open, high, low, close, volume,
                     created_by_ingest_run_id, updated_by_ingest_run_id)
                VALUES ('AUDUSD', 'D1', 1783555200, '1', '2', '0', '1.5', '10',
                        'original', 'correction')
                """
            )
            original = ("1", "2", "0", "1", "9")
            competing = ("1", "2", "0", "1.5", "10")
            _insert_event(
                connection,
                event_id="original-event",
                run_id="original",
                action="INSERT",
                candidate=original,
            )
            _insert_event(
                connection,
                event_id="conflict-event",
                run_id="conflict",
                action="CONFLICT_PRESERVED",
                candidate=competing,
                prior=original,
            )
            _insert_event(
                connection,
                event_id="correction-event",
                run_id="correction",
                action="CORRECTED",
                candidate=competing,
                prior=original,
                supersedes="original-event",
            )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "lineage"):
                _insert_event(
                    connection,
                    event_id="bad-correction-event",
                    run_id="correction",
                    action="CORRECTED",
                    candidate=("1", "2", "0", "1.6", "10"),
                    prior=("1", "2", "0", "9", "9"),
                    supersedes="original-event",
                    source_row=3,
                )
            correction = connection.execute(
                """
                SELECT candidate_close, candidate_volume, prior_close, prior_volume,
                       supersedes_event_id
                FROM provenance WHERE provenance_event_id = 'correction-event'
                """
            ).fetchone()
            self.assertEqual(correction, ("1.5", "10", "1", "9", "original-event"))
            conflict = connection.execute(
                """
                SELECT candidate_close, prior_close FROM provenance
                WHERE provenance_event_id = 'conflict-event'
                """
            ).fetchone()
            self.assertEqual(conflict, ("1.5", "1"))
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                connection.execute(
                    "UPDATE provenance SET candidate_close = '9' "
                    "WHERE provenance_event_id = 'correction-event'"
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                connection.execute(
                    "DELETE FROM provenance WHERE provenance_event_id = 'correction-event'"
                )

    def test_rejected_evidence_is_linked_and_outcome_json_is_enforced(self) -> None:
        database = self.root / "rejected.sqlite3"
        outcome = canonical_ingest_outcome(
            source_rows=1,
            rejected=1,
            rejections=(Rejection(2, "INVALID_OHLC", "high is below low"),),
        )
        self.assertEqual(
            outcome,
            canonical_ingest_outcome(
                source_rows=1,
                rejected=1,
                rejections=(Rejection(2, "INVALID_OHLC", "high is below low"),),
            ),
        )
        with registered_writer(database) as connection:
            apply_migrations(connection)
            _insert_raw(connection)
            connection.execute(
                """
                INSERT INTO ingest_runs
                    (ingest_run_id, kind, status, started_at_utc, raw_block_id)
                VALUES ('rejected-run', 'manual_file', 'active', ?, 'raw-1')
                """,
                (NOW,),
            )
            connection.execute(
                """
                UPDATE ingest_runs
                SET status = 'failed', finished_at_utc = ?, detail = ?
                WHERE ingest_run_id = 'rejected-run'
                """,
                (NOW, outcome),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT raw_block_id FROM ingest_runs WHERE ingest_run_id = 'rejected-run'"
                ).fetchone()[0],
                "raw-1",
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO ingest_runs
                        (ingest_run_id, kind, status, started_at_utc, detail)
                    VALUES ('invalid-json', 'proof', 'registered', ?, 'not-json')
                    """,
                    (NOW,),
                )

    def test_checksum_integrity_and_backup_remain_valid(self) -> None:
        database = self.root / "authority.sqlite3"
        with registered_writer(database) as connection:
            apply_migrations(connection)
            stored = connection.execute(
                "SELECT checksum_sha256 FROM schema_migrations WHERE version = 2"
            ).fetchone()[0]
            self.assertEqual(stored, migration_2_checksum())
        self.assertTrue(verify_integrity(database).ok)
        backup = self.root / "backup.sqlite3"
        backup_database(database, backup)
        self.assertTrue(verify_integrity(backup).ok)


if __name__ == "__main__":
    unittest.main()
