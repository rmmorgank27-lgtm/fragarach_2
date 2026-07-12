# SPEC-009A Preflight Report

**Specification:** `SPEC-009A_OPERATIONAL_AUTHORITY_SERVICE_CONTRACT`

**Date:** `2026-07-12`

**Result:** `PASS — IMPLEMENTATION AUTHORISED`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Decision

SPEC-009A can be implemented as a read-only service layer over the existing ten-table authority. No schema migration, new table, evidence mutation, constitutional amendment, provider call, or consumer-specific integration is required.

The existing authority supplies the commissioned inputs:

* canonical bars from `bars`;
* symbol and provider identity from `instrument_registrations`;
* declared lane identity from `evidence_lanes`;
* persisted factual validation from `lane_state.validation_summary`;
* provenance reference counts from `provenance`.

## Compatibility Boundaries

The implementation must:

* open the database through the established read-only/query-only connection;
* return one versioned response shape for every consumer;
* expose absent validation and entitlement as explicit limitations;
* calculate V1 Truth Score only from Authority, Freshness, Validation, and Coverage;
* continue serving bars when validation or gaps degrade confidence;
* reject only invalid requests, unknown/undeclared lanes, or ranges containing no authority;
* leave all ten application tables and six migration checksums unchanged.

## Exclusions Confirmed

No Truth Console, heat map, Balanced Scorecard, epoch scoring, maintenance automation, snapshot system, backup automation, gap repair, archive engine, forecasting, research, market analysis, trading logic, or consumer-specific behavior is authorised by this phase.

## Preflight Conclusion

The affected path is compatible. Implementation may proceed within the existing service and command boundaries. **Operations is King.**
