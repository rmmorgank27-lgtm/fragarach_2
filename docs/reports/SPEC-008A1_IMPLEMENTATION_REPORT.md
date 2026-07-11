# SPEC-008A1 Implementation Report

**Date:** 2026-07-11
**Outcome:** PASS
**Authority:** Candidate Authority

## Implementation

Migration 6 adds exactly one application table, `authority_events`, without altering the original nine tables or migrations 1–5. The ledger contains a deterministic event ID, entity kind/ID, event kind, optional predecessor, effective segment, canonical payload, payload/event SHA-256, insertion timestamp, and actor.

Implemented enforcement includes:

- strict table constraints and a self-referential supersession FK;
- unconditional update/delete rejection;
- event-ID/checksum equality and canonical-envelope insertion checks;
- event-kind/entity-kind checks;
- non-forking supersession through one partial unique index;
- four bounded reconstruction indexes;
- registered-writer canonicalization, checksum recomputation, predecessor validation, exact replay, readback verification, bootstrap, inspection, and as-of reconstruction;
- CLI inspection, validation, append, replay, supersession, bootstrap, Stage A matrix, and provider-contract inspection surfaces with dry-run support;
- checksummed declarative D1/H1/M30/M5 provider-contract assets;
- native read-only authority-ledger models, SQLite projection, and inspection view.

## Migration and bootstrap

- Migration: `6 — SPEC-008A1 immutable authority ledger amendment`.
- Migration checksum: `a8b2645460c5f62bdf5dd9d7cc0e6ae25d477ca755fd9ffb0d1efdb238e94cf1`.
- Pre-migration backup: `data/runtime/spec008a1_pre_migration_20260711.sqlite3`.
- Backup SHA-256: `a36f1c438b228a9597a07a09cff4849dc7bfe0b7f65d8fd13a2098d81e3d78c7`.
- Backup: 9 tables, migrations 1–5, integrity `ok`, 0 FK violations, legacy digests equal to source.
- Bootstrap first pass: 3 `LEGACY_REGISTRATION_BOUND` + 3 `LEGACY_LANE_BOUND` events inserted.
- Bootstrap replay: 6 `UNCHANGED`; zero additional rows.
- Ledger canonical digest: `8f9f4b6b755e94e7c32ee87767855398c14e584254c184129729ae1d2b6d68f3`.

The standard post-implementation verifier initially could not verify the pre-migration backup because it correctly expected Migration 6. The SQLite online backup had already completed. It was independently verified read-only against the migration-5 baseline before runtime mutation; all canonical legacy digests matched exactly.

## Preservation

All pre/post legacy row counts and canonical SHA-256 digests are identical:

| Table | Rows | Canonical SHA-256 |
|---|---:|---|
| bars | 33,551 | `da9997448ad426ef696144575e276d768dc560b454160934b713d51bb268a871` |
| raw_blocks | 6 | `8d86c9d41d7aa58b5fad6da29fcc39883dbe9d5b02363257e9e1ebdfc44ea012` |
| provenance | 81,419 | `eeedfc829a12e961ca2e0310cc012facda4e94518c44c8babfb11e6c0276e308` |
| ingest_runs | 14 | `8698b0aab536ba2631f5cbc1013597accc9ff0659ab632bcfad90caf8ea15fb7` |
| lane_state | 3 | `96629a43e2c3f26fb55d6b145da1949b9a14e96c159f0572dbc5d4a8f34807f1` |
| rollup_state | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| instrument_registrations | 3 | `27c24f8cead178084eab4b3547dd00393b1f0a7e31cbfac4d3de018cf60c6d8d` |
| evidence_lanes | 3 | `91ffb5cd24aff6abb6a447130405128d7307c6293f3b35b285875a50c051f2c3` |

Migrations 1–5 retain their original checksums. Existing D1 acquisition, ingestion, validation, evidence access, and native presentation pass regression tests.

## Security and scope

No provider credential was accessed. The credential-pattern scan found only the intentional `fixture-only-secret` native test literal. No credential or runtime database is included in the checkpoint. No Stage A acquisition, intraday ingestion, backfill, constitutional change, or push occurred.

**Operations is King.**
