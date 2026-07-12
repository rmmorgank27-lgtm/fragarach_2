# SPEC-013 Implementation Report

Date: 2026-07-12

## Implemented

- Deterministic read-only retirement impact planning.
- Whole-instrument and selected-lane scopes.
- Controlled reason validation and required notes for `OTHER_REVIEWED_REASON`.
- Typed confirmation for acquired evidence.
- Immutable registration and lane supersession events with deterministic retirement receipt.
- Binding declarations for post-bootstrap registrations before supersession.
- Idempotent identical retirement.
- Acquisition guard returning `INSTRUMENT_RETIRED` before provider activity.
- Manual ingestion registration guard for retired lanes.
- Active Truth, Estate Truth, and native lane filters based on immutable lifecycle projection.
- Discovery historical-retired presentation with no normal Open/Add/Acquire action.
- Native impact review, reason selection, typed confirmation, success receipt, and retired state.
- Acquire UI retirement warning/disablement from ledger state.

## Preservation

No deletion or rewrite path was added. Registration, lane, raw evidence, acquisition runs, provenance, canonical bars, validation history, and prior Truth inputs remain physically intact and available for audit.

## Verification

- Python regression suite: 137 tests passed.
- Native OperationsCore checks: 15 passed.
- Swift build and signed native launch passed.
- Isolated acquisition-race fixture made zero provider requests after retirement.
- No schema or migration changed.
- No push performed.
