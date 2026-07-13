# SPEC-025 — Core Multi-Timeframe Authority

**Document ID:** `SPEC-025_CORE_MULTI_TIMEFRAME_AUTHORITY`

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`

**Date:** `2026-07-13`

**Baseline:** `Fragarach II v1.0a`

**Status:** `DRAFT FOR OPERATOR APPROVAL — AMENDED`

**Revision:** `1 — Precision Amendments`

**Classification:** `Cross-Foundation Operational Evolution`

**Doctrine:** `Operations is King / Authority First / Zero Blocking`

---

# 1. Executive Decision

Fragarach II shall extend its stable D1 historical authority into one coherent core multi-timeframe authority supporting:

```text
D1
H1
M30
M5
```

for:

```text
Forex
Metals
Energy
Indices
Crypto
```

Stocks remain intentionally D1-only under this specification. Missing H1, M30, or M5 stock lanes are expected policy, not faults, warnings, coverage gaps, or Truth penalties.

The implementation shall extend the v1.0a chain:

```text
Canonical Registration
        ↓
Timeframe Evidence Lane Authority
        ↓
Provider Acquisition
        ↓
Immutable Evidence
        ↓
Row-Level Quarantine
        ↓
Validation
        ↓
Truth
        ↓
Estate Truth
        ↓
SPEC-018
        ↓
Consumers
```

It shall not create a parallel intraday architecture.

Implementation is not authorised until this specification is approved by the operator.

---

# 2. Governing Direction

This specification translates the accepted direction in:

```text
Fragarach II — Core Multi-Timeframe Authority Direction
Date: 2026-07-13
```

The following work remains paused until this authority is operationally accepted:

- Sea Eagle integration;
- Market Scout integration;
- Signal Bars integration;
- HARP operational confirmation.

No downstream consumer shall compensate for missing Fragarach timeframe authority by acquiring, repairing, resampling, substituting, or synthesising market bars.

---

# 3. Baseline Protection

The designated `v1.0a` baseline is the recovery point and compatibility floor. This wording does not assert that a repository tag already exists. If a tag is later created, it shall point to the accepted recovery commit and shall not redefine the baseline.

Implementation MUST preserve:

- every accepted D1 registration, bar, raw block, provenance event, rejection, ingest run, validation summary, Truth result, and authority event;
- the immutable evidence and append-only authority doctrines;
- the canonical registration identity and provider abstraction;
- current row-level quarantine and affected-lane-only failure behaviour;
- current Truth Engine ownership of Symbol × Timeframe Truth;
- current Estate Truth ownership of estate aggregation;
- SPEC-018 consumer independence and read-only service boundary;
- retirement, reactivation, and permanent-removal lifecycle semantics;
- Estate → Market → Subgroup → Symbol navigation;
- the signed native Operations Console as the operational acceptance surface.

No implementation step may reinterpret an existing D1 timestamp, modify an accepted D1 value, replace an existing D1 lane, or cause a D1-only consumer to change behaviour.

If an implementation checkpoint causes D1 regression, that checkpoint is rejected and shall be restored to the `v1.0a` recovery baseline.

---

# 4. Timeframe Roles

The core timeframes have fixed operational roles:

| Timeframe | Role |
|---|---|
| D1 | Strategic history and long-horizon authority |
| H1 | Primary operational timeframe |
| M30 | Intermediate structure |
| M5 | Core serving floor |

This specification does not authorise lower timeframes, tick data, order-book data, or derived bars.

Each Symbol × Timeframe is an independent authority lane. Bars, validation, CAODT, coverage, freshness, gaps, Truth, provider state, and availability MUST NOT be combined across timeframes.

---

# 5. Required Market Policy

The operational policy matrix is normative:

| Market | D1 | H1 | M30 | M5 |
|---|---:|---:|---:|---:|
| Forex | Required | Required | Required | Required |
| Metals | Required | Required | Required | Required |
| Energy | Required | Required | Required | Required |
| Indices | Required | Required | Required | Required |
| Crypto | Required | Required | Required | Required |
| Stocks | Required | Intentionally deferred | Intentionally deferred | Intentionally deferred |

`INTENTIONALLY_DEFERRED` is a healthy policy state. It MUST NOT:

- produce an unavailable-lane alert;
- reduce market or Estate Truth;
- count against coverage;
- appear as a registration, provider, ingestion, validation, or consumer failure;
- offer acquisition controls;
- be returned as `NO_HISTORY` for a lane advertised as servable.

Existing constitutional equity timeframe documents remain preserved. Their presence does not activate stock intraday operation under this specification.

---

# 6. Current Compatibility Boundary

The repository already contains constitutional D1/H1/M30/M5 authorities for the target markets and Twelve Data contracts:

```text
TWELVE_DATA_TIME_SERIES_D1_V1
TWELVE_DATA_TIME_SERIES_H1_V1
TWELVE_DATA_TIME_SERIES_M30_V1
TWELVE_DATA_TIME_SERIES_M5_V1
```

Document or contract presence alone is not operational capability.

At specification date, the following runtime boundaries remain D1-only and therefore require explicit, tested evolution:

- canonical registration creation and discovery planning;
- bar-to-registration storage enforcement;
- manual/common staging validation;
- Twelve Data acquisition and adapter wiring;
- Yahoo fallback;
- calendar loading and expected-session generation;
- session, alignment, freshness, and gap validation;
- native acquisition commands and refresh projection;
- some provider resolution and Truth lookup paths;
- authority-ledger activation rules for H1, M30, and M5.

The first implementation task shall be a compatibility preflight identifying the exact files, triggers, contracts, commands, tests, and native boundaries affected. No broad rewrite is authorised.

---

# 7. Authority Model

## 7.1 Canonical registration anchor

The accepted v1.0a registration remains the canonical instrument identity anchor.

For an instrument registered at D1:

```text
Registration: XAGUSD / D1
        ├── Evidence Lane: XAGUSD / D1
        ├── Evidence Lane: XAGUSD / H1
        ├── Evidence Lane: XAGUSD / M30
        └── Evidence Lane: XAGUSD / M5
