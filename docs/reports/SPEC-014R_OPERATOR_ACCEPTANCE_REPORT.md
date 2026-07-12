# SPEC-014R Operator Acceptance Report

Date: 2026-07-12

Running signed application baseline identifier: `198cb17` plus the reviewed SPEC-014R working-tree repair. Process verification passed and `FragarachII` remained running.

## Acceptance results

1. Initial Data Operations state showed a populated list, no highlighted row, and `Select a registered instrument` with no Apple details.
2. One click on Apple highlighted Apple and displayed the AAPL header, lanes, evidence, Truth, CAODT, and modes.
3. One click on EURAUD replaced Apple highlight and detail immediately.
4. One click on Silver highlighted Silver and displayed XAGUSD detail.
5. Search/filter reconciliation uses controlled clearing when a selected registration becomes invisible; clearing search never chooses the first row.
6. Refresh preserves a still-visible registration ID and re-resolves current snapshot detail.
7. Show Retired exposed JPYCHF. One click displayed only retired historical facts and no active Fetch/Import controls. Disabling Show Retired removed JPYCHF, cleared selection, and restored guidance.

## Screenshots

- [Initial empty selection](SPEC-014R/screenshots/01-initial-empty-selection.png)
- [Apple selected](SPEC-014R/screenshots/02-apple-selected.png)
- [EURAUD selected](SPEC-014R/screenshots/03-euraud-selected.png)
- [Silver selected](SPEC-014R/screenshots/04-silver-selected.png)
- [JPYCHF retired selected](SPEC-014R/screenshots/05-jpychf-retired-selected.png)
- [Retired hidden and selection cleared](SPEC-014R/screenshots/06-retired-hidden-selection-cleared.png)

No provider, import, registration, retirement, evidence, or database mutation was performed during selection acceptance.
