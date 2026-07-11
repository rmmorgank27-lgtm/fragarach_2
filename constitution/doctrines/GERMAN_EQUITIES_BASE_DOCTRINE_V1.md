# GERMAN EQUITIES BASE DOCTRINE V1

**Document Class:** Constitutional Market Authority  
**Authority Layer:** Market Ecosystem  
**Authority Name:** `GERMAN_EQUITIES_BASE_DOCTRINE_V1`  
**Market Name:** German Equities  
**Market Code:** `EQUITIES_DE`  
**Version:** 1.0  
**Status:** DRAFT FOR APPROVAL  
**Repository Location:** `constitution/doctrines/GERMAN_EQUITIES_BASE_DOCTRINE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Effective From:** Not effective until approved  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** PENDING  
**Approval Date:** PENDING

---

# 1. Purpose

This doctrine defines the constitutional operational truth for the German Equities market ecosystem within Fragarach II.

It establishes the market-wide authority inherited by every German-equities timeframe authority, evidence lane, acquisition specification, validator, native operation, migration, and acceptance proof.

It defines:

- the German-equities market boundary;
- security, share-class, and listing membership;
- venue, trading-system, and market-segment identity;
- the exchange-local calendar and regular trading session;
- trading-day, week, and month ownership;
- auction and extended-session treatment;
- approved provider roles;
- acceptable evidence and provenance;
- price, currency, adjustment, and volume semantics;
- corporate-action and structural-event authority;
- market-wide validation and conflict rules;
- effective historical range;
- the boundary between market authority and timeframe authority.

This doctrine does not define interval-specific bar alignment, provider interval codes, request chunking, bar completion, or latest-closed-bar calculations. Those matters belong to approved German-equities timeframe authorities.

---

# 2. Constitutional Position

```text
Constitution

↓

GERMAN_EQUITIES_BASE_DOCTRINE_V1

↓

German Equities Timeframe Authority

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides this doctrine;
2. this doctrine overrides subordinate German-equities timeframe authorities;
3. approved timeframe authorities override implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing authority.

Legacy code, provider defaults, ticker text, sample files, current application behaviour, or a generic `Germany` exchange label are not constitutional authority unless expressly adopted.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate document may weaken a mandatory requirement in this doctrine.

---

# 4. Market Definition

## 4.1 Market Identity

German Equities is a regulated, exchange-centred, multi-venue market ecosystem in which registered equity securities and approved equity-like listed instruments trade through recognised German venues and trading systems.

The ecosystem includes materially distinct venue and trading-system scopes.

Examples include:

- Xetra electronic trading;
- Börse Frankfurt trading;
- other recognised German exchanges or multilateral venues;
- venue-specific auctions and extended services;
- provider-specific venue aggregates.

These scopes are not constitutionally interchangeable.

A security may have:

- one approved primary listing or reference venue;
- multiple German trading venues;
- multiple venue-specific symbols or mnemonics;
- regular, auction, and extended-session activity;
- venue-specific or aggregated provider evidence;
- suspensions, interruptions, and exceptional schedules.

There is no constitutional assumption that every provider's ticker identifies the same security, venue, trading system, session scope, adjustment basis, or historical identity.

## 4.2 Classification

**Asset Class:** `EQUITY`  
**Instrument Type Family:** `DE_LISTED_EQUITY`  
**Venue Model:** Centralised multi-venue exchange ecosystem  
**Trading Model:** Exchange-calendar session based  
**Canonical Calendar Timezone:** `Europe/Berlin`  
**Primary Quote Convention:** One registered security unit priced in the registered trading currency

## 4.3 Included Scope

This doctrine includes, when explicitly registered:

- German exchange-listed ordinary or common shares;
- approved registered or bearer share classes;
- approved preference share classes;
- approved real estate investment companies;
- approved depositary receipts or certificates classified as equity securities;
- venue-specific or approved aggregated German-equities price evidence;
- suspended or delisted securities within approved historical ranges.

Admission is never automatic. Each security, class, venue, and effective range requires explicit authority.

## 4.4 Excluded Scope

