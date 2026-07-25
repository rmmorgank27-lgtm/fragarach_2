# SPEC-042 — Market Acquisition Orchestrator Phase 2

## Provider Routing, Rate Control, Failover, and Manual Escalation

### Status

Proposed.

---

## Objective

Extend the SPEC-041 scheduler into a provider-aware Market Acquisition Orchestrator.

For every due commissioned lane, Fragarach II must:

1. determine the missing canonical range;
2. identify eligible approved providers;
3. select the best provider;
4. respect provider rate and cost constraints;
5. fail over deterministically when acquisition fails;
6. request operator-supplied evidence when automation is exhausted;
7. publish successful evidence only through the existing immutable ingestion pipeline.

This specification does not introduce historical Evidence Discovery.

---

## Scope

Implement:

* provider capability profiles;
* provider priority and routing;
* rate-limit budgeting;
* provider health and cooldown;
* deterministic provider failover;
* acquisition queue management;
* manual acquisition requests;
* expanded native Scheduler monitoring;
* one live scheduler-enabled acceptance journey.

Initial provider support:

* Twelve Data
* Yahoo
* Binance
* CoinGecko

A provider may only be used where an approved symbol mapping and supported lane capability exist.

---

## 1. Acquisition Planning

Before making a provider request, the orchestrator must create an acquisition plan containing:

```text
lane
canonical edge
expected edge
missing range
eligible providers
selected provider
selection reason
estimated request count
rate-budget eligibility
fallback sequence
```

The plan is operational metadata.

It must not modify canonical authority.

Only the missing canonical edge range may be requested.

Existing overlap rules may be used where required for safe provider reconciliation.

---

## 2. Provider Capability Profiles

Each provider must expose a controlled capability profile.

Required fields:

```text
provider
enabled
supported asset classes
supported timeframes
approved symbol mappings
credential requirement
entitlement state
request limit
request window
maximum rows per request
history limitations
cost class
priority
current health
cooldown until
```

Provider capabilities must not be inferred from failed runtime requests when an explicit contract exists.

Credentials remain environment-only and must never be written to operational journals or monitor payloads.

---

## 3. Provider Eligibility

A provider is eligible only when:

* it is enabled;
* the lane has an approved provider mapping;
* the provider supports the asset class;
* the provider supports the commissioned timeframe;
* required credentials are present;
* entitlement is available;
* the provider is not in cooldown;
* sufficient request budget exists;
* the required range can be requested without violating the provider contract.

An ineligible provider must produce a structured reason.

Examples:

```text
NO_APPROVED_MAPPING
TIMEFRAME_UNSUPPORTED
ASSET_CLASS_UNSUPPORTED
CREDENTIAL_MISSING
ENTITLEMENT_BLOCKED
RATE_BUDGET_EXHAUSTED
PROVIDER_COOLDOWN
RANGE_UNAVAILABLE
```

---

## 4. Provider Selection

Provider selection must be deterministic.

Selection order:

1. eligible provider priority;
2. lowest acquisition cost;
3. best current provider health;
4. smallest estimated request count;
5. stable provider identifier.

The orchestrator must record why the selected provider was preferred.

It must not request multiple providers simultaneously for the same lane and boundary.

---

## 5. Rate-Limit Control

Rate limiting must occur before provider execution.

Each provider requires an independent rate-budget controller.

Twelve Data policy must default to its approved limit of:

```text
55 calls per minute
```

The implementation may reserve configurable safety headroom but must never exceed the configured provider limit.

Rate control must:

* use a monotonic clock;
* survive concurrent lane scheduling;
* prevent startup catch-up bursts;
* account for multi-request acquisitions;
* delay work rather than discard it;
* expose the next budget-available time;
* avoid polling while waiting.

Rate state is operational and may be reconstructed after application restart.

No credential or provider response body may be persisted in rate state.

---

## 6. Acquisition Queue

Due lanes must enter a controlled acquisition queue.

Cadence priority is mandatory:

```text
D1
↓
H1
↓
M30
↓
M5
```

Within the same market and operational class, no lower-timeframe lane may be selected while eligible higher-timeframe work remains. Required ordering is:

```text
Operator Fetch already in progress
↓
D1 required boundary
↓
H1 required boundary
↓
M30 required boundary
↓
M5 required boundary
↓
historical depth
```

