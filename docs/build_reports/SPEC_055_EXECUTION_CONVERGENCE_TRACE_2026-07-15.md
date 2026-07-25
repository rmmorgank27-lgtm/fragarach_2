# SPEC-055 — Execution Convergence Trace and Repair

Date: 2026-07-15  
Authority database: `data/runtime/spec002_real_evidence_acceptance.sqlite3`  
Operational journal: `data/runtime/spec002_real_evidence_acceptance.sqlite3.scheduler.json`

## Outcome

The one-lane live acceptance passed for `AUDUSD:M5`. One stable trace survived two attempts, canonical truth advanced, publication completed, the queue item was removed, and the lane became `CURRENT`.

The mandatory 30-minute Forex observation ran from `2026-07-15T01:53:20Z` through `2026-07-15T02:23:20Z`. It did **not** satisfy estate convergence acceptance. The implementation therefore ends in failure acceptance, not operational success.

## First deterministic stop point

The first failed transition was:

```text
CANONICAL_EDGE_EVALUATED -> CANONICAL_EDGE_ADVANCED
```

Pre-repair evidence for `AUDUSD:M5`:

- expected edge at the baseline was `2026-07-15T01:20:00Z`, while the canonical edge was `2026-07-14T04:05:00Z` (255 closed intervals behind);
- ingest run `a5623f8c1ebf401ab25d518288c4b3eb` committed with `inserted=0` and `unchanged=1`;
- the immutable raw provider response contained one bar at `2026-07-14 00:00:00` because the intraday request used date-only `start_date` and `end_date` values;
- the resulting no-advance path raised an unimported `AcquisitionError`, surfaced as `NameError: TEMPORARY_PROVIDER_FAILURE`, and placed the provider in cooldown;
- immediately before repair, Twelve Data had 20 responses, 18 transient failures, 11 consecutive failures, and an active provider-wide cooldown.

