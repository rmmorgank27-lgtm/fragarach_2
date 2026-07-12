# SPEC-009B Acceptance Report

**Specification:** `SPEC-009B_TRUTH_ENGINE_V1`

**Date:** `2026-07-12`

**Acceptance:** `PASS`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Python Acceptance

```text
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: **109 tests passed**.

The four SPEC-009B tests prove deterministic and repeatable TruthState, identical results for identical authority, mandatory explanation, preservation of unknown values, absence of fabricated provider confidence, read-only operation, consumer independence, one state per authoritative lane, and service consumption of range-independent engine output.

All SPEC-009A and earlier tests remain green.

## Native Acceptance

```text
swift build
swift run OperationsCoreChecks
```

Result: **build passed; 12 native checks passed**.

The added native check invokes the compact read-only TruthState command, decodes the complete model, verifies the contract and identity, and confirms explanation components are present. No UI was added.

## Structural Acceptance

| Requirement | Result |
| --- | --- |
| Truth Engine replaces inline scoring | YES |
| One TruthState per authoritative Symbol × Timeframe | YES |
| Authority Service consumes TruthState | YES |
| Existing SPEC-009A tests remain green | YES |
| Previous acceptance tests remain green | YES |
| Native build passes | YES |
| No schema change | YES |
| No migration | YES |
| No push | YES |

## Decision

SPEC-009B is accepted locally. The Truth Engine is now the single deterministic producer of operational confidence. Fragarach II remains a **Candidate Authority**.

**Operations is King.**
