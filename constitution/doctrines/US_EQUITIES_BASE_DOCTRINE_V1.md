# US EQUITIES BASE DOCTRINE V1

**Document Class:** Constitutional Market Authority  
**Authority Layer:** Market Ecosystem  
**Authority Name:** `US_EQUITIES_BASE_DOCTRINE_V1`  
**Market Name:** United States Equities  
**Market Code:** `EQUITIES_US`  
**Version:** 1.0  
**Status:** DRAFT FOR APPROVAL  
**Repository Location:** `constitution/doctrines/US_EQUITIES_BASE_DOCTRINE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Effective From:** Not effective until approved  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** PENDING  
**Approval Date:** PENDING

---

# 1. Purpose

This doctrine defines the constitutional operational truth for the United States Equities market ecosystem within Fragarach II.

It establishes the market-wide authority inherited by every US-equities timeframe authority, evidence lane, acquisition specification, validator, native operation, migration, and acceptance proof.

It defines:

- the US-equities market boundary;
- equity instrument and listing membership;
- primary listing venue and exchange identity;
- the exchange-local calendar and regular trading session;
- trading-day, week, and month ownership;
- extended-hours treatment;
- approved provider roles;
- acceptable evidence and provenance;
- price, adjustment, and volume semantics;
- corporate-action and structural-event authority;
- market-wide validation and conflict rules;
- effective historical range;
- the boundary between market authority and timeframe authority.

This doctrine does not define interval-specific bar alignment, provider interval codes, request chunking, bar completion, or latest-closed-bar calculations. Those matters belong to approved US-equities timeframe authorities.

---

# 2. Constitutional Position

```text
Constitution

↓

US_EQUITIES_BASE_DOCTRINE_V1

↓

US Equities Timeframe Authority

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides this doctrine;
2. this doctrine overrides subordinate US-equities timeframe authorities;
3. approved timeframe authorities override implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing authority.

Legacy code, provider defaults, ticker text, sample files, or existing application behaviour are not constitutional authority unless expressly adopted.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate document may weaken a mandatory requirement in this doctrine.

---

# 4. Market Definition

## 4.1 Market Identity

United States Equities is a regulated, exchange-centred, multi-venue market ecosystem in which registered equity securities and approved equity-like listed instruments trade on recognised United States venues and may also trade across other approved reporting or execution venues.

A security may have:

- one primary listing venue;
- multiple execution venues;
- consolidated or venue-specific provider evidence;
- regular-session and extended-hours activity;
- auctions, halts, and venue-specific interruptions.

There is no constitutional assumption that every provider's `AAPL`, `FDX`, `SHEL`, or other ticker represents the same venue scope, adjustment basis, session scope, or historical identity.

## 4.2 Classification

**Asset Class:** `EQUITY`  
**Instrument Type Family:** `US_LISTED_EQUITY`  
**Venue Model:** Centralised multi-venue exchange ecosystem  
**Trading Model:** Exchange-calendar session based  
**Canonical Calendar Timezone:** `America/New_York`  
**Primary Quote Convention:** One registered security unit priced in the listing currency

## 4.3 Included Scope

This doctrine includes, when explicitly registered:

- US exchange-listed common stock;
- registered depositary receipts;
- registered real estate investment trusts;
- other registered listed equity securities expressly admitted by instrument type;
- venue-specific or approved consolidated equity price evidence;
- suspended or delisted securities within their approved historical ranges.

## 4.4 Excluded Scope

This doctrine excludes unless separately authorised:

- exchange-traded funds and exchange-traded products;
- mutual funds;
- closed-end funds;
- preferred stock;
- warrants and rights;
- options and futures;
- over-the-counter securities without approved venue authority;
- private company shares;
- indices and baskets;
- contracts for difference;
- synthetic or calculated prices;
- foreign ordinary shares not registered under the US-equities authority.

An excluded class requires another market authority or an approved amendment.

---

# 5. Instrument Membership Authority

## 5.1 Membership Rule

An instrument belongs to `EQUITIES_US` only when:

1. the security is explicitly registered;
2. the controlled instrument type is approved under this doctrine;
3. the primary listing venue is explicit;
4. the exchange or venue identity is explicit;
5. the canonical ticker is registered for an effective range;
6. provider symbol mappings are registered;
7. listing currency is explicit;
8. calendar and session authority resolve;
9. adjustment basis is declared;
10. listing and delisting ranges are known where applicable;
11. it is not assigned to another market doctrine.

