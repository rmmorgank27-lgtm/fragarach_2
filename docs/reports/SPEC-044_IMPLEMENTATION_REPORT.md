# SPEC-044 Implementation and Acceptance Report

## Result

SPEC-044 is implemented. The scheduler now drains every currently actionable lane on each event-driven wake, applies queue bandwidth independently to each provider, protects normal scheduled demand, and persists retry, budget, queue, and recovery state without changing canonical authority.

## Delivered

- Added the `NORMAL`, `QUEUE`, and `OPERATOR_RETRY` work classes. Newly due normal work preempts retry and backlog work; queue fairness rotates D1, H1, M30, and M5 work after retry priority so an M5 backlog cannot starve larger timeframes.
- Replaced bounded one-task startup processing with a continuous drain. Startup, scheduled boundaries, task completion/failure, exact budget/cooldown release, Retry Now, Run Queue Now, and bandwidth increases all wake the same dispatcher. The service waits on the exact next event and does not poll.
- Extended the rolling budget controller with atomic multi-unit reservations, persisted work-class attribution, deterministic `floor(capacity × percentage)` queue ceilings, protected scheduled demand, provider safety reserves, and exact release times.
- Applied the approved Twelve Data contract of 55 requests per rolling 60 seconds. At the default 80% setting the queue ceiling is 44 and protected capacity is 11. Queue percentages are limited to 10–90%.
- Added explicit provider budget units, policy verification, concurrency limits, safety reserves, active-request reporting, and independent provider state. Twelve Data is verified; Yahoo Finance, Binance, and CoinGecko are visibly labelled `Rate Policy Unverified` and remain conservatively bounded.
- Added persistent Queue Bandwidth control, per-lane and per-manual-request Retry Now, manual Acknowledge/Dismiss/Open Manage Data, and Scheduler toolbar/content Run Queue Now.
- Retry rereads freshness at dispatch, removes already-satisfied work, rebuilds missing bounds and routing, clears a prior attempt cycle only for an explicit retry, and remains deduplicated under repeated presses.
- Added operational queue states: Ready, Running, Waiting for Budget, Cooling Down, Blocked, and Manual Required, with provider and exact-time wait detail rather than a generic Queued label.
- Added global queue metrics and provider capacity monitoring, including the clearly labelled estimated clear time.
- Added restart recovery for interrupted work and stable catch-up identity based on the expected canonical edge. Completed or attempted boundaries are not reconstructed merely because the application restarts.
- Added cross-process journal locking and control merging so slider/retry/run-queue changes made while acquisition is active are not overwritten by a stale scheduler save.
- Fixed the native process cancellation launch race encountered during verification.

## Authority Boundaries

- The canonical database remains exactly ten tables.
- Provider results still publish only through existing immutable staging, validation, ingestion, and canonical publication paths.
- No provider mapping, operational calendar, freshness doctrine, lane commissioning, SignalBar, MorphixFC, or Evidence Discovery behavior was added or changed.
- Queue acceleration and retry remain operational controls and cannot bypass credentials, entitlements, mappings, timeframes, cooldown, rate budgets, validation, or canonical publication.

## Automated Verification

- `PYTHONPATH=src python3 -m pytest -q tests/operations/test_spec044_queue_drain.py tests/operations/test_spec041_scheduler.py tests/operations/test_spec042_orchestrator.py tests/providers`
  - 46 passed.
  - Covers 44/11 queue protection, request 56 release, atomic multi-request reservation, slider bounds/persistence/wake behavior, normal priority, M5 demand forecasting, timeframe rotation, retry deduplication, Run Queue re-evaluation, stable catch-up identity, recovery, provider failover, and failure isolation.
- `swift run OperationsCoreChecks`
  - 28 checks passed, including version 1/2 scheduler monitor recovery decoding and process cancellation.
- Full Python suite
  - 217 passed, 2 subtests passed, 1 pre-existing stale assertion failed: `test_registration_command_migrates_v6_and_accepts_unmapped_fx` expects migration 7 although the repository's current default is migration 8 from SPEC-025.
- `swift build -c release`
  - Passed.
- Canonical verification
  - `PRAGMA integrity_check`: `ok`.
  - `PRAGMA foreign_key_check`: no findings.
  - Canonical table count: exactly 10.

## Signed Live Acceptance — 2026-07-14

- Built an ad-hoc signed release bundle, passed strict code-signature verification, launched the normal scheduler-enabled application, and visually inspected the native Scheduler.
- The Scheduler showed the persistent 80% slider, Run Queue Now, all queue metrics, exact operational states, and the expanded provider monitor.
- The current backlog loaded with 51 unique items. Native Run Queue Now updated the persisted control generation and woke dispatch immediately.
- Multiple lanes executed in the same signed session. The queue fell from 51 while failed and cooling lanes remained isolated.
- Successful immutable publications included MSFT D1, BTCUSD M5, SOLUSD M5, SOLUSD M30, and SOLUSD H1. BTCUSD M5 published 83 observations; SOLUSD lanes published 85, 15, and 8 observations respectively.
- Twelve Data rolling events remained below 55 and queue events below 44. The live monitor retained 11 protected requests at 80%. Yahoo Finance and Binance used independent budgets while Twelve Data was cooling down.
- One-provider failures did not stop other lanes. Exact cooldown detail was displayed, for example `Waiting for provider cooldown: TWELVE_DATA until 2026-07-14T05:51:07.942201+00:00`.
- Retry Now on AUDUSD M5 returned `RETRY_QUEUED`; a second press returned `RETRY_ALREADY_QUEUED`. The retry was reconstructed as one `OPERATOR_RETRY` item and correctly remained Cooling Down rather than bypassing provider controls.
- A normal quit left no scheduler process. Restart loaded 33/33 unique unfinished items with zero new identifiers and no repeated dispatch; blocked work remained blocked until its exact wake.

## Completion

Fragarach continuously uses the operator-selected safe share of each provider's capacity to clear actionable work, while preserving normal scheduled capacity and every canonical authority boundary. Evidence Discovery was not started.
