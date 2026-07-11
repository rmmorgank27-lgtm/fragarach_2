# METALS BASE DOCTRINE V1

**Document Class:** Constitutional Market Authority  
**Authority Layer:** Market Ecosystem  
**Authority Name:** `METALS_BASE_DOCTRINE_V1`  
**Market Name:** Spot Precious Metals  
**Market Code:** `METALS`  
**Version:** 1.0  
**Status:** APPROVED  
**Repository Location:** `constitution/doctrines/METALS_BASE_DOCTRINE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Effective From:** 2026-07-11  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** Ray Morgan  
**Approval Date:** 2026-07-11

---

# 1. Purpose

This doctrine defines the constitutional operational truth for the Spot Precious Metals market ecosystem within Fragarach II.

It establishes the market-wide authority inherited by every metals timeframe authority, evidence lane, acquisition specification, validator, native operation, migration, and acceptance proof.

It defines:

- the metals market boundary;
- spot precious-metal instrument membership;
- canonical metal and quote identity;
- troy-ounce unit authority;
- the near-continuous New York rollover calendar;
- trading-day, week, and month ownership;
- approved provider roles;
- acceptable evidence and provenance;
- price and volume semantics;
- market-wide validation and conflict rules;
- historical regime and effective-range requirements;
- the boundary between market authority and timeframe authority.

This doctrine does not define interval-specific bar alignment, provider interval codes, request chunking, bar completion, or latest-closed-bar calculations. Those matters belong to approved metals timeframe authorities.

---

# 2. Constitutional Position

```text
Constitution

↓

METALS_BASE_DOCTRINE_V1

↓

METALS Timeframe Authority

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides this doctrine;
2. this doctrine overrides subordinate metals timeframe authorities;
3. approved timeframe authorities override implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing authority.

Legacy code, provider defaults, retail-platform conventions, sample files, or existing application behaviour are not constitutional authority unless expressly adopted.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate document may weaken a mandatory requirement in this doctrine.

---

# 4. Market Definition

## 4.1 Market Identity

Spot Precious Metals is a decentralised, multi-venue, over-the-counter market in which a registered precious metal is priced in a registered fiat currency or another expressly approved quote asset.

Fragarach II recognises spot metals as a market ecosystem, not a single exchange.

There is no universal central venue, universal last trade, universal consolidated spot volume, or universal intraday bar authority for spot precious metals.

Approved providers may legitimately differ because of:

- liquidity-source composition;
- dealer and venue participation;
- bid, ask, midpoint, last, indicative, or aggregate price basis;
- filtering and aggregation;
- provider session treatment;
- maintenance windows;
- publication delay and revision behaviour.

Provider disagreement is not, by itself, proof that either evidence source is invalid.

## 4.2 Classification

**Asset Class:** `PRECIOUS_METALS`  
**Instrument Type Family:** `SPOT_METAL_PAIR`  
**Venue Model:** Decentralised multi-venue OTC  
**Trading Model:** Near-continuous, five trading days per operational week  
**Canonical Session Timezone:** `America/New_York`  
**Primary Unit:** Troy ounce  
**Quote Convention:** One troy ounce of the base metal priced in units of the quote asset

## 4.3 Included Scope

This doctrine includes:

- registered spot gold pairs;
- registered spot silver pairs;
- registered spot platinum pairs;
- registered spot palladium pairs;
- other registered precious-metal spot pairs expressly admitted by amendment;
- approved provider aggregates with declared price basis and source scope.

Initial expected examples include:

```text
XAUUSD
XAGUSD
```

Instrument registration remains mandatory. Example symbols do not create automatic membership.

## 4.4 Excluded Scope

This doctrine excludes:

- exchange-traded metal futures and options;
- forwards, swaps, leases, and financing instruments;
- mining equities;
- exchange-traded funds and trusts;
- physical inventory, vault, warehouse, or reserve series;
- official benchmark or fixing series treated as interchangeable with spot bars;
- industrial metals unless separately authorised;
- synthetic metal crosses unless separately authorised;
- provider CFDs whose underlying price basis cannot be established;
- crypto-backed or tokenised metal representations unless separately registered.

Excluded instruments require another market authority or a separately approved instrument class.

---

# 5. Instrument Membership Authority

## 5.1 Membership Rule

An instrument belongs to `METALS` only when:

1. the base asset is a registered precious metal;
2. the quote asset is explicit;
3. the canonical symbol is registered;
4. the instrument type is an approved spot-metal type;
5. the pricing unit is explicit;
6. provider symbol mappings are registered;
7. price basis is declared;
8. calendar and session authority resolve;
9. effective historical range is known;
10. it is not assigned to another market doctrine.

