# SPEC-062 — Authority & Throughput Audit

Audit date: 2026-07-18. Scope: source review plus deterministic fixture runs.
No authority rule was weakened and no live provider request was sent.

## Outcome

Fragarach is locally over-governed on the acquisition critical path. Provider
latency may still dominate a live request, but repeated planning, journal
rewrites, snapshot projection, and authority reads add material local work.

The two decisive structural findings are:

1. `run_required_set_fetch()` is a serial convenience wrapper. It loops D1,
   H1, M30 and M5, calling the complete `run_operator_fetch()` path for each.
   It does not batch planning, facts, reservations, or publication.
2. `_run_due_acquisitions_unlocked()` creates a `ThreadPoolExecutor`, but
   `guarded_execute()` holds `state_lock` around the complete
   `execute_selected_work()` operation. That includes provider I/O and ingest,
   so selected lanes are effectively serialized.

This makes the operator's one-to-five-minute observation plausible even without
a provider outage. A lane can wait behind unrelated provider work, then trigger
more local projections before it returns.

## Evidence status

The checked-in `data/fragarach_ii.sqlite` was a zero-byte placeholder and no
live credential/approved measurement database was supplied. This audit does
not invent live provider numbers.

| Fixture scenario | Result | Wall time | Meaning |
| --- | --- | ---: | --- |
| GBPAUD Required Set, canonical evidence fixture | pass | 0.67 s | Local-only four-lane commissioning path; no network wait. |
| Crypto Required Set, canonical evidence fixture | pass | 0.55 s | Local-only grouped path. |
| GBPAUD partial Required Set resume | pass | 0.75 s | Full job re-plans/revisits state while avoiding completed fetches. |
| Scheduler single-lane trace | pass | 0.12–0.21 s | Captures new planning/provider/lane/cycle spans. |
| Manual CSV fixtures | pass | 0.02–0.03 s | Local parsing/admission baseline. |
| Persistent scheduler service fixture | pass | 0.59 s | Socket/process lifecycle test, not a throughput benchmark. |

Live captures still required: GBPAUD H1, ETHUSD H1 or Required Set, JPM D1 CSV
attempt, idle/load scheduler cycle, Estate Truth refresh, and catalogue build.

## A. Authority pipeline map

### Symbol onboarding

| Step | Owner | Inputs → outputs | Blocking | Safety critical | Cost | Cache/batch/defer? | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Discover | `market_discovery.py:discover_market` | query → candidates/plan | Yes | Yes | local catalogue, optional provider search | cache short-lived discovery | Preserve identity decision. |
| Provider identity resolution | `providers/instrument_search.py`, `providers/resolution.py` | candidate → representation | Yes | Yes | provider call | batch by provider | Resolve once per selected representation. |
| Mapping approval | `provider_facts.py:approve_reviewed_provider_mapping` | selection → approved mapping | Yes | Yes | facts write/readback | do not repeat in operation | Keep human approval. |
| Atomic registration | `onboarding.py:register_provider_aware_instrument` | candidate/mapping → registration | Yes | Yes | SQLite + readback | combine readback queries | Keep atomicity. |
| Capability projection | `acquisition_orchestrator.py:acquisition_capability_projection` | facts/profile/credential → routes | Yes for fetch | Yes | SQLite/config/facts | memoize by facts revision | Build once for all required lanes. |
| Initial evidence/commissioning | `run_operator_fetch`, `ensure_commissioned_lane` | route → canonical evidence → commissioned lane | Yes | Yes | provider + ingest | defer display only | Evidence-before-commissioning is correct. |
| Estate/catalogue projection | `estate_truth_state`, `HistoryService.get_catalogue` | authority → read model | Should be no | No | broad SQLite work | revision cache, async | Move off registration/fetch completion. |

### Manual acquisition / Fetch Now

