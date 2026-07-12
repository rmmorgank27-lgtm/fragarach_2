# SPEC-017D Import Dispatch Repair Report

## Repair

Import review and confirmation now use an immutable `IMPORT_FILE` plan. The plan captures its own ID, file-selection ID, mode, instrument, timeframe, path, checksum, and conflict policy. Confirmation dispatches the captured `.importCSV` intent directly to the existing `ingest_file` command; it never re-reads the live Fetch/Import mode to choose a command.

Changing mode, instrument, or file clears the reviewed plan and visible result. Selecting a file creates a new file-selection ID. A result renders only when its plan ID, mode, instrument, timeframe, and file checksum still match the current screen.

Import failure presentation now extracts the actual ingestion rejection. Provider fallback wording and Try Again are restricted to Fetch plans.

## Verification

- Focused OperationsCore import-dispatch check passed: exact `.importCSV` intent, matching context accepted, Fetch mode rejected, changed checksum rejected.
- One Swift build passed.
- One signed native USDJPY/D1 CSV smoke passed using isolated runtime `/tmp/fragarach-spec017d.sqlite3`.
- The exact named `FX_USDJPY, 1D_44615.csv` was not present on disk; the available `old_USDJPY_d1.csv` was used for native dispatch proof.
- Native review showed `IMPORT_FILE`, USDJPY, D1, and checksum `df836edd70e8dc065cdd5a0aa39558bec7e5e29766dab6ef2d43d0937facc557`.
- `ingest_file` produced one committed `manual_file` run, raw block `raw-df836edd70e8dc065cdd5a0aa39558bec7e5e29766dab6ef2d43d0937facc557`, 657 inserted, 0 unchanged, and 0 conflicts preserved.
- Provider acquisitions beginning after the import run: 0.
- The native result showed the import counts and no provider-failure panel.

Provider resolution, mappings, registry authority, and ingestion behaviour were not changed.

Acceptance result: **PASS**.
