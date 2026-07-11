# CRYPTO BASE DOCTRINE V1

**Document Class:** Constitutional Market Authority  
**Authority Layer:** Market Ecosystem  
**Authority Name:** `CRYPTO_BASE_DOCTRINE_V1`  
**Market Name:** Cryptoassets  
**Market Code:** `CRYPTO`  
**Version:** 1.0  
**Status:** DRAFT FOR APPROVAL  
**Repository Location:** `constitution/doctrines/CRYPTO_BASE_DOCTRINE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Effective From:** Not effective until approved  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** PENDING  
**Approval Date:** PENDING

---

# 1. Purpose

This doctrine defines the constitutional operational truth for the Cryptoasset market ecosystem within Fragarach II.

It establishes the market-wide authority inherited by every crypto timeframe authority, evidence lane, acquisition specification, validator, native operation, migration, and acceptance proof.

It defines:

- the crypto market boundary;
- crypto instrument and pair membership;
- the continuous UTC calendar;
- UTC day, week, and month ownership;
- venue and aggregate-source treatment;
- approved provider roles;
- acceptable evidence and provenance;
- price and volume semantics;
- market-wide validation and conflict rules;
- token, network, fork, migration, listing, and delisting authority;
- effective historical range;
- the boundary between market authority and timeframe authority.

This doctrine does not define interval-specific bar alignment, provider interval codes, request chunking, or latest-closed-bar calculations. Those matters belong to approved crypto timeframe authorities.

---

# 2. Constitutional Position

```text
Constitution

↓

CRYPTO_BASE_DOCTRINE_V1

↓

CRYPTO Timeframe Authority

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides this doctrine;
2. this doctrine overrides subordinate crypto timeframe authorities;
3. approved timeframe authorities override implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing authority.

A venue API default, provider chart, ticker string, or existing application behaviour is not constitutional authority unless expressly adopted.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate document may weaken a mandatory requirement in this doctrine.

---

# 4. Market Definition

## 4.1 Market Identity

The Cryptoasset market is a continuous, multi-venue ecosystem in which digital assets, tokens, or registered crypto-native units are priced against fiat currencies, stable-value assets, or other cryptoassets.

The market has no universal central exchange, universal consolidated last price, universal volume, or universal trading-halt authority.

An instrument may trade:

- on one centralised venue;
- on multiple centralised venues;
- through decentralised protocols;
- through an approved provider aggregate;
- across materially different liquidity pools.

Evidence may differ legitimately because of:

- venue-specific order books;
- liquidity and spread;
- trade eligibility;
- geographic restrictions;
- asset or network representation;
- provider aggregation;
- stablecoin quote behaviour;
- outages and maintenance;
- listing and delisting times.

Provider or venue disagreement is not, by itself, proof that either evidence source is invalid.

## 4.2 Classification

**Asset Class:** `CRYPTOASSET`  
**Venue Model:** Multi-venue centralised, decentralised, and aggregate-source ecosystem  
**Trading Model:** Continuous, 24 hours per day and seven days per week  
**Canonical Calendar Timezone:** `UTC`  
**Quote Convention:** Base asset priced in quote asset

## 4.3 Included Scope

This doctrine includes:

- registered spot cryptoasset pairs;
- registered fiat-quoted spot pairs;
- registered stablecoin-quoted spot pairs;
- registered crypto-cross pairs;
- approved provider aggregates with declared venue scope and price basis;
- token histories with explicit identity, network, and effective range.

## 4.4 Excluded Scope

This doctrine excludes:

- perpetual swaps;
- dated futures;
- options;
- leveraged tokens unless separately authorised;
- prediction-market contracts;
- crypto equities and exchange-traded funds;
- staking-yield series;
- on-chain metrics that are not price bars;
- indices and baskets unless separately governed;
- wrapped, bridged, synthetic, or derivative representations unless separately registered;
- calculated cross rates unless expressly authorised.

Excluded instruments require another authority or separate registered instrument class.

