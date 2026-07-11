# FX BASE DOCTRINE V1

**Document Class:** Constitutional Market Authority  
**Authority Layer:** Market Ecosystem  
**Authority Name:** `FX_BASE_DOCTRINE_V1`  
**Market Name:** Foreign Exchange  
**Market Code:** `FX`  
**Version:** 1.0  
**Status:** APPROVED  
**Repository Location:** `constitution/doctrines/FX_BASE_DOCTRINE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Effective From:** 2026-07-11  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** Ray Morgan  
**Approval Date:** 2026-07-11

---

# 1. Purpose

This doctrine defines the constitutional operational truth for the Foreign Exchange market ecosystem within Fragarach II.

It establishes the market-wide authority inherited by every FX timeframe authority, evidence lane, acquisition specification, validator, native operation, migration, and acceptance proof.

It defines:

- the FX market boundary;
- FX instrument membership;
- the canonical FX calendar and session model;
- trading-day, week, and month ownership;
- approved provider roles;
- acceptable evidence and provenance;
- price and volume semantics;
- market-wide validation and conflict rules;
- historical regime and effective-range requirements;
- the boundary between market authority and timeframe authority.

This doctrine does not define interval-specific bar alignment, provider interval codes, request chunking, or latest-closed-bar calculations. Those matters belong to approved FX timeframe authorities.

---

# 2. Constitutional Position

```text
Constitution

↓

FX_BASE_DOCTRINE_V1

↓

FX Timeframe Authority

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides this doctrine;
2. this doctrine overrides subordinate FX timeframe authorities;
3. approved timeframe authorities override implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing authority.

Legacy code, provider defaults, sample files, or existing application behaviour are not constitutional authority unless expressly adopted.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate document may weaken a mandatory requirement in this doctrine.

---

# 4. Market Definition

## 4.1 Market Identity

Foreign Exchange is a decentralised, multi-venue, over-the-counter market in which one currency is priced in units of another currency.

Fragarach II recognises FX as a market ecosystem, not a single exchange.

There is no universal central venue, universal last trade, or universal consolidated spot-FX volume authority.

Approved providers may legitimately differ because of:

- liquidity-source composition;
- bid, ask, midpoint, last, or aggregate price basis;
- filtering and aggregation;
- provider session treatment;
- publication delay and revision behaviour.

Provider disagreement is not, by itself, proof that either evidence source is invalid.

## 4.2 Classification

**Asset Class:** `FOREIGN_EXCHANGE`  
**Venue Model:** Decentralised multi-venue OTC  
**Trading Model:** Near-continuous, five trading days per operational week  
**Canonical Session Timezone:** `America/New_York`  
**Quote Convention:** Base currency priced in quote currency

## 4.3 Included Scope

This doctrine includes:

- registered spot currency pairs;
- registered spot-like FX evidence whose source and price basis are explicit;
- approved major, minor, and exotic currency pairs;
- approved historical currency regimes with explicit effective ranges.

## 4.4 Excluded Scope

This doctrine excludes:

- precious metals, including `XAUUSD` and `XAGUSD`;
- cryptoassets;
- exchange-traded currency futures;
- options, forwards, swaps, and non-deliverable forwards;
- interest-rate instruments;
- baskets and indices;
- synthetic crosses unless separately authorised;
- provider CFDs that cannot be shown to represent an approved FX price basis.

Excluded instruments require another market authority.

---

# 5. Instrument Membership Authority

## 5.1 Membership Rule

An instrument belongs to FX only when:

1. it represents an exchange rate between two registered currencies;
2. base and quote currencies are explicit;
3. the canonical symbol is registered;
4. provider symbol mappings are registered;
5. price basis is declared;
6. calendar and session authority resolve;
7. effective historical range is known;
8. it is not assigned to another market doctrine.

Symbol spelling alone does not establish membership.

## 5.2 Canonical Symbol

The default canonical symbol is:

```text
BASEQUOTE
```

Examples:

```text
AUDUSD
EURGBP
USDJPY
```

Implementation MUST NOT split an unknown symbol and infer authority.

## 5.3 Required Metadata

Every FX registration MUST include:

- canonical symbol;
- controlled display name;
- market code `FX`;
- asset class `FOREIGN_EXCHANGE`;
- controlled instrument type;
- base currency;
- quote currency;
- price precision;
- calendar authority reference;
- session authority reference;
- provider symbol mappings;
- price basis;
- effective historical range;
- operational status;
- registration and approval provenance.

## 5.4 Currency Identity

