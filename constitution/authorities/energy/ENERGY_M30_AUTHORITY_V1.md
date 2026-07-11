# ENERGY M30 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority  
**Authority Layer:** Market Timeframe  
**Authority Name:** `ENERGY_M30_AUTHORITY_V1`  
**Market:** Energy Reference Prices  
**Market Code:** `ENERGY`  
**Timeframe:** `M30`  
**Version:** 1.0  
**Status:** APPROVED  
**Repository Location:** `constitution/authorities/energy/ENERGY_M30_AUTHORITY_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Authority:** `constitution/doctrines/ENERGY_BASE_DOCTRINE_V1.md`  
**Effective From:** 2026-07-11  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** Ray Morgan  
**Approval Date:** 2026-07-11

---

# 1. Purpose

This authority defines the constitutional operational truth for canonical Energy `M30` evidence within Fragarach II.

It establishes:

- what one Energy `M30` bar represents;
- exact interval alignment and ownership;
- canonical timestamp meaning;
- provider timestamp mapping;
- bar completion and latest-closed-bar rules;
- approved direct and derived construction;
- Twelve Data request and response semantics;
- expected bars, maintenance exclusions, gaps, duplicates, and revisions;
- effective-range proof;
- Evidence Lane identity;
- validation, freshness, and Current-As-Of Truth.

This authority applies only to registered Version 1 Energy instruments using:

```text
source_nature    = PROVIDER_DERIVED_REFERENCE
calendar_profile = ENERGY_REFERENCE_24X5_NEW_YORK_ROLLOVER_V1
```

It does not authorise identified futures contracts, settlements, physical assessments, benchmarks, or continuous-futures construction.

---

# 2. Constitutional Position

```text
Constitution

↓

ENERGY_BASE_DOCTRINE_V1

↓

ENERGY_M30_AUTHORITY_V1

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides all subordinate documents;
2. `ENERGY_BASE_DOCTRINE_V1` overrides this authority;
3. this authority overrides implementation specifications;
4. implementation MUST NOT invent missing operational facts.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No specification may weaken this authority.

---

# 4. Document Identity and Scope

## 4.1 Canonical Identity

**Market:** `ENERGY`  
**Timeframe:** `M30`  
**Nominal Duration:** 30 minutes  
**Time Unit:** `MINUTE`  
**Calendar Profile:** `ENERGY_REFERENCE_24X5_NEW_YORK_ROLLOVER_V1`  
**Session Authority:** `ENERGY_REFERENCE_DAILY_SESSION_V1`  
**Validator:** `ENERGY_M30_VALIDATOR_V1`

## 4.2 Included Instruments

A lane is eligible only when its Instrument Registration Authority defines:

- canonical symbol;
- source nature `PROVIDER_DERIVED_REFERENCE`;
- benchmark family;
- quote asset;
- pricing unit;
- provider symbol mapping;
- source scope;
- price basis;
- roll methodology or `NOT_APPLICABLE`;
- calendar profile;
- effective range.

Expected examples include `USOIL`, `UKOIL`, and `NATGAS`, but none is admitted by name alone.

## 4.3 Excluded Evidence

This authority excludes:

- specific futures expiries;
- official settlements;
- benchmark publications;
- physical spot assessments;
- continuous futures with undisclosed construction;
- broker CFDs lacking approved source identity;
- unit-converted or quote-converted data without transformation authority.

## 4.4 No Symbol Inference

Implementation MUST NOT infer WTI, Brent, Henry Hub, barrel, MMBtu, futures, spot, settlement, or roll identity from a symbol string.

---

# 5. Canonical Timeframe Definition

## 5.1 Definition

One canonical Energy `M30` bar represents 30 minutes of one registered provider-derived Energy reference under the approved New York rollover profile.

The bar retains one:

- instrument identity;
- source nature;
- provider or source identity;
- source scope;
- price basis;
- quote asset;
- pricing unit;
- roll methodology;
- adjustment state.

## 5.2 Interval Type

**Interval Type:** FIXED-DURATION WITH SESSION OWNERSHIP

