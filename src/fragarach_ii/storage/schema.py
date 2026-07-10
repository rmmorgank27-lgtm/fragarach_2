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


MIGRATION_2_NAME = "SPEC-001A provenance event and evidence-run amendment"

_OUTCOME_VALIDATION_CASE = """
CASE
    WHEN json_valid(NEW.detail) = 0
        THEN RAISE(ABORT, 'ingest outcome must be valid JSON')
    WHEN json_extract(NEW.detail, '$.format') <> 'fragarach_ii.ingest_outcome.v1'
        THEN RAISE(ABORT, 'invalid ingest outcome format')
    WHEN json_type(NEW.detail, '$.source_rows') <> 'integer'
      OR json_type(NEW.detail, '$.staged') <> 'integer'
      OR json_type(NEW.detail, '$.inserted') <> 'integer'
      OR json_type(NEW.detail, '$.corrected') <> 'integer'
      OR json_type(NEW.detail, '$.unchanged') <> 'integer'
      OR json_type(NEW.detail, '$.conflicts_preserved') <> 'integer'
      OR json_type(NEW.detail, '$.rejected') <> 'integer'
        THEN RAISE(ABORT, 'ingest outcome counts must be integers')
    WHEN json_extract(NEW.detail, '$.source_rows') < 0
      OR json_extract(NEW.detail, '$.staged') < 0
      OR json_extract(NEW.detail, '$.inserted') < 0
      OR json_extract(NEW.detail, '$.corrected') < 0
      OR json_extract(NEW.detail, '$.unchanged') < 0
      OR json_extract(NEW.detail, '$.conflicts_preserved') < 0
      OR json_extract(NEW.detail, '$.rejected') < 0
        THEN RAISE(ABORT, 'ingest outcome counts must be non-negative')
    WHEN json_type(NEW.detail, '$.rejections') <> 'array'
        THEN RAISE(ABORT, 'ingest outcome rejections must be an array')
    WHEN EXISTS (
        SELECT 1 FROM json_each(NEW.detail, '$.rejections') AS rejection
        WHERE json_type(rejection.value, '$.source_row_number') <> 'integer'
           OR json_extract(rejection.value, '$.source_row_number') < 0
           OR json_type(rejection.value, '$.code') <> 'text'
           OR length(json_extract(rejection.value, '$.code')) = 0
           OR json_type(rejection.value, '$.message') <> 'text'
           OR length(json_extract(rejection.value, '$.message')) = 0
    )
        THEN RAISE(ABORT, 'invalid ingest outcome rejection')
END
""".strip()

