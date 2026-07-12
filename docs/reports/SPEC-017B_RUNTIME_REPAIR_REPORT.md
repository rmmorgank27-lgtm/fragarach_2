# SPEC-017B Unmapped Registration Runtime Repair

## Cause and repair

The native Confirm Registration bridge correctly called `fragarach_ii.commands.register_instrument`, but that command still ran `validate_direct_mapping` for every FX registration. That Fetch-only guard rejected provider-independent candidates before the V2 writer could persist `REGISTERED_UNMAPPED`. The configured authority database also remained at migration 6.

The registration command now applies the already-approved migrations through version 7, then calls the existing registration writer without requiring an FX provider mapping. Direct-orientation validation remains in the Twelve Data Fetch path. Discover Market converts structured registration failures into readable text rather than displaying raw JSON, and the existing operation completion refresh remains unchanged.

## Native acceptance

Acceptance used the signed application with fresh isolated runtime `/tmp/fragarach-spec017b.sqlite3`.

- EURUSD: Confirm Registration completed as `REGISTERED_UNMAPPED` with null provider identity. Continue to Data Operations selected EURUSD immediately. Import File, View Registration, and Retire Instrument were available; provider Fetch alone displayed `Provider fetch unavailable for this instrument`.
- EURAUD: Confirm Registration completed as `REGISTERED_NO_EVIDENCE` with `TWELVE_DATA` / `EUR/AUD`. Continue to Data Operations selected EURAUD with Bounded Initial Fetch active and Review Data Operation available.

## Configured runtime and verification

- A pre-migration safety copy was created at `/tmp/spec017b-configured-pre-migration.sqlite3` with SHA-256 `da7dfaa6450b95c739f19e70e9912dfa88a6edc4b3584a7107aaf99f12b5cb07`.
- Configured runtime migration 7 applied successfully and its complete integrity/migration verification passed.
- Application preference was restored to the configured runtime.
- Python: 150 tests passed.
- OperationsCoreChecks: 25 passed.
- Swift build: passed.
- Signed application build, signing, launch, and process verification: passed.

Registry contents, provider mappings, Truth, ingestion, retirement, schema definition, and acquisition logic were not changed.

Acceptance result: **PASS**.
