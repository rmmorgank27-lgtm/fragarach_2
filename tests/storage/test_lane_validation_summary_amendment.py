from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.storage import (
    LaneValidationSummary,
    backup_database,
    open_read_only,
    registered_writer,
    verify_integrity,
)
from fragarach_ii.storage.migrations import apply_migrations
from fragarach_ii.storage.schema import APPLICATION_TABLES, migration_3_checksum


NOW = "2026-07-11T00:00:00+00:00"


def _summary(**overrides: object) -> LaneValidationSummary:
    values: dict[str, object] = {
        "symbol": "AUDUSD",
        "timeframe": "D1",
        "calendar_id": "FX_D1_V1",
        "calendar_version": 1,
        "calendar_checksum": "a" * 64,
        "gap_doctrine_id": "FRAGARACH_II_D1_GAP_DOCTRINE_V1",
        "gap_doctrine_version": 1,
        "gap_doctrine_checksum": "b" * 64,
        "validator_version": "1.0.0",
        "through_date": "2026-07-10",
        "expected_session_count": 10,
        "present_expected_session_count": 9,
        "missing_expected_session_count": 1,
        "outside_expected_session_count": 2,
        "empty_week_count": 0,
        "empty_month_count": 0,
        "latest_expected_session": "2026-07-10",
        "latest_expected_session_present": True,
        "material_gap_count": 0,
        "non_material_gap_count": 1,
        "result_checksum": "c" * 64,
        "validation_observed_at": NOW,
    }
    values.update(overrides)
    return LaneValidationSummary(**values)  # type: ignore[arg-type]


def _create_version_2_database(path: Path) -> None:
    payload = b"legacy evidence"
    with registered_writer(path) as connection:
        apply_migrations(connection, target_version=2)
        connection.execute(
            """
            INSERT INTO raw_blocks
                (raw_block_id, sha256, source_name, source_locator, media_type,
                 received_at_utc, byte_length, payload)
            VALUES ('raw-1', ?, 'proof.csv', '/proof.csv', 'text/csv', ?, ?, ?)
            """,
            (hashlib.sha256(payload).hexdigest(), NOW, len(payload), payload),
        )
        connection.execute(
            """
            INSERT INTO ingest_runs
                (ingest_run_id, kind, status, started_at_utc, raw_block_id)
            VALUES ('run-1', 'manual_file', 'registered', ?, 'raw-1')
            """,
            (NOW,),
        )
        connection.execute(
            """
            INSERT INTO bars
                (asset, timeframe, open_time_utc, open, high, low, close,
                 created_by_ingest_run_id, updated_by_ingest_run_id)
            VALUES ('AUDUSD', 'D1', 1783641600, '1', '2', '0', '1',
                    'run-1', 'run-1')
            """
        )
        connection.execute(
            """
            INSERT INTO provenance (
                provenance_event_id, ingest_run_id, raw_block_id, symbol,
                timeframe, timestamp, source_row_number, merge_action,
                candidate_open, candidate_high, candidate_low, candidate_close,
                recorded_at
            ) VALUES ('event-1', 'run-1', 'raw-1', 'AUDUSD', 'D1',
                      1783641600, 2, 'INSERT', '1', '2', '0', '1', ?)
            """,
            (NOW,),
        )
        connection.execute(
            """
            INSERT INTO lane_state
                (asset, timeframe, high_watermark_open_time_utc, state_version,
                 last_ingest_run_id, updated_at_utc)
            VALUES ('AUDUSD', 'D1', 1783641600, 7, 'run-1', ?)
            """,
            (NOW,),
        )


class LaneValidationSummaryAmendmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_version_2_rows_and_all_evidence_survive_with_null_summary(self) -> None:
        database = self.root / "version2.sqlite3"
        _create_version_2_database(database)
        with registered_writer(database) as connection:
            before = {
                table: connection.execute(f"SELECT * FROM {table}").fetchall()
                for table in ("raw_blocks", "bars", "provenance", "ingest_runs")
            }
            lane_before = connection.execute("SELECT * FROM lane_state").fetchone()
            apply_migrations(connection)
            after = {
                table: connection.execute(f"SELECT * FROM {table}").fetchall()
                for table in ("raw_blocks", "bars", "provenance", "ingest_runs")
            }
            lane_after = connection.execute("SELECT * FROM lane_state").fetchone()
            self.assertEqual(after, before)
            self.assertEqual(lane_after[:-1], lane_before)
            self.assertIsNone(lane_after[-1])
            self.assertEqual(
                connection.execute(
                    "SELECT checksum_sha256 FROM schema_migrations WHERE version = 3"
                ).fetchone()[0],
                migration_3_checksum(),
            )
        self.assertTrue(verify_integrity(database).ok)

    def test_interrupted_migration_restores_complete_version_2_schema(self) -> None:
        database = self.root / "interrupted.sqlite3"
        _create_version_2_database(database)
        with registered_writer(database) as connection:
            with self.assertRaisesRegex(RuntimeError, "injected migration interruption"):
                apply_migrations(
                    connection,
                    fault_after_statement=1,
                    fault_migration_version=3,
                )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(lane_state)")}
            self.assertNotIn("validation_summary", columns)
            self.assertEqual(
                connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall(),
                [(1,), (2,)],
            )
            self.assertEqual(connection.execute("SELECT state_version FROM lane_state").fetchone()[0], 7)
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            apply_migrations(connection)
        self.assertTrue(verify_integrity(database).ok)

    def test_canonical_serializer_and_database_boundary(self) -> None:
        database = self.root / "summary.sqlite3"
        _create_version_2_database(database)
        canonical = _summary().as_json()
        self.assertEqual(canonical, _summary().as_json())
        self.assertEqual(json.loads(canonical)["format"], "fragarach_ii.lane_validation_summary.v1")
        with registered_writer(database) as connection:
            apply_migrations(connection)
            before = connection.execute(
                """
                SELECT high_watermark_open_time_utc, state_version,
                       last_ingest_run_id, updated_at_utc
                FROM lane_state
                """
            ).fetchone()
            connection.execute(
                "UPDATE lane_state SET validation_summary = ? WHERE asset = 'AUDUSD' AND timeframe = 'D1'",
                (canonical,),
            )
            after = connection.execute(
                """
                SELECT high_watermark_open_time_utc, state_version,
                       last_ingest_run_id, updated_at_utc
                FROM lane_state
                """
            ).fetchone()
            self.assertEqual(after, before)
            invalid_documents = (
                "not-json",
                canonical.replace("lane_validation_summary.v1", "lane_validation_summary.v2"),
                canonical.replace('"symbol":"AUDUSD"', '"symbol":"XAUUSD"'),
                canonical.replace('"expected_session_count":10,', ""),
                canonical.replace('"expected_session_count":10', '"expected_session_count":-1'),
            )
            for document in invalid_documents:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE lane_state SET validation_summary = ? WHERE asset = 'AUDUSD'",
                        (document,),
                    )

        consumer = open_read_only(database)
        try:
            self.assertEqual(
                consumer.execute("SELECT validation_summary FROM lane_state").fetchone()[0],
                canonical,
            )
            with self.assertRaises(sqlite3.OperationalError):
                consumer.execute("UPDATE lane_state SET validation_summary = NULL")
        finally:
            consumer.close()

    def test_serializer_rejects_invalid_versions_counts_dates_and_checksums(self) -> None:
        invalid = (
            {"calendar_version": 0},
            {"missing_expected_session_count": 2},
            {"through_date": "07/10/2026"},
            {"calendar_checksum": "A" * 64},
            {"latest_expected_session_present": 1},
            {"validation_observed_at": "2026-07-11T00:00:00"},
        )
        for values in invalid:
            with self.assertRaises(ValueError):
                _summary(**values)

    def test_backup_restore_and_exact_table_boundary_after_summary(self) -> None:
        database = self.root / "authority.sqlite3"
        _create_version_2_database(database)
        with registered_writer(database) as connection:
            apply_migrations(connection)
            connection.execute(
                "UPDATE lane_state SET validation_summary = ?",
                (_summary().as_json(),),
            )
        backup = self.root / "backup.sqlite3"
        backup_database(database, backup)
        report = verify_integrity(backup)
        self.assertTrue(report.ok)
        self.assertEqual(report.application_tables, APPLICATION_TABLES)
        restored = open_read_only(backup)
        try:
            self.assertEqual(
                restored.execute("SELECT validation_summary FROM lane_state").fetchone()[0],
                _summary().as_json(),
            )
            self.assertEqual(
                restored.execute("SELECT count(*) FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0],
                12,
            )
        finally:
            restored.close()


if __name__ == "__main__":
    unittest.main()