The canonical grid is 48 nominal intervals per full owned day.

## 5.3 Bar Meaning

A bar may be:

- direct provider aggregation; or
- a Fragarach-derived rollup from approved lower Energy timeframes.

It is not automatically:

- an official physical spot bar;
- an identified futures-contract bar;
- an official settlement;
- a benchmark administrator value;
- a universal consolidated Energy price.

## 5.4 Price Basis

The bar represents the provider-declared or conservatively classified price basis.

For Twelve Data Version 1 mappings without a more specific approved methodology:

```text
source_nature = PROVIDER_DERIVED_REFERENCE
source_scope  = TWELVE_DATA_PROVIDER_AGGREGATE
price_basis   = PROVIDER_AGGREGATE
```

---

# 6. Interval Alignment Authority

## 6.1 Alignment Origin

Intervals align from successive 30-minute intervals from each 17:00 America/New_York session open.

## 6.2 Boundary Rule

```text
[interval_open, interval_open + 30 minutes)
```

The opening instant is included. The ending instant belongs to the next interval or closure boundary.

## 6.3 Alignment Formula

For session open instant `S` and integer `k >= 0`, canonical interval `k` is `[S + k×30 minutes, S + (k+1)×30 minutes)`, provided the interval is expected under the registered calendar profile.

## 6.4 Session Crossing

A canonical `M30` bar MUST NOT cross the 17:00 New York owned-day boundary.

It MUST NOT cross the Friday-to-Sunday weekend closure.

A bar MAY cross UTC midnight because UTC midnight is not the Energy session boundary.

Daylight-saving changes MUST use IANA timezone rules, not a fixed UTC offset.

## 6.5 Maintenance Windows

A recurring provider maintenance interval may be excluded from the expected grid only when the registered lane profile defines:

- local start and end;
- timezone;
- effective date range;
- provider and symbol scope;
- whether the boundary interval is expected;
- approval provenance.

Without that authority, provider silence is a gap, not a market closure.

## 6.6 Partial Intervals

An interval shortened by a provider outage, halt, launch boundary, or acquisition boundary is `PARTIAL` unless an approved calendar-profile exception defines it as a complete shortened interval. Fragarach MUST NOT stretch or merge it into a normal interval.

---

# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `INTERVAL-OPEN INSTANT`  
**Canonical Storage Timezone:** `UTC`

The canonical timestamp is the UTC instant at which the 30-minute interval opens. `session_date` separately records the New York close-date owner.

## 7.2 Provider Timestamp Mapping

| Provider | Provider Timestamp Meaning | Requested Timezone | Canonical Mapping | Notes |
|---|---|---|---|---|
| Twelve Data | Provider interval-open timestamp unless contrary semantics are proven | Requested `America/New_York` | A provider local timestamp is interpreted under its approved timezone semantics, mapped to the corresponding canonical interval open, then stored as UTC. | Ambiguity is a compatibility stop for the affected lane |
| Operator file | Declared by file authority | Declared | Map only under approved parser and timestamp profile | Ambiguity is retained as rejection or compatibility evidence |

## 7.3 Date-Only Values

**Date-Only Allowed:** `NO`

Date-only values are invalid for Energy `M30` because they cannot identify one canonical intraday interval. They MUST be rejected with `DATE_ONLY_TIMESTAMP_UNSUPPORTED_FOR_INTRADAY`.

## 7.4 Ambiguous Timestamps

Implementation MUST NOT guess whether a provider timestamp means interval open, close, settlement time, exchange trade date, or civil date.

Ambiguous rows MUST be rejected or quarantined with provenance.

## 7.5 Stored Ownership Fields

Each accepted bar MUST retain:

- canonical timestamp;
- `session_date` owned by New York close date;
- canonical interval open;
- canonical interval end;
- provider timestamp as received;
- provider timezone semantics;
- mapping method.

---

# 8. Trading-Day and Session Ownership

## 8.1 Inherited Rule

This authority inherits `ENERGY_REFERENCE_24X5_NEW_YORK_ROLLOVER_V1` from `ENERGY_BASE_DOCTRINE_V1`.

