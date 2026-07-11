# GERMAN EQUITIES M5 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority  
**Authority Layer:** Market Timeframe  
**Authority Name:** `GERMAN_EQUITIES_M5_AUTHORITY_V1`  
**Market Name:** German Equities  
**Market Code:** `EQUITIES_DE`  
**Timeframe:** `M5`  
**Version:** 1.0  
**Status:** DRAFT FOR APPROVAL  
**Repository Location:** `constitution/authorities/equities_de/GERMAN_EQUITIES_M5_AUTHORITY_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Authority:** `constitution/doctrines/GERMAN_EQUITIES_BASE_DOCTRINE_V1.md`  
**Effective From:** Not effective until approved  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** PENDING  
**Approval Date:** PENDING

---

# 1. Purpose

This authority defines the approved operational truth for `M5` evidence within the German Equities market ecosystem of Fragarach II.

It establishes:

- what one German-equities `M5` bar represents;
- venue and trading-system calendar and regular-session ownership;
- exact timestamp and interval semantics;
- direct-provider and approved construction rules;
- adjusted and unadjusted lane separation;
- bar completion and latest-closed-bar calculations;
- Twelve Data request, response, chunking, and history contracts;
- effective-range materialisation;
- expected-bar, halt, gap, duplicate, conflict, repair, and freshness rules;
- the `GERMAN_EQUITIES_M5_VALIDATOR_V1` validation contract;
- evidence-lane activation and operational eligibility.

This authority does not define database schemas, storage implementation, client architecture, native application layout, migration procedure, or acceptance-test code. Those matters belong to specifications that consume this authority.

---

# 2. Constitutional Position

```text
Constitution

↓

GERMAN_EQUITIES_BASE_DOCTRINE_V1

↓

GERMAN_EQUITIES_M5_AUTHORITY_V1

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides all subordinate documents;
2. `GERMAN_EQUITIES_BASE_DOCTRINE_V1` overrides this authority;
3. this authority overrides implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing operational facts.

Legacy code, provider defaults, sample files, ticker text, and historical application behaviour are not authority unless expressly adopted.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate specification may weaken a mandatory requirement defined here.

---

# 4. Document Identity and Scope

## 4.1 Authority Scope

This authority applies only to:

- securities registered under market code `EQUITIES_DE`;
- timeframe code `M5`;
- an approved German venue, MIC, trading system, and venue-session profile;
- Version 1 concrete profile `XETRA_REGULAR_CONTINUOUS_V1`;
- evidence whose provider symbol mapping, source scope, adjustment basis, timestamp meaning, and effective range are known;
- direct `M5` evidence and only the derived methods expressly permitted in Section 10.

## 4.2 Version 1 Concrete Venue Profile

The concrete session profile defined by this authority is:

```text
Venue:                 Deutsche Börse Xetra
MIC:                   XETR
Trading system:        Xetra / T7 cash market
Venue-session profile: XETRA_REGULAR_CONTINUOUS_V1
Timezone:              Europe/Berlin
Ordinary grid:         09:00–17:30 local time
Scope:                 regular continuous trading only
```

The 09:00–17:30 grid is an interval and expectation framework. It does not imply that every instrument trades at every instant.

## 4.3 Other German Venues and Services

This document does not silently assign the Xetra profile to:

- Deutsche Börse Frankfurt (`XFRA`);
- another German exchange or multilateral venue;
- Xetra early retail trading;
- Xetra late retail trading;
- opening, intraday, volatility, or closing auction-only evidence;
- Trade-at-Close;
- off-book or delayed-report evidence;
- a provider-defined German aggregate whose venue composition is unresolved.

Those paths require a separately approved venue-session profile or an effective-dated constitutional amendment.

## 4.4 Excluded Scope

This authority does not govern:

- extended-service, mixed-service, or unresolved auction-scope evidence;
- ETFs, ETPs, funds, bonds, participation certificates, warrants, subscription rights, options, futures, indices, CFDs, or OTC securities not admitted by the parent doctrine;
- foreign ordinary shares not explicitly registered under `EQUITIES_DE`;
- another timeframe;
- provider data whose MIC, trading system, venue composition, session, auction, adjustment, or timestamp semantics are unresolved;
- bars outside the approved listing, identity-segment, venue-profile, and provider effective range.

## 4.5 Inherited Market Truth

This authority inherits without modification:

- regulated multi-venue German-equities market identity;
- explicit security, share-class, ISIN, WKN, and primary-listing identity;
- explicit Xetra-versus-Frankfurt and other venue separation;
- `Europe/Berlin` calendar timezone;
- official venue and trading-system calendar authority;
- official holiday, exceptional schedule, halt, suspension, and interruption treatment;
- regular, auction, and extended-service separation;
- adjusted and unadjusted lane separation;
- corporate-action and security-continuity authority;
- immutable evidence and non-blocking operations doctrine.

---

# 5. Canonical Timeframe Definition

## 5.1 Timeframe Identity

**Timeframe Code:** `M5`  
**Nominal Duration:** Five minutes  
**Duration in Minutes:** `5`  
**Time Unit:** `MINUTE`  
**Interval Type:** `SESSION_ALIGNED`

## 5.2 Approved Definition

One canonical German-equities `M5` bar represents a half-open five-minute interval within `XETRA_REGULAR_CONTINUOUS_V1`.

Intervals begin at 09:00 Europe/Berlin and continue to the 17:30 continuous close.

## 5.3 Bar Meaning

A complete German-equities `M5` bar contains one approved Xetra continuous-source scope's OHLC and compatible volume for one registered security and adjustment basis.

A bar MAY originate through `DIRECT_PROVIDER_M5` or `DIRECT_OPERATOR_M5`.

M5 is the lowest authorised German-equities timeframe in Version 1.

## 5.4 Expected Counts

For the ordinary 09:00–17:30 Xetra continuous session:

```text
Expected M5 bars = 102
```

Exceptional counts MUST be calculated from the effective-dated venue-session profile.

---

# 6. Interval Alignment Authority

## 6.1 Alignment Origin

For `XETRA_REGULAR_CONTINUOUS_V1`:

```text
09:00:00 Europe/Berlin
```

Intervals advance in exact five-minute increments until 17:30.

## 6.2 Boundary Rule

Every interval uses `[start, end)`.

Auction and Trade-at-Close assignments are outside this continuous-only profile.

## 6.3 Alignment Formula

```text
interval_open(n) = O + n × 5 minutes
interval_end(n)  = min(O + (n + 1) × 5 minutes, C)
```

## 6.4 Ordinary Session Examples

```text
first bar = 09:00–09:05
final bar = 17:25–17:30
```

All 102 ordinary intervals are full five-minute intervals.

## 6.5 Auction Transition and No-Trade Periods

The opening auction may delay the first continuous trade beyond 09:00. The first canonical interval remains 09:00–09:05.

Authoritative phase evidence may explain no trade. Fragarach MUST NOT fabricate a bar.

## 6.6 Exceptional Schedules

The final interval ends at the approved continuous close. A shortened final interval is complete when that boundary closes.

## 6.7 Daylight-Saving Treatment

Every boundary MUST be resolved under historical IANA `Europe/Berlin` rules and converted to UTC.

## 6.8 Excluded Services

Opening or closing auctions, Trade-at-Close, early retail, late retail, Frankfurt trading, and mixed-service evidence are outside this profile.

---

# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `INTERVAL OPEN`  
**Canonical Storage Timezone:** `UTC`

The canonical timestamp is the exact UTC instant at which the approved Xetra continuous interval opens.

## 7.2 Required Companion Ownership

Every canonical row MUST also resolve:

- `session_date` in `Europe/Berlin`;
- `interval_end` in UTC;
- venue name, MIC, trading system, and venue-session profile;
- source and phase scope;
- source timezone and timestamp meaning;
- timestamp-mapping method.

## 7.3 Provider Timestamp Mapping

| Source | Source Timestamp Meaning | Source Timezone | Canonical Mapping | Conditions |
|---|---|---|---|---|
| Twelve Data `5min` | Provider intraday label proven to represent interval open | Request `Europe/Berlin` | Validate against the approved venue-session grid, then convert to UTC | Symbol, MIC/trading-system scope, phase scope, adjustment basis, and effective range MUST validate |
| Operator-supplied direct `M5` file | Declared interval open or unambiguous equivalent | MUST be declared | Convert to UTC and calculate session owner | Ambiguous labels are rejected |
| Existing accepted immutable `M5` evidence | Recorded accepted meaning | As recorded | Preserve canonical open and provenance | No silent reinterpretation |
| Derived evidence | First contributing canonical interval open | UTC | Preserve first child open | Section 10 MUST be satisfied |

