# SPEC-065 — Broker-Resilient Acquisition Authority

## Status

Implemented baseline. The estate-wide provider-priority amendment below is
aligned with SPEC-067 but is not yet proven live. The active runtime must
continue to report its actual route until the amended policy passes the
SPEC-067 migration and acceptance gates.

## Objective

Make Fragarach II's operational market acquisition resilient without weakening
canonical evidence truth.

The design establishes an estate-wide default with MT5 as the primary source
wherever a reviewed lane is available, followed by applicable
Binance/CoinGecko routes, then Yahoo, and finally Twelve Data. An activated
exact-lane override may disable or reorder any reviewed candidate. The design
also permits multiple independently located MT5 bridges without introducing
competing canonical writers or silent source blending.

This specification amends the routing, capacity, health, and recovery aspects
of SPEC-042 and the temporary-outcome handling of SPEC-063. It does not alter
the immutable evidence, validation, canonical publication, or consumer
authority contracts.

---

## 1. Governing decisions

1. **MT5 is the first provider tier by default** for every approved
   symbol/timeframe lane where the reviewed broker representation is present
   in the live terminal catalogue and the bridge is available. An activated
   lane override may disable or move it for that exact lane.
2. The estate-wide default provider order is:

   ```text
   MT5 -> BINANCE / COINGECKO -> YAHOO_FINANCE -> TWELVE_DATA
   ```

   A tier is skipped when it has no reviewed representation for the canonical
   symbol, does not support the timeframe, lacks required access, or is not
   operationally available. Skipping an inapplicable tier is not a fallback
   failure.
   An activated lane override may disable or reorder any reviewed candidate
   for its exact `symbol x timeframe` lane. It remains authoritative until the
   lane is restored to estate defaults, and it has no effect on another lane.
3. Binance, CoinGecko, and CoinGecko DEX are the crypto-market-data tier. They
   are never candidates for FX, metals, energy, indices, or equities merely
   because the provider offers a similarly named product. When more than one
   provider in this tier is reviewed for a lane, its deterministic order is
   recorded in that lane's routing revision.
4. An approved MT5 stock representation may be primary for `H1` and, where a
   lane-specific evidence review proves it preferable, for `D1`. This is a
   per-instrument decision; a broker CFD is never assumed to be identical to a
   listed equity solely because its name is similar.
5. Yahoo precedes Twelve Data by default wherever both are approved and
   available for the lane. Yahoo remains D1-only unless a separately reviewed
   capability proves otherwise; it is not an intraday escape hatch. An
   activated lane override may change their order.
6. Twelve Data remains the governed final fallback in the estate default and
   a general reference provider. Its credit window is a temporary capacity
   constraint, never a provider-route failure. It may become primary or move
   earlier only through an explicit activated lane override.
7. An asynchronous provider request is not a failure. The next enabled
   candidate in the effective lane order becomes executable only after a
   classified failure, rejection, expiry, or declared unavailability under
   the active routing revision.
8. Every MT5 node retains its delivered raw receipt records locally for the
   defined recovery window. Those receipts are secondary recovery evidence,
   not a second canonical authority.
9. Fragarach retains one canonical admission writer. MT5 nodes, provider
   workers, replicas, the native app, and recovery tooling must never write the
   canonical database directly.

## 2. Provider and node topology

```text
MT5 node A — primary broker, primary location
MT5 node B — same broker, separate location, hot standby
MT5 node C — approved alternate broker family, diversity fallback
         ↓
authenticated bridge request/receipt contract and local evidence spool
         ↓
Fragarach acquisition queue and single canonical admission writer
         ↓
immutable evidence, validation, canonical publication
```

Node A is the initial production node. Nodes B and C are first-class design
members from the outset but are not activated until their own configuration
and acceptance gates pass.

Nodes must use independent failure domains where practicable: separate Windows
host, physical location, power protection, network path, MT5 terminal, and
bridge identity. A second device in the same location is useful availability
capacity, but it is not location resilience.

## 3. Route manifest

The Scheduler shall consume one revisioned, inspectable route manifest. A
route is identified by:

```text
canonical symbol
timeframe
provider family
broker identity, when MT5-backed
terminal symbol and representation class
ordered node candidates
ordered provider fallbacks
estate-default or lane-override state
disabled reviewed candidates
calendar/session identity
effective date and review receipt
```

Default route policies are:

| Lane class | Ordered candidate tiers |
| --- | --- |
| FX, metals, energy - D1/H1/M30/M5 | Approved MT5 -> Yahoo where reviewed/supported -> Twelve Data where reviewed/supported |
| Broker index CFDs - D1/H1/M30/M5 | Approved MT5 -> fail closed unless a genuinely equivalent representation is separately reviewed |
| Crypto - D1/H1/M30/M5 | Approved MT5 -> reviewed Binance/CoinGecko candidate(s) -> Yahoo where reviewed/supported -> Twelve Data where reviewed/supported |
| Stocks and ETFs - D1 | Approved MT5 exact representation where reviewed -> Yahoo exact representation -> Twelve Data exact representation |
| Stocks and ETFs - H1/M30/M5 | Approved MT5 exact representation where reviewed -> other applicable reviewed tiers in estate-default order -> fail closed |
| Derived lanes | Approved internal derivation; no external-provider fallback |

The word `where` is mandatory in this table: a higher tier that cannot prove
the exact/equivalent representation and timeframe is absent from that lane,
not silently substituted.

These are estate defaults, not locked chains. An activated lane override may
disable or reorder any reviewed candidate in its exact lane. The effective
route manifest records the override revision, operator reason, disabled
candidates, and the inherited default so the lane can be restored without
editing source files. If every candidate is disabled, the effective route is
an explicit fail-closed lane; the Scheduler must not invent a replacement.

The alternate broker family is eligible only after a lane-specific approved
representation review. Its bars remain visibly attributed to that broker; it
is not assumed to be interchangeable with the primary broker's quote stream.

## 4. Source truth and failover doctrine

For one scheduled boundary, the Scheduler selects one route and one active
node. It must not request several providers simultaneously in an attempt to
manufacture a consensus bar.

The estate-default failover order is:

1. retry the active MT5 node within the SPEC-067 per-boundary attempt budget;
2. switch to a healthy approved standby or alternate MT5 node;
3. use the next reviewed Binance/CoinGecko candidate for a crypto lane;
4. use Yahoo where the lane has a reviewed, timeframe-capable representation;
5. use Twelve Data where the lane has a reviewed, timeframe-capable
   representation; and
6. enter a classified fail-closed or attention state when no approved route can
   serve the boundary.

The Scheduler follows the effective lane order after disabled candidates have
been removed. Under the estate default it must not jump directly from MT5 to
Twelve Data while an applicable crypto or Yahoo route is executable. An active
lane override may deliberately do so, and the event must cite the override
revision and operator reason.

Each route change creates an operational event containing the prior and new
source identity, reason, route-manifest revision, boundary, and bridge receipt
identifier. It must not overwrite existing canonical bars merely because the
preferred source later returns. Any re-acquisition or reconciliation of an
already admitted boundary is a reviewable evidence operation.

No route may silently:

* blend OHLC values from brokers or vendors;
* forward-fill a missed source bar;
* treat a broker suffix such as `.r` as proof of equivalence;
* replace a listed-equity `D1` series with a CFD representation without an
  explicit route decision; or
* alter historical provenance during recovery.

## 5. Capacity and temporary outcomes

MT5 capacity is governed by observed network latency, terminal health,
bridge-worker concurrency, queue age, and evidence-admission capacity. It has
no artificial provider-credit budget.

Twelve Data capacity remains governed by its approved credit window. The
following outcomes are always temporary and must preserve the same required
boundary in the update register:

```text
WAITING_FOR_CREDIT_WINDOW
WAITING_FOR_RATE_BUDGET
WAITING_FOR_NODE_CAPACITY
WAITING_FOR_PROVIDER_COOLDOWN
RETRYING_TRANSIENT_PROVIDER_FAILURE
```

For a temporary outcome, the Scheduler must record a calculated next wake and
automatically re-plan the lane at that time. It must not create a manual
request, claim `NO_ELIGIBLE_PROVIDER`, or require the operator to rediscover a
normal capacity release.

`NO_ELIGIBLE_PROVIDER` is permitted only when every approved route is
structurally ineligible, for example an unreviewed mapping, unsupported
timeframe, unavailable entitlement, or missing credential.

## 6. Bridge contract and local recovery evidence

Each bridge publishes authenticated health and receipt metadata. It receives
work from Fragarach and returns evidence; it does not receive SQLite database
access.

Required node status:

```text
node identity and software revision
broker family and terminal identity
bridge and terminal heartbeat
terminal authorisation/connectivity state
clock offset
active request count and queue age
last completed receipt per symbol/timeframe
local receipt-spool age, count, hash state, and free capacity
supported terminal symbols and timeframe capability revision
```

Raw provider responses and normalized bridge receipts are retained locally for
the active recovery window, initially **72 hours**. They must have a content
hash, request identity, source timestamp, symbol, timeframe, and node identity.
Recovery uses a normal queued admission path and all ordinary validation; a
local bridge archive can never bypass provenance or validation.

## 7. Single-writer boundary

The canonical authority database has exactly one live admission owner.

```text
provider or MT5 node → receipt inbox → Scheduler admission owner → canonical DB
```

The admission owner records process identity, lease token, release identity,
operation ID, and commit result. A second candidate owner must fail before any
write with a diagnostic naming the lease holder. A monitor may report and
request managed recovery but cannot acquire a writer lease or write authority
state itself.

