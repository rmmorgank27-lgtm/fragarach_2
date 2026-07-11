\
# ENERGY BASE DOCTRINE V1

**Document Class:** Constitutional Market Authority  
**Authority Layer:** Market Ecosystem  
**Authority Name:** `ENERGY_BASE_DOCTRINE_V1`  
**Market Name:** Energy Reference Prices  
**Market Code:** `ENERGY`  
**Version:** 1.0  
**Status:** DRAFT FOR APPROVAL  
**Repository Location:** `constitution/doctrines/ENERGY_BASE_DOCTRINE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Effective From:** Not effective until approved  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** PENDING  
**Approval Date:** PENDING

---

# 1. Purpose

This doctrine defines the constitutional operational truth for the Energy Reference Prices market ecosystem within Fragarach II.

It establishes the market-wide authority inherited by every Energy timeframe authority, Evidence Lane, acquisition specification, validator, native operation, migration, and acceptance proof.

It defines:

- the Energy market boundary;
- approved energy-reference instrument families;
- the distinction between physical commodities, benchmarks, futures, continuous futures, CFDs, and provider-derived references;
- canonical commodity, quote, unit, benchmark-family, and source-methodology identity;
- the Version 1 New York rollover calendar profile for provider-derived reference instruments;
- trading-day, week, and month ownership;
- provider and manual-evidence roles;
- price, volume, open-interest, settlement, and roll semantics;
- structural energy events and historical continuity;
- market-wide validation and conflict rules;
- effective-range requirements;
- the boundary between market authority and timeframe authority.

This doctrine does not define interval-specific bar alignment, provider interval codes, request chunking, bar completion, or latest-closed-bar calculations. Those matters belong to approved Energy timeframe authorities.

---

# 2. Constitutional Position

```text
Constitution

↓

ENERGY_BASE_DOCTRINE_V1

↓

ENERGY Timeframe Authority

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides this doctrine;
2. this doctrine overrides subordinate Energy timeframe authorities;
3. approved timeframe authorities override implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing authority.

Legacy code, provider defaults, broker labels, retail-platform names, sample files, or existing application behaviour are not constitutional authority unless expressly adopted.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate document may weaken a mandatory requirement in this doctrine.

---

# 4. Market Definition

## 4.1 Market Identity

Energy Reference Prices is a hybrid market ecosystem containing registered price references for energy commodities such as crude oil and natural gas.

Energy commodities do not possess one universal market structure.

Depending on the instrument, a quoted price may represent:

- a physical spot assessment;
- a cash benchmark;
- an exchange-traded futures contract;
- a specific futures settlement;
- a continuous futures series;
- a provider-derived reference;
- a dealer or broker CFD;
- an indicative provider aggregate;
- another expressly approved source type.

These forms are materially different evidence identities.

Fragarach II MUST NOT treat them as interchangeable merely because they refer to the same broad commodity.

There is no universal consolidated energy spot price, universal session, universal traded volume, universal contract-roll method, or universal intraday bar authority across all energy instruments.

## 4.2 Classification

**Asset Class:** `ENERGY_COMMODITIES`  
**Instrument Type Family:** `ENERGY_REFERENCE_PAIR`  
**Venue Model:** Hybrid: physical, benchmark, exchange, OTC, and provider-derived  
**Version 1 Trading Model:** Near-continuous provider-derived reference, five trading days per operational week  
**Version 1 Session Timezone:** `America/New_York`  
**Quote Convention:** Registered quote amount per registered energy pricing unit

## 4.3 Included Scope

Version 1 includes registered provider-derived energy reference instruments for which all required authority exists.

Expected examples include:

```text
USOIL
UKOIL
NATGAS
```

Possible registered benchmark families include:

- West Texas Intermediate crude oil;
- Brent crude oil;
- Henry Hub natural gas;
- another energy reference admitted by constitutional amendment.

Example names do not create membership. Instrument Registration Authority remains mandatory.

## 4.4 Excluded Scope

This doctrine does not automatically admit:

- dated or delivery-month futures contracts;
- futures options;
- swaps or forwards;
- physical cargoes or location-specific spot transactions;
- official price assessments or benchmark publications;
- futures settlement-only series;
- continuous futures series with undisclosed roll rules;
- CFDs with unknown underlying construction;
- exchange-traded funds, notes, or commodity securities;
- energy equities;
- electricity, power, emissions, carbon, freight, uranium, coal, or refined-product instruments unless separately registered;
- inventory, storage, production, reserve, flow, or fundamental-statistics series;
- synthetic commodity crosses created without transformation authority.

Excluded evidence requires another market authority, a separate instrument class, or an approved amendment.

## 4.5 Version 1 Operational Scope

Version 1 authorises canonical OHLC evidence only for instruments registered with:

```text
source_nature   = PROVIDER_DERIVED_REFERENCE
calendar_profile = ENERGY_REFERENCE_24X5_NEW_YORK_ROLLOVER_V1
```

A provider may market a symbol as “spot”. Fragarach SHALL still retain the more conservative constitutional identity `PROVIDER_DERIVED_REFERENCE` unless the source methodology proves a more specific classification.

---

# 5. Instrument Membership Authority

## 5.1 Membership Rule

An instrument belongs to `ENERGY` only when:

1. the underlying energy commodity or benchmark family is explicit;
2. the canonical symbol is registered;
3. the quote asset is explicit;
4. the pricing unit is explicit;
5. the source nature is explicit;
6. the provider or venue scope is explicit;
7. the price basis is explicit;
8. the benchmark, contract, or provider-reference relationship is explicit;
9. any roll or continuation methodology is explicit;
10. calendar and session authority resolve;
11. provider symbol mappings are registered;
12. effective historical ranges are known;
13. it is not assigned to another market doctrine.

Symbol spelling alone does not establish membership.

## 5.2 Canonical Symbols

Fragarach canonical symbols are controlled identifiers, not provider symbols.

Expected Version 1 examples include:

| Canonical Symbol | Intended Family | Default Unit Candidate | Registration Requirement |
|---|---|---|---|
| `USOIL` | WTI-related energy reference | USD per barrel | Exact provider mapping and source methodology required |
| `UKOIL` | Brent-related energy reference | USD per barrel | Exact provider mapping and source methodology required |
| `NATGAS` | Henry Hub-related natural-gas reference | USD per MMBtu | Exact provider mapping and source methodology required |

Provider examples such as `WTI/USD` or `XBR/USD` are provider mappings only. They MUST NOT silently replace canonical identity.

## 5.3 Source-Nature Classification

Every Energy instrument MUST use one controlled source-nature value:

| Source Nature | Meaning | Version 1 Canonical OHLC Eligibility |
|---|---|---|
| `PROVIDER_DERIVED_REFERENCE` | Provider-created reference or aggregate whose exact component market may be proprietary | YES, when registered and mapped |
| `PHYSICAL_SPOT_ASSESSMENT` | Assessment of physical transactions or indications | NO, separate authority required |
| `CASH_BENCHMARK` | Administrator-governed benchmark publication | NO, separate authority required |
| `EXCHANGE_FUTURES_CONTRACT` | One identified expiry contract | NO, separate futures authority required |
| `CONTINUOUS_FUTURES_SERIES` | Multi-contract series joined by a roll methodology | NO, separate construction authority required |
| `FUTURES_SETTLEMENT_SERIES` | Official or provider settlement values | NO, separate evidence type required |
| `CFD_INDICATIVE` | Dealer or broker contract-for-difference price | NO unless explicitly admitted by amendment |
| `OTHER` | Another controlled source nature | NO until separately approved |

## 5.4 Unit Authority

Pricing unit is part of instrument identity.

Common examples include:

| Commodity Family | Example Unit |
|---|---|
| Crude oil | barrel |
| Natural gas | million British thermal units (`MMBtu`) |
| Refined products | gallon, metric tonne, or another registered unit |

Implementation MUST NOT assume that every Energy price is quoted per barrel.

Unit conversion requires approved transformation authority, an exact conversion factor, effective range, and immutable provenance.

## 5.5 Required Metadata