This doctrine excludes unless separately authorised:

- exchange-traded funds and exchange-traded products;
- mutual funds and open-ended funds;
- bonds and other debt securities;
- participation certificates;
- warrants, subscription rights, and options;
- futures and other derivatives;
- contracts for difference;
- private company shares;
- indices and baskets;
- synthetic or calculated prices;
- foreign securities merely traded in Germany without approved German-equities registration;
- over-the-counter securities without approved venue authority.

An excluded class requires another market authority or an approved amendment.

---

# 5. Instrument Membership Authority

## 5.1 Membership Rule

An instrument belongs to `EQUITIES_DE` only when:

1. the security is explicitly registered;
2. the controlled instrument type is approved under this doctrine;
3. the approved primary listing or reference venue is explicit;
4. the venue MIC and trading system are explicit;
5. the market segment is explicit where material;
6. the canonical symbol or mnemonic is registered for an effective range;
7. ISIN is recorded where available;
8. WKN is recorded where available and applicable;
9. provider symbol mappings are registered;
10. trading currency is explicit;
11. calendar and session authority resolve;
12. adjustment basis is declared;
13. listing and delisting ranges are known where applicable;
14. it is not assigned to another market doctrine.

Ticker or mnemonic spelling alone does not establish membership or identity.

## 5.2 Canonical Symbol

The default canonical symbol is the approved venue-specific primary symbol or mnemonic for the effective range.

Examples may include:

```text
ADS
ALV
BAS
BMW
DTE
SAP
SIE
```

Examples do not create automatic registration.

The canonical symbol does not by itself identify:

- ISIN;
- WKN;
- venue or MIC;
- Xetra versus Frankfurt scope;
- market segment;
- share class;
- registered versus bearer form;
- trading currency;
- adjustment basis;
- historical continuity.

## 5.3 Required Metadata

Every German-equities registration MUST include:

- canonical symbol;
- controlled display name;
- market code `EQUITIES_DE`;
- asset class `EQUITY`;
- controlled instrument type;
- approved primary listing or reference exchange name;
- venue MIC;
- trading-system identity;
- market segment where material;
- ISIN where available;
- WKN where available and applicable;
- trading currency;
- security unit definition;
- price precision;
- quantity precision where applicable;
- timezone `Europe/Berlin` unless an approved exception exists;
- calendar authority reference;
- session authority reference;
- provider symbol mappings;
- provider venue or aggregate scope;
- price basis;
- adjustment basis;
- listing effective date;
- delisting, cancellation, or retirement date where known;
- operational status;
- registration and approval provenance.

Where material, registration MUST also include:

- issuer LEI;
- share class;
- voting-right classification;
- registered or bearer form;
- predecessor or successor security identity;
- corporate-action lineage;
- historical ticker or mnemonic ranges;
- dual-listing or cross-listing relationship;
- suspension, insolvency, or restructuring status.

## 5.4 Venue and Trading-System Identity

Venue and trading-system identity are constitutional properties.

Implementation MUST distinguish, where applicable:

- Xetra electronic trading;
- Börse Frankfurt;
- another named German exchange;
- another named multilateral or regulated venue;
- venue-specific auction evidence;
- provider-defined German aggregate evidence.

Implementation MUST NOT infer venue from:

- ticker alone;
- provider response;
- issuer domicile;
- euro denomination;
- a generic `Frankfurt`, `Germany`, or `DE` label;
- one observed execution.

Venue, trading-system, or segment changes require explicit effective-range authority.

## 5.5 Security Identity

A ticker or mnemonic is not a permanent unique identity.

Security identity MUST account for:

- ISIN changes;
- WKN changes;
- ticker or mnemonic changes;
- share-class differences;
- registered versus bearer share changes;
- mergers and acquisitions;
- demergers and spin-offs;
- capital increases and reductions;
- legal-form or issuer changes;
- delisting and relisting;
- venue transfer;
- symbol reuse by another issuer.

Implementation MUST NOT join histories solely because ticker text matches.

## 5.6 ISIN and WKN Authority

ISIN is a strong security identifier but does not by itself define:

- venue;
- trading system;
- session;
- price currency;
- adjustment basis;
- lane continuity.

WKN is useful historical and operational metadata but MUST NOT replace explicit venue, class, and effective-range authority.

Identifier mappings MUST be effective-dated and auditable.

## 5.7 Foreign Securities Traded in Germany

A foreign security traded on a German venue is not automatically a German-equities instrument.

Registration MUST explicitly decide whether the canonical market authority is:

- the security's primary foreign listing doctrine;
- `EQUITIES_DE` for a German venue-specific lane;
- another approved authority.

Different market authorities and venue-specific lanes MUST NOT be merged by assumption.

## 5.8 Prohibited Assumptions

Implementation MUST NOT invent:

- issuer identity;
- security class;
- instrument type;
- venue or trading system;
- market segment;
- ISIN or WKN mapping;
- trading currency;
- adjustment basis;
- session scope;
- provider mapping;
- corporate-action continuity;
- listing or delisting range.

Missing authority requires a compatibility report for the affected path.

---

# 6. Canonical German Equities Calendar Authority

## 6.1 Calendar Identity

**Calendar Authority:** `GERMAN_EQUITIES_PRIMARY_VENUE_CALENDAR_V1`  
**Calendar Type:** Venue and trading-system calendar  
**Timezone:** `Europe/Berlin`

## 6.2 Governing Calendar Rule

The canonical trading calendar for a registered German-equities instrument is the approved official calendar of its registered venue and trading system, interpreted in `Europe/Berlin`.

The registration MUST resolve the instrument to a named venue calendar.

A generic Monday-through-Friday calendar, German public-holiday calendar, provider weekday list, or fixed annual holiday table is not sufficient authority.

## 6.3 Xetra Regular Trading Session

For instruments whose approved canonical venue and trading system is Xetra, the constitutional default full-day continuous trading session is:

```text
09:00 Europe/Berlin
through
17:30 Europe/Berlin
```

Opening, intraday, and closing auction phases are governed by the official Xetra schedule and the applicable timeframe authority.

This default MUST NOT be applied to Börse Frankfurt, an extended Xetra service, another German venue, or another historical regime without explicit authority.

## 6.4 Other Venue Sessions

Börse Frankfurt and other German venues may have materially different trading hours and services.

Their evidence requires:

- explicit venue identity;
- explicit trading-system identity;
- approved venue calendar;
- approved session model;
- provider semantics;
- separate lane identity where necessary.

A generic German-equities session is prohibited.

## 6.5 Trading-Day Ownership

A German-equities trading day is owned by the `Europe/Berlin` civil date of the approved venue session.

Opening auctions, continuous trading, closing auctions, and approved same-date extended activity remain associated with that venue trading date unless a timeframe authority expressly defines another lane scope.

## 6.6 Week Ownership

A trading week consists of all approved venue trading days whose local civil dates fall within the Monday-through-Friday week.

A holiday-shortened week remains one trading week.

The week is owned by the final approved trading day in that local week.

## 6.7 Month Ownership

A trading day belongs to the calendar month of its `Europe/Berlin` trading date.

## 6.8 Holidays, Early Closes, and Exceptional Closures

The official venue and trading-system calendar is authoritative for:

- full-day non-trading days;
- early closes or shortened services;
- special auction schedules;
- emergency closures;
- technical suspension or interruption;
- venue-specific exceptional schedules;
- one-off service changes.

A German public holiday is not automatically a closure for every venue or trading system.

A provider's missing data is not proof of a venue closure.

Calendar corrections MUST be versioned and auditable.

Historical session ownership MUST NOT be silently changed.

## 6.9 Daylight Saving

The IANA timezone rules for `Europe/Berlin` are authoritative.

Implementation MUST NOT replace exchange-local time with a fixed UTC offset.

---

# 7. Session Authority

## 7.1 Canonical Session Model

The constitutional session model is venue-specific.

For an approved Xetra regular lane:

```text
GERMAN_EQUITIES_XETRA_REGULAR_SESSION_V1
```

with:

```text
Open:  Approved Xetra regular-session open
Close: Approved Xetra regular-session close
Owner: Xetra local civil date in Europe/Berlin
```

Another venue MUST use its own approved session authority.

## 7.2 Regular-Session Default

Unless an instrument registration or timeframe authority expressly states otherwise, an active canonical German-equities OHLC lane represents the regular session of its registered canonical venue and trading system.

Evidence from unlike venues or services MUST NOT be silently mixed.

## 7.3 Auctions

Opening, intraday, volatility, and closing auctions MAY form part of the approved venue process.

Whether provider OHLC evidence includes:

- auction calls;
- uncrossing trades;
- official opening price;
- official closing price;
- volatility-interruption auctions;
- post-close activity

MUST be explicit in provider and timeframe semantics.

Implementation MUST NOT assume inclusion or exclusion.

## 7.4 Extended Trading Services

Early or late trading services MAY be accepted only when:

- venue and service are explicit;
- covered hours are explicit;
- provider semantics are approved;
- lane identity distinguishes the scope where necessary;
- the timeframe authority defines alignment, completion, and gap rules.

Extended service evidence MUST NOT be silently merged into the Xetra regular lane or another venue's regular lane.

## 7.5 Volatility Interruptions, Halts, and Suspensions

A volatility interruption, regulatory halt, venue interruption, issuer suspension, or delisting may create a period with no continuous trades.

Such absence is not automatically a data gap.

The event MUST be supported by approved venue, provider, issuer, or instrument evidence, and the timeframe authority MUST define the operational consequence.

## 7.6 Precedence

