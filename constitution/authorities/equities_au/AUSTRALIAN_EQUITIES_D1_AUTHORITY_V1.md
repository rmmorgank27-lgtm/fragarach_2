# AUSTRALIAN EQUITIES D1 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority  
**Authority Layer:** Market Timeframe  
**Authority Name:** `AUSTRALIAN_EQUITIES_D1_AUTHORITY_V1`  
**Market Name:** Australian Equities  
**Market Code:** `EQUITIES_AU`  
**Timeframe:** `D1`  
**Version:** 1.0  
**Status:** APPROVED  
**Repository Location:** `constitution/authorities/equities_au/AUSTRALIAN_EQUITIES_D1_AUTHORITY_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Authority:** `constitution/doctrines/AUSTRALIAN_EQUITIES_BASE_DOCTRINE_V1.md`  
**Effective From:** 2026-07-11  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** Ray Morgan  
**Approval Date:** 2026-07-11

---

# 1. Purpose

This authority defines the approved operational truth for `D1` evidence within the Australian Equities market ecosystem of Fragarach II.

It establishes:

- what one Australian-equities `D1` bar represents;
- ASX Trade calendar and market-service and regular-session ownership;
- exact timestamp and interval semantics;
- direct-provider and approved construction rules;
- adjusted and unadjusted lane separation;
- bar completion and latest-closed-bar calculations;
- Twelve Data request, response, chunking, and history contracts;
- effective-range materialisation;
- expected-bar, halt, gap, duplicate, conflict, repair, and freshness rules;
- the `AUSTRALIAN_EQUITIES_D1_VALIDATOR_V1` validation contract;
- evidence-lane activation and operational eligibility.

This authority does not define database schemas, storage implementation, client architecture, native application layout, migration procedure, or acceptance-test code. Those matters belong to specifications that consume this authority.

---

# 2. Constitutional Position

```text
Constitution

↓

AUSTRALIAN_EQUITIES_BASE_DOCTRINE_V1

↓

AUSTRALIAN_EQUITIES_D1_AUTHORITY_V1

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides all subordinate documents;
2. `AUSTRALIAN_EQUITIES_BASE_DOCTRINE_V1` overrides this authority;
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

- securities registered under market code `EQUITIES_AU`;
- timeframe code `D1`;
- an approved Australian market operator, operating MIC, market service, and session profile;
- Version 1 concrete profile `ASX_NORMAL_TRADING_V1`;
- evidence whose provider symbol mapping, source scope, adjustment basis, timestamp meaning, and effective range are known;
- direct `D1` evidence and only the derived methods expressly permitted in Section 10.

## 4.2 Version 1 Concrete Market Profile

The concrete session profile defined by this authority is:

```text
Market operator:        ASX Limited
Operating MIC:          XASX
Trading platform:       ASX Trade
Market-service profile: ASX_NORMAL_TRADING_V1
Timezone:               Australia/Sydney
Canonical grid:         10:00–16:00 local time
Scope:                  normal continuous trading only
```

The canonical 10:00–16:00 grid is deliberately deterministic.

ASX's official opening transition is randomised during the period immediately before 10:00. Observations from the Opening Single Price Auction or the randomised transition before 10:00 do not enter the Version 1 continuous-only intraday grid.

## 4.3 Other Australian Venues, Services, and Phases

This document does not silently assign `ASX_NORMAL_TRADING_V1` to:

- another Australian market operator or alternative venue;
- ASX pre-open;
- Opening Single Price Auction;
- the randomised transition before 10:00;
- Pre-CSPA;
- Closing Single Price Auction;
- Post Close;
- Adjust or Adjust ON;
- overnight or overseas trade reports;
- crossings or other separately classified trade-report activity;
- a provider-defined Australian aggregate whose composition is unresolved.

Those paths require a separately approved market-service profile or an effective-dated constitutional amendment.

## 4.4 Excluded Scope

This authority does not govern:

- mixed-phase or unresolved auction-scope evidence;
- ETFs, ETPs, LICs, LITs, managed funds, hybrids, bonds, warrants, options, futures, indices, CFDs, or OTC securities not admitted by the parent doctrine;
- securities whose ordinary-share, stapled-security, CDI, share-class, or ratio identity is unresolved;
- another timeframe;
- provider data whose market operator, MIC, service, session, auction, trade-report, adjustment, or timestamp semantics are unresolved;
- bars outside the approved quotation, identity-segment, market-service-profile, and provider effective range.

