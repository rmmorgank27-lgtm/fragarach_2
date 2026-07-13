# SPEC-018 Acceptance Report

Date: 2026-07-12 (Australia/Brisbane)

## Result

PASS. Fragarach II serves complete D1 canonical history through
`fragarach_ii.external_consumer_history.v1`. Morphix FCv1 invokes the authority
process with only symbol and timeframe, maps every returned bar for display, and
does not fall back to chart-cache history when authority history is unavailable.

| Symbol | Status | Authority | Truth | First bar | Last bar / CAODT | Bars | Match |
|---|---|---:|---:|---|---|---:|---|
| EURUSD | AVAILABLE | GREEN | 87 | 2012-11-05 | 2026-07-11 | 3,642 | PASS |
| BTCUSD | AVAILABLE | GREEN | 91 | 2009-10-05 | 2026-07-11 | 6,032 | PASS |
| AAPL | AVAILABLE | GREEN | 90 | 2026-07-01 | 2026-07-09 | 6 | PASS |

For every lane, response bar count and first/last timestamps matched direct
read-only canonical queries; Truth Score and CAODT matched the existing Truth
Engine. AAPL's six rows are the complete history currently held by Fragarach.

## Verification

- Focused Fragarach contract tests: 3 passed.
- Focused Morphix contract/display tests: build and test command passed.
- Fragarach Swift build: passed.
- Morphix production app build and ad-hoc signing: passed.
- Native launch smoke test: passed; `Morphix FCv1` remained operational.
- Runtime preflight: Fragarach II contract import/request passed; the existing
  Morphix engine-control bridge remained separately configured and passed.

No ingestion, provider, Truth, registration, calendar, validation, schema, or
Morphix engine behavior was duplicated or changed.