| Step | Owner | Inputs → outputs | Blocking | Safety critical | Cost | Cache/batch/defer? | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Reconcile and pause check | `scheduler_service.py:run_operator_fetch` | request → active authority | Yes | Yes | journal/universe projection | once per job | Keep; return a structured gate. |
| Freshness/revision | `freshness.py`, `authority_revision_for_lane` | lane → edge/state/revision | Yes | Yes | SQLite reads | one lane snapshot | Reuse for bounds and response comparison. |
| Bounds/history depth | `_acquisition_bounds`, `history_depth.py` | edge/intent → range | Yes | Yes | calendar/SQLite | plan-local cache | Calculate once per lane. |
| Capability/credential | capability projection, `credential_map` | context → routing | Yes | Yes | facts/config reads | job context | Do not reload for each fallback/lane. |
| Queue and dispatch | `run_due_acquisitions` | operation → work item | Caller waits | No | journal/lock | enqueue set together | Do not call a full cycle per lane. |
| Plan/reservation | `acquisition_plan`, budget authority | lane → provider/reservation | Yes | Yes | local planning | provider/symbol grouping | Reserve exact grouped demand. |
| Provider execution | `providers/orchestrated.py` | request → staged evidence | Yes | Yes | provider wait | bounded parallelism | This should dominate live wait. |
| Canonical admission | `ingestion/pipeline.py:ingest_staged_batch` | staged evidence → canonical state | Yes | Yes | writer transaction | writer stays serial | Retain. |
| Publication/status | scheduler publication + `scheduler_snapshot` | commit → UI/read model | Currently yes | event yes; snapshot no | repeated snapshot/journal | async revisioned projection | Commit event synchronously; project later. |

### Required Set acquisition

| Step | Owner | Blocking | Finding | Recommendation |
| --- | --- | --- | --- | --- |
| Doctrine lane plan | `required_set_acquisition_plan` | per-lane eligibility | computes each lane independently | shared provider/facts/credential/budget context. |
| Pre-loop commissioning | `run_required_set_fetch` | no | invokes `_commission_lane_after_evidence` per lane | report state only before fetch. |
| Per-lane Fetch Now | Required Set loop → `run_operator_fetch` | yes | **strict serial loop**, each runs a complete scheduler cycle | enqueue all executable lanes then bounded batch. |
| Post-evidence commissioning | `ensure_commissioned_lane` | yes | correct safety check, repeats precheck | perform once after confirmed edge. |
| Final plan/snapshot | Required Set tail | no | another full plan and snapshot | one revision-keyed async refresh. |

Material conclusion: Required Set improves convenience and resume behavior but
does not materially improve throughput today.

### Scheduler maintenance

| Step | Owner | Blocking | Safety critical | Finding | Recommendation |
| --- | --- | --- | --- | --- | --- |
| Acquisition file lock | `run_due_acquisitions` | Yes | Yes | entire scheduler invocation serial | retain ownership, shorten critical sections. |
| Reconcile/pause/recovery | scheduler integrity functions | Yes | Yes | universe projection every cycle | once/cycle, cache read context. |
| Profiles/facts/budgets | profile load/budget construction | Yes | Yes | rebuilt each cycle | cache by revision. |
| Due selection | `_scheduled_demand_forecast`, `_due_lanes` | Yes | Yes | repeated lane/freshness reads | batch query. |
| Worker execution | `guarded_execute` | Yes | Yes | **whole lane under shared lock** | P0 narrow lock to shared mutation only. |
| Provider/ingest | `_execute_acquisition` | Yes | Yes | provider wait + writer transaction | overlap provider waits; keep writer serial. |
| Snapshot projection | `scheduler_snapshot` | No | No | called before/start/progress/completion/end | debounce at 1 Hz; cache/deltas. |
| Journal persistence | `SchedulerJournal.save` | operationally yes | audit integrity | full JSON write around many transitions | coalesce transitions per lane. |

### Manual CSV import

| Step | Owner | Blocking | Safety critical | Recommendation |
| --- | --- | --- | --- | --- |
| Read/checksum | `ingestion/manual.py:ingest_manual_file` | Yes | Yes | Good; now timed. |
| Parse/format/timezone | `staging/csv_adapter.py`, `ingestion/validation.py` | Yes | Yes | Keep strict; preflight with actionable timezone guidance. |
| Registration/lifecycle | `pipeline.py:_require_registration` | Yes | Yes | Add UI preflight before parsing large files. |
| Conflict policy | `ingestion/merge.py` | Yes | Yes | Retain preserve-by-default; preview conflicts. |
| Evidence/canonical admission | `ingest_staged_batch` | Yes | Yes | Keep atomic writer transaction. |
| Intraday validation | `manual.py:validate_lane` | Yes after commit | Yes | Keep; defer UI projection. |
| Automation pause/resume | scheduler pause records | should not block standalone import | No | show scope/owner/reason; scope to automation only. |

### Delivery to consumers

