# SPEC-012 Acceptance Report

**Specification:** `SPEC-012_MARKET_DISCOVERY_AND_INSTRUMENT_ONBOARDING`

**Date:** `2026-07-12`

**Acceptance:** `PASS`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Python Acceptance

```text
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: **125 tests passed**.

Six focused tests cover CFD, ETF, futures, index, commodity, currency, and company aliases; multiple representations; provider mappings; representation-aware recommendations; ambiguous BHP markets; existing Truth context; unknown guidance; determinism; and read-only operation. All SPEC-011 and earlier tests remain green.

## Native Acceptance

```text
swift build
swift run OperationsCoreChecks
```

Result: **build passed; 15 native checks passed**.

The added check invokes US30 discovery, decodes the complete onboarding model, and verifies its CFD recommendation, five Dow representations, and provider discovery.

## Bundle Acceptance

```text
./script/build_and_run.sh --verify
```

Result: **signed icon-bearing application bundle rebuilt, launched, and running process verified**.

## Acceptance Matrix

| Requirement | Result |
| --- | --- |
| Common market names recognized | YES |
| CFD, ETF, futures, and index aliases recognized | YES |
| Tradable forms displayed | YES |
| Provider discovery displayed | YES |
| Registration recommendation displayed | YES |
| Existing registrations and Truth detected | YES |
| Standalone Resolve Instrument removed | YES |
| Unknown is final and helpful | YES |
| No registration/acquisition mutation | YES |
| No schema change or migration | YES |
| Previous suites green | YES |
| Native app builds and launches | YES |
| No push | YES |

SPEC-012 is accepted locally. Market intent now owns onboarding, with identity resolution as an internal stage. No push was performed.

**Operations is King.**