## 7.4 Direct-Provider Compatibility

A direct provider row is eligible only when its labels align to the approved venue-session grid.

Rows aligned to Frankfurt, Xetra extended retail, auction phases, civil clock hours unrelated to the session profile, or an unresolved aggregate MUST NOT be forced onto the canonical grid.

## 7.5 Date-Only Values

**Date-Only Allowed:** `NO`

## 7.6 Ambiguous or Invalid Timestamps

Implementation MUST NOT guess when timezone, open-versus-close meaning, MIC, trading system, venue profile, or phase scope is unresolved.

The candidate MUST be retained as incompatible evidence and excluded from active use.

---

# 8. Trading-Day and Session Ownership

## 8.1 Owner Date

Every canonical `M5` bar is owned by the `Europe/Berlin` civil trading date of its approved venue and venue-session profile.

## 8.2 Calendar Authority

Expected sessions MUST come from the approved official venue and trading-system calendar, including effective-dated:

- non-trading days;
- shortened or exceptional schedules;
- opening, closing, or service changes;
- technical interruptions;
- venue-profile amendments.

A generic Monday-to-Friday calendar or German public-holiday list is insufficient.

## 8.3 Version 1 Session Scope

The concrete Version 1 intraday scope is `XETRA_REGULAR_CONTINUOUS_V1`.

Early Xetra retail, late Xetra retail, opening auctions, closing auctions, Trade-at-Close, Frankfurt trading, and another venue's services MUST remain separately identified and MUST NOT advance this profile's Current-As-Of Truth.

## 8.4 Venue and Aggregate Scope

Xetra evidence, Frankfurt evidence, another named-venue series, and an approved multi-venue aggregate MAY coexist only as separate lanes.

Trading-day ownership follows the lane's approved venue-session profile. A provider's generic `Germany` or `Frankfurt` label does not prove Xetra scope.

## 8.5 Security- and Venue-Specific Events

Volatility interruptions, regulatory halts, suspensions, delayed transitions from auction to continuous trading, delistings, and venue technical events require explicit evidence.

They do not authorise silent calendar mutation or fabricated prices.

---

# 9. Bar Price and Field Meaning

## 9.1 OHLC Meaning

For one approved source scope, trading system, venue-session profile, and adjustment basis:

- `open` is the first eligible price in the governed `M5` interval;
- `high` is the maximum eligible price;
- `low` is the minimum eligible price;
- `close` is the final eligible price;
- `volume` is eligible traded security-unit quantity within the same declared source scope, when supplied.

## 9.2 Source Scope

A lane MUST explicitly identify whether evidence is:

- Xetra on-book;
- Börse Frankfurt;
- another named German venue;
- an approved venue-specific licensed feed;
- an approved German multi-venue aggregate;
- another expressly approved scope.

These scopes are not interchangeable.

## 9.3 Session and Phase Scope

The concrete Version 1 canonical intraday scope is `XETRA_REGULAR_CONTINUOUS_ONLY`.

The following require separate scope identity:

- opening-auction evidence;
- intraday or volatility-auction evidence;
- closing-auction evidence;
- Trade-at-Close evidence;
- early Xetra retail;
- late Xetra retail;
- pre-trading or post-trading phases;
- mixed or unresolved provider sessions.

## 9.4 Adjustment Basis

Adjustment basis is part of lane identity. Controlled values MAY include:

- `UNADJUSTED`;
- `SPLIT_ADJUSTED`;
- `SPLIT_AND_DISTRIBUTION_ADJUSTED`;
- another approved effective-dated basis.

Adjusted and unadjusted values MUST NOT coexist in one lane or be compared as exact duplicates.

## 9.5 No-Trade Intervals

If no eligible trade occurs, Fragarach MUST NOT invent a flat OHLC bar from the previous close.

A provider-published no-trade bar MAY be retained as provider evidence only when its semantics are explicit. It remains distinguishable from an observed-trade bar.

---

# 10. Bar Construction Authority

## 10.1 Approved Methods

An M5 bar MAY be accepted through:

1. `DIRECT_PROVIDER_M5`;
2. `DIRECT_OPERATOR_M5`.

No lower-timeframe construction is authorised in Version 1.

## 10.2 Direct Evidence Contract

Direct M5 evidence MUST declare:

- registered security and identity segment;
- provider and provider symbol;
- MIC `XETR` or another separately approved MIC;
- trading system and venue-session profile;
- continuous-only phase scope;
- source scope;
- trading currency;
- price and adjustment basis;
- volume scope;
- timestamp meaning;
- effective range.

## 10.3 No Synthetic Construction

Fragarach MUST NOT construct M5 bars from ticks, quotes, snapshots, larger intervals, another venue, a CFD, an index, or a linked instrument without separate constitutional authority.

## 10.4 Forbidden Construction

Cross-provider, cross-MIC, cross-trading-system, cross-venue-profile, cross-phase, cross-source-scope, cross-adjustment, and extended-service construction are prohibited.

---

# 11. Bar Completion Authority

## 11.1 Closed M5 Bar

An M5 bar is closed only when:

1. its canonical end is at or before the approved continuous close;
2. current time is later than the interval end;
3. approved provider finalisation latency has elapsed or final status is proven;
4. validation has completed.

## 11.2 Session-End Interval

The ordinary 17:25–17:30 interval is complete at 17:30.

## 11.3 Latest Closed Bar

The latest closed M5 bar is the greatest canonical interval open whose governed interval has closed and validated.

---

# 12. Request and Response Authority

## 12.1 Twelve Data Request Contract

The approved automated request uses `/time_series` with:

| Parameter | Approved Value or Rule |
|---|---|
| `symbol` | Registered Twelve Data provider symbol |
| `interval` | `5min` |
| `timezone` | `Europe/Berlin` |
| `order` | `asc` |
| `format` | `JSON` |
| `start_date` | Desired first canonical interval-open local datetime |
| `end_date` | Desired final canonical interval-open local datetime plus the governed interval duration |
| `outputsize` | MUST be omitted when both bounded dates are supplied |
| authentication | Approved secret mechanism; secret MUST NOT enter logs or evidence payloads |

For desired inclusive canonical opens or owner dates `[S, E]`:

```text
start_date = S represented in Europe/Berlin
end_date   = E + 5 minutes represented in Europe/Berlin
```

The response MUST then be canonically filtered to the approved requested range, MIC/trading-system scope, venue-session profile, and phase scope. Boundary inclusivity MUST NOT be assumed.

A provider response MUST prove MIC, trading-system, source-scope, and phase-scope compatibility. If Frankfurt, auctions, Trade-at-Close, extended Xetra retail, or unresolved aggregate observations cannot be deterministically separated, the provider path is incompatible.

## 12.1A German Venue Compatibility Gate

A successful provider response is not active German-equities evidence until Fragarach proves:

- provider symbol to registered security mapping;
- venue name and MIC;
- Xetra versus Frankfurt or other venue scope;
- trading-system identity;
- venue-session profile;
- continuous, auction, Trade-at-Close, or extended-service phase scope;
- trading currency and adjustment basis.

A generic `Germany`, `Frankfurt`, or exchange-country label is insufficient.

## 12.2 Chunk Ceiling

Twelve Data documents a maximum of 5,000 returned records.

Fragarach's constitutional ceiling is:

```text
maximum 4,000 expected M5 intervals per request
```

The default chunk span MUST NOT exceed:

```text
50 full regular trading sessions
```

and MUST be shortened where required to remain at or below 4,000 expected rows.

## 12.3 Chunk Overlap

Adjacent chunks MUST overlap by at least:

```text
156 expected M5 intervals, equal to two normal regular sessions
```

Overlap provides deterministic reassembly, correction detection, and corporate-action boundary evidence.

## 12.4 Incremental Acquisition

An incremental request SHOULD begin at least:

```text
156 expected M5 intervals
```

before the latest accepted closed interval and continue through the interval immediately after the latest expected closed interval, followed by canonical filtering.

## 12.5 Response Semantics

An approved response MUST satisfy all of the following:

- metadata and error status are distinguished from value rows;
- symbol and exchange or venue metadata are retained where supplied;
- regular-session and extended-service scope are not silently merged;
- adjustment basis is explicit;
- ascending order is verified rather than assumed;
- numeric strings are parsed without avoidable precision loss;
- timestamps map to the approved venue calendar and session grid;
- holiday and official closure dates are not classified as gaps;
- rows later than the latest expected closed interval remain `OPEN` or `PROVISIONAL`;
- an empty successful response means no evidence returned, not proof of closure;
- an error payload is an acquisition failure, not an empty interval;
- a response reaching a row ceiling without full coverage is potentially truncated.

