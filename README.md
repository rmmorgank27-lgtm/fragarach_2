# Fragarach II

Fragarach II is a candidate authority for trusted historical market-bar evidence. Its only responsibilities are to read, validate, store, and serve evidence.

The current implementation preserves an exact ten-table SQLite authority while keeping Scheduler service state in user-scoped operational files. Passing its tests proves local mechanics; it does not by itself establish operational trust or production readiness.

## Development

Requires Python 3.12 or later and has no runtime dependencies outside the standard library.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Manual proof command:

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.ingest_file \
  --database /path/to/authority.sqlite3 \
  --file /path/to/AUDUSD_D1.csv \
  --symbol AUDUSD --timeframe D1 --merge-mode preserve --json
```

Factual D1 validation defaults to read-only/no-persist:

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.validate_lane \
  --database /path/to/authority.sqlite3 \
  --symbol AUDUSD --timeframe D1 --through-date 2026-07-10 \
  --no-persist --json
```

Bounded Twelve Data acquisition is documented in
[`TWELVE_DATA_ACQUISITION.md`](docs/operations/TWELVE_DATA_ACQUISITION.md).

Calendar-driven scheduled acquisition and the native Scheduler Monitor are documented in
[`SCHEDULED_ACQUISITION.md`](docs/operations/SCHEDULED_ACQUISITION.md).

Persistent Scheduler Service installation, lifecycle, and diagnostics are documented in
[`PERSISTENT_SCHEDULER_SERVICE.md`](docs/operations/PERSISTENT_SCHEDULER_SERVICE.md).

**Operations is King.**
