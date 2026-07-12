# SPEC-017 Operator Acceptance Report

Acceptance used the running signed native application and isolated runtime `/tmp/fragarach-spec017.sqlite3`.

## Passed journeys

1. Searched Tesla, reviewed the mapped TSLA representation, registered it as `REGISTERED_NO_EVIDENCE`, and continued directly to Data Operations with TSLA selected. Bounded Initial Fetch was selected and Review was enabled.
2. Selected AUDUSD, reviewed canonical dates `2026-06-12` through `2026-07-11`, and completed a bounded provider request. The receipt showed actual range `2026-06-13` through `2026-07-11`, 29 received, 7 inserted, 2 unchanged, 20 conflicts preserved, raw block, CAODT, Truth Score 92, and warnings.
3. Searched `ASX:CBA`, registered Commonwealth Bank without a provider mapping as `REGISTERED_UNMAPPED`, and continued with ASXCBA selected. Provider fetch alone was unavailable; Import File, View Registration, and Retire remained available.
4. Imported the reviewed two-row fixture into ASXCBA/D1 through the immutable pipeline. The registration remained `REGISTERED_UNMAPPED`; the native receipt showed 2 inserted rows and the matching raw block.
5. Opened History at All Instruments, filtered to ASXCBA, selected its receipt, and verified timestamp, instrument, timeframe, manual source, result, row counts, warnings, raw block, and technical detail. The full-width layout and filtered empty state did not overlap controls.
6. Refreshed Truth after mutation. ASXCBA appeared immediately with its imported D1 evidence and Truth Score 75; AUDUSD showed its refreshed CAODT and score.
7. Opened ASXCBA retirement and reached the populated SPEC-013 impact review showing active lane, evidence counts, acquisition history, operational effects, preservation guarantee, reason, note, and typed confirmation. The review was cancelled without retirement.
8. Opened working System Status, Backups, Settings, and Audit. Status reported the isolated runtime as readable, Backups exposed verification/destination controls, Settings exposed the configured paths, and Audit displayed real Authority Ledger events.

## Final gates

- Python tests: 146 passed.
- Swift build: passed.
- OperationsCoreChecks: 25 passed.
- Signed build and process verification: passed.
- Reviewed runtime SHA-256 before and after isolated acceptance: `da7dfaa6450b95c739f19e70e9912dfa88a6edc4b3584a7107aaf99f12b5cb07`.

Acceptance result: **PASS**.
