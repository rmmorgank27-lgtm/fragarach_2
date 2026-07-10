# SPEC-002 Manual Ingestion — Implementation Report

**Report date:** 2026-07-10

**Repository:** `/Users/raymorgan/VSC/fragarach_2`

**Classification:** Factual candidate-authority proof report

## Outcome

SPEC-002 is implemented through one manual UTF-8 CSV ingestion path. Synthetic runtime evidence demonstrates immutable byte preservation, common staging, structural rejection, deterministic preserve/correct merging, append-only event provenance, factual lane state, rollback, read-only concurrency, and restart persistence.

This proves local mechanics only. It does not establish source correctness, calendar correctness, operational trust, consumer readiness, or production readiness.

## Schema compatibility finding

The original SPEC-001 schema failed the mandatory gate. The separately authorized and checkpointed SPEC-001A migration resolved evidence-run association and event-history requirements while retaining exactly seven tables. SPEC-002 itself required no schema migration and added no table.

## Files added and changed

- Added `SPEC-002_COMMON_STAGING_MANUAL_INGESTION.md`.
- Added immutable staging contract and CSV boundary adapter under `src/fragarach_ii/staging/`.
- Added structural validation, deterministic merge, and manual orchestration under `src/fragarach_ii/ingestion/`.
- Added the narrow `fragarach_ii.commands.ingest_file` CLI.
- Extended canonical outcome serialization with deterministic factual scalar context.
- Added focused ingestion, recovery, command, and staging tests.
- Added three small synthetic D1 CSV fixtures.
- Updated the README with current boundary and command usage.

No provider, calendar, gap analysis, rollup, scheduler, service, dashboard, native application, consumer cache, readiness decision, or legacy Fragarach path was added.

## Automated proof

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result:

```text
Ran 33 tests
OK
```

The 33 tests comprise the 17 SPEC-001/001A foundation proofs and 16 staging, ingestion, recovery, concurrency, restart, and command proofs.

## Synthetic runtime proof commands

The following command form was executed once for each proof symbol against one newly created temporary authority:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python3 -m fragarach_ii.commands.ingest_file \
  --database "$database" \
  --file "tests/fixtures/manual/${symbol}_D1.csv" \
  --symbol "$symbol" \
  --timeframe D1 \
  --provider MANUAL \
  --merge-mode preserve \
  --json
```

### AUDUSD D1

```text
checksum:       59055fc0c78689e06f5d578983cf5e21d94a7223311f9c21ef984fa404069d87
raw_block_id:   raw-59055fc0c78689e06f5d578983cf5e21d94a7223311f9c21ef984fa404069d87
ingest_run_id:  8f5c94d0d5664447b4ea7ea2a759acca
source/staged/accepted: 2/2/2
inserted/corrected/unchanged/preserved/rejected: 2/0/0/0/0
earliest/latest: 2026-07-07T00:00:00+00:00 / 2026-07-08T00:00:00+00:00
canonical_count: 2
transaction_state: committed
```

### XAUUSD D1

```text
checksum:       ba34db6a0b400fcd76817c774951b744647c79e30ec8ea5bba9ba2802df36eea
raw_block_id:   raw-ba34db6a0b400fcd76817c774951b744647c79e30ec8ea5bba9ba2802df36eea
ingest_run_id:  4647711af8aa4b61bb7c5917258d073b
source/staged/accepted: 2/2/2
inserted/corrected/unchanged/preserved/rejected: 2/0/0/0/0
earliest/latest: 2026-07-07T00:00:00+00:00 / 2026-07-08T00:00:00+00:00
canonical_count: 2
transaction_state: committed
```

### BTCUSD D1

```text
checksum:       14425e4943b4b42fc8968832d8f17ffd47f3c10acb12acc69fdfe1df84c44b66
raw_block_id:   raw-14425e4943b4b42fc8968832d8f17ffd47f3c10acb12acc69fdfe1df84c44b66
ingest_run_id:  7d2f0cc4d87346dfb8d19b5d52370f4a
source/staged/accepted: 2/2/2
inserted/corrected/unchanged/preserved/rejected: 2/0/0/0/0
earliest/latest: 2026-07-07T00:00:00+00:00 / 2026-07-08T00:00:00+00:00
canonical_count: 2
transaction_state: committed
```

Combined database facts were six bars, six provenance events, three raw blocks, three committed runs, and three lanes. Full integrity verification returned true.

## Lane state before and after runtime proof

Before the first command, the authority did not exist and contained no lane state. After all three commands:

| Lane | High watermark epoch | Version | Last ingest run |
|---|---:|---:|---|
| AUDUSD D1 | 1783468800 | 1 | `8f5c94d0d5664447b4ea7ea2a759acca` |
| XAUUSD D1 | 1783468800 | 1 | `4647711af8aa4b61bb7c5917258d073b` |
| BTCUSD D1 | 1783468800 | 1 | `7d2f0cc4d87346dfb8d19b5d52370f4a` |

The watermark is the factual maximum stored UTC key. It is not a freshness, expected-session, or readiness statement.

## Deterministic merge and audit proof

- Identical bytes under the same or different filename reuse one checksum-identified raw block, create a new run, append `UNCHANGED`, and do not duplicate bars.
- Overlapping tails insert only new keys; shallow files do not remove earlier history.
- Exact duplicate rows collapse after numeric normalization; conflicting duplicate keys reject the complete attempt.
- Preserve mode retains the canonical bar and records both candidate and retained values.
- Correct mode updates only the conflicting key and records candidate, prior, and the superseded state-changing event.
- Raw blocks, provenance events, ingest history, and migrations remain protected by database triggers and foreign keys.

## Failure and rollback proof

The recovery test begins with a committed bar and lane state, stages two new keys, then injects `RuntimeError("forced before commit")` after bar/provenance/lane mutation but before run finalization.

The working transaction rolls back completely: bar count, provenance count, and lane version remain identical to their pre-attempt values. A separate recovery transaction preserves the new raw bytes and records the same attempt identity as failed with `UNEXPECTED_FAILURE`. No automatic retry occurs.

Six read-only consumers also held pre-import snapshots while a separate registered writer completed an import. They remained readable, observed their consistent old snapshot, then observed the committed two-bar state after ending that snapshot.

## Known limitations and deferred work

- Only native D1 is accepted. H1 remains deferred.
- Only UTF-8 CSV with the documented logical columns is supported.
- One file resolves to one symbol/timeframe lane.
- Structural validation does not establish market-session validity, expected coverage, material gaps, freshness, tradability, or source correctness.
- Equivalent decimal spellings normalize to one numeric text representation; exact original spelling remains only in immutable raw bytes.
- Synthetic fixtures prove mechanics. Operator-selected evidence is still required for real-world trust work.
- The unexpected-failure recovery path cannot guarantee a durable failure record if the database or storage device itself is no longer writable.
- Provider automation, calendars, gap doctrine, H1 proof, rollups, scheduling, services, Morphix, and consumers remain deferred.

## Git identity

```text
SPEC-001A report checkpoint: 7eec7f4
SPEC-002 implementation:     1c54b04b7c67b7861eed2f9a82ce9b94736d3ede
```

The report is committed separately so it can record the exact implementation identity. Nothing was pushed.

## Acceptance statement

Manual synthetic evidence can enter the candidate Truth Store through one deterministic path without silent overwrite or history truncation. Rejected evidence and interrupted attempts remain factual and auditable.

Fragarach II remains a candidate authority. **Operations is King.**
