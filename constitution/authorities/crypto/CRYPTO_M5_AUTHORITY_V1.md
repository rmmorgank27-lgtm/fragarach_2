# CRYPTO M5 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority
**Authority Layer:** Market Timeframe
**Authority Name:** `CRYPTO_M5_AUTHORITY_V1`
**Market Name:** Cryptoassets
**Market Code:** `CRYPTO`
**Timeframe:** `M5`
**Version:** 1.0
**Status:** DRAFT FOR APPROVAL
**Repository Location:** `constitution/authorities/crypto/CRYPTO_M5_AUTHORITY_V1.md`
**Governing Constitution:** `constitution/CONSTITUTION.md`
**Parent Authority:** `constitution/doctrines/CRYPTO_BASE_DOCTRINE_V1.md`
**Effective From:** Not effective until approved
**Effective Until:** OPEN
**Supersedes:** NONE
**Approved By:** PENDING
**Approval Date:** PENDING

---
# 1. Purpose

This authority defines the approved operational truth for `M5` evidence within the Cryptoasset market ecosystem of Fragarach II.

It establishes:

- what one crypto `M5` bar represents;
- canonical UTC interval alignment and ownership;
- canonical timestamp meaning;
- continuous 24×7 expectedness;
- direct provider evidence only;
- bar completion and latest-closed-bar rules;
- Twelve Data request and response semantics;
- provider, venue-scope, quote-asset, and price-basis requirements;
- exact effective-range determination;
- gap, duplicate, overlap, revision, conflict, and repair rules;
- the `CRYPTO_M5_VALIDATOR_V1` validation contract;
- operational freshness and evidence-lane eligibility.

This authority does not define database schemas, client implementation, secret storage, native application layout, migration procedure, or scheduling architecture.

Those matters belong to specifications that consume this authority.

---
# 2. Constitutional Position

