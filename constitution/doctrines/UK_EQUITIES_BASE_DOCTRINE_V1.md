# UK EQUITIES BASE DOCTRINE V1

**Document Class:** Constitutional Market Authority  
**Authority Layer:** Market Ecosystem  
**Authority Name:** `UK_EQUITIES_BASE_DOCTRINE_V1`  
**Market Name:** United Kingdom Equities  
**Market Code:** `EQUITIES_UK`  
**Version:** 1.0  
**Status:** DRAFT FOR APPROVAL  
**Repository Location:** `constitution/doctrines/UK_EQUITIES_BASE_DOCTRINE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Effective From:** Not effective until approved  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** PENDING  
**Approval Date:** PENDING

---

# 1. Purpose

This doctrine defines the constitutional operational truth for the United Kingdom Equities market ecosystem within Fragarach II.

It establishes the market-wide authority inherited by every UK-equities timeframe authority, evidence lane, acquisition specification, validator, native operation, migration, and acceptance proof.

It defines:

- the UK-equities market boundary;
- security, share-class, and listing membership;
- primary listing venue and market-segment identity;
- the exchange-local calendar and regular trading session;
- trading-day, week, and month ownership;
- auction, off-book, and extended-session treatment;
- approved provider roles;
- acceptable evidence and provenance;
- price, currency-unit, adjustment, and volume semantics;
- corporate-action and structural-event authority;
- market-wide validation and conflict rules;
- effective historical range;
- the boundary between market authority and timeframe authority.

This doctrine does not define interval-specific bar alignment, provider interval codes, request chunking, bar completion, or latest-closed-bar calculations. Those matters belong to approved UK-equities timeframe authorities.

---

# 2. Constitutional Position

```text
Constitution

↓

UK_EQUITIES_BASE_DOCTRINE_V1

↓

UK Equities Timeframe Authority

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides this doctrine;
2. this doctrine overrides subordinate UK-equities timeframe authorities;
3. approved timeframe authorities override implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing authority.

Legacy code, provider defaults, ticker text, sample files, current application behaviour, or common market convention are not constitutional authority unless expressly adopted.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate document may weaken a mandatory requirement in this doctrine.

---

# 4. Market Definition

## 4.1 Market Identity

United Kingdom Equities is a regulated, exchange-centred, multi-venue market ecosystem in which registered equity securities and approved equity-like listed instruments trade on recognised United Kingdom venues and may also trade across approved alternative venues or reporting channels.

A registered security may have:

- one primary listing venue;
- one named market or segment;
- multiple trading or reporting venues;
- regular-session and auction activity;
- off-book reporting;
- venue-specific or consolidated provider evidence;
- suspensions, trading halts, and exceptional schedules.

There is no constitutional assumption that every provider's ticker identifies the same security, market segment, venue scope, price-display unit, adjustment basis, or historical identity.

## 4.2 Classification

**Asset Class:** `EQUITY`  
**Instrument Type Family:** `UK_LISTED_EQUITY`  
**Venue Model:** Centralised multi-venue exchange ecosystem  
**Trading Model:** Exchange-calendar session based  
**Canonical Calendar Timezone:** `Europe/London`  
**Primary Quote Convention:** One registered security unit priced in the registered listing currency and price-display unit

## 4.3 Included Scope

This doctrine includes, when explicitly registered:

- UK exchange-listed ordinary shares;
- approved non-voting or limited-voting share classes;
- approved real estate investment trusts;
- approved listed investment companies where classified as equity securities;
- registered depositary interests or receipts admitted to a UK venue;
- venue-specific or approved consolidated UK-equities price evidence;
- suspended, cancelled, or delisted securities within approved historical ranges.

Admission is never automatic. Each security and class requires explicit instrument authority.

## 4.4 Excluded Scope

This doctrine excludes unless separately authorised:

- exchange-traded funds and exchange-traded products;
- open-ended funds and mutual funds;
- debt securities;
- preference shares unless expressly admitted as a controlled instrument type;
- warrants, rights, and nil-paid rights;
- options, futures, and other derivatives;
- private company shares;
- contracts for difference;
- spread-betting instruments;
- indices and baskets;
- synthetic or calculated prices;
- foreign ordinary shares not registered under UK-equities authority;
- over-the-counter securities without approved venue authority.

