# SPEC-049B Implementation Report

## Outcome

Unresolved manual acquisition requests are now reconciled by the Scheduler against current Estate, canonical, provider-fact, capability, credential, entitlement, budget, cooldown, and pause authority. A manual fallback created under stale facts is archived when automation becomes eligible, and one recalculated `QUEUE` item is restored per lane without deleting its original request history.

## Implemented

- Added monotonic provider-fact and capability-projection revisions under an atomic provider-facts file lock.
- Added manual-request creation and evaluation snapshots, original provider/rejection preservation, controlled outcomes, current reasons, reconciliation timestamps, and replacement queue identifiers.
- Added Scheduler-owned reconciliation during snapshot refresh, dispatch, startup/recovery, `Run Queue Now`, `Retry Now`, provider-fact commits, and five-second external-writer polling.
- Added current canonical-bound recalculation, already-satisfied resolution, inactive/uncommissioned archival, temporary operational states, provider-attempt exhaustion protection, queue deduplication, and migration totals.
- Added generation-aware journal merging so newer manual reconciliation and restored queue state survive concurrent service saves.
- Added native current-fact drilldowns, provider-fact revision display, automation-restored events, and inspectable archived manual-request creation history.
- Added focused AUDNZD M5/M30/H1/D1, credential-repair, already-satisfied, canonical-safety, history, and restart-idempotence tests.

## Verification

- Full Python suite: `273 passed, 2 subtests passed`.
- Focused scheduler/provider/manual reconciliation suite: `64 passed`.
- Native contract checks: `32 checks passed`.
- Swift debug build: passed.
- Swift release build: passed.
- Current local ad-hoc-signed `.app` bundle: code-signature verification passed; `./script/build_and_run.sh --verify` launched the bundle and confirmed the process remained alive.
- AUDNZD acceptance fixture: four stale requests archived, four deduplicated `QUEUE` lanes restored through current Twelve Data `AUD/NZD` exact-representation facts, no canonical database byte changes from reconciliation, and no requests returned to `Manual Required` after restart reconciliation.
- Canonical authority remains ten tables; reconciliation writes only operational sidecars and normal successful ingestion remains the only observation-publication path.
