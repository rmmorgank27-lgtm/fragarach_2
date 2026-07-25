# Performance Phase 2 — Publication & Planning Drag

## Outcome

Canonical admission remains synchronous. After a successful Scheduler lane,
Fragarach now records a durable dirty-lane publication job and returns without
waiting for Estate Truth or the consumer catalogue projection. The background
worker advances the publication revision only after both projections complete.

The publication sidecar is `fragarach_ii.publication_pipeline.v1` beside the
authority database. It carries dirty `(symbol,timeframe)` lanes, derived dirty
symbols, job state, failure detail, and publication revisions. Consumer history
does not report a dirty lane as available while its state is `PUBLISHING` or
`FAILED_RETRYABLE`.

## Publication-path audit

| Trigger | Current path | Blocking behavior | Phase 2 treatment |
| --- | --- | --- | --- |
| Scheduler lane success | `scheduler_service._run_due_acquisitions_unlocked` | Canonical admission is synchronous; Estate/catalogue rebuild is no longer on the worker path | Mark dirty lane and enqueue one background publication job per Scheduler cycle. |
| Manual Fetch Now success | `run_operator_fetch` → Scheduler executor | Same canonical path as Scheduler work | Receives the same dirty-lane job. |
| Fetch Required Set | `run_required_set_fetch` | Previously evaluated each lane independently | Defers per-wave publication and enqueues successful lanes once at the grouped-job boundary. |
| Manual CSV import | ingestion pipeline / direct authority readers | Canonical write is durable; Estate is demand-projected | No new synchronous rebuild was found in the import writer. A later worker trigger can enqueue an explicit import publication job. |
| Commissioning/registration/onboarding | lane/registration authority functions | State is canonical immediately; Estate remains demand-projected | Required Set batches its post-evidence commissioning into the grouped publication job. Direct registration remains a documented future hook. |

## Sync and async boundary

```text
provider/import evidence
→ canonical SQLite admission (sync, durable)
→ lane status / dirty marker (sync, durable)
→ publication job enqueue (sync, short)
→ Estate Truth + external catalogue projection (async)
→ PUBLISHED revision or FAILED_RETRYABLE
```

Canonical evidence is never rolled back when publication fails. The lane stays
non-consumer-visible until a successful publication revision. This keeps the
consumer authority boundary stricter than canonical storage.

## Planning cache

`cached_acquisition_capability_projection` uses a process-local cache keyed by:

- canonical database modification revision;
- provider-facts revision (including mapping changes);
- a one-way credential revision fingerprint;
- provider-profile configuration;
- provider/budget state; and
- requested symbol, timeframe, and range.

Cached values are deep-copied. Any canonical mutation, provider mapping update,
credential change, provider-state/budget update, or request-scope change yields
a new key. Scheduler monitor and Estate Truth use this wrapper for their broad
capability matrices.

## Monitor guard

Routine Scheduler snapshots now report `monitor_guard` with payload bytes and
generation time. The guard targets less than 2 MB and trims only monitor copies
of historical attempt/capability detail if needed; the journal and canonical
authority data remain unchanged.

## Timing evidence

Publication enqueue timing is appended to the existing operation timing journal
with trigger, changed lanes/symbols, prior publication revision, and sync
blocking time. The background job records its async duration and revision in
the publication sidecar. The focused delay test proves a 400 ms publisher is
enqueued in under 150 ms and completes later at revision 1.

## Files changed

- `src/fragarach_ii/publication_service.py`
- `src/fragarach_ii/authority_cache.py`
- `src/fragarach_ii/scheduler_service.py`
- `src/fragarach_ii/acquisition_orchestrator.py`
- `src/fragarach_ii/estate_truth_service.py`
- `src/fragarach_ii/external_consumer_service.py`
- `src/fragarach_ii/execution_trace.py`
- `tests/operations/test_perf_phase2_publication_planning.py`

## Test result

Focused Phase 2 tests passed (`4 passed`). Combined Phase 1/Phase 2 scheduler,
Required Set, provider-budget, Estate, and consumer regression selection passed
(`43 passed`). No live provider run was performed because it requires an
operator-selected credential and would spend provider quota.

## Remaining bottlenecks and Phase 3

- Estate Truth and consumer catalogue are still full projections inside the
  asynchronous publisher; their dirty-lane input makes incremental replacement
  possible without changing canonical authority.
- Direct registration/onboarding and manual-import flows should become explicit
  publication-job producers in Phase 3.
- SQLite canonical admission is intentionally serialized.

Phase 3 should implement incremental Estate/catalogue materialization from the
dirty-lane set, then add retry/control visibility for failed publication jobs.
