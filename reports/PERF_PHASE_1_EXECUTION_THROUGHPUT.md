# Performance Phase 1 — Execution Throughput Core

## Outcome

Scheduler lane execution now permits bounded, provider-safe overlap. The
shared Scheduler state mutex still protects journal, queue, trace, and status
mutation, but it is released before provider dispatch and reacquired only for
the post-acquisition status/canonical-edge projection. A lane guard prevents a
second worker in the same Scheduler process from writing the same
`(symbol,timeframe)` lane.

Required Set submits executable lanes first and dispatches them in bounded
two-lane waves. Blocked lanes are not submitted and do not hold up executable
lanes; each lane is commissioned only after canonical evidence is visible.

## Lock-boundary audit

| Boundary | Classification | Phase 1 treatment |
| --- | --- | --- |
| `run_due_acquisitions` acquisition-file lock | Scheduler/executor authority | Retained to prevent competing Scheduler processes from mutating the same queue. |
| `state_lock` before provider dispatch | Queue selection, reservation, lane Running status, journal/trace mutation | Retained and short. |
| `_execute_acquisition` provider call and response parsing | Provider/network wait and candidate preparation | Outside `state_lock`; different lanes may overlap. |
| Per-provider semaphore | Provider execution admission | New bounded gate using each provider profile's `concurrency_limit`. |
| `_ACTIVE_LANE_GUARDS` | Per-lane writer exclusion | New `(database,symbol,timeframe)` guard; duplicate worker attachment is skipped. |
| Twelve Data credit authority lock/file state | Provider-credit reservation, dispatch, settlement | Retained. Reservation is atomic; existing release paths settle unused/failing reservations. |
| `registered_writer` SQLite transaction | Canonical admission/write | Retained as the canonical write authority. |
| `SchedulerJournal.save` lock | Status/publication/trace snapshot mutation | Retained; it never wraps provider network time. |
| `scheduler_snapshot` / Estate projection | Publication/status update | Runs after the bounded cycle rather than inside each provider wait. |

## Concurrency limits

- Required Set: two executable lanes per wave.
- Scheduler: bounded by the highest configured worker limit, with each
  provider additionally constrained by its own `concurrency_limit`.
- Twelve Data: its central atomic credit authority remains the hard authority
  for the 55-credit plan / 50-credit operational minute limit and resets at
  the next minute window. It is independent of other providers.
- Same lane: one active worker per `(symbol,timeframe)`; same-symbol different
  timeframes remain eligible to run together when their provider limits allow.

## Timing evidence

`fragarach_ii.operation_timing.v1` lane records now include queue, provider,
canonical-commit, completion, lock-wait, reservation-wait, worker, and duration
boundaries. The focused fake-provider proof uses four 350 ms lane calls with a
Required Set limit of two. It observed a peak of two active provider calls and
completed in under 1.2 seconds (two waves), rather than the approximately
1.4-second serial provider time.

The timing record intentionally remains redacted: it contains no provider
credentials, request URL, headers, or response payload.

## Files changed

- `src/fragarach_ii/scheduler_service.py`
- `src/fragarach_ii/execution_trace.py`
- `tests/operations/test_perf_phase1_execution_throughput.py`
- `reports/PERF_PHASE_1_EXECUTION_THROUGHPUT.md`

## Verification

Focused execution, Required Set, and Twelve Data throughput tests passed:

```text
21 passed in 4.41s
```

`swift build -c release --product FragarachII` and
`./script/build_and_run.sh --verify` also passed. The broader
`PYTHONPATH=src python3 -m pytest tests/operations -q` run was attempted but
is currently blocked by the pre-existing market-registry regression
`test_registration_command_migrates_v6_and_accepts_unmapped_fx`: its CLI
registration command returns exit code 1 where the test expects 0. That path
does not exercise Scheduler execution or the changed throughput code.

The real provider/scheduler ten-minute acceptance run was not performed in
this implementation pass: it would consume live provider quota and needs an
operator-selected populated lane/credential. The new lane timing records are
the evidence surface for that run.

## Remaining bottlenecks

- SQLite canonical writes remain intentionally serialized by `registered_writer`.
- The Scheduler acquisition-file lock still gives one process ownership of a
  queue/journal; this is deliberate process-level authority, not a provider-I/O
  lock.
- Estate snapshot construction still occurs after a completed Scheduler cycle.

Phase 2 should target Estate publication first: provider I/O is now overlap-capable,
while publication and SQLite admission are the next observable end-of-cycle costs.