An excluded class requires another market authority or an approved amendment.

---

# 5. Instrument Membership Authority

## 5.1 Membership Rule

An instrument belongs to `EQUITIES_UK` only when:

1. the security is explicitly registered;
2. the controlled instrument type is approved under this doctrine;
3. the primary listing venue is explicit;
4. the market, segment, or trading service is explicit where material;
5. the canonical ticker is registered for an effective range;
6. stable identifiers are recorded where available;
7. provider symbol mappings are registered;
8. listing currency is explicit;
9. price-display unit is explicit;
10. calendar and session authority resolve;
11. adjustment basis is declared;
12. listing and cancellation ranges are known where applicable;
13. it is not assigned to another market doctrine.

Ticker spelling alone does not establish membership or identity.

## 5.2 Canonical Symbol

The default canonical symbol is the approved primary-listing ticker for the effective range.

Examples may include:

```text
AZN
BP.
HSBA
SHEL
VOD
```

Examples do not create automatic registration.

The canonical symbol does not by itself identify:

- primary listing venue;
- market segment;
- trading service;
- security class;
- ISIN or SEDOL;
- listing currency;
- `GBP` versus `GBX` price-display unit;
- adjustment basis;
- venue aggregation scope;
- historical continuity.

Punctuation is identity-bearing where the approved listing symbol contains punctuation.

Implementation MUST NOT silently strip, add, or normalise ticker punctuation without approved mapping authority.

## 5.3 Required Metadata

Every UK-equities registration MUST include:

- canonical symbol;
- controlled display name;
- market code `EQUITIES_UK`;
- asset class `EQUITY`;
- controlled instrument type;
- primary listing exchange name;
- primary listing venue identifier or MIC;
- market, segment, or trading service where material;
- listing currency;
- price-display unit;
- security unit definition;
- price precision;
- quantity precision where applicable;
- timezone `Europe/London` unless an approved exception exists;
- calendar authority reference;
- session authority reference;
- provider symbol mappings;
- provider venue or consolidated scope;
- price basis;
- adjustment basis;
- listing effective date;
- cancellation, delisting, or retirement date where known;
- operational status;
- registration and approval provenance.

Where material, registration MUST also include:

- ISIN;
- SEDOL;
- LEI or issuer identifier;
- security class;
- voting-right classification;
- depositary-interest or receipt ratio;
- predecessor or successor security identity;
- corporate-action lineage;
- historical ticker ranges;
- dual-listing relationship;
- suspension or restructuring status.

## 5.4 Primary Listing Venue

The primary listing venue is a constitutional property of the registered instrument.

Implementation MUST NOT infer venue from:

- ticker suffix or punctuation alone;
- provider response;
- issuer domicile;
- sterling denomination;
- a generic `London` or `UK` label;
- the venue from which one trade happened to originate.

Venue or market-segment changes require explicit effective-range authority.

## 5.5 Security Identity

A ticker is not a permanent unique identity.

Security identity MUST account for:

- ticker changes;
- share-class differences;
- schemes of arrangement;
- mergers and acquisitions;
- demergers and spin-offs;
- capital reorganisations;
- cancellations and readmissions;
- exchange or segment transfers;
- depositary-interest or receipt changes;
- issuer redomiciliation;
- symbol reuse by another issuer.

Implementation MUST NOT join histories solely because ticker text matches.

## 5.6 Stable Identifiers

Where available, UK-equities authority SHOULD retain:

- ISIN;
- SEDOL;
- venue MIC;
- issuer LEI;
- provider-specific instrument identifier.

No one identifier is sufficient on its own across every historical regime.

Identifier changes MUST be effective-dated and auditable.

## 5.7 Depositary Interests and Receipts

A depositary interest or receipt is a distinct registered security.

Its evidence MUST declare:

- controlled instrument type;
- UK listing or trading venue;
- listing and price-display currency;
- receipt or interest ratio where material;
- effective range;
- relationship to the underlying foreign security.

