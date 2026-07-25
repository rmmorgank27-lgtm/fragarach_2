# Persistent Scheduler Service

Fragarach II scheduled acquisition runs as the current user's LaunchAgent. The app is the native presentation and management surface; ordinary app quit only disconnects monitoring and does not stop acquisition.

## Ownership and files

The service uses one lifetime `flock` per authority database. Its inspectable owner metadata contains the database identity, service instance/build, process start and heartbeat times, and ownership generation. A second service or recovery CLI cannot acquire the same authority.

Operational service files are stored with user-only permissions under:

```text
~/Library/Application Support/Fragarach II/Scheduler/<authority-id>/
```

The LaunchAgent is:

```text
~/Library/LaunchAgents/com.raymorgan.fragarach-ii.scheduler.plist
```

The plist contains no provider credential. The service resolves the same chain as the app: development environment, macOS Keychain, then an explicitly approved credential file.

## Native lifecycle

The Scheduler workspace presents Install, Start, Stop, Restart, Update, Repair, Enable, Disable, and Uninstall actions. Installation confirmation shows the service location, authority database, journal, automatic login behavior, build, and credential source.

`Pause All` keeps the service and monitor alive while suppressing dispatch. `Stop Service` requests graceful shutdown, waits for active publication/checkpoint work, and releases acquisition ownership.

## Diagnostic CLI

The CLI is a diagnostic and command transport, not a competing scheduler:

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.scheduler \
  --database /path/to/authority.sqlite3 --mode service-status --json

PYTHONPATH=src python3 -m fragarach_ii.commands.scheduler \
  --database /path/to/authority.sqlite3 --mode repair --json
```

Direct execution requires `--development` or `--recovery` and still fails with `SERVICE_OWNS_ACQUISITION` if the persistent owner is live.

## Contracts

```text
fragarach_ii.scheduler_service_status.v1
fragarach_ii.scheduler_service_command.v1
fragarach_ii.scheduler_monitor.v3
```

Commands carry an identifier, type, issued time, app build, target service generation, scope, and payload. Acknowledgements are persisted and repeated identifiers return `already applied`.