## 4.5 Inherited Market Truth

This authority inherits without modification:

- regulated multi-venue Australian-equities market identity;
- explicit security, share-class, stapled-security, CDI, ratio, and primary-quotation identity;
- `Australia/Sydney` calendar timezone;
- official ASX Trade calendar authority;
- official non-trading-day, early-close, halt, suspension, and exceptional-session treatment;
- opening auction, normal trading, closing auction, post-close, crossing, and alternative-session separation;
- adjusted and unadjusted lane separation;
- corporate-action and security-continuity authority;
- immutable evidence and non-blocking operations doctrine.

---

# 5. Canonical Timeframe Definition

## 5.1 Timeframe Identity

**Timeframe Code:** `D1`  
**Nominal Duration:** One approved market trading session  
**Duration in Minutes:** `SESSION-DEFINED`  
**Time Unit:** `TRADING_SESSION`  
**Interval Type:** `SESSION_DEFINED`

## 5.2 Approved Definition

One canonical Australian-equities `D1` bar represents one approved market-service-profile trading date for one registered security and one declared source, phase, trade-class, and adjustment scope.

For `ASX_NORMAL_TRADING_V1`, the governed deterministic continuous interval is:

```text
[10:00:00 Australia/Sydney, 16:00:00 Australia/Sydney)
```

The session date and schedule are controlled by the official ASX Trade calendar and effective-dated market-service profile.

The D1 bar is owned by the ASX local trading date. It is not a midnight-to-midnight civil-day bar.

## 5.3 D1 Scope Classes

Version 1 permits distinct D1 lanes such as:

- `ASX_NORMAL_TRADING_ONLY`;
- `ASX_OFFICIAL_DAILY_AUCTION_INCLUSIVE`, only when the direct source proves its opening and closing price semantics;
- another separately approved Australian venue or aggregate scope.

A D1 bar derived from the Version 1 intraday authorities is `ASX_NORMAL_TRADING_ONLY`. It MUST NOT be labelled auction-inclusive.

## 5.4 Bar Meaning

A complete Australian-equities `D1` bar contains one approved scope's OHLC and compatible volume for one registered security and one adjustment basis.

A bar MAY originate through `DIRECT_PROVIDER_D1`, `DIRECT_OPERATOR_D1`, `DERIVED_FROM_H1`, `DERIVED_FROM_M30`, or `DERIVED_FROM_M5`.

Security identity, security form, ratio where applicable, provider, market operator, operating MIC, market-service profile, source and trade-class scope, adjustment basis, source timestamp, canonical timestamp, acquisition run, corporate-action segment, and effective range MUST remain explicit in provenance.

## 5.5 Expected Counts

Absent an approved exception:

```text
Expected D1 bars per approved ASX trading date = 1
Expected D1 bars on an official non-trading date = 0
```

An official early-close session still expects one D1 bar.

---

# 6. Interval Alignment Authority

## 6.1 Alignment Origin

For `ASX_NORMAL_TRADING_V1`, the deterministic alignment origin is:

```text
10:00:00 Australia/Sydney
```

and the ordinary normal-trading end is:

```text
16:00:00 Australia/Sydney
```

Official ASX calendar exceptions override the ordinary end.

## 6.2 Boundary Rule

The normal-trading-only D1 interval is half-open:

```text
[10:00, approved normal-trading close)
```

Pre-open, Opening Single Price Auction, the randomised transition before 10:00, Pre-CSPA, Closing Single Price Auction, Post Close, crossings, Adjust, Adjust ON, overnight reports, and another venue's observations are excluded unless the lane explicitly declares and proves another approved scope.

## 6.3 Randomised Opening Rule

ASX's opening transition is randomised immediately before 10:00.

Version 1 does not attempt to create variable-second intraday bars from that transition. Evidence before 10:00 remains opening-auction or opening-transition scope and does not enter `ASX_NORMAL_TRADING_V1`.

## 6.4 Session-Date Rule

The owner date is the `Australia/Sydney` civil date declared by the official ASX Trade calendar.

## 6.5 Exceptional Schedules

Official non-trading days, published early closes, and exceptional market schedules MUST come from effective-dated ASX authority.

## 6.6 Daylight-Saving Treatment

Session boundaries MUST be resolved with historical IANA `Australia/Sydney` timezone rules. A fixed UTC offset is prohibited.

