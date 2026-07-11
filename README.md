# Fragarach II

Fragarach II is a candidate authority for trusted historical market-bar evidence. Its only responsibilities are to read, validate, store, and serve evidence.

The current implementation has an exact eight-table SQLite foundation, including the canonical instrument-registration authority, plus bounded manual and Twelve Data D1 evidence paths. Passing its tests proves local mechanics; it does not establish operational trust or production readiness.

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

**Operations is King.**
