# SPEC-005 — Native macOS Operations Console Foundation

**Classification:** Foundation Specification

**Status:** Implemented; bounded runtime acceptance completed 2026-07-11

## Purpose and authority boundary

Fragarach II provides a native SwiftUI macOS operations console that answers what evidence exists, how lanes compare with their persisted validation boundary, what operations occurred, and which explicit bounded operation an operator may choose next.

The console is not an authority. It opens only an explicitly configured existing Fragarach II SQLite database with `SQLITE_OPEN_READONLY`, URI `mode=ro`, and `PRAGMA query_only=ON`. It creates no database, cache, shadow store, migration, table, market fact, or interpretation. All authority mutations remain exclusively in the registered Python CLI writer and common ingestion pipeline.

## Authorized application

The SwiftPM macOS 14 application contains Lanes, Acquire, Import, Operations, Integrity & Backup, and Settings surfaces. It uses `NavigationSplitView`, native controls, `NSOpenPanel`/`NSSavePanel`, bounded queries, in-memory view state, manual refresh, and an explicit review/confirmation step for mutations. No launch, refresh, selection, search, sort, or foreground event starts an operation.

The read layer requires exactly the seven foundation tables and three recognized migrations and rejects missing or incompatible databases. Reads retain the last successful in-memory snapshot on error. Operation history is bounded to 100 rows by default and at most 500.

## Process boundary

Swift constructs explicit arguments and invokes a configured Python executable from the configured repository. It first validates `fragarach_ii.operations_cli.v1`. Acquisition, manual import, validation, integrity verification, and backup are JSON child-process operations. Exactly one child operation may be active; cancellation terminates only that child. Swift issues no writable authority SQL and reimplements no ingestion doctrine.

Credentials are environment-only or resolved from the explicitly approved development secret file into child-process environment memory. They never enter arguments, UI, preferences, results, logs, reports, fixtures, SQLite, or Git. Missing credentials disable acquisition without disabling reads.

## Operational behavior

Lane views show canonical range/count, lane state, complete persisted validation facts, historical gaps, and outside-session observations without readiness scoring. Operation views show bounded run and provenance facts. Acquisition and import require review and explicit confirmation. Verification and backup run only on explicit request. Restore, deletion, editing, scheduling, provider fallback, background work, web technology, charts, trading, research, consumer migration, and legacy access remain excluded.

Passing tests and a local launch prove structural and bounded runtime behavior only. Fragarach II remains a **CANDIDATE AUTHORITY**. **Operations is King.**
