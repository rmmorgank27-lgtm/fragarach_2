# US EQUITIES M30 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority  
**Authority Layer:** Market Timeframe  
**Authority Name:** `US_EQUITIES_M30_AUTHORITY_V1`  
**Market Name:** United States Equities  
**Market Code:** `EQUITIES_US`  
**Timeframe:** `M30`  
**Version:** 1.0  
**Status:** DRAFT FOR APPROVAL  
**Repository Location:** `constitution/authorities/equities_us/US_EQUITIES_M30_AUTHORITY_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Authority:** `constitution/doctrines/US_EQUITIES_BASE_DOCTRINE_V1.md`  
**Effective From:** Not effective until approved  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** PENDING  
**Approval Date:** PENDING

---

# 1. Purpose

This authority defines the approved operational truth for `M30` evidence within the United States Equities market ecosystem of Fragarach II.

It establishes:

- what one US-equities `M30` bar represents;
- primary-venue calendar and regular-session ownership;
- exact timestamp and interval semantics;
- direct-provider and approved construction rules;
- adjusted and unadjusted lane separation;
- bar completion and latest-closed-bar calculations;
- Twelve Data request, response, chunking, and history contracts;
- effective-range materialisation;
- expected-bar, halt, gap, duplicate, conflict, repair, and freshness rules;
- the `US_EQUITIES_M30_VALIDATOR_V1` validation contract;
- evidence-lane activation and operational eligibility.

This authority does not define database schemas, storage implementation, client architecture, native application layout, migration procedure, or acceptance-test code. Those matters belong to specifications that consume this authority.

---

# 2. Constitutional Position

```text
Constitution

↓

US_EQUITIES_BASE_DOCTRINE_V1

↓

US_EQUITIES_M30_AUTHORITY_V1

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides all subordinate documents;
2. `US_EQUITIES_BASE_DOCTRINE_V1` overrides this authority;
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

- securities registered under market code `EQUITIES_US`;
- timeframe code `M30`;
- the registered instrument's approved primary-venue calendar;
- Version 1 `REGULAR_SESSION_ONLY` evidence;
- evidence whose provider, symbol mapping, venue or consolidated scope, adjustment basis, timestamp meaning, and effective range are known;
- direct `M30` evidence and only the derived methods expressly permitted in Section 10.

## 4.2 Excluded Scope

This authority does not govern:

- pre-market, post-market, overnight, or mixed-session evidence;
- ETFs, funds, preferred stock, warrants, options, futures, indices, CFDs, or OTC securities not admitted by the parent doctrine;
- foreign ordinary shares not registered under `EQUITIES_US`;
- another timeframe;
- provider data whose session, venue, adjustment, or timestamp semantics are unresolved;
- bars outside the approved listing and provider effective range.

## 4.3 Inherited Market Truth

This authority inherits without modification:

- regulated multi-venue US-equities market identity;
- explicit security, share-class, and primary-listing identity;
- `America/New_York` calendar timezone;
- official primary-venue calendar authority;
- ordinary 09:30–16:00 regular-session default;
- official holiday, early-close, halt, suspension, and exceptional-closure treatment;
- regular and extended-hours separation;
- adjusted and unadjusted lane separation;
- corporate-action and ticker-continuity authority;
- immutable evidence and non-blocking operations doctrine.

---

# 5. Canonical Timeframe Definition

## 5.1 Timeframe Identity

**Timeframe Code:** `M30`  
**Nominal Duration:** Thirty minutes, with an approved session-end shortened interval when required  
**Duration in Minutes:** `30 nominal`  
**Time Unit:** `MINUTE`  
**Interval Type:** `HYBRID_SESSION_ALIGNED`

## 5.2 Approved Definition

One canonical US-equities `M30` bar represents a half-open interval inside the approved primary-venue regular trading session:

```text
[canonical interval open, canonical interval end)
```

Intervals begin at the official regular-session open and advance in exact 30-minute increments. The final interval of a session closes at the official regular-session close even when it is shorter than 30 minutes.

A shortened final interval created by the official session boundary is a complete canonical session-end bar. It is not an incomplete or provisional bar merely because its elapsed duration is shorter than the nominal timeframe.

## 5.3 Bar Meaning

A complete US-equities `M30` bar contains one approved source scope's regular-session OHLC and compatible volume for one registered security and one adjustment basis.

A bar MAY originate through `DIRECT_PROVIDER_M30`, `DIRECT_OPERATOR_M30` or `DERIVED_FROM_M5`.

