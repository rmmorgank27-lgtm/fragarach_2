# INDICES BASE DOCTRINE V1

**Document Class:** Constitutional Market Authority  
**Authority Layer:** Market Ecosystem  
**Authority Name:** `INDICES_BASE_DOCTRINE_V1`  
**Market Name:** Indices  
**Market Code:** `INDICES`  
**Version:** 1.0  
**Status:** APPROVED  
**Repository Location:** `constitution/doctrines/INDICES_BASE_DOCTRINE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Effective From:** 2026-07-11  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** Ray Morgan  
**Approval Date:** 2026-07-11

---

# 1. Purpose

This doctrine defines the constitutional operational truth for the Indices market ecosystem within Fragarach II.

It establishes the market-wide authority inherited by every index timeframe authority, index registration, evidence lane, acquisition specification, validator, native operation, migration, and acceptance proof.

It defines:

- what an index is within Fragarach II;
- the boundary between an index and a tradable instrument;
- index administrator, family, methodology, and variant identity;
- calculation-calendar and publication-session authority;
- trading-day, week, and month ownership;
- official, indicative, delayed, preliminary, and corrected values;
- approved provider roles;
- acceptable evidence and provenance;
- level, return, currency, OHLC, and volume semantics;
- rebalancing, reconstitution, divisor, and methodology-event authority;
- market-wide validation and conflict rules;
- live, historical, and back-cast effective ranges;
- the boundary between index authority and timeframe authority.

This doctrine does not define interval-specific bar alignment, provider interval codes, request chunking, bar completion, or latest-closed-bar calculations. Those matters belong to approved index timeframe authorities and registered index profiles.

---

# 2. Constitutional Position

```text
Constitution

↓

INDICES_BASE_DOCTRINE_V1

↓

Index Registration and Index Timeframe Authority

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides this doctrine;
2. this doctrine overrides subordinate index timeframe authorities and profiles;
3. an approved index methodology and registration refine the general rules of this doctrine;
4. approved timeframe authorities override implementation specifications;
5. specifications override implementation;
6. implementation MUST NOT invent missing authority.

Legacy code, provider defaults, ticker text, chart labels, futures symbols, CFD symbols, or sample files are not constitutional index authority unless expressly adopted.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate document may weaken a mandatory requirement in this doctrine.

---

# 4. Market Definition

## 4.1 Market Identity

An index is a calculated measure produced under an approved methodology to represent the level, return, volatility, value, or other defined characteristic of a specified universe of securities, instruments, prices, rates, or assets.

An index is not, by itself:

- an exchange-traded security;
- a futures contract;
- an option;
- an exchange-traded fund;
- a contract for difference;
- a broker quote;
- a directly executable market price.

An index may be calculated and published by:

- an independent index administrator;
- an exchange or market operator;
- a benchmark administrator;
- another approved calculation agent acting under documented methodology.

The authoritative identity of an index comes from its administrator, methodology, variant, calculation basis, and effective range—not from ticker spelling alone.

## 4.2 Classification

**Asset Class:** `INDEX`  
**Instrument Type Family:** `CALCULATED_INDEX`  
**Venue Model:** Administrator-calculated and publication-based  
**Trading Model:** Methodology-defined calculation and publication schedule  
**Canonical Calendar Timezone:** Index-specific  
**Primary Quote Convention:** Index level or return value in declared points, percentage, currency, or other approved unit

## 4.3 Included Scope

This doctrine includes, when explicitly registered:

- equity-market benchmark indices;
- broad-market equity indices;
- size, sector, industry, style, factor, and thematic equity indices;
- price-return indices;
- gross total-return indices;
- net total-return indices;
- equal-weighted, market-capitalisation-weighted, price-weighted, and other approved variants;
- local-currency, base-currency, hedged, and unhedged variants;
- real-time, delayed, end-of-day, and official-close index series;
- historical official index levels;
- approved back-cast or back-tested index history when explicitly classified.

Examples may include index families associated with United States, United Kingdom, German, Australian, Japanese, European, or global equity markets.

Examples do not create registration authority.

## 4.4 Excluded Scope

This doctrine excludes unless separately registered and explicitly classified:

