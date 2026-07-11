# INDICES D1 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority  
**Authority Layer:** Market Timeframe  
**Authority Name:** `INDICES_D1_AUTHORITY_V1`  
**Market:** Calculated Indices  
**Market Code:** `INDICES`  
**Timeframe:** `D1`  
**Version:** 1.0  
**Status:** DRAFT FOR APPROVAL  
**Repository Location:** `constitution/authorities/indices/INDICES_D1_AUTHORITY_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Authority:** `constitution/doctrines/INDICES_BASE_DOCTRINE_V1.md`  
**Effective From:** Not effective until approved  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** PENDING  
**Approval Date:** PENDING


---

# 1. Purpose

This authority defines the constitutional operational truth for canonical Index `D1` evidence within Fragarach II.

It establishes:

- what one Index `D1` bar represents;
- interval alignment and calculation-date ownership;
- canonical timestamp meaning;
- administrator and provider mapping;
- publication state, delay, and correction treatment;
- approved direct and derived construction;
- request, response, overlap, and coverage proof;
- effective history segmentation;
- expected bars, gaps, duplicates, and conflicts;
- Evidence Lane identity;
- validation, freshness, and Current-As-Of Truth.

This authority applies only to explicitly registered calculated-index series with approved calendar, methodology, history-segment, and publication profiles.

It does not authorise futures, ETFs, funds, CFDs, spread-betting quotes, or other tradable proxies.

---

# 2. Constitutional Position

```text
Constitution

↓

INDICES_BASE_DOCTRINE_V1

↓

INDICES_D1_AUTHORITY_V1

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides all subordinate documents;
2. `INDICES_BASE_DOCTRINE_V1` overrides this authority;
3. an approved index-specific registration, methodology profile, and effective range refine this authority;
4. this authority overrides implementation specifications;
5. implementation MUST NOT invent missing operational facts.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No specification may weaken this authority.

---

# 4. Document Identity and Scope

## 4.1 Canonical Identity

**Market:** `INDICES`  
**Timeframe:** `D1`  
**Nominal Duration:** one approved index calculation date  
**Time Unit:** `DAY`  
**Interval Type:** `CALENDAR-DERIVED`  
**Validator:** `INDICES_D1_VALIDATOR_V1`

## 4.2 Eligible Index Registration

A lane is eligible only when its registration defines:

- canonical index code and official name;
- administrator and calculation agent;
- index family and exact variant;
- return type;
- currency or unit;
- weighting or calculation basis where material;
- methodology reference and effective version;
- calculation calendar;
- publication timezone and calculation window;
- calculation frequency and dissemination delay;
- official-close rule;
- publication-state model;
- provider symbol mapping and provider role;
- official-live, official-historical, or back-cast segment;
- effective start and end.

## 4.3 Excluded Evidence

This authority excludes:

- index futures and options;
- ETFs, funds, notes, certificates, and trackers;
- CFDs, broker cash-index quotes, and spread-betting prices;
- synthetic index reconstructions;
- a related but different return, currency, hedging, or weighting variant;
- constituent prices or baskets presented as the index;
- volume copied from any linked tradable product.

## 4.4 No Symbol Inference

Implementation MUST NOT infer index identity, administrator, official status, return type, currency, calendar, or publication class from ticker text alone.

---

# 5. Canonical Timeframe Definition

## 5.1 Definition

One canonical Index `D1` bar represents one approved index calculation date for one registered calculated-index series under one approved evidence identity.

The identity includes:

- administrator;
- family and variant;
- methodology effective range;
- return type;
- currency or unit;
- publication class;
- history segment;
- provider role and source scope.

## 5.2 Interval Type

**Interval Type:** `CALENDAR-DERIVED`

Index time is governed by calculation and publication authority, not by a universal exchange session.

## 5.3 Bar Meaning

A canonical bar is a time aggregation of index-level observations or an approved direct provider bar.

It is not an executable market price and does not imply that the index can be traded directly.

## 5.4 Eligibility by Calculation Frequency

