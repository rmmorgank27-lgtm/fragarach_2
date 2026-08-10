"""Rebuild an authority database while compacting redundant provenance.

The authority is append-only in normal operation.  This maintenance operation
therefore writes a new database and leaves the source untouched.  It retains
every raw block, every canonical bar, and every INSERT/CORRECTED provenance
event.  ``UNCHANGED`` is an operational ingestion outcome, not a second
scientific admission, and is therefore omitted.  Conflict evidence is retained
once for each distinct raw source row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

from fragarach_ii.storage.database import initialize_database, verify_integrity


COPY_TABLES = (
    "raw_blocks",
    "authority_events",
    "instrument_registrations",
    "evidence_lanes",
    "ingest_runs",
    "bars",
    "lane_state",
    "rollup_state",
    "scheduler_runtime_state",
    "scheduler_audit_events",
)
PROVENANCE_COLUMNS = (
    "provenance_event_id", "ingest_run_id", "raw_block_id", "symbol", "timeframe",
    "timestamp", "source_row_number", "merge_action", "candidate_open",
    "candidate_high", "candidate_low", "candidate_close", "candidate_volume",
    "prior_open", "prior_high", "prior_low", "prior_close", "prior_volume",
    "supersedes_event_id", "recorded_at",
)
DEDUPLICATED_ACTIONS = ("CONFLICT_PRESERVED",)


def rebuild_authority_database(source_path: str | Path, destination_path: str | Path) -> dict[str, object]:
    """Create and verify a compacted authority at *destination_path*.

    The destination must not exist.  Callers are responsible for the final
    atomic path swap only after this function returns successfully.
    """
    source = Path(source_path).expanduser().resolve()
    destination = Path(destination_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if destination.exists():
        raise FileExistsError(destination)
    if not destination.parent.is_dir():
        raise FileNotFoundError(destination.parent)

    initialize_database(destination)
    original_size = source.stat().st_size
    source_connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    destination_connection = sqlite3.connect(destination, isolation_level=None)
    try:
        source_connection.execute("PRAGMA query_only = ON")
        source_connection.execute("PRAGMA temp_store = FILE")
        destination_connection.execute("PRAGMA foreign_keys = ON")
        destination_connection.execute("PRAGMA synchronous = FULL")
        triggers = _suspend_destination_guards(destination_connection)
        for table in COPY_TABLES:
            _copy_table(source_connection, destination_connection, table)
        provenance_counts = _copy_provenance(source_connection, destination_connection)
        _restore_destination_guards(destination_connection, triggers)
    except BaseException:
        destination_connection.close()
        source_connection.close()
        destination.unlink(missing_ok=True)
        raise
    else:
        destination_connection.close()
        source_connection.close()

    verification = _verify_rebuild(source, destination, provenance_counts)
    compacted_size = destination.stat().st_size
    return {
        "source_path": str(source),
        "destination_path": str(destination),
        "source_bytes": original_size,
        "destination_bytes": compacted_size,
        "bytes_reclaimed": original_size - compacted_size,
        "provenance": provenance_counts,
        "verification": verification,
    }


def _suspend_destination_guards(destination: sqlite3.Connection) -> tuple[tuple[str, str], ...]:
    """Remove only bootstrap rows and guards from the newly created database.

    Current migrations seed three demonstration registrations.  Those values
    are not the source authority and cannot be updated through the normal
    immutable-table guards, so the new empty destination is cleared before its
    exact source history is copied.  The guards are restored verbatim before
    verification.
    """
    triggers = tuple(
        (row[0], row[1])
        for row in destination.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name"
        )
    )
    for name, _ in triggers:
        destination.execute(f"DROP TRIGGER {name}")
    destination.execute("PRAGMA foreign_keys = OFF")
    for table in reversed(COPY_TABLES):
        destination.execute(f"DELETE FROM {table}")
    destination.execute("PRAGMA foreign_keys = ON")
    return triggers


def _restore_destination_guards(
    destination: sqlite3.Connection, triggers: tuple[tuple[str, str], ...]
) -> None:
    for _, statement in triggers:
        if statement:
            destination.execute(statement)


def _copy_table(source: sqlite3.Connection, destination: sqlite3.Connection, table: str) -> None:
    columns = tuple(row[1] for row in destination.execute(f"PRAGMA table_info({table})"))
    source_columns = tuple(row[1] for row in source.execute(f"PRAGMA table_info({table})"))
    if columns != source_columns:
        raise RuntimeError(f"schema mismatch for {table}: {source_columns!r} != {columns!r}")
    quoted_columns = ",".join(columns)
    statement = f"INSERT INTO {table} ({quoted_columns}) VALUES ({','.join('?' for _ in columns)})"
    cursor = source.execute(f"SELECT {quoted_columns} FROM {table}")
    _copy_rows(destination, statement, cursor)


def _copy_provenance(source: sqlite3.Connection, destination: sqlite3.Connection) -> dict[str, int]:
    destination_columns = tuple(row[1] for row in destination.execute("PRAGMA table_info(provenance)"))
    if destination_columns != PROVENANCE_COLUMNS:
        raise RuntimeError("unexpected provenance schema")
    columns = ",".join(PROVENANCE_COLUMNS)
    insert = f"INSERT INTO provenance ({columns}) VALUES ({','.join('?' for _ in PROVENANCE_COLUMNS)})"
    copied: dict[str, int] = {}
    for action in ("INSERT", "CORRECTED"):
        copied[action] = _copy_rows(
            destination,
            insert,
            source.execute(
                f"SELECT {columns} FROM provenance WHERE merge_action=? "
                "ORDER BY recorded_at,provenance_event_id",
                (action,),
            ),
        )

    partition = ",".join(
        (
            "raw_block_id", "symbol", "timeframe", "timestamp", "source_row_number",
            "merge_action", "candidate_open", "candidate_high", "candidate_low",
            "candidate_close", "candidate_volume", "prior_open", "prior_high",
            "prior_low", "prior_close", "prior_volume",
        )
    )
    for action in DEDUPLICATED_ACTIONS:
        copied[action] = _copy_rows(
            destination,
            insert,
            source.execute(
                f"""
                SELECT {columns}
                FROM (
                    SELECT {columns},
                           row_number() OVER (
                               PARTITION BY {partition}
                               ORDER BY recorded_at,provenance_event_id
                           ) AS occurrence
                    FROM provenance
                    WHERE merge_action=?
                )
                WHERE occurrence=1
                ORDER BY recorded_at,provenance_event_id
                """,
                (action,),
            ),
        )
    copied["UNCHANGED"] = 0
    return copied


def _copy_rows(destination: sqlite3.Connection, statement: str, rows: sqlite3.Cursor) -> int:
    copied = 0
    while batch := rows.fetchmany(2_000):
        destination.execute("BEGIN IMMEDIATE")
        try:
            destination.executemany(statement, batch)
            destination.commit()
        except BaseException:
            destination.rollback()
            raise
        copied += len(batch)
    return copied


def _verify_rebuild(
    source_path: Path,
    destination_path: Path,
    provenance_counts: dict[str, int],
) -> dict[str, object]:
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    destination = sqlite3.connect(f"file:{destination_path}?mode=ro", uri=True)
    try:
        table_counts = {
            table: {
                "source": source.execute(f"SELECT count(*) FROM {table}").fetchone()[0],
                "destination": destination.execute(f"SELECT count(*) FROM {table}").fetchone()[0],
            }
            for table in COPY_TABLES
        }
        mismatches = {name: counts for name, counts in table_counts.items() if counts["source"] != counts["destination"]}
        if mismatches:
            raise RuntimeError(f"table copy count mismatch: {mismatches!r}")
        source_actions = dict(source.execute("SELECT merge_action,count(*) FROM provenance GROUP BY merge_action"))
        if any(provenance_counts[action] != source_actions.get(action, 0) for action in ("INSERT", "CORRECTED")):
            raise RuntimeError("INSERT or CORRECTED provenance was not preserved exactly")
        if provenance_counts["UNCHANGED"] != 0:
            raise RuntimeError("unchanged observations must not be canonical provenance")
        canonical_source = _bar_digest(source)
        canonical_destination = _bar_digest(destination)
        if canonical_source != canonical_destination:
            raise RuntimeError("canonical bars changed during rebuild")
        source_raw = source.execute("SELECT count(*),sum(byte_length),sum(length(payload)) FROM raw_blocks").fetchone()
        destination_raw = destination.execute("SELECT count(*),sum(byte_length),sum(length(payload)) FROM raw_blocks").fetchone()
        if source_raw != destination_raw:
            raise RuntimeError("raw evidence changed during rebuild")
        missing_correction_parent = destination.execute(
            """SELECT count(*) FROM provenance child
               LEFT JOIN provenance parent ON parent.provenance_event_id=child.supersedes_event_id
               WHERE child.merge_action='CORRECTED' AND parent.provenance_event_id IS NULL"""
        ).fetchone()[0]
        if missing_correction_parent:
            raise RuntimeError(f"{missing_correction_parent} correction lineage parents are missing")
    finally:
        destination.close()
        source.close()
    report = verify_integrity(destination_path)
    return {
        "table_counts": table_counts,
        "source_provenance_actions": source_actions,
        "destination_provenance_actions": provenance_counts,
        "canonical_bar_sha256": canonical_source,
        "raw_evidence_totals": {"raw_blocks": source_raw[0], "bytes": source_raw[1]},
        "integrity": report.ok,
    }


def _bar_digest(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    columns = "asset,timeframe,open_time_utc,close_time_utc,open,high,low,close,volume,created_by_ingest_run_id,updated_by_ingest_run_id"
    for row in connection.execute(f"SELECT {columns} FROM bars ORDER BY asset,timeframe,open_time_utc"):
        digest.update("\\x1f".join("<NULL>" if value is None else str(value) for value in row).encode())
        digest.update(b"\\n")
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild an authority with redundant provenance compacted")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(rebuild_authority_database(args.source, args.destination), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
