# Developer Guide

## Local requirements

- macOS 14 or later for the native console
- Python 3.12 or later (the development service currently uses Python 3.13)
- Swift 6 toolchain
- No third-party Python runtime dependencies

The project is a Swift Package plus Python authority service:

```text
Sources/                 Native macOS app and read-only OperationsCore
src/fragarach_ii/        Authority, ingestion, scheduler, and CLI modules
tests/                   Python contract and regression tests
script/                  Build and development helpers
docs/                    Handbook, doctrine, operations notes, and reports
```

## Build and test

```sh
swift build -c release --product FragarachII
PYTHONPATH=src python3 -m pytest -q
./script/build_and_run.sh --verify
```

`swift test` currently builds the package but reports that no Swift test target
is configured. That is a repository condition, not a passing native test
suite. Run `OperationsCoreChecks` and the focused Python tests appropriate to
the changed contract.

## Ownership boundaries

| Area | Owns | Must not do |
| --- | --- | --- |
| Swift native console | Presentation, read-only SQLite queries, command invocation | Mutate SQLite or implement ingestion |
| Python ingestion | Raw evidence, staging, canonical merge, provenance, transactions | Render UI state |
| Scheduler service | Lane claim, provider dispatch, retry/backoff, publication | Become a second authority store |
| Authority database | Canonical evidence and durable receipts | Store transient UI cache state |
| Integration consumer | Read fixed contracts and submit commands | Directly write authority or scheduler files |

## Ingestion invariants

1. Raw responses are content-addressed by SHA-256.
2. One writer owns authority mutation at a time.
3. A canonical bar is identified by `(asset, timeframe, open_time_utc)`.
4. A conflict is preserved unless a reviewed `correct` merge is requested.
5. Corrections retain lineage to their supporting prior event.
6. Equal bars never append per-bar provenance. The raw block and ingest run are
   the receipt of that observation.
7. Database growth must be bounded by unique evidence, not scheduler polling.

## Adding or changing a provider

1. Add a provider adapter that produces `RawEvidence` and staged bars.
2. Validate source identity, requested bounds, timestamps, and OHLCV values
   before admission.
3. Add provider facts, credential classification, and mapping logic.
4. Register an approved route and evidence lane; do not infer an alias.
5. Add tests for success, invalid response, conflict, correction, and retry.
6. Update the integration and operations documentation if the operator-visible
   contract changes.

## Schema and migration discipline

Schema changes live in `storage/schema.py`; registration and verification live
in `storage/migrations.py`. Migrations are append-only and checksum-verified.
Do not alter an existing migration after it has been applied to an authority.

Large evidence transformations are not in-place deletes. Create a new database,
copy and verify canonical authority, then make an atomic path swap while the
scheduler is stopped. `authority_rebuild.py` is the current governed example.

## Pull-request checklist

- Is the mutation in Python rather than Swift?
- Does every blocked path expose a reason and repair action?
- Does a repeated provider response remain bounded in storage?
- Are raw evidence, ingest outcomes, and canonical state consistent?
- Are success, rejection, conflict, correction, and retry tests updated?
- Is the handbook updated for a changed operator or integration contract?
