# SPEC-015 Implementation Report

Date: 2026-07-12

Primary navigation is now exactly Truth, Discover Market, Data Operations, and System, with Truth retained as the default workspace. The root uses one `ConsoleSection` selection and a readable native sidebar width.

Capability relocation:

- Lane observation remains in the Truth matrix/detail and action lane state remains in Data Operations.
- Operations is now Data Operations → History with selected-instrument filtering, readable receipt detail, collapsed technical detail, and a ledger-evidence link.
- Authority Ledger is System → Audit with contextual filtering.
- Integrity and verified backup actions are System → Status and Backups.
- Existing settings are System → Settings.

Compatibility routing maps legacy lanes, authority ledger, operations, integrity/backup, settings, acquire, and import routes to the appropriate workspace and internal section. Truth Manage Data preserves instrument context; Truth Authority History and Discover Market history actions open filtered System Audit. Discover Market existing-authority actions now use operator-facing Open Truth, Manage Data, Authority History, and Retire labels.

SPEC-014R registration selection remains stable across all four Data Operations modes. History is also available unfiltered when no instrument is selected.

Native checks cover exact sidebar order/count, internal Data Operations and System sections, and every legacy redirect. No schema, migration, authority, Truth, provider, registration, ingestion, retirement, backup engine, or runtime evidence change was made.