```

H1, M30, and M5 MUST NOT create duplicate canonical registrations, identities, aliases, or provider mappings merely to satisfy a timeframe key.

An intraday lane binds to the existing canonical registration through the Evidence Lane Authority and immutable authority ledger. Registration lifecycle state applies to all lanes belonging to that identity:

- retirement removes the identity's lanes from active serving;
- reactivation restores eligible existing lanes without recreating evidence;
- permanent removal follows SPEC-023 and does not silently erase retained evidence history.

## 7.2 Timeframe lane identity

Every active lane MUST have one stable authority identity containing or binding:

- canonical registration identity;
- canonical symbol;
- timeframe;
- market family;
- provider mapping identity;
- provider contract;
- entitlement state;
- timeframe authority document;
- calendar/session authority;
- timestamp meaning;
- alignment rule;
- effective range;
- activation state.

The ledger remains the versioned source for declarations, mapping revisions, entitlement facts, effective ranges, authority bindings, compatibility findings, and supersession.

Accepted authority rows are never edited to simulate a new timeframe state.

## 7.3 Policy and activation states

Timeframe policy and lane activation are separate dimensions and MUST NOT be collapsed into one state machine.

The deterministic timeframe policy states are:

```text
REQUIRED
INTENTIONALLY_DEFERRED
NOT_AUTHORISED
```

The deterministic lane authority states are:

```text
CAPABILITY_UNKNOWN
MAPPING_REQUIRED
ENTITLEMENT_UNKNOWN
DECLARED
ACTIVE_NO_EVIDENCE
ACTIVE
RETIRED
REMOVED
BLOCKED
```

`INTENTIONALLY_DEFERRED` is a healthy policy state, not a lane lifecycle or acquisition state. A deferred timeframe does not require an active lane row and MUST NOT enter provider, ingestion, validation, Truth, or failure calculations.

Only lanes with policy state `REQUIRED` and authority state `ACTIVE_NO_EVIDENCE` or `ACTIVE` may be selected for acquisition. Only `ACTIVE` lanes containing servable canonical evidence may be advertised by SPEC-018 as available history.

`BLOCKED` applies only to the affected Symbol × Timeframe and MUST contain explicit reason codes. It never blocks unrelated lanes.

---

# 8. Capability Projection

Estate Truth and SPEC-018 shall expose a single authoritative capability projection. SwiftUI and consumers shall not infer it from the presence of bars, configuration files, authority documents, or neighbouring timeframes.

For each symbol, the projection MUST identify:

```text
market_policy
authorised_timeframes
declared_timeframes
active_timeframes
servable_timeframes
intentionally_deferred_timeframes
blocked_timeframes
```

For each timeframe it MUST identify:

```text
policy_state
authority_state
provider_mapping_state
provider_contract
entitlement_state
evidence_state
validation_state
truth_state
servable
reason_codes
```

These sets have distinct meanings:

- `authorised_timeframes`: constitutional authority exists;
- `declared_timeframes`: a reviewed evidence lane has been declared;
- `active_timeframes`: acquisition and validation are operationally enabled;
- `servable_timeframes`: canonical history and Truth are available to consumers.

No broader set may be substituted for a narrower set.

---

# 9. Persistence Amendment

The implementation preflight shall propose one forward-only, checksummed migration if storage enforcement must change. The migration requires operator approval before execution.

The intended minimal persistence evolution is:

1. preserve the canonical D1 registration row as the instrument identity anchor;
2. preserve `bars` uniqueness by `(asset, timeframe, timestamp)`;
3. preserve `evidence_lanes` as the Symbol × Timeframe lane boundary;
4. replace same-timeframe registration enforcement for intraday bar writes with enforcement that requires:
   - the canonical registration anchor;
   - a matching declared and active Evidence Lane Authority;
   - a compatible provider mapping and contract;
5. preserve the current accepted application-table boundary confirmed by compatibility preflight, unless that preflight proves a constitutional incompatibility and a separate foundation amendment is approved;
6. preserve every existing migration name, statement, and checksum;
7. perform rollback by verified database restoration, never destructive reverse mutation.

Direct SQLite writes remain forbidden. All declarations, acquisitions, and evidence writes use registered service boundaries and single-writer discipline.

The existing ledger rule preventing intraday activation may be superseded only for an affected lane after all authority, provider, ingestion, validation, Truth, service, and native gates for that timeframe have passed.

---

# 10. Provider Acquisition

## 10.1 Twelve Data

Twelve Data remains the primary provider. Requests MUST use the exact approved contract for the requested timeframe:

| Timeframe | Contract | Provider interval |
|---|---|---|
| D1 | `TWELVE_DATA_TIME_SERIES_D1_V1` | `1day` |
| H1 | `TWELVE_DATA_TIME_SERIES_H1_V1` | `1h` |
| M30 | `TWELVE_DATA_TIME_SERIES_M30_V1` | `30min` |
| M5 | `TWELVE_DATA_TIME_SERIES_M5_V1` | `5min` |

Each request MUST obey its contract's request ceiling, hard maximum, bounds, sorting, truncation detection, timezone rule, timestamp authority, and overlap authority.

A provider mapping proven for one timeframe MUST NOT be treated as proof of entitlement or valid response semantics for another timeframe. Shared provider symbol text may be reused only through an explicit timeframe-capability projection.

## 10.2 Fallback

Fallback is timeframe-specific authority, not a generic provider switch.

The existing Yahoo fallback remains D1-only until reviewed Yahoo H1, M30, or M5 contracts and mappings are separately approved and implemented. For an intraday lane without an approved fallback, the factual state is:

```text
NO_APPROVED_FALLBACK
```

This state is visible but does not block acquisition from a healthy primary provider. The system MUST NOT request D1 fallback data for an intraday lane, relabel an interval, or resample fallback bars.

## 10.3 Entitlement and limits

Provider entitlement, historical-depth limits, rate limits, and unavailable ranges MUST remain explicit per provider mapping and timeframe. Unknown remains `ENTITLEMENT_UNKNOWN`; it is never converted into supported or unsupported by inference.

Provider failure affects only the requested lane. Successful evidence already held remains readable.

---

# 11. Immutable Evidence and Ingestion

All existing evidence doctrine applies independently to D1, H1, M30, and M5.

For every acquisition:

- raw provider bytes are preserved before canonical acceptance when preservation is authorised;
- raw blocks and checksums are immutable;
- every canonical row has provenance to its exact raw evidence and source row;
- accepted canonical bars are append-only under the existing merge doctrine;
- overlap is handled by explicit authority, never silent overwrite;
- rejected rows and rejection reasons are retained;
- one invalid row does not prevent valid rows from the same response from being accepted;
- retry is idempotent;
- H1, M30, and M5 timestamps are stored as exact UTC interval-open instants;
- accepted D1 timestamp and date semantics remain exactly as defined by the v1.0a authority and MUST NOT be reinterpreted, converted, or migrated by this specification;
- date-only staging remains valid only for D1;
- no bar is generated, filled, interpolated, rolled up, or downsampled by this specification.

Common staging shall accept intraday timestamps only when the exact source timestamp text, timezone interpretation, interval meaning, and canonical UTC conversion are preserved in provenance.

---

# 12. Timeframe Validation

Validation remains descriptive and non-destructive. It does not acquire, repair, or fabricate evidence.

Each active lane MUST validate against the exact market and timeframe authority. At minimum validation shall cover:

- canonical timestamp parsing;
- interval-open alignment;
- strictly ordered unique timestamps;
- OHLC and numeric invariants;
- provider response interval consistency;
- closed-bar status at acquisition time;
- applicable trading sessions;
- market timezone and UTC conversion;
- daylight-saving transitions;
- holidays and exceptional closures where applicable;
- expected interval coverage within each session;
- gaps and outside-session evidence;
- CAODT and latest expected closed interval.

Validation profiles shall distinguish:

- weekday/market-session instruments;
- exchange-session instruments;
- continuous Crypto instruments;
- representation-specific sessions such as cash index, CFD, spot, or futures.

A session profile valid for one representation MUST NOT be assigned to another by symbol resemblance.

Open or not-yet-due intervals are not gaps. Closed expected intervals missing from evidence are classified by the existing Gap Doctrine extended through the owning timeframe authority.

---

# 13. Truth and Estate Truth

The Truth Engine remains the sole calculator of Symbol × Timeframe Truth. Its explainable components and operational colour rules are preserved.

Multi-timeframe implementation shall:

- calculate Truth independently for every active lane;
- derive freshness from that lane's latest expected closed interval;
- derive coverage and continuity from that lane's timeframe-aware validation;
- preserve unknown provider confidence as `NOT_MEASURED`;
- never borrow D1 Truth for H1, M30, or M5;
- never penalise an intentionally deferred stock timeframe.

Estate Truth remains the sole estate aggregator. It shall add authoritative market, symbol, and timeframe capability projections and aggregate only lanes required by current market policy.

Presentation clients may filter and navigate Estate Truth. They MUST NOT calculate capability, Truth, coverage, freshness, or estate health.

---

# 14. SPEC-018 Compatibility

SPEC-018 remains Fragarach's versioned, read-only external consumer contract.

The existing request remains:

```text
get_history(symbol, timeframe)
```

The D1 response contract and existing D1 acceptance dataset MUST remain semantically backward compatible. Existing consumers must receive the same canonical D1 meaning, ordering, values, ranges, and response behaviour. Additive metadata is permitted only through the existing contract-versioning discipline and does not imply byte-for-byte response identity.

The catalog operation shall expose servable D1, H1, M30, and M5 lanes plus the authoritative capability projection. Consumers MUST discover availability; they shall not assume that every symbol has every timeframe.

Requests shall return factual states:

- `AVAILABLE` only for a servable lane;
- `NOT_REGISTERED` for an unknown canonical identity;
- `NO_HISTORY` for an authorised active lane without servable evidence;
- `TIMEFRAME_NOT_ACTIVE` for known but undeclared, blocked, or not-yet-activated authority;
- `INTENTIONALLY_DEFERRED` for stock H1, M30, and M5 under this policy;
- `RETIRED` or `REMOVED` according to lifecycle authority.

Unavailable responses contain no fabricated bars. A new response state or capability field shall be introduced through the existing versioning discipline and MUST NOT break D1 consumers.

Sea Eagle, Market Scout, Signal Bars, and HARP remain paused until the operator accepts this contract from the signed application and an external read-only verification proves the same authority.

---

# 15. Native Operations Console

The signed native application is the commissioning surface.

For a selected symbol, the operator shall see one truthful timeframe state for D1, H1, M30, and M5, including:

- policy and activation state;
- provider and mapping;
- entitlement and fallback state;
- evidence range and bar count;
- validation state;
- Truth, status colour, coverage, freshness, and CAODT;
- exact blocked or unavailable reasons;
- acquisition and refresh actions only when eligible.

The hierarchy introduced by SPEC-024 remains unchanged. Timeframes are a symbol authority dimension, not a new navigation hierarchy.

The operator shall be able to:

```text
Estate
  ↓