Ticker spelling alone does not establish membership or identity.

## 5.2 Canonical Symbol

The default canonical symbol is the approved primary-listing ticker for the effective range.

Examples may include:

```text
AAPL
FDX
JPM
SHEL
```

The canonical symbol does not by itself identify:

- primary listing venue;
- exchange MIC;
- security class;
- depositary-receipt status;
- adjustment basis;
- venue aggregation scope;
- historical continuity.

## 5.3 Required Metadata

Every US-equities registration MUST include:

- canonical symbol;
- controlled display name;
- market code `EQUITIES_US`;
- asset class `EQUITY`;
- controlled instrument type;
- primary listing exchange name;
- primary listing venue identifier or MIC;
- listing currency;
- security unit definition;
- price precision;
- quantity precision where applicable;
- timezone `America/New_York` unless an approved exception exists;
- calendar authority reference;
- session authority reference;
- provider symbol mappings;
- provider venue or consolidated scope;
- price basis;
- adjustment basis;
- listing effective date;
- delisting or retirement date where known;
- operational status;
- registration and approval provenance.

Where material, registration MUST also include:

- security class;
- depositary-receipt ratio;
- stable external identifier where available;
- predecessor or successor instrument identity;
- corporate-action lineage;
- historical ticker ranges;
- bankruptcy, reorganisation, or suspension status.

## 5.4 Primary Listing Venue

The primary listing venue is a constitutional property of the registered instrument.

Implementation MUST NOT infer venue from:

- ticker length;
- provider response;
- current popularity;
- a generic `US` exchange label;
- the venue from which one trade happened to originate.

Venue changes require explicit effective-range authority.

## 5.5 Security Identity

A ticker is not a permanent unique identity.

Security identity MUST account for:

- ticker changes;
- share-class differences;
- mergers and acquisitions;
- demergers and spin-offs;
- bankruptcy and reorganisation;
- relisting;
- depositary-receipt ratio changes;
- exchange transfer;
- reincorporation;
- symbol reuse by another issuer.

Implementation MUST NOT join histories solely because ticker text matches.

## 5.6 Depositary Receipts

A depositary receipt is a distinct registered security.

Its evidence MUST declare:

- depositary-receipt instrument type;
- US listing venue;
- receipt currency;
- receipt ratio where material;
- effective range;
- relationship to the underlying foreign security.

The underlying foreign ordinary share and the US depositary receipt MUST NOT share a canonical lane by assumption.

## 5.7 Prohibited Assumptions

Implementation MUST NOT invent:

- issuer identity;
- security class;
- instrument type;
- primary listing venue;
- exchange identity;
- listing currency;
- adjustment basis;
- session scope;
- provider mapping;
- corporate-action continuity;
- listing or delisting range.

Missing authority requires a compatibility report for the affected path.

---

# 6. Canonical US Equities Calendar Authority

## 6.1 Calendar Identity

**Calendar Authority:** `US_EQUITIES_PRIMARY_VENUE_CALENDAR_V1`  
**Calendar Type:** Primary-listing exchange calendar  
**Timezone:** `America/New_York`

## 6.2 Governing Calendar Rule

The canonical trading calendar for a registered US-equities instrument is the approved official calendar of its primary listing venue, interpreted in `America/New_York`.

The registration MUST resolve the instrument to a named venue calendar.

A generic weekday calendar, United States federal holiday calendar, provider weekday list, or fixed annual holiday table is not sufficient authority.

## 6.3 Regular Trading Session

The default regular trading session for approved US-listed equities is:

```text
09:30 America/New_York
through
16:00 America/New_York
```

on an approved full trading day.

On an approved early-close day, the regular session ends at the venue-authorised early close, commonly but not universally 13:00 America/New_York.

The official venue calendar controls.

## 6.4 Trading-Day Ownership

A US-equities trading day is owned by the `America/New_York` civil date of the primary venue session.

Pre-market, regular-session, after-hours, auction, and approved same-date extended activity remain associated with that venue trading date unless a timeframe authority expressly defines a separate overnight treatment.

## 6.5 Week Ownership

