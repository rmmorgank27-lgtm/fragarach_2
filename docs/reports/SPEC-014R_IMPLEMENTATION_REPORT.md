# SPEC-014R Implementation Report

Date: 2026-07-12

The authoritative selection identity is now `InstrumentRegistrationRecord.id` (`asset:timeframe`), held once by `DataOperationsSelection.selectedRegistrationID`.

Repairs:

- Removed mutable symbol-only `selectedAsset` selection.
- Removed the silent `selectFirst()` default.
- Changed each List row tag to the exact non-optional `String` registration ID expected by the optional List selection binding.
- Derived selected detail from the current filtered registration snapshot.
- Corrected the detail condition to show guidance when no current visible registration resolves.
- Preserved a selected ID across refresh when still visible; re-resolved the registration, lanes, evidence, and Truth from the refreshed snapshot.
- Chose the controlled simpler filter behavior: search or Show Retired filtering clears a hidden selection and shows the honest empty state.
- Resolved explicit navigation symbol context to a visible immutable registration ID without selecting an unrelated fallback.
- Reset range, file, review, retirement, error, and conflict state whenever registration selection changes.
- Suppressed active-operation modes for retired registrations and displayed `RETIRED`, `HISTORICAL_ONLY`, `NOT_SERVED`, and `ACQUISITION_DISABLED` facts.
- Added native checks for empty initial state, stable selection replacement, refresh preservation, filter/retirement clearing, and valid/invalid navigation context.

Changed implementation files:

- `Sources/OperationsCore/DataOperationsSelection.swift`
- `Sources/FragarachII/Views/DataOperationsView.swift`
- `Sources/OperationsCoreChecks/main.swift`

No Python authority behavior, schema, migration, registration, lifecycle event, evidence, Truth logic, or runtime database was changed.