The underlying foreign ordinary share and the UK-listed depositary instrument MUST NOT share a canonical lane by assumption.

## 5.8 Prohibited Assumptions

Implementation MUST NOT invent:

- issuer identity;
- security class;
- instrument type;
- primary listing venue;
- market segment;
- listing currency;
- price-display unit;
- adjustment basis;
- session scope;
- provider mapping;
- corporate-action continuity;
- listing or cancellation range.

Missing authority requires a compatibility report for the affected path.

---

# 6. Canonical UK Equities Calendar Authority

## 6.1 Calendar Identity

**Calendar Authority:** `UK_EQUITIES_PRIMARY_VENUE_CALENDAR_V1`  
**Calendar Type:** Primary-listing exchange calendar  
**Timezone:** `Europe/London`

## 6.2 Governing Calendar Rule

The canonical trading calendar for a registered UK-equities instrument is the approved official calendar of its primary listing venue, interpreted in `Europe/London`.

The registration MUST resolve the instrument to a named venue calendar.

A generic Monday-through-Friday calendar, United Kingdom bank-holiday calendar, provider weekday list, or fixed annual holiday table is not sufficient authority.

## 6.3 Regular Trading Session

For securities whose approved primary venue is the London Stock Exchange regular order book, the constitutional default full-day regular session is:

```text
08:00 Europe/London
through
16:30 Europe/London
```

The official venue schedule controls the exact session, auction, early-close, and exceptional-day treatment.

This default MUST NOT be applied to another venue, market service, historical regime, or instrument without explicit authority.

## 6.4 Trading-Day Ownership

A UK-equities trading day is owned by the `Europe/London` civil date of the approved primary-venue session.

Opening auctions, continuous trading, closing auctions, and approved same-date reporting activity remain associated with that venue trading date unless a timeframe authority expressly defines another lane scope.

## 6.5 Week Ownership

A trading week consists of all approved primary-venue trading days whose local civil dates fall within the Monday-through-Friday week.

A holiday-shortened week remains one trading week.

The week is owned by the final approved trading day in that local week.

## 6.6 Month Ownership

A trading day belongs to the calendar month of its `Europe/London` trading date.

## 6.7 Holidays, Early Closes, and Exceptional Closures

The official primary-venue calendar is authoritative for:

- full-day non-trading days;
- scheduled early closes;
- special settlement or currency-unit notices where operationally relevant;
- national days of mourning;
- emergency closures;
- venue-specific exceptional schedules;
- one-off market-service changes.

A United Kingdom bank holiday is not, by itself, sufficient proof of the exact operational treatment of every market service.

A provider's missing data is not proof of a venue closure.

Calendar corrections MUST be versioned and auditable.

Historical session ownership MUST NOT be silently changed.

## 6.8 Daylight Saving

The IANA timezone rules for `Europe/London` are authoritative.

Implementation MUST NOT replace exchange-local time with a fixed UTC offset.

---

# 7. Session Authority

## 7.1 Canonical Session Model

The constitutional default session model is:

```text
UK_EQUITIES_REGULAR_SESSION_V1
```

with:

```text
Open:  Approved primary-venue regular-session open
Close: Approved primary-venue regular-session close or early close
Owner: Primary-venue local civil date in Europe/London
```

## 7.2 Regular-Session Default

Unless an instrument registration or timeframe authority expressly states otherwise, active canonical OHLC lanes under this doctrine are regular-session lanes.

Regular-session evidence MUST NOT be silently mixed with:

- pre-open indications;
- auction-only evidence;
- after-hours activity;
- off-book trade reporting;
- another trading service;
- another venue's session.

## 7.3 Auctions

Opening, intraday, and closing auctions MAY be part of the approved venue process.

Whether a provider's OHLC evidence includes:

- auction calls;
- auction uncrossing trades;
- official opening price;
- official closing price;
- post-close auction or trade-at-last activity

MUST be explicit in provider and timeframe semantics.

Implementation MUST NOT assume inclusion or exclusion.

## 7.4 Off-Book and Reported Trades

