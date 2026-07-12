# SPEC-012R Operator Acceptance Report

Date: 2026-07-12
Application: Fragarach II — Operations Console

## Results

| Case | Result |
|---|---|
| XAGUSD | PASS — Silver, XAGUSD selected, SI and SLV alternatives, no WTI |
| Silver | PASS — representation selection required |
| Google | PASS — Alphabet, GOOGL Class A and GOOG Class C, no Gold, no silent selection |
| US30 | PARTIAL — Dow and alternatives resolve; provider-unmapped registration is authority-blocked |
| NZDJPY | PASS — deterministic FX and registration plan |
| QZXNOTAMARKET | PASS — honest UNKNOWN, no unrelated suggestions or mutation |
| Add/review/confirm | PASS — reviewed XAGUSD mutation through existing authority |
| Duplicate prevention | PASS — repeat confirmation returns identical existing registration |
| Continue to Acquisition | PASS — newly registered symbol prefills Acquire |
| Responsive layout | PASS — single result and unknown use full detail width; adaptive cards/grid; no permanent result master column |

## Screenshots

- [XAGUSD / Silver](SPEC-012R/screenshots/xagusd.png)
- [Google / Alphabet](SPEC-012R/screenshots/google.png)
- [US30 / Dow](SPEC-012R/screenshots/us30.png)
- [Add to Fragarach](SPEC-012R/screenshots/xagusd.png)
- [Registration review](SPEC-012R/screenshots/registration-review.png)
- [Successful registration and Continue to Acquisition](SPEC-012R/screenshots/registration-success.png)
- [Acquisition handoff](SPEC-012R/screenshots/continue-to-acquisition.png)
- [Full-width empty/search layout](SPEC-012R/screenshots/discover-empty.png)

## Runtime Evidence

The native app built, signed, launched, and remained running as process `FragarachII`. XAGUSD was registered in the configured runtime authority database as `REGISTERED_NO_EVIDENCE`.

## Acceptance Status

Conditional/blocked. All executable known-mapping onboarding gates passed. Full acceptance cannot be claimed until the immutable registration authority supports provider-unmapped Fragarach identities without fabricated provider fields.
