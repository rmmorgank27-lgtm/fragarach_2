# AUSTRALIAN EQUITIES BASE DOCTRINE V1

**Document Class:** Constitutional Market Authority  
**Authority Layer:** Market Ecosystem  
**Authority Name:** `AUSTRALIAN_EQUITIES_BASE_DOCTRINE_V1`  
**Market Name:** Australian Equities  
**Market Code:** `EQUITIES_AU`  
**Version:** 1.0  
**Status:** APPROVED  
**Repository Location:** `constitution/doctrines/AUSTRALIAN_EQUITIES_BASE_DOCTRINE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Effective From:** 2026-07-11  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** Ray Morgan  
**Approval Date:** 2026-07-11

---

# 1. Purpose

This doctrine defines the constitutional operational truth for the Australian Equities market ecosystem within Fragarach II.

It establishes the market-wide authority inherited by every Australian-equities timeframe authority, evidence lane, acquisition specification, validator, native operation, migration, and acceptance proof.

It defines:

- the Australian-equities market boundary;
- security, share-class, and listing membership;
- primary venue and market-service identity;
- the exchange-local calendar and session structure;
- trading-day, week, and month ownership;
- auction, crossing, and non-regular-session treatment;
- approved provider roles;
- acceptable evidence and provenance;
- price, currency, adjustment, and volume semantics;
- corporate-action and structural-event authority;
- market-wide validation and conflict rules;
- effective historical range;
- the boundary between market authority and timeframe authority.

This doctrine does not define interval-specific bar alignment, provider interval codes, request chunking, bar completion, or latest-closed-bar calculations. Those matters belong to approved Australian-equities timeframe authorities.

---

# 2. Constitutional Position

```text
Constitution

↓

AUSTRALIAN_EQUITIES_BASE_DOCTRINE_V1

↓

Australian Equities Timeframe Authority

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides this doctrine;
2. this doctrine overrides subordinate Australian-equities timeframe authorities;
3. approved timeframe authorities override implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing authority.

Legacy code, provider defaults, ticker text, sample files, current application behaviour, or a generic `Australia` exchange label are not constitutional authority unless expressly adopted.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate document may weaken a mandatory requirement in this doctrine.

---

# 4. Market Definition

## 4.1 Market Identity

Australian Equities is a regulated, exchange-centred market ecosystem in which registered equity securities and approved equity-like listed instruments trade through recognised Australian venues and market services.

The default reference ecosystem is the Australian Securities Exchange cash market, but this doctrine does not treat every Australian venue, market service, provider aggregate, or off-market report as interchangeable.

A registered security may have:

- one approved primary listing or reference venue;
- one or more market-service or trading-board classifications;
- regular continuous trading;
- opening and closing auctions;
- crossings or other reported trades;
- venue-specific or aggregated provider evidence;
- suspensions, trading halts, and exceptional schedules;
- ticker, security, or issuer changes through time.

There is no constitutional assumption that every provider's ticker identifies the same security, share class, venue scope, adjustment basis, session scope, or historical identity.

## 4.2 Classification

**Asset Class:** `EQUITY`  
**Instrument Type Family:** `AU_LISTED_EQUITY`  
**Venue Model:** Centralised exchange ecosystem with explicit venue and market-service identity  
**Trading Model:** Exchange-calendar session based  
**Canonical Calendar Timezone:** `Australia/Sydney`  
**Primary Quote Convention:** One registered security unit priced in the registered trading currency

## 4.3 Included Scope

This doctrine includes, when explicitly registered:

- Australian exchange-listed ordinary shares;
- approved preference or special share classes;
- approved listed real estate investment securities;
- approved stapled securities;
- approved CHESS Depositary Interests or equivalent depositary interests;
- approved foreign-incorporated securities whose Australian listing is explicitly registered;
- venue-specific or approved consolidated Australian-equities price evidence;
- suspended or delisted securities within approved historical ranges.

Admission is never automatic. Each security, class, venue, market service, and effective range requires explicit authority.

## 4.4 Excluded Scope

This doctrine excludes unless separately authorised:

- exchange-traded funds and exchange-traded products;
- managed funds and listed investment vehicles not explicitly classified as equity securities;
- bonds and other debt securities;
- warrants, rights, options, and futures;
- contracts for difference;
- private company shares;
- indices and baskets;
- synthetic or calculated prices;
- unlisted securities;
- foreign securities merely quoted by a provider without approved Australian listing authority;
- off-market transactions lacking an approved market-service scope.

An excluded class requires another market authority or an approved amendment.

---

# 5. Instrument Membership Authority

## 5.1 Membership Rule

An instrument belongs to `EQUITIES_AU` only when:

1. the security is explicitly registered;
2. the controlled instrument type is approved under this doctrine;
3. the approved primary listing or reference venue is explicit;
4. the venue identifier and market service are explicit where material;
5. the canonical ASX or venue code is registered for an effective range;
6. the legal security identity and share class are distinguishable;
7. ISIN is recorded where available;
8. provider symbol mappings are registered;
9. trading currency is explicit;
10. calendar and session authority resolve;
11. adjustment basis is declared;
12. listing and delisting ranges are known where applicable;
13. it is not assigned to another market doctrine.

Ticker spelling alone does not establish membership or identity.

## 5.2 Canonical Symbol

The default canonical symbol is the approved primary-listing security code for the effective range.

Examples may include:

```text
BHP
CBA
CSL
MQG
RIO
WES
WOW
```

Examples do not create automatic registration.

The canonical symbol does not by itself identify:

- ISIN;
- legal security or issuer;
- share class;
- stapled-security composition;
- depositary-interest status;
- venue or market service;
- trading currency;
- adjustment basis;
- historical continuity.

## 5.3 Required Metadata

Every Australian-equities registration MUST include:

- canonical symbol;
- controlled display name;
- market code `EQUITIES_AU`;
- asset class `EQUITY`;
- controlled instrument type;
- approved primary listing or reference exchange name;
- venue identifier or MIC where available;
- market-service identity where material;
- ISIN where available;
- trading currency;
- security unit definition;
- price precision;
- quantity precision where applicable;
- timezone `Australia/Sydney` unless an approved exception exists;
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

- share class;
- stapled-security component identity;
- CHESS Depositary Interest or other depositary-interest status;
- depositary ratio where applicable;
- issuer external identifier;
- predecessor or successor security identity;
- corporate-action lineage;
- historical ticker ranges;
- dual-listing or cross-listing relationship;
- suspension, administration, or restructuring status.

## 5.4 Venue and Market-Service Identity

The approved venue and market-service scope are constitutional properties of a lane.

Implementation MUST distinguish, where material:

- primary ASX cash-market evidence;
- another approved Australian venue;
- continuous-trading evidence;
- auction evidence;
- crossing or reported-trade evidence;
- approved consolidated evidence;
- provider-defined aggregates.

A generic provider label such as `Australia`, `ASX`, or `Sydney` is insufficient unless its exact scope is registered.

## 5.5 Security Identity

A ticker is not a permanent unique identity.

Security identity MUST account for:

- ticker changes;
- share-class changes;
- stapling or unstapling;
- schemes of arrangement;
- mergers and acquisitions;
- demergers and spin-offs;
- capital reconstructions;
- relisting;
- exchange transfer;
- depositary-interest changes;
- symbol reuse by another issuer.

Implementation MUST NOT join histories solely because ticker text matches.

## 5.6 Depositary and Stapled Securities

A CHESS Depositary Interest, other depositary interest, or stapled security is not constitutionally identical to an ordinary share.

Registration MUST declare:

- the controlled instrument type;
- the underlying or component relationship;
- any ratio or unit definition;
- continuity and adjustment rules;
- whether the provider evidence represents the listed unit or an underlying foreign security.

## 5.7 Prohibited Assumptions

Implementation MUST NOT infer:

- venue from ticker shape;
- security class from price level;
- Australian domicile from an ASX code;
- ordinary-share status from provider category;
- trading currency from market code alone;
- adjustment basis from a provider's default chart;
- session coverage from timestamp appearance;
- continuity across ticker changes;
- membership from inclusion in an index.

