# SPEC-012R Implementation Report

Date: 2026-07-12

## Implemented

- Added deterministic coverage for precious metals, major companies, indices, energy, commodities, FX, and crypto.
- Added Silver (`XAGUSD`, CFD, `SI`, `SLV`) and Alphabet (`GOOGL` Class A, `GOOG` Class C).
- Replaced loose character suggestions with exact symbol/name/alias and token-aware financial matching.
- Unknown results now show attempted categories and never pad Similar Markets with unrelated values.
- Added selection-specific readiness, warnings, provider mapping state, and encoded reviewed registration plans.
- Added full-width responsive SwiftUI results with selectable representation cards and adaptive detail grids.
- Added Add to Fragarach, explicit registration review, Confirm/Back/Cancel, Open Existing, registration completion, and Continue to Acquisition.
- Acquire now accepts a prefilled registered symbol.
- Registration continues to use the existing transactionally safe registered writer; duplicate submission returns `EXISTING_IDENTICAL`.

## Verification

- `PYTHONPATH=src python3 -m pytest -q`: 127 passed.
- `swift build`: passed.
- `swift run OperationsCoreChecks`: 15 passed.
- `./script/build_and_run.sh --verify`: built, ad-hoc signed, launched, and process remained running.
- Direct XAGUSD registration: `INSERTED`; repeat: `EXISTING_IDENTICAL`; rediscovery: `OPEN_EXISTING`.

## Schema

No schema or migration files were changed.

## Remaining Authority Limitation

See `SPEC-012R_REGISTRATION_AUTHORITY_BLOCKER.md`. Provider-unmapped representations cannot honestly be registered under the current mandatory provider-coupled authority contract.
