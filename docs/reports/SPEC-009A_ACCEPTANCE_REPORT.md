# SPEC-009A Acceptance Report

**Specification:** `SPEC-009A_OPERATIONAL_AUTHORITY_SERVICE_CONTRACT`

**Date:** `2026-07-12`

**Acceptance:** `PASS`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Acceptance Evidence

### Python

Command:

```text
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: **105 tests passed**.

Four focused SPEC-009A tests prove the complete versioned response, explainable score components, optional range filtering, factual errors, read-only behavior, and unrelated-lane availability.

### Native Application

Commands:

```text
swift build
swift run OperationsCoreChecks
```

Result: **build passed; 11 native checks passed**.

The native checks cover the real ten-table authority schema, bounded read-only queries, authority-ledger decoding, incompatible-database rejection, deterministic filtering, operation review, secret handling, CLI identity, single-operation enforcement, cancellation, and factual malformed-child handling.

## Success Criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| One identical authority contract | YES | Versioned service function and JSON CLI expose one fixed response shape. |
| Availability despite known gaps | YES | Bars are returned with degraded score/state; gaps do not block delivery. |
| CAODT, Truth Score, Validation, Gap Summary | YES | All are mandatory successful-response fields. |
| Consumer independence | YES | Requests accept no consumer identity and responses contain no consumer-specific fields. |
| Unrelated-lane non-blocking | YES | Focused test proves an unknown/degraded request does not alter a valid lane response. |
| Visible uncertainty | YES | Missing validation, unmeasured coverage, and unknown entitlement are explicit. |
| No fabrication | YES | Only persisted bars are served; missing operational facts remain visibly unknown. |
| Native application verified | YES | Swift build and all 11 runtime checks pass. |

## Operational Demonstration

Morphix, Signal Bar, and future HARP engines can invoke the same command or Python service without application-specific behavior. This proves contract independence; it does not add or claim integrations with those consumers.

## Acceptance Decision

SPEC-009A is accepted locally as the minimum operational historical-authority service contract. Fragarach II remains a **Candidate Authority**. No push was performed.

**Operations is King.**
