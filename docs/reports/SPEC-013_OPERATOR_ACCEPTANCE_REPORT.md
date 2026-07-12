# SPEC-013 Operator Acceptance Report

Date: 2026-07-12

| Gate | Result |
|---|---|
| JPYCHF Open Existing and Retire Instrument | PASS |
| Whole/selected lane scopes | PASS |
| Impact review and controlled reason | PASS |
| Typed `RETIRE JPYCHF` confirmation | PASS |
| Successful retirement receipt | PASS |
| Future acquisition disabled | PASS — controlled `INSTRUMENT_RETIRED` |
| Active Truth and Estate Truth | PASS — JPYCHF excluded |
| Active lane list | PASS — JPYCHF excluded |
| Discovery after retirement | PASS — historical retired, no active action |
| Historical audit | PASS — ledger declarations/supersessions visible |
| Evidence preservation | PASS — counts, checksum, bytes unchanged |
| Repeat retirement | PASS — `ALREADY_RETIRED_IDENTICAL` |
| Lane-only isolation | PASS in isolated test |
| Physical deletion | None |

## Screenshots

- [JPYCHF Open Existing](SPEC-013/screenshots/jpychf-open-existing.png)
- [Retirement impact and reason](SPEC-013/screenshots/retirement-impact-review.png)
- [Typed confirmation](SPEC-013/screenshots/typed-confirmation.png)
- [Successful retirement receipt](SPEC-013/screenshots/retirement-success.png)
- [Retired discovery/audit state](SPEC-013/screenshots/retired-discovery.png)
- [Active lanes without JPYCHF](SPEC-013/screenshots/active-lanes-without-jpychf.png)

The backend blocked-acquisition acceptance returned `INSTRUMENT_RETIRED` with `evidence_committed=false`; the retired-discovery screenshot proves the native workflow exposes no acquisition action for JPYCHF.

## Runtime

The signed native app launched and remained running after retirement. JPYCHF is preserved historically and no longer operationally served.
