# SPEC-012S Operator Acceptance Report

Date: 2026-07-12

| Case | Result |
|---|---|
| OIL | PASS — ambiguous WTI/Brent choice, neither selected |
| SOL / Solana | PASS — canonical Solana, distinct SOLUSD/SOLUSDT |
| solanna | PASS — deterministic “Did you mean Solana?” confirmation |
| JPYCHF | PARTIAL — D1 existing; H1/M30/M5 visible, supported, authority-blocked |
| SOLUSD timeframes | PARTIAL — all four evaluated; intraday mutation authority-blocked |
| Apple | PASS — D1 visible; intraday capability unknown and explained |
| QZXNOTAMARKET | PASS — honest unknown, no lane matrix or mutation |
| Multi-lane selection/review/success/handoff | BLOCKED — SQLite immutable D1 constraints |
| Responsive layout | PASS — full-width representation and lane matrices |

## Screenshots

- [OIL ambiguity](SPEC-012S/screenshots/oil-ambiguity.png)
- [SOL and timeframe matrix](SPEC-012S/screenshots/solana.png)
- [solanna correction](SPEC-012S/screenshots/solanna-correction.png)
- [JPYCHF existing D1 and intraday authority states](SPEC-012S/screenshots/jpychf-lanes.png)
- [Apple capability transparency](SPEC-012S/screenshots/apple-capability.png)

Screenshots for multi-timeframe selection, batch review, per-lane insertion success, and multi-timeframe acquisition are not fabricated because the immutable schema prevents those operations.

## Status

Blocked for full acceptance. Discovery coverage and transparency gates pass; multi-timeframe mutation gates require an authorised schema/contract revision.