## 8.2 Owner Date

Every bar belongs to the New York civil date at which its containing Energy session closes at 17:00.

## 8.3 Overnight Session

A bar opened on the preceding civil date MAY belong to the following owner date.

UTC date and owner date may differ.

## 8.4 Week and Month Boundaries

- Friday-owned intervals are the final normal intervals of the Energy week.
- Monday-owned intervals begin at Sunday 17:00 New York.
- A bar belongs to the month of its owner date.
- Public holidays do not remove expected bars without explicit exception authority.
- Contract-roll dates do not change owner-date rules.

---

# 9. Bar Price and Field Meaning

## 9.1 OHLC

For direct evidence, OHLC retains the provider's declared `M30` aggregation.

For derived evidence:

- **Open** is the first contributing open;
- **High** is the maximum contributing high;
- **Low** is the minimum contributing low;
- **Close** is the final contributing close.

## 9.2 Energy Identity

Every bar MUST retain:

- underlying commodity family;
- benchmark family;
- source nature;
- provider symbol;
- source scope;
- price basis;
- quote asset;
- pricing unit;
- contract identity or `NOT_APPLICABLE`;
- roll methodology or `NOT_APPLICABLE`;
- adjustment state.

## 9.3 Units

Crude-oil references commonly use quote currency per barrel.

Natural-gas references commonly use quote currency per MMBtu.

These are examples, not inferred defaults.

A unit mismatch is a material conflict.

## 9.4 Negative Prices

Finite negative values MAY be valid when permitted by instrument registration.

A validator MUST NOT reject a complete coherent OHLC row solely because one or more price values are negative.

## 9.5 Volume and Open Interest

Provider volume MUST retain its declared meaning.

Open interest MUST NOT be stored as volume.

For derived bars, volume may be summed only when source semantics are additive and identical. Otherwise it MUST be null or unavailable.

---

# 10. Bar Construction Authority

## 10.1 Approved Methods

The following construction methods are approved:

- `DIRECT_PROVIDER_M30`
- `DERIVED_FROM_M5`

## 10.2 Source Timeframe Eligibility

| Source Timeframe | Permitted | Conditions |
|---|---|---|
| `M5` | YES, CONDITIONAL | Approved `ENERGY_M5_AUTHORITY_V1`; same instrument, source nature, source scope, price basis, pricing unit, roll methodology; 6 expected M5 bars or profile-adjusted complete coverage |

All other source timeframes are prohibited under Version 1 unless separately authorised.

## 10.3 Direct Provider Authority

Twelve Data `30min` rows are approved as direct Energy `M30` evidence when:

- the registered provider symbol resolves;
- source nature, benchmark family, price basis, source scope, and pricing unit are declared;
- request and response rules in Section 12 are followed;
- timestamp mapping validates;
- the row lies within the proven effective range;
- `ENERGY_M30_VALIDATOR_V1` accepts it.

Provider-side aggregation MUST remain identified as provider-side aggregation.

## 10.4 Derived Construction

For a derived `M30` bar, all contributing bars MUST share instrument, source nature, source scope, price basis, quote asset, pricing unit, roll methodology, and adjustment state. Cross-provider construction is prohibited. A derived bar is complete only when every expected contributing interval is present after approved maintenance exclusions.

## 10.5 Direct Versus Derived Precedence

Direct and derived bars are independent immutable evidence. A lower-priority valid source MAY fill an uncovered interval but MUST NOT silently replace an already accepted comparable bar. Conflicts remain recorded.

## 10.6 Cross-Provider Construction

**Cross-Provider Construction Allowed:** `NO`

One derived bar MUST NOT combine observations from multiple providers, source natures, units, roll methods, or adjustment states.

---

# 11. Bar Completion Authority

## 11.1 Logical Closure

A logical Energy `M30` interval closes when its canonical interval end has passed.

## 11.2 Evidence Completion

An evidence bar is complete only when:

- the logical interval is closed;
- it is not the provider's current partial bar;
- timestamp and ownership validate;
- OHLC validates;
- source nature, source scope, price basis, unit, and roll methodology are known;
- effective-range rules pass;
- construction coverage is complete;
- no unresolved structural incompatibility exists.

## 11.3 Latest Expected Closed Bar

The latest expected closed M30 interval is the greatest expected canonical interval whose end instant is less than or equal to the current instant.

Provider delay does not change logical closure. It changes freshness and coverage state.

## 11.4 Status Model

| Status | Meaning |
|---|---|
| `OPEN` | Canonical interval has begun but not ended |
| `PARTIAL` | Evidence covers only part of an expected interval |
| `PROVISIONAL` | Closed evidence carries unresolved revision, maintenance, or structural uncertainty |
| `CLOSED` | Interval ended and mandatory validation passed |
| `REVISED` | New immutable comparable evidence differs from earlier evidence |
| `NOT_EXPECTED` | Approved calendar profile says no bar is expected |

An `OPEN`, `PARTIAL`, or `PROVISIONAL` bar MUST NOT be represented as the latest accepted closed bar.

## 11.5 Revision Window

No finite universal Energy revision window is assumed.

Corrections or changed provider methodology MUST be stored as new immutable evidence.

---

# 12. Request and Response Authority

## 12.1 Twelve Data Request Contract

The approved direct automated request uses `/time_series` with:

| Parameter | Approved Rule |
|---|---|
| `symbol` | Registered Twelve Data symbol for the Energy instrument |
| `interval` | `30min` |
| `timezone` | `America/New_York` |
| `order` | `asc` |
| `format` | `JSON` |
| `start_date` | Explicit bounded start |
| `end_date` | Explicit bounded end |
| `outputsize` | Omit when both bounded dates are used; otherwise MUST NOT exceed constitutional ceiling |
| authentication | Approved secret mechanism; secret MUST NOT enter logs or evidence |

Use explicit `start_date` and `end_date` values in `America/New_York` that bracket the desired canonical interval-open range. The response MUST be remapped to UTC, filtered to the canonical requested range, and checked for truncation.

## 12.2 Constitutional Row Ceiling

The external provider documents a 5,000-point maximum.

Fragarach's constitutional request ceiling is:

```text
4,000 expected rows per request
```

The lower value preserves headroom for overlap, unexpected rows, and provider behaviour changes.

A specification MAY choose a smaller operational target.

## 12.3 Chunk Overlap

Adjacent historical chunks MUST overlap by at least:

```text
96 expected M30 intervals, equal to two full nominal Energy trading days
```

Overlap supports deterministic reassembly, duplicate proof, and revision detection.

Overlap rows count inside the constitutional request ceiling.

## 12.4 Incremental Acquisition

Incremental acquisition MUST request a bounded overlap behind the latest accepted interval and continue through the latest expected closed interval.

It MUST NOT rely on only the provider's most recent row.

## 12.5 Response Ordering

Responses MUST be normalised into ascending canonical order before validation.

Provider order MUST NOT be assumed.

## 12.6 Empty Response

An empty response means only that no rows were returned for the request.

It does not prove:

- market closure;
- unsupported instrument;
- unsupported interval;
- delisting;
- complete coverage;
- absence of history.

The acquisition receipt MUST record request, status, provider message, and classification.

## 12.7 Truncation Detection

The adapter MUST detect possible truncation using:

- row count;
- requested range;
- first and last returned timestamps;
- expected-grid coverage;
- provider error metadata;
- adjacent chunk overlap.

Suspected truncation MUST NOT be represented as complete coverage.

## 12.8 Raw Evidence

Raw response bytes or a lossless canonical raw block MUST be sealed before canonical promotion.

Checksum, byte count, acquisition time, and request metadata MUST be retained.

---

# 13. Effective Historical Range

## 13.1 Lane-Specific Range

Each Energy `M30` lane MUST materialise:

- requested start and end;
- provider earliest timestamp where available;
- first returned timestamp;
- first accepted timestamp;
- latest accepted complete timestamp;
- first and latest owner dates;
- known roll or methodology boundaries;
- coverage status;
- evidence-confirmation time.

