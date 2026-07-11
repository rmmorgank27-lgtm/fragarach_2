# US EQUITIES D1 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority  
**Authority Layer:** Market Timeframe  
**Authority Name:** `UK_EQUITIES_D1_AUTHORITY_V1`  
**Market Name:** United Kingdom Equities  
**Market Code:** `EQUITIES_UK`  
**Timeframe:** `D1`  
**Version:** 1.0  
**Status:** APPROVED  
**Repository Location:** `constitution/authorities/equities_uk/UK_EQUITIES_D1_AUTHORITY_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Authority:** `constitution/doctrines/UK_EQUITIES_BASE_DOCTRINE_V1.md`  
**Effective From:** 2026-07-11  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** Ray Morgan  
**Approval Date:** 2026-07-11

---

# 1. Purpose

This authority defines the approved operational truth for `D1` evidence within the United Kingdom Equities market ecosystem of Fragarach II.

It establishes:

- what one UK-equities `D1` bar represents;
- primary-venue calendar and regular-session ownership;
- exact timestamp and interval semantics;
- direct-provider and approved construction rules;
- adjusted and unadjusted lane separation;
- bar completion and latest-closed-bar calculations;
- Twelve Data request, response, chunking, and history contracts;
- effective-range materialisation;
- expected-bar, halt, gap, duplicate, conflict, repair, and freshness rules;
- the `UK_EQUITIES_D1_VALIDATOR_V1` validation contract;
- evidence-lane activation and operational eligibility.

This authority does not define database schemas, storage implementation, client architecture, native application layout, migration procedure, or acceptance-test code. Those matters belong to specifications that consume this authority.

---

# 2. Constitutional Position

```text
Constitution

↓

UK_EQUITIES_BASE_DOCTRINE_V1

↓

UK_EQUITIES_D1_AUTHORITY_V1

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides all subordinate documents;
2. `UK_EQUITIES_BASE_DOCTRINE_V1` overrides this authority;
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

- securities registered under market code `EQUITIES_UK`;
- timeframe code `D1`;
- the registered instrument's approved primary-venue calendar;
- Version 1 regular-session evidence whose auction treatment is explicit;
- evidence whose provider, symbol mapping, venue or consolidated scope, adjustment basis, timestamp meaning, and effective range are known;
- direct `D1` evidence and only the derived methods expressly permitted in Section 10.

## 4.2 Excluded Scope

This authority does not govern:

- pre-open, post-close, alternative-session, or mixed-session evidence;
- ETFs, funds, preferred stock, warrants, options, futures, indices, CFDs, or OTC securities not admitted by the parent doctrine;
- foreign ordinary shares not registered under `EQUITIES_UK`;
- another timeframe;
- provider data whose trading service, session, auction treatment, venue, price-display unit, adjustment, or timestamp semantics are unresolved;
- bars outside the approved listing and provider effective range.

## 4.3 Inherited Market Truth

This authority inherits without modification:

- regulated multi-venue UK-equities market identity;
- explicit security, share-class, and primary-listing identity;
- `Europe/London` calendar timezone;
- official primary-venue calendar authority;
- ordinary 08:00–16:30 regular-session default;
- official holiday, early-close, halt, suspension, and exceptional-closure treatment;
- regular and extended-hours separation;
- adjusted and unadjusted lane separation;
- corporate-action and ticker-continuity authority;
- immutable evidence and non-blocking operations doctrine.

---

# 5. Canonical Timeframe Definition

## 5.1 Timeframe Identity

**Timeframe Code:** `D1`  
**Nominal Duration:** One official regular trading session  
**Duration in Minutes:** `SESSION-DEFINED`  
**Time Unit:** `TRADING_SESSION`  
**Interval Type:** `SESSION_DEFINED`

## 5.2 Approved Definition

One canonical UK-equities `D1` bar represents one official primary-venue regular trading session for one registered security and one declared evidence scope.

For an ordinary full session, the governed interval is:

```text
[08:00:00 Europe/London, 16:30:00 Europe/London]
```

The opening and closing instants are controlled by the approved primary-venue calendar. Official early closes, exceptional closures, and effective-dated session changes override the ordinary times.

The D1 bar is owned by the primary venue's local trading date. It is not a midnight-to-midnight civil-day bar.

## 5.3 Bar Meaning

