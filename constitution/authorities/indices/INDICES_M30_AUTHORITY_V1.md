# INDICES M30 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority  
**Authority Layer:** Market Timeframe  
**Authority Name:** `INDICES_M30_AUTHORITY_V1`  
**Market:** Calculated Indices  
**Market Code:** `INDICES`  
**Timeframe:** `M30`  
**Version:** 1.0  
**Status:** APPROVED  
**Repository Location:** `constitution/authorities/indices/INDICES_M30_AUTHORITY_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Authority:** `constitution/doctrines/INDICES_BASE_DOCTRINE_V1.md`  
**Effective From:** 2026-07-11  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** Ray Morgan  
**Approval Date:** 2026-07-11


---

# 1. Purpose

This authority defines the constitutional operational truth for canonical Index `M30` evidence within Fragarach II.

It establishes:

- what one Index `M30` bar represents;
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

INDICES_M30_AUTHORITY_V1

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
**Timeframe:** `M30`  
**Nominal Duration:** 30 minutes within an approved index calculation window  
**Time Unit:** `MINUTE`  
**Interval Type:** `HYBRID`  
**Validator:** `INDICES_M30_VALIDATOR_V1`

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

One canonical Index `M30` bar represents 30 minutes within an approved index calculation window for one registered calculated-index series under one approved evidence identity.

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

**Interval Type:** `HYBRID`

Index time is governed by calculation and publication authority, not by a universal exchange session.

## 5.3 Bar Meaning

A canonical bar is a time aggregation of index-level observations or an approved direct provider bar.

It is not an executable market price and does not imply that the index can be traded directly.

## 5.4 Eligibility by Calculation Frequency

An index is eligible for `M30` only when its approved calculation frequency and publication profile can support that timeframe without interpolation.

An end-of-day-only index is not eligible for H1, M30, or M5 merely because a vendor offers a similarly named chart.

## 5.5 Construction Boundary

Approved lower-timeframe construction may use M5 only under Section 10.

Cross-index, cross-variant, cross-currency, cross-provider, and cross-history-segment construction is prohibited.

---

# 6. Interval Alignment Authority

## 6.1 Alignment Origin

The alignment origin is the registered index calculation-window open in the publication timezone.

Intervals MUST be generated from that origin, not from generic UTC or wall-clock boundaries.

For example, an index profile opening at 09:30 local time produces H1 boundaries from 09:30, not automatically from 10:00. This example illustrates the rule and does not create an index profile.

## 6.2 Boundary Rule

Canonical intervals use:

```text
[start, end)
```

The opening instant belongs to the interval. The ending instant belongs to the next interval or ends the calculation window.

## 6.3 Alignment Formula

Let `O(D)` be the registered calculation-window open for approved calculation date `D`, and let `Δ` be the nominal timeframe duration.

```text
interval_n = [O(D) + nΔ, min(O(D) + (n+1)Δ, C(D)))
```

where `C(D)` is the registered calculation-window close.

## 6.4 Session Crossing

A bar MUST NOT cross:

- the registered calculation-window close;
- an approved calculation suspension;
- a methodology-defined discontinuity;
- an effective methodology or publication-profile boundary.

A bar MAY cross a civil-hour or UTC-date boundary when the registered profile requires it.

## 6.5 Partial Intervals

When the calculation window is not evenly divisible by the timeframe, the final shortened interval MAY exist only when the profile explicitly classifies it as `SESSION_END_PARTIAL` and records its actual end.

A shortened interval caused by provider outage is not a valid session-end partial.

---

# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `INTERVAL OPEN`  
**Canonical Storage Timezone:** `UTC`

The timestamp is the exact UTC instant corresponding to the interval open under the registered publication timezone and calculation profile.

## 7.2 Provider Timestamp Mapping

| Source | Provider Timestamp Meaning | Canonical Mapping | Requirement |
|---|---|---|---|
| Official administrator stream | Observation or interval time under methodology | Map through the registered publication timezone and cadence | Publication class and delay required |
| Licensed distributor | Provider interval open or close | Convert only after provider timestamp meaning is proven | Exact index variant required |
| Twelve Data | Provider time-series timestamp for the registered index symbol | Normalize through the approved provider timestamp profile | Exchange, country, variant, and index type must match registration |
| Operator file | Declared in manifest | Normalize under approved parser and timezone profile | No guessing |

## 7.3 Date-Only Values

**Date-Only Allowed:** `NO`

Date-only values cannot identify an intraday interval.

## 7.4 Ambiguous or Invalid Timestamps

A timestamp with unknown timezone, unknown open/close meaning, duplicate daylight-saving mapping, or impossible calculation-window placement MUST be rejected or retained as compatibility evidence.

Receipt time MUST NOT substitute for interval time.

---

# 8. Calculation-Date and Publication Ownership

## 8.1 Inherited Rule

The approved calculation date owns the index observation or interval under `INDICES_BASE_DOCTRINE_V1`.

## 8.2 Timeframe-Specific Ownership

Every `M30` bar belongs to the calculation date whose registered calculation window contains its interval or whose official end-of-day publication owns the observation.

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

**Approved Construction Source:** `DIRECT PROVIDER BAR OR APPROVED M5 ROLLUP`

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
| `M5` | YES | Six complete M5 intervals with identical index and evidence identity | A profile-defined shortened session-end interval requires explicit treatment |

## 10.4 Direct Versus Derived Precedence

Direct and derived bars may coexist as immutable evidence.

An official or licensed direct bar does not silently overwrite a derived bar. Selection depends on evidence class, publication state, provider role, completeness, and accepted continuity.

## 10.5 Missing Source Bars

A derived bar requires every expected contributing interval, including any profile-authorised shortened session-end contributor.

Missing contributors prohibit canonical derived construction. Direct evidence may still be accepted independently when its own contract passes.

---

# 11. Bar Completion Authority

## 11.1 Completion Rule

An intraday bar is complete only when:

1. its profile-defined interval end has passed;
2. the registered dissemination delay has elapsed;
3. the required source observations or direct provider bar are present;
4. the interval was inside an active calculation window;
5. no unresolved administrator suspension or profile transition affects it.

## 11.2 Latest Closed Bar

The latest closed bar is the greatest profile-aligned interval whose completion rule passes.

The current clock interval is not automatically closed.

## 11.3 Delayed and Indicative Publication

A delayed or indicative bar MAY be operationally usable when its profile permits it, but it MUST remain visibly classified.

Delay affects availability, not interval ownership.

## 11.4 Session-End Partial

A profile-authorised shortened final interval is complete at its actual calculation-window close plus required dissemination delay.

It MUST carry `SESSION_END_PARTIAL` classification.

## 11.5 Incomplete Frontier

The active interval may be retained as provisional frontier evidence but MUST NOT be selected as a closed canonical bar.

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
30min
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

Historical chunking MUST be deterministic and use an overlap of two approved calculation dates.

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

The expected grid is the exact profile-derived M30 grid inside the registered calculation window; no universal daily count exists.

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

Intraday expected counts are calculated from the exact registered calculation window, interval origin, approved suspensions, publication cadence, and session-end partial rule.

Implementation MUST NOT hard-code counts such as 24, 48, or 288 for indices.

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
INDICES_M30_VALIDATOR_V1
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

Every Index `M30` Evidence Lane MUST bind:

- instrument registration ID;
- market code `INDICES`;
- timeframe `M30`;
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
- validator `INDICES_M30_VALIDATOR_V1`;
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

Current-As-Of Truth is the latest complete profile-aligned M30 interval after accounting for calculation window, dissemination delay, and publication status.

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
- `INDICES_M30_AUTHORITY_V1` is approved;
- exact index identity and variant are registered;
- methodology and effective segment are explicit;
- calculation calendar and publication profile are approved;
- provider role, symbol mapping, delay, and timestamp semantics are approved;
- history segment is materialised;
- `INDICES_M30_VALIDATOR_V1` exists and is deterministic;
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

Approval means Fragarach II accepts this document as the constitutional authority for Index `M30` Evidence Lanes.

Approval does not itself implement acquisition, storage, validation, serving, or UI behaviour.

---

# 28. Provider Reference Record

The following external provider facts were used as capability evidence during drafting:

- Twelve Data advertises global index data through a common API structure;
- Twelve Data documents `30min` as a supported time-series interval;
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