Symbol spelling alone does not establish membership.

## 5.2 Canonical Symbol

The default canonical symbol is:

```text
METALQUOTE
```

Examples:

```text
XAUUSD
XAGUSD
XAUEUR
```

Implementation MUST NOT parse an unknown symbol and infer metal identity, quote identity, unit, venue, or market authority.

## 5.3 Canonical Metal Codes

The following base codes MAY be registered under this doctrine when instrument authority is complete:

| Code | Metal | Default Spot Unit |
|---|---|---|
| `XAU` | Gold | Troy ounce |
| `XAG` | Silver | Troy ounce |
| `XPT` | Platinum | Troy ounce |
| `XPD` | Palladium | Troy ounce |

A code does not by itself prove instrument identity, source equivalence, or historical continuity.

## 5.4 Unit Authority

The canonical spot quantity unit under this doctrine is one troy ounce.

```text
1 troy ounce = 31.1034768 grams
```

A provider using grams, kilograms, lots, contracts, or another unit MUST declare that unit.

Unit conversion requires approved transformation authority and provenance. Implementation MUST NOT silently rescale evidence.

## 5.5 Required Metadata

Every metals registration MUST include:

- canonical symbol;
- controlled display name;
- market code `METALS`;
- asset class `PRECIOUS_METALS`;
- controlled instrument type;
- base metal code;
- quote asset or currency;
- pricing unit;
- price precision;
- quantity precision where volume exists;
- calendar authority reference;
- session authority reference;
- provider symbol mappings;
- provider or aggregate scope;
- price basis;
- effective historical range;
- operational status;
- registration and approval provenance.

Where material, registration MUST also include:

- benchmark relationship;
- conversion factor;
- source-lane identity;
- historical symbol changes;
- provider methodology change boundaries.

## 5.6 Instrument Identity

Instrument continuity MUST NOT be assumed across:

- quote-currency replacement or redenomination;
- unit changes;
- provider symbol reuse;
- benchmark methodology change;
- conversion from spot to futures or CFD basis;
- material change in provider aggregate scope;
- legal or market-structure change affecting the instrument definition.

Pre-change and post-change evidence require explicit range and continuity authority.

## 5.7 Prohibited Assumptions

Implementation MUST NOT invent:

- metal identity;
- quote identity;
- troy-ounce or other unit;
- venue or aggregate scope;
- price basis;
- session or calendar ownership;
- provider mapping;
- benchmark equivalence;
- historical continuity;
- synthetic conversion authority.

Missing authority requires a compatibility report for the affected path.

---

# 6. Canonical Metals Calendar Authority

## 6.1 Calendar Identity

**Calendar Authority:** `METALS_24X5_NEW_YORK_ROLLOVER_V1`  
**Calendar Type:** OTC near-continuous calendar  
**Timezone:** `America/New_York`

## 6.2 Operational Week

The canonical metals operational week:

- opens Sunday at **17:00 America/New_York**;
- continues through five metals trading days;
- closes Friday at **17:00 America/New_York**.

The IANA timezone rules for `America/New_York`, including daylight-saving transitions, are authoritative.

Implementation MUST NOT replace this rule with a fixed UTC offset.

This operational calendar is a Fragarach constitutional ownership model. It does not assert that every OTC dealer or venue publishes continuously throughout the entire span.

## 6.3 Daily Boundary

The canonical metals trading-day boundary is **17:00 America/New_York**.

A metals trading day begins at 17:00 on the preceding New York civil date and ends at 17:00 on its owned New York civil date.

```text
Monday metals trading day
= Sunday 17:00 New York
  through
  Monday 17:00 New York
```

The exact inclusion of the boundary instant belongs to the relevant timeframe authority.

## 6.4 Trading-Day Ownership

A metals trading day is owned by the New York civil date on which its session closes.

Therefore:

- Sunday 17:00 to Monday 17:00 is owned by Monday;
- Thursday 17:00 to Friday 17:00 is owned by Friday;
- there is no canonical Saturday or Sunday metals trading day.

## 6.5 Week Ownership

The metals trading week consists of Monday through Friday trading days and is owned by the New York civil date of the Friday session close.

## 6.6 Month Ownership

A metals trading day belongs to the calendar month of its owned New York close date.

## 6.7 Weekend Closure

The period after Friday 17:00 and before Sunday 17:00 New York time is a canonical weekend closure.