A complete UK-equities `D1` bar contains one approved source scope's regular-session OHLC and compatible volume for one registered security and one adjustment basis.

A bar MAY originate through `DIRECT_PROVIDER_D1`, `DIRECT_OPERATOR_D1` or `DERIVED_FROM_H1`, `DERIVED_FROM_M30`, or `DERIVED_FROM_M5`.

Security identity, provider, venue scope, trading-service scope, session and auction scope, listing currency, price-display unit, adjustment basis, source timestamp, canonical timestamp, acquisition run, corporate-action segment, and effective range MUST remain explicit in provenance.

## 5.4 Expected Counts

Absent an approved exception:

```text
Expected D1 bars per official trading session = 1
Expected D1 bars on a full-market holiday     = 0
```

An official early-close day still expects one D1 bar. A full-day market closure expects none.

---

# 6. Interval Alignment Authority

## 6.1 Alignment Origin

The alignment origin is the official regular-session opening time for the registered instrument's primary venue and trading date.

The ordinary default is:

```text
08:00:00 Europe/London
```

The ordinary close is:

```text
16:30:00 Europe/London
```

Official early closes, exceptional schedules, and effective-dated venue changes override these defaults.

## 6.2 Boundary Rule

A D1 session begins at the official regular-session open and ends when the approved regular session and closing-auction process have completed for that trading date.

Pre-market, post-market, overnight, and other extended-hours observations MUST NOT enter the Version 1 regular-session D1 lane.

## 6.3 Session-Date Rule

The owner date is the `Europe/London` civil date assigned by the approved primary-venue calendar.

A date is expected only when the calendar declares an official trading session for that venue.

## 6.4 Early Closes

An official early close produces one complete D1 session bar covering the shortened regular session.

Implementation MUST NOT treat an early-close D1 bar as incomplete because its elapsed session duration is shorter than an ordinary session.

## 6.5 Holidays and Exceptional Closures

Official full-market holidays and exceptional closures produce no expected D1 bar.

Weekend dates are not expected unless an approved primary-venue calendar expressly defines a session.

## 6.6 Daylight-Saving Treatment

Session boundaries MUST be resolved with historical IANA `Europe/London` timezone rules.

Implementation MUST NOT use a fixed UTC offset.

## 6.7 Halts and Delayed Openings

A security-specific halt or delayed opening does not automatically change the venue's regular-session boundary.

Absence of trades may be classified as explained only when authoritative halt or delayed-opening evidence exists. Fragarach MUST NOT fabricate prices for the missing period.

---

# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `SESSION DATE LABEL`  
**Canonical Storage Timezone:** `UTC`

The canonical D1 timestamp is:

```text
YYYY-MM-DDT00:00:00Z
```

where `YYYY-MM-DD` is the approved primary-venue trading date in `Europe/London`.

This timestamp is a stable semantic date label. It is not the physical session-open instant and is not a midnight UTC market boundary.

## 7.2 Required Companion Ownership

Every canonical row MUST also resolve:

- `session_date`;
- official session open and close instants in UTC;
- primary venue, market segment or trading service, and calendar authority;
- source timezone;
- source timestamp meaning;
- timestamp-mapping method;
- regular-session scope.

## 7.3 Provider Timestamp Mapping

| Source | Source Timestamp Meaning | Canonical Mapping | Conditions |
|---|---|---|---|
| Twelve Data `1day` | Provider daily label | Resolve against registered venue calendar and map to the same local trading date label at `00:00:00Z` | Venue, symbol, session scope, adjustment basis, and effective range MUST validate |
| Operator-supplied D1 file | Declared trading date or unambiguous daily label | Map approved local trading date to semantic UTC label | Manifest MUST declare venue, session scope, and adjustment basis |
| Existing accepted immutable D1 evidence | Recorded accepted meaning | Preserve canonical label and provenance | No silent reinterpretation |
| Derived D1 evidence | Approved session owner of contributing intraday bars | Use session-date semantic label | Section 10 MUST be satisfied |

## 7.4 Date-Only Values

**Date-Only Allowed:** `YES`, only when the date unambiguously means the approved venue trading date.

A date-only row whose venue, calendar, session scope, or adjustment basis is unresolved MUST NOT enter an active lane.

## 7.5 Ambiguous Values

Implementation MUST NOT guess when a provider's daily label may represent UTC date, exchange-local date, settlement date, or another convention.

