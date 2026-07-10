# Fragarach II macOS Operations Console

The console is a native SwiftUI macOS 14 application. It reads the selected authority directly through SQLite's read-only contract and delegates every mutation to the repository's existing Python CLI.

## Build and launch

```sh
./script/build_and_run.sh
```

The script builds with SwiftPM, stages `dist/Fragarach II.app`, and launches it as an ordinary foreground application. `--verify` additionally checks that the process launched. Debug, logs, and telemetry modes are available as documented by the script usage.

The default development paths target this repository, its Python 3.13 executable, and `data/runtime/spec002_real_evidence_acceptance.sqlite3`. Settings can explicitly choose another database and configured CLI location. Database selection never searches for an authority or invokes a PATH installation.

## Safety model

- Launch, refresh, navigation, selection, search, and filtering are read-only.
- Acquire and Import require review followed by explicit confirmation.
- Integrity and backup run only when requested.
- One child operation can run at a time; read views remain available.
- Closing the application during an operation should be avoided; use Cancel and allow the CLI transaction boundary to finish.
- Preferences contain paths and presentation choices only.
- The app does not create, migrate, restore, edit, or delete authority data.

The app displays **Candidate Authority** and makes no readiness or trading judgment.
