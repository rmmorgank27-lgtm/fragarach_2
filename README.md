# Fragarach II

## Read-only replica clients

The Mac Studio can now run an isolated localhost publisher for approved
read-only replica clients. The Fragarach II application includes a **Read-Only
Clients** section for service lifecycle, client enable/disable/revoke, one-time
tokens, and compact full snapshots. Authority acquisition and storage remain
unchanged, and access defaults to disabled.

The MacBook Fragarach Lite snapshot admission, local Market History service,
automatic polling, LaunchAgent, and private Tailscale transport are commissioned
for the initial `AUDUSD/D1` lane. Publication signing, broader approved scope,
and incremental deltas remain gated. See
`docs/operations/READ_ONLY_REPLICA_CLIENTS.md` for the contract, current state,
controls, safety boundary, and verification evidence.

Fragarach II is a candidate authority for trusted historical market-bar evidence. Its only responsibilities are to read, validate, store, and serve evidence.

The current implementation preserves an exact twelve-table SQLite authority,
including durable Scheduler runtime and audit state. Passing its tests proves
local mechanics; it does not by itself establish operational trust or
production readiness.

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

## Handbook

The maintained documentation set is in [`docs/handbook/`](docs/handbook/README.md):

- [User manual](docs/handbook/USER_MANUAL.md)
- [Integration manual](docs/handbook/INTEGRATION_MANUAL.md)
- [Developer guide](docs/handbook/DEVELOPER_GUIDE.md)
- [Architecture and data flows](docs/handbook/ARCHITECTURE_AND_DATA_FLOWS.md)
- [Maintenance and troubleshooting](docs/handbook/MAINTENANCE_AND_TROUBLESHOOTING.md)
