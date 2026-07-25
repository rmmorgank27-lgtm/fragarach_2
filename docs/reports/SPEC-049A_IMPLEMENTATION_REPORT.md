# SPEC-049A Implementation Report

## Outcome

Scheduler service lifecycle mutations now use an inspectable, persisted, user-private mutation ledger and a dedicated file-lock domain. Acquisition ownership remains an independent lock and is never cleared by lifecycle repair or reconciliation.

## Implemented

- Added explicit records for Install, Start, Stop, Restart, Update, Repair, Enable, Disable, Uninstall, and Force Reconcile, including owner, stage, progress, timeout, failure, cancellation, and target-generation fields.
- Added atomic mutation persistence under the authority-specific Scheduler support directory, bounded stage timeouts, terminal timeout/failure handling, operation history, and safe cancellation requests.
- Added pre-mutation and status-time stale reconciliation with active, externally completed, timed-out, failed, abandoned, and stale-cleared outcomes.
- Added live-owner/broken-monitor protection so Start never launches a second Scheduler when acquisition ownership remains active.
- Removed acquisition-ownership metadata deletion from Repair.
- Extended service status and lifecycle acknowledgements with mutation and recommended-action fields while retaining backward Swift decoding.
- Added Force Reconcile, diagnostics, cancellation, and explicit mutation-reconciliation CLI modes.
- Raised the bounded monitor transport ceiling to 8 MiB and isolated disconnected clients so a large status response or `BrokenPipeError` cannot terminate the command-server thread.
- Separated native status polling from lifecycle execution so a long mutation cannot turn monitor polling into the generic mutation-lock error.
- Replaced the native unavailable dead end with active, failed/timed-out, abandoned, and reconciled service states; added operation detail and credential-free diagnostics sheets with copy support.

## Verification

- `PYTHONPATH=src python3 -m pytest -q`: 269 passed, 2 subtests passed.
- Focused SPEC-049/049A lifecycle tests: 13 passed.
- `FOCUSED_SPEC049A=1 swift run OperationsCoreChecks`: passed.
- `swift build`: passed (debug).
- `swift build -c release`: passed.
- Detached service journey: live monitor attached with one acquisition owner; controlled Stop completed; detached status reconstruction reported no live owner and a completed mutation.
- Canonical safety test: database hash unchanged, integrity `ok`, and exactly ten application tables after timeout recovery.

Production signing remains a separate SPEC-049 prerequisite and was not changed by this amendment.