An index is eligible for `D1` only when its approved calculation frequency and publication profile can support that timeframe without interpolation.

An end-of-day-only index is not eligible for H1, M30, or M5 merely because a vendor offers a similarly named chart.

## 5.5 Construction Boundary

Approved lower-timeframe construction may use H1, M30, or M5 only under Section 10.

Cross-index, cross-variant, cross-currency, cross-provider, and cross-history-segment construction is prohibited.

---

# 6. Interval Alignment Authority

## 6.1 Alignment Origin

The alignment origin is the registered index calculation date under its approved calculation calendar and publication timezone.

There is no universal exchange day or UTC day for all indices.

## 6.2 Boundary Rule

A D1 interval contains all eligible index observations owned by one approved calculation date under the registered publication profile.

The exact calculation window may be:

- a local-market calculation session;
- a multi-market calculation window;
- an administrator-defined end-of-day observation;
- another approved methodology-defined period.

## 6.3 Alignment Formula

For calculation date `D`, let `C(D)` be the complete administrator-approved calculation and publication ownership record for that date.

The canonical D1 owner is `D`. The physical opening and closing instants are attributes of `C(D)` and MUST NOT be inferred from UTC midnight.

## 6.4 Session Crossing

A D1 bar MAY cross UTC midnight or constituent-market dates when the registered methodology requires it.

It MUST NOT combine two approved calculation dates.

## 6.5 Partial Intervals

A shortened, suspended, delayed, or disrupted calculation date is complete only according to the approved administrator rule.

Provider silence is not proof of an administrator suspension. Administrator suspension is not a provider gap.

---

# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `SEMANTIC CALCULATION-DATE LABEL`  
**Canonical Storage Timezone:** `UTC`

The canonical timestamp is `YYYY-MM-DDT00:00:00Z`, where the date is the owning approved calculation date.

It is a semantic date label and MUST NOT be interpreted as the physical calculation-window open.

## 7.2 Provider Timestamp Mapping

| Source | Provider Timestamp Meaning | Canonical Mapping | Requirement |
|---|---|---|---|
| Official administrator | Methodology-defined calculation date or publication instant | Map to approved calculation date | Administrator identity and publication state required |
| Licensed distributor | Provider date or daily timestamp | Map only through registered provider timestamp profile | Exact index variant and history segment required |
| Twelve Data | Provider `1day` date or timestamp | Map through an approved index/provider profile to the same calculation date | Familiar symbol text is insufficient |
| Operator file | Declared in manifest | Map under approved parser and timezone profile | Ambiguity is retained, not guessed |

## 7.3 Date-Only Values

**Date-Only Allowed:** `YES`

A date-only value is valid only when the owning calculation date is unambiguous.

## 7.4 Ambiguous or Invalid Timestamps

Ambiguous timestamps MUST be rejected or retained as compatibility evidence.

Implementation MUST NOT infer the owner date from receipt time, provider delay, constituent exchange, or neighbouring rows.

---

# 8. Calculation-Date and Publication Ownership

## 8.1 Inherited Rule

The approved calculation date owns the index observation or interval under `INDICES_BASE_DOCTRINE_V1`.

## 8.2 Timeframe-Specific Ownership

Every `D1` bar belongs to the calculation date whose registered calculation window contains its interval or whose official end-of-day publication owns the observation.

## 8.3 Multi-Market Indices

For cross-market or global indices, the administrator's calculation date controls even when constituent markets occupy different civil dates.

## 8.4 Week and Month Boundaries

Week and month ownership follow the registered calculation calendar.

Implementation MUST NOT infer the week or month from provider receipt time.

## 8.5 Methodology Transitions

A methodology, administrator, currency, return-type, or publication-profile transition creates an effective-range boundary.

A bar MUST NOT cross that boundary.

---

# 9. Bar Level and Field Meaning

## 9.1 Open

`open` is the first eligible index level in the canonical interval under the approved aggregation basis.

It is not automatically the administrator's official opening index level unless explicitly classified as such.