- futures and options on an index;
- ETFs, funds, notes, or certificates tracking an index;
- broker CFDs or spread-betting quotes;
- synthetic cash-index approximations;
- proprietary trading signals;
- constituent baskets assembled without an approved methodology;
- exchange prices of index-linked products;
- volatility, rates, commodity, currency, digital-asset, or multi-asset indices unless their controlled index type is expressly admitted;
- unofficial reconstructions represented as official index history.

An excluded class requires a separate market authority, controlled type, or approved amendment.

---

# 5. Index Membership and Identity Authority

## 5.1 Membership Rule

A series belongs to `INDICES` only when:

1. the index is explicitly registered;
2. the controlled index type is approved;
3. the index administrator is explicit;
4. the official index name and family are explicit;
5. the methodology or ground-rules authority is explicit;
6. the exact variant is explicit;
7. the canonical index code or identifier is registered for an effective range;
8. the calculation currency or unit is explicit;
9. the return type is explicit;
10. the weighting and calculation basis are explicit where material;
11. the calculation calendar and publication schedule are explicit;
12. provider mappings are registered;
13. live, historical, and back-cast ranges are distinguishable;
14. the series is not assigned to another market doctrine.

Ticker similarity does not establish index identity.

## 5.2 Canonical Identifier

The canonical identifier is the approved Fragarach index code linked to the administrator's official identifier for the effective range.

Examples of familiar labels may include:

```text
SPX
NDX
DJI
FTSE100
DAX
ASX200
NIKKEI225
```

These examples are not self-authorising and may be ambiguous across providers.

The canonical code does not by itself identify:

- administrator;
- price-return versus total-return variant;
- gross versus net return;
- local versus converted currency;
- hedged versus unhedged treatment;
- real-time versus end-of-day series;
- official versus synthetic calculation;
- methodology version;
- constituent universe;
- effective historical range.

## 5.3 Required Metadata

Every index registration MUST include:

- canonical Fragarach index code;
- controlled display name;
- market code `INDICES`;
- asset class `INDEX`;
- controlled index type;
- index administrator;
- calculation agent where different;
- official index name;
- index family or series;
- official administrator identifier where available;
- methodology or ground-rules reference;
- methodology version or effective date;
- index objective;
- constituent or input universe description;
- weighting method;
- rebalancing or review model;
- divisor or calculation basis where material;
- return type;
- calculation currency or unit;
- hedging status where applicable;
- calculation frequency;
- publication status class;
- official calendar reference;
- publication timezone;
- official-close rule;
- provider symbol mappings;
- provider delay and publication scope;
- launch date;
- base date and base value where available;
- official-history start;
- back-cast-history start where applicable;
- retirement or cessation date where known;
- operational status;
- registration and approval provenance.

## 5.4 Variant Identity

Each material variant is a separate constitutional series identity.

Variants include:

- price return;
- gross total return;
- net total return;
- local currency;
- converted currency;
- currency hedged;
- equal weight;
- capped weight;
- leverage or inverse methodology;
- real-time or end-of-day publication;
- official close or indicative level.

Implementation MUST NOT substitute one variant for another because the names appear related.

## 5.5 Administrator and Methodology Identity

The index administrator and approved methodology are constitutional properties.

A methodology defines the rules governing construction, calculation, maintenance, constituent changes, and related events.

Implementation MUST NOT infer methodology from constituent composition, provider description, or historical price resemblance.

A change of administrator, calculation agent, or methodology requires explicit effective-range authority.

## 5.6 Tradable-Product Separation

An index and a product linked to that index are separate instruments.

The following are not index-level evidence for the underlying cash index:

- futures prices;
- options prices;
- ETF prices;
- exchange-traded note prices;
- CFD prices;
- spread-betting prices;
- broker synthetic quotes.

A linked product may be registered under its own market doctrine and may reference the index relationship, but its price history MUST remain separate.

## 5.7 Prohibited Assumptions

Implementation MUST NOT infer:

- index identity from ticker text alone;
- administrator from provider name;
- price-return status from omission of a suffix;
- currency from constituent domicile;
- calendar from one major constituent exchange;
- official status from a chart label;
- live history from a back-tested series;
- tradeability from the existence of an index level;
- volume from constituent activity;
- continuity across methodology or administrator changes.

Missing material identity requires a compatibility report.

---

# 6. Canonical Index Calendar Authority

## 6.1 Calendar Identity

Indices do not share one universal exchange calendar.

