# SPEC-020 Provider Resolution Bootstrap — Repair Report

Date: 2026-07-13 (Australia/Brisbane)

## Repair

`_confirm_registration_evidence` now writes an unmapped registration's
`evidence_confirmed_at_utc` only when that field is null. Later provider or file
ingestions preserve the original first-evidence timestamp and continue through
the existing immutable ingestion pipeline.

This is an idempotence guard at the failing boundary. It does not change:

- provider selection or symbol translation;
- registration identity or status;
- schema or immutable trigger rules;
- canonical merge, validation, Truth, or external serving;
- provider fallback behavior or Morphix.

## Verification

- Focused provider-resolution and Twelve Data tests: **18 passed**.
- New regression: repeated acquisition for an evidenced
  `REGISTERED_UNMAPPED` lane succeeds, keeps the original evidence timestamp,
  and records unchanged bars normally.
- Fragarach build: **passed**.
- Live provider fetch acceptance: **passed**.

| Symbol | Provider identity | Ingest | Confirmed mapping receipt | Truth after fetch |
|---|---|---|---|---|
| AUDCAD | `TWELVE_DATA / AUD/CAD` | 4 inserted | `CONFIRMED_BY_VALID_EVIDENCE` | GREEN, 87 |
| AUDNZD | `TWELVE_DATA / AUD/NZD` | 4 inserted | `CONFIRMED_BY_VALID_EVIDENCE` | GREEN, 87 |
| USDJPY | `TWELVE_DATA / USD/JPY` | 4 inserted | `CONFIRMED_BY_VALID_EVIDENCE` | GREEN, 90 |

All three acquisitions refreshed persisted validation and CAODT through the
normal Twelve Data acquisition workflow. Validation remains strict and reports
the existing historical/outside-session warnings; no validation rule was
weakened.

Acceptance result: **PASS**.