```text
Constitution

↓

CRYPTO_BASE_DOCTRINE_V1

↓

CRYPTO_M5_AUTHORITY_V1

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides all subordinate documents;
2. `CRYPTO_BASE_DOCTRINE_V1` overrides this authority;
3. this authority overrides implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing operational facts.

Provider defaults, exchange chart conventions, legacy files, and prior application behaviour are not authority unless expressly adopted.

---
# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

- **MUST / SHALL** indicates a mandatory constitutional requirement.
- **MUST NOT / SHALL NOT** indicates a prohibited action.
- **SHOULD** indicates the expected default unless a documented exception exists.
- **MAY** indicates permitted but optional behaviour.

No subordinate specification may weaken a mandatory requirement defined here.

---
# 4. Document Identity and Scope

## 4.1 Authority Scope

This authority applies only to:

- instruments registered under market code `CRYPTO`;
- timeframe code `M5`;
- spot cryptoasset pairs or approved crypto aggregates within the parent doctrine;
- evidence whose provider, venue or aggregate scope, quote asset, price basis, timestamp meaning, and effective segment are known;
- Twelve Data evidence under the contract in Section 12;
- operator-supplied evidence satisfying the same canonical semantics;
- existing accepted immutable evidence;
- derived evidence only where Section 10 expressly permits it.

## 4.2 Excluded Scope

This authority does not govern:

- perpetual swaps, dated futures, options, leveraged tokens, ETFs, equities, staking yields, or on-chain metrics;
- unregistered wrapped, bridged, synthetic, or derivative representations;
- calculated cross rates or stablecoin-to-fiat substitutions without separate authority;
- a venue, provider aggregate, or provider/timeframe combination whose semantics are not approved;
- any timeframe other than `M5`.

## 4.3 Inherited Market Truth

This authority inherits without modification:

- crypto market and instrument identity;
- base and quote asset semantics;
- explicit venue or aggregate scope;
- continuous `CRYPTO_CONTINUOUS_UTC_V1` calendar;
- no universal weekend or holiday closure;
- UTC day, week, and month ownership;
- stablecoin and fiat quote separation;
- provider roles and immutable evidence doctrine;
- price-basis and volume-basis requirements;
- structural-event, fork, migration, listing, and delisting rules;
- market-wide validation and effective-range doctrine.

---
# 5. Canonical Timeframe Definition

## 5.1 Timeframe Identity

**Timeframe Code:** `M5`
**Nominal Duration:** 5 minutes
**Time Unit:** `MINUTE`
**Interval Type:** `FIXED-DURATION`

## 5.2 Approved Definition

One canonical crypto `M5` bar covers the fixed interval `[open, open + 5 minutes)` aligned to a UTC minute divisible by five, with second and subsecond equal to zero.

## 5.3 Bar Meaning

A complete crypto `M5` bar contains the approved provider's declared OHLC for one canonical interval within one declared venue or aggregate scope and one declared price basis.

A bar MUST originate as an approved direct provider or direct operator-supplied bar under Version 1.

Direct and derived evidence are not assumed to be numerically identical.

The origin and construction method MUST remain explicit in provenance.

There is no constitutional regular-hours versus extended-hours split for spot crypto under this authority.

## 5.4 Elapsed Duration

Every canonical `M5` interval has a fixed elapsed duration of 5 minutes. Daylight-saving transitions do not change it.

Implementation MUST NOT anchor crypto intervals to a local exchange timezone or create daylight-saving gaps or duplicates.

---
# 6. Interval Alignment Authority

## 6.1 Alignment Origin

**Approved Alignment Origin:** UTC Unix-time grid, with UTC midnight as the civil-day origin.

`M5` intervals align to a UTC minute divisible by five, with second and subsecond equal to zero.

## 6.2 Boundary Rule

Every interval uses:

```text
[start, end)
```

An observation exactly at `end` belongs to the next interval.

## 6.3 Alignment Formula

```text
interval_open = floor_UTC(timestamp, 5 minutes)
interval_end  = interval_open + 5 minutes
```

Canonical calculations MUST use timezone-aware UTC instants.

## 6.4 Session, Day, Week, and Month Crossing

A canonical `M5` interval MAY cross regional session labels and exchange-local dates, but MUST NOT cross its UTC-aligned boundary.

Intervals continue without interruption across:

- Saturday and Sunday;
- civil holidays;
- regional daylight-saving transitions;
- month-end and year-end.

An interval that crosses UTC midnight is prohibited because alignment creates a boundary at UTC midnight.

## 6.5 Partial Intervals

A shortened or incomplete interval caused by instrument launch, pair listing, delisting, venue halt, provider outage, network interruption, acquisition interruption, or incomplete source coverage MUST NOT be silently promoted to a complete canonical bar.

Such evidence MAY be retained as `PARTIAL` or `PROVISIONAL` with visible provenance.

No holiday, weekend, or daylight-saving exception is permitted merely because a provider omitted rows.

---
# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `INTERVAL OPEN`
**Canonical Storage Timezone:** `UTC`

Every accepted canonical `M5` bar MUST be identified by the UTC instant at which its interval begins.

The canonical textual representation is RFC 3339 UTC:

```text
YYYY-MM-DDTHH:MM:SSZ
```

## 7.2 Provider Timestamp Mapping

| Provider | Provider Timestamp Meaning | Provider Timezone | Canonical Mapping | Notes |
|---|---|---|---|---|
| Twelve Data | Provider interval label, accepted as interval open only under this contract | UTC request | Parse, normalise to UTC, prove alignment, retain source label | The request MUST use `timezone=UTC`. The provider label is mapped as interval open only when alignment validation passes. |
| Operator-supplied file | Declared by manifest | Declared by manifest | Convert to UTC only under declared unambiguous mapping | Guessing is prohibited |
| Existing immutable evidence | Original accepted meaning | Original accepted timezone | Preserve accepted canonical identity | No silent remapping |

## 7.3 Date-Only Values

**Date-Only Allowed:** `NO`

A date-only value cannot identify an intraday interval and MUST be rejected for active use.

## 7.4 Ambiguous, Invalid, or Repeated Local Timestamps

Crypto canonical timestamps are UTC and therefore do not have daylight-saving folds or gaps.

A source timestamp MUST be rejected or quarantined when:

- timezone is absent and cannot be established by approved source semantics;
- offset and timezone disagree;
- timestamp cannot be parsed deterministically;
- timestamp does not align to the canonical `M5` grid;
- a local-time conversion is ambiguous;
- source label meaning is unresolved.

Implementation MUST retain the original label, declared timezone, normalisation result, parser version, and rejection reason.

---
# 8. Trading-Day and Session Ownership

## 8.1 Inherited Market Rule

Crypto operates continuously under `CRYPTO_CONTINUOUS_UTC_V1`.

There is no constitutional weekend closure, exchange-wide holiday calendar, or New York/London rollover.

## 8.2 Timeframe-Specific Ownership

The UTC civil date containing the interval open owns the bar. An interval ending at UTC midnight remains owned by the preceding date because its open lies there.

`session_date` MUST equal the UTC date of canonical interval open.

## 8.3 Regional and Venue Sessions

Asia, Europe, London, New York, exchange maintenance, and venue-specific session labels MAY be retained as analytical metadata.

They MUST NOT redefine canonical ownership or interval alignment.

## 8.4 Week and Month Boundaries

- UTC week ownership begins Monday at `00:00:00Z`.
- UTC month ownership begins on calendar day one at `00:00:00Z`.
- No holiday shifts a boundary.
- Venue maintenance does not shift a boundary.
- A structural event may end one effective segment and begin another at an approved UTC instant.

---
# 9. Bar Price and Field Meaning

## 9.1 OHLC

For one canonical `M5` interval and one compatible evidence identity:

- **Open** is the first eligible source observation or provider-declared opening aggregate.
- **High** is the maximum eligible source price or provider-declared high.
- **Low** is the minimum eligible source price or provider-declared low.
- **Close** is the final eligible source observation strictly before interval end or provider-declared close.

Provider-side aggregates are accepted as provider evidence. Their internal trade-selection method is not reconstructed unless separately supplied.

## 9.2 Price Basis

Every bar MUST declare one approved price basis, such as:

- `LAST_TRADE`;
- `PROVIDER_AGGREGATE`;
- `VENUE_INDEX`;
- `MIDPOINT`;
- `BID`;
- `ASK`.

Bars with different price bases are not directly merge-compatible.

## 9.3 Venue or Aggregate Scope

Every bar MUST identify whether it represents:

- one named venue;
- a named venue set;
- a provider aggregate;
- a reference price;
- another expressly approved scope.

Matching symbols do not establish matching scope.

## 9.4 Quote Asset

Fiat and stablecoin quote assets remain distinct.

`BTCUSD`, `BTCUSDT`, and `BTCUSDC` are separate registered instruments and MUST NOT share evidence by assumption.

## 9.5 Volume

Volume is optional unless an instrument-specific authority makes it mandatory.

When present, its meaning and unit MUST be explicit: base volume, quote volume, trade count, provider aggregate volume, or another approved measure.

Zero, null, and absent are distinct states.

---
# 10. Bar Construction Authority

## 10.1 Approved Construction Source

Approved methods are:

```text
DIRECT_PROVIDER_M5
DIRECT_OPERATOR_M5
```

Twelve Data `5min` labels MUST map to aligned UTC interval opens.

## 10.2 OHLC Construction

Where derived construction is authorised:

- **Open** MUST equal the first contributor's open.
- **High** MUST equal the maximum contributor high.
- **Low** MUST equal the minimum contributor low.
- **Close** MUST equal the final contributor's close.
- **Volume** MAY equal the sum only when every contributor has the same additive volume meaning, unit, provider, venue/aggregate scope, and effective segment; otherwise volume MUST be unavailable.

Contributors MUST be sorted by canonical interval open.

## 10.3 Source Timeframe Eligibility

| Source Timeframe | Permitted | Conditions | Notes |
|---|---|---|---|
| `M1`, tick, or trade data | NO under Version 1 | Separate approved authority required | May be retained but cannot construct canonical M5 |
| `M15` or higher | NO | Downsampling cannot construct M5 | Prohibited |

## 10.4 Direct Provider Authority

Twelve Data `5min` bars are approved as direct crypto `M5` evidence only when:

- instrument and provider symbol are registered;
- base and quote assets are explicit;
- venue or aggregate scope is declared;
- request and response follow Section 12;
- provider labels map to canonical UTC interval opens;
- the row lies within a materialised effective segment;
- price and volume bases are declared;
- `CRYPTO_M5_VALIDATOR_V1` passes.

## 10.5 Direct Versus Derived Precedence

No direct-versus-derived precedence exists under Version 1 because derived M5 is not authorised.

## 10.6 Missing Source Bars

Missing direct M5 intervals remain gaps or source-unavailable states. No lower-timeframe construction candidate may be invented.

## 10.7 Cross-Provider and Cross-Scope Construction

**Allowed:** `NO`

One derived bar MUST NOT combine providers, provider symbols, venue scopes, aggregate methodologies, quote assets, price bases, networks, or incompatible effective segments.

## 10.8 Higher-Timeframe Use

Complete eligible M5 evidence MAY support approved M30, H1, and D1 construction, but only under those higher-timeframe authorities.

---
# 11. Bar Completion Authority

## 11.1 Logical Completion

A canonical `M5` interval is logically closed when:

```text
current UTC instant >= canonical interval end
```

At `14:04:59Z`, the 14:00 M5 interval is open. At `14:05:00Z`, it is logically closed.

Provider publication lag does not alter logical closure. It alters evidence freshness and acquisition status.

## 11.2 Evidence Completion

A candidate is complete only when:

- the logical interval is closed;
- it is not identified as the provider's current partial bar;
- timestamp, alignment, owner date, and effective segment validate;
- OHLC and required identity fields validate;
- provider, venue/aggregate scope, quote asset, and price basis are declared;
- direct or derived construction requirements pass;
- immutable provenance is complete.

## 11.3 Latest Expected Closed Bar

The latest expected closed `M5` interval open is:

```text
floor_UTC(current instant, 5 minutes) minus 5 minutes
```

Crypto has no weekend or holiday freeze. The latest expected interval advances continuously as UTC intervals close.

## 11.4 Status Model

| Status | Meaning |
|---|---|
| `OPEN` | Canonical interval has begun but not ended |
| `PARTIAL` | Evidence covers only part of the interval or required contributors are missing |
| `PROVISIONAL` | Interval ended but source coverage, mapping, or revision uncertainty remains |
| `CLOSED` | Interval ended and all mandatory validation passed |
| `REVISED` | New immutable comparable evidence differs from prior evidence |
| `NOT_EXPECTED` | Interval lies outside the approved effective segment or an approved exception says no bar is expected |

`OPEN`, `PARTIAL`, and `PROVISIONAL` MUST NOT be represented as the latest accepted closed bar.

## 11.5 Revision Window

No finite universal revision window is assumed.

Corrections MUST be retained as new immutable evidence and classified as exact duplicates or conflicts.

---
# 12. Request and Response Authority

## 12.1 Twelve Data Request Contract

The approved automated request uses `/time_series` with:

| Parameter | Approved Value or Rule |
|---|---|
| `symbol` | Registered Twelve Data provider symbol |
| `interval` | `5min` |
| `timezone` | `UTC` |
| `order` | `asc` |
| `format` | `JSON` |
| `start_date` | Desired first canonical interval-open datetime in UTC |
| `end_date` | Desired final canonical interval-open datetime plus 5 minutes in UTC |
| `outputsize` | MUST be omitted when both bounded dates are supplied |
| authentication | Approved secret mechanism; secret MUST NOT enter logs or evidence payloads |

For desired inclusive canonical interval opens `[S, E]`:

```text
start_date = S represented in UTC
end_date   = E + 5 minutes represented in UTC
```

The response MUST then be canonically filtered to:

```text
S <= canonical interval open <= E
```

This removes dependency on undocumented boundary inclusivity.



## 12.2 Chunk Ceiling

Twelve Data documents a maximum of 5,000 returned records.

Fragarach's constitutional ceiling is:

```text
maximum 4,000 expected M5 intervals per request
```

The default chunk span MUST NOT exceed:

```text
13 full UTC calendar days
```

and MUST be shortened where required to keep expected rows at or below 4,000.

## 12.3 Chunk Overlap

Adjacent chunks MUST overlap by at least:

```text
576 expected M5 intervals
```

Overlap provides deterministic reassembly and revision evidence.

## 12.4 Incremental Acquisition

An incremental request SHOULD begin at least `576` expected `M5` intervals before the latest accepted closed interval and continue through the interval immediately after the latest expected closed open time, followed by canonical filtering.

## 12.5 Response Semantics

An approved response MUST satisfy all of the following:

- response metadata and error status are distinguished from value rows;
- every row contains a parseable timestamp or approved daily label;
- every row maps to an aligned UTC interval open;
- ascending order is verified rather than assumed;
- numeric strings are parsed without avoidable precision loss;
- no Saturday, Sunday, or holiday rows are discarded merely because of the civil date;
- rows later than the latest expected closed interval are retained only as `OPEN` or `PARTIAL`;
- an empty successful values set means no evidence returned, not proof of market closure;
- an error payload is an acquisition failure, not an empty interval;
- a response reaching a provider row ceiling without full requested coverage is potentially truncated;
- metadata about exchange, instrument type, currency, and timezone is retained where supplied.

## 12.6 Chunk Reassembly

Chunk responses MUST be reassembled by:

1. preserving every immutable response block;
2. mapping every row to canonical UTC interval open and owner date;
3. filtering to requested canonical opens;
4. sorting ascending;
5. comparing overlap rows;
6. collapsing exact repeats only in read models while retaining provenance;
7. retaining conflicting overlap rows as conflict evidence;
8. proving requested, received, duplicate, conflict, future, and uncovered ranges.

## 12.7 Request Coverage Proof

Every acquisition run MUST record:

- instrument and provider symbol;
- base and quote assets;
- venue or aggregate scope;
- provider interval and request timezone;
- requested UTC start/end;
- expected canonical interval count;
- provider and canonical response ranges;
- returned row count;
- accepted closed count;
- open or future count;
- misaligned or invalid count;
- exact duplicate and conflict counts;
- uncovered expected intervals;
- overlap range;
- truncation risk;
- acquisition outcome;
- immutable evidence-block identity.

## 12.8 Provider Limits

Rate limits and credits are account-dependent and are not assigned a fixed constitutional number.

Implementation MUST obey configured entitlement and provider responses and expose throttling, quota, or entitlement failures as acquisition outcomes.

---
# 13. Effective Historical Range

## 13.1 Range Model

**Effective Range Start:** Instrument-, provider-, venue-scope-, and timeframe-specific
**Effective Range End:** `OPEN` unless a structural event ends the segment

There is no universal crypto `M5` start date.

## 13.2 Mandatory Materialisation

Before an evidence lane becomes `ACTIVE`, its exact effective start MUST be materialised in lane authority or an authority-linked manifest.

`UNKNOWN`, “all available”, and provider default are not valid active-lane starts.

The materialised start is the latest of:

1. registered asset or pair inception;
2. venue listing or aggregate-scope start;
3. provider-symbol mapping start;
4. Twelve Data `/earliest_timestamp` result for the registered symbol and `5min`;
5. first successfully acquired aligned compatible row;
6. network, token-contract, migration, redenomination, or quote-asset transition boundary;
7. any approved instrument/provider exception.

## 13.3 Provider-Specific Rules

| Source | Effective Start | Effective End | Rule |
|---|---|---|---|
| Twelve Data | Exact immutably recorded result of the materialisation procedure | OPEN through latest available, subject to latest-closed filtering and structural events | Earliest endpoint alone does not prove a valid aligned row |
| Operator-supplied direct file | First validated aligned row in approved manifest range | Last validated closed row or approved open end | Source, scope, timezone, timestamp meaning, quote asset, price basis, and checksum required |
| Existing accepted immutable evidence | Existing accepted first interval | Existing accepted end or OPEN through later evidence | Preserve original provenance |


## 13.4 Effective Segments

A material change creates a new effective segment when it affects:

- asset or token identity;
- chain or contract;
- wrapped, bridged, or native status;
- venue scope;
- provider aggregate methodology;
- provider symbol mapping;
- quote asset;
- price basis;
- timestamp semantics;
- redenomination or conversion factor.

Evidence across incompatible segments MUST NOT be silently treated as one homogeneous series.

## 13.5 History Acquisition

A full backfill SHALL begin at the materialised effective start and proceed in Section 12 chunks through the latest expected closed interval.

Backfill is complete only when every chunk has coverage proof and every uncovered expected interval is classified.

---
# 14. Expected Bars and Gap Authority

## 14.1 Expectedness

288 canonical `M5` intervals are expected per complete UTC day.

Every canonical interval is expected after effective start and before effective end unless an approved instrument- or venue-specific exception classifies it otherwise.

Weekend and civil holiday are never valid generic non-bar reasons.

## 14.2 Approved Non-Expected Reasons

An interval MAY be `NOT_EXPECTED` only when immutable evidence and authority establish one of:

- before pair or aggregate inception;
- after delisting, retirement, or effective-segment end;
- approved venue-specific trading halt for a venue-scoped lane;
- approved provider aggregate not yet or no longer published;
- structural event requiring a new identity or segment;
- approved sparse-market no-trade rule;
- explicit constitutional exception.

Provider outage, API failure, maintenance, or silence does not by itself make an interval `NOT_EXPECTED`.

## 14.3 Gap Definition

A gap exists when an expected closed canonical interval has no accepted complete selected bar.

Gaps MUST be classified, not hidden.

## 14.4 Gap Materiality

| Class | Distance behind latest expected closed interval | Operational Treatment |
|---|---:|---|
| `FRONTIER` | 1–576 expected intervals | Highest repair priority and prominent warning |
| `RECENT` | 577–8640 expected intervals | Repair priority and visible warning |
| `HISTORICAL` | More than 8640 expected intervals | Retain, report, and repair proportionately; do not suppress usable newer history |

Age is measured in expected canonical intervals, not wall-clock assumptions.

## 14.5 Sparse Trading

Sparse trading MUST NOT be inferred from a missing provider row.

A `NO_TRADE_CONFIRMED` classification requires an approved venue-scoped rule and supporting evidence.

No synthetic flat bar may be created unless a future authority expressly permits it.

## 14.6 Repair

Repair MAY reacquire, import, or derive evidence only through approved paths.

Repair MUST preserve prior evidence, produce a new provenance event, and never mutate accepted source blocks.

## 14.7 Non-Blocking Operation

Gaps produce visible status and repair priority.

They MUST NOT hide valid accepted bars outside the affected intervals or unnecessarily disable unrelated lanes.

---
# 15. Duplicate and Overlap Authority

## 15.1 Comparable Identity

Two rows are comparable only when they share:

- registered instrument and quote asset;
- timeframe `M5`;
- canonical interval open;
- provider and provider symbol;
- venue or aggregate scope;
- price basis;
- effective segment;
- construction method where relevant.

## 15.2 Exact Duplicate

Comparable rows are exact duplicates when canonical OHLC and all mandatory comparable fields are equal after approved parsing at declared precision.

Exact duplicates MAY collapse to one selected read-model row, but all evidence blocks and provenance MUST remain.

## 15.3 Conflict

Comparable rows that differ materially are conflicts or revisions.

They MUST be retained as separate immutable evidence and MUST NOT be resolved through `INSERT OR REPLACE`, last-write-wins, newest-response-wins, or file-order preference.

## 15.4 Overlap

Request overlap is mandatory evidence, not waste.

Overlap comparison MUST report:

- exact repeats;
- changed rows;
- missing overlap rows;
- mapping changes;
- provider metadata changes;
- effective-segment mismatches.

## 15.5 Resolution

Selection changes require an explicit auditable resolution event naming old selection, new selection, reason, authority, operator or process identity, and time.

---
# 16. Price and Volume Semantics

## 16.1 Price Meaning

A crypto `M5` OHLC bar is evidence for its declared provider, scope, quote asset, and price basis.

It is not a universal consolidated crypto market price.

## 16.2 Precision

Prices MUST be parsed and stored without avoidable precision loss.

Registration owns permitted display and validation precision. Display rounding MUST NOT alter evidence values.

Negative prices are invalid unless a named exception exists.

Zero prices are invalid unless a named technical, launch, migration, redenomination, or historical exception exists.

## 16.3 Volume Meaning

Volume MUST retain its declared unit and scope.

Base volume, quote volume, trade count, and aggregate provider volume are distinct.

Cross-venue or cross-provider volume MUST NOT be summed without separate construction authority.

## 16.4 Stablecoin Exposure

A stablecoin quote remains a cryptoasset quote.

A depeg does not convert the evidence into fiat-quoted history and does not authorise rescaling.

---
# 17. Validation Authority

## 17.1 Validator Identity

**Validator:** `CRYPTO_M5_VALIDATOR_V1`

A candidate MUST pass this validator before it becomes accepted complete evidence.

## 17.2 Mandatory Identity Validation

The validator MUST prove:

- registered instrument and market code `CRYPTO`;
- registered base and quote assets;
- network, contract, wrapped/bridged status where material;
- provider and provider symbol mapping;
- declared venue or aggregate scope;
- timeframe `M5`;
- price basis and volume basis where present;
- compatible effective segment.

## 17.3 Timestamp and Alignment Validation

The validator MUST prove:

- canonical timestamp is timezone-aware UTC;
- minute is divisible by five and second/subsecond are zero;
- interval open and end are deterministic;
- owner date equals UTC date of interval open;
- row is not later than the latest accepted closed interval unless classified `OPEN` or `PARTIAL`;
- source timestamp mapping is approved and retained.

## 17.4 Numeric and OHLC Validation

Mandatory rules include:

```text
high >= open
high >= close
low <= open
low <= close
high >= low
```

OHLC values MUST be finite and parseable.

Negative values are rejected absent an exception.

Zero values are rejected absent an exception.

## 17.5 Ordering and Duplicate Validation

Within each evidence block:

- source order MUST be observed and recorded;
- canonical order MUST be strictly increasing after duplicate classification;
- duplicates and conflicts MUST be classified under Section 15;
- unsorted input MAY be normalised only in a derived read process while preserving original source order.

## 17.6 Coverage and Completion Validation

The validator MUST determine:

- expected intervals in requested range;
- accepted complete intervals;
- open, partial, provisional, invalid, duplicate, conflict, and missing intervals;
- whether derived construction has every required contributor;
- whether response truncation is possible;
- whether effective-range and structural-event boundaries are respected.

## 17.7 Severity

| Severity | Meaning | Consequence |
|---|---|---|
| `INFO` | Valid non-error observation | Retain and report |
| `WARNING` | Non-fatal uncertainty or gap | Continue with visible warning |
| `REJECT` | Invalid affected evidence | Reject affected row/block and retain proof |
| `CONFLICT` | Compatible evidence disagrees | Retain all versions; require resolution |
| `BLOCKED` | Required authority is missing | Stop only the affected path and emit compatibility report |

## 17.8 Determinism

The same evidence, authority version, registration state, and validator version MUST produce the same validation result.

---
# 18. Evidence Lane Contract

## 18.1 Lane Identity

The minimum active lane identity includes:

```text
registered instrument
+ timeframe M5
+ provider or source
+ provider symbol
+ venue or aggregate scope
+ quote asset
+ price basis
+ effective segment
```

A selected canonical read model MAY present one resolved row per registered instrument, timeframe, and canonical timestamp, but resolution provenance MUST remain accessible.

## 18.2 Mandatory Lane Authority Fields

Before activation, lane authority MUST materialise:

- authority name and version;
- instrument registration reference;
- timeframe `M5`;
- provider/source and symbol mapping;
- venue or aggregate scope;
- base and quote assets;
- network/contract identity where material;
- price and volume bases;
- timestamp meaning and timezone;
- effective start and end;
- expectedness rule;
- validator `CRYPTO_M5_VALIDATOR_V1`;
- construction methods;
- freshness state method;
- approval and provenance.

## 18.3 Lane States

| State | Meaning |
|---|---|
| `CANDIDATE` | Registered but not approved for active serving |
| `ACTIVE` | Authority complete and accepted evidence may serve |
| `REVIEW` | Usable evidence exists but a material warning requires review |
| `SUSPENDED` | New acquisition or selection paused; accepted history remains readable |
| `RETIRED` | Effective range ended; immutable history remains |
| `BLOCKED` | Required authority missing for this lane/path |

## 18.4 Current-As-Of Truth

Each active lane MUST expose:

- latest accepted complete canonical interval open;
- corresponding interval close;
- freshness state;
- source and scope;
- evidence status;
- latest acquisition time separately;
- unresolved gap or conflict counts.

---
# 19. Operational Freshness Authority

## 19.1 Reference

Freshness is measured against the latest expected closed `M5` interval from Section 11.3.

It uses expected canonical intervals, not local dates, weekends, or raw wall-clock differences.

## 19.2 States

| State | Definition | Operational Meaning |
|---|---|---|
| `CURRENT` | Latest accepted complete interval equals latest expected closed interval | Normal operation |
| `DELAYED` | Latest accepted complete interval is exactly one expected interval behind | Continue with visible warning |
| `STALE` | Latest accepted complete interval is two or more expected intervals behind | Continue with prominent warning and repair priority |
| `UNKNOWN` | Expected or accepted latest interval cannot be determined | Display authority/evidence uncertainty; stop only affected path if authority is missing |

## 19.3 Current-As-Of Truth

The operator-facing Current-As-Of Truth is the canonical interval-open identity and close instant of the latest accepted complete selected bar.

It MUST remain distinct from:

- current wall-clock time;
- acquisition time;
- latest provider response label;
- latest open or partial interval.

## 19.4 Non-Blocking Operation

`DELAYED` and `STALE` are warnings, not reasons to hide accepted history.

Where usable evidence exists, Fragarach MUST continue to serve it with Current-As-Of Truth, freshness state, scope, and reason.

---
# 20. Provider Precedence

| Priority | Source | Role | Conditions |
|---:|---|---|---|
| 1 | Existing accepted valid selected evidence | Continuity source | Remains selected until explicit resolution changes selection |
| 2 | Twelve Data direct `5min` | Primary automated acquisition and uncovered-interval source | Contract, mapping, scope, range, and validation pass |
| 3 | Operator-supplied direct `M5` file | Manual backfill or supplementary source | Manifest, checksum, timezone, timestamp meaning, scope, quote asset, price basis, and validation required |


Priority permits acquisition and uncovered-interval filling.

It does not authorise silent replacement of conflicting accepted evidence.

No direct exchange, decentralised protocol, or other aggregate provider is approved by Version 1 of the parent doctrine.

---
# 21. Exceptions

Initial exceptions:

```text
NONE
```

A future exception MUST identify:

- instrument, provider, scope, and timeframe;
- substituted rule;
- reason and supporting evidence;
- effective start and end;
- approving authority;
- operational consequence;
- review date;
- provenance and acceptance requirements.

No undocumented exception is valid.

---
# 22. Compatibility Requirements

Before an implementation specification or lane activation proceeds, it MUST prove:

- `CRYPTO_BASE_DOCTRINE_V1` is approved;
- `CRYPTO_M5_AUTHORITY_V1` is approved;
- instrument, base asset, quote asset, and scope are registered;
- network/contract identity is resolved where material;
- provider mapping and role are valid;
- timestamp semantics are approved;
- effective segment is materialised;
- price and volume bases are explicit;
- request contract and provider limits are implemented;
- `CRYPTO_M5_VALIDATOR_V1` exists and is deterministic;
- no implementation-critical authority is missing.

Failure requires a compatibility report and stops only the affected implementation, acquisition, validation, construction, migration, or lane-activation path.

Existing accepted unrelated operations MUST remain available.

---
# 23. Specification Boundary

Specifications MAY define:

- schemas and migrations;
- provider clients and authentication boundaries;
- parser and normaliser implementation;
- chunk planner and retry orchestration;
- immutable evidence storage;
- validator code;
- derived-bar materialisation where authorised;
- native operations console workflows;
- reports, tests, checkpoints, and acceptance proof.

Specifications MUST NOT redefine:

- UTC calendar or ownership;
- `M5` duration or alignment;
- timestamp meaning;
- provider role or venue/aggregate scope;
- quote-asset identity;
- price or volume meaning;
- effective-range logic;
- expectedness, gap, duplicate, conflict, or completion rules;
- construction eligibility;
- freshness states.

---
# 24. Implementation Prohibitions

Implementation MUST NOT:

- create weekend or holiday closures;
- align crypto `M5` bars to New York, London, exchange-local midnight, or daylight-saving time;
- infer UTC daily ownership from an unresolved provider daily label;
- treat provider silence as no-trade proof or market closure;
- merge venue or provider aggregates by assumption;
- equate stablecoin and fiat quotes;
- join histories by ticker alone;
- silently bridge migration, fork, redenomination, contract, or network changes;
- silently shift timestamps;
- fabricate, interpolate, or carry forward missing bars;
- construct across providers, scopes, quote assets, or price bases;
- overwrite conflicts;
- accept open or partial bars as closed;
- operate outside materialised effective segments;
- claim acceptance without immutable provenance and validation proof.

---
# 25. Amendment and Versioning

A new authority version is required when a change affects:

- `M5` duration, alignment, or ownership;
- canonical timestamp meaning;
- provider timestamp mapping;
- direct or derived construction eligibility;
- request limits, chunking, or overlap as constitutional values;
- expectedness or sparse-trading rules;
- gap materiality;
- duplicate or conflict semantics;
- effective-range logic;
- validator requirements;
- freshness states;
- provider precedence.

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| 1.0 | 2026-07-11 | Initial crypto `M5` timeframe authority drafted | Establish constitutional authority before implementation | PENDING |

Superseded versions remain immutable and auditable.

---
# 26. Approval Gate

This authority may be marked **APPROVED** only when:

- parent doctrine approval is recorded;
- `M5` interval and UTC ownership are accepted;
- timestamp mapping is accepted;
- direct and derived construction rules are accepted;
- Twelve Data request, chunking, and response semantics are accepted;
- provider daily-label proof requirement is accepted where applicable;
- effective-range and segment rules are accepted;
- expectedness, gap, duplicate, conflict, and repair rules are accepted;
- `CRYPTO_M5_VALIDATOR_V1` is accepted;
- lane and freshness contracts are accepted;
- exceptions and approval identity are recorded.

---
# 27. Acceptance Statement

Upon approval:

> `CRYPTO_M5_AUTHORITY_V1` is the approved constitutional authority for crypto `M5` evidence in Fragarach II. Every subordinate specification, implementation, acquisition, validation, construction, migration, evidence-lane operation, and acceptance proof MUST conform to it.

---
# 28. Provider Reference Record

The provider contract in this authority was drafted against the following official Twelve Data material, reviewed on `2026-07-11`:

1. **Twelve Data API Documentation** — `/time_series`, interval values, timezone, order, response metadata, and parameter semantics.
   `https://twelvedata.com/docs`
2. **How to get historical prices** — supported intervals, `/earliest_timestamp`, bounded `start_date` and `end_date`, omission of `outputsize` for bounded requests, and the 5,000-row maximum.
   `https://support.twelvedata.com/en/articles/5656039-how-to-get-historical-prices`
3. **Getting historical data** — historical boundary behaviour and the 5,000-point per-request limit.
   `https://support.twelvedata.com/en/articles/5214728-getting-historical-data`

Constitutional provider facts used here:

- approved interval code: `5min`;
- bounded requests use `start_date` and `end_date` without `outputsize`;
- documented provider maximum: 5,000 data points;
- Fragarach operational ceiling: 4,000 expected intervals;
- `/earliest_timestamp` is used to materialise provider/timeframe coverage;
- intraday timezone is requested as UTC;
- daily timezone behaviour requires explicit mapping proof.

If provider documentation or behaviour materially changes, implementation MUST emit a compatibility report and this authority MUST be reviewed before adopting the new semantics.

---
# 29. Governing Principle

> Crypto `M5` authority is continuous, UTC-owned, identity-sensitive, scope-explicit, immutable, and non-blocking.

Provider convention may be mapped.

Implementation may encode.

Neither may invent authority.

**Operations is King.**