## 13.2 No Universal Range

There is no universal Energy `M30` start date.

Coverage varies by instrument, provider mapping, interval, source nature, unit, benchmark family, and methodology.

## 13.3 Earliest Timestamp Endpoint

`/earliest_timestamp` MAY guide planning.

The result MUST be stored with request provenance and confirmed by actual acquisition.

## 13.4 Effective Start

The effective start is the first accepted canonical interval supported by immutable evidence under the current identity regime.

A provider claim alone is not sufficient.

## 13.5 Regime Boundaries

A roll-method, unit, source-nature, benchmark, or provider-methodology change may create a new effective sub-range.

---

# 14. Expected Bars and Gap Authority

## 14.1 Expected Grid

| Day Type | Nominal `M30` Grid | Expected Rule |
|---|---:|---|
| Normal full owner day | 48 | All canonical intervals except approved maintenance exclusions |
| Weekend closure | 0 | No intervals wholly inside Friday 17:00 to Sunday 17:00 closure |
| Approved shortened/exceptional session | Profile-derived | Exact intervals come from versioned exception evidence |
| Public holiday without exception | 48 nominal | Holiday alone does not remove expectations |

## 14.2 Maintenance Exclusions

An interval may be classified `NOT_EXPECTED` for recurring maintenance only when the registered profile contains explicit effective-dated evidence.

A generic assumption such as “Energy has a daily break” is insufficient.

## 14.3 Gap Definition

A gap exists when an expected closed interval has no accepted complete selected bar.

Provider silence, acquisition failure, and rejected evidence are different reasons and MUST remain distinct.

## 14.4 Gap Materiality

Gap reports SHOULD distinguish:

- live-frontier gaps;
- recent historical gaps;
- isolated old gaps;
- contiguous missing ranges;
- gaps adjacent to structural roll or methodology events;
- low-materiality gaps where higher-timeframe coverage remains usable.

## 14.5 Repair

Repair MUST:

- remain bounded to the affected lane and range;
- preserve original and new evidence;
- use approved provider semantics;
- report conflicts;
- avoid fabricating bars;
- avoid blocking unrelated operator output.

## 14.6 Structural Discontinuities

A price discontinuity caused by a roll or methodology event is not a timestamp gap.

It MUST be represented as a structural-series event, not repaired away.

---

# 15. Duplicate and Overlap Authority

## 15.1 Comparable Identity

Rows are comparable duplicates only when they share:

- canonical instrument;
- canonical interval;
- source provider;
- source nature;
- source scope;
- price basis;
- quote asset;
- pricing unit;
- roll methodology;
- adjustment state.

## 15.2 Exact Duplicate

An exact duplicate preserves evidence identity and produces no new canonical value.

It MAY create an `UNCHANGED` provenance event.

## 15.3 Conflicting Duplicate

A comparable row with different OHLC or material fields is a conflict or revision candidate.

Both observations MUST remain immutable.

## 15.4 Non-Comparable Rows

Rows with different source nature, unit, contract, settlement basis, roll methodology, or adjustment state are separate evidence, not duplicates.

## 15.5 Overlap

Repeated requests and chunk overlaps are expected.

Every overlap row MUST be classified as exact duplicate, unchanged evidence, revision candidate, conflict, or non-comparable evidence.

---

# 16. Price and Volume Semantics

## 16.1 Canonical Price

Canonical price means quote amount per registered pricing unit under one declared source identity.

## 16.2 No Silent Adjustment

Fragarach MUST NOT silently back-adjust, ratio-adjust, splice, or roll Energy history.

Adjusted and unadjusted series require separate identities.

## 16.3 Negative and Zero Values

Negative and zero prices MAY be valid where instrument authority permits.

Null is not zero. Missing is not zero.

## 16.4 Volume

Volume is optional unless a provider-specific authority makes it mandatory.

Volume semantics MUST remain source-specific.

## 16.5 Settlement and Open Interest

Settlement and open interest are not generic OHLCV fields and MUST remain separate unless specifically authorised.