## 12.6 Chunk Reassembly

Chunk responses MUST be reassembled by:

1. preserving every immutable response block;
2. mapping every row to canonical timestamp and session owner;
3. filtering to the requested canonical range and venue-session-profile and phase scope;
4. sorting ascending;
5. comparing overlap rows;
6. collapsing exact repeats only in read models while retaining provenance;
7. retaining conflicting overlap rows as conflict evidence;
8. proving requested, received, duplicate, conflict, future, and uncovered ranges.

## 12.7 Request Coverage Proof

Every acquisition run MUST record:

- instrument and provider symbol;
- security and venue-and-trading-system identity;
- provider interval and request timezone;
- source venue, trading-system, or approved aggregate scope;
- venue-session-profile and phase scope;
- adjustment and price basis;
- requested local and UTC start/end;
- expected canonical interval count;
- returned and accepted counts;
- wrong-venue, wrong-phase, extended-service, future, invalid, and misaligned counts;
- duplicate and conflict counts;
- uncovered expected intervals;
- overlap range;
- truncation risk;
- acquisition outcome;
- immutable evidence-block identity.

## 12.8 Provider Limits

Rate limits and credits are account-dependent and are not assigned a fixed constitutional number.

---

# 13. Effective Historical Range

## 13.1 Lane-Specific Range

Every `M5` evidence lane MUST materialise an exact effective range for the registered security, provider symbol, registered venue and trading system, source scope, trading-system scope, venue-session profile, session scope, adjustment basis, and provider interval.

## 13.2 Effective Start

The effective start is the latest of:

- the security's approved listing or identity-segment start;
- provider mapping start;
- venue, MIC, trading-system, and venue-session-profile effective start;
- provider `M5` availability start;
- venue/session mapping start;
- adjustment-basis segment start;
- corporate-action continuity segment start;
- any approved lane restriction.

The provider's `/earliest_timestamp` result MAY inform availability but does not override registration or listing authority.

## 13.3 Effective End

The effective end is the earliest applicable:

- delisting or retirement boundary;
- ticker or security-identity segment end;
- venue-transfer boundary;
- provider mapping end;
- venue, MIC, trading-system, or venue-session-profile effective end;
- adjustment-basis segment end;
- approved operational retirement.

## 13.4 No Invented History

Fragarach MUST NOT expect evidence before the effective start or after the effective end.

Ticker reuse, relisting, mergers, reorganisations, and share-class changes require explicit segmentation rather than silent history joining.

---

# 14. Expected Bars and Gap Authority

## 14.1 Expected Set

The expected `M5` set consists of the intervals generated from the approved venue-and-trading-system regular-session schedule within the lane effective range.

## 14.2 Non-Expected Periods

The following are not gaps:

- weekends without an approved session;
- official full-market holidays;
- official exceptional closures;
- time outside the Version 1 regular session;
- periods outside the lane effective range.

## 14.3 Explained Absence

An expected interval or session MAY be classified as explained when supported by authoritative evidence of:

- market-wide halt;
- security-specific halt, volatility interruption, suspension, or delayed phase transition;
- delayed opening;
- exceptional schedule;
- delisting or retirement;
- provider-declared no-trade condition consistent with venue evidence.

Explained absence MUST remain visible and MUST NOT be converted into fabricated OHLC.

## 14.4 Gap Classification

Unexplained expected absence is `MISSING_EXPECTED_EVIDENCE`.

A missing interval is not automatically a market closure. Official halts, delayed openings, exceptional schedules, suspensions, and no-trade conditions require evidence-backed classification.

## 14.5 Non-Blocking Repair

A gap or explained absence MUST NOT blank otherwise valid operator output.

Fragarach SHALL show Current-As-Of Truth, gap status, materiality, reason, and repair state while serving the best accepted evidence.

Repair acquisition MUST preserve all raw responses and MUST NOT silently overwrite accepted bars.

---

# 15. Duplicate and Overlap Authority

## 15.1 Exact Duplicate

Rows are exact duplicates only when canonical identity, timestamp, OHLC, volume, venue, trading-system, or approved aggregate scope, session scope, adjustment basis, and relevant provenance values agree.

## 15.2 Conflict

Rows sharing canonical lane identity and timestamp but differing materially are conflicts, not duplicates.

