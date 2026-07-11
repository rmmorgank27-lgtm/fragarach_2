# SPEC-008A1 Implementation Preflight

**Date:** 2026-07-11
**Decision:** PASS — isolated implementation is constitutionally and schematically compatible; runtime migration authorised after verified backup

## Governing scope

The implementation consumes SPEC-008A1, the SPEC-008A preflight and blocker, the Constitution, all nine Base Doctrines, all 36 Timeframe Authorities, and SPEC-001 through SPEC-008A. No constitutional document is changed.

## Architecture proof

- Migration 6 adds exactly one generic table: `authority_events`.
- Existing table definitions and primary keys are not changed.
- The ledger is append-only through unconditional no-update/no-delete triggers.
- Registration, mapping, and lane multiplicity is represented by stable polymorphic entity IDs and immutable events.
- Supersession is a non-forking self-reference; rejected candidates do not supersede accepted heads.
- Canonical JSON, payload SHA-256, event SHA-256, deterministic event IDs, replay, effective dating, and affected-path stopping are implemented in the registered writer.
- An isolated migration interruption rolls back the tenth table and migration record atomically.
- Bootstrap copies only exact legacy facts and marks absent metadata `UNRESOLVED`; it changes no legacy row.

## Verification before runtime mutation

- Python: 98 tests passed.
- Swift build: passed.
- OperationsCoreChecks: 11 passed.
- Native bundle build/launch verification: passed.
- Isolated table count: exactly 10.
- Isolated bootstrap: 6 inserted, exact replay 6 unchanged.
- Provider-contract declarations: D1/H1/M30/M5 checksums valid; provider maximum 5,000 and Fragarach ceiling 4,000 remain distinct.

## Runtime baseline

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

- Application tables: 9.
- Migrations: 1–5, verified.
- Integrity: `ok`.
- Foreign-key violations: 0.
- Runtime file SHA-256: `b39e9e521ea7f55d2c47011db3744d5494d28bd73761c8e60167173a093b5221`.

## Runtime mutation plan

1. Create a fresh verified SQLite backup outside the runtime file.
2. Apply only Migration 6 through the registered writer.
3. Append exactly three legacy-registration bindings and three legacy-lane bindings.
4. Replay bootstrap and require six `UNCHANGED` outcomes.
5. Recompute every legacy digest and require exact equality.
6. Verify ten tables, migrations 1–6, integrity, foreign keys, D1 reads, native checks, and secret scan.

No push is authorised.

**Operations is King.**
