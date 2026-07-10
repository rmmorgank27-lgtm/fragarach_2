# SPEC-001 — Storage Foundation

**Classification:** Foundation Specification  
**Status:** Implemented candidate  
**Scope:** SQLite storage only

## 1. Purpose and boundary

This specification defines the first Fragarach II truth-store structure and its local runtime proof. It implements storage mechanics only. It does not implement acquisition, CSV ingestion, calendars, rollup computation, scheduling, services, interfaces, migration, or recovery of the prior Fragarach project.

The application database contains exactly seven application tables. SQLite internal objects and integrity triggers are not additional authorities.

## 2. Canonical identities

- A raw block is identified by application-assigned text `raw_block_id`. Its SHA-256 digest is independently unique.
- A canonical bar is identified by `(asset, timeframe, open_time_utc)`. `asset` and `timeframe` are non-empty canonical codes. `open_time_utc` is an integer Unix epoch in seconds.
- A provenance edge is identified by `(asset, timeframe, open_time_utc, raw_block_id, source_record_ref)`. It joins one canonical bar to one immutable raw block and source record location.
- An ingest run is identified by application-assigned text `ingest_run_id`.
- Lane state is identified by `(asset, timeframe)`.
- Rollup state is identified by `(asset, source_timeframe, target_timeframe)`. Its presence does not implement rollups.
- A migration is identified by monotonically increasing integer `version`.

Identifiers are never inferred from SQLite rowids.

## 3. Schema

### `schema_migrations`

`version INTEGER PRIMARY KEY`, `name TEXT NOT NULL UNIQUE`, `checksum_sha256 TEXT NOT NULL`, and `applied_at_utc TEXT NOT NULL`. Applied migrations are append-only.

### `raw_blocks`

`raw_block_id TEXT PRIMARY KEY`, `sha256 TEXT NOT NULL UNIQUE`, `source_name TEXT NOT NULL`, `source_locator TEXT NOT NULL`, `media_type TEXT NOT NULL`, `received_at_utc TEXT NOT NULL`, `byte_length INTEGER NOT NULL`, and `payload BLOB NOT NULL`. Constraints require non-empty identity/source fields, a 64-character lowercase hexadecimal digest, non-negative byte length, and exact agreement between `byte_length` and the payload length.

Database triggers reject every update and delete. Retention is permanent within the truth store. Duplicate bytes may be detected by the unique digest; callers must not replace an existing row.

### `bars`

Composite primary key `(asset, timeframe, open_time_utc)`. Required OHLC values are stored as decimal text to prevent SQLite numeric-affinity conversion from silently changing source precision. `volume` is nullable decimal text. `close_time_utc` is nullable integer epoch seconds. `created_by_ingest_run_id` and `updated_by_ingest_run_id` reference `ingest_runs` using restrictive foreign keys. Constraints require non-empty identity/value text and, when present, `close_time_utc > open_time_utc`.

This foundation specifies identity and storage only; it does not define merge doctrine or validation semantics for prices.

### `provenance`

Contains the canonical bar identity, `raw_block_id`, `source_record_ref`, `observed_at_utc`, and `ingest_run_id`. Composite foreign key `(asset, timeframe, open_time_utc)` references `bars`; other foreign keys reference `raw_blocks` and `ingest_runs`. All use `ON UPDATE RESTRICT ON DELETE RESTRICT`. Provenance rows are append-only; update and delete triggers reject mutation.

### `ingest_runs`

Contains identity, `kind`, `status`, `started_at_utc`, nullable `finished_at_utc`, and nullable `detail`. Although full ingestion is outside scope, transaction ownership must be recorded. Legal states are `registered`, `active`, `committed`, `rolled_back`, and `failed`.

Legal transitions are `registered -> active`, `registered -> failed`, and `active -> committed|rolled_back|failed`. Terminal states cannot transition. A trigger rejects illegal transitions and changes to identity, kind, or start time. Terminal rows require `finished_at_utc`; non-terminal rows forbid it. No run may be deleted.

Registration is committed before evidence mutation begins. Evidence changes occur in one explicit transaction after transition to `active`; successful completion and the transition to `committed` occur in that same transaction. If the transaction or process is interrupted, SQLite rolls back all uncommitted evidence and the prior committed run state remains `registered` or `active`. A later recovery procedure may classify a stranded non-terminal run as `failed` in a new transaction after confirming no registered writer owns the lock.

### `lane_state`

Composite primary key `(asset, timeframe)`, nullable `high_watermark_open_time_utc`, required `state_version >= 0`, optional `last_ingest_run_id`, and required `updated_at_utc`. This is restart state, not a second bar authority.

### `rollup_state`