A trading week consists of all approved primary-venue trading days whose local civil dates fall within the Monday-through-Friday week.

A holiday-shortened week remains one trading week.

The week is owned by the final approved trading day in that local week.

## 6.6 Month Ownership

A trading day belongs to the calendar month of its `America/New_York` trading date.

## 6.7 Holidays, Early Closes, and Exceptional Closures

The official primary-venue calendar is authoritative for:

- full-day holidays;
- scheduled early closes;
- national days of mourning;
- emergency closures;
- weather-related closures;
- venue-specific exceptional schedules.

A United States federal holiday is not automatically a market closure.

A provider's missing data is not proof of a venue closure.

Calendar corrections MUST be versioned and auditable.

Historical session ownership MUST NOT be silently changed.

## 6.8 Daylight Saving

The IANA timezone rules for `America/New_York` are authoritative.

Implementation MUST NOT replace exchange-local time with a fixed UTC offset.

---

# 7. Session Authority

## 7.1 Canonical Session Model

The constitutional default session model is:

```text
US_EQUITIES_REGULAR_SESSION_V1
```

with:

```text
Open:  Primary venue regular-session open
Close: Primary venue regular-session close or approved early close
Owner: Primary venue local civil date in America/New_York
```

## 7.2 Regular-Session Default

Unless an instrument registration or timeframe authority expressly states otherwise, active canonical OHLC lanes under this doctrine are regular-session lanes.

Regular-session evidence MUST NOT be silently mixed with extended-hours evidence.

## 7.3 Extended Hours

Pre-market and after-hours activity MAY be accepted only when:

- session scope is explicit;
- provider semantics define the covered hours;
- the lane identity distinguishes the scope where necessary;
- the applicable timeframe authority defines alignment, completion, and gap rules.

Common provider windows such as 04:00–09:30 and 16:00–20:00 New York time are not automatically constitutional for every venue, instrument, or historical period.

## 7.4 Auctions

Opening and closing auctions are part of the regular exchange process where recognised by the primary venue.

Whether a provider's OHLC bar includes auction prints MUST be explicit in provider semantics.

Implementation MUST NOT assume inclusion or exclusion.

## 7.5 Halts and Suspensions

A regulatory halt, volatility halt, venue halt, issuer suspension, or delisting may create a period with no trades.

Such absence is not automatically a data gap.

The event MUST be supported by approved venue, provider, or instrument evidence, and the timeframe authority MUST define the operational consequence.

## 7.6 Precedence

```text
Approved instrument-specific exception

↓

Approved primary-venue calendar and session event

↓

Approved US-equities timeframe authority

↓

US_EQUITIES_BASE_DOCTRINE_V1

↓

Approved provider semantics

↓

Implementation
```

Provider convention may map into constitutional truth. It does not override it.

---

# 8. Provider Authority

## 8.1 Approved Roles

| Source | Approved Role | Scope | Conditions |
|---|---|---|---|
| Twelve Data | Primary automated acquisition provider | Registered US-equities instruments and approved US-equities timeframes | Symbol mapping, venue scope, session scope, adjustment basis, and approved timeframe semantics MUST exist |
| Operator-supplied file | Manual evidence source | Registered US-equities instruments and approved US-equities timeframes | Origin, venue scope, session scope, adjustment basis, checksum, parser result, and provenance MUST be retained |
| Existing accepted immutable evidence | Historical evidence source | Evidence already accepted by Fragarach II | Original provenance remains immutable |
| Official exchange or issuer publication | Verification and structural-event evidence | Calendar, halt, listing, delisting, and corporate-action verification | Not automatically approved as OHLC acquisition evidence |

No additional consolidated feed, broker feed, exchange direct feed, or data vendor is approved by this version.

Additional providers require constitutional amendment or separate provider authority.

## 8.2 Provider Scope

Every provider mapping MUST declare whether evidence represents:

- primary venue only;
- named venue only;
- approved multi-venue aggregate;
- consolidated US market activity;
- regular session only;
- extended hours;
- all provider-defined sessions;
- another expressly approved scope.

A matching ticker does not prove venue or session equivalence.

## 8.3 Provider Semantics Boundary

Each US-equities timeframe authority MUST define, for every approved provider:

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
- regular versus extended-hours inclusion;
- opening and closing auction treatment;
- adjusted versus unadjusted fields;
- split and dividend treatment;
- corporate-action revision behaviour;
- historical coverage.

