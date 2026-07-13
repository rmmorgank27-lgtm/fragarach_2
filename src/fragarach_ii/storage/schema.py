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
        "instrument_registrations",
        "evidence_lanes",
        "authority_events",
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


MIGRATION_3_NAME = "SPEC-003A lane validation summary foundation amendment"

_VALIDATION_SUMMARY_KEYS = (
    "format",
    "symbol",
    "timeframe",
    "calendar_id",
    "calendar_version",
    "calendar_checksum",
    "gap_doctrine_id",
    "gap_doctrine_version",
    "gap_doctrine_checksum",
    "validator_version",
    "through_date",
    "expected_session_count",
    "present_expected_session_count",
    "missing_expected_session_count",
    "outside_expected_session_count",
    "empty_week_count",
    "empty_month_count",
    "latest_expected_session",
    "latest_expected_session_present",
    "material_gap_count",
    "non_material_gap_count",
    "result_checksum",
    "validation_observed_at",
)

_VALIDATION_SUMMARY_KEY_SQL = ", ".join(
    f"'{key}'" for key in _VALIDATION_SUMMARY_KEYS
)

_VALIDATION_SUMMARY_CASE = f"""
CASE
    WHEN json_valid(NEW.validation_summary) = 0
        THEN RAISE(ABORT, 'lane validation summary must be valid JSON')
    WHEN json_extract(NEW.validation_summary, '$.format')
         <> 'fragarach_ii.lane_validation_summary.v1'
        THEN RAISE(ABORT, 'invalid lane validation summary format')
    WHEN (SELECT count(*) FROM json_each(NEW.validation_summary))
         <> {len(_VALIDATION_SUMMARY_KEYS)}
      OR EXISTS (
        SELECT 1 FROM json_each(NEW.validation_summary)
        WHERE key NOT IN ({_VALIDATION_SUMMARY_KEY_SQL})
      )
        THEN RAISE(ABORT, 'invalid lane validation summary keys')
    WHEN json_type(NEW.validation_summary, '$.symbol') <> 'text'
      OR json_extract(NEW.validation_summary, '$.symbol') <> NEW.asset
      OR json_type(NEW.validation_summary, '$.timeframe') <> 'text'
      OR json_extract(NEW.validation_summary, '$.timeframe') <> NEW.timeframe
        THEN RAISE(ABORT, 'lane validation summary identity mismatch')
    WHEN json_type(NEW.validation_summary, '$.calendar_id') <> 'text'
      OR length(json_extract(NEW.validation_summary, '$.calendar_id')) = 0
      OR json_type(NEW.validation_summary, '$.calendar_version') <> 'integer'
      OR json_extract(NEW.validation_summary, '$.calendar_version') < 1
      OR json_type(NEW.validation_summary, '$.gap_doctrine_id') <> 'text'
      OR length(json_extract(NEW.validation_summary, '$.gap_doctrine_id')) = 0
      OR json_type(NEW.validation_summary, '$.gap_doctrine_version') <> 'integer'
      OR json_extract(NEW.validation_summary, '$.gap_doctrine_version') < 1
      OR json_type(NEW.validation_summary, '$.validator_version') <> 'text'
      OR length(json_extract(NEW.validation_summary, '$.validator_version')) = 0
        THEN RAISE(ABORT, 'invalid lane validation summary version identity')
    WHEN json_type(NEW.validation_summary, '$.calendar_checksum') <> 'text'
      OR length(json_extract(NEW.validation_summary, '$.calendar_checksum')) <> 64
      OR json_extract(NEW.validation_summary, '$.calendar_checksum') GLOB '*[^0-9a-f]*'
      OR json_type(NEW.validation_summary, '$.gap_doctrine_checksum') <> 'text'
      OR length(json_extract(NEW.validation_summary, '$.gap_doctrine_checksum')) <> 64
      OR json_extract(NEW.validation_summary, '$.gap_doctrine_checksum') GLOB '*[^0-9a-f]*'
      OR json_type(NEW.validation_summary, '$.result_checksum') <> 'text'
      OR length(json_extract(NEW.validation_summary, '$.result_checksum')) <> 64
      OR json_extract(NEW.validation_summary, '$.result_checksum') GLOB '*[^0-9a-f]*'
        THEN RAISE(ABORT, 'invalid lane validation summary checksum')
    WHEN json_type(NEW.validation_summary, '$.through_date') <> 'text'
      OR length(json_extract(NEW.validation_summary, '$.through_date')) <> 10
      OR date(json_extract(NEW.validation_summary, '$.through_date'))
         <> json_extract(NEW.validation_summary, '$.through_date')
      OR (
        json_type(NEW.validation_summary, '$.latest_expected_session') <> 'null'
        AND (
          json_type(NEW.validation_summary, '$.latest_expected_session') <> 'text'
          OR length(json_extract(NEW.validation_summary, '$.latest_expected_session')) <> 10
          OR date(json_extract(NEW.validation_summary, '$.latest_expected_session'))
             <> json_extract(NEW.validation_summary, '$.latest_expected_session')
        )
      )
      OR json_type(NEW.validation_summary, '$.validation_observed_at') <> 'text'
      OR length(json_extract(NEW.validation_summary, '$.validation_observed_at')) = 0
        THEN RAISE(ABORT, 'invalid lane validation summary date')
    WHEN json_type(NEW.validation_summary, '$.expected_session_count') <> 'integer'
      OR json_type(NEW.validation_summary, '$.present_expected_session_count') <> 'integer'
      OR json_type(NEW.validation_summary, '$.missing_expected_session_count') <> 'integer'
      OR json_type(NEW.validation_summary, '$.outside_expected_session_count') <> 'integer'
      OR json_type(NEW.validation_summary, '$.empty_week_count') <> 'integer'
      OR json_type(NEW.validation_summary, '$.empty_month_count') <> 'integer'
      OR json_type(NEW.validation_summary, '$.material_gap_count') <> 'integer'
      OR json_type(NEW.validation_summary, '$.non_material_gap_count') <> 'integer'
        THEN RAISE(ABORT, 'lane validation summary counts must be integers')
    WHEN json_extract(NEW.validation_summary, '$.expected_session_count') < 0
      OR json_extract(NEW.validation_summary, '$.present_expected_session_count') < 0
      OR json_extract(NEW.validation_summary, '$.missing_expected_session_count') < 0
      OR json_extract(NEW.validation_summary, '$.outside_expected_session_count') < 0
      OR json_extract(NEW.validation_summary, '$.empty_week_count') < 0
      OR json_extract(NEW.validation_summary, '$.empty_month_count') < 0
      OR json_extract(NEW.validation_summary, '$.material_gap_count') < 0
      OR json_extract(NEW.validation_summary, '$.non_material_gap_count') < 0
      OR json_extract(NEW.validation_summary, '$.present_expected_session_count')
         + json_extract(NEW.validation_summary, '$.missing_expected_session_count')
         <> json_extract(NEW.validation_summary, '$.expected_session_count')
        THEN RAISE(ABORT, 'invalid lane validation summary counts')
    WHEN json_type(NEW.validation_summary, '$.latest_expected_session_present')
         NOT IN ('true', 'false')
        THEN RAISE(ABORT, 'latest expected session presence must be boolean')
END
""".strip()