Composite primary key `(asset, source_timeframe, target_timeframe)`, nullable `high_watermark_open_time_utc`, required `state_version >= 0`, optional `last_ingest_run_id`, and required `updated_at_utc`. Source and target must differ. This reserves restart state without implementing rollup behaviour.

No statement uses `INSERT OR REPLACE`.

## 4. Migration and initialization

The database parent directory must already exist. Initialization requires the registered-writer lock. The connection enables foreign keys, sets a finite busy timeout, selects WAL journal mode, and uses `synchronous=FULL`. Migration 1 creates all seven tables and enforcement triggers in one `BEGIN IMMEDIATE` transaction and records its source checksum before commit. Reopening validates the recorded checksum against the implementation.

Migration records are append-only. A checksum mismatch is a foundation failure, not an invitation to rewrite migration history.

## 5. Registered writer

For database path `authority.sqlite3`, the lock is `authority.sqlite3.writer.lock`. Before opening a mutable SQLite connection, a writer opens this file and obtains a non-blocking exclusive `fcntl.flock`. The lock is held by its file descriptor for the entire lifetime of the mutable connection and all its transactions. A second process fails before receiving a mutable connection.

While held, the lock file contains diagnostic JSON: format version, database path, PID, hostname, process start time, acquisition time, and a random ownership token. This metadata does not confer ownership; the kernel lock does. Stale text in an unlocked file is not a lock. Release writes release metadata while ownership is still held, flushes it, unlocks, and closes the descriptor.

This contract is independent of Python method restrictions. Any future writer implementation, in any language, must acquire the same filesystem lock before opening the database read-write. `flock` applies to cooperating processes on the local macOS filesystem; the database and lock must not be placed on a filesystem that does not preserve these semantics.

## 6. Transactions, crashes, and interruption

The writer uses autocommit mode only to make transaction boundaries explicit. Mutating work uses `BEGIN IMMEDIATE`; success commits and every exception rolls back. Nested implicit transactions are forbidden by the provided transaction context.

SQLite guarantees that an interrupted uncommitted transaction is absent after restart. WAL recovery is SQLite's responsibility. Fragarach II must never delete `-wal` or `-shm` files manually. A process crash releases the kernel writer lock automatically; diagnostic metadata may remain stale and must be interpreted only by attempting the lock.

## 7. Concurrency and read-only contract

Every consumer opens an existing database using the URI form `file:<absolute-path>?mode=ro`, then enables `query_only`, foreign keys, and the busy timeout. Consumers must not open the authority with a default read-write connection. They may begin read transactions for snapshot consistency and must keep them short enough not to prevent WAL checkpoint progress.

WAL permits readers concurrent with the one registered writer. “Unlimited” means the architecture imposes no application registration limit; operating-system and SQLite resource limits still apply.

## 8. Integrity verification

Verification uses a read-only connection and requires:

1. `PRAGMA integrity_check` returns exactly `ok`.
2. `PRAGMA foreign_key_check` returns no rows.
3. the application table set is exactly the seven specified tables.
4. migration versions, names, and checksums match the implementation.

Failure of any condition rejects the database as structurally valid. This is structural evidence only.

## 9. Backup and restoration

Use SQLite's online backup API from a read-only source connection to a newly created destination file on local durable storage. Never copy only the main database file while WAL mode is active. After backup, open the destination read-only and run the full integrity verification.

Restoration is performed while no writer or consumer uses the target path:

1. acquire the target writer lock;
2. verify the selected backup independently;
3. restore to a new sibling temporary path using SQLite's backup API;
4. verify the restored temporary database;
5. atomically rename the current database aside and the verified temporary database into place;
6. retain the prior database until post-restart verification succeeds;
7. open the restored authority, verify it again, and record the operational evidence externally.

The current code provides online backup and verification primitives; operator-controlled replacement is intentionally not automated in SPEC-001.

## 10. Acceptance tests and runtime proof

The focused standard-library test suite must prove:

- initialization persists `journal_mode=wal`;
- every mutable and read-only connection enforces foreign keys;
- the schema contains exactly seven application tables;
- raw blocks, provenance, migrations, and ingest-run history reject forbidden mutation;
- a second process cannot acquire writer ownership and lock metadata is diagnostic;
- multiple read-only connections can read while the writer holds an uncommitted transaction;
- an exception rolls a transaction back completely;
- committed data survives complete close and reopen;
- read-only consumers cannot mutate;
- integrity and foreign-key verification pass;
- an online backup can be restored and verified.

The report records environment, command, count, and results. These tests do not simulate sustained operation, storage-device failure, host loss, or production load, and cannot promote the candidate authority.

## 11. Runtime proof command

From the repository root:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Fragarach II remains a candidate authority until runtime operation proves otherwise. **Operations is King.**

