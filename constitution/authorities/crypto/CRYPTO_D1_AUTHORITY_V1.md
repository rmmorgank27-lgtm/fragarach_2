# CRYPTO D1 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority
**Authority Layer:** Market Timeframe
**Authority Name:** `CRYPTO_D1_AUTHORITY_V1`
**Market Name:** Cryptoassets
**Market Code:** `CRYPTO`
**Timeframe:** `D1`
**Version:** 1.0
**Status:** APPROVED
**Repository Location:** `constitution/authorities/crypto/CRYPTO_D1_AUTHORITY_V1.md`
**Governing Constitution:** `constitution/CONSTITUTION.md`
**Parent Authority:** `constitution/doctrines/CRYPTO_BASE_DOCTRINE_V1.md`
**Effective From:** 2026-07-11
**Effective Until:** OPEN
**Supersedes:** NONE
**Approved By:** Ray Morgan
**Approval Date:** 2026-07-11

---
# 1. Purpose

This authority defines the approved operational truth for `D1` evidence within the Cryptoasset market ecosystem of Fragarach II.

It establishes:

- what one crypto `D1` bar represents;
- canonical UTC interval alignment and ownership;
- canonical timestamp meaning;
- continuous 24×7 expectedness;
- direct provider evidence and approved lower-timeframe construction;
- bar completion and latest-closed-bar rules;
- Twelve Data request and response semantics;
- provider, venue-scope, quote-asset, and price-basis requirements;
- exact effective-range determination;
- gap, duplicate, overlap, revision, conflict, and repair rules;
- the `CRYPTO_D1_VALIDATOR_V1` validation contract;
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

CRYPTO_D1_AUTHORITY_V1

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
- timeframe code `D1`;
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
- any timeframe other than `D1`.

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

**Timeframe Code:** `D1`
**Nominal Duration:** One UTC calendar day
**Time Unit:** `DAY`
**Interval Type:** `CALENDAR-DERIVED`

## 5.2 Approved Definition

For each UTC civil date `D`:

```text
interval start = D at 00:00:00 UTC
interval end   = D + 1 calendar day at 00:00:00 UTC
interval owner = D
```

The canonical interval is `[start, end)`.

An event exactly at `00:00:00 UTC` belongs to the new UTC day.

## 5.3 Bar Meaning

A complete crypto `D1` bar contains the approved provider's declared OHLC for one canonical interval within one declared venue or aggregate scope and one declared price basis.

A bar MAY originate from an approved direct provider aggregation or an approved Fragarach-side rollup.

Direct and derived evidence are not assumed to be numerically identical.

The origin and construction method MUST remain explicit in provenance.

There is no constitutional regular-hours versus extended-hours split for spot crypto under this authority.

## 5.4 Elapsed Duration

A UTC day is exactly 24 hours under this Version 1 authority. Daylight-saving rules do not alter duration because the canonical calendar is UTC.

Implementation MUST NOT anchor crypto intervals to a local exchange timezone or create daylight-saving gaps or duplicates.

---
# 6. Interval Alignment Authority

## 6.1 Alignment Origin

**Approved Alignment Origin:** UTC Unix-time grid, with UTC midnight as the civil-day origin.

`D1` intervals align to 00:00:00 UTC at the beginning of each UTC civil date.

## 6.2 Boundary Rule

Every interval uses:

```text
[start, end)
```

An observation exactly at `end` belongs to the next interval.

## 6.3 Alignment Formula

```text
interval_open = UTC midnight of owner_date
interval_end  = interval_open + 1 UTC calendar day
```

Canonical calculations MUST use timezone-aware UTC instants.

## 6.4 Session, Day, Week, and Month Crossing

A D1 interval MUST NOT cross a UTC day boundary. It may cross every regional civil-day or exchange-local boundary, but those boundaries have no constitutional ownership effect.

The UTC week begins Monday at 00:00 UTC. The UTC month begins on the first calendar date at 00:00 UTC.

## 6.5 Partial Intervals

A shortened or incomplete interval caused by instrument launch, pair listing, delisting, venue halt, provider outage, network interruption, acquisition interruption, or incomplete source coverage MUST NOT be silently promoted to a complete canonical bar.

Such evidence MAY be retained as `PARTIAL` or `PROVISIONAL` with visible provenance.

No holiday, weekend, or daylight-saving exception is permitted merely because a provider omitted rows.

---
# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `INTERVAL OPEN`
**Canonical Storage Timezone:** `UTC`

Every accepted canonical `D1` bar MUST be identified by the UTC instant at which its interval begins.