Queue age orders work only within the same timeframe tier. An old M5 item must never outrank eligible stale D1, H1, or M30 work. After a repaired D1 path is released, all eligible D1 work must clear before H1, then M30, then M5.

A lane may have only one active acquisition task.

Each scheduled boundary may be attempted only once per provider unless an explicitly classified retry permits another attempt.

---

## 7. Provider Health

Provider health states:

```text
Healthy
Degraded
Cooling Down
Unavailable
Credential Missing
Entitlement Blocked
```

Health must be calculated from structured operational results.

Examples:

* successful valid acquisition improves health;
* transient transport failures degrade health;
* repeated rate responses trigger cooldown;
* authentication failure produces `Credential Missing`;
* explicit entitlement rejection produces `Entitlement Blocked`;
* invalid evidence affects the acquisition result but does not automatically invalidate all provider capabilities.

Cooldown duration must be controlled by provider policy and failure classification.

One provider failure must not stop unrelated providers or lanes.

---

## 8. Deterministic Failover

When the selected provider fails, the orchestrator must classify the failure.

Retryable examples:

```text
NETWORK_FAILURE
PROVIDER_TIMEOUT
RATE_LIMITED
TEMPORARY_PROVIDER_FAILURE
```

Non-retryable provider/lane examples:

```text
INVALID_MAPPING
ENTITLEMENT_BLOCKED
TIMEFRAME_UNSUPPORTED
RANGE_UNAVAILABLE
```

Evidence failures:

```text
INVALID_RESPONSE
INVALID_CHRONOLOGY
INVALID_OHLC
ORIENTATION_MISMATCH
NO_NEW_DATA
```

The next eligible provider must be attempted only after the first result is classified.

Every failover event must record:

```text
lane
scheduled boundary
provider
result
reason
next provider
attempt time
duration
```

`NO_NEW_DATA` must never fabricate or rewrite an observation.

---

## 9. Manual Acquisition Requests

A manual acquisition request must be created when:

* no provider is eligible; or
* every eligible provider has been exhausted; or
* the available provider history cannot cover the required range.

Required request fields:

```text
request identifier
symbol
timeframe
missing start
missing end
expected canonical edge
priority
reason
providers attempted
provider failure summaries
accepted import format
created time
current status
```

Request statuses:

```text
Required
Acknowledged
Resolved
Dismissed
```

The native application must allow the operator to open Manage Data from the request with symbol, timeframe, and required range prefilled.

A request becomes `Resolved` only when canonical authority contains the required evidence or the operator explicitly dismisses it.

Uploading or selecting a file alone does not resolve the request.

Manual evidence must use the existing preview, validation, quarantine, and immutable ingest path.

---

## 10. Native Scheduler Workspace

Extend the Scheduler workspace with:

### Provider Health

Show for each provider:

```text
health
rate budget
calls used
calls available
cooldown
credentials
entitlement
last success
last failure
```

Do not display credential values.

### Acquisition Queue

Show:

```text
lane
missing range
selected provider
fallback position
queue reason
estimated requests
budget wait
next attempt
```

### Manual Requests

Show:

```text
symbol
timeframe
missing range
reason
age
status
Open Manage Data
Dismiss
```

### Lane Detail

Each commissioned lane must expose:

```text
routing decision
providers considered
providers rejected
current provider
attempt history
publication result
manual request
```

The monitor must update live without restarting the application.

---

## 11. Monitor Contract

Introduce:

```text
fragarach_ii.scheduler_monitor.v2
```

Version 2 must retain the existing SPEC-041 fields and add:

```text
providers
rate_budgets
acquisition_queue
routing_decisions
manual_requests
```

The native application must remain able to render a SPEC-041 version 1 snapshot during upgrade or journal recovery.

---

## 12. Persistence

Continue using operational sidecar persistence outside the canonical database.

The implementation may extend the existing scheduler journal.

Persist only operational state required for:

* recent attempts;
* provider health;
* cooldown;
* routing results;
* manual acquisition requests;
* restart recovery.

Do not add or modify canonical authority tables.

Do not persist:

* API keys;
* authentication headers;
* full provider response bodies;
* temporary downloaded evidence;
* canonical observations outside the existing ingestion path.

---