Market
  ↓
Subgroup (where applicable)
  ↓
Symbol
  ↓
Timeframe
  ↓
Acquire / Refresh
  ↓
Validate
  ↓
Truth and CAODT refresh
```

No database edit, command-line tool, application restart, or hidden maintenance action may be required.

Stocks shall show D1 as the active policy and H1/M30/M5 as intentionally deferred without warning colour or acquisition actions.

---

# 16. Delivery Order and Gates

Implementation shall proceed in this exact market order:

```text
1. Forex
2. Metals
3. Energy
4. Indices
5. Crypto
```

Within each market, activate in this order:

```text
H1
 ↓
M30
 ↓
M5
```

One lane vertical slice must pass before broad market rollout. One timeframe must pass its complete gate before the next timeframe begins.

Each activation gate includes:

1. authority and capability projection;
2. provider mapping and entitlement fact;
3. acquisition using the exact timeframe contract;
4. immutable raw evidence and row provenance;
5. row-level quarantine proof;
6. timeframe-aware validation;
7. Truth and Estate Truth projection;
8. SPEC-018 discovery and history service;
9. signed native acquisition and refresh;
10. D1 non-regression proof.

Bulk onboarding, provider expansion, higher timeframes, and consumer integration are outside the activation gate.

---

# 17. Acceptance

SPEC-025 requires both signed-native operator acceptance and deterministic technical evidence. These are complementary gates and MUST NOT be substituted for one another.

## 17.1 Signed native operator acceptance

The operator must complete the following from the signed native application for at least one reviewed symbol in every commissioned market and for every distinct commissioned session or representation profile.

The representative set MUST cover, at minimum:

- a weekday or market-session Forex representation;
- each commissioned Metals session or representation profile;
- each commissioned Energy session or representation profile;
- each commissioned Indices session or representation profile, such as cash, CFD, or another explicitly authorised representation;
- continuous Crypto;
- D1-only Stocks policy behaviour.

One symbol may satisfy more than one requirement only when it genuinely exercises the same reviewed session and representation authority. Symbol resemblance is not sufficient.

For each required representative:

```text
Open symbol
  ↓