The canonical textual representation is RFC 3339 UTC:

```text
YYYY-MM-DDTHH:MM:SSZ
```

## 7.2 Provider Timestamp Mapping

| Provider | Provider Timestamp Meaning | Provider Timezone | Canonical Mapping | Notes |
|---|---|---|---|---|
| Twelve Data | Provider interval label, accepted as interval open only under this contract | UTC request; daily mapping additionally verified | Parse, normalise to UTC, prove alignment, retain source label | Twelve Data documents that the timezone parameter may be ignored for daily intervals. Therefore a direct `1day` lane additionally requires a materialised provider mapping proving that the returned date labels represent UTC crypto days for the registered symbol and scope. |
| Operator-supplied file | Declared by manifest | Declared by manifest | Convert to UTC only under declared unambiguous mapping | Guessing is prohibited |
| Existing immutable evidence | Original accepted meaning | Original accepted timezone | Preserve accepted canonical identity | No silent remapping |

## 7.3 Date-Only Values

**Date-Only Allowed:** `CONDITIONAL`

A date-only value is valid only for a direct D1 source whose approved mapping states that the date is the UTC owner date.

It MUST map to:

```text
YYYY-MM-DDT00:00:00Z
```

Date-only values from a provider whose daily timezone or owner-date meaning is unresolved MUST NOT be activated.

## 7.4 Ambiguous, Invalid, or Repeated Local Timestamps

Crypto canonical timestamps are UTC and therefore do not have daylight-saving folds or gaps.

A source timestamp MUST be rejected or quarantined when:

- timezone is absent and cannot be established by approved source semantics;
- offset and timezone disagree;
- timestamp cannot be parsed deterministically;
- timestamp does not align to the canonical `D1` grid;
- a local-time conversion is ambiguous;
- source label meaning is unresolved.

Implementation MUST retain the original label, declared timezone, normalisation result, parser version, and rejection reason.

---
# 8. Trading-Day and Session Ownership

## 8.1 Inherited Market Rule

Crypto operates continuously under `CRYPTO_CONTINUOUS_UTC_V1`.

There is no constitutional weekend closure, exchange-wide holiday calendar, or New York/London rollover.

## 8.2 Timeframe-Specific Ownership

The UTC civil date at interval open owns the D1 bar.

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

For one canonical `D1` interval and one compatible evidence identity:

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
DIRECT_PROVIDER_D1
DIRECT_OPERATOR_D1
DERIVED_D1
```

For direct Twelve Data `1day` evidence, the provider daily-label mapping MUST prove UTC owner-date semantics for the registered symbol and scope.

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
| `H1` | YES | Exactly 24 aligned, closed, compatible contributors; one provider/scope/price basis/effective segment | Full provenance required |
| `M30` | YES | Exactly 48 aligned, closed, compatible contributors; one provider/scope/price basis/effective segment | Full provenance required |
| `M5` | YES | Exactly 288 aligned, closed, compatible contributors; one provider/scope/price basis/effective segment | Full provenance required |
| Any higher timeframe | NO | Downsampling cannot construct a lower timeframe | Prohibited |

## 10.4 Direct Provider Authority

Twelve Data `1day` bars are approved as direct crypto `D1` evidence only when:

- instrument and provider symbol are registered;
- base and quote assets are explicit;
- venue or aggregate scope is declared;
- request and response follow Section 12;
- provider labels map to canonical UTC interval opens;
- the row lies within a materialised effective segment;
- price and volume bases are declared;
- `CRYPTO_D1_VALIDATOR_V1` passes.

## 10.5 Direct Versus Derived Precedence

Existing selected accepted evidence remains selected until an explicit resolution changes selection.

Direct Twelve Data `1day` evidence is the primary automated acquisition source.

Complete derived `D1` evidence MAY fill uncovered intervals or provide verification, but MUST NOT silently replace conflicting direct evidence.

## 10.6 Missing Source Bars

A derived target bar is `CLOSED` only when every expected contributor is present, closed, valid, aligned, and compatible.

Missing contributors make the derived target `PARTIAL` or unavailable.

No-price carry-forward, interpolation, synthetic flat bar, or cross-provider fill is authorised.

## 10.7 Cross-Provider and Cross-Scope Construction

**Allowed:** `NO`

One derived bar MUST NOT combine providers, provider symbols, venue scopes, aggregate methodologies, quote assets, price bases, networks, or incompatible effective segments.

## 10.8 Higher-Timeframe Use

Complete eligible `D1` evidence MAY support construction of approved higher timeframes, subject to those authorities.

---
# 11. Bar Completion Authority

## 11.1 Logical Completion

A canonical `D1` interval is logically closed when:

```text
current UTC instant >= canonical interval end
```

At `2026-07-11T23:59:59Z`, the 2026-07-11 D1 interval is open. At `2026-07-12T00:00:00Z`, it is logically closed.

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

The latest expected closed `D1` interval open is:

```text
UTC midnight of the current UTC civil date minus one calendar day
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
| `interval` | `1day` |
| `timezone` | `UTC` |
| `order` | `asc` |
| `format` | `JSON` |
| `start_date` | Desired first UTC owner date at 00:00:00 UTC |
| `end_date` | UTC civil day after the final requested owner date at 00:00:00 UTC |
| `outputsize` | MUST be omitted when both bounded dates are supplied |
| authentication | Approved secret mechanism; secret MUST NOT enter logs or evidence payloads |