## 6.7 Halts and Interruptions

Security-specific halts, suspensions, deferred openings, or market technical events do not authorise fabricated prices.

---

# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `SESSION DATE LABEL`  
**Canonical Storage Timezone:** `UTC`

The canonical D1 timestamp is:

```text
YYYY-MM-DDT00:00:00Z
```

where `YYYY-MM-DD` is the approved `Australia/Sydney` ASX trading date.

This is a semantic date label, not the physical market-open instant.

## 7.2 Required Companion Ownership

Every canonical row MUST also resolve:

- `session_date`;
- official normal-trading open and close instants in UTC;
- market operator, operating MIC, trading platform, and market-service profile;
- source, phase, and trade-class scope;
- source timezone and timestamp meaning;
- timestamp-mapping method.

## 7.3 Provider Timestamp Mapping

| Source | Source Timestamp Meaning | Canonical Mapping | Conditions |
|---|---|---|---|
| Twelve Data `1day` | Provider daily label | Resolve against approved ASX calendar and map the same Sydney trading date to `00:00:00Z` | Symbol, exchange mapping, session scope, adjustment basis, and effective range MUST validate |
| Operator-supplied D1 file | Declared trading date or unambiguous daily label | Map approved Sydney trading date to semantic UTC label | Manifest MUST declare market operator, service, phase scope, and adjustment basis |
| Existing accepted immutable D1 evidence | Recorded accepted meaning | Preserve canonical label and provenance | No silent reinterpretation |
| Derived D1 evidence | Approved session owner of contributors | Use session-date semantic label | Section 10 MUST be satisfied |

## 7.4 Date-Only Values

**Date-Only Allowed:** `YES`, only when the date unambiguously means the approved ASX trading date.

## 7.5 Ambiguous Values

Implementation MUST NOT guess whether a provider's daily label means ASX local date, UTC date, settlement date, another Australian venue date, or another convention.

The candidate remains incompatible while other approved evidence continues operating.

---

# 8. Trading-Day and Session Ownership

## 8.1 Owner Date

Every canonical `D1` bar is owned by the `Australia/Sydney` civil trading date of its approved market-service profile.

## 8.2 Calendar Authority

Expected sessions MUST come from the approved official ASX Trade calendar, including effective-dated:

- non-trading days;
- early closes;
- exceptional schedules;
- market-wide interruptions;
- profile amendments.

A generic Monday-to-Friday calendar or Australian public-holiday list is insufficient.

## 8.3 Version 1 Session Scope

The concrete Version 1 intraday scope is `ASX_NORMAL_TRADING_V1`.

Pre-open, opening auction, randomised opening transition, Pre-CSPA, closing auction, Post Close, Adjust, Adjust ON, overnight reports, crossings, and another market operator's evidence MUST remain separately identified and MUST NOT advance this profile's Current-As-Of Truth.

## 8.4 Market Operator and Aggregate Scope

ASX Trade evidence, another Australian venue's evidence, and an approved multi-venue aggregate MAY coexist only as separate lanes.

Trading-day ownership follows the lane's approved market-service profile. A provider's generic `Australia`, `Sydney`, or `.AX` label does not by itself prove ASX Trade normal-session scope.

## 8.5 Security- and Market-Specific Events

Security halts, suspensions, deferred openings, quotation changes, delistings, and market technical events require explicit evidence.

They do not authorise silent calendar mutation or fabricated prices.

---

# 9. Bar Price and Field Meaning

## 9.1 OHLC Meaning

For one approved source scope, market-service profile, and adjustment basis:

- `open` is the first eligible price in the governed `D1` interval;
- `high` is the maximum eligible price;
- `low` is the minimum eligible price;
- `close` is the final eligible price;
- `volume` is eligible traded security-unit quantity within the same declared source scope, when supplied.

## 9.2 Source Scope

A lane MUST explicitly identify whether evidence is:

- ASX Trade on-market;
- another named Australian venue;
- an approved venue-specific licensed feed;
- an approved Australian multi-venue aggregate;
- another expressly approved scope.

These scopes are not interchangeable.

## 9.3 Session and Trade-Class Scope

The concrete Version 1 canonical intraday scope is `ASX_NORMAL_TRADING_ONLY`.

The following require separate scope identity:

- Opening Single Price Auction evidence;
- randomised opening-transition evidence;
- Closing Single Price Auction evidence;
- Post Close trades;
- crossings;
- overnight or overseas trade reports;
- Adjust or Adjust ON activity;
- another separately classified trade-report type;
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
- security form and CDI or other ratio where applicable;
- provider and provider symbol;
- market operator, operating MIC, and market-service profile;
- source venue or aggregate scope;
- normal-only or auction-inclusive phase and trade-class scope;
- price and adjustment basis;
- trading currency and volume scope;
- timestamp meaning;
- effective range.

A direct daily bar with unresolved auction, post-close, crossing, venue, or aggregate semantics is incompatible.

## 10.3 Derived D1

Derived D1 evidence is permitted only when every expected child interval is present and all contributors share:

- the same registered security identity, security form, ratio, and corporate-action segment;
- session date;
- provider;
- operating MIC and market-service profile `ASX_NORMAL_TRADING_V1`;
- normal-trading-only scope;
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

For an ordinary 10:00–16:00 ASX normal-trading session, a complete derived D1 bar requires:

```text
6 H1 intervals, or
12 M30 intervals, or
72 M5 intervals
```

For an approved 10:00–14:10 ASX early-close session:

```text
5 H1 intervals, or
9 M30 intervals, or
50 M5 intervals
```

The final H1 and M30 intervals on that early-close session are complete 10-minute session-end intervals.

## 10.5 Auction Restriction

A normal-trading-only child set cannot create an auction-inclusive D1 bar.

An auction-inclusive D1 lane requires direct evidence or a separately approved phase-aware construction profile.

## 10.6 Adjustment Restriction

Timeframe rollup MUST preserve the contributor adjustment basis. Corporate-action adjustment is a separate authorised transformation.

## 10.7 Forbidden Construction

Fragarach MUST NOT:

- mix ASX Trade, another venue, or an unresolved aggregate;
- mix normal trading, auctions, post-close, crossings, Adjust, or overnight reports;
- mix adjusted and unadjusted contributors;
- mix providers within one bar;
- fill missing intervals with the previous close;
- create a no-trade bar without source evidence;
- infer corporate actions or CDI-ratio changes from price discontinuities.

---

# 11. Bar Completion Authority

## 11.1 Closed D1 Bar

A normal-trading-only D1 bar is closed only when:

1. the approved normal-trading session has ended;
2. the provider's approved finalisation latency has elapsed or final status is proven;
3. the bar maps to an official ASX trading date;
4. validation has completed.

An auction-inclusive direct D1 lane is closed only after its declared closing-auction or post-close finalisation boundary and provider finalisation have completed.

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
| `timezone` | `Australia/Sydney` |
| `order` | `asc` |
| `format` | `JSON` |
| `start_date` | Desired first market-operator-and-service trading date |
| `end_date` | Civil date after the final requested trading date |
| `outputsize` | MUST be omitted when both bounded dates are supplied |
| authentication | Approved secret mechanism; secret MUST NOT enter logs or evidence payloads |

For desired inclusive canonical opens or owner dates `[S, E]`:

```text
start_date = S represented in Australia/Sydney
end_date   = E + one calendar day represented in Australia/Sydney
```

The response MUST then be canonically filtered to the approved requested range, operating-MIC scope, market-service profile, phase scope, and trade-class scope. Boundary inclusivity MUST NOT be assumed.

A provider response MUST prove market operator, operating MIC, market-service, source, phase, and trade-class compatibility. If auction, post-close, crossing, Adjust, overnight-report, alternative-venue, or unresolved aggregate observations cannot be deterministically separated, the provider path is incompatible.

## 12.1A Australian Market Compatibility Gate

A successful provider response is not active Australian-equities evidence until Fragarach proves:

- provider symbol to registered security mapping;
- market operator and operating MIC;
- ASX Trade versus another venue or aggregate scope;
- market-service profile;
- normal trading versus auction, post-close, crossing, Adjust, or overnight-report scope;
- security form and ratio where applicable;
- trading currency and adjustment basis.

A generic `Australia`, `Sydney`, `ASX`, or `.AX` label is insufficient by itself.

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
- regular-session and alternative-session scope are not silently merged;
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
3. filtering to the requested canonical range and regular-session scope;
4. sorting ascending;
5. comparing overlap rows;
6. collapsing exact repeats only in read models while retaining provenance;
7. retaining conflicting overlap rows as conflict evidence;
8. proving requested, received, duplicate, conflict, future, and uncovered ranges.

## 12.7 Request Coverage Proof

Every acquisition run MUST record:

- instrument and provider symbol;
- security and market-operator-and-service identity;
- provider interval and request timezone;
- source venue or consolidated scope;
- regular-session scope;
- adjustment and price basis;
- requested local and UTC start/end;
- expected canonical interval count;
- returned and accepted counts;
- alternative-session, future, invalid, and misaligned counts;
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

Every `D1` evidence lane MUST materialise an exact effective range for the registered security, security form, ratio where applicable, provider symbol, market operator, operating MIC, market-service profile, source scope, phase and trade-class scope, adjustment basis, and provider interval.

## 13.2 Effective Start

The effective start is the latest of:

- the security's approved listing or identity-segment start;
- provider mapping start;
- market-operator, operating-MIC, market-service-profile, and security-form effective start;
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
- market-operator, operating-MIC, market-service-profile, security-form, or ratio effective end;
- adjustment-basis segment end;
- approved operational retirement.

## 13.4 No Invented History

Fragarach MUST NOT expect evidence before the effective start or after the effective end.

Ticker reuse, relisting, mergers, reorganisations, and share-class changes require explicit segmentation rather than silent history joining.

---

# 14. Expected Bars and Gap Authority

## 14.1 Expected Set

The expected `D1` set consists of one bar on each official market-operator-and-service trading day within the lane effective range.

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
- security-specific halt, suspension, deferred opening, or quotation interruption;
- delayed opening;
- early close;
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

Rows are exact duplicates only when canonical identity, timestamp, OHLC, volume, venue/consolidated scope, session scope, adjustment basis, and relevant provenance values agree.

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

Australian-dollar denomination MUST NOT be inferred merely from issuer domicile, ASX quotation, ticker suffix, or provider metadata.

## 16.2 Security Unit and Ratio Identity

Ordinary shares, stapled securities, CHESS Depositary Interests, and other admitted security forms remain distinct instrument identities.

Where a CDI or other depositary instrument has a ratio to an underlying security, that ratio is mandatory effective-dated identity metadata. It MUST NOT be used to silently transform prices or volume into the underlying instrument.

## 16.3 Price Basis

ASX normal-trading, opening-auction, closing-auction, post-close, crossing, venue-specific, approved aggregate, adjusted, and unadjusted price bases MUST remain explicit and compatible with the lane contract.

## 16.4 Volume

Volume means eligible traded security units within the declared market operator, service, phase, trade-class, and source scope.

ASX on-market volume, crossing volume, post-close volume, another venue's volume, approved aggregate volume, turnover value, and provider-estimated volume are not interchangeable.

Volume MUST be `NULL` when unavailable or semantically incompatible. It MUST NOT be replaced with zero merely to satisfy a schema.

## 16.5 Corporate Actions

Subdivision, consolidation, dividend, distribution, entitlement offer, rights issue, capital return, demerger, scheme of arrangement, takeover, stapling or unstapling, CDI-ratio change, cancellation, readmission, and other corporate-action effects MUST remain governed by explicit adjustment and identity authority.

Timeframe construction alone does not authorise adjustment.

## 16.6 Precision

Decimal values MUST be preserved without avoidable binary floating-point loss. Rounding is permitted only at approved presentation or storage precision boundaries and MUST NOT alter source evidence.

---

# 17. Validation Authority

## 17.1 Validator Identity

The mandatory validator is:

```text
AUSTRALIAN_EQUITIES_D1_VALIDATOR_V1
```

## 17.2 Mandatory Checks

The validator MUST prove:

- registered security identity, security form, ratio where applicable, and active ticker/identity segment;
- market code `EQUITIES_AU` and timeframe `D1`;
- market operator, operating MIC, trading platform, and market-service profile;
- provider symbol and source scope;
- normal-trading-only phase scope for `ASX_NORMAL_TRADING_V1`;
- opening-transition, auction, post-close, crossing, Adjust, overnight-report, and alternative-venue exclusion;
- timestamp meaning and `Australia/Sydney` timezone mapping;
- interval open and end match the approved 10:00-based session grid;
- any session-end shortened interval ends exactly at the approved early close;
- OHLC numeric validity: `low <= open <= high`, `low <= close <= high`, and `low <= high`;
- price precision and trading-currency consistency;
- security-unit, stapled-security, and CDI-ratio consistency;
- adjustment-basis consistency;
- non-negative volume when volume is present;
- monotonic canonical ordering;
- duplicate and conflict classification;
- effective-range membership;
- closed, open, provisional, or corrected state;
- immutable evidence and acquisition provenance;
- no silent venue, phase, ratio, or corporate-action transformation.

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
- market operator, service profile, phase, trade-class, source, adjustment, and session-scope summary;
- Current-As-Of Truth;
- compatibility findings.

