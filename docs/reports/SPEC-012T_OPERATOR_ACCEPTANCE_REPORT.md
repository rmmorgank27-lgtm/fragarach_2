# SPEC-012T Operator Acceptance Report

Date: 2026-07-12

| Case | Result |
|---|---|
| EURAUD | PASS — ordered identity, EUR/AUD exact mapping, direct orientation, existing registration |
| AUDEUR | PASS — distinct identity, no AUD/EUR mapping, inverse-only, EURAUD offered |
| AUD/EUR, AUD-EUR, AUD EUR | PASS — preserve AUD then EUR |
| Reverse fixtures | PASS — authority-driven direct, inverse, or unknown state |
| Both-orientations fixture | PASS — each independent direct mapping accepted |
| Unknown valid ISO pair | PASS — capability unknown, not known/unsupported |
| Registration guard | PASS — inverse-only rejected before writer |
| Acquisition guard | PASS — mismatch rejected before provider/persistence |
| Runtime audit | PASS — three registrations inspected read-only; no suspect registration found |
| Responsive native layout | PASS |

## Screenshots

- [EURAUD direct presentation and valid existing path](SPEC-012T/screenshots/euraud-direct.png)
- [AUDEUR inverse-only, Open EURAUD, and unavailable lanes](SPEC-012T/screenshots/audeur-inverse.png)
- [Open EURAUD navigation result](SPEC-012T/screenshots/open-euraud.png)

No suspect-registration warning screenshot is applicable because the runtime audit found no suspect registration. The warning state is covered by the isolated synthetic audit fixture without mutating runtime history.

## Acceptance

SPEC-012T orientation gates pass. The separate SPEC-012S D1-only multi-timeframe schema limitation remains documented and unchanged.
