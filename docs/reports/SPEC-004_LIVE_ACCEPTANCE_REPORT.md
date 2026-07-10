# SPEC-004 Twelve Data — Live Acceptance Report

**Report date:** 2026-07-11

**Repository:** `/Users/raymorgan/VSC/fragarach_2`

**Authority:** `data/runtime/spec002_real_evidence_acceptance.sqlite3`

**Range:** 2026-07-01 through 2026-07-10 inclusive

## Outcome

The bounded SPEC-004 live-provider acceptance proof completed for AUDUSD, XAUUSD, and BTCUSD native D1. Each request succeeded, each eligible response was preserved byte-for-byte, all six ingest runs committed, and every command completed its direct read-only verification.

Repeating all three requests reused the same three immutable raw blocks and inserted no additional canonical bars. Integrity, foreign keys, exact table boundaries, source-file invariants, deterministic fixture replay, and credential non-disclosure checks passed.

The live responses also exposed real disagreements with existing evidence and calendar expectations. Preserve mode retained the existing canonical values for every conflict. No correction, deletion, synthesis, interpretation, or calendar adjustment occurred.

This is bounded runtime proof, not production readiness or a certification that the provider is correct. Fragarach II remains a **CANDIDATE AUTHORITY**. No consumer migration is authorized.

## Credential boundary

The operator explicitly authorized the existing non-legacy secret file at:

```text
/Users/raymorgan/VSC/Morphix_Data_Hot/runtime_state/secrets/local.env
```

The file mode was `0600`. Its established variable name was mapped in child-process memory to SPEC-004's required `TWELVE_DATA_API_KEY`. The value was never printed, passed as a command argument, copied to another file, committed, rotated, or exposed to legacy Fragarach.

Secret-byte scans found zero occurrences in:

- captured stdout and stderr;
- tracked files;
- complete Git patch history;
- reports and fixtures;
- SQLite databases, WAL/SHM files, and other runtime files under `data/`; and
- temporary SPEC-004 proof artifacts.

## Safety backup and pre-state

Before acquisition, a fresh SQLite backup was created and verified:

```text
data/runtime/spec004_live_preflight_20260711.sqlite3
```

| Fact | Value |
|---|---|
| Size | 26,583,040 bytes |
| SHA-256 | `ad570de6ea23773d86487d944006105dcde60d8e65e52903becb69af7e0725be` |
| Integrity | `ok` |
| Foreign-key violations | 0 |

Pre-proof authority counts were 33,547 bars, 3 raw blocks, 67,094 provenance events, 6 ingest runs, 3 lane rows, 0 rollup-state rows, and 3 schema migrations.

## Live response evidence

| Asset | Provider symbol | Observations | Bytes | Raw SHA-256 |
|---|---|---:|---:|---|
| AUDUSD | `AUD/USD` | 9 | 1,007 | `d171168f24e7eb94a2bec2f50d475d2c85d6af3262549e68fd8778fb4c4a515d` |
| XAUUSD | `XAU/USD` | 9 | 1,104 | `6f66b47d1f277591bf2aa1cd0c565eb85d5ed5f0bd7c7d12a13316deff11dd8a` |
| BTCUSD | `BTC/USD` | 10 | 1,230 | `68cd584bf4d797dae93352c02c4593d0a3d65198fa09289d54f5e3eb9285cfe7` |

All blocks are `application/json` and use contract `TWELVE_DATA_TIME_SERIES_D1_V1`. Request targets contained explicit symbols, UTC, ascending order, JSON format, and inclusive date bounds. They contained no credential.

## First import

| Asset | Inserted | Conflicts preserved | Corrected | Rejected |
|---|---:|---:|---:|---:|
| AUDUSD | 2 | 7 | 0 | 0 |
| XAUUSD | 2 | 7 | 0 | 0 |
| BTCUSD | 0 | 10 | 0 | 0 |

The four inserted facts were provider observations dated Saturday 2026-07-04 and Sunday 2026-07-05 for AUDUSD and XAUUSD. Volume was absent and remained null. Their insertion increased the corresponding calendar validator's outside-expected-session count by two:

| Asset | Before | After | Result checksum after proof |
|---|---:|---:|---|
| AUDUSD | 14 | 16 | `f210183431fd50ea13274ba396390b3bb37a80e3eed2917e86f2af53e256ed0c` |
| XAUUSD | 47 | 49 | `b8f4a9fd8bb05277a76f128722c91a70478b7d1b7861aa96cf078150b690528b` |
| BTCUSD | 0 | 0 | `713ebb30d3855d5ada42cb529f90e0edffdd40703a4c08decfe28ea722715e62` |

The system records these as evidence outside the versioned V1 session expectations. It does not infer whether the observations or calendars should change.

## Idempotent repeat

Every request was repeated with identical boundaries and preserve mode.

| Asset | Raw reused | Inserted | Unchanged | Conflicts preserved |
|---|---|---:|---:|---:|
| AUDUSD | yes | 0 | 2 | 7 |
| XAUUSD | yes | 0 | 2 | 7 |
| BTCUSD | yes | 0 | 0 | 10 |

The repeat created required ingest and provenance history but no raw-block or canonical-bar duplicate. Across both passes, 56 provenance events were appended: 48 `CONFLICT_PRESERVED`, 4 `INSERT`, and 4 `UNCHANGED` events.

## Post-proof authority state

| Table | Before | After | Change |
|---|---:|---:|---:|
| `bars` | 33,547 | 33,551 | +4 |
| `raw_blocks` | 3 | 6 | +3 |
| `provenance` | 67,094 | 67,150 | +56 |
| `ingest_runs` | 6 | 12 | +6 |
| `lane_state` | 3 | 3 | 0 |
| `rollup_state` | 0 | 0 | 0 |
| `schema_migrations` | 3 | 3 | 0 |

Canonical lane counts are now AUDUSD 14,262, XAUUSD 13,258, and BTCUSD 6,031. All high-water marks remain 2026-07-10 00:00:00 UTC.

The application table set remains exactly the seven foundation tables. `PRAGMA integrity_check` returned `ok`; `PRAGMA foreign_key_check` returned no rows. Migration count and checksums remained unchanged. All three operator-selected manual CSV files retained their original byte hashes, sizes, and mtimes.

## Deterministic fixture and regression proof

The 14 controlled Twelve Data tests were replayed twice in succession. Both passes returned:

```text
Ran 14 tests
OK
```

The complete suite also returned:

```text
Ran 72 tests
OK
```

This covers exact response bytes, deterministic requests and mappings, ordering, null/present volume, raw reuse, duplicates, preserve/correct behavior, malformed/error responses, bounded retries, transport protections, interruption, validation failure, credential absence, configuration checksum drift, read-only verification, integrity, and the exact table boundary, plus all earlier storage, ingestion, recovery, and calendar-validation regressions.

## Acceptance boundary

This proof establishes that, for the observed 2026-07-01 through 2026-07-10 responses, the authorized credential bridge, live HTTPS adapter, immutable evidence preservation, common staging pipeline, deterministic preserve merge, provenance, idempotent replay, calendar validation, and read-only verification operated as specified.

It does not establish provider correctness, general historical completeness, continuous availability, broader entitlement, rate-limit behavior under load, unattended operation, or production authority. No provider fallback, scheduler, service, consumer interface, automated correction, or legacy integration is authorized.

**Operations is King.**