No bar is expected wholly inside that closure unless an approved timeframe authority explicitly defines otherwise.

## 6.8 Holidays and Exceptional Closures

Spot precious metals have no single exchange holiday calendar that closes every dealer, venue, and provider.

Therefore:

- a public holiday in one jurisdiction is not automatically a global metals closure;
- reduced liquidity is not automatically a non-trading period;
- provider silence is not proof of global market closure;
- exchange-futures holiday hours do not automatically define OTC spot closure;
- Christmas, New Year, emergency closure, and exceptional non-publication periods require explicit evidence or an approved exception.

Calendar corrections MUST be versioned and auditable.

Historical trading-day ownership MUST NOT be silently changed.

---

# 7. Session Authority

## 7.1 Canonical Session

The constitutional metals session model is:

```text
METALS_DAILY_SESSION_V1
```

with:

```text
Open:  17:00 America/New_York on the preceding civil date
Close: 17:00 America/New_York on the owned civil date
Owner: close-date civil day in America/New_York
```

## 7.2 Regional Session Labels

Asia, London, Europe, New York, and other regional session labels MAY be used for analysis or display.

They are not constitutional evidence-lane boundaries and MUST NOT redefine the canonical rollover or trading-day owner.

## 7.3 Provider Maintenance and Publication Breaks

Providers or venues may observe daily maintenance, settlement, illiquidity, or publication breaks.

Such a break affects expected evidence only when:

- provider scope is declared;
- the break is supported by provider semantics or evidence;
- the applicable timeframe authority defines the operational consequence.

Implementation MUST NOT convert a provider-specific break into a market-wide closure.

## 7.4 Benchmark Windows

London or other benchmark windows MAY be relevant reference events.

A benchmark price or fixing is a distinct evidence type and MUST NOT be substituted for a spot OHLC bar unless separately authorised.

## 7.5 Precedence

