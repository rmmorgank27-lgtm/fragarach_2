# SPEC-014R Preflight Report

Date: 2026-07-12

- Current mutable selection was `selectedAsset: String?` in `DataOperationsView`.
- `List` bound directly to that value, while each row used `.tag(Optional(r.asset))`. With optional selection, the row tag must be the wrapped `String`, not `Optional<String>`; the nested optional disconnected the visible highlight from detail state.
- Detail presentation used `if let r = registration`, where `registration` was derived independently by matching `selectedAsset` against all registrations.
- `selectFirst()` assigned the first registration whenever selection was nil or invalid. That caused Apple details to appear with no honest explicit selection.
- Selecting Apple through the mismatched tag could write a value that did not match the bound selection identity, producing the empty guidance state.
- Refresh called `selectFirst()`, silently replacing nil or invalid selection instead of preserving a valid ID or clearing it.
- Search and Show Retired filtered rows but detail resolution used the unfiltered registration collection, permitting invisible selection/detail disagreement.
- Navigation context supplied a symbol through `ConsoleStore.acquisitionAsset`; it did not resolve the immutable registration ID.
- Instrument-specific file, range, review, retirement, and error state was not reset when changing instruments.

Repair files:

- `Sources/OperationsCore/DataOperationsSelection.swift`
- `Sources/FragarachII/Views/DataOperationsView.swift`
- `Sources/OperationsCoreChecks/main.swift`

The controlled filter behavior is the acceptable simpler behavior from SPEC-014R §7.3: if search or retired filtering hides the selected registration, selection is cleared and the honest empty state is shown. Clearing a filter never selects the first row.

No authority, schema, migration, registration, evidence, Truth, or database change is required.