Missing material identity requires a compatibility report.

---

# 6. Canonical Australian Equities Calendar Authority

## 6.1 Calendar Identity

The governing calendar is the official calendar of the approved primary venue and market service.

For the default ASX cash-market scope:

```text
Calendar timezone: Australia/Sydney
Calendar class: Official exchange cash-market calendar
Calendar owner: Approved ASX cash-market authority
```

## 6.2 Governing Calendar Rule

A date is an expected trading date only when the official venue calendar declares the relevant market service open for that date.

Civil weekdays are not sufficient calendar authority.

Implementation MUST consume a versioned calendar authority that records:

- open days;
- full-day closures;
- early closes;
- special sessions;
- exceptional closures;
- effective dates of calendar corrections.

## 6.3 Default ASX Cash-Market Session Framework

The default ASX cash-market framework includes:

- pre-open activity before the opening auction;
- an opening single-price auction with venue-controlled timing;
- normal continuous trading beginning around 10:00 Sydney time under the official schedule;
- normal continuous trading ending at 16:00 Sydney time;
- a pre-closing phase;
- a closing single-price auction around 16:10 Sydney time under the official schedule;
- post-close and administrative states.

The official venue schedule, including randomised transition windows and effective-date changes, is authoritative.

This doctrine does not decide which of those components a particular timeframe bar includes. That decision belongs to the approved timeframe authority and lane profile.

## 6.4 Other Venue Sessions

Any non-default venue or market service MUST have an explicit calendar and session profile.

Implementation MUST NOT apply the ASX default calendar to another venue merely because the security is Australian or traded in Australian dollars.

## 6.5 Trading-Day Ownership

The exchange-local civil date in `Australia/Sydney` owns the approved session activity assigned to that venue trading day.

A post-midnight provider publication timestamp does not move the bar to another trading day unless the approved timeframe authority expressly says so.

## 6.6 Week Ownership

An Australian-equities trading week consists of the official venue trading days assigned to one exchange-local Monday-to-Friday week, subject to closures and exceptional sessions.

A week with fewer trading days due to official closures remains a valid trading week.

## 6.7 Month Ownership

A trading month consists of official venue trading days whose exchange-local trading-day dates fall within the same Gregorian calendar month.

## 6.8 Holidays, Early Closes, and Exceptional Closures

The official venue trading calendar and approved notices govern:

- public-holiday closures;
- early-closing days;
- emergency closures;
- delayed openings;
- market-service outages;
- special settlement or auction arrangements where relevant to evidence.

A public holiday that does not close the approved venue is not automatically a missing-day exception.

An official closure MUST NOT be classified as a missing trading day.

## 6.9 Daylight Saving

Session times are owned in `Australia/Sydney` local time.

UTC offsets change according to the applicable timezone rules.

Implementation MUST NOT fix Australian-equities sessions to a permanent UTC offset.

Historical timezone-rule changes MUST be preserved by the approved timezone database and authority version.

---

# 7. Session Authority

## 7.1 Canonical Session Model

The canonical session model is venue-defined and component-aware.

A lane MUST identify whether it represents:

- normal continuous trading only;
- opening auction plus normal trading;
- normal trading plus closing auction;
- all approved on-market activity;
- an approved consolidated scope;
- another explicitly defined session profile.

The phrase `regular session` is insufficient unless its components are enumerated.

## 7.2 Regular-Session Default

For a default ASX cash-equity lane, normal continuous trading is the baseline regular component.

Opening and closing auctions are separate constitutional components and MUST NOT be silently included or excluded.

A timeframe authority MUST define the approved inclusion rule for each bar class.

## 7.3 Opening Auction

Opening-auction evidence is materially distinct from pre-open order entry and normal continuous trading.

Where included, evidence MUST preserve:

- auction classification;
- official venue timing semantics;
- security-specific or market-wide opening behaviour where material;
- provider scope and timestamp meaning.

Implementation MUST NOT fabricate an exact opening instant where the official process uses randomised or controlled transitions.

## 7.4 Closing Auction

Closing-auction evidence is materially distinct from the final normal-trading trade.

A provider's `close` may represent:

- last continuous-trading price;
- official closing-auction price;
- last eligible trade;
- a provider-derived or adjusted close.

The lane and timeframe authority MUST declare which meaning applies.

## 7.5 Crossings, Off-Market Reports, and Other Trade Classes

Crossings, special crossings, off-market transfers, late reports, and other trade classes MUST NOT be blended into a canonical lane unless the approved market-service scope explicitly includes them.

Their treatment MUST be declared by the provider and lane authority.

## 7.6 Trading Halts and Suspensions

A trading halt, suspension, or venue interruption is not automatically a data gap.

Validation MUST distinguish:

- no trading because the security was halted or suspended;
- no trading because the venue was closed;
- no provider publication;
- missing evidence despite expected activity.

## 7.7 Precedence

Session authority precedence is:

```text
Approved instrument-specific exception

↓

Approved venue and market-service session authority

↓

Approved Australian-equities default session profile

↓

No authority
```

Provider defaults and implementation convenience do not override approved session authority.

---

# 8. Provider Authority

## 8.1 Approved Roles

A provider may be approved for one or more roles:

- official venue or market operator;
- official issuer or regulatory notice source;
- licensed consolidated market-data vendor;
- venue-specific market-data vendor;
- historical-data vendor;
- corporate-action vendor;
- manual evidence source;
- discovery-only source.

Approval for one role does not imply approval for every role.

## 8.2 Provider Scope

Every provider mapping MUST declare:

- provider name;
- provider symbol;
- security identity;
- venue or aggregate scope;
- market-service scope;
- session coverage;
- price basis;
- adjustment basis;
- volume basis;
- timestamp timezone;
- timestamp meaning;
- correction or revision behaviour;
- effective historical range.

## 8.3 Provider Semantics Boundary

This doctrine does not approve a provider merely because it can return an Australian-equity ticker.

Before acquisition implementation, subordinate authority MUST establish:

- request symbol semantics;
- exchange and venue parameters;
- interval mapping;
- output timestamp semantics;
- pagination and chunking constraints;
- session inclusion;
- adjusted or unadjusted behaviour;
- volume definition;
- corporate-action treatment;
- correction and restatement behaviour;
- rate-limit and effective-range facts.

## 8.4 Provider Precedence

Default evidence precedence is:

1. official venue evidence or approved official files;
2. approved licensed venue-specific or consolidated vendor evidence;
3. approved historical vendor evidence;
4. approved manual evidence with complete provenance;
5. discovery-only evidence, which cannot become canonical without review.

Higher precedence does not permit silent overwriting. Conflicts remain auditable evidence events.

---

# 9. Evidence Authority

## 9.1 Immutability

Accepted raw evidence is immutable.

Corrections, replacements, reclassifications, and provider restatements MUST create new evidence and provenance events.

## 9.2 Acceptable Sources

Acceptable evidence may include:

- official exchange files or feeds;
- approved licensed vendor responses;
- approved historical data files;
- approved corporate-action notices;
- approved issuer announcements;
- approved manually supplied files;
- approved migration evidence with verified lineage.

## 9.3 Evidence Identity

Every evidence object MUST identify, where applicable:

- canonical instrument registration;
- provider and provider symbol;
- venue and market-service scope;
- requested range;
- received range;
- interval or event type;
- session profile;
- price basis;
- adjustment basis;
- volume basis;
- source timezone;
- timestamp semantics;
- acquisition or receipt timestamp;
- checksum and byte size;
- parser or normaliser version;
- row count;
- acceptance or rejection result;
- correction or supersession relationship.

## 9.4 Prohibitions

Implementation MUST NOT:

- overwrite accepted raw evidence;
- relabel one venue as another;
- infer auction inclusion from price shape;
- treat adjusted and unadjusted rows as duplicates;
- invent volume for a missing field;
- merge distinct securities because tickers match;
- remove a conflicting source merely to make validation pass;
- promote discovery-only data without approved provenance.

---

# 10. Price, Currency, Adjustment, and Volume Semantics

## 10.1 Price

Price represents the registered security unit in the registered trading currency and declared market scope.

A lane MUST declare whether OHLC values derive from:

- eligible on-market trades;
- a venue-specific trade set;
- an approved consolidated trade set;
- auction-inclusive activity;
- another explicitly approved basis.

Indicative quotes, midpoint values, broker valuations, and synthetic prices are not trade-price evidence unless separately authorised.

## 10.2 Security Unit

The registered security unit MUST be explicit.

For stapled securities, depositary interests, partly paid securities, or special classes, the unit definition MUST preserve the listed instrument's actual legal and economic form.

## 10.3 Trading Currency

Trading currency is a registered property of the security and lane.

`AUD` is common but MUST NOT be inferred solely from Australian listing status.

A currency change or separate foreign-currency market requires explicit effective-range authority.

## 10.4 Unadjusted Price Authority

Unadjusted OHLC preserves observed market prices as published for the declared session and venue scope.

It MUST remain distinguishable from any adjusted series.

## 10.5 Adjusted Price Authority

An adjusted series MUST declare:

- adjustment provider;
- adjustment method;
- covered corporate actions;
- whether dividends are included;
- adjustment direction;
- version or calculation date;
- effective historical range.

Adjusted and unadjusted series are separate evidence-lane identities.

Implementation MUST NOT derive an adjusted series without approved methodology authority.

## 10.6 Volume

Volume MUST declare its unit and scope.

Possible meanings include:

- number of listed security units traded;
- venue-specific volume;
- approved consolidated volume;
- auction-inclusive volume;
- a provider-defined subset.

Volume from distinct market scopes MUST NOT be compared or merged as if equivalent.

Null, absent, and zero volume are distinct states.

## 10.7 Currency Conversion

Converted-price series are derived evidence.

They MUST declare:

- source price lane;
- FX conversion lane;
- conversion timestamp rule;
- conversion direction;
- derived-series version.

Converted prices MUST NOT replace the native trading-currency lane.

---

# 11. Market-Wide Validation Authority

## 11.1 Mandatory Validation

Australian-equities evidence MUST be validated for:

- registered security identity;
- approved venue and market-service scope;
- approved calendar date;
- session compatibility;
- timestamp parseability and timezone meaning;
- monotonic ordering within a lane;
- duplicate identity;
- OHLC coherence;
- finite numeric values;
- non-negative price where the provider contract requires it;
- currency compatibility;
- adjustment-basis compatibility;
- volume unit and scope;
- effective listing range;
- corporate-action discontinuities;
- provenance completeness.

## 11.2 OHLC Rules

For a conventional OHLC bar:

```text
high >= open
high >= close
low <= open
low <= close
high >= low
```

These rules do not establish that the bar belongs to the correct security, venue, session, or adjustment basis.

## 11.3 Calendar Rules

Validation MUST use the approved venue calendar.

It MUST NOT classify as missing:

- official full-day closures;
- approved early-close absence outside the shortened session;
- periods of official suspension or halt where no eligible trade was expected;
- dates before listing or after delisting.

## 11.4 Venue and Session Conflict Validation

Rows with the same symbol and timestamp but different venue, market-service, session, or aggregate scope are not duplicates by default.

A conflict report MUST preserve each evidence identity.

## 11.5 Duplicate Rule

A duplicate requires matching lane identity and matching canonical bar key under the approved timeframe authority.

Conflicting values require an auditable conflict event, not silent replacement.

## 11.6 Gap Rule

A gap exists only when an approved calendar and session model expected evidence and the lane's approved completeness rule is not met.

No-trade bars, suspended securities, sparse historical periods, and provider non-publication require explicit classification.

Gap severity MUST be operational and materiality-aware.

## 11.7 Conflict Rule

Where approved sources disagree, Fragarach MUST:

1. preserve all evidence;
2. identify the exact lane and semantic difference;
3. apply approved precedence only where authority exists;
4. record the resolution;
5. expose unresolved uncertainty without disabling usable operations.

## 11.8 Operational Failure Boundary

Incomplete or conflicting evidence MAY prevent promotion of the affected lane or range.

It MUST NOT block unrelated instruments, timeframes, markets, evidence intake, or read-only operations.

**Operations is King.**

