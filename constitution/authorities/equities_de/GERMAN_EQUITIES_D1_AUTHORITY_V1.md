# GERMAN EQUITIES D1 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority  
**Authority Layer:** Market Timeframe  
**Authority Name:** `GERMAN_EQUITIES_D1_AUTHORITY_V1`  
**Market Name:** German Equities  
**Market Code:** `EQUITIES_DE`  
**Timeframe:** `D1`  
**Version:** 1.0  
**Status:** APPROVED  
**Repository Location:** `constitution/authorities/equities_de/GERMAN_EQUITIES_D1_AUTHORITY_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Authority:** `constitution/doctrines/GERMAN_EQUITIES_BASE_DOCTRINE_V1.md`  
**Effective From:** 2026-07-11  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** Ray Morgan  
**Approval Date:** 2026-07-11

---

# 1. Purpose

This authority defines the approved operational truth for `D1` evidence within the German Equities market ecosystem of Fragarach II.

It establishes:

- what one German-equities `D1` bar represents;
- venue and trading-system calendar and regular-session ownership;
- exact timestamp and interval semantics;
- direct-provider and approved construction rules;
- adjusted and unadjusted lane separation;
- bar completion and latest-closed-bar calculations;
- Twelve Data request, response, chunking, and history contracts;
- effective-range materialisation;
- expected-bar, halt, gap, duplicate, conflict, repair, and freshness rules;
- the `GERMAN_EQUITIES_D1_VALIDATOR_V1` validation contract;
- evidence-lane activation and operational eligibility.

This authority does not define database schemas, storage implementation, client architecture, native application layout, migration procedure, or acceptance-test code. Those matters belong to specifications that consume this authority.

---

# 2. Constitutional Position

```text
Constitution

↓

GERMAN_EQUITIES_BASE_DOCTRINE_V1

↓

GERMAN_EQUITIES_D1_AUTHORITY_V1

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
- timeframe code `D1`;
- an approved German venue, MIC, trading system, and venue-session profile;
- Version 1 concrete profile `XETRA_REGULAR_CONTINUOUS_V1`;
- evidence whose provider symbol mapping, source scope, adjustment basis, timestamp meaning, and effective range are known;
- direct `D1` evidence and only the derived methods expressly permitted in Section 10.

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

**Timeframe Code:** `D1`  
**Nominal Duration:** One approved venue trading session  
**Duration in Minutes:** `SESSION-DEFINED`  
**Time Unit:** `TRADING_SESSION`  
**Interval Type:** `SESSION_DEFINED`

## 5.2 Approved Definition

One canonical German-equities `D1` bar represents one approved venue-session-profile trading date for one registered security and one declared source, phase, and adjustment scope.

For `XETRA_REGULAR_CONTINUOUS_V1`, the ordinary governed continuous-trading interval is:

```text
[09:00:00 Europe/Berlin, 17:30:00 Europe/Berlin)
```

The session date and schedule are controlled by the official Xetra calendar and effective-dated venue profile.

The D1 bar is owned by the Xetra local trading date. It is not a midnight-to-midnight civil-day bar.

## 5.3 D1 Scope Classes

Version 1 permits distinct D1 lanes such as:

- `XETRA_REGULAR_CONTINUOUS_ONLY`;
- `XETRA_AUCTION_INCLUSIVE_DIRECT`, only when the direct source proves auction semantics;
- another separately approved German venue-session scope.

A D1 bar derived from the Version 1 intraday authorities is `XETRA_REGULAR_CONTINUOUS_ONLY`. It MUST NOT be labelled auction-inclusive.

## 5.4 Bar Meaning

A complete German-equities `D1` bar contains one approved scope's OHLC and compatible volume for one registered security and one adjustment basis.

A bar MAY originate through `DIRECT_PROVIDER_D1`, `DIRECT_OPERATOR_D1`, `DERIVED_FROM_H1`, `DERIVED_FROM_M30`, or `DERIVED_FROM_M5`.

Security identity, ISIN/WKN segment, provider, MIC, trading system, venue-session profile, source and phase scope, adjustment basis, source timestamp, canonical timestamp, acquisition run, corporate-action segment, and effective range MUST remain explicit in provenance.

## 5.5 Expected Counts

Absent an approved exception:

```text
Expected D1 bars per approved Xetra trading date = 1
Expected D1 bars on an official non-trading date = 0
```

An exceptional shortened service still expects one D1 bar when the venue profile declares a trading session.

---

# 6. Interval Alignment Authority

## 6.1 Alignment Origin

For `XETRA_REGULAR_CONTINUOUS_V1`, the ordinary alignment origin is:

```text
09:00:00 Europe/Berlin
```

and the ordinary continuous-session end is:

```text
17:30:00 Europe/Berlin
```

Official venue-calendar or instrument-specific exceptions override these defaults.

## 6.2 Boundary Rule

The continuous-only D1 interval is half-open:

```text
[session continuous open, session continuous close)
```

