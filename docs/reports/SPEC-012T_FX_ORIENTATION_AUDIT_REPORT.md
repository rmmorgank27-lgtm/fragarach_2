# SPEC-012T FX Orientation Audit Report

Date: 2026-07-12
Database: configured runtime authority
Mode: read-only
Mutations performed: 0

| Canonical FX symbol | Timeframe | Base | Quote | Provider symbol | Registration | Bars | Audit state | Future acquisition |
|---|---|---|---|---|---|---:|---|---|
| AUDUSD | D1 | AUD | USD | AUD/USD | REGISTERED_WITH_EVIDENCE | 14262 | ORIENTATION_CONFIRMED | Allowed |
| EURAUD | D1 | EUR | AUD | EUR/AUD | REGISTERED_NO_EVIDENCE | 0 | ORIENTATION_CONFIRMED | Allowed |
| JPYCHF | D1 | JPY | CHF | JPY/CHF | REGISTERED_WITH_EVIDENCE | 9 | ORIENTATION_CONFIRMED | Allowed |

Evidence source for each confirmed mapping: `config/providers/mappings/TWELVE_DATA_FX_DIRECT_PAIRS_V1.json`.

No constructed provider symbol, inverse evidence reuse, or canonical/provider orientation mismatch was found in the configured runtime database. Existing evidence was not changed. No reciprocal data was generated.
