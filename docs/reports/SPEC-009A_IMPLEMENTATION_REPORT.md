# SPEC-009A Implementation Report

**Specification:** `SPEC-009A_OPERATIONAL_AUTHORITY_SERVICE_CONTRACT`

**Date:** `2026-07-12`

**Result:** `IMPLEMENTED`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Delivered

`fragarach_ii.authority_service` now assembles the Version 1 operational authority contract through the established read-only database boundary. `fragarach_ii.commands.serve_authority` exposes that contract as deterministic structured JSON.

The request contains only symbol, timeframe, and optional inclusive epoch-second range boundaries. Canonical symbols and registered aliases are supported. No consumer identity is accepted.

Every successful response contains:

* historical bars;
* CAODT derived from the latest returned canonical bar;
* GREEN, AMBER, or RED authority state;
* PASS, WARNING, or LIMITED validation state;
* an explainable 0–100 Truth Score with Authority, Freshness, Validation, and Coverage components;
* informational current, recent, historical, total, impact, and limitation gap fields;
* provider identity, freshness, confidence, and explicit entitlement state;
* row count, earliest/latest bar, symbol, timeframe, authority version, and provenance reference count.

Unknown validation or provider entitlement is reported as `NO_PERSISTED_VALIDATION_SUMMARY`, `NOT_MEASURED`, or `NOT_RECORDED`. The service does not infer or fabricate those facts. Missing validation and known gaps degrade confidence but do not suppress usable bars.

## Scoring Contract

Truth Score is the rounded equal-weight mean of four independently visible component scores:

* Authority: registration evidence state;
* Freshness: persisted confirmation of the latest expected session;
* Validation: persisted gap/outside-session findings;
* Coverage: present expected sessions divided by expected sessions.

Authority state thresholds are GREEN at 80 or above, AMBER at 50–79, and RED below 50. The inputs and basis strings are returned with every score; no black-box input exists.

## Native Check Harness Correction

The native check fixture already contained six bootstrap authority events. Its temporary-copy setup unconditionally ran bootstrap again, producing twelve events when authority-document checksums had changed. The check harness now bootstraps only when the copied ledger is empty. No stored evidence, production ledger behavior, or native read path was changed.

## Files

* `specs/operations/SPEC-009A_OPERATIONAL_AUTHORITY_SERVICE_CONTRACT.md`
* `src/fragarach_ii/authority_service.py`
* `src/fragarach_ii/commands/serve_authority.py`
* `tests/operations/test_authority_service.py`
* `Sources/OperationsCoreChecks/main.swift`

**Operations is King.**