Opening-auction, closing-auction, Trade-at-Close, early-retail, late-retail, pre-trading, and post-trading observations are excluded unless the lane explicitly declares and proves another approved scope.

## 6.3 Auction Transition

The Xetra opening auction may transition into continuous trading after 09:00 according to instrument or segment scheduling.

The canonical D1 owner date and 09:00 grid are unchanged. A lack of trades before continuous transition is not automatically a data gap when authoritative phase evidence explains it.

## 6.4 Session-Date Rule

The owner date is the `Europe/Berlin` civil date declared by the approved Xetra calendar.

## 6.5 Exceptional Schedules

Official non-trading days, shortened sessions, special first or last trading days, and exceptional venue schedules MUST come from effective-dated venue authority.

## 6.6 Daylight-Saving Treatment

Session boundaries MUST be resolved with historical IANA `Europe/Berlin` timezone rules. A fixed UTC offset is prohibited.

## 6.7 Halts and Interruptions

Security-specific halts, volatility interruptions, delayed auction transitions, or venue technical events do not authorise fabricated prices.

---

# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `SESSION DATE LABEL`  
**Canonical Storage Timezone:** `UTC`

The canonical D1 timestamp is:

```text
YYYY-MM-DDT00:00:00Z
```

where `YYYY-MM-DD` is the approved `Europe/Berlin` venue trading date.

This is a semantic date label, not the physical Xetra session-open instant.

## 7.2 Required Companion Ownership

Every canonical row MUST also resolve:

- `session_date`;
- official continuous open and close instants in UTC;
- venue name, MIC, trading system, and venue-session profile;
- source and phase scope;
- source timezone and timestamp meaning;
- timestamp-mapping method.

## 7.3 Provider Timestamp Mapping

| Source | Source Timestamp Meaning | Canonical Mapping | Conditions |
|---|---|---|---|
| Twelve Data `1day` | Provider daily label | Resolve against approved venue calendar and map the same local trading date to `00:00:00Z` | Symbol, MIC/trading-system scope, session scope, adjustment basis, and effective range MUST validate |
| Operator-supplied D1 file | Declared trading date or unambiguous daily label | Map approved local trading date to semantic UTC label | Manifest MUST declare venue, phase scope, and adjustment basis |
| Existing accepted immutable D1 evidence | Recorded accepted meaning | Preserve canonical label and provenance | No silent reinterpretation |
| Derived D1 evidence | Approved session owner of contributors | Use session-date semantic label | Section 10 MUST be satisfied |

## 7.4 Date-Only Values

**Date-Only Allowed:** `YES`, only when the date unambiguously means the approved venue trading date.

## 7.5 Ambiguous Values

Implementation MUST NOT guess whether a provider's daily label means Xetra, Frankfurt, exchange-local date, UTC date, settlement date, or another convention.

The candidate remains incompatible while other approved evidence continues operating.

---

# 8. Trading-Day and Session Ownership

## 8.1 Owner Date

Every canonical `D1` bar is owned by the `Europe/Berlin` civil trading date of its approved venue and venue-session profile.

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

- `open` is the first eligible price in the governed `D1` interval;
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

A D1 bar MAY be accepted through:

1. `DIRECT_PROVIDER_D1`;
2. `DIRECT_OPERATOR_D1`;
3. `DERIVED_FROM_H1`;
4. `DERIVED_FROM_M30`;
5. `DERIVED_FROM_M5`.

## 10.2 Direct Evidence

Direct evidence MUST declare:

- registered security and identity segment;
- provider and provider symbol;
- MIC and trading system;
- venue-session profile;
- source venue or aggregate scope;
- continuous-only or auction-inclusive phase scope;
- price and adjustment basis;
- trading currency and volume scope;
- timestamp meaning;
- effective range.

A direct daily bar with unresolved Xetra-versus-Frankfurt or auction-versus-continuous semantics is incompatible.

## 10.3 Derived D1

Derived D1 evidence is permitted only when every expected child interval is present and all contributors share:

- the same registered security identity and corporate-action segment;
- session date;
- provider;
- MIC and trading system;
- venue-session profile `XETRA_REGULAR_CONTINUOUS_V1`;
- continuous-only phase scope;
- source scope;
- trading currency;
- price and adjustment basis;
- effective range.

The aggregation is:

```text
open   = first child open
high   = maximum child high
low    = minimum child low
close  = last child close
volume = sum of compatible child volume, otherwise NULL
```

## 10.4 Normal Child Counts

For an ordinary 09:00–17:30 Xetra continuous session, a complete derived D1 bar requires:

```text
9 H1 intervals, or
17 M30 intervals, or
102 M5 intervals
```

The H1 set includes eight complete 60-minute intervals and the complete 17:00–17:30 session-end interval.

Exceptional counts MUST come from the approved venue profile.

## 10.5 Auction Restriction

A continuous-only child set cannot create an auction-inclusive D1 bar.

An auction-inclusive D1 lane requires direct evidence or a separately approved phase-aware construction profile.