## 13. Application Lifecycle

Normal Fragarach II launch must:

1. start the scheduler;
2. load commissioned lanes;
3. restore operational provider state;
4. calculate current rate budgets;
5. perform bounded startup catch-up;
6. route due lanes through eligible providers;
7. publish valid evidence;
8. update the Scheduler and Estate workspaces.

Application termination must stop acquisition cleanly.

Interrupted lanes must return to a recoverable queued state.

---

## 14. Constitutional Boundaries

Do not change:

* the ten-table canonical authority;
* immutable evidence ingestion;
* canonical validation;
* lane commissioning;
* operational calendars;
* freshness doctrine;
* SignalBar;
* MorphixFC;
* existing manual import validation;
* provider identity authority.

All provider evidence must pass through the existing canonical validation and immutable publication path.

---

## 15. Non-Goals

Do not implement:

* general internet searching;
* local filesystem evidence discovery;
* legacy Fragarach harvesting;
* automatic registration of new symbols;
* automatic provider mapping creation;
* automatic import of discovered files;
* speculative data repair;
* fabricated observations;
* historical depth optimisation.

These belong to later Evidence Discovery and Harvest phases.

---

## 16. Acceptance Tests

### Routing

* A due lane selects the highest-ranked eligible provider.
* An unsupported provider is rejected before any request.
* Selection is deterministic for identical state.
* Only one provider executes at a time for a lane boundary.

### Rate Limits

* Twelve Data never exceeds the configured 55-call-per-minute ceiling.
* Startup catch-up cannot create a request burst above the limit.
* Multi-request acquisitions reserve the required budget.
* Budget exhaustion delays the lane until the exact available time.
* Waiting does not use polling.

Use a fake monotonic clock for automated tests.

### Failover

* A retryable Twelve Data failure falls through to Yahoo where eligible.
* A Yahoo failure for crypto falls through to Binance or CoinGecko where approved.
* Entitlement failure skips further attempts for that provider during its classified state.
* One failed lane does not stop another lane.
* A successful fallback publishes through the normal immutable ingest path.

### Manual Escalation

* No eligible provider creates one manual acquisition request.
* Exhausting all approved providers creates one request.
* Restart does not duplicate an unresolved request.
* Opening the request pre-fills Manage Data.
* Successful canonical publication resolves the request.
* Selecting a CSV without publication does not resolve it.

### Provider Health

* Successful requests restore or improve health.
* Repeated transient failures trigger cooldown.
* Authentication failure reports `Credential Missing`.
* Entitlement rejection reports `Entitlement Blocked`.
* Cooldown expiry restores provider eligibility.

### Authority

* Successful publication advances the lane authority revision.
* Freshness recalculates from the new canonical edge.
* Estate and Scheduler update without application restart.
* Invalid provider evidence cannot advance canonical authority.
* Canonical table count remains exactly ten.

---

## 17. Live Operational Acceptance

Run one normal signed application launch with scheduling enabled.

The live journey must prove:

1. all commissioned lanes load;
2. startup catch-up creates a controlled queue;
3. provider selection is visible;
4. rate budgeting is visible;
5. at least one real provider acquisition succeeds;
6. at least one missing canonical edge is published;
7. authority revision advances;
8. the lane becomes Current;
9. Estate refreshes automatically;
10. a provider or lane failure remains isolated;
11. application restart does not duplicate completed work;
12. no configured provider rate is exceeded.

Do not deliberately cause paid calls beyond the evidence required for this acceptance.

---

## 18. Verification

Use proportional verification:

* focused Python tests for acquisition planning, routing, rate limits, failover, provider health, and manual requests;
* existing SPEC-041 scheduler tests affected by the change;
* focused OperationsCore monitor-contract checks;
* one release Swift build;
* one signed native launch;
* one live scheduler-enabled smoke journey;
* one concise implementation report.

Do not run unrelated full regression suites unless shared canonical ingestion or authority code is changed.

---

## Completion Condition

SPEC-042 is complete when Fragarach II can keep commissioned lanes current using controlled multi-provider routing, remain within every provider limit, fail over without operator intervention, and clearly request manual evidence when automated acquisition cannot succeed.

The following phase should be the **Evidence Discovery Engine**, but only after this routing layer has demonstrated stable live operation.