## 9.2 High and Low

`high` and `low` are extrema of eligible index-level observations within the interval.

They are not constituent extrema, futures extrema, ETF extrema, or CFD extrema.

## 9.3 Close

`close` is the final eligible index level in the interval.

For D1, an administrator's official close and a vendor's final sampled close are distinct evidence semantics unless equivalence is proven.

## 9.4 Volume

Index volume is null unless the exact index methodology defines an approved volume-like measure and the lane registers its meaning.

Constituent turnover, futures volume, ETF volume, provider update count, and tick count MUST NOT populate canonical volume.

## 9.5 Value Domain

Index values MUST be finite numbers.

Implementation MUST NOT impose a universal positive-value rule unless the registered index profile requires it.

## 9.6 Adjustment and Return Type

Price return, gross total return, net total return, hedged, unhedged, local-currency, and converted-currency series are separate identities.

A bar-level adjustment flag MUST NOT substitute for exact variant identity.

---

# 10. Bar Construction Authority

## 10.1 Source of Construction

**Approved Construction Source:** `DIRECT PROVIDER BAR OR APPROVED INTRADAY ROLLUP`

A source is eligible only when index identity, administrator, family, variant, return type, currency or unit, history segment, publication class, provider role, and timestamp profile all match.

## 10.2 OHLC Construction

Where Fragarach-side aggregation is authorised:

- **Open** MUST equal the first eligible index observation or first complete source-bar open.
- **High** MUST equal the maximum eligible index level or source-bar high.
- **Low** MUST equal the minimum eligible index level or source-bar low.
- **Close** MUST equal the final eligible index observation or final complete source-bar close.
- **Volume** MUST remain null unless the registered index methodology defines an approved volume-like field for that exact index series.

Constituent trading volume, ETF volume, futures volume, update count, and provider tick count MUST NOT be relabelled as index volume.

## 10.3 Source Timeframe Eligibility

| Source Timeframe | Permitted | Conditions | Notes |
|---|---|---|---|
| `H1` | YES | Complete registered calculation session and one consistent evidence identity | Official-close equivalence remains separately classified |
| `M30` | YES | Complete registered calculation session and one consistent evidence identity | Official-close equivalence remains separately classified |
| `M5` | YES | Complete registered calculation session and one consistent evidence identity | Official-close equivalence remains separately classified |

## 10.4 Direct Versus Derived Precedence

Official administrator final close evidence has the highest authority for the close observation, but it does not silently replace or manufacture the other OHLC fields.

A direct OHLC-qualified D1 bar and an intraday-derived D1 bar may coexist as distinct evidence. Selection requires explicit evidence-class and publication-state rules.

## 10.5 Missing Source Bars

A D1 OHLC bar MUST NOT be constructed when required source intervals are missing unless the registered methodology explicitly proves that the missing intervals were outside the calculation window or that no calculation was expected.

A close-only official observation MUST NOT be expanded into flat OHLC values. It remains close-observation evidence until an approved close-only serving contract exists.

---

# 11. Bar Completion Authority

## 11.1 Completion Rule

A D1 bar is complete when the approved calculation date has ended under the registered profile and the evidence has reached a permitted publication state.

Permitted states may include:

- `PRELIMINARY_USABLE`;
- `OFFICIAL_FINAL`;
- `OFFICIAL_CORRECTED`;
- another approved state.

The state MUST remain visible.

## 11.2 Latest Closed Bar

The latest closed D1 bar is the latest approved calculation date for which the required publication state is available.

A delayed receipt does not move the owner date.

## 11.3 Preliminary and Corrected Values

Preliminary, final, and corrected values are separate evidence events.

A correction MUST preserve the prior value and correction relationship.

## 11.4 Disruptions

If the administrator declares no calculation, suspension, or deferred publication, the date is classified under that event—not as an ordinary missing bar.

## 11.5 Incomplete Frontier

An incomplete current calculation date may be shown as frontier context but MUST NOT be selected as a closed D1 bar.

---

# 12. Request and Response Authority