---

# 12. Corporate Actions and Structural Events

## 12.1 Governed Events

Material events include:

- stock splits and consolidations;
- dividends and distributions;
- capital returns;
- rights and entitlement offers;
- bonus issues;
- placements and capital raisings;
- schemes of arrangement;
- takeovers and compulsory acquisitions;
- mergers and acquisitions;
- demergers and spin-offs;
- stapling or unstapling;
- ticker changes;
- class conversions;
- depositary-interest changes;
- suspensions and trading halts;
- administration, insolvency, or restructuring;
- delisting, cancellation, and relisting.

## 12.2 Continuity Rule

Continuity is an approved relationship, not a ticker heuristic.

A structural event MUST declare whether history:

- continues under the same registration;
- continues with an effective-range identity change;
- links to a successor registration;
- terminates;
- requires a derived adjusted series;
- remains separate despite economic relationship.

## 12.3 Split and Consolidation Rule

Observed raw prices and volumes remain immutable.

Any split- or consolidation-adjusted series is derived and versioned.

The adjustment factor, effective date, and affected fields MUST be auditable.

## 12.4 Distribution and Entitlement Rule

Cash dividends, distributions, rights, entitlements, and capital returns MUST NOT silently alter raw OHLC.

Their inclusion in an adjusted series requires explicit methodology authority.

## 12.5 Scheme, Takeover, Merger, and Demerger Rule

A scheme, takeover, merger, or demerger does not automatically create one continuous price history.

The approved registration and event authority must define predecessor, successor, exchange ratio, cash component, and continuity treatment.

## 12.6 Delisting and Relisting

Delisting ends the approved active range unless a later explicit relisting authority exists.

A reused ticker or reactivated listing MUST NOT inherit prior history without approved identity continuity.

---

# 13. Effective Historical Range

## 13.1 Start Rule

The authoritative start for a security lane is the latest of:

- the security's approved listing or registration start;
- the provider mapping's effective start;
- the venue or market-service scope's effective start;
- the adjustment-basis effective start;
- the first accepted evidence supported by provenance.

A provider's earliest returned row is not automatically the constitutional start.

## 13.2 End Rule

The authoritative end is determined by:

- delisting or cancellation;
- provider mapping retirement;
- security identity change;
- lane retirement;
- latest accepted evidence for an active lane.

## 13.3 Provider Coverage

Different providers may cover different historical ranges and semantics.

Coverage gaps MUST remain visible.

Implementation MUST NOT fabricate an uninterrupted history by blending incompatible provider, venue, session, currency, or adjustment scopes.

---

# 14. Timeframe Inheritance

Every Australian-equities timeframe authority inherits:

- market code `EQUITIES_AU`;
- exchange-centred market identity;
- explicit security and venue registration;
- `Australia/Sydney` default calendar timezone;
- official venue calendar ownership;
- exchange-local trading-day ownership;
- explicit session-component semantics;
- auction separation;
- trading-currency authority;
- adjusted and unadjusted lane separation;
- immutable evidence and provenance;
- corporate-action and structural-event rules;
- no silent cross-venue or cross-security merging;
- non-blocking operational failure boundaries.

A timeframe authority may refine these facts but MUST NOT contradict them.

---

# 15. Required Australian Equities Timeframe Authorities

The following authorities are required before their corresponding lanes may become operational authority:

```text
AUSTRALIAN_EQUITIES_D1_AUTHORITY_V1
AUSTRALIAN_EQUITIES_H1_AUTHORITY_V1
AUSTRALIAN_EQUITIES_M30_AUTHORITY_V1
AUSTRALIAN_EQUITIES_M5_AUTHORITY_V1
```

Additional timeframe authorities MAY be created through the approved template and approval process.

No timeframe is authorised merely because a provider offers an interval with the same name.

---

# 16. Explicit Delegation to Timeframe Authorities

Each Australian-equities timeframe authority MUST define:

- interval duration;
- bar-open and bar-close alignment;
- timestamp label meaning;
- session-component inclusion;
- treatment of opening and closing auctions;
- treatment of partial final intervals;
- early-close alignment;
- trading-day ownership in stored timestamps;
- bar completion rule;
- latest-closed-bar rule;
- provider request interval;
- provider response semantics;
- pagination and chunking;
- effective request range;
- overlap and retry rules;
- duplicate key;
- expected-bar model;
- no-trade and zero-volume treatment;
- gap classification and materiality;
- correction and restatement handling;
- lane validation requirements;
- compatibility requirements.

If any material item is unresolved, implementation MUST stop that lane with a compatibility report.

---

# 17. Compatibility Requirements

Before an implementation specification may consume this doctrine, it MUST identify:

- the approved market doctrine version;
- the approved timeframe authority version;
- the instrument registration;
- the evidence-lane registration;
- the venue and market-service scope;
- the session profile;
- the provider mapping and role;
- the price, currency, adjustment, and volume basis;
- the effective historical range;
- any approved exceptions.

Compatibility MUST be explicit and testable.

A green software test suite does not compensate for missing authority.

---

# 18. Specification Boundary

A specification MAY define:

- database schema and migrations;
- application services;
- acquisition workflow;
- parsing and normalisation;
- APIs and commands;
- user-interface behaviour;
- operational receipts;
- error reporting;
- acceptance tests.

A specification MUST NOT redefine:

- what belongs to `EQUITIES_AU`;
- security identity;
- venue identity;
- calendar ownership;
- session components;
- trading-day ownership;
- price or volume meaning;
- adjustment methodology;
- corporate-action continuity;
- effective historical range;
- provider semantics.

Those are authority facts.

---

# 19. Implementation Prohibitions

Implementation MUST NOT:

- invent missing exchange or venue identity;
- infer security class from ticker spelling;
- treat every ASX code as an ordinary share;
- assume every lane is in AUD;
- assume every provider includes the same auctions or trade classes;
- hard-code a permanent UTC offset;
- label official closures as gaps;
- merge adjusted and unadjusted bars;
- overwrite immutable evidence;
- join histories solely by ticker;
- use an index membership list as instrument authority;
- continue beyond a material authority gap without a compatibility report;
- block unrelated operations because one lane is unresolved.

---

# 20. Exceptions

An exception MUST:

- identify the exact rule varied;
- identify the affected instrument, venue, session, provider, timeframe, and range;
- state the operational reason;
- define the replacement rule;
- include approval and effective dates;
- preserve provenance;
- define expiry or review conditions.

An undocumented implementation branch is not an exception.

---

# 21. Amendment and Versioning

A material amendment requires a new doctrine version when it changes:

- market membership;
- controlled instrument types;
- venue or market-service identity;
- calendar or session ownership;
- trading-day ownership;
- price, currency, adjustment, or volume semantics;
- provider precedence;
- corporate-action continuity;
- validation rules;
- effective historical ranges;
- subordinate authority obligations.

Historical versions MUST remain available for audit.

A new version MUST state:

- what changed;
- why it changed;
- affected instruments and ranges;
- migration requirements;
- compatibility consequences;
- supersession date.

---

# 22. Approval Gate

This doctrine may be approved only when:

- all sections are complete;
- no drafting placeholders remain;
- the market code and controlled types are accepted;
- the default calendar and session framework are accepted;
- venue and market-service separation is accepted;
- security-unit and depositary/stapled treatment are accepted;
- price, currency, adjustment, and volume semantics are accepted;
- corporate-action and continuity rules are accepted;
- required timeframe authorities are acknowledged;
- compatibility and exception rules are accepted;
- approval identity and date are recorded.

Approval makes this doctrine constitutional authority for subordinate Australian-equities work.

---

# 23. Acceptance Statement

Approval confirms that this document defines the market-level operational truth for Australian Equities within Fragarach II.

Approval does not authorise a timeframe lane by itself.

Each lane still requires approved instrument registration, evidence-lane registration, timeframe authority, provider compatibility, implementation specification, and acceptance proof.

---

# 24. Governing Principle

```text
The market defines the trading truth.

The timeframe defines the interval truth.

The evidence lane defines the authorised evidence identity.

The specification implements that truth.

Implementation must never invent authority.

Operations is King.
```
