# SPEC-003A Lane Validation Summary — Implementation Report

**Report date:** 2026-07-11

**Repository:** `/Users/raymorgan/VSC/fragarach_2`

**Classification:** Foundation amendment proof report

## Outcome

SPEC-003A is implemented, proven, and applied to the local SPEC-002 real-evidence acceptance authority. The amendment adds one nullable structured field to `lane_state`, retains exactly seven application tables, and does not change canonical bars or evidence history.

SPEC-003 remains paused until its compatibility gate is rerun. Fragarach II remains a candidate authority. No consumer migration is authorized.

## Original incompatibility

Before this amendment, `lane_state` contained only lane identity, canonical high watermark, state version, last mutating ingest-run identity, and update timestamp. It had no safe location for calendar identity, gap-doctrine identity, declared boundary, factual counts, deterministic result checksum, or validation observation metadata.

Repurposing any existing field would have destroyed or confused established canonical and ingestion facts. Using ingest history, rollup state, or a sidecar would have created a competing or semantically false authority.

## Exact schema change

Migration 3 adds:

```text
lane_state.validation_summary TEXT NULL
```

No table was added. Existing rows receive null. Existing `high_watermark_open_time_utc`, `state_version`, `last_ingest_run_id`, and `updated_at_utc` values are not changed.

Non-null summaries must use exact format `fragarach_ii.lane_validation_summary.v1` and the exact published key set. Database triggers enforce JSON validity, format and key version, lane identity, positive definition versions, lowercase SHA-256 checksums, date/observation shape, non-negative integer counts, count reconciliation, and boolean edge presence.

The immutable Python value object enforces canonical ISO dates, offset-bearing observation time, normalized lane identity, typed counts and booleans, checksum shape, and deterministic JSON serialization.

## Migration identity

```text
Version:  3
Name:     SPEC-003A lane validation summary foundation amendment
SHA-256:  13b64f4e72b8c9897d616936cdb5cd526e9cbfbbbaf59cc01752973834594b39
```

Migrations 1 and 2 were not edited. Current verification requires all three stored identities and executable checksums.

## Automated proof

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result:

```text
Ran 39 tests
OK
```

The five new focused tests prove version-2 preservation, null behavior for existing rows, deterministic serialization, database validation boundaries, read-only enforcement, injected migration rollback, backup/restoration, exact seven-table membership, and integrity. All 34 prior tests continue to pass.

## Migration-from-version-2 proof

A seeded version-2 database containing a raw block, bar, provenance event, ingest run, and lane row was migrated. Before/after row comparisons were exact for all evidence tables. The six original lane columns were exact and the appended summary was null.

The stored migration-3 checksum matched the executable checksum, `integrity_check` returned only `ok`, and `foreign_key_check` returned no rows.

## Interrupted-migration proof

An exception was injected after the first migration-3 statement, while the migration was inside `BEGIN IMMEDIATE`. Rollback proved:

- `validation_summary` was absent;
- migration history remained exactly versions 1 and 2;
- the existing lane row and state version remained readable and unchanged;
- integrity and foreign keys passed; and
- the same database could then apply migration 3 successfully.

## Read/write boundary proof

A valid canonical summary crossed the registered-writer boundary and was returned byte-identically through `mode=ro`/`query_only` SQLite. The write changed only `validation_summary`; watermark, lane version, last ingest identity, and update timestamp remained exact.

The database rejected malformed JSON, wrong format version, lane-identity mismatch, missing keys, negative counts, and other structurally invalid documents. The Python serializer rejected invalid definition versions, inconsistent totals, non-ISO dates, uppercase checksums, non-boolean presence, and observation timestamps without offsets.

A read-only attempt to clear the field failed with SQLite's read-only enforcement.

## Acceptance-authority migration

Before migrating:

- a SQLite online backup was created at `data/runtime/spec002_before_spec003a.sqlite3`;
- the backup retained migration versions 1 and 2;
- backup integrity and foreign keys passed; and
- deterministic evidence and lane-fact hashes matched the source authority.

Migration 3 was then applied through the registered writer to:

```text
data/runtime/spec002_real_evidence_acceptance.sqlite3
```

All three existing lane rows received null validation summaries. A current-schema online backup was created and fully verified at:

```text
data/runtime/spec003a_acceptance_backup.sqlite3
```

## Before-and-after invariants

| Authority content | Count | Before SHA-256 | After SHA-256 |
|---|---:|---|---|
| Canonical bars | 33,547 | `0d5071b2df747bcc14b06f71b8e50ab178fa78a33ab7902620756840ebdb8c81` | identical |
| Raw blocks | 3 | `3c47f31744539392dba745b3e66d207de07f44fdb0306909445718a6e3705ccf` | identical |
| Provenance events | 67,094 | `9968c3de348858ca0d3cd242ab5edccdf22fae25fd1d32be90243697127414c2` | identical |
| Ingest runs | 6 | `481cd4efca5f9b267cc64a42ff81b3a6ad1c090b27ce34aa48c511484cc0d1c5` | identical |
| Existing lane facts | 3 | `8555877970df7169f69096d71935bb02ab561dcea31a2f2c3216e6cb073eef34` | identical |

The hashes serialize rows in explicit canonical order and replace BLOB content with its byte length and SHA-256 before hashing. They are comparison evidence, not new stored authority.

After migration:

```text
application tables:         7
lane rows:                  3
null validation summaries: 3
integrity_check:            ok
foreign-key violations:     0
post-migration backup:      verified
```

## Files added and changed

- Added `SPEC-003A_LANE_VALIDATION_SUMMARY_AMENDMENT.md`.
- Added `storage/validation_summary.py`.
- Added migration 3 and its schema-boundary triggers.
- Extended migration execution and verification through version 3.
- Exported the immutable summary value object through the storage package.
- Added focused SPEC-003A tests.
- Updated the parent storage specification with the amendment reference.
- Updated one SPEC-001A migration expectation to include the newly authorized current version.

No calendar, validator, gap doctrine, validation command, provider, rollup, scheduler, service, consumer, or legacy integration was added.

## Known limitations and deferred work

- The summary field is replaceable current factual state. Historical full-result retention is not authorized by this amendment.
- Database triggers enforce shape and version; the later validator remains responsible for calculating truthful calendar facts and the full deterministic result checksum.
- `validation_observed_at` is persisted metadata. SPEC-003 must exclude it from the full factual-result checksum.
- Null means no persisted summary, not a validation conclusion.
- Only SPEC-003 will define calendars, gap classifications, full results, and persistence workflow.
- No consumer is authorized to interpret or depend on the field yet.

## Git identity

```text
SPEC-003A implementation: c54f611264374d045cab587f7ee21601ec3a5e76
```

The report is committed separately so it can record the implementation identity. Nothing was pushed.

## Acceptance statement

The seven-table foundation can now persist one versioned, canonical, structurally enforced factual validation summary on each lane without repurposing or modifying existing authority facts.

This is storage capability only. SPEC-003 must restart at its compatibility gate.

**Operations is King.**