MIGRATION_2_STATEMENTS = (
    "DROP TRIGGER ingest_runs_legal_update",
    "ALTER TABLE ingest_runs ADD COLUMN raw_block_id TEXT REFERENCES raw_blocks(raw_block_id) ON UPDATE RESTRICT ON DELETE RESTRICT",
    """
    UPDATE ingest_runs
    SET raw_block_id = (
        SELECT min(p.raw_block_id)
        FROM provenance AS p
        WHERE p.ingest_run_id = ingest_runs.ingest_run_id
    )
    WHERE (
        SELECT count(DISTINCT p.raw_block_id)
        FROM provenance AS p
        WHERE p.ingest_run_id = ingest_runs.ingest_run_id
    ) = 1
    """,
    """
    UPDATE ingest_runs
    SET detail = json_object(
        'format', 'fragarach_ii.ingest_outcome.v1',
        'source_rows', 0,
        'staged', 0,
        'inserted', 0,
        'corrected', 0,
        'unchanged', 0,
        'conflicts_preserved', 0,
        'rejected', 1,
        'rejections', json_array(json_object(
            'source_row_number', 0,
            'code', 'LEGACY_DETAIL',
            'message', detail
        ))
    )
    WHERE detail IS NOT NULL
    """,
    """
    CREATE TRIGGER ingest_runs_legal_update
    BEFORE UPDATE ON ingest_runs
    BEGIN
        SELECT CASE
            WHEN NEW.ingest_run_id <> OLD.ingest_run_id
              OR NEW.kind <> OLD.kind
              OR NEW.started_at_utc <> OLD.started_at_utc
              OR NEW.raw_block_id IS NOT OLD.raw_block_id
            THEN RAISE(ABORT, 'ingest run identity is immutable')
            WHEN OLD.status = 'registered' AND NEW.status IN ('active', 'failed') THEN NULL
            WHEN OLD.status = 'active' AND NEW.status IN ('committed', 'rolled_back', 'failed') THEN NULL
            ELSE RAISE(ABORT, 'illegal ingest run transition')
        END;
    END
    """,
    f"""
    CREATE TRIGGER ingest_runs_outcome_insert
    BEFORE INSERT ON ingest_runs
    WHEN NEW.detail IS NOT NULL
    BEGIN
        SELECT {_OUTCOME_VALIDATION_CASE};
    END
    """,
    f"""
    CREATE TRIGGER ingest_runs_outcome_update
    BEFORE UPDATE OF detail ON ingest_runs
    WHEN NEW.detail IS NOT NULL
    BEGIN
        SELECT {_OUTCOME_VALIDATION_CASE};
    END
    """,
    """
    CREATE TABLE provenance_v2 (
        provenance_event_id TEXT PRIMARY KEY CHECK (length(provenance_event_id) > 0),
        ingest_run_id TEXT NOT NULL,
        raw_block_id TEXT NOT NULL,
        symbol TEXT NOT NULL CHECK (length(symbol) > 0),
        timeframe TEXT NOT NULL CHECK (length(timeframe) > 0),
        timestamp INTEGER NOT NULL,
        source_row_number INTEGER NOT NULL CHECK (source_row_number >= 0),
        merge_action TEXT NOT NULL CHECK (
            merge_action IN ('INSERT', 'UNCHANGED', 'CONFLICT_PRESERVED', 'CORRECTED')
        ),
        candidate_open TEXT NOT NULL CHECK (length(candidate_open) > 0),
        candidate_high TEXT NOT NULL CHECK (length(candidate_high) > 0),
        candidate_low TEXT NOT NULL CHECK (length(candidate_low) > 0),
        candidate_close TEXT NOT NULL CHECK (length(candidate_close) > 0),
        candidate_volume TEXT CHECK (candidate_volume IS NULL OR length(candidate_volume) > 0),
        prior_open TEXT,
        prior_high TEXT,
        prior_low TEXT,
        prior_close TEXT,
        prior_volume TEXT,
        supersedes_event_id TEXT,
        recorded_at TEXT NOT NULL,
        FOREIGN KEY (ingest_run_id) REFERENCES ingest_runs(ingest_run_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        FOREIGN KEY (raw_block_id) REFERENCES raw_blocks(raw_block_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        FOREIGN KEY (symbol, timeframe, timestamp)
            REFERENCES bars(asset, timeframe, open_time_utc)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        FOREIGN KEY (supersedes_event_id) REFERENCES provenance_v2(provenance_event_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        CHECK (
            (merge_action = 'INSERT'
             AND prior_open IS NULL AND prior_high IS NULL AND prior_low IS NULL
             AND prior_close IS NULL AND prior_volume IS NULL
             AND supersedes_event_id IS NULL)
            OR
            (merge_action <> 'INSERT'
             AND prior_open IS NOT NULL AND prior_high IS NOT NULL
             AND prior_low IS NOT NULL AND prior_close IS NOT NULL)
        ),
        CHECK (
            (merge_action = 'CORRECTED' AND supersedes_event_id IS NOT NULL)
            OR (merge_action <> 'CORRECTED' AND supersedes_event_id IS NULL)
        )
    ) STRICT
    """,
    """
    INSERT INTO provenance_v2 (
        provenance_event_id, ingest_run_id, raw_block_id, symbol, timeframe,
        timestamp, source_row_number, merge_action,
        candidate_open, candidate_high, candidate_low, candidate_close,
        candidate_volume, prior_open, prior_high, prior_low, prior_close,
        prior_volume, supersedes_event_id, recorded_at
    )
    SELECT
        lower(hex(randomblob(16))), p.ingest_run_id, p.raw_block_id,
        p.asset, p.timeframe, p.open_time_utc,
        CASE
            WHEN p.source_record_ref GLOB 'line:[0-9]*'
            THEN CAST(substr(p.source_record_ref, 6) AS INTEGER)
            ELSE 0
        END,
        'INSERT', b.open, b.high, b.low, b.close, b.volume,
        NULL, NULL, NULL, NULL, NULL, NULL, p.observed_at_utc
    FROM provenance AS p
    JOIN bars AS b
      ON b.asset = p.asset
     AND b.timeframe = p.timeframe
     AND b.open_time_utc = p.open_time_utc
    ORDER BY p.asset, p.timeframe, p.open_time_utc, p.raw_block_id, p.source_record_ref
    """,
    "DROP TRIGGER provenance_no_update",
    "DROP TRIGGER provenance_no_delete",
    "DROP TABLE provenance",
    "ALTER TABLE provenance_v2 RENAME TO provenance",
    """
    CREATE TRIGGER provenance_correction_lineage
    BEFORE INSERT ON provenance
    WHEN NEW.merge_action = 'CORRECTED'
    BEGIN
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM provenance AS prior
            WHERE prior.provenance_event_id = NEW.supersedes_event_id
              AND prior.symbol = NEW.symbol
              AND prior.timeframe = NEW.timeframe
              AND prior.timestamp = NEW.timestamp
              AND prior.merge_action IN ('INSERT', 'CORRECTED')
              AND prior.candidate_open = NEW.prior_open
              AND prior.candidate_high = NEW.prior_high
              AND prior.candidate_low = NEW.prior_low
              AND prior.candidate_close = NEW.prior_close
              AND prior.candidate_volume IS NEW.prior_volume
              AND prior.recorded_at <= NEW.recorded_at
        ) THEN RAISE(ABORT, 'invalid correction lineage') END;
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
)


def migration_2_checksum() -> str:
    """Return the stable checksum of the SPEC-001A executable statements."""

    source = "\n-- statement --\n".join(
        statement.strip() for statement in MIGRATION_2_STATEMENTS
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