Security identity, provider, venue scope, session scope, adjustment basis, source timestamp, canonical timestamp, acquisition run, corporate-action segment, and effective range MUST remain explicit in provenance.

## 5.4 Expected Counts

Expected intervals are calculated from the approved session schedule:

```text
expected_count = ceiling((official session close - official session open) / 30 minutes)
```

For the ordinary 09:30–16:00 regular session:

```text
Expected M30 bars = 13
```

For the common 09:30–13:00 official early-close session:

```text
Expected M30 bars = 7
```

No universal count may override an effective-dated official venue schedule.

---

# 6. Interval Alignment Authority

## 6.1 Alignment Origin

The alignment origin is the official regular-session opening time for the registered instrument's primary venue and trading date.

The ordinary default is:

```text
09:30:00 America/New_York
```

Intervals advance in exact 30-minute increments until the official session close.

## 6.2 Boundary Rule

Every canonical interval uses:

```text
[start, end)
```

An observation exactly at `end` belongs to the next interval, except an approved closing-auction observation assigned by the source to the final regular-session interval.

## 6.3 Alignment Formula

For session open `O`, session close `C`, and interval index `n`:

```text
interval_open(n) = O + n × 30 minutes
interval_end(n)  = min(O + (n + 1) × 30 minutes, C)
```

An interval exists only when:

```text
interval_open(n) < C
```

## 6.4 Ordinary Session Examples

For an ordinary 09:30–16:00 session:
- first bar: 09:30–10:00;
- final bar: 15:30–16:00;
- all 13 intervals are full 30-minute intervals.

## 6.5 Official Early Closes

The same formula applies to an official early close. The final interval closes exactly at the approved session close and MAY be shorter than 30 minutes.

## 6.6 Daylight-Saving Treatment

Every interval boundary MUST be resolved under historical IANA `America/New_York` rules and converted to UTC.

Implementation MUST NOT use a fixed UTC offset.

## 6.7 Extended Hours and Halts

Pre-market, post-market, overnight, and other extended-hours observations are outside this Version 1 regular-session authority.

A symbol-specific halt does not remove the canonical interval from the schedule. A no-trade interval MAY be classified as `EXPLAINED_HALT` only when authoritative halt evidence exists. Fragarach MUST NOT manufacture a flat bar.

---

# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `INTERVAL OPEN`  
**Canonical Storage Timezone:** `UTC`

The canonical timestamp is the exact UTC instant at which the approved regular-session interval opens.

## 7.2 Required Companion Ownership

Every canonical row MUST also resolve:

- `session_date` in `America/New_York`;
- `interval_end` in UTC;
- primary venue and calendar authority;
- regular-session scope;
- source timezone;
- source timestamp meaning;
- timestamp-mapping method.

## 7.3 Provider Timestamp Mapping

| Source | Source Timestamp Meaning | Source Timezone | Canonical Mapping | Conditions |
|---|---|---|---|---|
| Twelve Data `30min` | Provider intraday label proven to represent interval open | Request `America/New_York` | Validate against canonical session grid, then convert to UTC | Symbol, venue scope, session scope, adjustment basis, and effective range MUST validate |
| Operator-supplied direct `M30` file | Declared interval open or unambiguous equivalent | MUST be declared | Convert to UTC and calculate session owner | Ambiguous labels are rejected |
| Existing accepted immutable `M30` evidence | Recorded accepted meaning | As recorded | Preserve canonical open and provenance | No silent reinterpretation |
| Derived evidence | First contributing canonical interval open | UTC | Preserve first child open | Section 10 MUST be satisfied |

## 7.4 Direct-Provider Compatibility

A direct provider row is eligible only when its labels align to the primary-venue regular-session grid established in Section 6.

Rows aligned to civil clock hours, extended-hours sessions, or another venue schedule MUST NOT be forced onto the canonical grid.

## 7.5 Date-Only Values

**Date-Only Allowed:** `NO`

A date without time cannot identify a `M30` interval.

## 7.6 Ambiguous or Invalid Timestamps

Implementation MUST NOT guess when timezone, open-versus-close meaning, venue schedule, or session scope is unresolved.

The candidate MUST be retained as incompatible evidence and excluded from active use.

---

# 8. Trading-Day and Session Ownership

## 8.1 Owner Date

Every canonical `M30` bar is owned by the approved primary venue's `America/New_York` trading date.

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

- `open` is the first eligible regular-session price in the governed `M30` interval;
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

An M30 bar MAY be accepted through:

1. `DIRECT_PROVIDER_M30`;
2. `DIRECT_OPERATOR_M30`;
3. `DERIVED_FROM_M5`.