Each registered index MUST reference an approved calculation calendar defined by its administrator, methodology, and variant.

The calendar may derive from:

- one underlying exchange calendar;
- multiple constituent-market calendars;
- a benchmark publication calendar;
- a global business-day convention;
- another methodology-defined schedule.

## 6.2 Governing Calendar Rule

An expected index publication date exists only when the approved methodology and administrator calendar expect calculation or publication for that series.

Implementation MUST NOT use generic weekdays or one constituent exchange calendar as a substitute.

## 6.3 Trading-Day or Calculation-Day Ownership

The index's approved calculation date owns the official index observation.

The owning date MUST be defined by:

- administrator methodology;
- publication timezone;
- official-close convention;
- constituent-market treatment;
- holiday and disruption rules.

A provider receipt time or delayed publication time does not change the owning calculation date.

## 6.4 Week Ownership

A weekly index period is assigned according to the approved calculation calendar and timeframe authority.

For a conventional local-market equity index, the default may be the administrator's Monday-to-Friday calculation week.

For global or cross-market indices, the methodology-defined week controls.

## 6.5 Month Ownership

A monthly index period is assigned according to the registered index's calculation dates within the Gregorian calendar month unless the methodology defines another convention.

## 6.6 Holidays and Partial Market Openings

The index methodology governs treatment when:

- the principal market is closed;
- some constituent markets are open and others closed;
- one or more constituents are suspended;
- official closing prices are unavailable;
- a market closes early;
- a market disruption occurs;
- currency conversion inputs are unavailable.

Implementation MUST NOT invent stale-price, carry-forward, or alternative-price rules.

## 6.7 Timezone and Daylight Saving

Each index registration MUST declare its publication timezone.

A global index may have a calculation or publication timezone different from any constituent market.

Implementation MUST use timezone rules applicable to the registered series and effective date.

No universal fixed UTC offset is authorised.

## 6.8 Calendar Amendment Rule

Calendar corrections and administrator changes MUST be versioned and auditable.

Historical calculation-day ownership MUST NOT be silently rewritten.

---

# 7. Calculation and Publication Session Authority

## 7.1 Session Model

An index has a calculation and publication session, not a trading session in the ordinary instrument sense.

A registered series MUST identify whether it is:

- real-time calculated;
- periodically calculated intraday;
- delayed;
- indicative;
- preliminary end-of-day;
- official end-of-day;
- official close only;
- another methodology-defined publication class.

## 7.2 Real-Time Calculation Window

A real-time index MUST declare:

- calculation start;
- calculation end;
- update frequency;
- publication timezone;
- constituent price eligibility;
- treatment of unavailable or stale constituent prices;
- dissemination delay;
- official opening and closing level rules.

A vendor's display availability does not establish the official calculation window.

## 7.3 Opening Level

The official opening level may depend on:

- constituent opening prices;
- prior closes for unopened constituents;
- methodology-defined alternative prices;
- an administrator's designated opening calculation.

Implementation MUST NOT assume the first published intraday value is the official open.

## 7.4 Official Close

The official close is defined by the administrator's methodology and publication process.

It may differ from:

- the last intraday disseminated value;
- a provider's sampled close;
- a futures settlement;
- an ETF closing price;
- a post-close corrected value.

The lane and timeframe authority MUST identify official-close semantics.

## 7.5 Preliminary, Final, and Corrected Values

Preliminary, final, and corrected index observations are distinct evidence states.

A later official correction MUST create a new evidence and provenance event.

Implementation MUST NOT overwrite the prior publication without preserving the correction relationship.

## 7.6 Delayed and Indicative Values

Delay duration and indicative status are material evidence properties.

Delayed or indicative data MAY support operations when approved, but MUST remain visibly classified and MUST NOT be relabelled as official real-time evidence.

## 7.7 Market Disruption and Calculation Suspension

An administrator may suspend, defer, cancel, or alter calculation during market disruption.

Such an event is not automatically a data gap.

Validation MUST distinguish:

- no official calculation;
- suspended dissemination;
- delayed publication;
- provider outage;
- missing evidence despite expected publication.

## 7.8 Precedence

Calculation-session authority precedence is:

```text
Approved index-specific methodology and administrator notice

↓

Approved index-family rules

↓

Approved index timeframe authority

↓

No authority
```