The [Twelve Data API documentation](https://twelvedata.com/docs) permits date-time request bounds. The provider treats a date-only intraday end bound as the start of that date, which matched the captured one-bar response.

The first repaired live attempt then exposed the other half of the same boundary defect. The provider returned 262 `AUDUSD:M5` rows for the New York day, but admission compared their canonical UTC dates with the New York request date. The final 22 rows after the UTC day rollover were rejected, advancing only to `2026-07-15T00:00:00Z`. The queue remained present with `QUEUE_COMPLETION_FAILED`, as required.

## Exact repair

The repair remained at the provider request/admission boundary:

1. Intraday Twelve Data requests now use `T00:00:00` through `T23:59:59`; D1 request semantics are unchanged.
2. Intraday admission compares observations with the provider-local calendar date (`America/New_York` for Forex), not the canonical UTC date.
3. Canonical advancement is measured from the database before and after ingestion. A queue item completes only when the actual edge satisfies its completion target.
4. `CANONICAL_UNCHANGED` and incomplete completion now retain the queue item with an explicit stop reason rather than falsely completing it or converting it into a provider-health failure.

No priority, queue-ordering, provider-authority, credential-authority, commissioning, storage, publication-lineage, or budget policy was redesigned.

## Execution observability

Implemented one stable UUID `trace_id` per queue item and monotonic `attempt_number` values. The identity is retained across scheduler cycles, queue-key changes, retries, provider routing, ingestion, publication, and completion. Legacy deferred queue entries are assigned an identity before they become eligible again.

The operational journal records the 17 required ordered success events and explicit `ATTEMPT_DEFERRED` / `ATTEMPT_FAILED` events with deterministic reason codes. Event persistence uses a field allow-list; credentials, API keys, and arbitrary secret fields are dropped.

Each completed cycle records queue, selection, dispatch, worker, request, canonical, completion, failure, deferral, worker-capacity, provider-budget, oldest-age, duration, next-intended-cycle, and overrun facts. Heartbeats identify `STARTING`, `ACTIVE`, or `COMPLETED` cycle state rather than merely reporting process liveness.

The read-only command is available as:

```text
fragarach-ii execution-trace AUDUSD M5
fragarach-ii execution-trace AUDUSD M5 --json
```

The Scheduler Monitor has a compact Execution section and lane trace field. The Truth Matrix derives `QUEUED`, `DOWNLOADING`, `BEHIND`, and `CURRENT` from queue ownership, active trace/worker state, deterministic deferral, and canonical freshness. It cannot show `DOWNLOADING` without an active trace and worker.

## Live one-lane trace

Trace ID: `701ad8c9-f825-433d-98dc-3f356b1cdf98`

```text
Attempt 1
QUEUE_CREATED -> PRIORITY_CALCULATED -> ELIGIBILITY_EVALUATED -> SELECTED
-> DISPATCH_STARTED -> WORKER_ALLOCATED -> BUDGET_RESERVED
-> PROVIDER_SELECTED -> REQUEST_STARTED -> RESPONSE_RECEIVED
-> RAW_EVIDENCE_STORED -> INGESTION_COMPLETED
-> CANONICAL_EDGE_EVALUATED -> CANONICAL_EDGE_ADVANCED
-> PUBLICATION_COMPLETED -> ATTEMPT_DEFERRED(QUEUE_COMPLETION_FAILED)

canonical: 2026-07-14T04:05:00Z -> 2026-07-15T00:00:00Z
received: 262; admitted: 240

Attempt 2 (same trace ID)
DISPATCH_STARTED -> WORKER_ALLOCATED -> BUDGET_RESERVED
-> PROVIDER_SELECTED -> REQUEST_STARTED -> RESPONSE_RECEIVED
-> RAW_EVIDENCE_STORED -> INGESTION_COMPLETED
-> CANONICAL_EDGE_EVALUATED -> CANONICAL_EDGE_ADVANCED
-> PUBLICATION_COMPLETED -> QUEUE_COMPLETED -> LANE_CURRENT

canonical: 2026-07-15T00:00:00Z -> 2026-07-15T01:50:00Z
final queue disposition: REMOVED
final lane state: CURRENT
```

This used the signed native application and the persistent live scheduler with a real Twelve Data response. The completed item was absent from `acquisition_queue` after `LANE_CURRENT`.

## Thirty-minute Forex convergence

Observation window: `2026-07-15T01:53:20Z` — `2026-07-15T02:23:20Z` (normal Forex session).

| Measurement | Before | After | Change |
|---|---:|---:|---:|
| Commissioned Forex lanes | 50 | 50 | 0 |
| Current Forex lanes | 7 | 10 | +3 |
| Queued Forex lanes | 0 | 0 | 0 |
| Downloading Forex lanes | 1 | 0 | -1 |
| Behind Forex lanes | 42 | 40 | -2 |
| Oldest Forex queue age | 17,299.8 s | 4,925.8 s | -12,374.0 s |
| Forex queue depth | 34 | 33 | -1 |
| Provider requests completed in window | 0 | 29 | +29 |
| Canonical edges advanced in window | 0 | 16 | +16 |
| Queue items completed in window | 0 | 16 | +16 |
| New Forex queue-item traces created | 0 | 59 | +59 |
| Distinct new Forex queue boundary IDs | 0 | 30 | +30 |
| Scheduler cycle overruns | 0 | 16 | +16 |

The positive facts are real: Current increased by three, the oldest age fell sharply, 16 canonical edges advanced, 16 items completed and were removed, live Downloading states were observed, and the rolling provider budget was consumed. The trace recorded 16 successful and 13 failed Twelve Data response completions. Every completed cycle overran, and all 16 overruns reported their duration.

The acceptance gate nevertheless failed:

- 16 completed queue items did not exceed either 59 newly created queue-item traces or 30 distinct new boundary identifiers;
- queue depth improved by only one item because 23 `ATTEMPT_FAILED` removals also made the queue appear smaller;
- repeated HTTP failures caused provider-wide cooldowns for much of the window;
- transiently failed work was later recreated under new trace IDs, so the aggregate stable-retry invariant is not yet satisfied for that path.

Operational verdict: **FAILURE ACCEPTANCE — NOT OPERATIONALLY CONVERGED**.

## Verification

- Focused Python authority/provider suite: `101 passed in 7.73s` (including `6` SPEC-055 tests).
- Native Swift checks: `OperationsCoreChecks: 33 checks passed`, including five SPEC-055 lifecycle assertions.
- Production Swift application build: passed.
- Ad-hoc code-signing and native launch: `Fragarach II signed bundle launched and remained alive`.
- Live `AUDUSD:M5` provider execution: passed with the stable trace shown above.
- Thirty-minute Forex observation: completed; convergence gate failed.

## Deterministic blocker report

First blocked transition during the estate window:

```text
REQUEST_STARTED -> RESPONSE_RECEIVED(success)
reason_code: HTTP_ERROR
provider classification: TEMPORARY_PROVIDER_FAILURE
subsequent state: PROVIDER_COOLDOWN
```

The blocker affected 13 traces across nine Forex lanes:

```text
AUDJPY:D1  27e1fc3f-b11a-404f-b5f8-b9bd878db2af
AUDJPY:D1  3162cac1-da79-4207-8a9e-0a50edbadeb9
AUDNZD:D1  9ae51e88-7a3b-49c3-be54-af7dfdec8074
AUDNZD:D1  11c65ef9-ffc6-4c6e-8872-a550ba5910fc
AUDSGD:D1  22500f0f-fa41-4faf-87d7-86558af0363c
AUDSGD:D1  a0a3f9ed-7ee3-4823-894d-9cddcf67757d
AUDUSD:D1  508e1aa3-3c26-4d8d-96d8-328fece68ce4
EURAUD:D1  59a25991-e25b-473c-b2b0-9b5b01dd6951
EURUSD:D1  945db347-5852-4c7e-9c71-2b51ab6a4233
NZDUSD:D1  c37d4eaf-eb42-4323-bb75-ec4a4c697aab
NZDUSD:D1  4a7b38df-9919-4493-a2ba-a0fd19d38130
USDCHF:D1  d6705306-28e1-483e-90e5-98a77c3385c5
USDJPY:D1  bd337a07-bf61-490f-bf70-e6553e56525a
```

At the cutoff:

- affected Forex lanes: 9;
- oldest active Forex queue age: 4,925.8 seconds;
- active workers: 0 (the final in-window worker completed at `02:23:18Z`); no item was indefinitely active;
- provider state: Twelve Data had recovered to Healthy, cooldown cleared, and rolling budget was `3 used / 52 available`; the window nevertheless contained 13 failed responses and multiple provider-wide cooldowns;
- canonical state: 10 of 50 Forex lanes were Current and 40 remained Behind;
- cycle state: 16 of 16 completed window cycles overran the five-second cadence and reported the overrun.

The repaired `AUDUSD:M5` transition is proven, but SPEC-055 is not complete because live estate work did not complete faster than new work was created. The next investigation should begin at transient-response handling and trace preservation after a retryable provider failure; changing that path was outside the narrow first-transition repair made here.