Every Energy registration MUST include:

- canonical symbol;
- controlled display name;
- market code `ENERGY`;
- asset class `ENERGY_COMMODITIES`;
- controlled instrument type;
- underlying commodity family;
- benchmark family;
- source nature;
- quote asset or currency;
- pricing unit;
- price precision;
- quantity precision where applicable;
- calendar profile;
- session authority reference;
- provider symbol mappings;
- provider or venue scope;
- price basis;
- roll methodology, or `NOT_APPLICABLE`;
- contract identity, or `NOT_APPLICABLE`;
- settlement relationship, or `NOT_APPLICABLE`;
- effective historical range;
- operational status;
- registration and approval provenance.

Where material, registration MUST also include:

- delivery location or grade;
- contract multiplier;
- front-month selection rule;
- roll trigger and adjustment method;
- benchmark administrator;
- historical symbol changes;
- provider methodology-change boundaries;
- negative-price eligibility;
- recurring maintenance windows.

## 5.6 Instrument Identity and Continuity

Continuity MUST NOT be assumed across:

- commodity grade or quality changes;
- delivery-location changes;
- quote-currency changes;
- unit changes;
- provider symbol reuse;
- source-nature changes;
- futures expiry or contract roll;
- roll-methodology changes;
- adjustment-method changes;
- benchmark methodology changes;
- settlement-to-last-trade changes;
- material changes in provider aggregate scope;
- legal or market-structure changes.

Pre-change and post-change evidence require explicit continuity authority and effective ranges.

## 5.7 Prohibited Assumptions

Implementation MUST NOT invent:

- commodity or benchmark identity;
- source nature;
- quote asset;
- pricing unit;
- venue or provider scope;
- price basis;
- contract expiry;
- roll methodology;
- settlement meaning;
- session or calendar ownership;
- provider mapping;
- historical continuity;
- synthetic conversion authority.

Missing authority requires a compatibility report for the affected path.

---

# 6. Canonical Energy Calendar Authority

## 6.1 Version 1 Calendar Profile

**Calendar Authority:** `ENERGY_REFERENCE_24X5_NEW_YORK_ROLLOVER_V1`  
**Calendar Type:** Provider-derived near-continuous reference calendar  
**Timezone:** `America/New_York`

This calendar profile applies only to registered Version 1 provider-derived reference instruments.

It does not define futures-exchange trade dates, official settlement dates, physical-market assessment windows, or benchmark-administrator publication calendars.

## 6.2 Operational Week

The Version 1 operational week:

- opens Sunday at **17:00 America/New_York**;
- continues through five owned Energy trading days;
- closes Friday at **17:00 America/New_York**.

The IANA timezone rules for `America/New_York`, including daylight-saving transitions, are authoritative.

Implementation MUST NOT replace this rule with a fixed UTC offset.

## 6.3 Daily Boundary

The canonical Energy reference trading-day boundary is **17:00 America/New_York**.

An owned trading day begins at 17:00 on the preceding New York civil date and ends at 17:00 on its owned New York civil date.

```text
Monday Energy reference day
= Sunday 17:00 New York
  through
  Monday 17:00 New York
```

The exact boundary inclusion belongs to the relevant timeframe authority.

## 6.4 Trading-Day Ownership

A Version 1 Energy trading day is owned by the New York civil date on which its session closes.

Therefore:

- Sunday 17:00 through Monday 17:00 is owned by Monday;
- Thursday 17:00 through Friday 17:00 is owned by Friday;
- there is no normal Saturday or Sunday owned Energy day.

## 6.5 Week and Month Ownership

The Energy trading week contains Monday through Friday owned days and is owned by the Friday close date.

An Energy trading day belongs to the calendar month of its owned New York close date.

## 6.6 Weekend Closure

The period after Friday 17:00 and before Sunday 17:00 New York time is a canonical weekend closure for the Version 1 profile.

No canonical bar is expected wholly inside this closure.

## 6.7 Maintenance Windows

Energy providers and underlying derivative markets commonly have recurring maintenance or publication breaks.