Provider chart behaviour does not override this precedence.

---

# 8. Provider Authority

## 8.1 Approved Roles

A provider may be approved for one or more roles:

- official index administrator;
- official calculation agent;
- official exchange or benchmark publisher;
- licensed real-time distributor;
- licensed delayed distributor;
- licensed historical-data vendor;
- manual official-file source;
- discovery-only source.

Approval for one role does not imply approval for another.

## 8.2 Provider Scope

Every index provider mapping MUST declare:

- provider name;
- provider symbol;
- official index identity;
- administrator and family;
- variant;
- return type;
- currency or unit;
- hedging status;
- calculation frequency;
- real-time, delayed, indicative, preliminary, or official status;
- dissemination delay;
- timestamp timezone;
- timestamp meaning;
- OHLC construction basis where bars are supplied;
- correction and revision behaviour;
- effective historical range;
- whether history is official, reconstructed, or back-cast.

## 8.3 Provider Semantics Boundary

This doctrine does not approve a provider merely because it returns a familiar index code.

Before acquisition implementation, subordinate authority MUST establish:

- request identifier semantics;
- exact index variant;
- interval mapping;
- output timestamp meaning;
- calculation or sampling basis;
- official-close treatment;
- delay classification;
- pagination and chunking;
- correction behaviour;
- live and historical coverage;
- back-cast classification;
- rate limits and effective ranges.

## 8.4 Provider Precedence

Default evidence precedence is:

1. official administrator or official calculation-agent evidence;
2. official exchange or benchmark publication acting under the methodology;
3. approved licensed distributor evidence;
4. approved historical vendor evidence;
5. approved manual official files with complete provenance;
6. discovery-only evidence, which cannot become canonical without review.

A broker CFD or synthetic quote is not an index provider under this precedence.

Higher precedence does not permit silent overwriting.

---

# 9. Evidence Authority

## 9.1 Immutability

Accepted raw index evidence is immutable.

Corrections, restatements, methodology revisions, and provider replacements MUST create new evidence and provenance events.

## 9.2 Acceptable Sources

Acceptable evidence may include:

- official administrator feeds or files;
- official calculation-agent publications;
- approved exchange or benchmark publications;
- approved licensed vendor responses;
- approved historical files;
- approved methodology and constituent-change notices;
- approved manually supplied official files;
- approved migration evidence with verified lineage.

## 9.3 Evidence Identity

Every index evidence object MUST identify, where applicable:

- canonical index registration;
- administrator and family;
- provider and provider symbol;
- exact variant;
- return type;
- currency or unit;
- methodology version or effective date;
- calculation and publication class;
- delay or indicative status;
- requested and received range;
- interval or observation type;
- source timezone;
- timestamp semantics;
- official, preliminary, final, or corrected state;
- acquisition or receipt timestamp;
- checksum and byte size;
- parser or normaliser version;
- row count;
- live, official historical, or back-cast classification;
- acceptance or rejection result;
- correction or supersession relationship.

## 9.4 Prohibitions

Implementation MUST NOT:

- overwrite accepted raw index evidence;
- relabel a derivative price as an index level;
- merge price-return and total-return variants;
- merge local-currency and converted-currency variants;
- represent a back-cast series as live official history;
- infer official close from the last sampled value;
- invent index volume;
- reconstruct methodology without authority;
- remove conflicting evidence merely to make validation pass.

---

# 10. Level, Return, Currency, OHLC, and Volume Semantics

## 10.1 Index Level

An index level is a calculated value under the approved methodology.

It may be expressed in:

- points;
- percentage terms;
- a declared currency;
- basis points;
- another approved unit.

An index point is not automatically a currency amount or directly executable price.

## 10.2 Return Type

The return type MUST be explicit.

At minimum, Fragarach MUST distinguish:

- price return;
- gross total return;
- net total return.

Additional return variants require controlled identity.

## 10.3 Currency and Hedging

Currency and hedging are constitutional series properties.

A local-currency index, converted-currency index, and currency-hedged index are separate series.

Implementation MUST NOT convert one into another without an approved derived-series authority.

## 10.4 Weighting and Calculation Basis

The weighting and calculation basis MUST be registered where material.

Examples include:

- float-adjusted market capitalisation;
- full market capitalisation;
- price weighting;
- equal weighting;
- capped weighting;
- factor or rules-based weighting.