Validation failure blocks only the affected candidate or lane.

---

# 18. Evidence Lane Contract

## 18.1 Mandatory Lane Identity

An active `D1` lane MUST bind at least:

- registered instrument identity and effective identity segment;
- security form and ratio where applicable;
- market `EQUITIES_AU`;
- timeframe `D1`;
- market operator and operating MIC;
- trading platform and market-service profile;
- provider and provider symbol;
- source venue or approved aggregate scope;
- phase and trade-class scope;
- price basis;
- adjustment basis;
- trading currency;
- timestamp meaning;
- construction method;
- effective range;
- validator `AUSTRALIAN_EQUITIES_D1_VALIDATOR_V1`;
- approval and activation state.

## 18.2 Activation Gate

A lane may become active only when:

1. instrument registration is approved;
2. security form and any CDI or other ratio are explicit;
3. provider mapping, operating MIC, service profile, and source scope are approved;
4. ASX calendar and market-service profile resolve;
5. phase, trade-class, and adjustment scope are explicit;
6. effective start is materialised;
7. timestamp mapping passes validation;
8. evidence provenance is immutable;
9. latest accepted closed interval is known;
10. compatibility blockers are absent for that lane.

## 18.3 Read Contract

Consumers MUST be able to read:

- best accepted bars;
- Current-As-Of Truth;
- freshness state;
- source, market operator, service profile, phase, trade-class, and adjustment scope;
- gap and explained-absence status;
- conflict and correction status;
- effective range;
- validator result.

Maintenance state MUST NOT hide otherwise usable evidence.

---

# 19. Operational Freshness Authority

## 19.1 Current-As-Of Truth

Current-As-Of Truth is the session date of the latest accepted closed `D1` bar, together with its source, market-service profile, phase scope, and validation state.

## 19.2 Freshness States

Implementations MAY expose controlled states such as:

- `GREEN` — latest expected closed interval accepted;
- `AMBER` — usable evidence exists but the live edge is delayed, provisional, or under repair;
- `RED` — no usable accepted evidence for the lane;
- `CLOSED` — the approved market-service profile is outside its expected operating interval.

`AMBER` remains usable. Warnings MUST NOT blank accepted history.

## 19.3 Expected Live Edge

The expected latest closed interval MUST be calculated from:

- approved ASX Trade calendar;
- market-service profile for the trading date;
- current `Australia/Sydney` time;
- interval boundaries under Section 6;
- approved provider finalisation latency;
- effective-dated early-close or exceptional market events.

## 19.4 Non-Blocking Doctrine

Repair, provider failure, stale live edge, missing recent bars, and unresolved lower-priority conflicts remain visible but MUST NOT block unrelated lanes or historical reads.

---

# 20. Provider Precedence

## 20.1 Precedence Classes

Where multiple compatible candidates exist, deterministic precedence SHOULD favour:

1. approved official ASX or licensed ASX-specific evidence;
2. approved direct provider evidence with exact operating-MIC, market-service-profile, source-scope, session-scope, trade-class, and adjustment compatibility;
3. approved operator-supplied direct evidence;
4. approved derived evidence from complete lower-timeframe contributors.

## 20.2 No Silent Preference

Precedence MUST NOT be inferred from arrival order, longest history, numerical smoothness, highest volume, a generic `Australia` label, `.AX` suffix, provider popularity, or an assumption that one venue always overrides another authorised lane.

## 20.3 Scope Compatibility

Precedence applies only among candidates with the same security identity, operating MIC, market-service profile, source scope, session and trade-class scope, adjustment basis, currency, timeframe, and effective segment.

---

# 21. Exceptions

Any exception MUST be:

- named;
- effective-dated;
- scoped to specific instruments, market operators, MICs, service profiles, providers, phases, trade classes, or dates;
- justified by evidence;
- approved at the correct authority layer;
- testable;
- visible to operators.

Examples include non-trading days, official early closes, exceptional schedules, market interruptions, security halts, deferred openings, suspensions, ticker or identifier changes, stapled-security changes, CDI-ratio changes, corporate-action segments, first or last trading days, and provider timestamp deviations.

