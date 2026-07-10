# Fragarach II

Fragarach II is a candidate authority for trusted historical market-bar evidence. Its only responsibilities are to read, validate, store, and serve evidence.

The current implementation includes the seven-table SQLite foundation and the bounded manual D1 CSV ingestion path defined by [`SPEC-002_COMMON_STAGING_MANUAL_INGESTION.md`](specs/foundation/SPEC-002_COMMON_STAGING_MANUAL_INGESTION.md). Passing its tests proves local mechanics; it does not establish operational trust or production readiness.

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

**Operations is King.**
