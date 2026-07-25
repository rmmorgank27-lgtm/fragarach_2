# SPEC-046 Implementation and Acceptance Report

## Result

SPEC-046 is implemented. Scheduler state is now projected from the canonical active Estate, provider accounting distinguishes reserved capacity from calls actually dispatched, classified waits replace generic cooldowns, acquisition can be paused safely, manual publication is gated on quiescence, exception counts drill into their exact records, and Estate keeps the application navigation usable at desktop and narrow widths.

## Delivered

- Added active-universe reconciliation from canonical registration, commissioning, and retirement authority. Reconciliation runs during scheduler snapshot, execution, retry, resume, retirement, reactivation, and manual-request refresh paths.
- Removed retired, superseded, inactive, and uncommissioned lanes from actionable queue, retry, pause, and manual-request state while retaining immutable, non-actionable operational history.
- Made `INCORRECT_INSTRUMENT_IDENTITY` a non-reactivatable tombstone. The operator is directed to register the correct instrument separately; existing evidence is never reassigned or deleted.
- Added persisted request lifecycle states for planned, reserved, dispatched, response-received, failed-before-dispatch, failed-after-dispatch, and cancelled work.
- Separated budget reservations from actual dispatched-call accounting. Undispatched capacity is released on cancellation and recovered after restart; dispatched calls remain in rolling usage.
- Replaced ambiguous provider cooldown presentation with controlled wait states and structured cause, scope, triggering request/response, start, expiry, and recovery fields.
- Required remote-rate-limit evidence before showing `Remote Rate Limited`. Local capacity, authentication, entitlement, lane failures, and transient provider backoff retain their own truthful scopes.
- Added persisted acquisition pauses for all acquisition, controlled Estate market/group, and symbol scope. The effective pause is the union of applicable records, so resuming a narrow pause cannot override a broader one.
- Added active-work draining: already-dispatched requests may finish, new dispatch is prevented, and the pause becomes fully effective only when matching work is quiescent.
- Added pause enforcement to automatic execution, `Retry Now`, and `Run Queue Now`, including a final journal reread immediately before network dispatch.
- Added a temporary scheduled-acquisition hold to Acquire & Import. Canonical commit remains unavailable until the selected scope is quiescent; successful publication resumes or retains the hold according to the operator choice and recomputes scheduler work from current authority.
- Added exact, interactive Scheduler drilldowns for all summary cards. Manual Required reports requests, unique lanes, and unique symbols separately and exposes age, cause, provider attempts, request lifecycle, commissioning, pause, latest failure, and cross-navigation actions.
- Added structured Unavailable diagnostics for calendar, timezone, session-close, calculation time, and exact failure detail instead of reducing all unavailable work to one generic bucket.
- Reworked Estate to use the native inspector pattern. Desktop layout preserves primary sidebar, Estate content, and inspector; at narrow widths the inspector collapses/overlays and navigation retains its compact selected rail.
- Added monitor-only app scheduling for signed acceptance so the native monitor can exercise the live contract without dispatching provider requests. Relaunch cleanup is scoped to stale scheduler processes from this repository.

## Authority and Persistence Boundaries

- Canonical market-data authority remains the sole source of active Estate membership.
- Reconciliation archives operational records; it does not delete canonical observations, raw payloads, provenance, or tombstones.
- Pause records and request lifecycle state remain operational journal data. A pause does not alter authority revision, freshness, commissioning, retirement, or manual-request resolution.
- Scheduler journal writes continue to use cross-process locking and merge independently changed pause controls.
- No Evidence Discovery capability or SignalBar/MorphixFC doctrine was added or changed.

## Automated Verification

- `PYTHONPATH=src python3 -m pytest -q`
  - 236 passed, 2 subtests passed.
- `swift build`
  - Passed.
- `swift run OperationsCoreChecks`
  - 28 checks passed.
- SPEC-046 tests cover incorrect-identity reconciliation and evidence immutability, reservation-versus-dispatch accounting, cooldown proof and scope, pause hierarchy and restart persistence, active-work drain, and prevention of dispatch for a paused symbol.

## Live Authority Acceptance — 2026-07-14

- Reconciled the live scheduler journal against `spec002_real_evidence_acceptance.sqlite3`.
- JPYCHF remained `RETIRED_INCORRECT_IDENTITY` with reason `INCORRECT_INSTRUMENT_IDENTITY` and was absent from active lanes, queue, retry, and Manual Required.
- Its obsolete manual request and lane-control record were retained as two non-actionable archived records under the incorrect-identity reason.
- All nine JPYCHF canonical bars and all nine linked raw/provenance records remained intact.
- The canonical database remained exactly ten non-SQLite tables; `PRAGMA integrity_check` returned `ok` and `PRAGMA foreign_key_check` returned no findings.
- Manual Required displayed an exact identity of 37 requests, 37 unique lanes, and 15 unique symbols, with the same records present in the drilldown.
- Unavailable displayed four commissioned lanes with structured `CALENDAR_UNAVAILABLE` diagnostics and actionable navigation.

## Signed Native Acceptance

- Built, strictly code-signed, launched, and kept the production bundle alive with the live scheduler contract in monitor-only mode.
- Confirmed Scheduler excludes JPYCHF from actionable work and exposes clickable Manual Required and Unavailable detail records.
- Confirmed Estate at normal width renders `Primary Sidebar | Estate Content | Estate Inspector`.
- Confirmed Estate at narrow width keeps usable Estate content and compact primary navigation while the inspector yields layout priority.
- Confirmed the app-owned scheduler process was a child of the signed application during the journey; a normal quit left no application or scheduler process behind.

## Completion

Scheduler work can no longer outlive canonical Estate eligibility, accounting reflects actual provider dispatch, classified waits are externally explainable, pause and manual-publication controls are race-safe, exception counts identify their exact records, and Estate no longer sacrifices application navigation to its inspector.