## 12.1 Approved Direct Provider Contract

Version 1 permits Twelve Data as a conditional licensed-distributor source only when the registered provider mapping proves:

- the returned instrument is the intended calculated index;
- administrator and index family match;
- exact variant and return type match;
- currency or unit match;
- the series is not a futures, ETF, CFD, fund, or synthetic proxy;
- publication class and delay are explicit;
- timestamp semantics are proven;
- history segment is classified.

The requested interval is:

```text
1day
```

## 12.2 Request Range

Requests MUST use bounded `start_date` and `end_date` ranges or a bounded `outputsize` plan.

Unbounded acquisition is prohibited.

## 12.3 Row Limits

```text
Provider documented hard maximum: 5,000 rows
Fragarach constitutional ceiling: 4,000 rows
Normal operational target: 4,000 rows or fewer
```

Implementation MUST detect truncation and MUST NOT treat a full-limit response as proof of complete coverage.

## 12.4 Ordering

Responses MUST be normalized into ascending canonical timestamp order before validation.

Provider order MUST NOT be assumed.

## 12.5 Timezone

The request timezone SHOULD be the registered publication timezone when the provider supports it.

Every returned timestamp MUST still be normalized through the approved provider timestamp profile into canonical UTC.

## 12.6 Chunking and Overlap

Historical chunking MUST be deterministic and use an overlap of five approved calculation dates.

Overlap rows do not count as new unique progress.

Every request and response MUST preserve:

- requested start and end;
- returned first and last timestamp;
- row count;
- provider metadata;
- response checksum and size;
- retry and error state;
- acquisition time;
- plan step and overlap relationship.

## 12.7 Earliest Availability

Provider-reported earliest availability MAY be discovered through `/earliest_timestamp`, but it is capability evidence—not automatic constitutional effective-range authority.

## 12.8 Error Handling

Rate limits, entitlement failures, empty responses, symbol ambiguity, proxy substitution, malformed rows, and provider outages MUST produce immutable acquisition evidence.

They MUST NOT silently alter the registered index mapping.

---

# 13. Effective Historical Range

## 13.1 Segment Classes

Every accepted lane range MUST be classified as one of:

- `OFFICIAL_LIVE`;
- `OFFICIAL_HISTORICAL`;
- `OFFICIAL_RESTATED`;
- `BACK_CAST`;
- `VENDOR_RECONSTRUCTED`;
- another approved class.

## 13.2 Effective Start

The effective start is the latest applicable date among:

- index launch or admitted back-cast start;
- methodology-version start;
- administrator or calculation-agent effective start;
- variant start;
- provider mapping start;
- provider coverage start;
- calendar and publication-profile start;
- timestamp-profile start;
- accepted evidence start.

## 13.3 Effective End

An effective segment ends at the earliest applicable cessation, methodology transition, provider mapping end, variant retirement, administrator change, or approved range end.

## 13.4 Back-Cast Separation

Back-cast history MUST remain explicitly classified and MUST NOT be silently joined to official live history as if both had identical publication provenance.

## 13.5 Earliest Timestamp

A provider's earliest timestamp does not prove official launch, methodology continuity, or back-cast status.

## 13.6 Range Materialisation

The exact effective segment MUST be materialised in Instrument Registration or Evidence Lane Authority before activation.

---

# 14. Expected Bars and Gap Authority

## 14.1 Expected Grid

The expected grid is one expected D1 observation or OHLC bar for each approved index calculation date on which the registered publication profile requires it.

Expected timestamps MUST be generated from the registered index calendar and publication profile.

## 14.2 No Universal Calendar

Generic weekdays, one constituent exchange, or a provider's chart availability MUST NOT define expected bars.

## 14.3 Gap Classes

Validation MUST distinguish:

- `NO_CALCULATION_EXPECTED`;
- `ADMINISTRATOR_SUSPENSION`;
- `PUBLICATION_DELAY`;
- `PROVIDER_OUTAGE`;
- `MISSING_EXPECTED_EVIDENCE`;
- `HISTORY_SEGMENT_BOUNDARY`;
- `METHODOLOGY_TRANSITION`;
- `BACK_CAST_BOUNDARY`;
- `SESSION_END_PARTIAL`;
- `INCOMPLETE_FRONTIER`.