Implementation MUST NOT proceed for a provider/timeframe combination until those facts are approved.

## 8.4 Provider Precedence

There is no market-wide rule that the newest response, adjusted series, primary venue, or consolidated feed automatically wins.

Compatible conflicting evidence MUST be retained and resolved only by an approved lane-resolution rule.

Silent overwrite is prohibited.

---

# 9. Evidence Authority

## 9.1 Immutability

Accepted US-equities evidence is immutable.

A correction requires new evidence, new provenance, a new validation result, and an auditable resolution decision.

## 9.2 Acceptable Sources

Acceptable sources are:

- approved provider API responses;
- approved provider exports;
- operator-supplied files with declared venue, session, and adjustment scope;
- existing immutable Fragarach II evidence;
- official venue or issuer publications for calendar and structural-event verification.

## 9.3 Evidence Identity

Every evidence block MUST identify:

- canonical instrument;
- source symbol;
- provider or source identity;
- source role;
- primary listing venue;
- provider venue or consolidation scope;
- session scope;
- timeframe;
- requested and received ranges;
- observed timestamp range;
- row count;
- checksum;
- acquisition timestamp;
- parser or adapter version;
- price basis;
- adjustment basis;
- volume basis;
- timestamp interpretation;
- evidence and validation status.

## 9.4 Prohibitions

Implementation MUST NOT:

- fabricate missing bars;
- mutate accepted evidence;
- discard venue or provider conflicts without record;
- shift timestamps without approved mapping;
- merge regular and extended-hours data by assumption;
- merge primary-venue and consolidated data by assumption;
- convert adjusted and unadjusted prices by assumption;
- splice predecessor and successor securities without authority;
- reuse a ticker's historical evidence after identity change without approval.

---

# 10. Price, Adjustment, and Volume Semantics

## 10.1 Price

US-equities OHLC evidence represents the provider's declared price basis within its declared venue and session scope.

The price basis MUST be one of:

- executed trade price;
- official open or close;
- venue-specific trade aggregate;
- consolidated trade aggregate;
- bid;
- ask;
- midpoint;
- another expressly approved basis.

Unlike price bases MUST NOT be merged without construction authority.

## 10.2 Security Unit

Price is expressed per registered security unit.

For common stock this is normally one share.

For depositary receipts, units and ratios MUST follow the registered receipt authority.

## 10.3 Unadjusted Price Authority

Unadjusted OHLC preserves the published historical trading prices as observed for the registered security at the time.

Unadjusted evidence is the default evidentiary price form unless a provider source is explicitly registered otherwise.

## 10.4 Adjusted Price Authority

Adjusted prices are a separate transformed or provider-published evidence form.

Adjustment basis MUST declare whether it reflects:

- stock splits;
- reverse splits;
- cash dividends;
- capital distributions;
- rights issues;
- spin-offs;
- another corporate action.

Adjusted and unadjusted series MUST NOT share one lane without explicit construction authority.

Implementation MUST NOT derive adjustment factors from price discontinuity alone.

## 10.5 Volume

Volume may mean:

- shares or security units traded on one venue;
- consolidated reported shares or units;
- provider-defined aggregate volume;
- another declared measure.

Venue and aggregation scope MUST be explicit.

Volume from unlike scopes MUST NOT be treated as directly comparable without authority.

## 10.6 Zero, Null, and Absent Volume

Zero, null, or absent volume MAY be valid depending on provider, venue, session, and instrument semantics.

Measured zero SHOULD remain distinguishable from absent or unknown volume.

A valid OHLC bar with zero volume SHOULD receive a warning unless the source semantics expressly support it.

Missing volume MUST NOT automatically invalidate valid OHLC evidence unless the timeframe authority makes it mandatory.

---

# 11. Market-Wide Validation Authority

## 11.1 Mandatory Validation

Every US-equities row MUST be evaluated for:

- registered security identity;
- approved instrument type;
- primary listing venue;
- approved provider mapping;
- declared venue or consolidation scope;
- declared session scope;
- declared adjustment basis;
- timestamp parseability and exchange-local interpretation;
- calendar and session eligibility;
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

Negative equity prices are invalid unless a named constitutional exception permits them.