## 10.2 Derived M30

A full M30 interval requires six complete M5 bars.

If an approved exceptional session close creates a shorter final M30 interval, all canonical M5 children inside that shortened interval are required.

## 10.3 Contributor Identity

All contributors MUST share security, provider, venue/consolidated scope, regular-session scope, currency, price basis, adjustment basis, corporate-action segment, and effective range.

## 10.4 Aggregation

```text
open   = first child open
high   = maximum child high
low    = minimum child low
close  = last child close
volume = sum of compatible child volume, otherwise NULL
```

## 10.5 Completeness and Prohibitions

Missing children MUST NOT be filled. Cross-provider, cross-venue-scope, cross-session, cross-adjustment, and extended-hours construction are prohibited.

---

# 11. Bar Completion Authority

## 11.1 Closed `M30` Bar

A `M30` bar is closed only when:

1. its canonical interval end is at or before the official session close;
2. current time is later than the interval end;
3. the provider's approved publication latency has elapsed or final status is proven;
4. any required auction assignment for the final interval is complete;
5. validation has completed.

## 11.2 Session-End Interval

A shortened final interval ending at the official session close is complete at that close. It MUST NOT remain open until the nominal 30 nominal duration would have elapsed.

## 11.3 Latest Closed Bar

The latest closed `M30` bar is the greatest canonical interval open whose complete governed interval has closed and validated.

Bars from a future or still-forming interval remain `OPEN` or `PROVISIONAL` and do not advance Current-As-Of Truth.

---

# 12. Request and Response Authority

## 12.1 Twelve Data Request Contract

The approved automated request uses `/time_series` with:

| Parameter | Approved Value or Rule |
|---|---|
| `symbol` | Registered Twelve Data provider symbol |
| `interval` | `30min` |
| `timezone` | `America/New_York` |
| `order` | `asc` |
| `format` | `JSON` |
| `start_date` | Desired first canonical interval-open local datetime |
| `end_date` | Desired final canonical interval-open local datetime plus the governed interval duration |
| `outputsize` | MUST be omitted when both bounded dates are supplied |
| authentication | Approved secret mechanism; secret MUST NOT enter logs or evidence payloads |

For desired inclusive canonical opens or owner dates `[S, E]`:

```text
start_date = S represented in America/New_York
end_date   = E + 30 minutes represented in America/New_York
```

The response MUST then be canonically filtered to the approved requested range. Boundary inclusivity MUST NOT be assumed.

A provider response MUST prove regular-session scope. If it includes extended-hours observations and those observations cannot be deterministically separated, the provider path is incompatible.

## 12.2 Chunk Ceiling

Twelve Data documents a maximum of 5,000 returned records.

Fragarach's constitutional ceiling is:

```text
maximum 4,000 expected M30 intervals per request
```

The default chunk span MUST NOT exceed:

```text
300 full regular trading sessions
```

and MUST be shortened where required to remain at or below 4,000 expected rows.

## 12.3 Chunk Overlap

Adjacent chunks MUST overlap by at least:

```text
26 expected M30 intervals, equal to two normal regular sessions
```

Overlap provides deterministic reassembly, correction detection, and corporate-action boundary evidence.

## 12.4 Incremental Acquisition

An incremental request SHOULD begin at least:

```text
26 expected M30 intervals
```

before the latest accepted closed interval and continue through the interval immediately after the latest expected closed interval, followed by canonical filtering.

## 12.5 Response Semantics

An approved response MUST satisfy all of the following:

- metadata and error status are distinguished from value rows;
- symbol and exchange or venue metadata are retained where supplied;
- regular-session and extended-hours scope are not silently merged;
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
- source venue or consolidated scope;
- regular-session scope;
- adjustment and price basis;
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

Every `M30` evidence lane MUST materialise an exact effective range for the registered security, provider symbol, primary venue, source scope, session scope, adjustment basis, and provider interval.

## 13.2 Effective Start

The effective start is the latest of:

- the security's approved listing or identity-segment start;
- provider mapping start;
- provider `M30` availability start;
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

The expected `M30` set consists of the intervals generated from the approved primary-venue regular-session schedule within the lane effective range.

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

A missing interval is not automatically a market closure. Official halts, delayed openings, early closes, suspensions, and no-trade conditions require evidence-backed classification.

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

## 16.1 Currency

Prices MUST remain in the registered listing currency unless a separately authorised currency-conversion lane exists.

## 16.2 Price Basis

Trade, official auction, consolidated, venue-specific, adjusted, and unadjusted price bases MUST remain explicit and compatible with the lane contract.