```text
Approved instrument-specific exception

↓

Approved METALS timeframe authority

↓

METALS_BASE_DOCTRINE_V1

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
| Twelve Data | Primary automated acquisition provider | Registered metals instruments and approved metals timeframes | Symbol mapping, price basis, source scope, and approved timeframe semantics MUST exist |
| Operator-supplied file | Manual evidence source | Registered metals instruments and approved metals timeframes | Origin, provider or venue scope, checksum, parser result, unit, and provenance MUST be retained |
| Existing accepted immutable evidence | Historical evidence source | Evidence already accepted by Fragarach II | Original provenance remains immutable |

No futures exchange, benchmark administrator, dealer feed, or additional data vendor is approved as a bar-acquisition provider by this version.

Additional providers require constitutional amendment or separate provider authority.

## 8.2 Provider Scope

Every provider mapping MUST declare whether evidence represents:

- bid;
- ask;
- midpoint;
- last or indicative trade;
- provider aggregate;
- dealer composite;
- benchmark;
- another expressly approved price basis.

A matching symbol does not prove price-basis equivalence.

## 8.3 Provider Semantics Boundary

Each metals timeframe authority MUST define, for every approved provider:

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
- daily maintenance treatment;
- historical coverage;
- unit and precision behaviour.

Implementation MUST NOT proceed for a provider/timeframe combination until those facts are approved.

## 8.4 Provider Precedence

There is no market-wide rule that the newest provider response, highest row count, or smallest spread automatically wins.

Compatible conflicting evidence MUST be retained and resolved only by an approved lane-resolution rule.

Silent overwrite is prohibited.

---

# 9. Evidence Authority

## 9.1 Immutability

Accepted metals evidence is immutable.

A correction requires new evidence, new provenance, a new validation result, and an auditable resolution decision.

## 9.2 Acceptable Sources

Acceptable sources are:

- approved provider API responses;
- approved provider exports;
- operator-supplied files with declared source and price basis;
- existing immutable Fragarach II evidence;
- official benchmark publications only where separately authorised for their distinct evidence type.

## 9.3 Evidence Identity

Every evidence block MUST identify:

- canonical instrument;
- source symbol;
- provider or source identity;
- source role;
- price basis;
- provider or aggregate scope;
- pricing unit;
- timeframe;
- requested and received ranges;
- observed timestamp range;
- row count;
- checksum;
- acquisition timestamp;
- parser or adapter version;
- volume basis where present;
- timestamp interpretation;
- evidence and validation status.

## 9.4 Prohibitions

Implementation MUST NOT:

- fabricate missing bars;
- mutate accepted evidence;
- discard provider conflicts without record;
- shift timestamps without approved mapping;
- merge price bases by assumption;
- convert grams, kilograms, lots, or contracts to troy ounces without authority;
- substitute futures settlement or benchmark fixes for spot bars;
- create synthetic metal crosses without construction authority;
- treat provider-estimated volume as universal market volume.

---

# 10. Price and Volume Semantics

## 10.1 Price

Metals OHLC evidence represents the provider's declared spot-price basis within its declared source scope.

It is not a universal consolidated market price.

The price basis MUST be one of:

- bid;
- ask;
- midpoint;
- last or indicative trade;
- provider aggregate;
- dealer composite;
- another expressly approved basis.

Different price bases MUST NOT be merged without construction authority.

## 10.2 Quote Direction

For `METALQUOTE`:

```text
one troy ounce of METAL is priced in units of QUOTE
```

Pair inversion or conversion into another quote currency requires approved transformation authority and provenance.

## 10.3 Volume

Spot metals have no universal consolidated volume authority.

Provider volume may mean:

- tick count;
- quote updates;
- provider-estimated activity;
- venue-specific units;
- another declared measure;
- unavailable.

Meaning and unit MUST be explicit.

Volume from different sources MUST NOT be treated as directly comparable without authority.

## 10.4 Zero, Null, and Absent Volume

Zero, null, or absent volume MAY be valid depending on source semantics.

Measured zero SHOULD remain distinguishable from absent or unknown volume.

Missing volume MUST NOT invalidate valid OHLC evidence unless the timeframe authority makes it mandatory.

## 10.5 Benchmark and Futures Separation

A benchmark fixing, futures contract, settlement price, ETF price, or physical-market quote is not interchangeable with a registered spot-metal bar.

Any relationship between them is analytical unless separate construction authority exists.

---

# 11. Market-Wide Validation Authority

## 11.1 Mandatory Validation

Every metals row MUST be evaluated for:

- registered instrument identity;
- registered metal and quote identity;
- approved provider mapping;
- declared price basis and source scope;
- declared pricing unit;
- timestamp parseability and timezone interpretation;
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

Negative spot-metal prices are invalid unless a named constitutional exception permits them.

A zero spot-metal price is invalid unless a named historical or technical exception permits it.

## 11.2 Calendar Validation

A row MUST be evaluated against the approved New York rollover calendar.

Provider-specific maintenance gaps, thin-liquidity periods, and holidays are not automatically invalid.

Exact expectedness, tolerance, and materiality belong to the timeframe authority.

## 11.3 Lane Identity and Conflict

The constitutional lane key begins with:

```text
registered instrument + approved timeframe + canonical timestamp
```

Price basis or source scope MAY be an additional lane dimension where registration or provider authority requires it.

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

Usable accepted evidence MUST remain available when a provider, venue, or newer acquisition is delayed, stale, incomplete, or under review.

Warnings MUST remain visible.

Missing authority stops only the affected acquisition, validation, construction, or migration path.

It MUST NOT unnecessarily disable unrelated lanes or the wider operations console.

**Operations is King.**

---

# 12. Structural Metals Events

## 12.1 Governed Events

Metals authority MUST account for:

- quote-currency redenomination or replacement;
- unit-of-measure change;
- provider symbol remapping;
- benchmark methodology change;
- provider aggregate methodology change;
- source or dealer-composition change;
- market suspension;
- exceptional closure;
- instrument retirement;
- conversion between spot, benchmark, futures, or CFD basis.

## 12.2 Continuity Rule

No structural event automatically permits continuity.

Authority MUST decide:

- whether pre-event and post-event evidence represents the same instrument;
- whether a new registration is required;
- whether one lane may span the event;
- whether conversion or scaling is authorised;
- whether historical evidence requires reclassification;
- the effective transition timestamp.

Implementation MUST NOT splice or rescale histories by assumption.

## 12.3 Unit Conversion Rule

Unit conversion requires:

- source unit;
- target unit;
- approved conversion factor;
- effective range;
- transformation provenance;
- lane-continuity decision.

Silent conversion is prohibited.

---

# 13. Effective Historical Range

## 13.1 Start Rule

There is no universal earliest date for every metals instrument or provider series.

The effective start for a registered instrument is the latest of:

1. the date the instrument identity and quote regime became valid;
2. the start of the approved unit and price basis;
3. the start of approved provider semantics;
4. the earliest reliable compatible evidence;
5. any instrument-specific authority date.

## 13.2 End Rule

The default end is `OPEN` while the metal identity, quote identity, instrument registration, and provider mapping remain valid.

## 13.3 Provider Coverage

Provider history limits restrict that provider's approved range.

They do not redefine the market-level existence of the instrument.

Historical evidence outside an approved regime or range may be retained but MUST NOT enter an active canonical lane until resolved.

---

# 14. Timeframe Inheritance

Every metals timeframe authority MUST inherit:

- metals market identity;
- instrument membership;
- base-metal and quote semantics;
- troy-ounce unit authority;
- `America/New_York` calendar timezone;
- Sunday 17:00 week open;
- Friday 17:00 week close;
- 17:00 New York daily boundary;
- close-date trading-day ownership;
- provider roles;
- evidence immutability;
- price-basis and source-scope provenance;
- non-centralised volume doctrine;
- market-wide validation;
- structural-event and effective-range rules.

A timeframe authority MUST NOT contradict these facts.

---

# 15. Required Metals Timeframe Authorities

| Timeframe | Required Authority | Status |
|---|---|---|
| `D1` | `METALS_D1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `H1` | `METALS_H1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M30` | `METALS_M30_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M5` | `METALS_M5_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |

Additional timeframe authorities require an approved amendment or later doctrine version.

Existing accepted D1 behaviour is not silently invalidated or re-authorised by this draft.

---

# 16. Explicit Delegation to Timeframe Authorities

The following are intentionally delegated:

- interval duration and type;
- alignment origin and boundary rule;
- canonical timestamp meaning;
- provider timestamp mapping;
- bar completion and latest-closed-bar rules;
- direct versus derived precedence;
- rollup eligibility;
- request codes, limits, pagination, chunking, and overlap;
- exact duplicate fields;
- provider maintenance-gap treatment;
- gap expectedness and materiality;
- freshness thresholds;
- timeframe-specific effective ranges.

These are not implementation choices.

Implementation MUST wait for approved timeframe authority.

---

# 17. Compatibility Requirements

Before a metals implementation specification begins, it MUST prove that:

- this doctrine is approved;
- the relevant timeframe authority is approved;
- the instrument is registered as `METALS`;
- metal and quote identities are explicit;
- pricing unit is explicit;
- provider mapping and role are valid;
- price basis and source scope are explicit;
- calendar and session authority resolve;
- effective range is known;
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
- metal or quote identity;
- pricing unit;
- daily rollover boundary;
- trading-day ownership;
- operational week;
- provider role;
- price or volume meaning;
- benchmark equivalence;
- structural-event meaning;
- effective-range authority.

---

# 19. Implementation Prohibitions

Implementation MUST NOT:

- treat spot metals as a single-exchange market;
- assume a universal last price or consolidated volume;
- use a fixed UTC rollover offset;
- create Saturday or Sunday trading days;
- treat every public holiday or futures closure as a global spot closure;
- treat provider silence as market closure;
- substitute benchmark or futures data for spot bars;
- infer or apply unit conversion without authority;
- merge unlike price bases;
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
- instrument membership;
- canonical pricing unit;
- rollover timezone or daily boundary;
- trading-day or week ownership;
- provider roles;
- price or volume doctrine;
- benchmark treatment;
- structural-event treatment;
- effective-range logic;
- required timeframe authorities;
- inheritance rules.

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| 1.0 | 2026-07-11 | Initial metals constitutional doctrine drafted | Establish market authority before further timeframe implementation | PENDING |

Superseded versions remain immutable and auditable.

---

# 22. Approval Gate

This doctrine may be marked **APPROVED** only when:

- market scope is accepted;
- instrument and unit authority are accepted;
- calendar and session model are accepted;
- day, week, and month ownership are accepted;
- provider roles are accepted;
- evidence rules are accepted;
- price and volume semantics are accepted;
- benchmark separation is accepted;
- validation and structural-event rules are accepted;
- effective-range logic is accepted;
- required timeframe authorities are accepted;
- exceptions and approval identity are recorded.

---

# 23. Acceptance Statement

Upon approval:

> `METALS_BASE_DOCTRINE_V1` is the approved constitutional authority for the Spot Precious Metals market ecosystem within Fragarach II. All subordinate metals timeframe authorities, specifications, implementations, acquisitions, validations, migrations, evidence-lane operations, and acceptance proofs MUST conform to it.

---

# 24. Governing Principle

> Spot precious metals are decentralised OTC instruments governed operationally by explicit metal identity, troy-ounce unit authority, New York rollover ownership, declared provider price basis, immutable evidence, and visible uncertainty.

Provider convention may be mapped.

Implementation may encode.

Neither may invent authority.

**Operations is King.**