## 10.6 Adjustment Restriction

Timeframe rollup MUST preserve the contributor adjustment basis. Corporate-action adjustment is a separate authorised transformation.

## 10.7 Forbidden Construction

Fragarach MUST NOT:

- mix Xetra, Frankfurt, another venue, or an unresolved aggregate;
- mix continuous trading, auctions, Trade-at-Close, or extended retail;
- mix adjusted and unadjusted contributors;
- mix providers within one bar;
- fill missing intervals with the previous close;
- create a no-trade bar without source evidence;
- infer corporate actions from price discontinuities.

---

# 11. Bar Completion Authority

## 11.1 Closed D1 Bar

A continuous-only D1 bar is closed only when:

1. the approved continuous session has ended;
2. the provider's approved finalisation latency has elapsed or final status is proven;
3. the bar maps to an official trading date;
4. validation has completed.

An auction-inclusive direct D1 lane is closed only after its declared closing-auction or Trade-at-Close process and provider finalisation have completed.

## 11.2 Latest Closed Bar

The latest closed D1 bar is the greatest approved session date satisfying Section 11.1.

A row for the current session remains `OPEN` or `PROVISIONAL` until closure and finalisation are proven.

## 11.3 Corrections

A later official or provider correction creates new immutable evidence. It does not rewrite the earlier evidence event.

---

# 12. Request and Response Authority

## 12.1 Twelve Data Request Contract

The approved automated request uses `/time_series` with:

| Parameter | Approved Value or Rule |
|---|---|
| `symbol` | Registered Twelve Data provider symbol |
| `interval` | `1day` |
| `timezone` | `Europe/Berlin` |
| `order` | `asc` |
| `format` | `JSON` |
| `start_date` | Desired first venue-and-trading-system trading date |
| `end_date` | Civil date after the final requested trading date |
| `outputsize` | MUST be omitted when both bounded dates are supplied |
| authentication | Approved secret mechanism; secret MUST NOT enter logs or evidence payloads |

For desired inclusive canonical opens or owner dates `[S, E]`:

```text
start_date = S represented in Europe/Berlin
end_date   = E + one calendar day represented in Europe/Berlin
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
maximum 4,000 expected D1 intervals per request
```

The default chunk span MUST NOT exceed:

```text
3,650 calendar days
```

and MUST be shortened where required to remain at or below 4,000 expected rows.

## 12.3 Chunk Overlap

Adjacent chunks MUST overlap by at least:

```text
2 expected D1 trading sessions
```

Overlap provides deterministic reassembly, correction detection, and corporate-action boundary evidence.

## 12.4 Incremental Acquisition

An incremental request SHOULD begin at least:

```text
7 expected D1 trading sessions
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

Every `D1` evidence lane MUST materialise an exact effective range for the registered security, provider symbol, registered venue and trading system, source scope, trading-system scope, venue-session profile, session scope, adjustment basis, and provider interval.

## 13.2 Effective Start

The effective start is the latest of:

- the security's approved listing or identity-segment start;
- provider mapping start;
- venue, MIC, trading-system, and venue-session-profile effective start;
- provider `D1` availability start;
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

The expected `D1` set consists of one bar on each official venue-and-trading-system trading day within the lane effective range.

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

Missing recent D1 sessions are generally more material than isolated old gaps. Coverage for Morphix and other consumers MUST be assessed by declared consumer requirements, not by a universal all-bars-or-nothing rule.

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
GERMAN_EQUITIES_D1_VALIDATOR_V1
```

## 17.2 Mandatory Checks

The validator MUST prove:

- registered security identity and active ISIN/WKN/ticker segment;
- market code `EQUITIES_DE` and timeframe `D1`;
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

An active `D1` lane MUST bind at least:

- registered instrument identity and effective identity segment;
- market `EQUITIES_DE`;
- timeframe `D1`;
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
- validator `GERMAN_EQUITIES_D1_VALIDATOR_V1`;
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

Current-As-Of Truth is the session date of the latest accepted closed `D1` bar, together with its source, venue-session profile, phase scope, and validation state.

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

Approval of `GERMAN_EQUITIES_D1_AUTHORITY_V1` means Fragarach II accepts this document as the constitutional source of truth for German Equities `D1` evidence under the approved venue-session profiles defined herein.

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
- Twelve Data API documentation: `/time_series`, interval `1day`, bounded date requests, ascending order, timezone selection, `/earliest_timestamp`, and documented maximum response size of 5,000 records.

These references describe external interfaces and schedules. They do not override this authority, the parent doctrine, registered instrument metadata, venue-session profiles, or effective-dated venue calendar records.

Provider behaviour that differs from the approved contract is a compatibility event, not permission for implementation to reinterpret authority.

---

# 29. Governing Principle

> Constitution defines what is true.  
> Authority defines the approved operational meaning.  
> Specification defines how Fragarach implements that meaning.  
> Implementation must never invent authority.

**Operations is King.**