The provider path MUST stop with a compatibility report while other approved evidence remains operational.

---

# 8. Trading-Day and Session Ownership

## 8.1 Owner Date

Every canonical `D1` bar is owned by the approved primary venue's `Europe/London` trading date.

## 8.2 Calendar Authority

Expected sessions MUST come from the registered primary-venue calendar, including effective-dated:

- holidays;
- early closes;
- exceptional closures;
- venue schedule changes.

A generic Monday-to-Friday calendar is insufficient.

## 8.3 Regular Session

Version 1 authority covers only the approved regular session. Extended-hours evidence MUST remain in separate lanes and MUST NOT advance this authority's Current-As-Of Truth.

## 8.4 Venue and Consolidated Scope

Primary-venue evidence and approved consolidated evidence MAY both exist, but only as separately identified lanes.

Trading-day ownership follows the registered primary-venue calendar even when the price source is approved consolidated evidence.

## 8.5 Security-Specific Events

Halts, suspensions, delayed openings, and delistings require explicit event evidence. They do not authorise silent calendar mutation or fabricated prices.

---

# 9. Bar Price and Field Meaning

## 9.1 OHLC Meaning

For one approved source scope and adjustment basis:

- `open` is the first eligible regular-session price in the governed `D1` interval;
- `high` is the maximum eligible price;
- `low` is the minimum eligible price;
- `close` is the final eligible price;
- `volume` is eligible traded share quantity within the same declared source scope, when supplied.

## 9.2 Source Scope

A lane MUST explicitly identify whether evidence is:

- primary-venue specific;
- named-venue specific;
- approved consolidated market evidence;
- another expressly approved scope.

These scopes are not interchangeable.

## 9.3 Session Scope

Version 1 canonical bars are `REGULAR_SESSION_ONLY`.

Pre-market, post-market, overnight, and mixed-session bars require separate authority and separate evidence lanes.

## 9.4 Adjustment Basis

Adjustment basis is part of lane identity. Controlled values MAY include:

- `UNADJUSTED`;
- `SPLIT_ADJUSTED`;
- `SPLIT_AND_DIVIDEND_ADJUSTED`;
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

- provider and provider symbol;
- primary-venue or consolidated source scope;
- declared regular-session scope, including whether evidence is continuous-trading-only or auction-inclusive;
- price basis;
- adjustment basis;
- listing currency;
- price-display unit;
- volume scope;
- timestamp meaning;
- effective range.

A daily bar that includes extended-hours trades MUST NOT enter the Version 1 regular-session D1 lane.

## 10.3 Derived D1

Derived D1 evidence is permitted only when every expected regular-session child interval is present or authoritatively explained and all contributors share:

- the same registered security identity;
- session date;
- source provider, trading service, and venue/consolidated scope;
- regular-session scope;
- listing currency;
- price-display unit;
- price basis;
- adjustment basis;
- corporate-action segment;
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

For an ordinary 08:00–16:30 session, a complete derived D1 bar requires:

```text
9 H1 session intervals, or
17 M30 intervals, or
102 M5 intervals
```

The H1 set includes eight complete 60-minute intervals and the complete 16:00–16:30 session-end interval.

Early-close and exceptional-session counts MUST come from the official calendar.

## 10.5 Adjustment Restriction

An unadjusted intraday lane may derive only an unadjusted D1 lane.

Fragarach MUST NOT create split-adjusted or dividend-adjusted D1 bars during timeframe rollup. Adjustment is a separate, explicitly authorised corporate-action transformation with its own provenance.

## 10.6 Closing Auction

Where the registered lane scope is `AUCTION_INCLUSIVE_REGULAR_SESSION`, the relevant opening or closing uncrossing observations MUST be assigned only under approved source semantics.

A derived D1 bar MUST NOT be labelled auction-inclusive unless the required auction evidence is present. A `REGULAR_CONTINUOUS_ONLY` D1 bar remains complete without auction evidence when all continuous-session intervals are complete.

## 10.7 Forbidden Construction

Fragarach MUST NOT:

- mix continuous trading, auctions, off-book reports, or alternative sessions;
- mix venue-specific and consolidated evidence;
- mix adjusted and unadjusted contributors;
- mix providers within one bar;
- fill missing intervals with the previous close;
- create a no-trade bar without source evidence;
- infer corporate actions from price discontinuities.

