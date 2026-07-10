# SPEC-001A — Provenance Event and Evidence-Run Amendment

**Classification:** Foundation Specification amendment  
**Authorization:** Approved by Ray  
**Parent:** SPEC-001 Storage Foundation  
**Status:** Implemented candidate  
**Scope:** Storage contract amendment only

## 1. Purpose and boundary

SPEC-002's mandatory compatibility gate established that SPEC-001 could not unambiguously retain repeated attempts, rejected evidence, competing candidate values, or correction lineage. This amendment corrects those audit-model deficiencies without adding a table or implementing ingestion.

The authority still contains exactly seven application tables. CSV parsing, manual commands, merge execution, providers, calendars, rollups, scheduling, services, and consumer integration remain excluded.

## 2. Evidence-run association

Migration 2 adds nullable `raw_block_id` to `ingest_runs` with a restrictive foreign key to immutable `raw_blocks`. It is nullable for non-evidence administrative and recovery runs. Every manual-ingestion run must provide it through application validation. A manual run processes exactly one raw block; many runs may reference the same raw block.

For migrated SPEC-001 history, a run is backfilled when its existing provenance refers to exactly one distinct raw block. Runs associated with zero or multiple legacy blocks remain null rather than receiving an invented association.

The `raw_block_id` association is immutable after run creation. Kernel writer exclusion, the run state machine, and raw-block update/delete prohibitions remain in force.

## 3. Provenance event schema

The old composite provenance identity is replaced by application-assigned `provenance_event_id TEXT PRIMARY KEY`. New events use random UUID identifiers independent of checksum, row identity, wall-clock time, and ingest-run identity.

Every event contains:

- mandatory `ingest_run_id` and `raw_block_id` restrictive foreign keys;
- canonical key `symbol`, `timeframe`, and integer UTC `timestamp`, referencing `bars`;
- non-negative integer `source_row_number`; zero is reserved for migrated legacy records whose row cannot be recovered;
- `merge_action`, restricted to `INSERT`, `UNCHANGED`, `CONFLICT_PRESERVED`, or `CORRECTED`;
- mandatory candidate OHLC text and nullable candidate volume text;
- prior OHLCV fields;
- nullable self-referencing `supersedes_event_id`;
- required `recorded_at` timestamp text.

`INSERT` requires every prior field and `supersedes_event_id` to be null. Every other action requires prior OHLC; prior volume may be null because absence of source volume is factual. Only `CORRECTED` may use `supersedes_event_id`, and it must do so.

The correction-lineage trigger requires the referenced event to:

1. already exist;
2. concern the same canonical key;
3. be a state-changing `INSERT` or `CORRECTED` event;
4. contain candidate OHLCV exactly equal to the correction's recorded prior state; and
5. have a `recorded_at` value no later than the correction.

All update and delete attempts on provenance continue to abort. Events are never replaced.

## 4. Migrating existing provenance

Migration 2 rebuilds `provenance` inside one immediate transaction. Each existing edge becomes a legacy baseline `INSERT` event:

- a random 128-bit event identifier is generated with SQLite `randomblob`;
- the canonical bar's current OHLCV supplies candidate values;
- prior values and supersession are null;
- `line:<integer>` source references recover that row number; other forms use the legacy-unknown sentinel zero;
- the old observation timestamp becomes `recorded_at`.

The old table is dropped only after the replacement table has been populated. Foreign keys and append-only triggers are recreated before commit.

This representation does not claim historical merge semantics that SPEC-001 never stored. It truthfully records the only recoverable baseline state.

## 5. Structured ingest outcome

Non-null `ingest_runs.detail` is canonical JSON with format identifier `fragarach_ii.ingest_outcome.v1`. The required object fields are:

```json
{
  "format": "fragarach_ii.ingest_outcome.v1",
  "source_rows": 0,
  "staged": 0,
  "inserted": 0,
  "corrected": 0,
  "unchanged": 0,
  "conflicts_preserved": 0,
  "rejected": 0,
  "rejections": []
}
```

Counts are non-negative integers. Each rejection contains non-negative `source_row_number`, non-empty stable `code`, and non-empty factual `message`. Original rows are not copied into JSON.

Database triggers reject invalid JSON, wrong format, missing or invalid counts, non-array rejections, and malformed rejection entries. The standard serializer sorts keys, removes insignificant whitespace, preserves Unicode, and sorts rejection records by row, code, and message, producing deterministic text for equivalent outcomes.

Existing non-null free text is preserved during migration as the message of one `LEGACY_DETAIL` rejection in a versioned outcome document. Null administrative detail remains null.

## 6. Forward migration

Migration 2 is forward-only, versioned, and checksummed independently from migration 1. The already-applied SPEC-001 migration is unchanged.

The migration:

1. begins an immediate transaction;
2. adds and backfills the evidence-run association;
3. converts legacy detail where present and installs outcome validation;
4. creates and fills the replacement provenance event table;
5. replaces the old provenance table and restores enforcement triggers;
6. records its version, name, checksum, and application time; and
7. commits.

Any exception rolls back the entire migration. Reopening recognizes matching applied checksums idempotently and refuses drift. Unsupported target versions are rejected.

## 7. Integrity and recovery

After migration, `integrity_check` must return only `ok`, `foreign_key_check` must return no rows, the application table set must remain exactly the seven foundation tables, and both stored migration records must match executable checksums.

The existing online backup, restoration verification, WAL, read-only consumer, crash rollback, and registered-writer contracts are unchanged.

## 8. Acceptance proof

Focused tests must demonstrate:

- seeded SPEC-001 rows survive forward migration;
- an injected interruption restores the complete version-1 schema and data, after which migration can succeed;
- repeated runs share one raw block and create separate events;
- rejected evidence remains linked to its run;
- outcome JSON enforcement and deterministic serialization;
- immutable provenance;
- preserved-conflict candidate and retained values;
- correction candidate/prior values and enforced supersession lineage;
- exact seven-table boundary, migration checksum, foreign keys, integrity, and backup restoration; and
- every original SPEC-001 proof remains passing, adjusted only for the authorized provenance contract.

Passing SPEC-001A proves the foundation can represent the evidence relationships required for manual ingestion. It does not prove ingestion, operational trust, or production readiness.

Fragarach II remains a candidate authority. **Operations is King.**