---

# 17. Validation Authority

## 17.1 Validator Identity

The required validator is:

```text
ENERGY_M30_VALIDATOR_V1
```

## 17.2 Mandatory Checks

The validator MUST check:

- registered instrument identity;
- market code `ENERGY`;
- timeframe `M30`;
- provider mapping;
- source nature;
- benchmark family;
- source scope;
- price basis;
- quote asset;
- pricing unit;
- roll methodology;
- adjustment state;
- timestamp mapping;
- interval alignment;
- owner date;
- weekend and maintenance classification;
- closed/partial status;
- finite OHLC;
- OHLC ordering;
- duplicate classification;
- effective range;
- construction completeness;
- request and response provenance.

## 17.3 OHLC Rules

```text
high >= low
high >= open
high >= close
low  <= open
low  <= close
```

Negative values are permitted when the instrument registration permits them.

## 17.4 Validation Outcomes

| Outcome | Meaning |
|---|---|
| `ACCEPTED` | Mandatory authority and structural checks passed |
| `ACCEPTED_WITH_WARNING` | Usable evidence with visible non-material uncertainty |
| `REJECTED` | Structurally invalid or incompatible evidence |
| `COMPATIBILITY_BLOCKED` | Required constitutional authority is missing for this lane or operation |

## 17.5 Non-Blocking Doctrine

A rejected row or blocked update path MUST NOT erase or hide prior accepted evidence.

AMBER evidence remains usable with visible warning.

---

# 18. Evidence Lane Contract

## 18.1 Lane Identity

A canonical Energy `M30` Evidence Lane key MUST include at least:

- instrument registration identity;
- market code `ENERGY`;
- timeframe `M30`;
- provider/source identity;
- source nature;
- source scope;
- price basis;
- quote asset;
- pricing unit;
- roll methodology;
- adjustment state;
- calendar profile;
- authority version.

## 18.2 Required Lane Metadata

The lane MUST expose:

- authority status;
- effective start and latest accepted interval;
- Current-As-Of Truth;
- freshness state;
- source and provider mapping;
- source nature;
- unit and price basis;
- roll methodology;
- gap counts;
- conflict counts;
- latest acquisition receipt;
- validator version;
- operational status and reason.

## 18.3 Immutability

Evidence rows and raw blocks are immutable.

Selection state MAY change through an auditable authority decision, but evidence MUST NOT be mutated.

## 18.4 Serving

Consumers MUST read through the approved Evidence Lane or serving contract.

They MUST NOT bypass authority by reading arbitrary provider files.

---

# 19. Operational Freshness Authority

## 19.1 Reference

Freshness is measured against the latest expected closed Energy `M30` interval from Section 11.

It uses expected canonical intervals, not raw civil-time differences.

## 19.2 States

| State | Definition | Operational Meaning |
|---|---|---|
| `CURRENT` | Latest accepted complete interval equals latest expected closed interval | Normal operation |
| `DELAYED` | Latest accepted complete interval is one or two expected M30 intervals behind | Continue with visible warning |
| `STALE` | Latest accepted complete interval is three or more expected M30 intervals behind | Continue with prominent warning and repair priority |
| `UNKNOWN` | Expected or accepted latest interval cannot be determined | Display authority/evidence uncertainty; stop only affected update path if authority is missing |

## 19.3 Current-As-Of Truth

The operator-facing Current-As-Of Truth value is the owner date and canonical close identity of the latest accepted complete selected bar.

It MUST remain distinct from:

- current wall-clock time;
- acquisition time;
- latest provider response timestamp;
- latest open or partial bar;
- futures settlement or benchmark publication time.

## 19.4 Non-Blocking Operation

`DELAYED` and `STALE` are warnings, not reasons to hide accepted history.

Where usable evidence exists, Fragarach MUST continue to serve it with Current-As-Of Truth, freshness state, and visible reason.

---

# 20. Provider Precedence

The default evidence-selection order for an uncovered interval is:

1. accepted valid existing evidence for continuity;
2. validated direct Twelve Data evidence;
3. validated operator-supplied direct evidence;
4. validated complete derived evidence.