## 14.4 Timeframe-Specific Materiality

A missing D1 final close after the profile's expected publication deadline is material.

A preliminary value may keep operations usable while final publication remains pending, provided its status is visible.

## 14.5 Repair

Repair MAY acquire missing evidence from an approved source for the same index identity and history segment.

Repair MUST NOT use futures, ETFs, CFDs, linked products, constituent reconstruction, interpolation, or cross-variant substitution.

## 14.6 Non-Blocking Operation

A gap, delay, or pending correction MUST NOT blank unrelated accepted output.

Fragarach shall serve best available accepted evidence with Current-As-Of Truth, status, and warning visibility.

---

# 15. Duplicate and Overlap Authority

## 15.1 Canonical Duplicate Key

A candidate duplicate is evaluated by:

```text
index_registration
+ timeframe
+ canonical timestamp
+ administrator
+ variant
+ methodology segment
+ history segment
+ publication class
+ provider/source identity
```

## 15.2 Exact Repeats

An exact repeat remains immutable `UNCHANGED` evidence and MUST NOT create a second canonical row.

## 15.3 Corrections

A preliminary-to-final change or official correction is not an ordinary duplicate.

It MUST preserve:

- prior value;
- replacement value;
- publication-state transition;
- correction sequence or notice where available;
- receipt and evidence provenance.

## 15.4 Conflicts

Differing values with the same apparent key are conflicts until identity, publication class, delay, correction state, and history segment are reconciled.

## 15.5 Chunk Overlap

Chunk overlap is expected acquisition behaviour and MUST be reconciled deterministically.

Overlap MUST NOT be mistaken for provider conflict when the evidence is identical.

---

# 16. Index Level and Volume Semantics

## 16.1 Level Unit

The index level uses the registered points, percentage, currency, volatility, rate, or other approved unit.

Unit conversion requires separate transformation authority.

## 16.2 Decimal Precision

Storage MUST preserve provider precision sufficient to reproduce accepted evidence.

Display rounding MUST NOT alter canonical evidence.

## 16.3 Volume

Default canonical volume is `NULL`.

Zero MUST NOT be used to mean unknown or not applicable.

## 16.4 Tradability

No OHLC field implies executable bid, ask, midpoint, trade, settlement, or linked-product price.

## 16.5 Return-Series Separation

Return-type transformations belong to registered index variants, not ad hoc bar transformation.

---

# 17. Validation Authority

## 17.1 Validator Identity

The controlling validator is:

```text
INDICES_D1_VALIDATOR_V1
```

## 17.2 Mandatory Identity Checks

The validator MUST verify:

- registered index identity;
- administrator and family;
- exact variant and return type;
- currency or unit;
- methodology segment;
- calendar and publication profile;
- provider role and symbol mapping;
- publication class and delay;
- history segment;
- timeframe and timestamp profile.

## 17.3 Mandatory Bar Checks

The validator MUST verify:

- finite OHLC values;
- `high >= max(open, close)`;
- `low <= min(open, close)`;
- `high >= low`;
- canonical timestamp alignment;
- interval ownership;
- completion state;
- no unexplained session crossing;
- no forbidden volume semantics;
- no proxy-instrument contamination.

## 17.4 Coverage Checks

Coverage MUST be compared with the registered expected grid and publication cadence.

A generic exchange calendar is insufficient.

## 17.5 Publication-State Checks

Preliminary, official final, corrected, delayed, indicative, and reconstructed values MUST remain distinguishable.

## 17.6 Result Classes

Validation results include:

- `VALID`;
- `VALID_WITH_WARNING`;
- `PRELIMINARY_USABLE`;
- `DELAYED_USABLE`;
- `INCOMPLETE`;
- `CONFLICT`;
- `REJECTED`;
- `COMPATIBILITY_REQUIRED`.

