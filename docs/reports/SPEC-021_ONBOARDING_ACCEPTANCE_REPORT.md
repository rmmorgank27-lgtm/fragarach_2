# SPEC-021 End-to-End Onboarding — Acceptance Report

Date: 2026-07-13 (Australia/Brisbane)

## Result

**PASS.** GBPJPY progressed from an unused reviewed registry record to
authoritative consumer history through the normal operator workflow.

```text
Discover → Select → Register → Acquire → Ingest → Validate
→ Truth → Authority Refresh → SPEC-018 → Morphix
```

## Accepted authority

| Fact | Result |
|---|---|
| Canonical symbol | GBPJPY |
| Registration | `REGISTERED_UNMAPPED` |
| Confirmed provider receipt | `TWELVE_DATA / GBP/JPY` |
| Provider observations | 3,698 |
| Canonical bars | 3,691 |
| Explicitly rejected observations | 7 invalid OHLC rows |
| First canonical bar | 2012-11-05 |
| Last bar / CAODT | 2026-07-12 |
| Truth | GREEN 87 |
| SPEC-018 | `AVAILABLE` |
| Morphix | symbol visible; 3,691-bar authority chart rendered |

The Fragarach native app refreshed GBPJPY into its Truth matrix without restart.
Morphix discovered the new authority lane on Reload and displayed the returned
history without requiring an engine cache, alternate data, CSV, or duplicated
database.

Validation remained strict: invalid provider observations were excluded and
preserved as explicit rejections; existing session warnings remained visible.
