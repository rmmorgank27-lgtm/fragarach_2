# SPEC-001 Storage Foundation — Implementation Report

**Report date:** 2026-07-10  
**Repository:** `/Users/raymorgan/VSC/fragarach_2`  
**Classification:** Factual structural implementation report

## Outcome

SPEC-001 is implemented within its storage-only boundary. The repository was initialized empty; no existing Fragarach code or runtime was copied, read, modified, migrated, or recovered.

Fragarach II remains a candidate authority. The results below prove defined storage structure and behaviours in one local test environment only. They do not demonstrate operational trust, production load, sustained runtime, host-loss recovery, or production readiness.

## Implemented artifacts

- Permanent Truth Store Doctrine and Deployment Plan under `docs/foundation/`.
- Foundation specification `SPEC-001_STORAGE_FOUNDATION.md`.
- Python package `src/fragarach_ii/`, avoiding the prior project's import namespace.
- One versioned SQLite migration containing exactly seven application tables: `raw_blocks`, `bars`, `provenance`, `ingest_runs`, `lane_state`, `rollup_state`, and `schema_migrations`.
- Database-enforced immutability for raw blocks and append-only provenance, ingest-run history, and migration history.
- Process-held non-blocking exclusive macOS `fcntl.flock`, independent of API access restrictions, with diagnostic ownership metadata.
- WAL writer and direct `mode=ro`/`query_only` consumer connections.
- Explicit immediate transactions with rollback on exceptions.
- Structural integrity, online backup, and backup verification primitives.

No provider acquisition, CSV ingestion, calendar logic, rollup computation, service, scheduler, dashboard, native application, chart, Morphix integration, or Fragarach migration was implemented.

## Proof environment

```text
Platform: macOS-26.5.2-arm64-arm-64bit-Mach-O
Python:   3.13.0
SQLite:   3.45.3
```

The project requires Python 3.12 or later and uses the standard-library `sqlite3` module.

## Proof command

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Final result on 2026-07-10 (elapsed time varies by run):

```text
Ran 11 tests
OK
```

## Proven behaviours

| Required property | Runtime evidence |
|---|---|
| WAL mode | A reopened read-only connection reported `journal_mode=wal`. |
| Foreign keys | Writer and consumer connections reported enforcement enabled; an unrelated provenance insert failed. |
| One writer | A spawned second process was denied the `flock` while the owner metadata identified the holding process; acquisition succeeded after release. |
| Concurrent readers | Eight read-only connections read the committed snapshot while the writer held an uncommitted immediate transaction. |
| Transaction rollback | An exception removed every change from its explicit transaction. |
| Crash rollback | A child process exited through `os._exit(91)` with a transaction open; the row was absent after restart, the writer lock was reacquired, and integrity passed. |
| Restart persistence | A committed raw block retained identical digest and bytes after writer close and read-only reopen. |
| Database integrity | `integrity_check` returned only `ok`, `foreign_key_check` returned no rows, the application table set was exact, and migration history matched its implementation checksum. |
| Read-only enforcement | An insert through a `mode=ro` and `query_only` consumer raised a read-only database error. |
| Evidence immutability | Database triggers rejected raw-block update/delete and migration-history deletion. |
| Backup/restoration primitive | SQLite online backup produced a separate database that passed full structural verification. |

## Limits of the evidence

- Concurrency was exercised locally with eight consumers, not to an operating-system limit.
- Writer exclusion is cooperative at the process boundary: every conforming writer in any language must acquire the documented sibling lock. The Python API cannot prevent a deliberately non-conforming process from bypassing that protocol.
- `flock` behaviour is proven on the reported local macOS filesystem only. Network or other filesystems require separate qualification.
- The crash proof covers process termination during an uncommitted SQLite transaction. It does not model power loss, media corruption, full disk, host loss, or kernel failure.
- Backup creation and verification are implemented. Operator-controlled atomic replacement of an authority database is intentionally not automated.
- Price validation, merge doctrine, manual ingestion, provenance population through a pipeline, and operational recovery exercises belong to later authorised specifications.

## Authority statement

Passing these tests establishes structural evidence only. Fragarach II remains a candidate authority until runtime operation proves otherwise.

**Operations is King.**