For desired inclusive canonical interval opens `[S, E]`:

```text
start_date = S represented in UTC
end_date   = E + one UTC calendar day represented in UTC
```

The response MUST then be canonically filtered to:

```text
S <= canonical interval open <= E
```

This removes dependency on undocumented boundary inclusivity.

Twelve Data documentation states that timezone selection may be ignored for daily intervals and daily values may follow exchange-local conventions. Therefore, `timezone=UTC` is requested for consistency but is not sufficient proof. An active direct D1 mapping MUST separately prove that returned labels map to UTC owner dates.

## 12.2 Chunk Ceiling

Twelve Data documents a maximum of 5,000 returned records.

Fragarach's constitutional ceiling is:

```text
maximum 4,000 expected D1 intervals per request
```

The default chunk span MUST NOT exceed:

```text
3,650 full UTC calendar days
```

and MUST be shortened where required to keep expected rows at or below 4,000.

## 12.3 Chunk Overlap

Adjacent chunks MUST overlap by at least:

```text
2 expected D1 intervals
```

Overlap provides deterministic reassembly and revision evidence.

## 12.4 Incremental Acquisition

An incremental request SHOULD begin at least `7` expected `D1` intervals before the latest accepted closed interval and continue through the interval immediately after the latest expected closed open time, followed by canonical filtering.

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

There is no universal crypto `D1` start date.

## 13.2 Mandatory Materialisation

Before an evidence lane becomes `ACTIVE`, its exact effective start MUST be materialised in lane authority or an authority-linked manifest.

`UNKNOWN`, “all available”, and provider default are not valid active-lane starts.

The materialised start is the latest of:

1. registered asset or pair inception;
2. venue listing or aggregate-scope start;
3. provider-symbol mapping start;
4. Twelve Data `/earliest_timestamp` result for the registered symbol and `1day`;
5. first successfully acquired aligned compatible row;
6. network, token-contract, migration, redenomination, or quote-asset transition boundary;
7. any approved instrument/provider exception.

## 13.3 Provider-Specific Rules

| Source | Effective Start | Effective End | Rule |
|---|---|---|---|
| Twelve Data | Exact immutably recorded result of the materialisation procedure | OPEN through latest available, subject to latest-closed filtering and structural events | Earliest endpoint alone does not prove a valid aligned row |
| Operator-supplied direct file | First validated aligned row in approved manifest range | Last validated closed row or approved open end | Source, scope, timezone, timestamp meaning, quote asset, price basis, and checksum required |
| Existing accepted immutable evidence | Existing accepted first interval | Existing accepted end or OPEN through later evidence | Preserve original provenance |
| Derived evidence | Latest source-lane effective start rounded to the first fully covered `D1` interval | Latest fully covered target interval | Source authorities and complete compatible contributors required |

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

1 canonical `D1` interval is expected per complete UTC day.

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
| `FRONTIER` | 1–7 expected intervals | Highest repair priority and prominent warning |
| `RECENT` | 8–30 expected intervals | Repair priority and visible warning |
| `HISTORICAL` | More than 30 expected intervals | Retain, report, and repair proportionately; do not suppress usable newer history |

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
- timeframe `D1`;
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

A crypto `D1` OHLC bar is evidence for its declared provider, scope, quote asset, and price basis.

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

**Validator:** `CRYPTO_D1_VALIDATOR_V1`

A candidate MUST pass this validator before it becomes accepted complete evidence.

## 17.2 Mandatory Identity Validation

The validator MUST prove:

- registered instrument and market code `CRYPTO`;
- registered base and quote assets;
- network, contract, wrapped/bridged status where material;
- provider and provider symbol mapping;
- declared venue or aggregate scope;
- timeframe `D1`;
- price basis and volume basis where present;
- compatible effective segment.

## 17.3 Timestamp and Alignment Validation

The validator MUST prove:

- canonical timestamp is timezone-aware UTC;
- timestamp is exactly `00:00:00Z`;
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
+ timeframe D1
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
- timeframe `D1`;
- provider/source and symbol mapping;
- venue or aggregate scope;
- base and quote assets;
- network/contract identity where material;
- price and volume bases;
- timestamp meaning and timezone;
- effective start and end;
- expectedness rule;
- validator `CRYPTO_D1_VALIDATOR_V1`;
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

Freshness is measured against the latest expected closed `D1` interval from Section 11.3.

It uses expected canonical intervals, not local dates, weekends, or raw wall-clock differences.

## 19.2 States

| State | Definition | Operational Meaning |
|---|---|---|
| `CURRENT` | Latest accepted complete interval equals latest expected closed interval | Normal operation |
| `DELAYED` | Latest accepted complete interval is exactly one expected interval behind | Continue with visible warning |
| `STALE` | Latest accepted complete interval is two or more expected intervals behind | Continue with prominent warning and repair priority |
| `UNKNOWN` | Expected or accepted latest interval cannot be determined | Display authority/evidence uncertainty; stop only affected path if authority is missing |

## 19.3 Current-As-Of Truth

The operator-facing Current-As-Of Truth is the owner date and canonical close instant of the latest accepted complete selected bar.

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
| 2 | Twelve Data direct `1day` | Primary automated acquisition and uncovered-interval source | Contract, mapping, scope, range, and validation pass |
| 3 | Operator-supplied direct `D1` file | Manual backfill or supplementary source | Manifest, checksum, timezone, timestamp meaning, scope, quote asset, price basis, and validation required |
| 4 | Complete derived `D1` evidence | Uncovered-interval or verification source | Section 10 permits; one provider/scope/price basis and complete contributors |

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
- `CRYPTO_D1_AUTHORITY_V1` is approved;
- instrument, base asset, quote asset, and scope are registered;
- network/contract identity is resolved where material;
- provider mapping and role are valid;
- timestamp semantics are approved;
- effective segment is materialised;
- price and volume bases are explicit;
- request contract and provider limits are implemented;
- `CRYPTO_D1_VALIDATOR_V1` exists and is deterministic;
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
- `D1` duration or alignment;
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
- align crypto `D1` bars to New York, London, exchange-local midnight, or daylight-saving time;
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

- `D1` duration, alignment, or ownership;
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
| 1.0 | 2026-07-11 | Initial crypto `D1` timeframe authority drafted | Establish constitutional authority before implementation | PENDING |

Superseded versions remain immutable and auditable.

---
# 26. Approval Gate

This authority may be marked **APPROVED** only when:

- parent doctrine approval is recorded;
- `D1` interval and UTC ownership are accepted;
- timestamp mapping is accepted;
- direct and derived construction rules are accepted;
- Twelve Data request, chunking, and response semantics are accepted;
- provider daily-label proof requirement is accepted where applicable;
- effective-range and segment rules are accepted;
- expectedness, gap, duplicate, conflict, and repair rules are accepted;
- `CRYPTO_D1_VALIDATOR_V1` is accepted;
- lane and freshness contracts are accepted;
- exceptions and approval identity are recorded.

---
# 27. Acceptance Statement

Upon approval:

> `CRYPTO_D1_AUTHORITY_V1` is the approved constitutional authority for crypto `D1` evidence in Fragarach II. Every subordinate specification, implementation, acquisition, validation, construction, migration, evidence-lane operation, and acceptance proof MUST conform to it.

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

- approved interval code: `1day`;
- bounded requests use `start_date` and `end_date` without `outputsize`;
- documented provider maximum: 5,000 data points;
- Fragarach operational ceiling: 4,000 expected intervals;
- `/earliest_timestamp` is used to materialise provider/timeframe coverage;
- intraday timezone is requested as UTC;
- daily timezone behaviour requires explicit mapping proof.

If provider documentation or behaviour materially changes, implementation MUST emit a compatibility report and this authority MUST be reviewed before adopting the new semantics.

---
# 29. Governing Principle

> Crypto `D1` authority is continuous, UTC-owned, identity-sensitive, scope-explicit, immutable, and non-blocking.

Provider convention may be mapped.

Implementation may encode.

Neither may invent authority.

**Operations is King.**