A lower-priority source MAY fill an uncovered interval.

It MUST NOT silently replace accepted comparable evidence.

---

# 21. Exceptions

An exception MUST identify:

- instrument and provider mapping;
- timeframe `M30`;
- exact rule varied;
- maintenance, holiday, methodology, or operational reason;
- effective range;
- approval authority;
- expiry or review date;
- required acceptance proof.

Exceptions MUST be narrow and versioned.

---

# 22. Compatibility Requirements

Before implementation, all of the following MUST resolve:

- approved `ENERGY_BASE_DOCTRINE_V1`;
- approved `ENERGY_M30_AUTHORITY_V1`;
- registered instrument;
- source nature;
- benchmark family;
- provider symbol mapping;
- source scope;
- price basis;
- quote asset;
- pricing unit;
- roll methodology;
- calendar profile;
- timestamp mapping;
- effective range;
- validator contract.

Missing material authority requires a compatibility report and stops only the affected operation.

---

# 23. Specification Boundary

Specifications MAY define:

- adapters;
- modules;
- schemas;
- commands;
- retry and scheduling;
- storage paths;
- native UI;
- migrations;
- tests and acceptance reports.

Specifications MUST NOT redefine:

- Energy identity;
- source nature;
- pricing unit;
- roll methodology;
- interval alignment;
- timestamp ownership;
- provider request semantics;
- expected-bar truth;
- completion rules;
- validation outcomes;
- freshness truth.

---

# 24. Implementation Prohibitions

Implementation MUST NOT:

- infer commodity, benchmark, contract, unit, or roll identity from a symbol;
- treat provider reference as official spot, futures, settlement, or benchmark evidence;
- use a fixed UTC offset for New York;
- accept date-only values for intraday bars;
- merge source natures, units, roll methods, or contracts;
- construct across providers;
- silently back-adjust or splice history;
- reject negative prices solely for being negative;
- fabricate maintenance or missing bars;
- overwrite immutable conflicts;
- promote partial bars as closed;
- hide valid history because freshness is delayed;
- allow legacy behaviour to overrule this authority.

---

# 25. Amendment and Versioning

A new authority version is required for a material change to:

- interval definition or alignment;
- timestamp meaning;
- session ownership;
- provider request contract;
- row ceiling or overlap;
- construction sources;
- expected-bar rules;
- maintenance treatment;
- validation rules;
- lane identity;
- freshness thresholds.

Historical versions MUST remain available.

---

# 26. Approval Gate

This authority may be approved only when:

- all 29 sections are present;
- no unresolved placeholders remain;
- the parent Energy doctrine is approved;
- instrument and source-nature scope are explicit;
- alignment and timestamp semantics are exact;
- provider request and response rules are explicit;
- construction rules are explicit;
- expected-bar and maintenance rules are explicit;
- validator identity is explicit;
- compatibility and non-blocking behaviour are explicit.

Before approval, status remains `DRAFT FOR APPROVAL`.

---

# 27. Acceptance Statement

Approval means Fragarach II accepts this document as the constitutional authority for Energy `M30` Evidence Lanes under the Version 1 provider-derived reference profile.

Approval does not itself implement acquisition, storage, validation, serving, or UI behaviour.

---

# 28. Provider Reference Record

The following external provider facts were used as capability evidence during drafting:

- Twelve Data documents `30min` as a supported time-series interval.
- Twelve Data documents `/earliest_timestamp` for discovering provider-reported historical availability.
- Twelve Data documents a maximum of 5,000 points per request.
- Twelve Data lists commodity coverage and a WTI/USD commodity reference.

These external references do not override the Constitution or this authority.

Access and review date: `2026-07-11`.

The constitutional operating ceiling remains 4,000 rows even where the provider permits 5,000.

---

# 29. Governing Principle

> An Energy bar is valid only when commodity identity, source nature, benchmark family, unit, price basis, roll methodology, interval, timestamp, and owner date all agree.

> Implementation must never invent authority.

> Operations is King.