| Step | Owner | Blocking acquisition? | Safety critical | Finding | Recommendation |
| --- | --- | --- | --- | --- | --- |
| Governed history API | `market_history_service.py`, consumer service | No | Yes at read boundary | canonical/truth queries | revision-key response cache. |
| Estate Truth matrix | `estate_truth_service.py:estate_truth_state` | Often indirectly | No | broad SQL and per-lane work | only on revision change. |
| External catalogue | `HistoryService.get_catalogue` | No | No | registrations/lanes/bars/ingests/events queries | cache by authority revision. |
| Morphix/SignalBar eligibility | consumer projection | No | Yes at delivery boundary | rebuilt with projection | cached read model invalidated after commit. |

## B. Timing trace

Added `fragarach_ii.operation_timing.v1` in `execution_trace.py`. It is
operator-readable and redacted. The allowed fields are:

`operation_id`, `symbol`, `timeframe`, `intent`, `provider`, `step_name`,
`started_at`, `ended_at`, `duration_ms`, `blocking_reason`, `rows_read`,
`rows_written`, `provider_calls`, and `publication_revision`.

Scheduler records are bounded in the durable journal under
`operation_timing_records`. Manual imports return `timing_trace` in their JSON
result. Unknown fields, including credentials, are discarded before persistence.

| Operation | Steps recorded | Current split |
| --- | --- | --- |
| Scheduler lane | `planning_and_reservation`, `provider_execution_and_admission`, `lane_total` | planning vs provider+admission vs total |
| Scheduler cycle | `cycle_total` | idle/load cycle, provider calls, canonical advances |
| Manual CSV | `file_read`, `parse_and_validate`, `canonical_admission`, optional intraday validation | parse vs canonical write/validation |

| Target | planning ms | provider wait ms | canonical write ms | publication ms | Estate ms | status ms | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GBPAUD H1 fetch | pending approved capture | pending | pending | pending | pending | pending | pending |
| ETHUSD H1 / Required Set | pending approved capture | pending | pending | pending | pending | pending | pending |
| JPM D1 manual import attempt | pending supplied CSV | n/a | pending | pending | pending | pending | pending |
| scheduler under load / idle | pending approved non-empty estate | n/a | n/a | n/a | pending | pending | pending |
| Estate Truth / external catalogue | n/a | n/a | n/a | n/a | direct timing pending | direct timing pending | pending |

P0 must split the current combined provider/admission span into `provider_wait`,
`canonical_write`, and `publication` before production SLO attribution.

## C. Blocking gate register

| Blocker | Classification | Assessment |
| --- | --- | --- |
| `NO_APPROVED_MAPPING` | Correct safety; operator-hostile presentation | Never fetch unapproved identity; offer direct mapping review/approval. |
| `NOT_COMMISSIONED` / `EVIDENCE_LANE_NOT_COMMISSIONED` | Correct safety | Do not claim availability; permit reviewed initial fetch then commission after evidence. |
| missing expected edge | Correct safety | Show session reason and next boundary. |
| `NO_CANONICAL_EVIDENCE` | Correct downstream safety | Blocks governed delivery, not discovery/registration. |
| `PROVIDER_ALREADY_ATTEMPTED` | Performance workaround hiding as authority | Key by provider, lane, bounds and response revision; allow material operator change. |
| `LOCAL_PROGRAMMING_ERROR` | Bug | Never present as authority; preserve diagnostic and alert engineering. |
| `timestamp offset must be UTC` | Correct safety; operator-hostile | Keep strict rule; preflight and explain UTC/explicit-timezone options. |
| credential/auth failure | Correct operational blocker | One repair action per provider/job, not per lane. |
| cooldown | Correct safety | Show next eligible time and run other eligible work. |
| budget/reservation | Performance workaround mixed with safety | Preserve quota guard; measure/report idle capacity and revise static reserve. |
| acquisition pause | Correct safety | Show pause scope, owner, reason and resume action. |
| reviewed range required | Correct safety | UI should form reviewed request instead of dead-ending operator. |

## D. Redundant work register

| Repeated work | Evidence | Repair |
| --- | --- | --- |
| Capability/profile/facts per Required Set lane | each lane calls full Fetch Now | one immutable `AcquisitionJobContext`. |
| Reconciliation per Required Set lane | each Fetch Now reconciles universe | reconcile once before group dispatch. |
| Commissioning checks | pre-loop plus post-evidence | preflight state, commission only after edge. |
| Snapshots | selection/start/progress/completion/final | debounce/cache/delta projection. |
| Journal rewrites | save around routing/reservation/events | coalesce transition groups. |
| Freshness/revision/edge reads | Fetch Now, worker, result | job-scoped lane snapshot + one post-commit readback. |
| Estate/catalogue build | independent broad read models | shared revisioned cache. |
| Bounds/history calculation | replanned paths | retain immutable planned bounds. |
| Credential checks | lane/fallback projection | validate once per provider/job. |
| Provider attempt history | recomputed fallback plan | retain per-boundary facts, not broad prior attempts. |