Conflicts MUST remain visible with both immutable source records.

## 15.3 Overlap

Acquisition overlap is mandatory evidence. Exact repeats MAY collapse in read models but MUST NOT be deleted from immutable provenance.

## 15.4 Corporate-Action Boundaries

Apparent price conflicts across splits, dividends, mergers, ticker changes, or security-identity boundaries MUST be evaluated against the registered effective segment and adjustment basis.

Fragarach MUST NOT resolve them by choosing the numerically smoother series.

## 15.5 Correction Precedence

A later correction may supersede an earlier active value only through an approved deterministic precedence rule. The earlier evidence remains immutable.

---

# 16. Price and Volume Semantics

## 16.1 Trading Currency

Prices MUST remain in the registered trading currency unless a separately authorised conversion lane exists.

Euro denomination MUST NOT be inferred merely from issuer domicile, venue, ticker, ISIN, or provider metadata.

## 16.2 Price Basis

Xetra on-book trade, Frankfurt price, official auction, Trade-at-Close, venue-specific, approved aggregate, adjusted, and unadjusted price bases MUST remain explicit and compatible with the lane contract.

## 16.3 Volume

Volume means eligible traded security units within the declared venue, trading-system, phase, and source scope.

Xetra on-book volume, Frankfurt volume, off-book reports, approved aggregate volume, turnover value, and provider-estimated volume are not interchangeable.

Volume MUST be `NULL` when unavailable or semantically incompatible. It MUST NOT be replaced with zero merely to satisfy a schema.

## 16.4 Corporate Actions

Subdivision, consolidation, dividend, distribution, capital increase or reduction, subscription right, demerger, merger, squeeze-out, insolvency restructuring, delisting, identifier change, and other corporate-action effects MUST remain governed by explicit adjustment and identity authority.

Timeframe construction alone does not authorise adjustment.

## 16.5 Precision

Decimal values MUST be preserved without avoidable binary floating-point loss. Rounding is permitted only at approved presentation or storage precision boundaries and MUST NOT alter source evidence.

---

# 17. Validation Authority

## 17.1 Validator Identity

The mandatory validator is:

```text
GERMAN_EQUITIES_M5_VALIDATOR_V1
```

## 17.2 Mandatory Checks

The validator MUST prove:

- registered security identity and active ISIN/WKN/ticker segment;
- market code `EQUITIES_DE` and timeframe `M5`;
- venue name, MIC, trading system, and venue-session profile;
- provider symbol and source scope;
- continuous-only phase scope for `XETRA_REGULAR_CONTINUOUS_V1`;
- auction, Trade-at-Close, Frankfurt, and extended-retail exclusion;
- timestamp meaning and Europe/Berlin timezone mapping;
- interval open and end match the approved session-derived grid;
- any session-end shortened interval ends exactly at the approved close;
- OHLC numeric validity: `low <= open <= high`, `low <= close <= high`, and `low <= high`;
- price precision and trading-currency consistency;
- adjustment-basis consistency;
- non-negative volume when volume is present;
- monotonic canonical ordering;
- duplicate and conflict classification;
- effective-range membership;
- closed, open, provisional, or corrected state;
- immutable evidence and acquisition provenance;
- no silent venue, phase, or corporate-action transformation.

## 17.3 Negative Prices

Negative equity prices are invalid under this authority and MUST be rejected from active use while evidence is retained.

## 17.4 Validation Outcome

The validator MUST produce a deterministic result containing:

- status;
- reason codes;
- accepted and rejected counts;
- first and latest accepted closed intervals;
- duplicate and conflict counts;
- missing and explained-absence counts;
- venue, trading-system, phase, source, adjustment, and session-scope summary;
- Current-As-Of Truth;
- compatibility findings.

Validation failure blocks only the affected candidate or lane.

---

# 18. Evidence Lane Contract

## 18.1 Mandatory Lane Identity

An active `M5` lane MUST bind at least:

- registered instrument identity and effective identity segment;
- market `EQUITIES_DE`;
- timeframe `M5`;
- venue name and MIC;
- trading system;
- venue-session profile;
- provider and provider symbol;
- source venue or approved aggregate scope;
- phase scope;
- price basis;
- adjustment basis;
- trading currency;
- timestamp meaning;
- construction method;
- effective range;
- validator `GERMAN_EQUITIES_M5_VALIDATOR_V1`;
- approval and activation state.