Select H1
  ↓
Acquire or refresh
  ↓
Observe accepted evidence and any factual warnings or quarantined rows
  ↓
Observe validation
  ↓
Observe H1 Truth and CAODT
```

Repeat for M30 and M5 in the required delivery order.

The operator must additionally verify:

- D1 remains selectable, readable, refreshable, and unchanged;
- no invalid interval is silently realigned;
- no incomplete current interval is admitted as a closed bar;
- global search finds the symbol regardless of selected hierarchy context;
- Estate and market scorecards refresh from Estate Truth rather than SwiftUI calculation;
- SPEC-018 catalogs and returns the same accepted lanes and exact bar ranges;
- a stock such as AAPL remains healthy at D1 and reports H1/M30/M5 as intentionally deferred without alerts;
- retirement and reactivation preserve all existing timeframe evidence;
- provider failure on one Symbol × Timeframe leaves unrelated lanes operational;
- the workflow requires no database edit, CLI command, application restart, test-fixture injection, or hidden maintenance action.

The signed native application acceptance uses genuine operational provider or approved replay workflows. Production UI controls MUST NOT be added solely to inject malformed test fixtures.

## 17.2 Deterministic technical evidence

Focused automated or approved replay verification MUST prove that:

- one mixed valid/invalid provider payload accepts valid rows and quarantines only invalid rows;
- exact rejection reasons and source-row provenance are retained;
- retry remains idempotent;
- malformed, misaligned, outside-contract, and incomplete-current-interval observations are not silently corrected or admitted;
- the affected-lane-only failure boundary holds;
- D1 semantics and accepted D1 consumer behaviour do not regress.

This deterministic fixture or replay proof belongs in focused tests and the commissioning evidence. It is not a requirement to expose fixture injection through the signed Operations Console.

The application used for acceptance MUST be rebuilt from the approved commit and signed. The accepted commit hash, bundle version, database migration state, representative symbols, session and representation profiles, lane ranges, bar counts, Truth values, deterministic fixture results, and screenshots shall be recorded in the commissioning report.

**A feature is not accepted until the operator can successfully execute the complete workflow from the signed native application. Backend implementation alone is insufficient.**

---

# 18. Verification Budget

For each timeframe activation checkpoint run:

- focused storage and migration tests;
- focused provider-contract and acquisition tests;
- focused staging, quarantine, provenance, and idempotency tests;
- focused session, alignment, gap, and freshness validation tests;
- focused Truth, Estate Truth, and SPEC-018 contract tests;
- focused Swift bridge and native UI tests;
- one release-style native build;
- one signed native launch and operator workflow;
- one focused D1 non-regression suite.

Do not run unrelated full regression suites unless a focused failure establishes broader risk.

---

# 19. Forbidden

Do not:

- redesign canonical registration;
- create one canonical registration per timeframe;
- replace the immutable evidence model;
- redesign the Truth Engine or Estate Truth hierarchy;
- introduce consumer-specific acquisition or scoring;
- change the SPEC-018 request shape;
- synthesize H1, M30, or M5 from another timeframe;
- resample provider data within this specification;
- infer provider entitlement or fallback support;
- treat authority-document presence as operational activation;
- silently align, overwrite, repair, or discard provider rows;
- block unrelated lanes because one lane fails;
- count intentionally deferred stock intraday lanes as unhealthy;
- activate all markets or timeframes in one uncommissioned change;
- resume paused consumers before signed native acceptance;
- use direct SQLite manipulation as an operational step.

---

# 20. Completion State

SPEC-025 is complete when Fragarach II is the demonstrably operational authority for D1, H1, M30, and M5 across Forex, Metals, Energy, Indices, and Crypto; remains intentionally D1-only for Stocks; preserves v1.0a D1 authority; exposes exact capability through Estate Truth and SPEC-018; and permits the operator to acquire, validate, inspect, and serve every commissioned lane from the signed native application.

Until every acceptance condition is proven, the correct status is:

```text
SPEC-025 — NOT ACCEPTED
```
