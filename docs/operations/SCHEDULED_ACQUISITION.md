# Scheduled Acquisition Operations

The native Fragarach II app owns the scheduler lifecycle. Opening the app starts `fragarach_ii.commands.scheduler`; closing the app terminates it. No cron job or launch agent is required.

## Inspect without starting acquisition

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.scheduler \
  --database /path/to/authority.sqlite3 --mode status --json
```

This is read-only. It reports the current lane states, next approved boundary, authority revision, health assessment, and recent operational journal events.

## Run the service

```sh
TWELVE_DATA_API_KEY='…' PYTHONPATH=src python3 -m fragarach_ii.commands.scheduler \
  --database /path/to/authority.sqlite3 --mode run --json
```

The service emits one JSON monitor snapshot per line. It performs a startup catch-up pass, then sleeps until the exact next operational boundary. `SIGTERM` and `SIGINT` stop it cleanly.

## State and failure behavior

- Operational journal: `<database>.scheduler.json`
- Canonical tables: unchanged
- Credential: environment only; never emitted or written to the journal
- Failure scope: one lane
- Retry: the next eligible boundary, or the next service startup catch-up
- `NO_NEW_DATA`: recorded without fabricating or rewriting an observation

Delete the operational journal only when intentionally discarding scheduler history. Doing so does not modify canonical market evidence.