---

# 5. Instrument Membership Authority

## 5.1 Membership Rule

An instrument belongs to crypto only when:

1. base asset is explicit;
2. quote asset is explicit;
3. the pair or provider aggregate is registered;
4. venue or aggregation scope is declared;
5. provider mappings are registered;
6. price basis is declared;
7. launch or listing boundary is known;
8. retirement or delisting boundary is known where applicable;
9. network, token contract, or asset identity is recorded where ticker ambiguity is material;
10. it is not assigned to another market doctrine.

Ticker spelling alone does not establish asset identity or market membership.

## 5.2 Canonical Symbol

The default canonical pair symbol is:

```text
BASEQUOTE
```

Examples:

```text
BTCUSD
ETHUSD
SOLUSD
BTCUSDT
ETHBTC
```

The canonical symbol does not, by itself, identify:

- venue;
- network;
- contract address;
- wrapped status;
- aggregate methodology;
- quote-asset risk.

Those facts MUST be registered where material.

## 5.3 Required Metadata

Every crypto registration MUST include:

- canonical symbol;
- controlled display name;
- market code `CRYPTO`;
- asset class `CRYPTOASSET`;
- controlled instrument type;
- base asset;
- quote asset;
- venue or aggregate scope;
- price basis;
- price precision;
- quantity precision where volume exists;
- canonical timezone `UTC`;
- calendar authority reference;
- provider symbol mappings;
- launch or listing effective date;
- delisting or retirement date where known;
- operational status;
- registration and approval provenance.

Where material, registration MUST also include:

- network or chain;
- token contract or canonical asset identifier;
- native, wrapped, bridged, or synthetic status;
- redenomination factor;
- migration or fork lineage;
- stablecoin or fiat quote classification.

## 5.4 Asset Identity

A ticker is not a permanent unique identity.

Asset identity MUST account for:

- ticker reuse;
- token contract replacement;
- chain migration;
- wrapped and bridged forms;
- rebranding;
- redenomination;
- token swap;
- hard fork;
- chain split or merge;
- provider remapping.

Implementation MUST NOT join histories solely because ticker text matches.

## 5.5 Quote Asset Classification

The quote asset MUST be classified as:

- fiat currency;
- stable-value cryptoasset;
- cryptoasset;
- another approved class.

A stablecoin quote MUST NOT be treated as legally or economically identical to fiat by assumption.

`BTCUSD` and `BTCUSDT` are distinct instruments and MUST remain distinct evidence lanes.

## 5.6 Prohibited Assumptions

Implementation MUST NOT invent:

- asset or quote identity;
- venue identity;
- aggregate scope;
- network or contract address;
- wrapped status;
- launch or delisting date;
- price basis;
- provider mapping;
- stablecoin equivalence;
- continuity across migrations or forks.

Missing authority requires a compatibility report for the affected path.

---

# 6. Canonical Crypto Calendar Authority

## 6.1 Calendar Identity

**Calendar Authority:** `CRYPTO_24X7_UTC_V1`  
**Calendar Type:** Continuous calendar  
**Timezone:** `UTC`

## 6.2 Continuous Operation

The canonical calendar is:

```text
24 hours per day
7 days per week
365 or 366 days per year
```

There is no canonical weekend closure.

There is no universal market holiday closure.

## 6.3 Operational Day

The canonical crypto day is the UTC civil day:

```text
[00:00:00 UTC, 00:00:00 UTC on the following date)
```

The day is owned by its UTC civil date.

## 6.4 Operational Week

The canonical crypto week is:

```text
Monday 00:00:00 UTC
through
following Monday 00:00:00 UTC
```

The week is owned by the UTC date of its Monday opening boundary.

A future W1 authority MUST preserve this boundary while defining exact timestamp semantics.

## 6.5 Operational Month

The canonical crypto month is:

```text
first day of month 00:00:00 UTC
through
first day of following month 00:00:00 UTC
```