---

# 11. Bar Completion Authority

## 11.1 Closed D1 Bar

A D1 bar is closed only when:

1. the official regular session has ended;
2. the approved closing-auction process for the lane scope has completed;
3. the provider's approved finalisation latency has elapsed or final status is proven;
4. the bar maps to an official trading date;
5. validation has completed.

## 11.2 Latest Closed Bar

The latest closed D1 bar is the greatest approved session date satisfying Section 11.1.

A row for the current session remains `OPEN` or `PROVISIONAL` until closure and finalisation are proven.

## 11.3 Corrections

A later official or provider correction does not rewrite immutable evidence. It creates a new evidence event and may update the active read model through approved conflict resolution.

---

# 12. Request and Response Authority

## 12.1 Twelve Data Request Contract

The approved automated request uses `/time_series` with:

| Parameter | Approved Value or Rule |
|---|---|
| `symbol` | Registered Twelve Data provider symbol |
| `interval` | `1day` |
| `timezone` | `Europe/London` |
| `order` | `asc` |
| `format` | `JSON` |
| `start_date` | Desired first primary-venue trading date |
| `end_date` | Civil date after the final requested trading date |
| `outputsize` | MUST be omitted when both bounded dates are supplied |
| authentication | Approved secret mechanism; secret MUST NOT enter logs or evidence payloads |

For desired inclusive canonical opens or owner dates `[S, E]`:

```text
start_date = S represented in Europe/London
end_date   = E + one calendar day represented in Europe/London
```

The response MUST then be canonically filtered to the approved requested range. Boundary inclusivity MUST NOT be assumed.

A provider response MUST prove its regular-session, auction, off-book, and alternative-session scope. If incompatible observations cannot be deterministically separated, the provider path is incompatible for the affected lane.

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
- continuous-trading, auction, off-book, and alternative-session scopes are not silently merged;
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
- security and primary-venue identity;
- provider interval and request timezone;
- source venue, trading service, or consolidated scope;
- regular-session scope;
- adjustment, price basis, listing currency, and price-display unit;
- requested local and UTC start/end;
- expected canonical interval count;
- returned and accepted counts;
- extended-hours, future, invalid, and misaligned counts;
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

Every `D1` evidence lane MUST materialise an exact effective range for the registered security, provider symbol, primary venue, source scope, session scope, adjustment basis, listing currency, price-display unit, and provider interval.

## 13.2 Effective Start

The effective start is the latest of:

- the security's approved listing or identity-segment start;
- provider mapping start;
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
- adjustment-basis segment end;
- approved operational retirement.

## 13.4 No Invented History

Fragarach MUST NOT expect evidence before the effective start or after the effective end.

Ticker reuse, relisting, mergers, reorganisations, and share-class changes require explicit segmentation rather than silent history joining.

---

# 14. Expected Bars and Gap Authority

## 14.1 Expected Set

The expected `D1` set consists of one bar on each official primary-venue trading day within the lane effective range.

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
- security-specific halt or suspension;
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

Rows are exact duplicates only when canonical identity, timestamp, OHLC, volume, venue/consolidated scope, session scope, adjustment basis, listing currency, price-display unit, and relevant provenance values agree.

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

## 16.1 Listing Currency and Price-Display Unit

Listing currency and price-display unit are separate material lane facts.

Prices MUST remain in the registered price-display unit. For sterling-listed securities this may be:

- `GBP` — pounds sterling;
- `GBX` — pence sterling;
- another expressly registered currency or subunit.

The arithmetic relationship:

```text
100 GBX = 1 GBP
```

does not authorise silent conversion.

Any conversion requires a separately authorised transformation lane that records source unit, target unit, exact factor, retained original evidence, transformation authority, and provenance.

A material 100-fold discrepancy MUST be investigated as possible `GBP`/`GBX` confusion and MUST NOT be normalised by assumption.

## 16.2 Price Basis

Trade, official auction, on-book, off-book, consolidated, venue-specific, adjusted, and unadjusted price bases MUST remain explicit and compatible with the lane contract.

Auction-inclusive and continuous-trading-only evidence MUST NOT be silently merged.

## 16.3 Volume

Volume means eligible traded security units within the declared source, venue, trading-service, reporting, and session scope.

Primary-venue on-book volume, off-book reported volume, consolidated volume, turnover value, and provider-estimated volume are not interchangeable.

