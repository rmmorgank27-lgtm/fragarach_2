# SPEC-005 Native macOS Operations Console — Implementation Report

**Report date:** 2026-07-11

**Implementation checkpoint:** `32ef3ec679687b0f0c85d003ab09941cd24ed85f`

## Outcome

SPEC-005 implements a native macOS 14 SwiftUI operations console as a SwiftPM application. It builds into `dist/Fragarach II.app`, launches without a browser or server, reads the existing authority through system SQLite read-only semantics, and invokes only the configured existing Python CLI for mutations.

The application contains Lanes, Acquire, Import, Operations, Integrity & Backup, and Settings surfaces. It displays Candidate Authority explicitly and contains no charting, forecasting, trading, readiness, promotion, consumer, or migration feature.

## Compatibility gate

The mandatory pre-edit gate passed at commit `c77aec4c625d4c6a946100ddf946610fab418ed5`:

- 72 Python tests passed;
- tracked Git state was clean except intentional operator `data/`;
- the authority contained 33,551 bars, 6 raw blocks, 67,150 provenance events, 12 ingest runs, and 3 lane rows;
- integrity, foreign keys, all three migration checksums, WAL, and exactly seven tables passed;
- a compiled Swift/system-SQLite probe opened the real database with URI `mode=ro`, `SQLITE_OPEN_READONLY`, and `sqlite3_db_readonly == 1`; and
- acquisition, manual import, and validation already exposed stable JSON CLI results.

The gate identified missing JSON commands for CLI identity, integrity, and backup. A narrow Python-only amendment added `fragarach_ii.operations_cli.v1` with `identity`, `verify`, and `backup` operations. It uses existing `verify_integrity` and `backup_database` functions and adds no schema, table, writer, or ingestion path.

## Architecture

`SQLiteReadService` links system SQLite through the local `CSQLite` module. Every load:

- requires an existing explicit path;
- opens `READONLY | URI | NOMUTEX` with `mode=ro`;
- verifies SQLite reports the handle read-only;
- enables `query_only`;
- rejects any table set other than the exact seven foundation tables;
- requires three recognized migration rows; and
- executes only fixed, bounded `SELECT` statements.

The default operation query is limited to 100 records and capped at 500. The app preserves the last successful in-memory snapshot after a later read error and has no persistent authority cache.

`ProcessBridge` validates the configured Python executable and repository using the versioned CLI identity before running a child. Arguments always include an explicit database and operation bounds. A lock permits one active child. Cancellation terminates only that child; Python retains transaction, rollback, writer-lock, raw-evidence, merge, provenance, lane, validation, integrity, and backup authority.

Credential resolution checks the inherited SPEC-004 environment first, then the explicitly authorized non-legacy development secret file. Only the existing alias value enters child-process environment memory. It never enters arguments or preferences, and output is filtered before publication.

AppKit is limited to native file/folder panels and application quit coordination. The first runtime backup attempt revealed that `NSSavePanel` pre-created an empty file, which the Foundation overwrite guard correctly rejected. The boundary was corrected to an `NSOpenPanel` folder choice plus a new timestamped filename. The zero-byte failed artifact was removed, and the rerun produced a verified backup.

## Interaction guarantees

- Default launch opens Lanes.
- Search, timeframe filtering, sorting, selection, refresh, and launch perform no mutation.
- Acquisition and import require review and separate confirmation.
- Verification and backup are explicit.
- Credential absence disables acquisition but not reads.
- The selected import file is hashed before review and never modified.
- Active-operation UI remains visible while read surfaces remain available.
- Quit during a child operation presents Keep App Open or Request Cancellation; it never force-quits or silently orphans the child.
- Preferences persist only explicit paths and ordinary UI choices.

## Build and automated proof

```sh
swift build
swift run OperationsCoreChecks
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests
```

Results:

```text
OperationsCoreChecks: 10 checks passed
Ran 75 Python tests
OK
```

The Swift checks cover real-schema read-only opening, missing/incompatible rejection, byte preservation, exact lane decoding, nullable summaries, weekend/outside-session facts, bounded operations, deterministic search/filter/sort, explicit secret-free arguments for all five command families, review confirmation, credential alias resolution, secret filtering, CLI identity, single-operation exclusion, cancellation, non-zero status, and malformed output.

The Python suite includes the 72 prior regressions plus identity, structured verification, verified backup, and factual failure behavior.

## Build and launch tooling

`script/build_and_run.sh` is the single build/bundle/launch entry point and supports run, debug, logs, telemetry, and process verification modes. `.codex/environments/environment.toml` exposes the same script as the Codex Run action. Build artifacts are ignored by Git.

The SwiftUI and AppKit skill guidance materially shaped the source split, `NavigationSplitView`, native sidebar density, independently scrolling content, minimal panel bridge, SwiftPM `.app` staging, and foreground activation behavior.

Fragarach II remains a **CANDIDATE AUTHORITY**. No consumer migration is authorized.