## 17.7 Non-Blocking Rule

A failed candidate does not invalidate previously accepted unrelated evidence.

Operations continue from best accepted evidence with visible status.

---

# 18. Evidence Lane Contract

## 18.1 Required Lane Identity

Every Index `D1` Evidence Lane MUST bind:

- instrument registration ID;
- market code `INDICES`;
- timeframe `D1`;
- administrator and calculation agent;
- index family and exact variant;
- methodology segment;
- return type;
- currency or unit;
- calendar profile;
- publication profile;
- calculation frequency;
- dissemination delay;
- publication class;
- history segment;
- provider and provider symbol;
- provider role;
- source scope;
- timestamp profile;
- effective start and end;
- validator `INDICES_D1_VALIDATOR_V1`;
- approval provenance.

## 18.2 Lane Separation

Separate lanes are mandatory for material differences in:

- index variant;
- return type;
- currency or hedging;
- administrator or methodology segment;
- official, delayed, indicative, or vendor publication;
- official live, historical, back-cast, or reconstructed history;
- provider source;
- timeframe.

## 18.3 Evidence Immutability

Accepted raw responses, files, observations, and correction notices are immutable.

## 18.4 Serving Selection

Serving selection MUST be explicit and auditable.

A higher-precedence source does not silently erase accepted lower-precedence evidence.

## 18.5 Lane Activation

Activation requires approved parent doctrine, approved timeframe authority, complete registration, provider mapping, effective segment, validator, and compatibility proof.

---

# 19. Operational Freshness Authority

## 19.1 Current-As-Of Truth

Current-As-Of Truth is the latest approved calculation date whose required publication state is available or whose preliminary state is explicitly usable.

It MUST identify:

- calculation date or interval;
- publication state;
- source and provider role;
- dissemination delay;
- history segment;
- validation state;
- receipt time.

## 19.2 Freshness States

Permitted states include:

- `CURRENT_OFFICIAL`;
- `CURRENT_PRELIMINARY`;
- `CURRENT_DELAYED`;
- `PENDING_PUBLICATION`;
- `STALE_PROVIDER`;
- `ADMINISTRATOR_SUSPENDED`;
- `MARKET_PROFILE_CLOSED`;
- `NO_CALCULATION_EXPECTED`;
- `UNKNOWN_COMPATIBILITY_REQUIRED`.

## 19.3 Delay Awareness

An approved dissemination delay is part of normal freshness calculation.

A delayed feed is not stale merely because it is not real-time.

## 19.4 Correction Awareness

A later correction MAY update the selected current truth through an auditable selection event while preserving prior evidence.

## 19.5 Operations Doctrine

Warnings, delay, preliminary state, and gaps MUST remain visible without blocking unrelated operator output.

---

# 20. Provider Precedence

| Priority | Source | Role | Conditions |
|---:|---|---|---|
| 1 | Existing accepted selected evidence | Operational continuity | Remains selected until explicit resolution changes selection |
| 2 | Official administrator or calculation-agent evidence | Highest constitutional source | Exact variant, methodology, publication state, and segment match |
| 3 | Approved licensed distributor such as Twelve Data | Automated acquisition or supplementary source | Mapping, index type, delay, timestamp, coverage, and validation pass |
| 4 | Approved manual official file | Backfill, correction, or supplementary source | Manifest, checksum, source authority, segment, and validation required |
| 5 | Approved derived bar | Verification or uncovered-interval source | Section 10 permits; complete contributors and one evidence identity |

Priority authorises consideration, not silent overwrite.

A linked tradable product never gains precedence as index evidence.

---

# 21. Exceptions

Initial exceptions:

```text
NONE
```

A future exception MUST identify:

- index and exact variant;
- timeframe;
- administrator and methodology segment;
- provider and publication class;
- substituted rule;
- effective start and end;
- reason and evidence;
- approving authority;
- operational consequence;
- review date.

No undocumented exception is valid.

---

# 22. Compatibility Requirements