Currency identity MUST be historically explicit.

Continuity MUST NOT be assumed across:

- redenomination;
- currency replacement;
- monetary union;
- code reuse;
- legal-tender transition;
- material peg-regime change.

Predecessor and successor currencies require explicit ranges and, where necessary, separate registrations.

## 5.5 Prohibited Assumptions

Implementation MUST NOT invent:

- base or quote currency;
- currency-code meaning;
- venue identity;
- price basis;
- session or calendar ownership;
- provider mapping;
- historical continuity;
- synthetic conversion authority.

Missing authority requires a compatibility report for the affected path.

---

# 6. Canonical FX Calendar Authority

## 6.1 Calendar Identity

**Calendar Authority:** `FX_24X5_NEW_YORK_ROLLOVER_V1`  
**Calendar Type:** OTC near-continuous calendar  
**Timezone:** `America/New_York`

## 6.2 Operational Week

The canonical FX operational week:

- opens Sunday at **17:00 America/New_York**;
- continues through five FX trading days;
- closes Friday at **17:00 America/New_York**.

The IANA timezone rules for `America/New_York`, including daylight-saving transitions, are authoritative.

Implementation MUST NOT replace this rule with a fixed UTC offset.

## 6.3 Daily Boundary

The canonical FX trading-day boundary is **17:00 America/New_York**.

A trading day begins at 17:00 on the preceding New York civil date and ends at 17:00 on its owned New York civil date.

```text
Monday FX trading day
= Sunday 17:00 New York
  through
  Monday 17:00 New York
```

The exact inclusion of the boundary instant is defined by the relevant timeframe authority.

## 6.4 Trading-Day Ownership

An FX trading day is owned by the New York civil date on which its session closes.

Therefore:

- Sunday 17:00 to Monday 17:00 is owned by Monday;
- Thursday 17:00 to Friday 17:00 is owned by Friday;
- there is no canonical Saturday or Sunday FX trading day.

## 6.5 Week Ownership

The FX trading week consists of Monday through Friday trading days and is owned by the New York civil date of the Friday session close.

## 6.6 Month Ownership

An FX trading day belongs to the calendar month of its owned New York close date.

## 6.7 Weekend Closure

The period after Friday 17:00 and before Sunday 17:00 New York time is a canonical weekend closure.

No bar is expected wholly inside that closure unless an approved timeframe authority explicitly defines otherwise.

## 6.8 Holidays and Exceptional Closures

FX has no single exchange holiday calendar that closes the entire global market.

Therefore:

- a public holiday in one jurisdiction is not automatically a global FX closure;
- reduced liquidity is not automatically a non-trading period;
- provider absence is not proof of global market closure;
- Christmas, New Year, emergency closure, and exceptional non-publication periods require explicit evidence or an approved exception.

Calendar corrections MUST be versioned and auditable.

Historical trading-day ownership MUST NOT be silently changed.

---

# 7. Session Authority

## 7.1 Canonical Session

The constitutional FX session model is:

```text
FX_DAILY_SESSION_V1
```

with:

```text
Open:  17:00 America/New_York on the preceding civil date
Close: 17:00 America/New_York on the owned civil date
Owner: close-date civil day in America/New_York
```

## 7.2 Regional Session Labels

Sydney, Tokyo, London, and New York session labels MAY be used for analysis or display.

They are not constitutional evidence-lane boundaries and MUST NOT redefine canonical bar alignment or day ownership.

## 7.3 Rollover and Maintenance

A provider may pause, omit quotes, or widen spreads around rollover.

There is no universal constitutional maintenance duration.

Provider-specific behaviour MUST be defined by the applicable provider or timeframe authority.

Implementation MUST NOT invent a universal gap exemption around 17:00 New York.

## 7.4 Precedence

```text
Approved instrument-specific exception

↓

Approved FX timeframe authority

↓

FX_BASE_DOCTRINE_V1

↓

Approved provider mapping and semantics

↓

Implementation
```

Provider convention may map into constitutional truth. It does not override it.

---

# 8. Provider Authority

## 8.1 Approved Roles

| Source | Approved Role | Scope | Conditions |
|---|---|---|---|
| Twelve Data | Primary automated acquisition provider | Registered FX instruments and approved FX timeframes | Provider mapping and approved timeframe semantics MUST exist |
| Operator-supplied file | Manual evidence source | Registered FX instruments and approved FX timeframes | Origin, source identity, checksum, parser result, and provenance MUST be retained |
| Existing accepted immutable evidence | Historical evidence source | Evidence already accepted by Fragarach II | Original provenance remains immutable |