A future MN1 authority MUST preserve this boundary while defining exact timestamp semantics.

## 6.6 Holidays

No civil or exchange holiday is a market-wide crypto closure.

Venue closure, maintenance, or trading halt is venue-specific unless approved evidence proves that the registered instrument did not trade within its declared scope.

## 6.7 Maintenance and Outages

Venue maintenance, chain interruption, provider outage, API outage, and network disruption are not automatically market closures.

They MUST be classified by affected scope:

- venue unavailable;
- provider unavailable;
- instrument halted;
- network disrupted;
- evidence unavailable;
- authority unresolved.

Provider silence MUST NOT be converted into a universal non-bar period.

## 6.8 Calendar Amendments

Calendar corrections MUST be versioned and auditable.

Historical day, week, or month ownership MUST NOT be silently changed.

---

# 7. Session Authority

## 7.1 Canonical Session

Crypto has no canonical trading-session open or close separate from the UTC calendar boundary.

The constitutional session model is:

```text
CRYPTO_CONTINUOUS_UTC_V1
```

with continuous eligibility after the instrument's effective start and before its effective end.

## 7.2 Analytical Sessions

Asia, Europe, London, and New York session labels MAY be used for analysis or display.

They are not constitutional crypto evidence-lane boundaries and MUST NOT redefine UTC alignment or ownership.

## 7.3 Venue-Specific Events

A venue-specific auction, maintenance period, settlement window, or trading halt MAY affect expected bars only when:

- venue scope is part of registration or provider definition;
- the event is supported by evidence;
- the applicable timeframe authority defines the operational consequence.

## 7.4 Precedence

```text
Approved instrument-specific exception

↓

Approved CRYPTO timeframe authority

↓

CRYPTO_BASE_DOCTRINE_V1

↓

Approved provider and venue semantics

↓

Implementation
```

Provider and venue conventions may map into constitutional truth. They do not override it.

---

# 8. Provider Authority

## 8.1 Approved Roles

| Source | Approved Role | Scope | Conditions |
|---|---|---|---|
| Twelve Data | Primary automated acquisition provider | Registered crypto instruments and approved crypto timeframes | Symbol mapping, venue or aggregate scope, and approved timeframe semantics MUST exist |
| Operator-supplied file | Manual evidence source | Registered crypto instruments and approved crypto timeframes | Origin, venue or provider scope, checksum, parser result, and provenance MUST be retained |
| Existing accepted immutable evidence | Historical evidence source | Evidence already accepted by Fragarach II | Original provenance remains immutable |

No direct exchange, decentralised protocol, or additional aggregate provider is approved by this version.

Additional providers require constitutional amendment or separate provider authority.

## 8.2 Provider Scope

Every provider mapping MUST declare whether evidence represents:

- one named venue;
- a named venue set;
- a provider aggregate;
- a reference price;
- another approved scope.

A matching symbol does not prove venue equivalence.

## 8.3 Provider Semantics Boundary

Each crypto timeframe authority MUST define, for every approved provider:

- interval code;
- timestamp meaning;
- request start and end semantics;
- inclusive and exclusive boundaries;
- row and span limits;
- pagination or cursor behaviour;
- chunking and overlap;
- response ordering;
- duplicate behaviour;
- partial-bar behaviour;
- empty-response meaning;
- revision behaviour;
- venue or aggregate scope;
- historical coverage.

Implementation MUST NOT proceed for a provider/timeframe combination until those facts are approved.

## 8.4 Provider Precedence

There is no market-wide rule that one venue or the newest response automatically wins.

Compatible conflicting evidence MUST be retained and resolved only by an approved lane-resolution rule.

Silent overwrite is prohibited.

---

# 9. Evidence Authority

## 9.1 Immutability

Accepted crypto evidence is immutable.

A correction requires new evidence, new provenance, a new validation result, and an auditable resolution decision.

## 9.2 Acceptable Sources

Acceptable sources are:

- approved provider API responses;
- approved provider exports;
- operator-supplied files with declared source and venue scope;
- existing immutable Fragarach II evidence;
- official venue or protocol publications only where separately authorised.

## 9.3 Evidence Identity

Every evidence block MUST identify:

- canonical instrument;
- source symbol;
- provider or source identity;
- source role;
- venue or aggregate scope;
- timeframe;
- requested and received ranges;
- observed timestamp range;
- row count;
- checksum;
- acquisition timestamp;
- parser or adapter version;
- price basis;
- volume basis where present;
- timestamp interpretation;
- evidence and validation status.

## 9.4 Prohibitions

Implementation MUST NOT:

- fabricate missing bars;
- mutate accepted evidence;
- discard venue conflicts without record;
- shift timestamps without approved mapping;
- merge venues by assumption;
- equate stablecoin and fiat quotes;
- join token histories by ticker alone;
- convert wrapped and native assets by assumption;
- create cross rates without construction authority.

---

# 10. Price and Volume Semantics

## 10.1 Price

Crypto OHLC evidence represents the provider's declared price basis within its declared venue or aggregate scope.

It is not a universal consolidated market price.

The price basis MUST be one of:

- last trade;
- provider aggregate;
- venue index;
- midpoint;
- bid;
- ask;
- another expressly approved basis.

Different venue scopes or price bases MUST NOT be merged without construction authority.

## 10.2 Quote Direction

For `BASEQUOTE`:

```text
one unit of BASE is priced in units of QUOTE
```

Pair inversion or stablecoin-to-fiat substitution requires approved transformation authority and provenance.

## 10.3 Volume

Crypto volume may mean:

- base-asset volume;
- quote-asset volume;
- trade count;
- venue-defined volume;
- aggregate provider volume;
- another declared measure.

Meaning and unit MUST be explicit.

Volume across venues or providers MUST NOT be treated as directly comparable without authority.

## 10.4 Zero, Null, and Absent Volume

Zero, null, or absent volume MAY be valid depending on source semantics.

Measured zero SHOULD remain distinguishable from absent or unknown volume.

Missing volume MUST NOT invalidate valid OHLC evidence unless the timeframe authority makes it mandatory.

## 10.5 Stablecoin Quote Risk

A stablecoin quote is a separate asset exposure.

A depeg does not retroactively convert the pair into a fiat-quoted series.

Stablecoin-to-fiat transformation is not authorised by this doctrine.

---

# 11. Market-Wide Validation Authority

## 11.1 Mandatory Validation

Every crypto row MUST be evaluated for:

- registered identity;
- registered base and quote assets;
- declared venue or aggregate scope;
- approved provider mapping;
- timestamp parseability and UTC interpretation;
- effective-range eligibility;
- numeric validity;
- OHLC consistency;
- price precision;
- monotonic ordering within the block;
- duplicate or conflict status;
- provenance completeness.

At minimum:

```text
high >= open
high >= close
low <= open
low <= close
high >= low
```

NaN and infinite OHLC values are invalid.

Negative crypto prices are invalid unless a named constitutional exception permits them.

A zero crypto price is invalid unless a named technical, launch, redenomination, or historical exception permits it.

## 11.2 Continuous Calendar Validation

After effective start and before effective end, intervals may be expected on every UTC day.

Weekend or civil holiday MUST NOT be treated as a valid non-bar period.

A missing bar may reflect:

- provider outage;
- venue outage;
- instrument halt;
- network interruption;
- lack of trades under an approved sparse-market rule;
- source truncation;
- unresolved authority.

Exact expectedness and materiality belong to the timeframe authority.

## 11.3 Lane Identity and Conflict

The constitutional lane key begins with:

```text
registered instrument + approved timeframe + canonical timestamp
```

Venue or aggregate scope MAY be an additional lane dimension where registration requires it.

Conflicts MUST NOT be resolved through silent replacement.

## 11.4 Severity

