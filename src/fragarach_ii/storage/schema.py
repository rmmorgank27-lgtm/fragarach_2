"""Versioned SQLite schema for SPEC-001."""

from __future__ import annotations

import hashlib


APPLICATION_TABLES = frozenset(
    {
        "raw_blocks",
        "bars",
        "provenance",
        "ingest_runs",
        "lane_state",
        "rollup_state",
        "schema_migrations",
    }
)

MIGRATION_1_NAME = "SPEC-001 storage foundation"

MIGRATION_1_STATEMENTS = (
    """
    CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        checksum_sha256 TEXT NOT NULL CHECK (
            length(checksum_sha256) = 64
            AND checksum_sha256 NOT GLOB '*[^0-9a-f]*'
        ),
        applied_at_utc TEXT NOT NULL
    ) STRICT
    """,
    """
    CREATE TABLE ingest_runs (
        ingest_run_id TEXT PRIMARY KEY CHECK (length(ingest_run_id) > 0),
        kind TEXT NOT NULL CHECK (length(kind) > 0),
        status TEXT NOT NULL CHECK (
            status IN ('registered', 'active', 'committed', 'rolled_back', 'failed')
        ),
        started_at_utc TEXT NOT NULL,
        finished_at_utc TEXT,
        detail TEXT,
        CHECK (
            (status IN ('registered', 'active') AND finished_at_utc IS NULL)
            OR
            (status IN ('committed', 'rolled_back', 'failed') AND finished_at_utc IS NOT NULL)
        )
    ) STRICT
    """,
    """
    CREATE TABLE raw_blocks (
        raw_block_id TEXT PRIMARY KEY CHECK (length(raw_block_id) > 0),
        sha256 TEXT NOT NULL UNIQUE CHECK (
            length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'
        ),
        source_name TEXT NOT NULL CHECK (length(source_name) > 0),
        source_locator TEXT NOT NULL CHECK (length(source_locator) > 0),
        media_type TEXT NOT NULL CHECK (length(media_type) > 0),
        received_at_utc TEXT NOT NULL,
        byte_length INTEGER NOT NULL CHECK (byte_length >= 0),
        payload BLOB NOT NULL,
        CHECK (byte_length = length(payload))
    ) STRICT
    """,
    """
    CREATE TABLE bars (
        asset TEXT NOT NULL CHECK (length(asset) > 0),
        timeframe TEXT NOT NULL CHECK (length(timeframe) > 0),
        open_time_utc INTEGER NOT NULL,
        close_time_utc INTEGER,
        open TEXT NOT NULL CHECK (length(open) > 0),
        high TEXT NOT NULL CHECK (length(high) > 0),
        low TEXT NOT NULL CHECK (length(low) > 0),
        close TEXT NOT NULL CHECK (length(close) > 0),
        volume TEXT CHECK (volume IS NULL OR length(volume) > 0),
        created_by_ingest_run_id TEXT NOT NULL,
        updated_by_ingest_run_id TEXT NOT NULL,
        PRIMARY KEY (asset, timeframe, open_time_utc),
        FOREIGN KEY (created_by_ingest_run_id) REFERENCES ingest_runs(ingest_run_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        FOREIGN KEY (updated_by_ingest_run_id) REFERENCES ingest_runs(ingest_run_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        CHECK (close_time_utc IS NULL OR close_time_utc > open_time_utc)
    ) STRICT, WITHOUT ROWID
    """,
    """
    CREATE TABLE provenance (
        asset TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        open_time_utc INTEGER NOT NULL,
        raw_block_id TEXT NOT NULL,
        source_record_ref TEXT NOT NULL CHECK (length(source_record_ref) > 0),
        observed_at_utc TEXT NOT NULL,
        ingest_run_id TEXT NOT NULL,
        PRIMARY KEY (asset, timeframe, open_time_utc, raw_block_id, source_record_ref),
        FOREIGN KEY (asset, timeframe, open_time_utc)
            REFERENCES bars(asset, timeframe, open_time_utc)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        FOREIGN KEY (raw_block_id) REFERENCES raw_blocks(raw_block_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        FOREIGN KEY (ingest_run_id) REFERENCES ingest_runs(ingest_run_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT
    ) STRICT, WITHOUT ROWID
    """,
    """
    CREATE TABLE lane_state (
        asset TEXT NOT NULL CHECK (length(asset) > 0),
        timeframe TEXT NOT NULL CHECK (length(timeframe) > 0),
        high_watermark_open_time_utc INTEGER,
        state_version INTEGER NOT NULL CHECK (state_version >= 0),
        last_ingest_run_id TEXT,
        updated_at_utc TEXT NOT NULL,
        PRIMARY KEY (asset, timeframe),
        FOREIGN KEY (last_ingest_run_id) REFERENCES ingest_runs(ingest_run_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT
    ) STRICT, WITHOUT ROWID
    """,
    """
    CREATE TABLE rollup_state (
        asset TEXT NOT NULL CHECK (length(asset) > 0),
        source_timeframe TEXT NOT NULL CHECK (length(source_timeframe) > 0),
        target_timeframe TEXT NOT NULL CHECK (length(target_timeframe) > 0),
        high_watermark_open_time_utc INTEGER,
        state_version INTEGER NOT NULL CHECK (state_version >= 0),
        last_ingest_run_id TEXT,
        updated_at_utc TEXT NOT NULL,
        PRIMARY KEY (asset, source_timeframe, target_timeframe),
        FOREIGN KEY (last_ingest_run_id) REFERENCES ingest_runs(ingest_run_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        CHECK (source_timeframe <> target_timeframe)
    ) STRICT, WITHOUT ROWID
    """,
    """
    CREATE TRIGGER raw_blocks_no_update
    BEFORE UPDATE ON raw_blocks
    BEGIN
        SELECT RAISE(ABORT, 'raw_blocks are immutable');
    END
    """,
    """
    CREATE TRIGGER raw_blocks_no_delete
    BEFORE DELETE ON raw_blocks
    BEGIN
        SELECT RAISE(ABORT, 'raw_blocks are immutable');
    END
    """,
    """
    CREATE TRIGGER provenance_no_update
    BEFORE UPDATE ON provenance
    BEGIN
        SELECT RAISE(ABORT, 'provenance is append-only');
    END
    """,
    """
    CREATE TRIGGER provenance_no_delete
    BEFORE DELETE ON provenance
    BEGIN
        SELECT RAISE(ABORT, 'provenance is append-only');
    END
    """,
    """
    CREATE TRIGGER schema_migrations_no_update
    BEFORE UPDATE ON schema_migrations
    BEGIN
        SELECT RAISE(ABORT, 'schema migration history is append-only');
    END
    """,
    """
    CREATE TRIGGER schema_migrations_no_delete
    BEFORE DELETE ON schema_migrations
    BEGIN
        SELECT RAISE(ABORT, 'schema migration history is append-only');
    END
    """,
    """
    CREATE TRIGGER ingest_runs_legal_update
    BEFORE UPDATE ON ingest_runs
    BEGIN
        SELECT CASE
            WHEN NEW.ingest_run_id <> OLD.ingest_run_id
              OR NEW.kind <> OLD.kind
              OR NEW.started_at_utc <> OLD.started_at_utc
            THEN RAISE(ABORT, 'ingest run identity is immutable')
            WHEN OLD.status = 'registered' AND NEW.status IN ('active', 'failed') THEN NULL
            WHEN OLD.status = 'active' AND NEW.status IN ('committed', 'rolled_back', 'failed') THEN NULL
            ELSE RAISE(ABORT, 'illegal ingest run transition')
        END;
    END
    """,
    """
    CREATE TRIGGER ingest_runs_no_delete
    BEFORE DELETE ON ingest_runs
    BEGIN
        SELECT RAISE(ABORT, 'ingest run history is append-only');
    END
    """,
)


def migration_1_checksum() -> str:
    """Return the stable checksum of migration 1's executable statements."""

    source = "\n-- statement --\n".join(
        statement.strip() for statement in MIGRATION_1_STATEMENTS
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()