## 18.2 Activation Gate

A lane may become active only when:

1. instrument registration is approved;
2. provider mapping, MIC, trading system, and source scope are approved;
3. venue calendar and venue-session profile resolve;
4. phase and adjustment scope are explicit;
5. effective start is materialised;
6. timestamp mapping passes validation;
7. evidence provenance is immutable;
8. latest accepted closed interval is known;
9. compatibility blockers are absent for that lane.

## 18.3 Read Contract

Consumers MUST be able to read:

- best accepted bars;
- Current-As-Of Truth;
- freshness state;
- source, venue, trading-system, venue-profile, phase, and adjustment scope;
- gap and explained-absence status;
- conflict and correction status;
- effective range;
- validator result.

Maintenance state MUST NOT hide otherwise usable evidence.

---

# 19. Operational Freshness Authority

## 19.1 Current-As-Of Truth

Current-As-Of Truth is the end instant of the latest accepted closed `M5` bar, together with its source, venue-session profile, phase scope, and validation state.

## 19.2 Freshness States

Implementations MAY expose controlled states such as:

- `GREEN` — latest expected closed interval accepted;
- `AMBER` — usable evidence exists but the live edge is delayed, provisional, or under repair;
- `RED` — no usable accepted evidence for the lane;
- `CLOSED` — the approved venue-session profile is outside its expected operating interval.

`AMBER` remains usable. Warnings MUST NOT blank accepted history.

## 19.3 Expected Live Edge

The expected latest closed interval MUST be calculated from:

- approved venue and trading-system calendar;
- venue-session profile for the trading date;
- current `Europe/Berlin` time;
- interval boundaries under Section 6;
- approved provider finalisation latency;
- effective-dated exceptional venue events.

## 19.4 Non-Blocking Doctrine

Repair, provider failure, stale live edge, missing recent bars, and unresolved lower-priority conflicts remain visible but MUST NOT block unrelated lanes or historical reads.

---

# 20. Provider Precedence

## 20.1 Precedence Classes

Where multiple compatible candidates exist, deterministic precedence SHOULD favour:

1. approved official venue or licensed venue-specific evidence;
2. approved direct provider evidence with exact MIC, trading-system, venue-session-profile, source-scope, session-scope, and adjustment compatibility;
3. approved operator-supplied direct evidence;
4. approved derived evidence from complete lower-timeframe contributors.

## 20.2 No Silent Preference

Precedence MUST NOT be inferred from arrival order, longest history, numerical smoothness, highest volume, a generic `Germany` label, provider popularity, or an assumption that Xetra always overrides another authorised lane.

## 20.3 Scope Compatibility

Precedence applies only among candidates with the same security identity, MIC, trading system, venue-session profile, source scope, phase scope, adjustment basis, currency, timeframe, and effective segment.

---

# 21. Exceptions

Any exception MUST be:

- named;
- effective-dated;
- scoped to specific instruments, MICs, trading systems, venue-session profiles, providers, phases, or dates;
- justified by evidence;
- approved at the correct authority layer;
- testable;
- visible to operators.

Examples include non-trading days, exceptional venue schedules, technical interruptions, volatility interruptions, delayed auction transitions, suspensions, ticker or identifier changes, corporate-action segments, first or last trading days, and provider timestamp deviations.

A recurring exception indicates that this authority or its venue-session profile requires amendment.

---

# 22. Compatibility Requirements

Before implementation or activation, Fragarach MUST prove compatibility for:

- registered security, share class, ISIN/WKN segment, and listing identity;
- venue name, MIC, trading system, and venue-session profile;
- official calendar and phase schedule;
- provider symbol and exchange mapping;
- regular continuous-session isolation;
- auction and extended-service exclusion;
- timestamp semantics and alignment;
- source venue or approved aggregate scope;
- trading currency, adjustment basis, and price basis;
- corporate-action segment;
- effective range;
- request coverage and provider limits;
- validator availability.

If any material fact is unresolved, the affected implementation path SHALL stop with a compatibility report.

This is correct constitutional behaviour. Other approved operations continue.

---

# 23. Specification Boundary

Subordinate specifications MAY define:

- schema and migration mechanics;
- acquisition clients and retry behaviour;
- immutable evidence storage;
- validator implementation;
- read-model projection;
- native application workflow;
- repair scheduling;
- acceptance tests.