| Severity | Meaning | Operational Consequence |
|---|---|---|
| `INFO` | Observed non-error condition | Retain and report |
| `WARNING` | Non-fatal uncertainty | Continue with visible warning |
| `REJECT` | Constitutionally invalid evidence | Reject affected evidence and retain proof |
| `CONFLICT` | Compatible evidence disagrees | Retain all evidence and require resolution |
| `BLOCKED` | Required authority is missing | Stop only the affected path and emit compatibility report |

## 11.5 Operations Doctrine

Usable accepted evidence MUST remain available when a provider, venue, network, or newer acquisition is delayed, stale, incomplete, or under review.

Warnings MUST remain visible.

Missing authority stops only the affected acquisition, validation, construction, or migration path.

It MUST NOT unnecessarily disable unrelated lanes or the wider operations console.

**Operations is King.**

---

# 12. Structural Crypto Events

## 12.1 Governed Events

Crypto authority MUST account for:

- asset launch;
- pair listing and delisting;
- venue closure;
- token migration;
- contract replacement;
- chain migration;
- redenomination;
- rebranding and ticker change;
- hard fork;
- chain split or merge;
- wrapped or bridged representation;
- stablecoin depeg;
- exchange hack or insolvency;
- trading halt;
- network halt;
- provider aggregate methodology change.

## 12.2 Continuity Rule

No structural event automatically permits continuity.

Authority MUST decide:

- whether pre-event and post-event assets are the same identity;
- whether a new registration is required;
- whether one lane may span the event;
- whether scaling is authorised;
- whether historical evidence requires reclassification;
- the effective transition timestamp.

Implementation MUST NOT splice histories by assumption.

## 12.3 Fork Rule

A fork or chain split creates distinct asset identity unless explicit authority states otherwise.

Pre-fork history MAY be referenced analytically but MUST NOT be duplicated into descendant canonical lanes without approved lineage rules.

## 12.4 Migration and Redenomination

Migration or redenomination requires:

- old and new identifiers;
- effective timestamp;
- conversion ratio where applicable;
- source authority;
- lane-continuity decision;
- provenance for transformed data.

Silent rescaling is prohibited.

---

# 13. Effective Historical Range

## 13.1 Start Rule

There is no universal earliest date for all crypto instruments.

The lane start is the latest of:

1. constitutional asset launch or recognised existence;
2. pair listing or aggregate start;
3. approved provider coverage start;
4. earliest compatible evidence;
5. any instrument-specific authority date.

## 13.2 End Rule

The lane end is the earliest of:

- pair delisting;
- asset retirement;
- migration requiring a new identity;
- provider mapping termination;
- venue-scope termination;
- another approved structural event.

The default is `OPEN` only while no end condition applies.

## 13.3 Venue and Provider Coverage

A pair may exist on one venue before another.

Provider coverage does not establish universal market inception.

Historical evidence outside an approved identity, venue, or provider range may be retained but MUST NOT enter an active canonical lane until resolved.

---

# 14. Timeframe Inheritance

Every crypto timeframe authority MUST inherit:

- crypto market identity;
- instrument membership;
- base and quote semantics;
- venue or aggregate-scope requirement;
- continuous UTC calendar;
- absence of weekend and holiday closure;
- UTC day ownership;
- Monday-based UTC week boundary;
- UTC calendar-month boundary;
- provider roles;
- evidence immutability;
- price-basis and venue-scope provenance;
- volume semantics;
- structural-event rules;
- market-wide validation;
- effective-range logic.

A timeframe authority MUST NOT contradict these facts.

---

# 15. Required Crypto Timeframe Authorities

| Timeframe | Required Authority | Status |
|---|---|---|
| `D1` | `CRYPTO_D1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `H1` | `CRYPTO_H1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M30` | `CRYPTO_M30_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M5` | `CRYPTO_M5_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |

Additional timeframe authorities require an approved amendment or later doctrine version.

---

# 16. Explicit Delegation to Timeframe Authorities

The following are intentionally delegated:

