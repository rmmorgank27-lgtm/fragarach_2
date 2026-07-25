# SPEC-063 — Time-Triggered Lane Update Scheduler

## Status

Proposed.

## Objective

Replace recurring full-estate scheduler reconciliation with a durable,
time-triggered lane update register.

Normal Scheduler operation must inspect and execute only lanes whose next
approved update boundary is due. Full-estate reconciliation remains an Audit
operation, initiated by an operator or a weekly maintenance schedule.

This specification supersedes the normal-operation reconciliation behaviour
implicit in SPEC-041. It preserves the governed SQLite authority database,
existing provider contracts, immutable ingestion, validation, publication, and
the Scheduler's single acquisition owner.

## Problem

The current Scheduler repeatedly rebuilds a broad estate projection and rewrites
its large operational journal to decide whether a small amount of work is due.
That cost scales with the complete estate and audit history rather than the
number of due lanes. A past-due or blocked item can therefore keep the service
in a continuous reconciliation loop.

Normal upkeep and governance audit are different jobs and must not share the
same execution path.

## Operating model

```text
approved calendar/session profile
        ↓
lane update register (one durable row per active commissioned lane)
        ↓  indexed next_check_at <= now
due-work queue
        ↓
provider planning, acquisition, immutable admission, validation, publication
        ↓
record lane outcome and calculate the next check
```

The Scheduler waits until the earliest `next_check_at`, a provider-budget
release, or an explicit command wake. It must not poll or scan the estate to
discover ordinary due work.

## Scope

Implement:

* a durable lane update register;
* exact calendar/session-driven check scheduling;
* a small, indexed due-work query;
* outcome-driven rescheduling and bounded retry;
* independent normal, repair, and historical-backfill queues;
* compact Scheduler runtime state and monitor summaries;
* an explicit full-estate Audit operation and weekly audit schedule;
* migration from current commissioned lanes and Scheduler journal state.

Do not change canonical bar ownership, merge conflict doctrine, validation
rules, provider mapping authority, or consumer authority contracts.

## 1. Lane update register

The Scheduler shall own one operational row for each active commissioned lane.
It is runtime state, not canonical market evidence and not an audit journal.

Required fields:

```text
asset
timeframe
state                         READY | RETRY | BLOCKED | PAUSED | RUNNING
next_expected_boundary_utc
next_check_at_utc
last_checked_boundary_utc
last_attempted_at_utc
last_successful_bar_utc
last_outcome
retry_count
retry_not_before_utc
provider_route_revision
calendar_or_session_revision
lane_state_version
updated_at_utc
```

`(state, next_check_at_utc)` must be indexed. A lane has at most one active
update-register row and one active acquisition task.

The register is reconstructed only during migration, an explicit Audit, or a
defined recovery action. It is not rebuilt during each Scheduler wake.

## 2. Time-triggered scheduling

The approved operational calendar and session profile determine the next closed
boundary for each lane.

* `M5`, `M30`, and `H1` schedule after their exact closed interval plus the
  approved provider grace period.
* `D1` schedules after the registered market session close, owner-day rule,
  and approved acquisition delay.
* No lane is scheduled during a closed market interval unless it is repair or
  operator-requested work.
* Lanes sharing a boundary may be planned together, subject to provider budget
  and bounded worker capacity.

After a normal no-change result, the Scheduler records that boundary as checked
and schedules the *next* expected boundary. It must not repeatedly re-check the
same boundary.

The normal schedule is authoritative for routine upkeep. A passive lane does
not require a broad fifteen-minute re-evaluation; its next approved boundary
already states when it can change. A fifteen-minute maximum may be used only as
a lightweight staleness watchdog for active, retrying, or otherwise suspect
lanes.

## 3. Due-work query and dispatch

Normal selection is limited to due rows:

```sql
SELECT asset, timeframe
FROM lane_update_register
WHERE state IN ('READY', 'RETRY')
  AND next_check_at_utc <= :now
  AND (retry_not_before_utc IS NULL OR retry_not_before_utc <= :now)
ORDER BY priority, next_check_at_utc, asset, timeframe
LIMIT :available_capacity;
```

The query must not join bars, provenance, the full authority ledger, or an
estate read model.

Before dispatch, selected lanes may be batch-planned against a revision-keyed
context containing only the needed provider profiles, credentials, mappings,
rate budgets, and lane-edge facts. Provider I/O remains bounded and concurrent
where safe; canonical evidence admission remains serialized by the existing
writer authority.

Cadence and market priority from SPEC-042 remain in force inside the selected
due set. They do not justify selecting or inspecting lanes that are not due.

