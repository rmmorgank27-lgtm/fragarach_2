# SPEC-015 Preflight Report

Date: 2026-07-12

The primary route model was `ConsoleSection` with Truth, Lanes, Authority Ledger, Data Operations, Discover Market, Operations, Integrity & Backup, and Settings. `ConsoleStore.section` was the single root selection and `ContentView` switched directly over the eight implementation-facing views.

Capability map before repair:

- `TruthConsoleView`: Estate Truth summary, matrix, and selected Truth detail.
- `LanesView`: read-only lane list, validation, and bar state.
- `AuthorityLedgerView`: read-only immutable authority events.
- `DataOperationsView`: fetch/update, import, retirement, and instrument selection.
- `DiscoverMarketView`: discovery, representation choice, registration, open existing, acquisition continuation, and retirement.
- `OperationsView`: latest 100 ingest operation receipts and detail JSON.
- `IntegrityBackupView`: verification and verified backup actions.
- `DiagnosticsSettingsView`: database, repository, Python, and presentation preferences.

Existing contextual navigation used `ConsoleStore.section`, `acquisitionAsset`, `selectedTruthLaneID`, `selectedLaneID`, `selectedOperationID`, and Discover Market action closures. Data Operations already preserved stable registration selection from SPEC-014R.

Operation history is sourced read-only from `ingest_runs` plus provenance aggregates in `SQLiteReadService.queryOperations`. Authority Audit is sourced from immutable `authority_events`. Backup and settings components already invoke their reviewed existing services.

Required implementation files include the navigation enums/router, `ConsoleStore`, `ContentView`, Data Operations, Truth detail, Discover Market, operation history, Authority Ledger, and a new System workspace container. Compatibility redirects are required for lanes, ledger, operations, integrity/backup, settings, acquire, and import routes.

No schema, migration, constitutional authority, Truth, registration, ingestion, retirement, backup engine, or runtime database change is needed.
