# SPEC-015R Operator Acceptance Report

Status: ACCEPTED IN ISOLATED NATIVE RUNTIME

Date: 2026-07-12 (Australia/Brisbane)

## Native acceptance journeys

1. Discover Market: searched Google, selected the GOOGL representation, reviewed D1 registration, confirmed it, and received Registration Complete.
2. Mutation refresh: Continue to Data Operations immediately selected and displayed GOOGL/D1 as active with no evidence.
3. Fetch: selected Custom Range and reached an enabled final review showing provider, D1, canonical inclusive dates, and conflict policy. The provider call was intentionally not executed.
4. Import File: selected active AUDUSD/D1, chose `tests/fixtures/manual/AUDUSD_D1.csv`, reviewed filename, byte size, SHA-256, two detected rows, selected lane, and conflict policy, then executed the immutable import. The app returned Data Operation Complete with two preserved conflicts and raw-block ID `raw-59055fc0c78689e06f5d578983cf5e21d94a7223311f9c21ef984fa404069d87`.
5. Retirement: selected EURAUD/D1 through the repaired Retire segment, reviewed SPEC-013 impact, supplied a controlled reason and operator note, confirmed retirement, and received a readable retirement receipt showing acquisition disabled, evidence preserved, and active serving removed.
6. System: directly opened working Status, Backups, Settings, and Audit segments. Status showed the isolated runtime and verification control; Backups exposed verification and backup destination controls; Settings exposed database/repository/Python controls; Audit exposed real ledger events, lifecycle registrations, and committed operation receipts.
7. Contextual authority navigation: selected XAUUSD in Truth and used View Authority History. The app routed to System → Audit → Authority Events with the XAUUSD filter and displayed its lane and registration events.
8. Selector refresh: registration immediately appeared after onboarding; retired GOOGL and EURAUD disappeared from active selectors while remaining visible as RETIRED in Audit lifecycle history; Truth remained operational after mutation.

## Integrity boundary

All mutations occurred only in `/tmp/fragarach-spec015r.sqlite3`. The reviewed runtime SHA-256 remained `88f962b004ac359bf9263c1102a2b265105d5365764f28252d3d15c259d061c6` after acceptance.

This acceptance is based on completed native operator interaction, not tab screenshots or backend tests alone.