## E. Bottleneck analysis

Minimum successful single-lane path: one plan, one reservation, one or more
provider calls, one writer transaction, journal writes before and after
dispatch, and one final snapshot. With UI `emit`, snapshots are also emitted
before execution, at start, on progress, and after completion. Chunking/fallback
multiplies provider calls; the trace records that count.

Top local cost centres, ranked from source structure pending live-ms ranking:

1. Whole-lane `state_lock` serialization.
2. Full `scheduler_snapshot` projection on frequent emits.
3. Required Set serial full Fetch Now/scheduler cycle per lane.
4. `estate_truth_state` broad queries and per-lane projection.
5. `SchedulerJournal.save()` full JSON serialization/fsync/replace.
6. Reconciliation/active-universe projection every cycle/job.
7. Per-lane capability projection and provider fact/profile reloads.
8. Repeated freshness, edge, and revision SQLite reads.
9. SQLite writer lock wait during canonical admission.
10. Catalogue rebuilding from registrations, lanes, bars, ingests, and events.

Fragarach cannot yet be honestly called provider-limited; provider latency was
not measurable here. The local serialization and repeated read-model work are
already enough to identify local over-governance.

## F. Prioritized repair plan

| Priority | Repair | Guardrail |
| --- | --- | --- |
| P0 | Narrow `state_lock`; never hold it over provider I/O or canonical ingestion. Split timing spans. Debounce snapshots. | Canonical writer and event durability remain serial. |
| P0 | Commit publication event synchronously, then make Estate/catalogue/UI projection async and revision-keyed. | No evidence claim before canonical commit. |
| P1 | Add immutable `AcquisitionJobContext` with one reconciliation, facts revision, profiles, credentials, lane snapshots and bounds. | Deterministic routing inputs retained. |
| P1 | Batch due-lane SQL/freshness/capability reads and coalesce journal saves. | Preserve audit events. |
| P2 | Plan Required Set once; enqueue executable lanes together; group reservations by provider/symbol. | Independent per-lane evidence identities stay intact. |
| P3 | Revisioned publication worker/read-model cache for Estate, catalogue, Morphix and SignalBar. | Invalidate only after committed canonical revision. |
| P4 | Bounded provider parallelism with a single canonical writer. | Never parallelize authority writes. |
| P5 | Cached monitor/delta payload under 2 MB and revision invalidation. | Target <1 s monitor projection. |

## Next three specs

1. **SPEC-063 — Scheduler critical-path concurrency and snapshot coalescing.**
2. **SPEC-064 — Acquisition job context and Required Set batch planner.**
3. **SPEC-065 — Revisioned Estate and consumer read models.**

## Live capture protocol

Use an approved non-empty authority database and approved credential.

1. Run GBPAUD H1 and ETHUSD Required Set normally; save command JSON plus
   journal timing records filtered by operation/symbol.
2. Run JPM D1 CSV preflight/import with a supplied representative file; save
   returned `timing_trace` even if rejected.
3. Run one idle and one controlled multi-lane scheduler cycle; record queue
   depth, credits, SQLite wait, cycle span and snapshot byte size.
4. Time `estate_truth_state()` and `HistoryService.get_catalogue()` twice at
   the same revision (cold/warm) and populate the timing table above.

## Files touched and checks

- `src/fragarach_ii/execution_trace.py`: redacted bounded timing contract.
- `src/fragarach_ii/scheduler_service.py`: lane/cycle timing only; no authority
  decision changed.
- `src/fragarach_ii/ingestion/manual.py`, `ingestion/pipeline.py`: manual CSV
  timing returned in normal result.
- timing/redaction tests and this report.

`PYTHONPATH=src pytest -q tests/operations/test_spec055_execution_trace.py
tests/ingestion/test_manual_ingestion.py tests/operations/test_spec060_required_set_acquisition.py
--disable-warnings --maxfail=1 --durations=15` → **25 passed**.

`PYTHONPATH=src pytest -q tests/operations/test_spec060_required_set_acquisition.py
tests/operations/test_spec049_scheduler_service.py tests/operations/test_spec056_twelve_data_throughput.py
--disable-warnings --maxfail=1 --durations=12` → **22 passed**.