The implementation does not need to reproduce the methodology unless separately specified, but it MUST preserve the declared identity.

## 10.5 OHLC Semantics

Index OHLC may be supplied by an administrator or vendor as:

- official calculated open, high, low, and close;
- sampled intraday index levels;
- vendor-aggregated interval bars;
- another documented construction.

A lane MUST declare the construction basis.

High and low MUST NOT be reconstructed from constituent closes or a linked derivative unless authority expressly permits it.

## 10.6 Volume

An index generally has no intrinsic traded volume because the index itself is not traded.

A volume field MUST be null or absent unless an approved definition exists.

Possible separately authorised meanings include:

- constituent aggregate volume;
- number of index updates;
- notional calculation input;
- linked-product volume.

These meanings are not interchangeable and linked-product volume MUST NOT be presented as intrinsic index volume.

## 10.7 Divisor and Base Value

A divisor, base value, or equivalent scaling mechanism is part of the methodology identity where applicable.

Divisor changes and base adjustments MUST be treated as methodology events, not unexplained price discontinuities.

---

# 11. Market-Wide Validation Authority

## 11.1 Mandatory Validation

Index evidence MUST be validated for:

- registered index identity;
- administrator and provider compatibility;
- exact variant and return type;
- currency and hedging compatibility;
- methodology effective range;
- calculation calendar and publication schedule;
- timestamp parseability and timezone meaning;
- publication-state classification;
- delay classification;
- monotonic ordering within a lane;
- duplicate identity;
- finite numeric values;
- OHLC coherence where OHLC exists;
- expected unit and scale;
- live, official historical, or back-cast classification;
- correction sequence;
- provenance completeness.

## 11.2 OHLC Rules

For a conventional index OHLC bar:

```text
high >= open
high >= close
low <= open
low <= close
high >= low
```

These rules do not prove that the bar is official, belongs to the right index variant, or uses the correct sampling basis.

## 11.3 Calendar and Publication Rules

Validation MUST use the registered index calendar and publication schedule.

It MUST NOT classify as missing:

- administrator-declared non-calculation days;
- officially suspended calculations;
- periods before launch or after cessation;
- absent intraday updates outside the official calculation window.

## 11.4 Variant Conflict Validation

Rows with the same timestamp but different return type, currency, hedging status, methodology version, or publication class are not duplicates.

They belong to distinct lane identities.

## 11.5 Duplicate Rule

A duplicate requires matching index registration, variant, publication class, lane identity, and canonical observation key under the approved timeframe authority.

Conflicting values require an auditable conflict event.

## 11.6 Gap Rule

A gap exists only when the approved index calendar and publication schedule expected an observation and the approved completeness rule is not met.

A calculation suspension, delayed official publication, or methodology-defined carry-forward treatment requires explicit classification.

## 11.7 Scale and Discontinuity Rule

Large changes are not automatically invalid.

Validation MUST consider:

- divisor changes;
- rebalancing or reconstitution;
- base-value changes;
- currency conversion;
- methodology revision;
- data correction;
- genuine market movement.

No discontinuity may be repaired by arbitrary scaling.

## 11.8 Conflict Rule

Where approved sources disagree, Fragarach MUST:

1. preserve all evidence;
2. identify the exact index, variant, methodology, and publication-state difference;
3. apply approved precedence only where authority exists;
4. record the resolution;
5. expose unresolved uncertainty without disabling usable operations.

## 11.9 Operational Failure Boundary

Incomplete or conflicting evidence MAY prevent promotion of the affected index lane or range.

It MUST NOT block unrelated indices, instruments, markets, evidence intake, or read-only operations.

**Operations is King.**

---

# 12. Index Maintenance and Structural Events

## 12.1 Governed Events

Material index events include:

- scheduled rebalance;
- scheduled reconstitution or review;
- constituent addition or deletion;
- fast entry or exceptional deletion;
- free-float or shares update;
- weighting-cap change;
- divisor adjustment;
- corporate-action treatment;
- market-classification change;
- currency or hedging-rule change;
- methodology amendment;
- index name or code change;
- administrator or calculation-agent change;
- calculation suspension;
- index cessation;
- successor-index launch.

## 12.2 Continuity Rule

Constituent changes do not normally create a new index identity when they occur under the approved methodology.