A maintenance interval affects expected-bar calculation only when it is recorded in the registered instrument/provider calendar profile.

Implementation MUST NOT:

- infer a recurring break from one missing observation;
- declare the entire Energy market closed because one provider is silent;
- fabricate bars across maintenance intervals;
- import a futures-exchange halt into a provider-derived reference lane without explicit authority.

## 6.8 Holidays and Exceptional Closures

There is no single holiday calendar governing all energy reference sources.

Therefore:

- a public holiday is not automatically a global Energy closure;
- futures holiday hours do not automatically define provider-reference closure;
- reduced liquidity does not remove a canonical interval;
- provider silence is evidence of missing publication, not proof of market closure;
- Christmas, New Year, emergency events, and exceptional non-publication periods require explicit evidence or approved exception records.

Calendar corrections MUST be versioned and auditable.

---

# 7. Session Authority

## 7.1 Canonical Session

The Version 1 session model is:

```text
ENERGY_REFERENCE_DAILY_SESSION_V1
```

with:

```text
Open:  17:00 America/New_York on the preceding civil date
Close: 17:00 America/New_York on the owned civil date
Owner: close-date civil day in America/New_York
```

## 7.2 Futures and Benchmark Separation

Exchange-traded Energy futures may operate on exchange trade-date rules and daily maintenance schedules that resemble, but do not equal, this profile.

Official benchmark and settlement windows are point-in-time or methodology-governed events.

They MUST NOT redefine the Version 1 session unless separately adopted.

## 7.3 Regional Labels

Asia, Europe, London, New York, pit, electronic, settlement, and other labels MAY be used for analysis or display.

They are not constitutional Evidence Lane boundaries unless separately authorised.

## 7.4 Contract Roll Boundaries

A contract roll is a structural series event, not a daily session boundary.

A continuous or provider-derived series MUST retain roll-methodology identity and any known roll event.

## 7.5 Precedence

