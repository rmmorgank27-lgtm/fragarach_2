# SPEC-064 — Estate Audit & Reconciliation

## Status

Proposed.

## Objective

Define **Audit Estate** as Fragarach II's explicit full-estate governance
workflow.

Audit Estate verifies that registrations, commissioned lanes, canonical
authority, update-register state, calendars, provider routes, and operational
audit records remain coherent. It is separate from normal time-triggered
acquisition defined by SPEC-063.

An audit may identify drift, produce a durable report, and create targeted
repair recommendations. It must not become a normal Scheduler polling path or
silently acquire every lane it inspects.

## Scope

Implement:

* an operator-invoked and weekly scheduled Audit Estate job;
* immutable audit run records and a bounded report;
* cross-authority coherence checks;
* deterministic classification of findings;
* an explicit, reviewable repair plan;
* targeted register repair where no canonical authority decision is changed;
* audit status and findings in the native Scheduler/Audit workspaces.

Do not change governed bars, raw evidence, provenance, validation doctrine,
provider mappings, or instrument lifecycle state merely because an audit ran.

## Relationship to normal Scheduler operation

| Concern | Time-triggered Scheduler (SPEC-063) | Audit Estate |
| --- | --- | --- |
| Purpose | Keep known commissioned lanes current. | Prove and reconcile estate structure. |
| Selection | Only due rows in the lane update register. | Every in-scope active lane and supporting authority. |
| Cadence | Exact approved market/session boundary. | Operator request, weekly schedule, or defined recovery/change trigger. |
| Acquisition | Normal expected update only. | Never automatic; may recommend targeted repair work. |
| Runtime state | Lane update register. | Audit run/report and findings. |
| Cost model | Proportional to due work. | Proportional to audit scope; intentionally bounded and observable. |

The normal Scheduler must never invoke Audit Estate to determine whether an
ordinary update is due.

## 1. Triggers

Audit Estate may run only under one of these triggers:

```text
OPERATOR_REQUEST
WEEKLY_MAINTENANCE
SCHEDULER_RECOVERY
REGISTER_RECOVERY
CALENDAR_OR_SESSION_REVISION
PROVIDER_ROUTE_REVISION
LIFECYCLE_CHANGE
```

Weekly maintenance must run outside the busiest scheduled-acquisition window.
An active audit must not block normal due-work dispatch or canonical admission.
Only one full-estate audit may run at a time for one authority database.

## 2. Audit scope

The audit reads the following authority surfaces:

```text
instrument registrations
evidence lanes and commissioned lane authority
lane_state and governed bar bounds/counts
validation summaries
lane update register
approved calendars and intraday session profiles
approved provider mappings, capabilities, and route revisions
Scheduler queue, blocked/retry state, and compact audit journal summaries
```

It must use aggregate and set-based queries where possible. It must not load
full bar histories, row-level provenance, raw blocks, or consumer read models
unless a specific finding requires a targeted follow-up.

## 3. Audit run record

Every audit produces one immutable run record with:

```text
audit_run_id
trigger
started_at_utc
completed_at_utc
scope revision fingerprints
audit contract/version
overall result
finding counts by severity and class
repair-plan identifier, if created
report checksum
```

The report contains bounded summaries plus finding identifiers. Detailed
evidence remains in the existing authority and operational records; an audit
report must not duplicate large journals or market history.

## 4. Required checks

### 4.1 Registration and lifecycle coherence

For every active registration, verify:

* its declared timeframe and representation remain permitted;
* lifecycle state and evidence/commissioned lane state agree;
* retired, quarantined, and permanently removed instruments are excluded from
  normal update scheduling;
* no active update-register row exists for an ineligible lifecycle state.

### 4.2 Canonical lane coherence

For every in-scope lane, verify:

* lane state exists when governed bars or commissioned evidence exist;
* lane state version, high watermark, and aggregate bar bounds agree;
* canonical edge and validation summary identity agree with the lane;
* commissioned lanes have usable canonical evidence;
* non-commissioned lanes are not presented as normal automated upkeep work.

### 4.3 Update-register coherence

For every commissioned lane, verify:

* exactly one update-register row exists;
* its calendar/session and provider-route revisions are current;
* its expected boundary and next check are valid for the approved schedule;
* `RUNNING`, `RETRY`, `BLOCKED`, and `PAUSED` states have a valid reason,
  owner, and time boundary;
* stale active work is recovered to an explicit retry or blocked state;
* no register row exists for an inactive or removed lane.