Before implementation, acquisition, migration, construction, or lane activation proceeds, it MUST prove:

- `INDICES_BASE_DOCTRINE_V1` is approved;
- `INDICES_D1_AUTHORITY_V1` is approved;
- exact index identity and variant are registered;
- methodology and effective segment are explicit;
- calculation calendar and publication profile are approved;
- provider role, symbol mapping, delay, and timestamp semantics are approved;
- history segment is materialised;
- `INDICES_D1_VALIDATOR_V1` exists and is deterministic;
- no proxy instrument is being substituted;
- no implementation-critical authority is missing.

Failure requires a compatibility report and stops only the affected path.

Existing accepted unrelated operations MUST remain available.

---

# 23. Specification Boundary

Specifications MAY define:

- schemas and migrations;
- provider clients and entitlement handling;
- parsers and normalisers;
- request planning, retry, and chunking;
- immutable evidence storage;
- validators;
- approved derived-bar materialisation;
- selection events and serving queries;
- native operations workflows;
- tests, reports, checkpoints, and acceptance proof.

Specifications MUST NOT redefine:

- index identity or variant;
- administrator or methodology;
- calculation calendar;
- publication class or delay;
- timestamp meaning;
- history segment;
- provider role;
- bar construction eligibility;
- volume semantics;
- effective-range rules.

---

# 24. Implementation Prohibitions

Implementation MUST NOT:

- treat an index as a directly traded instrument;
- substitute futures, ETFs, CFDs, funds, or broker synthetics;
- infer official status from a familiar ticker;
- assume one universal index calendar or session;
- hard-code a universal intraday bar count;
- align intraday bars from UTC or clock hours when the profile opens elsewhere;
- fabricate OHLC from an official close-only observation;
- fabricate index volume;
- merge price-return and total-return variants;
- merge local and converted currency variants;
- merge official and back-cast history without classification;
- interpolate missing index values;
- silently overwrite preliminary, final, or corrected evidence;
- treat provider receipt time as calculation ownership;
- hide warnings by blocking operator output.

---

# 25. Amendment and Versioning

A new authority version is required when changing:

- timeframe meaning or alignment;
- timestamp ownership;
- permitted construction;
- provider role or contract;
- publication-state treatment;
- expected-grid logic;
- effective-range rules;
- validator semantics;
- Evidence Lane identity requirements.

Index-specific methodology changes normally create registration/profile segments rather than silently changing this generic authority.

Historical authority MUST remain auditable.

---

# 26. Approval Gate

Approval requires confirmation that:

- all sections are complete;
- no placeholders remain;
- the parent doctrine is approved;
- index-specific profiles can express the required calendar and publication facts;
- provider semantics are explicit;
- proxy separation is explicit;
- construction and gap rules are explicit;
- validator identity is explicit;
- compatibility behaviour is non-blocking;
- acceptance criteria are testable.

Before approval, status remains `DRAFT FOR APPROVAL`.

---

# 27. Acceptance Statement

Approval means Fragarach II accepts this document as the constitutional authority for Index `D1` Evidence Lanes.

Approval does not itself implement acquisition, storage, validation, serving, or UI behaviour.

---

# 28. Provider Reference Record

The following external provider facts were used as capability evidence during drafting:

- Twelve Data advertises global index data through a common API structure;
- Twelve Data documents `1day` as a supported time-series interval;
- Twelve Data documents bounded historical requests and a maximum of 5,000 returned records;
- Twelve Data documents reference-data discovery and `/earliest_timestamp` capabilities.

These facts do not prove that any provider symbol is the intended official index variant.

They do not override the Constitution, the parent doctrine, or this authority.

Access and review date: `2026-07-11`.

The Fragarach constitutional request ceiling remains 4,000 rows.

---

# 29. Governing Principle

> An Index bar is valid only when administrator, methodology, exact variant, publication class, history segment, interval, timestamp, and calculation-date ownership all agree.

> A tradable proxy is not the index.

> Implementation must never invent authority.

> Operations is King.