No other automated provider is approved by this version.

Additional providers require constitutional amendment or separate provider authority.

## 8.2 Provider Semantics Boundary

Each FX timeframe authority MUST define, for every approved provider:

- interval code;
- timestamp meaning and timezone;
- request start and end semantics;
- inclusive and exclusive boundaries;
- row and span limits;
- pagination;
- chunking and overlap;
- response ordering;
- duplicate behaviour;
- partial-bar behaviour;
- empty-response meaning;
- revision behaviour;
- effective historical coverage.

Implementation MUST NOT proceed for a provider/timeframe combination until those facts are approved.

## 8.3 Price Basis

Provider evidence MUST declare one price basis:

- bid;
- ask;
- midpoint;
- last;
- provider aggregate;
- another expressly approved basis.

Unlike price bases MUST NOT be silently combined.

## 8.4 Provider Conflict

There is no rule that the newest provider response automatically wins.

Compatible conflicting evidence MUST be retained and resolved only by an approved lane-resolution rule.

Silent overwrite is prohibited.

---

# 9. Evidence Authority

## 9.1 Immutability

Accepted FX evidence is immutable.

A correction requires new evidence, new provenance, a new validation result, and an auditable resolution decision.

## 9.2 Acceptable Sources

Acceptable sources are:

- approved provider API responses;
- approved provider exports;
- operator-supplied files with declared origin;
- existing immutable Fragarach II evidence;
- official monetary-authority publications only where separately authorised.

## 9.3 Evidence Identity

Every evidence block MUST identify:

- canonical instrument;
- source symbol;
- provider or source identity;
- source role;
- timeframe;
- requested and received ranges;
- observed timestamp range;
- row count;
- checksum;
- acquisition timestamp;
- parser or adapter version;
- price basis;
- timestamp interpretation;
- evidence and validation status.

## 9.4 Prohibitions

Implementation MUST NOT:

- fabricate missing bars;
- calculate a synthetic cross without authority;
- mutate accepted evidence;
- discard conflicts without record;
- shift timestamps without approved mapping;
- infer price basis from OHLC values;
- merge providers into one bar without construction authority.

---

# 10. Price and Volume Semantics

## 10.1 Price

FX OHLC evidence represents the approved provider's declared price basis for the registered pair.

It does not represent a universal consolidated FX price.

The price basis MUST remain attached to provenance.

## 10.2 Quote Direction

For `BASEQUOTE`:

```text
one unit of BASE is priced in units of QUOTE
```

Reversal or inversion requires explicit transformation authority and provenance.

## 10.3 Volume

Spot FX has no universal centralised volume.

A provider volume field may represent:

- tick count;
- provider-observed activity;
- provider-defined volume;
- no meaningful volume.

Its meaning MUST be declared.

Volume from different providers MUST NOT be treated as directly comparable without authority.

## 10.4 Zero, Null, and Absent Volume

Zero, null, or absent volume MAY be valid.

It MUST NOT invalidate valid OHLC evidence unless the timeframe authority makes volume mandatory.

Measured zero and missing volume SHOULD remain distinguishable.

---

# 11. Market-Wide Validation Authority

## 11.1 Mandatory Validation

Every FX row MUST be evaluated for:

- registered identity;
- valid base and quote currencies;
- approved provider mapping;
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

Negative FX prices are invalid unless a named constitutional exception permits them.

A zero FX price is invalid unless a named exception permits it.

## 11.2 Timeframe Validation

Session membership, interval alignment, expected-bar determination, partial-bar status, exact duplicate meaning, and gap materiality are defined by the applicable timeframe authority.

## 11.3 Severity

| Severity | Meaning | Operational Consequence |
|---|---|---|
| `INFO` | Observed non-error condition | Retain and report |
| `WARNING` | Non-fatal uncertainty | Continue with visible warning |
| `REJECT` | Constitutionally invalid evidence | Reject affected evidence and retain proof |
| `CONFLICT` | Compatible evidence disagrees | Retain all evidence and require resolution |
| `BLOCKED` | Required authority is missing | Stop only the affected path and emit compatibility report |

## 11.4 Operations Doctrine

Usable accepted evidence MUST remain available when newer acquisition is delayed, stale, incomplete, or under review.

Warnings MUST remain visible.

Missing authority stops only the affected acquisition, validation, construction, or migration path.

It MUST NOT unnecessarily disable unrelated lanes or the wider operations console.

