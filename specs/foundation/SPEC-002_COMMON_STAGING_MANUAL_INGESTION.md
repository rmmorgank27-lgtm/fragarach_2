# SPEC-002 — Common Staging and Manual File Ingestion

**Classification:** Foundation Specification  
**Dependency:** SPEC-001 and SPEC-001A  
**Status:** Implemented candidate  
**Scope:** Manual UTF-8 CSV ingestion of native D1 evidence

## 1. Objective and exclusions

SPEC-002 implements the first evidence path:

```text
selected file → immutable raw bytes → common staging → structural validation
→ deterministic canonical merge → append-only provenance → factual lane state → commit
```

It introduces no automated provider, calendar, expected-session analysis, gap doctrine, rollup, scheduler, service, interface, consumer integration, signal, readiness decision, or migration from the failed Fragarach project.

Passing this specification proves only that manual evidence can enter the candidate Truth Store safely and deterministically.

## 2. Scope

The proof symbols are AUDUSD, XAUUSD, and BTCUSD. The pipeline has no symbol-specific branch and does not invent aliases. Native D1 is the only accepted timeframe in this work cycle. The staging contract can represent other timeframes when later authorized.

One ingestion run processes one selected file, one immutable raw block, and one symbol/timeframe lane. Files resolving to multiple lanes are rejected rather than split into another ingestion path.

## 3. CSV boundary

The adapter accepts UTF-8, optionally with a UTF-8 BOM, and requires a header row. Logical headers are trimmed and case-normalized independently of column order. Required fields are `timestamp`, `open`, `high`, `low`, and `close`; `volume`, `symbol`, and `timeframe` are optional. The physical header `time` is explicitly mapped to the logical `timestamp` field; providing both is a duplicate logical header and is rejected. Duplicate, missing, empty, extra, and unsupported logical columns are factual errors.

Symbol and timeframe may be supplied by the command, the row, or both. Values are trimmed and uppercased without alias translation. When command and row both supply a value, disagreement rejects that row. Missing identity rejects it. Filenames never supply identity.

The boundary adapter creates staged values only. It does not access SQLite or choose merge winners.

## 4. Common staging contract

`StagedBar` is immutable and contains symbol, timeframe, canonical UTC epoch timestamp, normalized OHLCV decimal text, source, provider, raw-block ID, physical source row number, exact source timestamp text, and receipt time. Manual rows use source `MANUAL_FILE`; provider defaults to `MANUAL` and is operator-declared.

Missing volume remains null. The immutable raw block, not staged or outcome data, retains original row bytes and numeric spelling.

## 5. Timestamp and decimal rules

Accepted timestamps are:

- strict ISO calendar dates (`YYYY-MM-DD`) for D1, normalized to 00:00:00 UTC; and
- ISO 8601 timestamps that explicitly declare a zero UTC offset or `Z`.

Naive timestamps, non-zero offsets, slash-style locale dates, malformed values, and date-only input for non-D1 are rejected. This is structural normalization only and makes no market-session claim.

OHLCV uses arbitrary-precision `Decimal`. Empty, malformed, NaN, and infinite values are rejected. Equivalent numeric spellings normalize deterministically to plain decimal text with insignificant trailing fractional zeroes removed; negative zero becomes zero. Original precision remains in raw evidence.

Structural relationships require `high >= low`, `high >= open`, `high >= close`, `low <= open`, and `low <= close`. Volume is null or non-negative.

## 6. Batch validation and duplicates

Rows retain exact physical row numbers and factual rejection codes. Any structural rejection rejects the complete attempt: raw evidence and a failed run are committed, while canonical bars, provenance, and lane state remain unchanged.

Rows are ordered by `(symbol, timeframe, timestamp, source_row_number)`. Exact numeric duplicates for one canonical key collapse to the first source row and increment `duplicate_identical`. Differing values for one key produce `CONFLICTING_DUPLICATE`, increment `duplicate_conflicting`, and reject the attempt. No last-row-wins rule exists.

## 7. Raw evidence and runs

The selected file is read as bytes before parsing. SHA-256, filename, absolute diagnostic path, length, media type, receipt time, and exact payload are stored in immutable `raw_blocks`. The raw-block identity is `raw-<sha256>`.

An existing checksum reuses the same immutable raw block. Every attempt creates a new random ingest-run identity linked through `ingest_runs.raw_block_id`, including repeats, different filenames with identical bytes, validation rejection, and recovered unexpected failure.

Outcome JSON records counts, row rejections, checksum, selected filename, provider, merge mode, raw-block reuse, accepted rows, and duplicate counts. It contains no session, freshness, readiness, fitness, or trading interpretation.

## 8. Transaction model

Successful and structurally rejected attempts use one registered-writer immediate transaction. A successful transaction ensures the raw block, creates an active run, merges bars, appends provenance, refreshes factual lane state after canonical mutation, marks the run committed, and commits.

A rejected transaction ensures the raw block, creates an active run, records structured rejection outcome, marks it failed, and commits without canonical mutation.

An unexpected exception rolls the entire working transaction back. A new recovery transaction then preserves or reuses the raw block and records the same run identity as failed with `UNEXPECTED_FAILURE`. The exception is surfaced; automatic retry does not occur.

## 9. Canonical merge

Canonical identity is `(symbol, timeframe, timestamp)`. Default merge mode is `preserve`; `correct` requires explicit selection.

- A new key inserts one bar and one `INSERT` event.
- Identical existing OHLCV leaves the bar untouched and appends `UNCHANGED` with equal candidate and prior values.
- Differing OHLCV in preserve mode leaves the bar untouched and appends `CONFLICT_PRESERVED` with candidate and retained prior values.
- Differing OHLCV in correct mode updates only that key and appends `CORRECTED`, recording candidate and prior values and superseding the state-changing provenance event named by `bars.updated_by_ingest_run_id`.

Bars absent from the file are never removed. No lane is deleted or replaced. `INSERT OR REPLACE`, snapshot interpretation, filename precedence, complete-history replacement, and silent last-write-wins are prohibited.

## 10. Lane state

After at least one inserted or corrected bar, only the affected lane is updated using `INSERT ... ON CONFLICT DO UPDATE`. `high_watermark_open_time_utc` is the factual maximum stored key, `state_version` increments once per mutating run, `last_ingest_run_id` identifies that run, and `updated_at_utc` records observation time.

Earliest key, latest key, and canonical count are calculated directly from `bars` for command output. No readiness, tradability, expected-session coverage, gap status, or calendar-aware freshness is stored.

## 11. Command contract

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.ingest_file \
  --database /path/to/authority.sqlite3 \
  --file /path/to/AUDUSD_D1.csv \
  --symbol AUDUSD \
  --timeframe D1 \
  --provider MANUAL \
  --merge-mode preserve \
  --json
```

The command reports run ID, raw-block ID, checksum, source/staged/accepted rows, merge counts, rejection and duplicate counts, earliest/latest keys, canonical count, raw-block reuse, transaction state, and row-specific factual rejections. It returns zero for committed ingestion, two for structural rejection, and one for unexpected failure.

## 12. Acceptance proof

Tests and synthetic runtime commands must prove clean ingestion, checksum idempotence, differently named duplicates, overlapping and shallow tails, identical overlap, preserve/correct conflict behavior and lineage, duplicate handling, invalid OHLCV, ambiguous timestamps, rollback, concurrent snapshot readers, read-only enforcement, restart persistence, all three proof symbols, and continued SPEC-001/001A integrity.

Synthetic evidence proves mechanics only. Operator-selected real evidence is required later for real-world operational trust.

Fragarach II remains a candidate authority. **Operations is King.**