This boundary applies equally to MT5 recovery imports, replica publication,
manual ingestion, and Scheduler dispatch.

## 8. Honest health model

The native app must display four separate operational facts:

| Surface | Question answered |
| --- | --- |
| Scheduler service | Is the process alive, progressing, and the sole writer? |
| MT5 nodes | Which bridge nodes are reachable and able to supply approved receipts? |
| Acquisition | Which lanes are ready, waiting for capacity, retrying, or structurally blocked? |
| Estate truth | Are the required canonical lanes current and viable? |

An estate with critical blocked or behind lanes must not present an overall
healthy state merely because a process heartbeat is current. The display must
show the blast radius, exact reason, next automatic action, and next expected
recovery time.

## 9. Retention and storage

Canonical evidence, provenance, and the current live authority database are
not disposable operational cache.

Local pre-change database snapshots are limited to a **72-hour** recovery
window. Their creation, size, source revision, expiry, and deletion action must
be recorded. On expiry they are removed through a bounded retention job; they
are not allowed to accumulate indefinitely beside the live database.

No snapshot deletion may target the current authority database, its active WAL,
or a live receipt spool. A retention job must first prove that a snapshot is
outside the recovery window and is not open by a process.

Storage health policy:

```text
warning: below 20% free
protect normal acquisition: below 15% free
controlled fault: below 10% free or 150 GiB, whichever is greater
```

The service-status heartbeat and monitor publication must have reserved local
capacity so a full evidence volume cannot suppress the evidence that the
service is unhealthy.

## 10. Release discipline

Production Scheduler and bridge services must run an identified release bundle
and pinned route-manifest revision. They must not execute from a mutable
development checkout.

A promotion records:

```text
application and bridge release identities
route-manifest revision
database compatibility revision
provider/node capability revisions
test and acceptance results
rollback release identity
```

Configuration or source changes require shadow-plan validation before they can
become active routing decisions.

## 11. Rollout

### Phase A — Stabilise and instrument

* classify current `CREDIT_WINDOW` blocks as temporary capacity waits;
* publish truthful service, acquisition, bridge, and estate states;
* inventory current writers, route revisions, runtime snapshots, and storage;
* stop release drift by identifying the actual running bundle.

### Phase B — Route-manifest and queue cutover

* introduce the MT5-primary intraday route manifest in shadow mode;
* prove route selection and receipt provenance without canonical writes;
* migrate temporary waits to automatic scheduled re-planning;
* activate the estate-wide default order plus exact-lane override model and
  retain each provider only in an approved, applicable lane position.

### Phase C — Single-writer and release cutover

* route all bridge evidence through the receipt inbox and admission owner;
* deploy an immutable Scheduler release with a pinned manifest;
* run the current MT5 node as the only active production node.

### Phase D — Resilience expansion

* provision the same-broker standby node at the second location;
* validate node failover without source blending;
* provision and review the alternate broker-family node;
* activate only approved lane representations on that node.

## 12. Acceptance gates

The design is accepted only when automated and live tests prove:

1. an MT5-primary intraday lane selects the correct approved node and retains
   its complete receipt provenance;
2. a same-broker node failure fails over without duplicate canonical admission;
3. an alternate-broker route cannot activate without a reviewed representation;
4. a non-overridden MT5 crypto-lane failure selects a reviewed
   Binance/CoinGecko candidate before Yahoo or Twelve Data;
5. a non-overridden D1 stock/ETF lane with no executable MT5 route selects
   Yahoo before Twelve Data when both are reviewed;
6. no inapplicable Binance/CoinGecko route is offered to a non-crypto lane;
7. under estate defaults, Twelve Data is not selected while an earlier
   reviewed candidate is executable;
8. a Twelve Data credit-window exhaustion becomes a timed wait and restores
   automatically without a manual request;
9. no process other than the admission owner can write canonical evidence;
10. bridge-local recovery receipts cannot bypass validation or alter existing
   provenance;
11. the app cannot show overall healthy while critical lanes are blocked;
12. an expired snapshot is eligible for retention cleanup while the active
   canonical database, WAL, and live spools are protected;
13. fourteen continuous days show no writer-lock restart and no temporary
   capacity condition promoted to a terminal provider failure;
14. an exact-lane override can disable MT5 and select an approved Twelve Data
   route without changing any other symbol/timeframe lane;
15. an exact-lane override can reorder reviewed candidates across the default
   tiers and the Scheduler follows that effective order;
16. restoring a lane to estate defaults removes its override through a new
   audited revision and reinstates the currently applicable inherited order;
   and
17. disabling every candidate in one lane creates an explicit fail-closed
   state and cannot cause an unreviewed or disabled provider to be selected.