- interval duration and alignment;
- canonical bar timestamp meaning;
- provider timestamp mapping;
- partial-bar and latest-closed-bar rules;
- direct versus derived precedence;
- rollup eligibility;
- sparse-trading expectedness;
- request codes, limits, pagination, chunking, and overlap;
- exact duplicate fields;
- gap materiality;
- freshness thresholds;
- timeframe-specific effective ranges.

These are not implementation choices.

Implementation MUST wait for approved timeframe authority.

---

# 17. Compatibility Requirements

Before a crypto implementation specification begins, it MUST prove that:

- this doctrine is approved;
- the relevant timeframe authority is approved;
- the instrument is registered as crypto;
- base and quote assets are explicit;
- venue or aggregate scope is explicit;
- provider mapping and role are valid;
- price and volume basis are explicit;
- effective range and structural-event state are resolved;
- no implementation-critical authority is missing.

Failure requires a compatibility report and stops the affected path.

---

# 18. Specification Boundary

Specifications MAY define:

- schemas;
- provider clients;
- parsers;
- acquisition orchestration;
- validation code;
- evidence storage;
- migrations;
- native workflows;
- reports, tests, and acceptance proof.

Specifications MUST NOT redefine:

- market boundary;
- asset or quote identity;
- venue or aggregate scope;
- continuous UTC calendar;
- UTC day, week, or month ownership;
- provider roles;
- price or volume meaning;
- structural-event meaning;
- effective-range authority.

---

# 19. Implementation Prohibitions

Implementation MUST NOT:

- create weekend or holiday closures;
- treat provider silence as market closure;
- infer venue equivalence from matching symbols;
- equate stablecoin and fiat quotes;
- merge venue evidence by assumption;
- join histories by ticker alone;
- silently rescale migrated or redenominated assets;
- duplicate pre-fork history without lineage authority;
- silently rewrite timestamps;
- silently overwrite conflicts;
- fabricate bars;
- create cross rates without authority;
- operate an unapproved timeframe;
- claim acceptance without provenance and validation proof.

---

# 20. Exceptions

Initial exceptions:

```text
NONE
```

Every future exception MUST identify scope, substituted rule, reason, approval, effective range, review date, operational impact, and provenance requirements.

No undocumented exception is valid.

---

# 21. Amendment and Versioning

A new version is required when a change affects:

- market boundary;
- instrument membership;
- UTC calendar or day ownership;
- week or month ownership;
- venue-scope requirements;
- provider roles;
- price or volume doctrine;
- structural-event treatment;
- effective-range logic;
- required timeframe authorities;
- inheritance rules.

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| 1.0 | 2026-07-11 | Initial crypto constitutional doctrine drafted | Establish market authority before timeframe implementation | PENDING |

Superseded versions remain immutable and auditable.

---

# 22. Approval Gate

This doctrine may be marked **APPROVED** only when:

- market scope is accepted;
- continuous UTC calendar is accepted;
- day, week, and month ownership are accepted;
- venue and aggregate treatment is accepted;
- provider roles are accepted;
- evidence rules are accepted;
- price and volume semantics are accepted;
- validation and structural-event rules are accepted;
- effective-range logic is accepted;
- required timeframe authorities are accepted;
- exceptions and approval identity are recorded.

---

# 23. Acceptance Statement

Upon approval:

> `CRYPTO_BASE_DOCTRINE_V1` is the approved constitutional authority for the Cryptoasset market ecosystem within Fragarach II. All subordinate crypto timeframe authorities, specifications, implementations, acquisitions, validations, migrations, evidence-lane operations, and acceptance proofs MUST conform to it.

---

# 24. Governing Principle

> Crypto is continuous, multi-venue, identity-sensitive, and structurally mutable. Its authority depends on explicit asset identity, UTC ownership, declared venue scope, immutable evidence, and visible uncertainty.

Provider convention may be mapped.

Implementation may encode.

Neither may invent authority.

**Operations is King.**