A zero equity price is invalid unless a named technical or historical exception permits it.

## 11.2 Calendar and Session Validation

Regular-session evidence MUST be evaluated against the primary venue calendar, including early closes and exceptional closures.

Extended-hours evidence MUST be evaluated against its declared provider and session scope.

A missing interval during a halt or suspension is not automatically a gap.

Exact expectedness, tolerance, and materiality belong to the timeframe authority.

## 11.3 Lane Identity and Conflict

The constitutional lane key begins with:

```text
registered instrument + approved timeframe + canonical timestamp
```

Session scope, adjustment basis, or venue scope MAY be additional lane dimensions where authority requires them.

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

Usable accepted evidence MUST remain available when a provider, venue, corporate-action review, or newer acquisition is delayed, stale, incomplete, or under review.

Warnings MUST remain visible.

Missing authority stops only the affected acquisition, validation, construction, or migration path.

It MUST NOT unnecessarily disable unrelated instruments, lanes, or the wider operations console.

**Operations is King.**

---

# 12. Corporate Actions and Structural Events

## 12.1 Governed Events

US-equities authority MUST account for:

- stock splits and reverse splits;
- cash and stock dividends;
- special distributions;
- rights issues;
- tender offers;
- mergers and acquisitions;
- demergers and spin-offs;
- ticker changes;
- share-class changes;
- exchange transfers;
- depositary-receipt ratio changes;
- bankruptcy and reorganisation;
- suspension and delisting;
- relisting;
- issuer identity change;
- symbol reuse;
- provider adjustment-methodology change.

## 12.2 Continuity Rule

No corporate or structural event automatically permits historical continuity.

Authority MUST decide:

- whether pre-event and post-event securities are the same identity;
- whether a new registration is required;
- whether one lane may span the event;
- whether adjusted continuity is authorised;
- whether historical evidence requires reclassification;
- the effective transition timestamp or trading date.

Implementation MUST NOT splice histories by assumption.

## 12.3 Split and Reverse-Split Rule

A split or reverse split does not mutate accepted unadjusted evidence.

Any adjusted representation requires:

- the event identity;
- effective trading date;
- adjustment factor;
- source authority;
- transformation method;
- provenance;
- separate adjusted-lane authority.

Silent historical rewriting is prohibited.

## 12.4 Dividend Rule

Cash dividends and other distributions MUST NOT be inferred from price gaps.

Dividend adjustment requires explicit event authority and adjustment methodology.

## 12.5 Merger, Acquisition, and Spin-Off Rule

A merger, acquisition, or spin-off creates continuity only when approved instrument authority states the relationship and effective range.

The predecessor and successor securities remain distinct by default.

## 12.6 Delisting and Relisting

Delisting ends the default active range for that registration.

A later relisting requires explicit identity and continuity authority.

The same ticker after a gap does not prove the same security.

---

# 13. Effective Historical Range

## 13.1 Start Rule

There is no universal earliest date for every US-equities instrument.

The effective start for a registered instrument is the latest of:

1. the security's approved listing or predecessor-authority date;
2. the start of the approved primary venue identity;
3. the start of the approved ticker and security-class range;
4. the start of approved provider semantics;
5. the earliest reliable compatible evidence;
6. any instrument-specific authority date.

## 13.2 End Rule

The effective end is the earliest of:

- delisting;
- merger termination;
- security retirement;
- bankruptcy cancellation;
- ticker or identity replacement requiring a new registration;
- venue authority termination;
- another approved structural event.

The default is `OPEN` only while no end condition applies.

## 13.3 Provider Coverage

Provider history limits restrict that provider's approved range.

They do not redefine the security's listing history.

Historical evidence outside an approved identity, venue, adjustment, or provider range may be retained but MUST NOT enter an active canonical lane until resolved.

---

# 14. Timeframe Inheritance

Every US-equities timeframe authority MUST inherit:

- US-equities market identity;
- instrument and security-membership rules;
- primary listing venue authority;
- `America/New_York` calendar timezone;
- primary-venue official calendar authority;
- regular-session default;
- local-date trading-day ownership;
- early-close and exceptional-closure authority;
- explicit extended-hours separation;
- provider roles;
- evidence immutability;
- venue, session, price-basis, and adjustment provenance;
- corporate-action rules;
- market-wide validation;
- effective-range logic.