A methodology, return variant, currency, administrator, or objective change may create:

- continued identity with an effective-range amendment;
- a new registered variant;
- a successor index;
- a terminated series.

The authority decision MUST be explicit.

## 12.3 Rebalance and Reconstitution Rule

Rebalancing and reconstitution are methodology events.

Implementation MUST preserve:

- announcement or review date where available;
- effective date;
- affected version or constituent set;
- official administrator notice;
- any resulting correction or back-history treatment.

## 12.4 Divisor and Corporate-Action Rule

Administrator divisor adjustments or equivalent calculation changes preserve index continuity only under the approved methodology.

Implementation MUST NOT reinterpret them as security splits or price corrections.

## 12.5 Methodology Change Rule

A material methodology change MUST record:

- prior and new methodology versions;
- effective date;
- affected variants;
- continuity decision;
- historical-restatement rule;
- migration and compatibility consequences.

## 12.6 Cessation and Successor Rule

Index cessation ends the active range.

A successor index does not inherit history automatically.

Any linked history requires explicit administrator evidence and approved continuity authority.

---

# 13. Effective Historical Range

## 13.1 Launch Date, Base Date, and History Start

The following dates are distinct:

- base date;
- launch date;
- first official live calculation date;
- first official historical observation;
- first back-cast or back-tested observation;
- provider coverage start.

Registration MUST preserve these distinctions.

## 13.2 Official Live and Historical Range

The authoritative official range begins only where administrator-supported official history exists for the registered variant and methodology lineage.

A provider's earliest row does not establish official history.

## 13.3 Back-Cast and Back-Tested Range

Back-cast or back-tested history MUST be classified separately.

It MUST declare:

- methodology used;
- calculation producer;
- production date or version;
- start and end range;
- whether constituent and corporate-action data are historical or reconstructed;
- whether the administrator treats the history as official.

Back-cast evidence MUST NOT be relabelled as contemporaneously published live evidence.

## 13.4 End Rule

The authoritative end is determined by:

- cessation;
- variant retirement;
- provider mapping retirement;
- methodology or identity transition;
- latest accepted evidence for an active series.

## 13.5 Provider Coverage

Different providers may expose different ranges, delays, variants, and correction histories.

Implementation MUST NOT create an apparently continuous series by blending incompatible variants or publication classes.

---

# 14. Timeframe Inheritance

Every index timeframe authority inherits:

- market code `INDICES`;
- calculated-benchmark identity;
- strict separation from tradable products;
- explicit administrator, family, methodology, and variant identity;
- index-specific calendar and publication timezone;
- calculation-day ownership;
- official, indicative, delayed, preliminary, final, and corrected state separation;
- explicit level, return, currency, and hedging semantics;
- generally absent intrinsic volume;
- immutable evidence and provenance;
- live, official historical, and back-cast separation;
- methodology-event and continuity rules;
- no silent cross-variant or cross-provider merging;
- non-blocking operational failure boundaries.

A timeframe authority may refine these facts but MUST NOT contradict them.

---

# 15. Required Index Timeframe Authorities

The following umbrella authorities are required before their corresponding index lanes may become operational authority:

```text
INDICES_D1_AUTHORITY_V1
INDICES_H1_AUTHORITY_V1
INDICES_M30_AUTHORITY_V1
INDICES_M5_AUTHORITY_V1
```

Because index methodologies differ materially, each umbrella authority MUST require either:

- an approved index-specific profile; or
- an approved compatibility class that proves identical calendar, publication, timestamp, and bar semantics.

A generic provider interval is not sufficient authority.

Additional timeframe authorities MAY be created through the approved template and approval process.

---

# 16. Explicit Delegation to Timeframe Authorities

Each index timeframe authority and profile MUST define:

- interval duration;
- bar-open and bar-close alignment;
- timestamp label meaning;
- calculation-window coverage;
- real-time sampling or official-bar basis;
- opening and official-close treatment;
- preliminary, final, and corrected-value treatment;
- calculation-day ownership;
- partial final intervals;
- bar completion rule;
- latest-closed-bar rule;
- provider request interval;
- provider response semantics;
- delay and publication-state handling;
- pagination and chunking;
- effective request range;
- overlap and retry rules;
- duplicate key;
- expected-observation model;
- gap classification and materiality;
- correction and restatement handling;
- live versus back-cast eligibility;
- lane validation requirements;
- index-profile compatibility requirements.