### 4.4 Calendar, session, and provider-route coherence

Verify that each commissioned lane has:

* an approved calendar and, for intraday lanes, a session profile;
* a schedule that resolves a next completed boundary;
* an approved eligible provider route or a classified blocked reason;
* no silently changed provider mapping, entitlement, or capability contract.

### 4.5 Operational record coherence

Verify that queued, retrying, paused, and blocked Scheduler records agree with
the update register. The audit may compact aged successful operational detail,
but it must preserve durable summaries and traceability.

## 5. Finding classes

Each finding has one severity and one deterministic class.

| Severity | Meaning | Examples |
| --- | --- | --- |
| `INFO` | No correction needed; useful governance observation. | Audit compaction completed. |
| `WARNING` | Normal updates can continue, but review is appropriate. | A lane is approaching its staleness watchdog. |
| `REPAIRABLE` | Operational state can be rebuilt without changing canonical authority. | Missing update-register row for an otherwise valid commissioned lane. |
| `BLOCKING` | Normal update cannot safely continue. | Calendar, mapping, credential, or lifecycle authority is inconsistent. |
| `INTEGRITY` | Canonical or governance evidence appears inconsistent. | Lane state/bounds mismatch or malformed validation identity. |

Finding records include the lane or authority identifier, observed facts,
expected facts, detection time, and recommended action. They must never contain
credentials, provider response bodies, or unbounded history payloads.

## 6. Repairs and authority boundaries

Audit Estate must distinguish safe operational repair from authority-changing
work.

### Safe automatic repair

The audit may automatically perform only idempotent operational repairs such
as:

* create or remove a lane update-register row when lifecycle and commissioning
  authority unambiguously require it;
* recompute `next_expected_boundary_utc` and `next_check_at_utc` from the
  approved schedule;
* clear a stale local `RUNNING` marker after proving no acquisition owner or
  active trace exists;
* compact expired successful journal detail according to retention policy.

Each automatic repair must be separately recorded in the audit run.

### Review-required repair

The audit must create a repair plan, without applying it, for:

* provider mapping, credential, entitlement, or route changes;
* calendar or session policy changes;
* lifecycle/registration changes;
* canonical backfill or re-acquisition;
* validation reruns that may alter published operational interpretation;
* any evidence, bar, provenance, or canonical lane-state mutation.

Targeted repair acquisition is an explicit Scheduler work item after operator
review. Auditing a lane never authorises fetching it.

## 7. Execution and resource limits

Audit Estate is intentionally broad but must remain controlled:

* run using read-only authority connections wherever possible;
* page or batch aggregate lane checks;
* hold no Scheduler dispatch lock during broad reads;
* yield between batches when normal due work is pending;
* publish progress by audit phase and bounded finding count;
* retain no full-estate object graph after a phase is complete;
* enforce a report-size and per-finding-detail limit.

The audit must record wall time, SQL/read time, rows/lane counts inspected,
finding count, repair count, monitor payload size, and report size.

## 8. Native operator experience

The Audit workspace exposes:

```text
last audit result and age
trigger and run duration
scope revision fingerprints
finding counts by severity
filterable finding list
safe repairs applied
review-required repair plan
Run Audit Estate action
weekly schedule and next planned audit
```

The Scheduler workspace may show a compact audit health indicator and last-run
time, but it must not render the full audit report during normal monitoring.

## 9. Recovery

After a Scheduler crash, register corruption, database restore, or service
repair, Audit Estate may run in recovery mode. Recovery mode verifies the same
authority relationships and may rebuild operational register state. It must
not infer or publish missing market bars.

If canonical integrity findings are present, normal work for only the affected
lanes is blocked. Unaffected lanes continue through the normal due-work loop.

## Acceptance

Automated and live acceptance must prove:

1. normal Scheduler wakes do not invoke Audit Estate;
2. an operator-requested audit checks every active lane without triggering
   automatic acquisition;
3. a weekly audit creates a durable bounded report;
4. a valid estate produces no blocking or integrity findings;
5. each deliberate drift fixture produces the correct finding class;
6. safe update-register repair is idempotent and leaves canonical authority
   unchanged;
7. a provider/calendar/lifecycle mismatch yields a review-required repair,
   not an automatic authority mutation;
8. an affected lane can be blocked while unaffected due lanes continue;
9. audit execution does not hold the Scheduler dispatch or canonical writer
   lock for the full audit duration;
10. audit reports and monitor payloads remain bounded as journal and bar
   history grow.