Off-book or reported trades are not automatically interchangeable with on-book continuous trading.

Evidence MUST declare whether it includes:

- on-book executions;
- off-book reports;
- delayed reports;
- negotiated trades;
- venue aggregates;
- another approved category.

A provider's combined series requires explicit scope authority.

## 7.5 Extended and Alternative Sessions

An extended-hours or alternative-service lane MAY be accepted only when:

- session scope is explicit;
- venue and trading service are explicit;
- provider semantics define the covered hours;
- lane identity distinguishes the scope where necessary;
- the applicable timeframe authority defines alignment, completion, and gap rules.

Common vendor labels such as `extended`, `all sessions`, or `London` are not sufficient authority.

## 7.6 Halts and Suspensions

A regulatory halt, venue halt, issuer suspension, cancellation, or delayed admission may create a period with no trades.

Such absence is not automatically a data gap.

The event MUST be supported by approved venue, provider, issuer, or instrument evidence, and the timeframe authority MUST define the operational consequence.

## 7.7 Precedence

```text
Approved instrument-specific exception

↓

Approved primary-venue calendar and session event

↓

Approved UK-equities timeframe authority

↓

UK_EQUITIES_BASE_DOCTRINE_V1

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
| Twelve Data | Primary automated acquisition provider | Registered UK-equities instruments and approved UK-equities timeframes | Symbol mapping, venue scope, session scope, currency unit, adjustment basis, and approved timeframe semantics MUST exist |
| Operator-supplied file | Manual evidence source | Registered UK-equities instruments and approved UK-equities timeframes | Origin, venue scope, session scope, price-display unit, adjustment basis, checksum, parser result, and provenance MUST be retained |
| Existing accepted immutable evidence | Historical evidence source | Evidence already accepted by Fragarach II | Original provenance remains immutable |
| Official exchange or issuer publication | Verification and structural-event evidence | Calendar, suspension, admission, cancellation, and corporate-action verification | Not automatically approved as OHLC acquisition evidence |

No additional consolidated feed, broker feed, exchange direct feed, or data vendor is approved by this version.

Additional providers require constitutional amendment or separate provider authority.

## 8.2 Provider Scope

Every provider mapping MUST declare whether evidence represents:

- primary venue only;
- named venue only;
- approved multi-venue aggregate;
- regular session only;
- auction-inclusive regular session;
- extended or alternative trading service;
- on-book only;
- on-book plus off-book reports;
- another expressly approved scope.

A matching ticker does not prove venue, service, session, or currency-unit equivalence.

## 8.3 Provider Semantics Boundary

Each UK-equities timeframe authority MUST define, for every approved provider:

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
- venue and market-service coverage;
- regular-session, auction, and extended-session inclusion;
- adjusted versus unadjusted fields;
- split and dividend treatment;
- `GBP`, `GBX`, or other price-display unit;
- corporate-action revision behaviour;
- historical coverage.

Implementation MUST NOT proceed for a provider/timeframe combination until those facts are approved.

## 8.4 Provider Precedence

There is no market-wide rule that the newest response, adjusted series, primary venue, sterling series, or consolidated feed automatically wins.

Compatible conflicting evidence MUST be retained and resolved only by an approved lane-resolution rule.

Silent overwrite is prohibited.

---

# 9. Evidence Authority

## 9.1 Immutability

Accepted UK-equities evidence is immutable.

A correction requires new evidence, new provenance, a new validation result, and an auditable resolution decision.

## 9.2 Acceptable Sources

Acceptable sources are:

- approved provider API responses;
- approved provider exports;
- operator-supplied files with declared venue, service, session, price-display unit, and adjustment scope;
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
- market service where material;
- session scope;
- timeframe;
- requested and received ranges;
- observed timestamp range;
- row count;
- checksum;
- acquisition timestamp;
- parser or adapter version;
- price basis;
- listing currency;
- price-display unit;
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
- strip ticker punctuation without approved mapping;
- merge regular and alternative sessions by assumption;
- merge on-book and off-book evidence by assumption;
- merge `GBP` and `GBX` values by assumption;
- convert adjusted and unadjusted prices by assumption;
- splice predecessor and successor securities without authority;
- reuse a ticker's historical evidence after identity change without approval.

---

# 10. Price, Currency-Unit, Adjustment, and Volume Semantics

## 10.1 Price

UK-equities OHLC evidence represents the provider's declared price basis within its declared venue and session scope.

The price basis MUST be one of:

- executed trade price;
- official open or close;
- venue-specific trade aggregate;
- approved multi-venue aggregate;
- bid;
- ask;
- midpoint;
- another expressly approved basis.

Unlike price bases MUST NOT be merged without construction authority.

## 10.2 Security Unit

Price is expressed per registered security unit.

For ordinary shares this is normally one share.

For depositary interests or receipts, the unit and ratio MUST follow the registered instrument authority.

## 10.3 Listing Currency and Price-Display Unit

Listing currency and price-display unit are separate material facts.

A UK-listed security may be quoted or distributed using:

- `GBP` pounds sterling;
- `GBX` pence sterling;
- another expressly registered currency or subunit.

For approved sterling conversion:

```text
100 GBX = 1 GBP
```

This arithmetic relationship does not authorise silent conversion.

Any conversion requires:

- source unit;
- target unit;
- exact factor;
- transformation authority;
- provenance;
- retained original evidence.

A 100-fold mismatch is a material validation event, not a cosmetic formatting issue.

## 10.4 Unadjusted Price Authority

Unadjusted OHLC preserves the published historical trading prices as observed for the registered security at the time and in the declared price-display unit.

Unadjusted evidence is the default evidentiary price form unless the source is explicitly registered otherwise.

## 10.5 Adjusted Price Authority

Adjusted prices are a separate transformed or provider-published evidence form.

Adjustment basis MUST declare whether it reflects:

- subdivisions or consolidations;
- cash dividends;
- special dividends;
- capital distributions;
- rights issues;
- demergers;
- another approved corporate action.

Adjusted and unadjusted evidence MUST NOT share a canonical lane unless explicit construction authority exists.

## 10.6 Volume

Volume semantics MUST declare whether quantity represents:

- on-book shares;
- total reported shares;
- venue-specific turnover quantity;
- consolidated quantity;
- notional value;
- provider estimate;
- another approved measure.

Volume from unlike venue or reporting scopes MUST NOT be compared or merged as if equivalent.

Missing volume does not invalidate price evidence unless the timeframe authority requires volume.

## 10.7 Currency Conversion

Foreign-exchange conversion is not part of raw UK-equities evidence authority.

A converted price series requires separate transformation authority, source FX evidence, timestamp alignment, precision rules, and provenance.

---

# 11. Market-Wide Validation Authority

## 11.1 Mandatory Validation

Every accepted block MUST be validated for:

- registered instrument identity;
- effective ticker range;
- primary venue and market-service compatibility;
- provider mapping;
- timeframe authority;
- timestamp parseability;
- exchange-local calendar compatibility;
- regular or declared session compatibility;
- monotonic ordering after approved normalisation;
- duplicate timestamps;
- OHLC structural validity;
- finite numeric values;
- listing currency and price-display unit;
- declared adjustment basis;
- declared venue and session scope;
- effective historical range;
- immutable checksum and provenance completeness.

## 11.2 OHLC Rules

For every accepted row:

```text
high >= open
high >= close
low <= open
low <= close
high >= low
```

Negative prices are invalid unless an approved instrument-specific exception exists.

Zero prices require explicit source or structural-event authority.

## 11.3 Calendar Rules

A bar MUST NOT be rejected merely because a generic weekday calendar disagrees with the approved venue calendar.

A bar outside the approved session or trading day requires classification as:

- alternative-session evidence;
- auction evidence;
- off-book or reported evidence;
- provider timestamp-mapping issue;
- exceptional venue event;
- incompatible evidence;
- another approved category.

Implementation MUST NOT silently shift it into the regular session.

## 11.4 Currency-Unit Validation

The validator MUST detect material evidence that may indicate `GBP` versus `GBX` confusion.

It MUST NOT automatically divide or multiply prices by 100 unless approved transformation authority applies.

Potential unit conflict requires visible classification and provenance-preserving resolution.

## 11.5 Duplicate Rule

Duplicate identity is timeframe-specific and MUST be defined by the applicable timeframe authority.

Conflicting duplicates MUST be retained as evidence and MUST NOT be silently collapsed.

## 11.6 Gap Rule

Absence of bars may result from:

- official non-trading day;
- early close;
- auction structure;
- halt or suspension;
- no eligible trade;
- provider coverage limit;
- provider outage;
- ticker or identity transition;
- genuine missing evidence.

The timeframe authority MUST define expected bars and gap materiality.

Implementation MUST NOT fabricate replacements.

## 11.7 Conflict Rule

Provider, venue, market-service, currency-unit, adjustment, or session disagreement is retained.

Resolution MUST be deterministic, provenance-aware, and authorised.

`latest received`, `largest row count`, `primary venue`, or `adjusted` is not a universal winner rule.

## 11.8 Operational Failure Boundary

Missing authority stops only the affected acquisition, validation, construction, or migration path.

It MUST NOT unnecessarily disable unrelated instruments, lanes, or the wider operations console.

**Operations is King.**

---

# 12. Corporate Actions and Structural Events

## 12.1 Governed Events

UK-equities authority MUST account for:

- subdivisions and consolidations;
- cash and stock dividends;
- special distributions;
- rights issues and open offers;
- tender offers and buybacks where identity is affected;
- schemes of arrangement;
- mergers and acquisitions;
- demergers and spin-offs;
- ticker changes;
- share-class changes;
- admission, cancellation, and readmission;
- market-segment or venue transfer;
- depositary-interest or receipt ratio changes;
- issuer redomiciliation;
- administration, insolvency, and restructuring;
- suspension and delisting;
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

## 12.3 Subdivision and Consolidation Rule

A subdivision or consolidation does not mutate accepted unadjusted evidence.

Any adjusted representation requires:

- event identity;
- effective trading date;
- adjustment factor;
- source authority;
- transformation method;
- provenance;
- separate adjusted-lane authority.

Silent historical rewriting is prohibited.

## 12.4 Dividend and Distribution Rule

Cash dividends and other distributions MUST NOT be inferred from price gaps.

Dividend or distribution adjustment requires explicit event authority and adjustment methodology.

## 12.5 Rights and Open Offers

Rights issues, open offers, and nil-paid rights may create separate temporary instruments.

Temporary rights instruments MUST NOT be merged into the ordinary-share lane unless explicit authority defines the relationship and transformation.

## 12.6 Scheme, Merger, and Demerger Rule

A scheme of arrangement, merger, acquisition, or demerger creates continuity only when approved instrument authority states the relationship and effective range.

Predecessor and successor securities remain distinct by default.

## 12.7 Cancellation and Readmission

Cancellation ends the default active range for that registration.

A later readmission requires explicit identity and continuity authority.

The same ticker after a gap does not prove the same security.

---

# 13. Effective Historical Range

## 13.1 Start Rule

There is no universal earliest date for every UK-equities instrument.

The effective start for a registered instrument is the latest of:

1. the security's approved admission or predecessor-authority date;
2. the start of the approved primary venue and market-service identity;
3. the start of the approved ticker and security-class range;
4. the start of the approved currency and price-display unit range;
5. the start of approved provider semantics;
6. the earliest reliable compatible evidence;
7. any instrument-specific authority date.

## 13.2 End Rule

The effective end is the earliest of:

- cancellation or delisting;
- merger termination;
- security retirement;
- insolvency cancellation;
- ticker or identity replacement requiring a new registration;
- venue or market-service authority termination;
- another approved structural event.

The default is `OPEN` only while no end condition applies.

## 13.3 Provider Coverage

Provider history limits restrict that provider's approved range.

They do not redefine the security's listing history.

Historical evidence outside an approved identity, venue, session, unit, adjustment, or provider range may be retained but MUST NOT enter an active canonical lane until resolved.

---

# 14. Timeframe Inheritance

Every UK-equities timeframe authority MUST inherit:

- UK-equities market identity;
- instrument and security-membership rules;
- primary listing venue and market-service authority;
- `Europe/London` calendar timezone;
- primary-venue official calendar authority;
- regular-session default;
- local-date trading-day ownership;
- early-close and exceptional-closure authority;
- explicit auction, off-book, and alternative-session separation;
- provider roles;
- evidence immutability;
- venue, session, price-basis, unit, and adjustment provenance;
- corporate-action rules;
- market-wide validation;
- effective-range logic.

A timeframe authority MUST NOT contradict these facts.

---

# 15. Required UK Equities Timeframe Authorities

| Timeframe | Required Authority | Status |
|---|---|---|
| `D1` | `UK_EQUITIES_D1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `H1` | `UK_EQUITIES_H1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M30` | `UK_EQUITIES_M30_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M5` | `UK_EQUITIES_M5_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |

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
- auction and uncrossing treatment;
- off-book and reported-trade lane treatment;
- alternative-session lane treatment;
- partial-bar and latest-closed-bar rules;
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

Before a UK-equities implementation specification begins, it MUST prove that:

- this doctrine is approved;
- the relevant timeframe authority is approved;
- the instrument is registered as `EQUITIES_UK`;
- security type and class are explicit;
- primary listing venue and market service resolve;
- provider mapping and role are valid;
- venue, session, and reporting scope are explicit;
- listing currency and price-display unit are explicit;
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
- market-service identity;
- exchange calendar;
- regular-session ownership;
- auction, off-book, or alternative-session separation;
- provider role;
- price, currency-unit, adjustment, or volume meaning;
- corporate-action continuity;
- effective-range authority.

---

# 19. Implementation Prohibitions

Implementation MUST NOT:

- infer security identity from ticker alone;
- strip or rewrite ticker punctuation without mapping authority;
- infer primary venue or market service from provider response alone;
- use a generic weekday or bank-holiday calendar;
- use a fixed UTC offset for exchange-local sessions;
- create bars on official full-day closures;
- extend regular-session bars beyond an approved early close;
- mix regular, auction-only, off-book, or alternative-session evidence silently;
- mix venue-specific and consolidated evidence silently;
- treat `GBP` and `GBX` as interchangeable values;
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
- primary venue, market service, or calendar authority;
- regular-session definition;
- auction, off-book, or alternative-session doctrine;
- trading-day, week, or month ownership;
- provider roles;
- listing currency or price-display-unit doctrine;
- price, adjustment, or volume doctrine;
- corporate-action treatment;
- effective-range logic;
- required timeframe authorities;
- inheritance rules.

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| 1.0 | 2026-07-11 | Initial UK-equities constitutional doctrine drafted | Establish market authority before timeframe implementation | PENDING |

Superseded versions remain immutable and auditable.

---

# 22. Approval Gate

This doctrine may be marked **APPROVED** only when:

- market scope is accepted;
- included instrument types are accepted;
- primary-venue, market-service, and calendar authority are accepted;
- regular-session, auction, off-book, and alternative-session rules are accepted;
- trading-day, week, and month ownership are accepted;
- provider roles are accepted;
- evidence rules are accepted;
- listing currency and price-display-unit semantics are accepted;
- price, adjustment, and volume semantics are accepted;
- validation and corporate-action rules are accepted;
- effective-range logic is accepted;
- required timeframe authorities are accepted;
- exceptions and approval identity are recorded.

---

# 23. Acceptance Statement

Upon approval:

> `UK_EQUITIES_BASE_DOCTRINE_V1` is the approved constitutional authority for the United Kingdom Equities market ecosystem within Fragarach II. All subordinate UK-equities timeframe authorities, specifications, implementations, acquisitions, validations, migrations, evidence-lane operations, and acceptance proofs MUST conform to it.

---

# 24. Governing Principle

> UK equities are exchange-calendar instruments governed operationally by explicit security identity, primary listing venue, market-service scope, local-session ownership, declared sterling price unit, immutable evidence, and auditable corporate-action continuity.

Provider convention may be mapped.

Implementation may encode.

Neither may invent authority.

**Operations is King.**