A recurring exception indicates that this authority or its market-service profile requires amendment.

---

# 22. Compatibility Requirements

Before implementation or activation, Fragarach MUST prove compatibility for:

- registered security, share class, stapled-security or CDI form, ratio, and quotation identity;
- market operator, operating MIC, trading platform, and market-service profile;
- official ASX Trade calendar and phase schedule;
- provider symbol and exchange mapping;
- normal-trading isolation;
- auction, post-close, crossing, overnight-report, and alternative-venue exclusion;
- timestamp semantics and alignment;
- source venue or approved aggregate scope;
- trading currency, adjustment basis, and price basis;
- corporate-action and identity segment;
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
- operating MIC and market-service-profile identity;
- calendar and phase ownership;
- normal-trading boundaries;
- interval alignment;
- timestamp meaning;
- phase, trade-class, source, and adjustment scope;
- provider request semantics;
- effective-range rules;
- validation requirements.

---

# 24. Implementation Prohibitions

Implementation MUST NOT:

- invent a market operator, MIC, platform, or market-service profile;
- infer security identity solely from ticker text or `.AX` suffix;
- treat a generic `Australia`, `Sydney`, or provider exchange label as proof of ASX normal-trading scope;
- merge ASX Trade, another venue, or a multi-venue aggregate silently;
- merge normal trading, opening auction, closing auction, post-close, crossing, overnight-report, or Adjust activity silently;
- shift randomised pre-10:00 opening-transition trades onto the 10:00 intraday grid;
- mix adjusted and unadjusted bars;
- transform CDI or stapled-security units into an underlying instrument without authority;
- create corporate-action adjustments without authority;
- fabricate no-trade bars;
- fill gaps with previous closes;
- force provider timestamps onto an incompatible grid;
- treat official non-trading days or approved interruptions as ordinary gaps;
- silently overwrite conflicting evidence;
- join histories across ticker, security-form, ratio, share-class, or identity changes;
- expose secrets in logs or evidence;
- block unrelated operations because one lane is incompatible.

---

# 25. Amendment and Versioning

A new major version is required when changing:

- regular-session scope;
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

- reviewed against `AUSTRALIAN_EQUITIES_BASE_DOCTRINE_V1`;
- tested with representative ASX ordinary shares, stapled securities, and CDIs where applicable;
- tested against operating MIC `XASX`;
- tested across ordinary sessions, official non-trading days, and ASX early-close schedules;
- tested across `Australia/Sydney` daylight-saving offsets;
- tested with opening auction, normal trading, closing auction, post-close, crossings, and alternative-venue evidence kept separate;
- tested with adjusted and unadjusted evidence kept separate;
- tested across ticker, security-form, CDI-ratio, and corporate-action boundaries;
- approved by the constitutional authority owner;
- recorded with approval date and effective date.

Until then, status remains `DRAFT FOR APPROVAL`.

---

# 27. Acceptance Statement

Approval of `AUSTRALIAN_EQUITIES_D1_AUTHORITY_V1` means Fragarach II accepts this document as the constitutional source of truth for Australian Equities `D1` evidence under the approved market-service profiles defined herein.

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

- ASX official cash-market trading-hours record: pre-open from 07:00, Opening Single Price Auction beginning at 09:59 with a randomised transition, normal trading through 16:00, Pre-CSPA, Closing Single Price Auction, Post Close, Adjust, and later system phases;
- ASX official trading calendar: effective-dated non-trading days and early closes, including published days on which normal trading ceases at 14:10 Sydney time;
- ASX records identifying CHESS Depositary Interests as distinct quoted financial products and requiring their security identity to remain explicit;
- ISO 10383 market-identifier records and ASX technical material identifying `XASX` as the ASX operating MIC;
- Twelve Data API documentation: `/time_series`, interval `1day`, bounded date requests, ascending order, timezone selection, `/earliest_timestamp`, and documented maximum response size of 5,000 records.

These references describe external interfaces and schedules. They do not override this authority, the parent doctrine, registered instrument metadata, market-service profiles, or effective-dated ASX calendar records.

Provider behaviour that differs from the approved contract is a compatibility event, not permission for implementation to reinterpret authority.

---

# 29. Governing Principle

> Constitution defines what is true.  
> Authority defines the approved operational meaning.  
> Specification defines how Fragarach implements that meaning.  
> Implementation must never invent authority.

**Operations is King.**