A timeframe authority MUST NOT contradict these facts.

---

# 15. Required US Equities Timeframe Authorities

| Timeframe | Required Authority | Status |
|---|---|---|
| `D1` | `US_EQUITIES_D1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `H1` | `US_EQUITIES_H1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M30` | `US_EQUITIES_M30_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M5` | `US_EQUITIES_M5_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |

Additional timeframe authorities require an approved amendment or later doctrine version.

Existing accepted D1 behaviour is not silently invalidated or re-authorised by this draft.

---

# 16. Explicit Delegation to Timeframe Authorities

The following are intentionally delegated:

- interval duration and alignment;
- canonical bar timestamp meaning;
- provider timestamp mapping;
- regular-session bar alignment;
- early-close bar treatment;
- extended-hours lane treatment;
- partial-bar and latest-closed-bar rules;
- opening and closing auction inclusion;
- direct versus derived precedence;
- rollup eligibility;
- request codes, limits, pagination, chunking, and overlap;
- exact duplicate fields;
- halt and suspension gap classification;
- gap materiality;
- freshness thresholds;
- timeframe-specific effective ranges.

These are not implementation choices.

Implementation MUST wait for approved timeframe authority.

---

# 17. Compatibility Requirements

Before a US-equities implementation specification begins, it MUST prove that:

- this doctrine is approved;
- the relevant timeframe authority is approved;
- the instrument is registered as `EQUITIES_US`;
- security type and class are explicit;
- primary listing venue and calendar resolve;
- provider mapping and role are valid;
- venue and session scope are explicit;
- price and adjustment basis are explicit;
- listing and effective range are known;
- unresolved corporate-action identity does not affect the requested range;
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
- security identity;
- instrument type;
- primary listing venue;
- exchange calendar;
- regular-session ownership;
- extended-hours separation;
- provider role;
- price, adjustment, or volume meaning;
- corporate-action continuity;
- effective-range authority.

---

# 19. Implementation Prohibitions

Implementation MUST NOT:

- infer security identity from ticker alone;
- infer primary venue from provider response alone;
- use a generic weekday or federal-holiday calendar;
- use a fixed UTC offset for exchange-local sessions;
- create bars on official full-day closures;
- extend regular-session bars beyond an approved early close;
- mix regular and extended-hours evidence silently;
- mix primary-venue and consolidated evidence silently;
- mix adjusted and unadjusted evidence silently;
- derive corporate actions from price gaps alone;
- splice predecessor and successor securities without authority;
- silently rewrite timestamps;
- silently overwrite conflicts;
- fabricate bars;
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
- included security classes;
- primary venue or calendar authority;
- regular-session definition;
- extended-hours doctrine;
- trading-day, week, or month ownership;
- provider roles;
- price, adjustment, or volume doctrine;
- corporate-action treatment;
- effective-range logic;
- required timeframe authorities;
- inheritance rules.

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| 1.0 | 2026-07-11 | Initial US-equities constitutional doctrine drafted | Establish market authority before timeframe implementation | PENDING |

Superseded versions remain immutable and auditable.

---

# 22. Approval Gate

This doctrine may be marked **APPROVED** only when:

- market scope is accepted;
- included instrument types are accepted;
- primary-venue and calendar authority are accepted;
- regular-session and extended-hours rules are accepted;
- trading-day, week, and month ownership are accepted;
- provider roles are accepted;
- evidence rules are accepted;
- price, adjustment, and volume semantics are accepted;
- validation and corporate-action rules are accepted;
- effective-range logic is accepted;
- required timeframe authorities are accepted;
- exceptions and approval identity are recorded.

---

# 23. Acceptance Statement

Upon approval:

> `US_EQUITIES_BASE_DOCTRINE_V1` is the approved constitutional authority for the United States Equities market ecosystem within Fragarach II. All subordinate US-equities timeframe authorities, specifications, implementations, acquisitions, validations, migrations, evidence-lane operations, and acceptance proofs MUST conform to it.

---

# 24. Governing Principle

> US equities are exchange-calendar instruments governed operationally by explicit security identity, primary listing venue, regular-session ownership, declared adjustment and venue scope, immutable evidence, and auditable corporate-action continuity.

Provider convention may be mapped.

Implementation may encode.

Neither may invent authority.

**Operations is King.**