They MUST consume, not redefine:

- market and security identity;
- venue, MIC, trading-system, and venue-session-profile identity;
- calendar and phase ownership;
- regular continuous-session boundaries;
- interval alignment;
- timestamp meaning;
- phase, source, and adjustment scope;
- provider request semantics;
- effective-range rules;
- validation requirements.

---

# 24. Implementation Prohibitions

Implementation MUST NOT:

- invent a venue, MIC, trading system, or venue-session profile;
- infer security identity solely from ticker text;
- treat a generic `Germany`, `Frankfurt`, or `DE` provider label as proof of Xetra scope;
- merge Xetra, Frankfurt, another venue, or a multi-venue aggregate silently;
- merge regular continuous trading, auctions, Trade-at-Close, or extended Xetra retail silently;
- mix adjusted and unadjusted bars;
- create corporate-action adjustments without authority;
- fabricate no-trade bars;
- fill gaps with previous closes;
- force provider timestamps onto an incompatible grid;
- treat official non-trading days or approved phase interruptions as ordinary gaps;
- silently overwrite conflicting evidence;
- join histories across ticker, ISIN, WKN, share-class, or identity changes;
- expose secrets in logs or evidence;
- block unrelated operations because one lane is incompatible.

---

# 25. Amendment and Versioning

A new major version is required when changing:

- venue-session-profile and phase scope;
- timestamp meaning;
- interval alignment;
- adjustment doctrine;
- provider interpretation;
- construction eligibility;
- effective-range semantics;
- validator contract;
- evidence-lane identity.

Clarifications that do not change operational truth MAY use a minor version.

Approved amendments MUST identify superseded authority and effective ranges. Historical evidence remains interpretable under the authority effective when it was accepted.

---

# 26. Approval Gate

This authority is not effective until:

- reviewed against `GERMAN_EQUITIES_BASE_DOCTRINE_V1`;
- tested with representative Xetra-listed securities;
- tested against MIC `XETR` and explicit rejection of unresolved `XFRA` or generic-Germany mappings;
- tested across ordinary sessions, official non-trading days, and exceptional schedules;
- tested across Europe/Berlin daylight-saving offsets;
- tested with continuous-trading, auction, Trade-at-Close, and extended-retail evidence kept separate;
- tested with adjusted and unadjusted evidence kept separate;
- tested across ticker, ISIN, WKN, and corporate-action boundaries;
- approved by the constitutional authority owner;
- recorded with approval date and effective date.

Until then, status remains `DRAFT FOR APPROVAL`.

---

# 27. Acceptance Statement

Approval of `GERMAN_EQUITIES_M5_AUTHORITY_V1` means Fragarach II accepts this document as the constitutional source of truth for German Equities `M5` evidence under the approved venue-session profiles defined herein.

After approval:

- specifications SHALL consume it;
- validators SHALL enforce it;
- evidence lanes SHALL reference it;
- implementations SHALL conform to it;
- acceptance proofs SHALL demonstrate conformance;
- missing authority SHALL NOT be invented.

---

# 28. Provider Reference Record

The Version 1 authority was drafted against the following external provider and venue records as checked on 2026-07-11:

- Deutsche Börse official trading-calendar and trading-hours records: Xetra regular trading Monday to Friday from 09:00 to 17:30 Europe/Berlin, with opening and closing auction schedules and official non-trading days;
- Deutsche Börse Xetra Extended Retail Service records: early retail trading from 08:00 to 08:55 and late retail trading after the closing process to 22:00, effective from the approved service date and kept outside `XETRA_REGULAR_CONTINUOUS_V1`;
- Deutsche Börse records distinguishing Xetra (`XETR`) from Börse Frankfurt (`XFRA`) and its generally different trading hours;
- Twelve Data API documentation: `/time_series`, interval `5min`, bounded date requests, ascending order, timezone selection, `/earliest_timestamp`, and documented maximum response size of 5,000 records.

These references describe external interfaces and schedules. They do not override this authority, the parent doctrine, registered instrument metadata, venue-session profiles, or effective-dated venue calendar records.

Provider behaviour that differs from the approved contract is a compatibility event, not permission for implementation to reinterpret authority.

---

# 29. Governing Principle

> Constitution defines what is true.  
> Authority defines the approved operational meaning.  
> Specification defines how Fragarach implements that meaning.  
> Implementation must never invent authority.

**Operations is King.**