MIGRATION_3_STATEMENTS = (
    "ALTER TABLE lane_state ADD COLUMN validation_summary TEXT",
    f"""
    CREATE TRIGGER lane_state_validation_summary_insert
    BEFORE INSERT ON lane_state
    WHEN NEW.validation_summary IS NOT NULL
    BEGIN
        SELECT {_VALIDATION_SUMMARY_CASE};
    END
    """,
    f"""
    CREATE TRIGGER lane_state_validation_summary_update
    BEFORE UPDATE OF validation_summary ON lane_state
    WHEN NEW.validation_summary IS NOT NULL
    BEGIN
        SELECT {_VALIDATION_SUMMARY_CASE};
    END
    """,
)


def migration_3_checksum() -> str:
    """Return the stable checksum of the SPEC-003A executable statements."""

    source = "\n-- statement --\n".join(
        statement.strip() for statement in MIGRATION_3_STATEMENTS
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


MIGRATION_4_NAME = "SPEC-006A instrument registration authority foundation amendment"

MIGRATION_4_STATEMENTS = (
    """
    CREATE TABLE instrument_registrations (
        asset TEXT NOT NULL, timeframe TEXT NOT NULL,
        registration_contract TEXT NOT NULL, registration_contract_version INTEGER NOT NULL,
        instrument_family TEXT NOT NULL, local_symbol TEXT NOT NULL, aliases_json TEXT NOT NULL,
        display_name TEXT NOT NULL, instrument_type TEXT NOT NULL, asset_class TEXT NOT NULL,
        representation_type TEXT NOT NULL, underlying_reference TEXT, contract_or_series TEXT,
        semantic_equivalence TEXT NOT NULL, jurisdiction TEXT, trading_currency TEXT NOT NULL,
        exchange_name TEXT NOT NULL, exchange_mic TEXT,
        provider_id TEXT NOT NULL, provider_contract TEXT NOT NULL, provider_symbol TEXT NOT NULL,
        provider_exchange TEXT, provider_country TEXT, provider_instrument_type TEXT NOT NULL,
        provider_identity_key TEXT NOT NULL,
        calendar_id TEXT NOT NULL, calendar_version INTEGER NOT NULL,
        gap_doctrine_id TEXT NOT NULL, gap_doctrine_version INTEGER NOT NULL,
        registration_status TEXT NOT NULL, registered_at_utc TEXT NOT NULL,
        evidence_confirmed_at_utc TEXT, identity_json TEXT NOT NULL,
        identity_checksum_sha256 TEXT NOT NULL,
        PRIMARY KEY (asset,timeframe),
        UNIQUE (provider_identity_key,timeframe), UNIQUE (identity_checksum_sha256),
        CHECK (length(asset)>0 AND asset=trim(asset) AND asset=upper(asset)
               AND asset NOT GLOB '*[^A-Z0-9._-]*'),
        CHECK (timeframe='D1'),
        CHECK (registration_contract='INSTRUMENT_REGISTRATION_V1' AND registration_contract_version=1),
        CHECK (length(instrument_family)>0 AND instrument_family=trim(instrument_family)
               AND instrument_family=upper(instrument_family) AND instrument_family NOT GLOB '*[^A-Z0-9._-]*'),
        CHECK (length(local_symbol)>0 AND local_symbol=trim(local_symbol)
               AND local_symbol=upper(local_symbol) AND local_symbol NOT GLOB '*[^A-Z0-9._-]*'),
        CHECK (json_valid(aliases_json) AND json_type(aliases_json)='array'),
        CHECK (length(display_name)>0 AND display_name=trim(display_name)),
        CHECK (length(instrument_type)>0 AND instrument_type=trim(instrument_type)),
        CHECK (length(asset_class)>0 AND asset_class=trim(asset_class)),
        CHECK (representation_type IN ('CFD','INDEX','ETF','FUTURES','SPOT','FX_SPOT_PAIR','CRYPTO_SPOT_PAIR','COMMON_STOCK')),
        CHECK (semantic_equivalence='DISTINCT_INSTRUMENT'),
        CHECK (length(trading_currency)>0 AND trading_currency=trim(trading_currency)
               AND trading_currency=upper(trading_currency) AND trading_currency NOT GLOB '*[^A-Z0-9]*'),
        CHECK (length(exchange_name)>0 AND exchange_name=trim(exchange_name)),
        CHECK (exchange_mic IS NULL OR (length(exchange_mic)=4 AND exchange_mic=upper(exchange_mic)
               AND exchange_mic NOT GLOB '*[^A-Z0-9]*')),
        CHECK (length(provider_id)>0 AND provider_id=trim(provider_id)),
        CHECK (length(provider_contract)>0 AND provider_contract=trim(provider_contract)),
        CHECK (length(provider_symbol)>0 AND provider_symbol=trim(provider_symbol)),
        CHECK (length(provider_instrument_type)>0 AND provider_instrument_type=trim(provider_instrument_type)),
        CHECK (length(provider_identity_key)>0 AND provider_identity_key=trim(provider_identity_key)),
        CHECK (length(calendar_id)>0 AND calendar_id=trim(calendar_id) AND calendar_version>0),
        CHECK (length(gap_doctrine_id)>0 AND gap_doctrine_id=trim(gap_doctrine_id) AND gap_doctrine_version>0),
        CHECK (registration_status IN ('REGISTERED_NO_EVIDENCE','REGISTERED_WITH_EVIDENCE')),
        CHECK (registered_at_utc=trim(registered_at_utc) AND julianday(registered_at_utc) IS NOT NULL
               AND substr(registered_at_utc,-6)='+00:00'),
        CHECK ((registration_status='REGISTERED_NO_EVIDENCE' AND evidence_confirmed_at_utc IS NULL)
               OR (registration_status='REGISTERED_WITH_EVIDENCE' AND evidence_confirmed_at_utc IS NOT NULL
                   AND julianday(evidence_confirmed_at_utc) IS NOT NULL AND substr(evidence_confirmed_at_utc,-6)='+00:00')),
        CHECK (json_valid(identity_json)),
        CHECK (length(identity_checksum_sha256)=64 AND identity_checksum_sha256 NOT GLOB '*[^0-9a-f]*'),
        CHECK (representation_type<>'FUTURES' OR contract_or_series IS NOT NULL),
        CHECK (instr(asset,'.')=0 OR asset=instrument_family||'.'||local_symbol)
    ) STRICT, WITHOUT ROWID
    """,
    """
    INSERT INTO instrument_registrations VALUES
    ('AUDUSD','D1','INSTRUMENT_REGISTRATION_V1',1,'AUDUSD','AUDUSD','[]','Australian Dollar / US Dollar','FX_SPOT_PAIR','FX','FX_SPOT_PAIR',NULL,NULL,'DISTINCT_INSTRUMENT',NULL,'USD','OTC',NULL,'TWELVE_DATA','TWELVE_DATA_TIME_SERIES_D1_V1','AUD/USD',NULL,NULL,'Physical Currency','["TWELVE_DATA","AUD/USD",null,"Physical Currency","USD",null]','FX_D1_V1',1,'FRAGARACH_II_D1_GAP_DOCTRINE_V1',1,'REGISTERED_WITH_EVIDENCE','2026-07-10T13:55:08.321103+00:00','2026-07-10T13:55:08.321103+00:00','{"aliases":[],"asset":"AUDUSD","asset_class":"FX","calendar_id":"FX_D1_V1","calendar_version":1,"contract_or_series":null,"display_name":"Australian Dollar / US Dollar","exchange_mic":null,"exchange_name":"OTC","gap_doctrine_id":"FRAGARACH_II_D1_GAP_DOCTRINE_V1","gap_doctrine_version":1,"instrument_family":"AUDUSD","instrument_type":"FX_SPOT_PAIR","jurisdiction":null,"local_symbol":"AUDUSD","provider_contract":"TWELVE_DATA_TIME_SERIES_D1_V1","provider_country":null,"provider_exchange":null,"provider_id":"TWELVE_DATA","provider_identity_key":"[\\"TWELVE_DATA\\",\\"AUD/USD\\",null,\\"Physical Currency\\",\\"USD\\",null]","provider_instrument_type":"Physical Currency","provider_symbol":"AUD/USD","registration_contract":"INSTRUMENT_REGISTRATION_V1","registration_contract_version":1,"representation_type":"FX_SPOT_PAIR","semantic_equivalence":"DISTINCT_INSTRUMENT","timeframe":"D1","trading_currency":"USD","underlying_reference":null}','20c0355ae9ca4b6e1ffe6f24f5dc7920d036757e132c3e33e1648d5a86b7730f'),
    ('XAUUSD','D1','INSTRUMENT_REGISTRATION_V1',1,'GOLD','XAUUSD','[]','Gold Spot / US Dollar','PRECIOUS_METAL_SPOT_PAIR','METALS','SPOT',NULL,NULL,'DISTINCT_INSTRUMENT',NULL,'USD','OTC',NULL,'TWELVE_DATA','TWELVE_DATA_TIME_SERIES_D1_V1','XAU/USD',NULL,NULL,'Precious Metal','["TWELVE_DATA","XAU/USD",null,"Precious Metal","USD",null]','METALS_D1_V1',1,'FRAGARACH_II_D1_GAP_DOCTRINE_V1',1,'REGISTERED_WITH_EVIDENCE','2026-07-10T13:55:08.686443+00:00','2026-07-10T13:55:08.686443+00:00','{"aliases":[],"asset":"XAUUSD","asset_class":"METALS","calendar_id":"METALS_D1_V1","calendar_version":1,"contract_or_series":null,"display_name":"Gold Spot / US Dollar","exchange_mic":null,"exchange_name":"OTC","gap_doctrine_id":"FRAGARACH_II_D1_GAP_DOCTRINE_V1","gap_doctrine_version":1,"instrument_family":"GOLD","instrument_type":"PRECIOUS_METAL_SPOT_PAIR","jurisdiction":null,"local_symbol":"XAUUSD","provider_contract":"TWELVE_DATA_TIME_SERIES_D1_V1","provider_country":null,"provider_exchange":null,"provider_id":"TWELVE_DATA","provider_identity_key":"[\\"TWELVE_DATA\\",\\"XAU/USD\\",null,\\"Precious Metal\\",\\"USD\\",null]","provider_instrument_type":"Precious Metal","provider_symbol":"XAU/USD","registration_contract":"INSTRUMENT_REGISTRATION_V1","registration_contract_version":1,"representation_type":"SPOT","semantic_equivalence":"DISTINCT_INSTRUMENT","timeframe":"D1","trading_currency":"USD","underlying_reference":null}','f296a6ed305bc12146b6ed84a2fee22fcb70f1697889100c6ebaaa06074d136a'),
    ('BTCUSD','D1','INSTRUMENT_REGISTRATION_V1',1,'BITCOIN','BTCUSD','[]','Bitcoin / US Dollar','CRYPTO_SPOT_PAIR','CRYPTO','CRYPTO_SPOT_PAIR',NULL,NULL,'DISTINCT_INSTRUMENT',NULL,'USD','Coinbase Pro',NULL,'TWELVE_DATA','TWELVE_DATA_TIME_SERIES_D1_V1','BTC/USD','Coinbase Pro',NULL,'Digital Currency','["TWELVE_DATA","BTC/USD","Coinbase Pro","Digital Currency","USD",null]','CRYPTO_D1_V1',1,'FRAGARACH_II_D1_GAP_DOCTRINE_V1',1,'REGISTERED_WITH_EVIDENCE','2026-07-10T13:55:09.027943+00:00','2026-07-10T13:55:09.027943+00:00','{"aliases":[],"asset":"BTCUSD","asset_class":"CRYPTO","calendar_id":"CRYPTO_D1_V1","calendar_version":1,"contract_or_series":null,"display_name":"Bitcoin / US Dollar","exchange_mic":null,"exchange_name":"Coinbase Pro","gap_doctrine_id":"FRAGARACH_II_D1_GAP_DOCTRINE_V1","gap_doctrine_version":1,"instrument_family":"BITCOIN","instrument_type":"CRYPTO_SPOT_PAIR","jurisdiction":null,"local_symbol":"BTCUSD","provider_contract":"TWELVE_DATA_TIME_SERIES_D1_V1","provider_country":null,"provider_exchange":"Coinbase Pro","provider_id":"TWELVE_DATA","provider_identity_key":"[\\"TWELVE_DATA\\",\\"BTC/USD\\",\\"Coinbase Pro\\",\\"Digital Currency\\",\\"USD\\",null]","provider_instrument_type":"Digital Currency","provider_symbol":"BTC/USD","registration_contract":"INSTRUMENT_REGISTRATION_V1","registration_contract_version":1,"representation_type":"CRYPTO_SPOT_PAIR","semantic_equivalence":"DISTINCT_INSTRUMENT","timeframe":"D1","trading_currency":"USD","underlying_reference":null}','f3bbb3d7770a3ae0668d8b2a68e0e224df91123c4cff96e226e0223429a1042b')
    """,
    """UPDATE instrument_registrations
       SET registration_status='REGISTERED_NO_EVIDENCE', evidence_confirmed_at_utc=NULL
       WHERE NOT EXISTS (SELECT 1 FROM bars b WHERE b.asset=instrument_registrations.asset AND b.timeframe=instrument_registrations.timeframe)""",
    """INSERT INTO instrument_registrations(asset)
       SELECT 'INVALID' WHERE EXISTS (
         SELECT asset,timeframe FROM bars EXCEPT SELECT asset,timeframe FROM instrument_registrations
       ) OR EXISTS (
         SELECT asset,timeframe FROM lane_state EXCEPT SELECT asset,timeframe FROM instrument_registrations
       )""",
    """
    CREATE TRIGGER instrument_registrations_alias_insert BEFORE INSERT ON instrument_registrations BEGIN
      SELECT CASE WHEN EXISTS (
        SELECT 1 FROM json_each(NEW.aliases_json) a
        WHERE json_type(a.value)<>'object' OR (SELECT count(*) FROM json_each(a.value))<>3
          OR json_type(a.value,'$.alias')<>'text' OR json_type(a.value,'$.normalized_alias')<>'text'
          OR json_extract(a.value,'$.alias_type') NOT IN ('OPERATOR_SYMBOL','COMMON_NAME','PLATFORM_SYMBOL','LEGACY_SYMBOL')
          OR json_extract(a.value,'$.normalized_alias')<>upper(trim(json_extract(a.value,'$.normalized_alias')))
      ) OR (SELECT count(*) FROM json_each(NEW.aliases_json))<>(SELECT count(DISTINCT json_extract(value,'$.normalized_alias')) FROM json_each(NEW.aliases_json))
      THEN RAISE(ABORT,'invalid aliases') END;
      SELECT CASE WHEN EXISTS (
        SELECT 1 FROM instrument_registrations r WHERE r.asset IN (NEW.asset,NEW.local_symbol) OR r.local_symbol IN (NEW.asset,NEW.local_symbol)
        OR EXISTS (SELECT 1 FROM json_each(r.aliases_json) WHERE json_extract(value,'$.normalized_alias') IN (NEW.asset,NEW.local_symbol))
        OR EXISTS (SELECT 1 FROM json_each(NEW.aliases_json) n WHERE json_extract(n.value,'$.normalized_alias') IN (r.asset,r.local_symbol)
          OR EXISTS (SELECT 1 FROM json_each(r.aliases_json) e WHERE json_extract(e.value,'$.normalized_alias')=json_extract(n.value,'$.normalized_alias')))
      ) THEN RAISE(ABORT,'registration naming collision') END;
    END
    """,
    """
    CREATE TRIGGER instrument_registrations_no_delete BEFORE DELETE ON instrument_registrations
    BEGIN SELECT RAISE(ABORT,'instrument registrations cannot be deleted'); END
    """,
    """
    CREATE TRIGGER instrument_registrations_update BEFORE UPDATE ON instrument_registrations BEGIN
      SELECT CASE WHEN NEW.asset IS NOT OLD.asset OR NEW.timeframe IS NOT OLD.timeframe OR NEW.registration_contract IS NOT OLD.registration_contract
        OR NEW.registration_contract_version IS NOT OLD.registration_contract_version OR NEW.instrument_family IS NOT OLD.instrument_family
        OR NEW.local_symbol IS NOT OLD.local_symbol OR NEW.aliases_json IS NOT OLD.aliases_json OR NEW.display_name IS NOT OLD.display_name
        OR NEW.instrument_type IS NOT OLD.instrument_type OR NEW.asset_class IS NOT OLD.asset_class OR NEW.representation_type IS NOT OLD.representation_type
        OR NEW.underlying_reference IS NOT OLD.underlying_reference OR NEW.contract_or_series IS NOT OLD.contract_or_series
        OR NEW.semantic_equivalence IS NOT OLD.semantic_equivalence OR NEW.jurisdiction IS NOT OLD.jurisdiction OR NEW.trading_currency IS NOT OLD.trading_currency
        OR NEW.exchange_name IS NOT OLD.exchange_name OR NEW.exchange_mic IS NOT OLD.exchange_mic OR NEW.provider_id IS NOT OLD.provider_id
        OR NEW.provider_contract IS NOT OLD.provider_contract OR NEW.provider_symbol IS NOT OLD.provider_symbol OR NEW.provider_exchange IS NOT OLD.provider_exchange
        OR NEW.provider_country IS NOT OLD.provider_country OR NEW.provider_instrument_type IS NOT OLD.provider_instrument_type
        OR NEW.provider_identity_key IS NOT OLD.provider_identity_key OR NEW.calendar_id IS NOT OLD.calendar_id OR NEW.calendar_version IS NOT OLD.calendar_version
        OR NEW.gap_doctrine_id IS NOT OLD.gap_doctrine_id OR NEW.gap_doctrine_version IS NOT OLD.gap_doctrine_version
        OR NEW.registered_at_utc IS NOT OLD.registered_at_utc OR NEW.identity_json IS NOT OLD.identity_json OR NEW.identity_checksum_sha256 IS NOT OLD.identity_checksum_sha256
      THEN RAISE(ABORT,'instrument registration identity is immutable') END;
      SELECT CASE WHEN NOT (OLD.registration_status='REGISTERED_NO_EVIDENCE' AND NEW.registration_status='REGISTERED_WITH_EVIDENCE'
        AND OLD.evidence_confirmed_at_utc IS NULL AND NEW.evidence_confirmed_at_utc IS NOT NULL
        AND EXISTS(SELECT 1 FROM bars WHERE asset=OLD.asset AND timeframe=OLD.timeframe))
      THEN RAISE(ABORT,'invalid registration status transition') END;
    END
    """,
    """
    CREATE TRIGGER bars_require_registration_insert BEFORE INSERT ON bars BEGIN
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM instrument_registrations r WHERE r.asset=NEW.asset AND r.timeframe=NEW.timeframe)
      THEN RAISE(ABORT,'canonical evidence requires registration') END;
    END
    """,
    """
    CREATE TRIGGER bars_require_registration_update BEFORE UPDATE OF asset,timeframe ON bars BEGIN
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM instrument_registrations r WHERE r.asset=NEW.asset AND r.timeframe=NEW.timeframe)
      THEN RAISE(ABORT,'canonical evidence requires registration') END;
    END
    """,
)


def migration_4_checksum() -> str:
    source = "\n-- statement --\n".join(statement.strip() for statement in MIGRATION_4_STATEMENTS)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


MIGRATION_5_NAME = "SPEC-007 generic evidence lane foundation"

MIGRATION_5_STATEMENTS = (
    "DROP TRIGGER bars_require_registration_insert",
    "DROP TRIGGER bars_require_registration_update",
    """
    CREATE TABLE evidence_lanes (
        asset TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        registration_timeframe TEXT NOT NULL,
        lane_contract TEXT NOT NULL,
        lane_contract_version INTEGER NOT NULL,
        created_at_utc TEXT NOT NULL,
        PRIMARY KEY (asset,timeframe),
        FOREIGN KEY (asset,registration_timeframe)
          REFERENCES instrument_registrations(asset,timeframe)
          ON UPDATE RESTRICT ON DELETE RESTRICT,
        CHECK (length(asset)>0 AND asset=trim(asset) AND asset=upper(asset)),
        CHECK (length(timeframe)>0 AND timeframe=trim(timeframe) AND timeframe=upper(timeframe)),
        CHECK (registration_timeframe='D1'),
        CHECK (lane_contract='EVIDENCE_LANE_V1' AND lane_contract_version=1),
        CHECK (created_at_utc=trim(created_at_utc) AND julianday(created_at_utc) IS NOT NULL
               AND substr(created_at_utc,-6)='+00:00')
    ) STRICT, WITHOUT ROWID
    """,
    """
    INSERT INTO evidence_lanes
      (asset,timeframe,registration_timeframe,lane_contract,lane_contract_version,created_at_utc)
    SELECT asset,'D1',timeframe,'EVIDENCE_LANE_V1',1,registered_at_utc
    FROM instrument_registrations ORDER BY asset
    """,
    """
    CREATE TRIGGER evidence_lanes_no_update BEFORE UPDATE ON evidence_lanes
    BEGIN SELECT RAISE(ABORT,'evidence lanes are immutable'); END
    """,
    """
    CREATE TRIGGER evidence_lanes_no_delete BEFORE DELETE ON evidence_lanes
    BEGIN SELECT RAISE(ABORT,'evidence lanes cannot be deleted'); END
    """,
    """
    CREATE TRIGGER bars_require_evidence_lane_insert BEFORE INSERT ON bars BEGIN
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM evidence_lanes l WHERE l.asset=NEW.asset AND l.timeframe=NEW.timeframe)
      THEN RAISE(ABORT,'canonical evidence requires evidence lane') END;
    END
    """,
    """
    CREATE TRIGGER bars_require_evidence_lane_update BEFORE UPDATE OF asset,timeframe ON bars BEGIN
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM evidence_lanes l WHERE l.asset=NEW.asset AND l.timeframe=NEW.timeframe)
      THEN RAISE(ABORT,'canonical evidence requires evidence lane') END;
    END
    """,
)


def migration_5_checksum() -> str:
    source = "\n-- statement --\n".join(statement.strip() for statement in MIGRATION_5_STATEMENTS)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


MIGRATION_6_NAME = "SPEC-008A1 immutable authority ledger amendment"

_AUTHORITY_EVENT_KINDS = (
    "'LEGACY_REGISTRATION_BOUND','REGISTRATION_DECLARED','REGISTRATION_REVISED',"
    "'REGISTRATION_REJECTED','REGISTRATION_SUPERSEDED','PROVIDER_MAPPING_DISCOVERED',"
    "'PROVIDER_MAPPING_REVIEWED','PROVIDER_MAPPING_APPROVED','PROVIDER_MAPPING_REJECTED',"
    "'PROVIDER_MAPPING_SUPERSEDED','LEGACY_LANE_BOUND','LANE_CANDIDATE_RETAINED',"
    "'LANE_DECLARED','LANE_REVISED','LANE_REJECTED','LANE_SUPERSEDED',"
    "'ENTITLEMENT_CHANGED','EFFECTIVE_RANGE_CHANGED','AUTHORITY_BINDING_CHANGED',"
    "'COMPATIBILITY_FINDING_RECORDED','COMPATIBILITY_FINDING_SUPERSEDED'"
)

MIGRATION_6_STATEMENTS = (
    f"""
    CREATE TABLE authority_events (
        authority_event_id TEXT PRIMARY KEY,
        ledger_contract TEXT NOT NULL,
        ledger_contract_version INTEGER NOT NULL,
        entity_kind TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        event_kind TEXT NOT NULL,
        supersedes_event_id TEXT,
        effective_from_utc TEXT NOT NULL,
        effective_to_utc TEXT,
        canonical_payload TEXT NOT NULL,
        payload_checksum_sha256 TEXT NOT NULL,
        event_checksum_sha256 TEXT NOT NULL,
        recorded_at_utc TEXT NOT NULL,
        recorded_by TEXT NOT NULL,
        FOREIGN KEY (supersedes_event_id) REFERENCES authority_events(authority_event_id)
          ON UPDATE RESTRICT ON DELETE RESTRICT,
        UNIQUE (event_checksum_sha256),
        CHECK (length(authority_event_id)=64 AND authority_event_id NOT GLOB '*[^0-9a-f]*'),
        CHECK (ledger_contract='AUTHORITY_EVENT_LEDGER_V1' AND ledger_contract_version=1),
        CHECK (entity_kind IN ('INSTRUMENT_REGISTRATION','PROVIDER_MAPPING','EVIDENCE_LANE')),
        CHECK (length(entity_id)>0 AND entity_id=trim(entity_id)),
        CHECK (event_kind IN ({_AUTHORITY_EVENT_KINDS})),
        CHECK (supersedes_event_id IS NULL OR supersedes_event_id<>authority_event_id),
        CHECK (effective_from_utc=trim(effective_from_utc) AND julianday(effective_from_utc) IS NOT NULL
               AND substr(effective_from_utc,-6)='+00:00'),
        CHECK (effective_to_utc IS NULL OR (effective_to_utc=trim(effective_to_utc)
               AND julianday(effective_to_utc) IS NOT NULL AND substr(effective_to_utc,-6)='+00:00'
               AND julianday(effective_to_utc)>julianday(effective_from_utc))),
        CHECK (json_valid(canonical_payload) AND json_type(canonical_payload)='object'),
        CHECK (length(payload_checksum_sha256)=64 AND payload_checksum_sha256 NOT GLOB '*[^0-9a-f]*'),
        CHECK (length(event_checksum_sha256)=64 AND event_checksum_sha256 NOT GLOB '*[^0-9a-f]*'),
        CHECK (length(recorded_by)>0 AND recorded_by=trim(recorded_by)),
        CHECK (recorded_at_utc=trim(recorded_at_utc) AND julianday(recorded_at_utc) IS NOT NULL
               AND substr(recorded_at_utc,-6)='+00:00')
    ) STRICT
    """,
    "CREATE INDEX authority_events_entity_order ON authority_events(entity_kind,entity_id,effective_from_utc,recorded_at_utc,authority_event_id)",
    "CREATE INDEX authority_events_kind_effective ON authority_events(event_kind,effective_from_utc,effective_to_utc)",
    "CREATE INDEX authority_events_payload_checksum ON authority_events(payload_checksum_sha256)",
    "CREATE UNIQUE INDEX authority_events_one_successor ON authority_events(supersedes_event_id) WHERE supersedes_event_id IS NOT NULL",
    """
    CREATE TRIGGER authority_events_no_update BEFORE UPDATE ON authority_events
    BEGIN SELECT RAISE(ABORT,'authority events are immutable'); END
    """,
    """
    CREATE TRIGGER authority_events_no_delete BEFORE DELETE ON authority_events
    BEGIN SELECT RAISE(ABORT,'authority events cannot be deleted'); END
    """,
    """
    CREATE TRIGGER authority_events_validate_insert BEFORE INSERT ON authority_events BEGIN
      SELECT CASE WHEN NEW.authority_event_id<>NEW.event_checksum_sha256
        THEN RAISE(ABORT,'authority event id/checksum mismatch') END;
      SELECT CASE WHEN json_extract(NEW.canonical_payload,'$.format')<>'fragarach_ii.authority_event_payload.v1'
        OR json_extract(NEW.canonical_payload,'$.entity_kind')<>NEW.entity_kind
        OR json_extract(NEW.canonical_payload,'$.entity_id')<>NEW.entity_id
        OR json_extract(NEW.canonical_payload,'$.event_kind')<>NEW.event_kind
        OR json_type(NEW.canonical_payload,'$.authority_bindings')<>'array'
        OR json_type(NEW.canonical_payload,'$.compatibility_state')<>'text'
        OR json_type(NEW.canonical_payload,'$.compatibility_reasons')<>'array'
        OR json_type(NEW.canonical_payload,'$.body')<>'object'
        THEN RAISE(ABORT,'invalid authority event payload envelope') END;
      SELECT CASE WHEN NEW.supersedes_event_id IS NOT NULL AND NOT EXISTS(
        SELECT 1 FROM authority_events p WHERE p.authority_event_id=NEW.supersedes_event_id
          AND p.entity_kind=NEW.entity_kind AND p.entity_id=NEW.entity_id
          AND julianday(NEW.effective_from_utc)>=julianday(p.effective_from_utc))
        THEN RAISE(ABORT,'invalid authority supersession predecessor') END;
      SELECT CASE WHEN
        (NEW.event_kind LIKE 'REGISTRATION_%' OR NEW.event_kind='LEGACY_REGISTRATION_BOUND')
          AND NEW.entity_kind<>'INSTRUMENT_REGISTRATION'
        OR (NEW.event_kind LIKE 'PROVIDER_MAPPING_%' AND NEW.entity_kind<>'PROVIDER_MAPPING')
        OR (NEW.event_kind LIKE 'LANE_%' OR NEW.event_kind='LEGACY_LANE_BOUND')
          AND NEW.entity_kind<>'EVIDENCE_LANE'
        THEN RAISE(ABORT,'invalid authority event kind for entity') END;
    END
    """,
)


def migration_6_checksum() -> str:
    source = "\n-- statement --\n".join(statement.strip() for statement in MIGRATION_6_STATEMENTS)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


MIGRATION_7_NAME = "SPEC-017 provider-independent registration contract amendment"

MIGRATION_7_STATEMENTS = (
    """
    CREATE TABLE instrument_registrations_v2 (
        asset TEXT NOT NULL, timeframe TEXT NOT NULL,
        registration_contract TEXT NOT NULL, registration_contract_version INTEGER NOT NULL,
        instrument_family TEXT NOT NULL, local_symbol TEXT NOT NULL, aliases_json TEXT NOT NULL,
        display_name TEXT NOT NULL, instrument_type TEXT NOT NULL, asset_class TEXT NOT NULL,
        representation_type TEXT NOT NULL, underlying_reference TEXT, contract_or_series TEXT,
        semantic_equivalence TEXT NOT NULL, jurisdiction TEXT, trading_currency TEXT NOT NULL,
        exchange_name TEXT NOT NULL, exchange_mic TEXT,
        provider_id TEXT, provider_contract TEXT, provider_symbol TEXT,
        provider_exchange TEXT, provider_country TEXT, provider_instrument_type TEXT,
        provider_identity_key TEXT,
        calendar_id TEXT NOT NULL, calendar_version INTEGER NOT NULL,
        gap_doctrine_id TEXT NOT NULL, gap_doctrine_version INTEGER NOT NULL,
        registration_status TEXT NOT NULL, registered_at_utc TEXT NOT NULL,
        evidence_confirmed_at_utc TEXT, identity_json TEXT NOT NULL,
        identity_checksum_sha256 TEXT NOT NULL,
        PRIMARY KEY (asset,timeframe),
        UNIQUE (provider_identity_key,timeframe), UNIQUE (identity_checksum_sha256),
        CHECK (length(asset)>0 AND asset=trim(asset) AND asset=upper(asset) AND asset NOT GLOB '*[^A-Z0-9._-]*'),
        CHECK (timeframe='D1'),
        CHECK ((registration_contract='INSTRUMENT_REGISTRATION_V1' AND registration_contract_version=1)
            OR (registration_contract='INSTRUMENT_REGISTRATION_V2' AND registration_contract_version=2)),
        CHECK (length(instrument_family)>0 AND instrument_family=trim(instrument_family) AND instrument_family=upper(instrument_family) AND instrument_family NOT GLOB '*[^A-Z0-9._-]*'),
        CHECK (length(local_symbol)>0 AND local_symbol=trim(local_symbol) AND local_symbol=upper(local_symbol) AND local_symbol NOT GLOB '*[^A-Z0-9._-]*'),
        CHECK (json_valid(aliases_json) AND json_type(aliases_json)='array'),
        CHECK (length(display_name)>0 AND display_name=trim(display_name)),
        CHECK (length(instrument_type)>0 AND length(asset_class)>0),
        CHECK (representation_type IN ('CFD','INDEX','ETF','FUTURES','SPOT','FX_SPOT_PAIR','CRYPTO_SPOT_PAIR','COMMON_STOCK')),
        CHECK (semantic_equivalence='DISTINCT_INSTRUMENT'),
        CHECK (length(trading_currency)>0 AND trading_currency=trim(trading_currency) AND trading_currency=upper(trading_currency) AND trading_currency NOT GLOB '*[^A-Z0-9]*'),
        CHECK (length(exchange_name)>0 AND exchange_name=trim(exchange_name)),
        CHECK (exchange_mic IS NULL OR (length(exchange_mic)=4 AND exchange_mic=upper(exchange_mic) AND exchange_mic NOT GLOB '*[^A-Z0-9]*')),
        CHECK ((registration_status='REGISTERED_UNMAPPED' AND registration_contract='INSTRUMENT_REGISTRATION_V2'
                AND provider_id IS NULL AND provider_contract IS NULL AND provider_symbol IS NULL
                AND provider_instrument_type IS NULL AND provider_identity_key IS NULL)
            OR (registration_status IN ('REGISTERED_NO_EVIDENCE','REGISTERED_WITH_EVIDENCE')
                AND provider_id IS NOT NULL AND length(provider_id)>0 AND provider_contract IS NOT NULL AND length(provider_contract)>0
                AND provider_symbol IS NOT NULL AND length(provider_symbol)>0 AND provider_instrument_type IS NOT NULL
                AND length(provider_instrument_type)>0 AND provider_identity_key IS NOT NULL AND length(provider_identity_key)>0)),
        CHECK (length(calendar_id)>0 AND calendar_version>0 AND length(gap_doctrine_id)>0 AND gap_doctrine_version>0),
        CHECK (registered_at_utc=trim(registered_at_utc) AND julianday(registered_at_utc) IS NOT NULL AND substr(registered_at_utc,-6)='+00:00'),
        CHECK ((registration_status='REGISTERED_NO_EVIDENCE' AND evidence_confirmed_at_utc IS NULL)
            OR (registration_status IN ('REGISTERED_WITH_EVIDENCE','REGISTERED_UNMAPPED')
                AND (evidence_confirmed_at_utc IS NULL OR (julianday(evidence_confirmed_at_utc) IS NOT NULL AND substr(evidence_confirmed_at_utc,-6)='+00:00')))),
        CHECK (json_valid(identity_json)),
        CHECK (length(identity_checksum_sha256)=64 AND identity_checksum_sha256 NOT GLOB '*[^0-9a-f]*'),
        CHECK (representation_type<>'FUTURES' OR contract_or_series IS NOT NULL),
        CHECK (instr(asset,'.')=0 OR asset=instrument_family||'.'||local_symbol)
    ) STRICT, WITHOUT ROWID
    """,
    "INSERT INTO instrument_registrations_v2 SELECT * FROM instrument_registrations",
    """
    CREATE TABLE evidence_lanes_v2 (
        asset TEXT NOT NULL,timeframe TEXT NOT NULL,registration_timeframe TEXT NOT NULL,
        lane_contract TEXT NOT NULL,lane_contract_version INTEGER NOT NULL,created_at_utc TEXT NOT NULL,
        PRIMARY KEY (asset,timeframe),
        FOREIGN KEY (asset,registration_timeframe) REFERENCES instrument_registrations_v2(asset,timeframe) ON UPDATE RESTRICT ON DELETE RESTRICT,
        CHECK (length(asset)>0 AND asset=trim(asset) AND asset=upper(asset)),
        CHECK (length(timeframe)>0 AND timeframe=trim(timeframe) AND timeframe=upper(timeframe)),
        CHECK (registration_timeframe='D1'),CHECK (lane_contract='EVIDENCE_LANE_V1' AND lane_contract_version=1),
        CHECK (created_at_utc=trim(created_at_utc) AND julianday(created_at_utc) IS NOT NULL AND substr(created_at_utc,-6)='+00:00')
    ) STRICT, WITHOUT ROWID
    """,
    "INSERT INTO evidence_lanes_v2 SELECT * FROM evidence_lanes",
    "DROP TRIGGER evidence_lanes_no_update","DROP TRIGGER evidence_lanes_no_delete",
    "DROP TRIGGER bars_require_evidence_lane_insert","DROP TRIGGER bars_require_evidence_lane_update",
    "DROP TABLE evidence_lanes",
    "DROP TRIGGER instrument_registrations_alias_insert","DROP TRIGGER instrument_registrations_no_delete","DROP TRIGGER instrument_registrations_update",
    "DROP TABLE instrument_registrations",
    "ALTER TABLE instrument_registrations_v2 RENAME TO instrument_registrations",
    "ALTER TABLE evidence_lanes_v2 RENAME TO evidence_lanes",
    """CREATE TRIGGER evidence_lanes_no_update BEFORE UPDATE ON evidence_lanes BEGIN SELECT RAISE(ABORT,'evidence lanes are immutable'); END""",
    """CREATE TRIGGER evidence_lanes_no_delete BEFORE DELETE ON evidence_lanes BEGIN SELECT RAISE(ABORT,'evidence lanes cannot be deleted'); END""",
    """CREATE TRIGGER bars_require_evidence_lane_insert BEFORE INSERT ON bars BEGIN SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM evidence_lanes l WHERE l.asset=NEW.asset AND l.timeframe=NEW.timeframe) THEN RAISE(ABORT,'canonical evidence requires evidence lane') END; END""",
    """CREATE TRIGGER bars_require_evidence_lane_update BEFORE UPDATE OF asset,timeframe ON bars BEGIN SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM evidence_lanes l WHERE l.asset=NEW.asset AND l.timeframe=NEW.timeframe) THEN RAISE(ABORT,'canonical evidence requires evidence lane') END; END""",
    """
    CREATE TRIGGER instrument_registrations_alias_insert BEFORE INSERT ON instrument_registrations BEGIN
      SELECT CASE WHEN EXISTS (SELECT 1 FROM json_each(NEW.aliases_json) a
        WHERE json_type(a.value)<>'object' OR json_type(a.value,'$.alias')<>'text'
          OR json_type(a.value,'$.normalized_alias')<>'text' OR json_extract(a.value,'$.alias_type') NOT IN ('OPERATOR_SYMBOL','COMMON_NAME','PLATFORM_SYMBOL','LEGACY_SYMBOL'))
      THEN RAISE(ABORT,'invalid aliases') END;
      SELECT CASE WHEN EXISTS (SELECT 1 FROM instrument_registrations r WHERE r.asset IN (NEW.asset,NEW.local_symbol)
        OR r.local_symbol IN (NEW.asset,NEW.local_symbol)
        OR EXISTS (SELECT 1 FROM json_each(r.aliases_json) WHERE json_extract(value,'$.normalized_alias') IN (NEW.asset,NEW.local_symbol))
        OR EXISTS (SELECT 1 FROM json_each(NEW.aliases_json) n WHERE json_extract(n.value,'$.normalized_alias') IN (r.asset,r.local_symbol)
          OR EXISTS (SELECT 1 FROM json_each(r.aliases_json) e WHERE json_extract(e.value,'$.normalized_alias')=json_extract(n.value,'$.normalized_alias'))))
      THEN RAISE(ABORT,'registration naming collision') END;
    END
    """,
    """CREATE TRIGGER instrument_registrations_no_delete BEFORE DELETE ON instrument_registrations BEGIN SELECT RAISE(ABORT,'instrument registrations cannot be deleted'); END""",
    """
    CREATE TRIGGER instrument_registrations_update BEFORE UPDATE ON instrument_registrations BEGIN
      SELECT CASE WHEN NEW.asset IS NOT OLD.asset OR NEW.timeframe IS NOT OLD.timeframe OR NEW.registration_contract IS NOT OLD.registration_contract
        OR NEW.registration_contract_version IS NOT OLD.registration_contract_version OR NEW.instrument_family IS NOT OLD.instrument_family
        OR NEW.local_symbol IS NOT OLD.local_symbol OR NEW.aliases_json IS NOT OLD.aliases_json OR NEW.display_name IS NOT OLD.display_name
        OR NEW.instrument_type IS NOT OLD.instrument_type OR NEW.asset_class IS NOT OLD.asset_class OR NEW.representation_type IS NOT OLD.representation_type
        OR NEW.underlying_reference IS NOT OLD.underlying_reference OR NEW.contract_or_series IS NOT OLD.contract_or_series
        OR NEW.semantic_equivalence IS NOT OLD.semantic_equivalence OR NEW.jurisdiction IS NOT OLD.jurisdiction OR NEW.trading_currency IS NOT OLD.trading_currency
        OR NEW.exchange_name IS NOT OLD.exchange_name OR NEW.exchange_mic IS NOT OLD.exchange_mic OR NEW.provider_id IS NOT OLD.provider_id
        OR NEW.provider_contract IS NOT OLD.provider_contract OR NEW.provider_symbol IS NOT OLD.provider_symbol OR NEW.provider_exchange IS NOT OLD.provider_exchange
        OR NEW.provider_country IS NOT OLD.provider_country OR NEW.provider_instrument_type IS NOT OLD.provider_instrument_type
        OR NEW.provider_identity_key IS NOT OLD.provider_identity_key OR NEW.calendar_id IS NOT OLD.calendar_id OR NEW.calendar_version IS NOT OLD.calendar_version
        OR NEW.gap_doctrine_id IS NOT OLD.gap_doctrine_id OR NEW.gap_doctrine_version IS NOT OLD.gap_doctrine_version
        OR NEW.registered_at_utc IS NOT OLD.registered_at_utc OR NEW.identity_json IS NOT OLD.identity_json OR NEW.identity_checksum_sha256 IS NOT OLD.identity_checksum_sha256
      THEN RAISE(ABORT,'instrument registration identity is immutable') END;
      SELECT CASE WHEN NOT ((OLD.registration_status='REGISTERED_NO_EVIDENCE' AND NEW.registration_status='REGISTERED_WITH_EVIDENCE'
          AND OLD.evidence_confirmed_at_utc IS NULL AND NEW.evidence_confirmed_at_utc IS NOT NULL)
        OR (OLD.registration_status='REGISTERED_UNMAPPED' AND NEW.registration_status='REGISTERED_UNMAPPED'
          AND OLD.evidence_confirmed_at_utc IS NULL AND NEW.evidence_confirmed_at_utc IS NOT NULL))
        OR NOT EXISTS(SELECT 1 FROM bars WHERE asset=OLD.asset AND timeframe=OLD.timeframe)
      THEN RAISE(ABORT,'invalid registration status transition') END;
    END
    """,
)

def migration_7_checksum() -> str:
    source="\n-- statement --\n".join(statement.strip() for statement in MIGRATION_7_STATEMENTS)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()

MIGRATION_8_NAME = "SPEC-025 intraday validation summary coexistence amendment"
_V2_KEYS=("format","symbol","timeframe","calendar_id","calendar_version","calendar_checksum","session_profile_id","session_profile_version","session_profile_checksum","gap_doctrine_id","gap_doctrine_version","gap_doctrine_checksum","validator_version","boundary_utc","expected_interval_count","present_expected_interval_count","missing_expected_interval_count","outside_expected_interval_count","latest_expected_closed_interval_open_utc","latest_expected_closed_interval_end_utc","latest_expected_closed_interval_present","material_gap_count","non_material_gap_count","result_checksum","validation_observed_at")
_V2_KEY_SQL=", ".join(f"'{key}'" for key in _V2_KEYS)
_V2_CASE=f"""CASE
WHEN (SELECT count(*) FROM json_each(NEW.validation_summary))<>{len(_V2_KEYS)} OR EXISTS(SELECT 1 FROM json_each(NEW.validation_summary) WHERE key NOT IN ({_V2_KEY_SQL})) THEN RAISE(ABORT,'invalid intraday validation summary keys')
WHEN json_extract(NEW.validation_summary,'$.symbol')<>NEW.asset OR json_extract(NEW.validation_summary,'$.timeframe')<>NEW.timeframe THEN RAISE(ABORT,'intraday validation summary identity mismatch')
WHEN json_type(NEW.validation_summary,'$.calendar_version')<>'integer' OR json_type(NEW.validation_summary,'$.session_profile_version')<>'integer' OR json_type(NEW.validation_summary,'$.gap_doctrine_version')<>'integer' THEN RAISE(ABORT,'invalid intraday validation authority version')
WHEN length(json_extract(NEW.validation_summary,'$.calendar_checksum'))<>64 OR length(json_extract(NEW.validation_summary,'$.session_profile_checksum'))<>64 OR length(json_extract(NEW.validation_summary,'$.gap_doctrine_checksum'))<>64 OR length(json_extract(NEW.validation_summary,'$.result_checksum'))<>64 THEN RAISE(ABORT,'invalid intraday validation checksum')
WHEN julianday(json_extract(NEW.validation_summary,'$.boundary_utc')) IS NULL OR julianday(json_extract(NEW.validation_summary,'$.latest_expected_closed_interval_open_utc')) IS NULL OR julianday(json_extract(NEW.validation_summary,'$.latest_expected_closed_interval_end_utc')) IS NULL OR julianday(json_extract(NEW.validation_summary,'$.validation_observed_at')) IS NULL THEN RAISE(ABORT,'invalid intraday validation timestamp')
WHEN json_type(NEW.validation_summary,'$.expected_interval_count')<>'integer' OR json_type(NEW.validation_summary,'$.present_expected_interval_count')<>'integer' OR json_type(NEW.validation_summary,'$.missing_expected_interval_count')<>'integer' OR json_type(NEW.validation_summary,'$.outside_expected_interval_count')<>'integer' OR json_type(NEW.validation_summary,'$.material_gap_count')<>'integer' OR json_type(NEW.validation_summary,'$.non_material_gap_count')<>'integer' OR json_extract(NEW.validation_summary,'$.present_expected_interval_count')+json_extract(NEW.validation_summary,'$.missing_expected_interval_count')<>json_extract(NEW.validation_summary,'$.expected_interval_count') THEN RAISE(ABORT,'invalid intraday validation counts')
WHEN json_type(NEW.validation_summary,'$.latest_expected_closed_interval_present') NOT IN ('true','false') THEN RAISE(ABORT,'invalid intraday latest interval state') END"""
_COEXISTENCE_CASE=f"""CASE
WHEN json_valid(NEW.validation_summary)=0 THEN RAISE(ABORT,'lane validation summary must be valid JSON')
WHEN json_extract(NEW.validation_summary,'$.format')='fragarach_ii.lane_validation_summary.v1' THEN {_VALIDATION_SUMMARY_CASE}
WHEN json_extract(NEW.validation_summary,'$.format')='fragarach_ii.lane_validation_summary.v2' THEN {_V2_CASE}
ELSE RAISE(ABORT,'invalid lane validation summary format') END"""
MIGRATION_8_STATEMENTS=(
 "DROP TRIGGER lane_state_validation_summary_insert","DROP TRIGGER lane_state_validation_summary_update",
 f"CREATE TRIGGER lane_state_validation_summary_insert BEFORE INSERT ON lane_state WHEN NEW.validation_summary IS NOT NULL BEGIN SELECT {_COEXISTENCE_CASE}; END",
 f"CREATE TRIGGER lane_state_validation_summary_update BEFORE UPDATE OF validation_summary ON lane_state WHEN NEW.validation_summary IS NOT NULL BEGIN SELECT {_COEXISTENCE_CASE}; END",
)
def migration_8_checksum() -> str:
    return hashlib.sha256("\n-- statement --\n".join(s.strip() for s in MIGRATION_8_STATEMENTS).encode()).hexdigest()