## 16.3 Volume

Volume means eligible traded security units within the declared source and session scope.

Primary-venue volume, consolidated volume, and provider-estimated volume are not interchangeable.

Volume MUST be `NULL` when unavailable or semantically incompatible. It MUST NOT be replaced with zero merely to satisfy a schema.

## 16.4 Corporate Actions

Split, dividend, distribution, merger, spin-off, rights, depositary-ratio, and other corporate-action effects MUST remain governed by explicit adjustment and identity authority.

Timeframe construction alone does not authorise adjustment.

## 16.5 Precision

Decimal values MUST be preserved without avoidable binary floating-point loss. Rounding is permitted only at approved presentation or storage precision boundaries and MUST NOT alter source evidence.

---

# 17. Validation Authority

## 17.1 Validator Identity

The mandatory validator is:

```text
US_EQUITIES_M30_VALIDATOR_V1
```

## 17.2 Mandatory Checks

The validator MUST prove:

- registered security identity and active effective segment;
- market code `EQUITIES_US` and timeframe `M30`;
- primary venue and calendar authority;
- provider symbol and source scope;
- regular-session-only scope;
- timestamp meaning and timezone mapping;
- interval open and end match the approved session-derived grid;
- the session-end shortened interval, where present, ends exactly at the official close;
- OHLC numeric validity: `low <= open <= high`, `low <= close <= high`, and `low <= high`;
- price precision and currency consistency;
- adjustment-basis consistency;
- non-negative volume when volume is present;
- monotonic canonical ordering;
- duplicate and conflict classification;
- effective-range membership;
- closed, open, provisional, or corrected state;
- immutable evidence and acquisition provenance;
- no silent extended-hours contamination;
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

An active `M30` lane MUST bind at least:

- registered instrument identity;
- market `EQUITIES_US`;
- timeframe `M30`;
- primary venue and calendar authority;
- provider and provider symbol;
- source venue or consolidated scope;
- session scope `REGULAR_SESSION_ONLY`;
- price basis;
- adjustment basis;
- listing currency;
- timestamp meaning;
- construction method;
- effective range;
- validator `US_EQUITIES_M30_VALIDATOR_V1`;
- approval and activation state.

## 18.2 Activation Gate

A lane may become active only when:

1. instrument registration is approved;
2. provider mapping and venue scope are approved;
3. calendar and session authority resolve;
4. adjustment basis is explicit;
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
- source, venue, session, and adjustment scope;
- gap and explained-absence status;
- conflict and correction status;
- effective range;
- validator result.

Maintenance state MUST NOT hide otherwise usable evidence.

---

# 19. Operational Freshness Authority

## 19.1 Current-As-Of Truth

Current-As-Of Truth is the end instant or session date of the latest accepted closed `M30` bar, together with its source and validation state.

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
- current `America/New_York` time;
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

Precedence applies only among candidates with the same security identity, venue/consolidated scope, session scope, adjustment basis, currency, timeframe, and effective segment.

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
- source venue or consolidated scope;
- adjustment and price basis;
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

- reviewed against `US_EQUITIES_BASE_DOCTRINE_V1`;
- tested with representative NYSE- and Nasdaq-listed securities;
- tested across ordinary sessions, official holidays, and early closes;
- tested across daylight-saving offsets;
- tested with adjusted and unadjusted evidence kept separate;
- tested across ticker or corporate-action boundaries;
- approved by the constitutional authority owner;
- recorded with approval date and effective date.

Until then, status remains `DRAFT FOR APPROVAL`.

---

# 27. Acceptance Statement

Approval of `US_EQUITIES_M30_AUTHORITY_V1` means Fragarach II accepts this document as the constitutional source of truth for United States Equities `M30` evidence.

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

- NYSE official Holidays & Trading Hours record: Core Trading Session 09:30–16:00 Eastern Time, with official calendar and early-close schedules;
- Twelve Data API documentation: `/time_series`, intervals `30min`, bounded date requests, ascending order, timezone selection, `/earliest_timestamp`, and documented maximum response size of 5,000 records.

These references describe external interfaces and schedules. They do not override this authority, the parent doctrine, registered instrument metadata, or effective-dated venue calendar records.

Provider behaviour that differs from the approved contract is a compatibility event, not permission for implementation to reinterpret authority.

---

# 29. Governing Principle

> Constitution defines what is true.  
> Authority defines the approved operational meaning.  
> Specification defines how Fragarach implements that meaning.  
> Implementation must never invent authority.

**Operations is King.**