If any material item is unresolved, implementation MUST stop that lane with a compatibility report.

---

# 17. Compatibility Requirements

Before an implementation specification may consume this doctrine, it MUST identify:

- the approved doctrine version;
- the approved index registration;
- the exact administrator, family, methodology, and variant;
- the approved timeframe authority and index profile;
- the evidence-lane registration;
- the calculation calendar and publication schedule;
- the provider mapping and role;
- the level, return, currency, hedging, OHLC, and volume basis;
- the live, historical, and back-cast effective ranges;
- any approved exceptions.

Compatibility MUST be explicit and testable.

A familiar ticker and plausible chart are not compatibility proof.

---

# 18. Specification Boundary

A specification MAY define:

- database schema and migrations;
- index registration storage;
- application services;
- acquisition workflow;
- parsing and normalisation;
- APIs and commands;
- user-interface behaviour;
- operational receipts;
- error reporting;
- acceptance tests.

A specification MUST NOT redefine:

- what an index is;
- index administrator or methodology identity;
- index variant;
- return type;
- calculation currency or hedging status;
- calendar or calculation-day ownership;
- publication status;
- official-close semantics;
- live versus back-cast classification;
- divisor or methodology continuity;
- provider semantics.

Those are authority facts.

---

# 19. Implementation Prohibitions

Implementation MUST NOT:

- treat a futures, ETF, CFD, or broker quote as the cash index;
- infer variant from ticker suffix conventions;
- assume every index follows one exchange calendar;
- assume the index's timezone from constituent domicile;
- use the last intraday sample as official close without authority;
- invent intrinsic volume;
- merge price-return and total-return series;
- merge local, converted, hedged, and unhedged variants;
- relabel delayed or indicative values as official real-time values;
- represent back-cast history as contemporaneously published history;
- overwrite corrected evidence;
- reconstruct index levels from constituents without methodology authority;
- continue beyond a material authority gap without a compatibility report;
- block unrelated operations because one index lane is unresolved.

---

# 20. Exceptions

An exception MUST:

- identify the exact rule varied;
- identify the affected index, variant, provider, timeframe, and range;
- state the operational reason;
- define the replacement rule;
- include approval and effective dates;
- preserve provenance;
- define expiry or review conditions.

An undocumented provider mapping or implementation branch is not an exception.

---

# 21. Amendment and Versioning

A material amendment requires a new doctrine version when it changes:

- included index types;
- index identity requirements;
- administrator or methodology precedence;
- calendar or calculation-day ownership;
- publication-state semantics;
- level, return, currency, hedging, OHLC, or volume semantics;
- provider precedence;
- live and back-cast classification;
- structural-event continuity;
- validation rules;
- subordinate timeframe obligations.

Historical versions MUST remain available for audit.

A new version MUST state:

- what changed;
- why it changed;
- affected indices, variants, and ranges;
- migration requirements;
- compatibility consequences;
- supersession date.

---

# 22. Approval Gate

This doctrine may be approved only when:

- all sections are complete;
- no drafting placeholders remain;
- market code and controlled index types are accepted;
- index-versus-tradable-product separation is accepted;
- administrator, methodology, and variant identity are accepted;
- index-specific calendar and publication authority are accepted;
- level, return, currency, hedging, OHLC, and volume semantics are accepted;
- live, official historical, and back-cast separation is accepted;
- maintenance-event and continuity rules are accepted;
- required timeframe authorities and index profiles are acknowledged;
- compatibility and exception rules are accepted;
- approval identity and date are recorded.

Approval makes this doctrine constitutional authority for subordinate index work.

---

# 23. Acceptance Statement

Approval confirms that this document defines the market-level operational truth for Indices within Fragarach II.

Approval does not register any particular index or authorise a timeframe lane by itself.

Each lane still requires approved index registration, evidence-lane registration, timeframe authority, index profile, provider compatibility, implementation specification, and acceptance proof.

---

# 24. Governing Principle

```text
An index is a governed calculation, not a traded instrument.

The methodology defines the index truth.

The timeframe defines the interval truth.

The evidence lane defines the authorised publication identity.

The specification implements that truth.

Implementation must never invent authority.

Operations is King.
```