Volume MUST be `NULL` when unavailable or semantically incompatible. It MUST NOT be replaced with zero merely to satisfy a schema.

## 16.4 Corporate Actions

Subdivision, consolidation, dividend, capital distribution, rights issue, demerger, scheme of arrangement, takeover, cancellation, readmission, depositary-interest or receipt-ratio, and other corporate-action effects MUST remain governed by explicit adjustment and identity authority.

Timeframe construction alone does not authorise adjustment.

## 16.5 Precision

Decimal values MUST be preserved without avoidable binary floating-point loss. Rounding is permitted only at approved presentation or storage precision boundaries and MUST NOT alter source evidence.

---

# 17. Validation Authority

## 17.1 Validator Identity

The mandatory validator is:

```text
UK_EQUITIES_D1_VALIDATOR_V1
```

## 17.2 Mandatory Checks

The validator MUST prove:

- registered security identity and active effective segment;
- market code `EQUITIES_UK` and timeframe `D1`;
- primary venue, market segment or trading service, and calendar authority;
- provider symbol and source scope;
- declared regular-session scope, including whether evidence is continuous-trading-only or auction-inclusive;
- timestamp meaning and timezone mapping;
- the semantic date label equals the approved venue trading date;
- official session open, close, holiday, and early-close mapping validate;
- OHLC numeric validity: `low <= open <= high`, `low <= close <= high`, and `low <= high`;
- price precision, listing-currency, and price-display-unit consistency;
- detection of material `GBP`/`GBX` scale confusion;
- adjustment-basis consistency;
- non-negative volume when volume is present;
- monotonic canonical ordering;
- duplicate and conflict classification;
- effective-range membership;
- closed, open, provisional, or corrected state;
- immutable evidence and acquisition provenance;
- no silent auction, off-book, or alternative-session contamination;
- no silent corporate-action transformation.

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
- source, adjustment, and session-scope summary;
- Current-As-Of Truth;
- compatibility findings.

Validation failure blocks only the affected candidate or lane. It MUST NOT block unrelated operations.

---

# 18. Evidence Lane Contract

## 18.1 Mandatory Lane Identity

An active `D1` lane MUST bind at least:

- registered instrument identity;
- market `EQUITIES_UK`;
- timeframe `D1`;
- primary venue, market segment or trading service, and calendar authority;
- provider and provider symbol;
- source venue, trading service, or consolidated scope;
- explicit session scope such as `REGULAR_CONTINUOUS_ONLY` or `AUCTION_INCLUSIVE_REGULAR_SESSION`;
- price basis;
- adjustment basis;
- listing currency;
- price-display unit;
- timestamp meaning;
- construction method;
- effective range;
- validator `UK_EQUITIES_D1_VALIDATOR_V1`;
- approval and activation state.

## 18.2 Activation Gate

A lane may become active only when:

1. instrument registration is approved;
2. provider mapping, venue scope, trading service, and price-display unit are approved;
3. calendar and session authority resolve;
4. adjustment basis, listing currency, and price-display unit are explicit;
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
- source, venue, trading-service, session, adjustment, listing-currency, and price-display-unit scope;
- gap and explained-absence status;
- conflict and correction status;
- effective range;
- validator result.

Maintenance state MUST NOT hide otherwise usable evidence.

---

# 19. Operational Freshness Authority

## 19.1 Current-As-Of Truth

Current-As-Of Truth is the end instant or session date of the latest accepted closed `D1` bar, together with its source and validation state.

## 19.2 Freshness States

Implementations MAY expose controlled states such as:

- `GREEN` — latest expected closed interval accepted;
- `AMBER` — usable evidence exists but the live edge is delayed, provisional, or under repair;
- `RED` — no usable accepted evidence for the lane;
- `CLOSED` — venue is outside the approved regular session and no newer closed interval is expected.

`AMBER` remains usable. Freshness warnings MUST NOT blank accepted history.

## 19.3 Expected Live Edge

The expected latest closed interval MUST be calculated from:

- approved primary-venue calendar;
- official session schedule for the trading date;
- current `Europe/London` time;
- interval boundaries under Section 6;
- approved provider finalisation latency.

## 19.4 Non-Blocking Doctrine

