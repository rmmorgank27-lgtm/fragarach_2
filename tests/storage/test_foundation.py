from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.storage import (
    WriterLock,
    WriterLockError,
    backup_database,
    canonical_ingest_outcome,
    initialize_database,
    open_read_only,
    registered_writer,
    transaction,
    verify_integrity,
)
from fragarach_ii.storage.schema import APPLICATION_TABLES


def _attempt_writer_lock(database_path: str, result_queue: multiprocessing.Queue) -> None:
    try:
        with WriterLock(database_path):
            result_queue.put(("acquired", None))
    except WriterLockError as error:
        result_queue.put(("blocked", error.owner))


def _crash_during_transaction(database_path: str) -> None:
    with registered_writer(database_path) as writer:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            """
            INSERT INTO ingest_runs
                (ingest_run_id, kind, status, started_at_utc)
            VALUES ('crash-proof', 'proof', 'registered', '2026-07-10T00:00:00Z')
            """
        )
        os._exit(91)


class StorageFoundationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = self.root / "authority.sqlite3"
        initialize_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_wal_foreign_keys_and_exact_table_boundary(self) -> None:
        connection = open_read_only(self.database)
        try:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            self.assertEqual(tables, APPLICATION_TABLES)
        finally:
            connection.close()

        with registered_writer(self.database) as writer:
            self.assertEqual(writer.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(writer.execute("PRAGMA synchronous").fetchone()[0], 2)

    def test_writer_lock_excludes_another_process_and_reports_owner(self) -> None:
        context = multiprocessing.get_context("spawn")
        result_queue = context.Queue()
        with WriterLock(self.database):
            metadata = json.loads(Path(f"{self.database}.writer.lock").read_text())
            self.assertEqual(metadata["state"], "held")
            self.assertEqual(metadata["database_path"], str(self.database.resolve()))
            self.assertIsInstance(metadata["pid"], int)
            self.assertTrue(metadata["ownership_token"])

            process = context.Process(
                target=_attempt_writer_lock, args=(str(self.database), result_queue)
            )
            process.start()
            process.join(timeout=10)
            self.assertFalse(process.is_alive(), "lock contender did not exit")
            self.assertEqual(process.exitcode, 0)
            outcome, observed_owner = result_queue.get(timeout=2)
            self.assertEqual(outcome, "blocked")
            self.assertEqual(observed_owner["ownership_token"], metadata["ownership_token"])

        with WriterLock(self.database):
            pass

    def test_concurrent_readers_see_committed_snapshot_during_write(self) -> None:
        readers = [open_read_only(self.database) for _ in range(8)]
        try:
            with registered_writer(self.database) as writer:
                writer.execute("BEGIN IMMEDIATE")
                writer.execute(
                    """
                    INSERT INTO ingest_runs
                        (ingest_run_id, kind, status, started_at_utc)
                    VALUES ('uncommitted', 'proof', 'registered', '2026-07-10T00:00:00Z')
                    """
                )
                for reader in readers:
                    count = reader.execute(
                        "SELECT count(*) FROM ingest_runs"
                    ).fetchone()[0]
                    self.assertEqual(count, 0)
                writer.rollback()
        finally:
            for reader in readers:
                reader.close()

    def test_transaction_rolls_back_all_changes_on_exception(self) -> None:
        with registered_writer(self.database) as writer:
            with self.assertRaisesRegex(RuntimeError, "interrupt"):
                with transaction(writer):
                    writer.execute(
                        """
                        INSERT INTO ingest_runs
                            (ingest_run_id, kind, status, started_at_utc)
                        VALUES ('rollback-proof', 'proof', 'registered', ?)
                        """,
                        ("2026-07-10T00:00:00Z",),
                    )
                    raise RuntimeError("interrupt")
            self.assertEqual(
                writer.execute(
                    "SELECT count(*) FROM ingest_runs WHERE ingest_run_id = 'rollback-proof'"
                ).fetchone()[0],
                0,
            )

    def test_process_crash_rolls_back_and_releases_writer_lock(self) -> None:
        context = multiprocessing.get_context("spawn")
        process = context.Process(
            target=_crash_during_transaction, args=(str(self.database),)
        )
        process.start()
        process.join(timeout=10)
        self.assertFalse(process.is_alive(), "crash proof child did not exit")
        self.assertEqual(process.exitcode, 91)

        with WriterLock(self.database):
            pass
        consumer = open_read_only(self.database)
        try:
            self.assertEqual(
                consumer.execute(
                    "SELECT count(*) FROM ingest_runs WHERE ingest_run_id = 'crash-proof'"
                ).fetchone()[0],
                0,
            )
        finally:
            consumer.close()
        self.assertTrue(verify_integrity(self.database).ok)

    def test_committed_data_persists_across_complete_restart(self) -> None:
        payload = b"source evidence\n"
        digest = hashlib.sha256(payload).hexdigest()
        with registered_writer(self.database) as writer:
            with transaction(writer):
                writer.execute(
                    """
                    INSERT INTO raw_blocks
                        (raw_block_id, sha256, source_name, source_locator, media_type,
                         received_at_utc, byte_length, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "block-1",
                        digest,
                        "manual-proof",
                        "test-fixture",
                        "text/plain",
                        "2026-07-10T00:00:00Z",
                        len(payload),
                        payload,
                    ),
                )

        reopened = open_read_only(self.database)
        try:
            stored = reopened.execute(
                "SELECT sha256, payload FROM raw_blocks WHERE raw_block_id = 'block-1'"
            ).fetchone()
            self.assertEqual(stored, (digest, payload))
        finally:
            reopened.close()

    def test_raw_blocks_and_migration_history_are_immutable(self) -> None:
        payload = b"immutable"
        with registered_writer(self.database) as writer:
            writer.execute(
                """
                INSERT INTO raw_blocks
                    (raw_block_id, sha256, source_name, source_locator, media_type,
                     received_at_utc, byte_length, payload)
                VALUES (?, ?, 'proof', 'fixture', 'application/octet-stream', ?, ?, ?)
                """,
                (
                    "immutable-1",
                    hashlib.sha256(payload).hexdigest(),
                    "2026-07-10T00:00:00Z",
                    len(payload),
                    payload,
                ),
            )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                writer.execute(
                    "UPDATE raw_blocks SET source_name = 'changed' "
                    "WHERE raw_block_id = 'immutable-1'"
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                writer.execute("DELETE FROM raw_blocks WHERE raw_block_id = 'immutable-1'")
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                writer.execute("DELETE FROM schema_migrations WHERE version = 1")

            writer.execute(
                """
                INSERT INTO ingest_runs
                    (ingest_run_id, kind, status, started_at_utc)
                VALUES ('provenance-run', 'proof', 'registered', ?)
                """,
                ("2026-07-10T00:00:00Z",),
            )
            writer.execute(
                """
                INSERT INTO bars
                    (asset, timeframe, open_time_utc, open, high, low, close,
                     created_by_ingest_run_id, updated_by_ingest_run_id)
                VALUES ('AUDUSD', 'D1', 0, '1.0', '1.1', '0.9', '1.05',
                        'provenance-run', 'provenance-run')
                """
            )
            writer.execute(
                """
                INSERT INTO provenance
                    (provenance_event_id, ingest_run_id, raw_block_id, symbol,
                     timeframe, timestamp, source_row_number, merge_action,
                     candidate_open, candidate_high, candidate_low, candidate_close,
                     candidate_volume, recorded_at)
                VALUES ('event-1', 'provenance-run', 'immutable-1', 'AUDUSD',
                        'D1', 0, 1, 'INSERT', '1.0', '1.1', '0.9', '1.05',
                        NULL, ?)
                """,
                ("2026-07-10T00:00:00Z",),
            )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                writer.execute(
                    "UPDATE provenance SET source_row_number = 2 "
                    "WHERE provenance_event_id = 'event-1'"
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                writer.execute(
                    "DELETE FROM provenance WHERE raw_block_id = 'immutable-1'"
                )

    def test_foreign_keys_reject_unrelated_provenance(self) -> None:
        with registered_writer(self.database) as writer:
            with self.assertRaises(sqlite3.IntegrityError):
                writer.execute(
                    """
                    INSERT INTO provenance
                        (provenance_event_id, ingest_run_id, raw_block_id, symbol,
                         timeframe, timestamp, source_row_number, merge_action,
                         candidate_open, candidate_high, candidate_low,
                         candidate_close, recorded_at)
                    VALUES ('missing-event', 'missing', 'missing', 'AUDUSD',
                            'D1', 0, 1, 'INSERT', '1', '1', '1', '1', ?)
                    """,
                    ("2026-07-10T00:00:00Z",),
                )

    def test_ingest_run_state_machine_rejects_illegal_transition(self) -> None:
        with registered_writer(self.database) as writer:
            writer.execute(
                """
                INSERT INTO ingest_runs
                    (ingest_run_id, kind, status, started_at_utc)
                VALUES ('run-1', 'proof', 'registered', '2026-07-10T00:00:00Z')
                """
            )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "illegal"):
                writer.execute(
                    """
                    UPDATE ingest_runs
                    SET status = 'committed', finished_at_utc = '2026-07-10T00:01:00Z'
                    WHERE ingest_run_id = 'run-1'
                    """
                )
            writer.execute(
                "UPDATE ingest_runs SET status = 'active' WHERE ingest_run_id = 'run-1'"
            )
            writer.execute(
                """
                UPDATE ingest_runs
                SET status = 'committed', finished_at_utc = '2026-07-10T00:01:00Z'
                WHERE ingest_run_id = 'run-1'
                """
            )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "illegal"):
                writer.execute(
                    "UPDATE ingest_runs SET detail = ? WHERE ingest_run_id = 'run-1'",
                    (canonical_ingest_outcome(),),
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                writer.execute("DELETE FROM ingest_runs WHERE ingest_run_id = 'run-1'")

    def test_read_only_consumer_cannot_mutate(self) -> None:
        consumer = open_read_only(self.database)
        try:
            with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"):
                consumer.execute(
                    """
                    INSERT INTO ingest_runs
                        (ingest_run_id, kind, status, started_at_utc)
                    VALUES ('forbidden', 'proof', 'registered', '2026-07-10T00:00:00Z')
                    """
                )
        finally:
            consumer.close()

    def test_integrity_and_online_backup_restoration(self) -> None:
        report = verify_integrity(self.database)
        self.assertTrue(report.ok)
        self.assertEqual(report.application_tables, APPLICATION_TABLES)

        backup = self.root / "backup.sqlite3"
        backup_database(self.database, backup)
        restored_report = verify_integrity(backup)
        self.assertTrue(restored_report.ok)


if __name__ == "__main__":
    unittest.main()