**Operations is King.**

---

# 12. Structural and Monetary Events

FX authority MUST account for:

- currency introduction or withdrawal;
- redenomination;
- monetary union;
- official code change;
- peg introduction or removal;
- legal-tender transition;
- capital-control regime change;
- market suspension;
- provider symbol remapping;
- material quotation or decimal changes.

These events do not automatically permit continuity.

Each affected instrument requires an explicit range, transition decision, and transformation provenance where applicable.

Implementation MUST NOT splice predecessor and successor histories by assumption.

---

# 13. Effective Historical Range

## 13.1 Start Rule

There is no universal earliest date for all FX instruments.

The lane start is the latest of:

1. the date both currencies existed under the registered identities;
2. the date the pair became operationally meaningful;
3. the start of approved provider semantics;
4. the earliest reliable compatible evidence;
5. any instrument-specific authority date.

## 13.2 End Rule

The default end is `OPEN` while both currencies, the pair registration, and provider mapping remain valid.

## 13.3 Provider Coverage

Provider history limits restrict that provider's approved range.

They do not redefine the market-level existence of the pair.

Historical evidence outside an approved regime or range may be retained but MUST NOT enter an active canonical lane until resolved.

---

# 14. Timeframe Inheritance

Every FX timeframe authority MUST inherit:

- FX market identity;
- instrument membership;
- base and quote semantics;
- `America/New_York` calendar timezone;
- Sunday 17:00 week open;
- Friday 17:00 week close;
- 17:00 New York daily boundary;
- close-date trading-day ownership;
- provider roles;
- evidence immutability;
- price-basis provenance;
- non-centralised volume doctrine;
- market-wide validation;
- structural-event and effective-range rules.

A timeframe authority MUST NOT contradict these facts.

---

# 15. Required FX Timeframe Authorities

| Timeframe | Required Authority | Status |
|---|---|---|
| `D1` | `FX_D1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `H1` | `FX_H1_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M30` | `FX_M30_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |
| `M5` | `FX_M5_AUTHORITY_V1` | REQUIRED — NOT YET APPROVED |

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
- gap expectedness and materiality;
- freshness thresholds;
- timeframe-specific effective ranges.

These are not implementation choices.

Implementation MUST wait for approved timeframe authority.

---

# 17. Compatibility Requirements

Before an FX implementation specification begins, it MUST prove that:

- this doctrine is approved;
- the relevant timeframe authority is approved;
- the instrument is registered as FX;
- base and quote currencies are explicit;
- provider mapping and role are valid;
- price basis is explicit;
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
- pair membership;
- quote direction;
- daily rollover boundary;
- trading-day ownership;
- operational week;
- provider role;
- price or volume meaning;
- structural-event meaning;
- effective-range authority.

---

# 19. Implementation Prohibitions

Implementation MUST NOT:

- treat FX as a single-exchange market;
- assume a universal last price;
- use a fixed UTC rollover offset;
- create Saturday or Sunday trading days;
- treat every public holiday as a global closure;
- treat provider silence as market closure;
- infer synthetic crosses;
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
- rollover timezone or daily boundary;
- trading-day or week ownership;
- provider roles;
- price or volume doctrine;
- structural-event treatment;
- effective-range logic;
- required timeframe authorities;
- inheritance rules.

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| 1.0 | 2026-07-11 | Initial FX constitutional doctrine drafted | Establish market authority before further timeframe implementation | PENDING |

Superseded versions remain immutable and auditable.

---

# 22. Approval Gate

This doctrine may be marked **APPROVED** only when:

- market scope is accepted;
- calendar and session model are accepted;
- day, week, and month ownership are accepted;
- provider roles are accepted;
- evidence rules are accepted;
- price and volume semantics are accepted;
- validation and structural-event rules are accepted;
- effective-range logic is accepted;
- required timeframe authorities are accepted;
- exceptions and approval identity are recorded.

---

# 23. Acceptance Statement

Upon approval:

> `FX_BASE_DOCTRINE_V1` is the approved constitutional authority for the Foreign Exchange market ecosystem within Fragarach II. All subordinate FX timeframe authorities, specifications, implementations, acquisitions, validations, migrations, evidence-lane operations, and acceptance proofs MUST conform to it.

---

# 24. Governing Principle

> FX is a decentralised market governed operationally by explicit currency identity, New York rollover ownership, declared provider semantics, immutable evidence, and visible uncertainty.

Provider convention may be mapped.

Implementation may encode.

Neither may invent authority.

**Operations is King.**