```text
Approved instrument-specific exception

↓

Approved venue and trading-system calendar or event

↓

Approved German-equities timeframe authority

↓

GERMAN_EQUITIES_BASE_DOCTRINE_V1

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
| Twelve Data | Primary automated acquisition provider | Registered German-equities instruments and approved German-equities timeframes | Symbol mapping, venue, trading-system scope, session scope, currency, adjustment basis, and approved timeframe semantics MUST exist |
| Operator-supplied file | Manual evidence source | Registered German-equities instruments and approved German-equities timeframes | Origin, venue, trading-system scope, session scope, currency, adjustment basis, checksum, parser result, and provenance MUST be retained |
| Existing accepted immutable evidence | Historical evidence source | Evidence already accepted by Fragarach II | Original provenance remains immutable |
| Official exchange or issuer publication | Verification and structural-event evidence | Calendar, interruption, listing, delisting, and corporate-action verification | Not automatically approved as OHLC acquisition evidence |

No additional consolidated feed, broker feed, exchange direct feed, or data vendor is approved by this version.

Additional providers require constitutional amendment or separate provider authority.

## 8.2 Provider Scope

Every provider mapping MUST declare whether evidence represents:

- Xetra only;
- Börse Frankfurt only;
- another named venue only;
- a named trading service;
- an approved German multi-venue aggregate;
- regular session only;
- auction-inclusive session;
- extended service;
- another expressly approved scope.

A matching ticker or ISIN does not prove venue, trading-system, or session equivalence.

## 8.3 Provider Semantics Boundary

Each German-equities timeframe authority MUST define, for every approved provider:

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
- venue and trading-system coverage;
- regular, auction, and extended-session inclusion;
- adjusted versus unadjusted fields;
- split, dividend, and rights treatment;
- corporate-action revision behaviour;
- historical coverage.

Implementation MUST NOT proceed for a provider/timeframe combination until those facts are approved.

## 8.4 Provider Precedence

There is no market-wide rule that the newest response, Xetra series, longest session, adjusted series, or multi-venue aggregate automatically wins.

Compatible conflicting evidence MUST be retained and resolved only by an approved lane-resolution rule.

Silent overwrite is prohibited.

---

# 9. Evidence Authority

## 9.1 Immutability

Accepted German-equities evidence is immutable.

A correction requires new evidence, new provenance, a new validation result, and an auditable resolution decision.

## 9.2 Acceptable Sources

Acceptable sources are:

- approved provider API responses;
- approved provider exports;
- operator-supplied files with declared venue, trading-system, session, currency, and adjustment scope;
- existing immutable Fragarach II evidence;
- official venue or issuer publications for calendar and structural-event verification.

## 9.3 Evidence Identity

Every evidence block MUST identify:

- canonical instrument;
- source symbol or mnemonic;
- ISIN where available;
- provider or source identity;
- source role;
- approved canonical venue;
- provider venue or aggregate scope;
- trading-system identity;
- session scope;
- timeframe;
- requested and received ranges;
- observed timestamp range;
- row count;
- checksum;
- acquisition timestamp;
- parser or adapter version;
- price basis;
- trading currency;
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
- merge Xetra and Frankfurt evidence by assumption;
- merge regular and extended services by assumption;
- merge venue-specific and aggregate evidence by assumption;
- convert adjusted and unadjusted prices by assumption;
- splice predecessor and successor securities without authority;
- reuse a ticker's historical evidence after identity change without approval.

---

# 10. Price, Currency, Adjustment, and Volume Semantics

## 10.1 Price

German-equities OHLC evidence represents the provider's declared price basis within its declared venue, trading-system, and session scope.

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

For shares this is normally one share.

Any depositary, certificate, or ratio-based unit MUST follow the registered instrument authority.

## 10.3 Trading Currency

Trading currency MUST be explicit.

Euro denomination is common but MUST NOT be inferred from:

- German issuer domicile;
- German venue;
- ticker;
- ISIN prefix;
- provider default.

A different trading currency requires explicit registration.

## 10.4 Unadjusted Price Authority

Unadjusted OHLC preserves the published historical trading prices as observed for the registered security, venue, trading system, and currency at the time.

Unadjusted evidence is the default evidentiary price form unless the source is explicitly registered otherwise.

## 10.5 Adjusted Price Authority

Adjusted prices are a separate transformed or provider-published evidence form.

Adjustment basis MUST declare whether it reflects:

- stock splits or consolidations;
- cash dividends;
- special distributions;
- subscription rights;
- spin-offs;
- capital increases or reductions;
- another approved corporate action.

Adjusted and unadjusted evidence MUST NOT share a canonical lane unless explicit construction authority exists.

## 10.6 Volume

Volume semantics MUST declare whether quantity represents:

- venue-executed shares;
- order-book volume;
- auction-inclusive volume;
- multi-venue aggregate volume;
- turnover value;
- provider estimate;
- another approved measure.

Volume from unlike venues or services MUST NOT be compared or merged as if equivalent.

Missing volume does not invalidate price evidence unless the timeframe authority requires volume.

## 10.7 Currency Conversion

Foreign-exchange conversion is not part of raw German-equities evidence authority.

A converted price series requires separate transformation authority, source FX evidence, timestamp alignment, precision rules, and provenance.

---

# 11. Market-Wide Validation Authority

## 11.1 Mandatory Validation

Every accepted block MUST be validated for:

- registered instrument identity;
- effective ticker, ISIN, and security-class range;
- venue and trading-system compatibility;
- provider mapping;
- timeframe authority;
- timestamp parseability;
- exchange-local calendar compatibility;
- regular or declared session compatibility;
- monotonic ordering after approved normalisation;
- duplicate timestamps;
- OHLC structural validity;
- finite numeric values;
- trading currency;
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

A bar MUST NOT be rejected merely because a generic weekday or public-holiday calendar disagrees with the approved venue calendar.

A bar outside the approved session or trading day requires classification as:

- extended-service evidence;
- auction evidence;
- another venue's evidence;
- provider timestamp-mapping issue;
- exceptional venue event;
- incompatible evidence;
- another approved category.

Implementation MUST NOT silently shift it into the canonical regular session.

## 11.4 Venue Conflict Validation

A material price, timestamp, or volume difference between Xetra, Frankfurt, another venue, and a provider aggregate is not automatically corruption.

The evidence MUST retain venue identity.

A validator MUST NOT choose one venue as canonical unless approved authority names that lane's venue and resolution rule.

## 11.5 Duplicate Rule

Duplicate identity is timeframe-specific and MUST be defined by the applicable timeframe authority.

Conflicting duplicates MUST be retained as evidence and MUST NOT be silently collapsed.

## 11.6 Gap Rule

Absence of bars may result from:

- official non-trading day;
- auction structure;
- volatility interruption;
- halt or suspension;
- no eligible trade;
- venue or service coverage limit;
- provider outage;
- ticker, ISIN, or identity transition;
- genuine missing evidence.

The timeframe authority MUST define expected bars and gap materiality.

Implementation MUST NOT fabricate replacements.

## 11.7 Conflict Rule

Provider, venue, trading-system, currency, adjustment, or session disagreement is retained.

Resolution MUST be deterministic, provenance-aware, and authorised.

`latest received`, `largest row count`, `Xetra`, `longest session`, or `adjusted` is not a universal winner rule.

## 11.8 Operational Failure Boundary

Missing authority stops only the affected acquisition, validation, construction, or migration path.

It MUST NOT unnecessarily disable unrelated instruments, lanes, or the wider operations console.

**Operations is King.**

---

# 12. Corporate Actions and Structural Events

## 12.1 Governed Events

German-equities authority MUST account for:

- stock splits and consolidations;
- cash and stock dividends;
- special distributions;
- subscription rights and capital increases;
- capital reductions;
- tender offers;
- mergers and acquisitions;
- demergers and spin-offs;
- domination, profit-transfer, squeeze-out, or similar structural events where identity is affected;
- ticker, ISIN, or WKN changes;
- registered or bearer share conversion;
- share-class changes;
- venue or segment transfers;
- issuer legal-form or domicile change;
- insolvency, restructuring, and liquidation;
- suspension and delisting;
- relisting;
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

## 12.3 Split and Consolidation Rule

A split or consolidation does not mutate accepted unadjusted evidence.

Any adjusted representation requires:

- event identity;
- effective trading date;
- adjustment factor;
- source authority;
- transformation method;
- provenance;
- separate adjusted-lane authority.

Silent historical rewriting is prohibited.

## 12.4 Dividend and Rights Rule

Cash dividends, distributions, and subscription-right events MUST NOT be inferred from price gaps.

Adjustment requires explicit event authority and methodology.

Temporary rights instruments remain distinct unless approved authority defines their relationship.

## 12.5 Merger, Spin-Off, and Squeeze-Out Rule

A merger, acquisition, spin-off, squeeze-out, or similar event creates continuity only when approved instrument authority states the relationship and effective range.

Predecessor and successor securities remain distinct by default.

## 12.6 Delisting and Relisting

Delisting ends the default active range for that registration.

A later relisting requires explicit identity and continuity authority.

The same ticker or ISIN-related issuer after a gap does not prove the same security.

---

# 13. Effective Historical Range

## 13.1 Start Rule

There is no universal earliest date for every German-equities instrument.

The effective start for a registered instrument is the latest of:

1. the security's approved listing or predecessor-authority date;
2. the start of the approved venue and trading-system identity;
3. the start of the approved ticker, ISIN, and security-class range;
4. the start of the approved currency range;
5. the start of approved provider semantics;
6. the earliest reliable compatible evidence;
7. any instrument-specific authority date.

## 13.2 End Rule

The effective end is the earliest of:

- delisting;
- merger or squeeze-out termination;
- security retirement;
- insolvency cancellation;
- ticker, ISIN, or identity replacement requiring a new registration;
- venue or trading-system authority termination;
- another approved structural event.

The default is `OPEN` only while no end condition applies.

## 13.3 Provider Coverage

Provider history limits restrict that provider's approved range.

They do not redefine the security's listing history.

Historical evidence outside an approved identity, venue, trading-system, session, adjustment, currency, or provider range may be retained but MUST NOT enter an active canonical lane until resolved.

---

# 14. Timeframe Inheritance

Every German-equities timeframe authority MUST inherit:

- German-equities market identity;
- instrument and security-membership rules;
- venue and trading-system authority;
- `Europe/Berlin` calendar timezone;
- official venue calendar authority;
- venue-specific regular-session ownership;
- local-date trading-day ownership;
- auction, extended-service, interruption, and exceptional-closure authority;
- provider roles;
- evidence immutability;
- venue, service, session, price-basis, currency, and adjustment provenance;
- corporate-action rules;
- market-wide validation;
- effective-range logic.

A timeframe authority MUST NOT contradict these facts.

---

# 15. Required German Equities Timeframe Authorities

| Timeframe | Required Authority | Status |
|---|---|---|
| `D1` | `GERMAN_EQUITIES_D1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `H1` | `GERMAN_EQUITIES_H1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M30` | `GERMAN_EQUITIES_M30_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M5` | `GERMAN_EQUITIES_M5_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |

Additional timeframe authorities require an approved amendment or later doctrine version.

Existing accepted D1 behaviour is not silently invalidated or re-authorised by this draft.

---

# 16. Explicit Delegation to Timeframe Authorities

The following are intentionally delegated:

- interval duration and alignment;
- canonical bar timestamp meaning;
- provider timestamp mapping;
- venue-specific regular-session bar alignment;
- auction and volatility-interruption treatment;
- extended-service lane treatment;
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

Before a German-equities implementation specification begins, it MUST prove that:

- this doctrine is approved;
- the relevant timeframe authority is approved;
- the instrument is registered as `EQUITIES_DE`;
- security type and class are explicit;
- venue, MIC, and trading system resolve;
- provider mapping and role are valid;
- venue, session, and aggregation scope are explicit;
- trading currency is explicit;
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
- venue or trading-system identity;
- exchange calendar;
- venue-specific regular-session ownership;
- auction or extended-service separation;
- provider role;
- price, currency, adjustment, or volume meaning;
- corporate-action continuity;
- effective-range authority.

---

# 19. Implementation Prohibitions

Implementation MUST NOT:

- infer security identity from ticker alone;
- infer venue or trading system from provider response alone;
- treat Xetra, Frankfurt, and other German venues as interchangeable;
- use a generic weekday or public-holiday calendar;
- use a fixed UTC offset for exchange-local sessions;
- create bars on official full-day closures;
- extend a regular-session bar into an unapproved service;
- mix regular, auction, or extended-service evidence silently;
- mix venue-specific and aggregate evidence silently;
- mix adjusted and unadjusted evidence silently;
- infer trading currency from issuer domicile or venue alone;
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
- venue, trading-system, or calendar authority;
- regular-session definition;
- auction or extended-service doctrine;
- trading-day, week, or month ownership;
- provider roles;
- price, currency, adjustment, or volume doctrine;
- corporate-action treatment;
- effective-range logic;
- required timeframe authorities;
- inheritance rules.

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| 1.0 | 2026-07-11 | Initial German-equities constitutional doctrine drafted | Establish market authority before timeframe implementation | PENDING |

Superseded versions remain immutable and auditable.

---

# 22. Approval Gate

This doctrine may be marked **APPROVED** only when:

- market scope is accepted;
- included instrument types are accepted;
- venue, trading-system, and calendar authority are accepted;
- regular-session, auction, and extended-service rules are accepted;
- trading-day, week, and month ownership are accepted;
- provider roles are accepted;
- evidence rules are accepted;
- price, currency, adjustment, and volume semantics are accepted;
- validation and corporate-action rules are accepted;
- effective-range logic is accepted;
- required timeframe authorities are accepted;
- exceptions and approval identity are recorded.

---

# 23. Acceptance Statement

Upon approval:

> `GERMAN_EQUITIES_BASE_DOCTRINE_V1` is the approved constitutional authority for the German Equities market ecosystem within Fragarach II. All subordinate German-equities timeframe authorities, specifications, implementations, acquisitions, validations, migrations, evidence-lane operations, and acceptance proofs MUST conform to it.

---

# 24. Governing Principle

> German equities are venue-specific exchange-calendar instruments governed operationally by explicit security identity, named venue and trading system, local-session ownership, declared currency and adjustment scope, immutable evidence, and auditable corporate-action continuity.

Provider convention may be mapped.

Implementation may encode.

Neither may invent authority.

**Operations is King.**
