# SPEC-017 Implementation Report

SPEC-017 adds a deterministic local market registry and connects it to the existing Discover Market and Data Operations workflows.

## Delivered

- Registry-first discovery with exact canonical/listed symbols, aliases, names, normalised search, safe spelling correction, and the existing provider fallback.
- Mapped registrations enter `REGISTERED_NO_EVIDENCE`; unmapped registrations use the provider-independent V2 contract and enter `REGISTERED_UNMAPPED` without invented provider facts.
- Schema migration 7 preserves registrations, lanes, triggers, immutable evidence, and history while permitting all-null provider identity for V2 registrations.
- Unmapped instruments remain importable and retireable; only their provider fetch is unavailable.
- Fetch defaults to Bounded Initial Fetch, Bounded Update when a safe append exists, or Custom Range. Maximum Available remains visibly unavailable without blocking safe intents.
- Fetch results expose requested/actual ranges, row outcomes, raw block, CAODT, Truth Score, warnings, and collapsed technical details.
- History has All Instruments and instrument scopes, receipt columns, matching detail, and an unobstructed empty state.
- Swift Truth and authority models decode provider-independent registrations honestly.

## Verification

- Python: 146 tests passed.
- Swift build: passed without warnings.
- OperationsCoreChecks: 25 passed.
- Signed application bundle: built, ad-hoc signed, launched, and process-verified.

No provider credentials, Truth scoring rules, immutable ingestion semantics, retirement authority, backup service, or settings service were redesigned.