## 4. Outcome-driven rescheduling

| Outcome | Register action |
| --- | --- |
| Canonical edge advanced and validated | Mark boundary complete; calculate next approved boundary. |
| Provider reports no new completed data | Mark boundary checked; calculate next approved boundary. |
| Temporary provider/network failure | Keep the same boundary; enter `RETRY` with bounded exponential backoff and jitter. |
| Rate budget unavailable | Keep the boundary; schedule at the provider budget release. |
| Provider cooldown | Keep the boundary; schedule at cooldown expiry. |
| Missing credential/mapping/entitlement | Enter `BLOCKED`; require a provider-authority revision or explicit operator action to replan. |
| Operator pause | Enter `PAUSED`; resume at the next valid boundary after the pause is cleared. |
| Canonical validation/publication failure | Enter `RETRY` or `BLOCKED` according to the existing classified failure doctrine. |

An unchanged result is a valid completed check, not a reason to run a broad
reconciliation loop.

## 5. Separate work classes

The Scheduler shall maintain separate queues and rate allocations for:

1. **Normal upkeep** — exact scheduled boundary checks for commissioned lanes.
2. **Repair/retry** — a known missed boundary or classified transient failure.
3. **Historical backfill** — operator-approved depth work, always lower
   priority than normal upkeep.
4. **Operator Fetch** — explicit reviewed work, visible and auditable.

Backfill and repair must not cause unrelated current lanes to be re-planned.
Normal upkeep must not be starved by historical work.

## 6. Scheduler journal and monitor

The Scheduler journal is an audit record, not the live work index.

* Runtime scheduling state lives in the lane update register.
* The journal stores bounded summaries and links to detailed immutable events.
* Successful detailed traces and timing records are compacted or archived on a
  retention policy; they are never decoded and rewritten for each normal wake.
* The monitor publishes a cached delta or compact summary, invalidated only by
  a register, queue, provider, or publication revision.
* Status reads must not invoke full estate reconciliation.

The normal idle path must be a small due-work query followed by a sleep. Its
memory and CPU cost must be independent of historical journal size and total
bar count.

## 7. Estate Audit

Full-estate reconciliation is renamed and exposed as **Audit Estate**.

It verifies, reports, and where authorised repairs drift between:

* active registrations and commissioned lanes;
* lane state and the lane update register;
* calendar/session revisions and scheduled boundaries;
* provider-route revisions and blocked lanes;
* outstanding operational work and durable journal summaries.

Audit Estate runs only:

* at explicit operator request;
* on a weekly maintenance schedule;
* after a calendar, session, provider-route, or lifecycle authority change;
* after Scheduler recovery or detected register corruption.

An audit may enqueue targeted repair work. It must not itself start normal
acquisition for every lane merely because it inspected them.

## 8. Migration and recovery

Migration derives one update-register row per active commissioned lane from the
existing lane edge, approved calendar/session profile, and current time. It
does not alter bars or canonical authority.

During cutover:

1. stop new normal dispatch;
2. snapshot the current Scheduler journal for audit retention;
3. create and validate the update register;
4. seed normal, repair, and blocked states deterministically;
5. start the new due-work loop;
6. retain the existing journal as read-only audit history.

If the register is unavailable or invalid, the Scheduler must enter an explicit
recoverable fault state. It must not fall back to continuous full-estate scans.

## Acceptance

Automated and live acceptance must prove:

1. an idle estate with no due lane performs no full-estate projection and
   sleeps until the earliest valid wake;
2. a due M5, M30, H1, or D1 lane is selected from the register at its exact
   approved boundary;
3. a no-change response is checked off once and is not retried before the next
   boundary;
4. retry, cooldown, pause, and blocked outcomes affect only their lane;
5. historical work cannot delay current scheduled work;
6. an Estate Audit is the only normal path allowed to scan every active lane;
7. status reads do not decode the full audit journal or recompute the estate;
8. journal growth does not materially change idle Scheduler CPU or memory;
9. canonical ingestion, validation, publication, and consumer revision
   semantics remain unchanged;
10. recovery rebuilds the register deterministically without changing governed
    bars.

## Observability

The Scheduler must expose:

```text
next due check
due lanes selected
normal / repair / backfill queue depths
per-lane next boundary and last checked boundary
blocked and retrying lane counts
idle-wake duration
due-work query duration
planning, provider, canonical admission, and publication duration
monitor payload size
journal size and compacted-record count
```

The target idle wake is a bounded due-work lookup and return to sleep, with no
full-estate SQL projection or whole-journal serialization.