Repair, provider failure, stale live edge, missing recent bars, and unresolved lower-priority conflicts MUST remain visible but MUST NOT block unrelated lanes or historical reads.

---

# 20. Provider Precedence

## 20.1 Precedence Classes

Where multiple compatible candidates exist, deterministic precedence SHOULD favour:

1. approved official venue or licensed consolidated evidence;
2. approved direct provider evidence with exact lane compatibility;
3. approved operator-supplied direct evidence;
4. approved derived evidence from complete lower-timeframe contributors.

## 20.2 No Silent Preference

Precedence MUST NOT be inferred from arrival order, longest history, smoothness, highest volume, or provider popularity.

## 20.3 Scope Compatibility

Precedence applies only among candidates with the same security identity, venue/consolidated scope, session scope, adjustment basis, listing currency, price-display unit, timeframe, and effective segment.

---

# 21. Exceptions

Any exception MUST be:

- named;
- effective-dated;
- scoped to specific instruments, venues, providers, or dates;
- justified by evidence;
- approved at the correct authority layer;
- testable;
- visible to operators.

Examples include exceptional market closures, venue schedule changes, security suspensions, ticker changes, corporate-action segments, and provider timestamp deviations.

A recurring exception indicates that this authority requires amendment.

---

# 22. Compatibility Requirements

Before implementation or activation, Fragarach MUST prove compatibility for:

- registered security and primary venue;
- official calendar and session schedule;
- provider symbol and exchange mapping;
- regular-session isolation;
- timestamp semantics and alignment;
- source venue, trading service, or consolidated scope;
- adjustment, price basis, listing currency, and price-display unit;
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
- venue and calendar ownership;
- regular-session boundaries;
- interval alignment;
- timestamp meaning;
- session and adjustment scope;
- provider request semantics;
- effective-range rules;
- validation requirements.

---

# 24. Implementation Prohibitions

Implementation MUST NOT:

- invent a primary venue or calendar;
- infer security identity solely from ticker text;
- merge regular and extended hours;
- mix primary-venue and consolidated evidence silently;
- mix continuous-trading, auction, trade-at-last, off-book, or alternative-session evidence silently;
- treat `GBP` and `GBX` values as interchangeable;
- mix adjusted and unadjusted bars;
- create corporate-action adjustments without authority;
- fabricate no-trade bars;
- fill gaps with previous closes;
- force provider timestamps onto an incompatible grid;
- treat official holidays or early closes as ordinary gaps;
- silently overwrite conflicting evidence;
- join histories across ticker reuse or identity changes;
- expose secrets in logs or evidence;
- block unrelated operations because one lane is incompatible.

---

# 25. Amendment and Versioning

A new major version is required when changing:

- regular-session scope;
- timestamp meaning;
- interval alignment;
- adjustment doctrine;
- listing-currency or price-display-unit doctrine;
- auction, off-book, and trading-service scope;
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

- reviewed against `UK_EQUITIES_BASE_DOCTRINE_V1`;
- tested with representative London Stock Exchange Main Market- and AIM-listed securities;
- tested across ordinary sessions, official holidays, and early closes;
- tested across daylight-saving offsets;
- tested with adjusted and unadjusted evidence kept separate;
- tested across ticker or corporate-action boundaries;
- approved by the constitutional authority owner;
- recorded with approval date and effective date.

Until then, status remains `DRAFT FOR APPROVAL`.

---

# 27. Acceptance Statement

Approval of `UK_EQUITIES_D1_AUTHORITY_V1` means Fragarach II accepts this document as the constitutional source of truth for United Kingdom Equities `D1` evidence.

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

- London Stock Exchange official trading-hours and business-days records: regular trading from 08:00 to 16:30 London time, with official calendar, auction, early-close, and exceptional-day schedules;
- Twelve Data API documentation: `/time_series`, intervals `1day`, bounded date requests, ascending order, timezone selection, `/earliest_timestamp`, and documented maximum response size of 5,000 records.

These references describe external interfaces and schedules. They do not override this authority, the parent doctrine, registered instrument metadata, or effective-dated venue calendar records.

Provider behaviour that differs from the approved contract is a compatibility event, not permission for implementation to reinterpret authority.

---

# 29. Governing Principle

> Constitution defines what is true.  
> Authority defines the approved operational meaning.  
> Specification defines how Fragarach implements that meaning.  
> Implementation must never invent authority.

**Operations is King.**