```text
Approved instrument-specific exception

↓

Approved ENERGY timeframe authority

↓

ENERGY_BASE_DOCTRINE_V1

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
| Twelve Data | Primary automated acquisition provider | Registered Energy provider-reference instruments and approved timeframes | Symbol mapping, unit, source nature, price basis, calendar profile, and timeframe semantics MUST exist |
| Operator-supplied file | Manual evidence source | Registered Energy instruments and approved timeframes | Origin, provider/venue scope, checksum, parser result, source nature, unit, and provenance MUST be retained |
| Existing accepted immutable evidence | Historical evidence source | Evidence already accepted by Fragarach II | Original provenance remains immutable |

No futures exchange, benchmark administrator, price-reporting agency, broker CFD feed, or additional data vendor is approved as a canonical Energy bar provider by this version.

Additional providers require amendment or separate provider authority.

## 8.2 Twelve Data Source Scope

For a registered Twelve Data Energy mapping, Version 1 uses conservative provenance unless a more specific methodology is approved:

```text
source_nature = PROVIDER_DERIVED_REFERENCE
source_scope  = TWELVE_DATA_PROVIDER_AGGREGATE
price_basis   = PROVIDER_AGGREGATE
```

These labels do not assert that the data is:

- an official physical spot assessment;
- one named futures contract;
- an official settlement;
- a transparent continuous-futures construction;
- a universal consolidated Energy price.

## 8.3 Provider Semantics Boundary

Each Energy timeframe authority MUST define:

- provider interval code;
- timestamp meaning;
- timezone mapping;
- request start and end semantics;
- row and span limits;
- chunking and overlap;
- ordering;
- duplicate behaviour;
- partial-bar behaviour;
- empty-response meaning;
- revision behaviour;
- maintenance treatment;
- historical coverage;
- unit and precision handling.

Implementation MUST NOT proceed for a provider/timeframe combination until those facts are approved.

## 8.4 Provider Precedence

There is no market-wide rule that the newest response, largest row count, official-sounding symbol, or smallest spread automatically wins.

Compatible conflicting evidence MUST be retained and resolved only by an approved lane-resolution rule.

Silent overwrite is prohibited.

---

# 9. Evidence Authority

## 9.1 Immutability

Accepted Energy evidence is immutable.

A correction requires new evidence, new provenance, a new validation result, and an auditable resolution decision.

## 9.2 Acceptable Sources

Acceptable Version 1 sources are:

- approved Twelve Data API responses;
- approved Twelve Data exports;
- operator-supplied files with declared origin and source nature;
- existing immutable Fragarach II evidence.

Official settlements, benchmark publications, futures histories, and physical assessments may be retained as distinct evidence only after the corresponding authority exists.

## 9.3 Evidence Identity

Every Energy evidence block MUST identify:

- canonical instrument;
- source symbol;
- provider or source identity;
- source role;
- source nature;
- benchmark family;
- price basis;
- provider or venue scope;
- quote asset;
- pricing unit;
- contract identity or `NOT_APPLICABLE`;
- roll methodology or `NOT_APPLICABLE`;
- timeframe;
- requested and received ranges;
- observed timestamp range;
- row count;
- checksum;
- acquisition timestamp;
- parser or adapter version;
- timestamp interpretation;
- volume meaning where present;
- evidence and validation status.

## 9.4 Prohibitions

Implementation MUST NOT:

- fabricate missing bars;
- mutate accepted evidence;
- discard conflicts without record;
- shift timestamps without approved mapping;
- merge source natures by assumption;
- substitute futures settlement for provider-reference OHLC;
- hide contract-roll discontinuities;
- rescale units without authority;
- create synthetic crosses without authority;
- treat provider volume as universal Energy volume.

---

# 10. Price, Volume, Open Interest, and Settlement Semantics

## 10.1 Price

Energy OHLC evidence represents the declared price basis within the declared source scope.

Approved Version 1 price-basis values include:

- `BID`;
- `ASK`;
- `MIDPOINT`;
- `LAST`;
- `PROVIDER_AGGREGATE`;
- another separately approved basis.

Different source natures, price bases, units, or roll methodologies MUST NOT be merged without construction authority.

## 10.2 Quote Direction

A canonical Energy price means:

```text
registered quote amount per one registered pricing unit
```

Examples:

```text
USD per barrel
USD per MMBtu
```

Inversion or unit conversion requires approved transformation authority.

## 10.3 Negative and Zero Prices

Energy prices may be zero or negative in exceptional market conditions, particularly in derivative-linked or provider-derived series.

Therefore:

- a negative price MUST NOT be rejected solely because it is negative;
- zero MUST NOT be treated automatically as missing;
- instrument registration MUST declare whether negative values are structurally permitted;
- validators MUST still enforce finite values and coherent OHLC ordering.

## 10.4 Volume

There is no universal consolidated volume for provider-derived Energy references.

Provider volume may mean:

- traded contract volume;
- tick count;
- quote updates;
- provider-estimated activity;
- venue-specific volume;
- unavailable.

Meaning and unit MUST be explicit.

## 10.5 Open Interest

Open interest is a derivative-contract field, not a generic spot or provider-reference volume field.

It MUST remain separate from OHLCV evidence unless an approved derivative authority defines it.

## 10.6 Settlement

Official settlement is a distinct evidence type.

Settlement MUST NOT be treated as the close of a provider-derived OHLC bar unless the provider mapping expressly defines the close that way and the authority approves it.

## 10.7 Missing Volume

Zero, null, and absent volume are distinct states.

Missing volume MUST NOT invalidate valid OHLC evidence unless a subordinate authority makes volume mandatory.

---

# 11. Market-Wide Validation Authority

## 11.1 Identity Validation

Evidence MUST match the registered:

- canonical instrument;
- source symbol mapping;
- market code;
- source nature;
- benchmark family;
- quote asset;
- pricing unit;
- provider scope;
- price basis;
- roll methodology;
- calendar profile;
- timeframe authority.

## 11.2 OHLC Validation

For every bar:

```text
high >= low
high >= open
high >= close
low  <= open
low  <= close
```

All required price values MUST be finite numeric values.

Negative values MAY be valid when the registration permits them.

## 11.3 Unit Validation

Evidence in barrels, MMBtu, gallons, tonnes, contracts, lots, or another unit MUST NOT be mixed.

A unit mismatch is a material identity conflict.

## 11.4 Timestamp and Calendar Validation

Every bar MUST map to one canonical interval under the approved timeframe authority and calendar profile.

Weekend, maintenance, holiday, and exceptional-closure classification MUST use approved calendar evidence.

## 11.5 Structural-Series Validation

A provider-derived or continuous series MUST preserve any known:

- roll event;
- contract basis change;
- adjustment event;
- methodology change;
- benchmark-family change;
- source-scope change.

An unexplained price jump is not automatically a bad bar. It may be a structural-series event requiring review.

## 11.6 Conflict Validation

Comparable evidence requires matching:

- instrument;
- interval;
- timestamp;
- source nature;
- source scope;
- price basis;
- pricing unit;
- roll methodology;
- adjustment state.

Rows that are not comparable MUST coexist as separate evidence identities.

## 11.7 Severity

Validation severity follows:

- `GREEN`: accepted and complete;
- `AMBER`: usable with visible uncertainty, staleness, or non-material deficiency;
- `RED`: structurally invalid evidence;
- `BLOCKED`: authority missing for the affected operation.

`AMBER` MUST remain usable.

`BLOCKED` applies only to the affected operation and MUST NOT hide unrelated accepted evidence.

---

# 12. Structural Energy Events

## 12.1 Contract Roll

A roll from one futures expiry to another can create a discontinuity unrelated to contemporaneous market movement.

Any series affected by rolling MUST declare:

- selected contracts;
- roll trigger;
- roll date;
- adjustment method;
- whether history is adjusted or unadjusted;
- effective range.

Version 1 does not authorise Fragarach to construct a continuous futures series.

## 12.2 Benchmark and Methodology Change

Changes to benchmark definitions, assessment windows, delivery locations, grade specifications, or administrator methodology are structural events.

They require versioned authority and continuity review.

## 12.3 Unit and Currency Change

A unit or quote-currency change creates a new evidence regime unless an approved transformation preserves continuity.

## 12.4 Expiry, Delivery, and Settlement

Expiry, first-notice, last-trade, delivery, and settlement events belong to identified derivative contracts.

They MUST NOT be inferred for a provider-derived reference.

## 12.5 Extreme Market Conditions

Negative prices, price limits, exchange halts, storage constraints, sanctions, supply disruptions, and market dislocations MAY produce unusual but valid evidence.

Validation MUST distinguish unusual values from structurally impossible rows.

## 12.6 Provider Methodology Change

A provider may change symbol mapping, component sources, calculation method, publication schedule, or precision.

Such a change MUST be recorded as an effective-dated methodology boundary when known.

---

# 13. Effective Historical Range

## 13.1 Per-Lane Requirement

Every Energy Evidence Lane MUST materialise:

- requested start;
- provider earliest timestamp where available;
- first returned timestamp;
- first accepted timestamp;
- latest accepted timestamp;
- known methodology boundaries;
- coverage status;
- confirmation timestamp;
- evidence supporting the range.

## 13.2 No Universal Start Date

No universal Energy start date exists.

Coverage varies by:

- instrument;
- provider symbol;
- timeframe;
- source nature;
- benchmark family;
- provider methodology;
- roll methodology;
- unit and quote regime.

## 13.3 Earliest Timestamp

Provider earliest-timestamp endpoints MAY guide planning.

They do not replace proof from the acquired response and accepted Evidence Lane.

## 13.4 Historical Regime Boundaries

Data before and after a source-nature, unit, roll, benchmark, or provider-methodology change MUST NOT be assumed homogeneous.

---

# 14. Timeframe Inheritance

Every Energy timeframe authority inherits:

- market code `ENERGY`;
- Energy instrument membership;
- source-nature separation;
- pricing-unit identity;
- Version 1 New York close-date ownership for the approved profile;
- evidence immutability;
- conservative provider-source labels;
- conflict retention;
- structural-roll and methodology rules;
- non-blocking operational doctrine.

A timeframe authority MAY refine these rules for its interval.

It MUST NOT weaken or contradict them.

---

# 15. Required Energy Timeframe Authorities

Version 1 requires:

```text
ENERGY_D1_AUTHORITY_V1
ENERGY_H1_AUTHORITY_V1
ENERGY_M30_AUTHORITY_V1
ENERGY_M5_AUTHORITY_V1
```

No corresponding acquisition or canonical-lane implementation may proceed until its authority is approved.

---

# 16. Explicit Delegation to Timeframe Authorities

Each Energy timeframe authority MUST define:

- canonical interval meaning;
- exact alignment;
- timestamp meaning;
- session-date ownership;
- partial-bar handling;
- latest-closed-bar logic;
- provider request contract;
- provider response mapping;
- chunk ceiling and overlap;
- construction sources;
- expected-bar calculation;
- maintenance-window treatment;
- gaps and duplicate handling;
- effective-range proof;
- validator identity;
- freshness and Current-As-Of Truth.

---

# 17. Compatibility Requirements

Before implementation, all of the following MUST resolve:

- approved Energy base doctrine;
- approved timeframe authority;
- registered instrument;
- provider mapping;
- source nature;
- benchmark family;
- pricing unit;
- price basis;
- calendar profile;
- session authority;
- effective range;
- validator contract.

If any material item is missing, implementation shall produce a compatibility report and stop only the affected operation.

---

# 18. Specification Boundary

Specifications MAY define:

- software modules;
- schemas;
- commands;
- APIs;
- native UI;
- scheduling;
- retry mechanics;
- storage paths;
- migration sequencing;
- acceptance tests.

Specifications MUST consume, not redefine:

- Energy instrument identity;
- source nature;
- pricing unit;
- session ownership;
- provider semantics;
- roll rules;
- effective range;
- validation truth.

---

# 19. Implementation Prohibitions

Implementation MUST NOT:

- infer Energy identity from a symbol name;
- call a provider-derived reference official spot;
- treat futures, settlements, benchmarks, CFDs, and provider aggregates as interchangeable;
- invent a continuous-futures roll method;
- combine contracts across expiries without authority;
- silently adjust historical prices;
- convert units without authority;
- reject negative prices solely for being negative;
- fabricate bars across provider breaks;
- overwrite conflicting immutable evidence;
- use a fixed UTC offset for New York;
- hide usable history because the frontier is stale;
- allow legacy behaviour to overrule constitutional authority.

---

# 20. Exceptions

An exception MUST identify:

- affected instrument;
- affected provider and timeframe;
- exact rule being varied;
- operational reason;
- effective range;
- approval authority;
- expiry or review date;
- required evidence and acceptance proof.

Exceptions MUST be narrow and versioned.

An exception MUST NOT silently change unrelated Energy lanes.

---

# 21. Amendment and Versioning

A new version is required for a material change to:

- market boundary;
- source-nature classifications;
- calendar or session ownership;
- provider role;
- unit rules;
- price or settlement semantics;
- roll authority;
- structural-event treatment;
- validation rules;
- required timeframe authorities.

Historical versions MUST remain available.

---

# 22. Approval Gate

This doctrine may be approved only when:

- all 24 sections are present;
- no unresolved placeholders remain;
- market scope is explicit;
- source-nature separation is explicit;
- units and quote conventions are explicit;
- calendar and session ownership are explicit;
- provider roles are explicit;
- roll and settlement boundaries are explicit;
- prohibited assumptions are explicit;
- required timeframe authorities are named;
- compatibility behaviour is explicit.

Before approval, status remains `DRAFT FOR APPROVAL`.

---

# 23. Acceptance Statement

Approval means Fragarach II accepts this doctrine as the constitutional market authority for Version 1 Energy Reference Price operations.

Approval does not itself implement acquisition, storage, validation, serving, or native UI behaviour.

Those require subordinate specifications and acceptance proof.

---

# 24. Governing Principle

> Energy identity is more than a commodity name. Source nature, benchmark family, unit, contract basis, roll methodology, price basis, and session ownership are part of the evidence.

> Implementation must never invent authority.

> Operations is King.
