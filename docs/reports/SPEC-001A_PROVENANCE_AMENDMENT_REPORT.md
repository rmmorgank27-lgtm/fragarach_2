# SPEC-001A Provenance Amendment — Implementation Report

**Report date:** 2026-07-10  
**Repository:** `/Users/raymorgan/VSC/fragarach_2`  
**Classification:** Foundation amendment proof report

## Outcome

SPEC-001A is implemented and structurally proven in the local environment. The foundation still contains exactly seven application tables. Fragarach II remains a candidate authority; these results do not establish operational trust or production readiness.

## Original incompatibilities

The SPEC-002 gate found four material deficiencies:

1. provenance could not record merge action, competing candidate values, prior state, or correction lineage;
2. correcting `bars` made old value-free provenance ambiguous;
3. provenance identity prevented a repeated run from recording a separate event for identical bytes and source row; and
4. rejected raw evidence had no constrained relationship to its ingest run because it produced no bar-linked provenance.

## Schema changes

Version 2 adds nullable, restrictive `ingest_runs.raw_block_id`, backfilled when a legacy run has exactly one evidenced raw block. Application validation will require it for SPEC-002 manual runs.

`provenance` is atomically rebuilt as append-only event history keyed by `provenance_event_id`. Each event records its run, raw block, canonical key, source row, merge action, candidate OHLCV, prior OHLCV, optional superseded event, and recording time. A correction-lineage trigger requires the referenced state-changing event to match the same key and recorded prior values.

Non-null `ingest_runs.detail` is now versioned outcome JSON. Database triggers validate its minimum structure; the standard serializer provides deterministic key and rejection ordering.

No table was added. Migration 1 was not edited.

## Migration identity

```text
Version:  2
Name:     SPEC-001A provenance event and evidence-run amendment
SHA-256:  76c22b13fdd2941efbd86d75f71b42d24d34e9c2896d6308c66f70ed8bdfdb46
```

The executable checksum is persisted in `schema_migrations` and checked on every current-schema verification.

## Test command and result

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

```text
Ran 17 tests
OK
```

All 11 original foundation tests pass after changes limited to the authorized provenance contract. Six amendment tests cover migration, rollback, repeated attempts, correction/conflict history, rejected evidence, JSON enforcement, checksums, integrity, and backup.

## Migration-from-SPEC-001 proof

The compatibility fixture creates a real version-1 database using the unchanged migration 1, then seeds a raw block, committed run with legacy detail, canonical bar, and old-format provenance row. Applying migration 2 proves:

- both migration records persist;
- raw bytes and canonical bar remain identical;
- the run is linked to its single raw block;
- legacy detail remains present inside a `LEGACY_DETAIL` outcome rejection;
- old provenance becomes a baseline `INSERT` event with recovered source row and canonical candidate values; and
- the application table set remains exactly seven.

## Interrupted-migration proof

The migration runner injects an exception after statement 8 while migration 2 is inside `BEGIN IMMEDIATE`. After rollback:

- only migration version 1 is recorded;
- `ingest_runs` has its original columns;
- `provenance` has its original columns and data;
- canonical bars remain readable;
- `integrity_check` returns `ok`; and
- `foreign_key_check` returns no rows.

The same database then accepts the complete migration and passes full current integrity verification.

## Integrity and backup results

After migration, `integrity_check` returned only `ok`, `foreign_key_check` returned no rows, both migration checksums matched, and the exact table boundary passed. SQLite online backup produced a separate database that passed the same verification.

## Known limitations

- Legacy source references other than `line:<integer>` migrate with source-row sentinel zero because the original schema did not retain a structured row number.
- Legacy runs associated with zero or multiple raw blocks remain nullable; no evidence relationship is invented.
- A migrated legacy provenance edge is represented as a baseline `INSERT` because prior merge action and historical values were never stored.
- Database triggers validate outcome structure, while canonical JSON byte serialization is provided by the standard application helper and remains a writer responsibility.
- Timestamps and decimal values remain structurally stored text/integer values; ingestion-level parsing and finite-number validation belong to SPEC-002.
- The interruption test proves SQLite transaction rollback under deterministic injected failure, not power loss or media failure.

## Git identity

```text
SPEC-001 checkpoint:  b5140d745fd05f629806f31437322b8ec0ed1750
SPEC-001A implementation: ebf29bf4e53963b62bbcbe4d753a84c6a03b70cf
```

The report is committed separately so it can truthfully record the immutable implementation commit identity. Nothing was pushed.

## Acceptance statement

The seven-table foundation can now preserve evidence identity, repeated attempts, rejected evidence, merge actions, candidate and prior values, correction lineage, and append-only provenance.

This proves storage capability only. **Operations is King.**

