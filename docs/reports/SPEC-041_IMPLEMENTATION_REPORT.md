# SPEC-041 Implementation Report

## Result

SPEC-041 is implemented as one integrated scheduled-acquisition and native-monitor feature.

## Delivered

- Calendar-owned exact acquisition boundaries for `M5`, `M30`, `H1`, and `D1`.
- Explicit D1 close schedule facts in approved calendar definitions.
- Core scheduler service with startup catch-up and non-polling waits.
- Missing-edge bounded acquisition through the existing immutable ingest and validation chain.
- Isolated lane failures and persistent operational results.
- Publication-sensitive authority revisions using existing lane-state versions.
- Native Scheduler and Overview health surfaces with live updates.
- Automatic estate refresh after authority publication.
- Primary navigation aligned to Overview, Estate, Scheduler, History, and Manage Data while preserving discovery, operations, and system tools inside Manage Data.

## Constitutional boundary

No canonical table or ingestion doctrine changed. Scheduler events are operational metadata in a sidecar journal. The exact ten-table authority identity remains enforced.

## Verification

- Python unit suite, including `tests/operations/test_spec041_scheduler.py`.
- `swift build`.
- `swift run OperationsCoreChecks` with native scheduler-contract and navigation checks.
- Read-only status proof against the commissioned 74-lane runtime authority.

The runtime status proof returned a valid `fragarach_ii.scheduler_monitor.v1` snapshot for all 74 commissioned lanes and an exact next-run boundary.
