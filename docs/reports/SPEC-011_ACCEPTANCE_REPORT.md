# SPEC-011 Acceptance Report

**Specification:** `SPEC-011_INSTRUMENT_IDENTITY_RESOLUTION_ENGINE`

**Date:** `2026-07-12`

**Acceptance:** `PASS`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Python Acceptance

```text
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: **119 tests passed**.

Five focused tests prove repeatability, deterministic confidence, alias and ISO currency-pair resolution, commodity/company/index/crypto metadata, ambiguous BHP identities, helpful unknown responses, registered Truth context, and byte-for-byte read-only operation.

All previous acceptance tests remain green.

## Native Acceptance

```text
swift build
swift run OperationsCoreChecks
```

Result: **build passed; 14 native checks passed**.

The added native check invokes BHP resolution through the provider-free bridge, decodes the result, and verifies deterministic ASX:BHP/NYSE:BHP ambiguity.

## Bundle Acceptance

```text
./script/build_and_run.sh --verify
```

Result: **signed SwiftPM application bundle rebuilt, launched, and running process verified**.

## Acceptance Matrix

| Requirement | Result |
| --- | --- |
| Common instrument names resolve | YES |
| No provider lookup required | YES |
| Aliases and confidence displayed | YES |
| Ambiguous identities selectable | YES |
| Unknown identities provide guidance | YES |
| Existing registrations recognized | YES |
| Preliminary metadata generated | YES |
| No authority fabricated | YES |
| No provider dependency | YES |
| No schema change or migration | YES |
| Existing suites green | YES |
| Native application builds and launches | YES |
| No push | YES |

SPEC-011 is accepted locally. Identity now precedes provider discovery. No push was performed.

**Operations is King.**
