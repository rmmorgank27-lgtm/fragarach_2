# FX M30 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority  
**Authority Layer:** Market Timeframe  
**Authority Name:** `FX_M30_AUTHORITY_V1`  
**Market Name:** Foreign Exchange  
**Market Code:** `FX`  
**Timeframe:** `M30`  
**Version:** 1.0  
**Status:** DRAFT FOR APPROVAL  
**Repository Location:** `constitution/authorities/fx/FX_M30_AUTHORITY_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Authority:** `constitution/doctrines/FX_BASE_DOCTRINE_V1.md`  
**Effective From:** Not effective until approved  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** PENDING  
**Approval Date:** PENDING

---

# 1. Purpose

This authority defines the approved operational truth for `M30` evidence within the Foreign Exchange market ecosystem of Fragarach II.

It establishes:

- what one FX `M30` bar represents;
- exact New York rollover-relative interval alignment;
- canonical UTC interval-open timestamps and close-date session ownership;
- direct-provider and, where authorised, lower-timeframe construction rules;
- bar completion and latest-closed-bar calculations;
- concrete Twelve Data request, response, chunking, and history contracts;
- effective-range materialisation;
- expected-bar, gap, duplicate, conflict, repair, and freshness rules;
- the `FX_M30_VALIDATOR_V1` validation contract;
- evidence-lane activation and operational eligibility.

This authority does not define database schemas, client architecture, storage implementation, native application layout, migration procedure, or acceptance-test code.

Those matters belong to specifications that consume this authority.

---

# 2. Constitutional Position

```text
Constitution

↓

FX_BASE_DOCTRINE_V1

↓

FX_M30_AUTHORITY_V1

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides all subordinate documents;
2. `FX_BASE_DOCTRINE_V1` overrides this authority;
3. this authority overrides implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing operational facts.

Legacy code, provider defaults, sample files, and historical application behaviour are not authority unless expressly adopted here or by the parent doctrine.

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

- instruments registered under market code `FX`;
- timeframe code `M30`;
- intervals within `FX_24X5_NEW_YORK_ROLLOVER_V1`;
- evidence whose provider, price basis, timestamp meaning, and effective range are known;
- direct `M30` provider or operator-supplied evidence;
- derived `M30` evidence only where Section 10 explicitly permits it.

## 4.2 Excluded Scope

This authority does not govern:

- metals such as `XAUUSD` or `XAGUSD`;
- cryptoassets;
- exchange-traded currency futures;
- any timeframe other than `M30`;
- synthetic FX crosses not separately authorised;
- provider data whose interval semantics or price basis are unresolved;
- bars wholly inside the canonical Friday-to-Sunday weekend closure.

## 4.3 Inherited Market Truth

This authority inherits without modification:

- FX market identity and base/quote semantics;
- decentralised multi-venue OTC status;
- `America/New_York` calendar timezone;
- Sunday 17:00 operational-week open;
- Friday 17:00 operational-week close;
- 17:00 New York daily rollover;
- close-date trading-day ownership;
- immutable evidence doctrine;
- declared price-basis requirement;
- non-centralised volume doctrine;
- market-wide validation and structural-event rules.

---

# 5. Canonical Timeframe Definition

## 5.1 Timeframe Identity

**Timeframe Code:** `M30`  
**Nominal Duration:** Thirty minutes  
**Duration in Minutes:** `30`  
**Time Unit:** `MINUTE`  
**Interval Type:** `HYBRID`

The bar duration is fixed, but valid intervals exist only inside the session-derived FX operational week and are owned under the 17:00 New York rollover model.

## 5.2 Approved Definition

One canonical FX `M30` bar represents the half-open interval:

```text
[canonical interval open, canonical interval open + 30 minutes)
```

The interval open MUST satisfy:

```text
local minute ∈ {00, 30} and local second = 00
```

in `America/New_York`, and the interval MUST lie wholly inside an owned FX trading day.

## 5.3 Bar Meaning

A complete FX `M30` bar contains one approved source's declared price-basis OHLC for exactly thirty minutes.

A bar MAY originate through `DIRECT_PROVIDER_M30`, `DIRECT_OPERATOR_M30`, or `DERIVED_FROM_M5`.

The construction method, provider, provider symbol, price basis, source timestamp, canonical timestamp, session owner, acquisition run, and effective segment MUST remain explicit in provenance.

There is no separate extended-hours category for spot FX.

## 5.4 Expected Counts

Absent an approved exception:

```text
Expected bars per FX trading day = 48
Expected bars per FX week        = 240
```

The weekend closure contains no expected `M30` intervals.

---

# 6. Interval Alignment Authority

## 6.1 Alignment Origin

The alignment origin is each FX trading-day boundary at:

```text
17:00:00 America/New_York
```

Intervals advance in exact 30-minute increments from that boundary until the next 17:00 boundary.

## 6.2 Boundary Rule

Every canonical bar uses:

```text
[start, end)
```

An observation exactly at `end` belongs to the next interval.

An interval beginning exactly at 17:00 belongs to the next owned FX trading day.

## 6.3 Alignment Formula

A local interval open is aligned only when it has minute `00` or `30`, second `00`, and fractional second `0` and lies within the canonical FX operational week.

Equivalent owner-date rule for a local interval open `t`:

```text
owner_date(t) = the New York civil date D for which
                D-1 at 17:00 <= t < D at 17:00
```

The canonical interval end is:

```text
interval_end = interval_open + 30 elapsed minutes
```

Timezone conversion MUST use the IANA rules applicable to the historical instant.

## 6.4 Daily Boundary Examples

For every normal owned date:

- the first `M30` bar opens at `17:00` on the preceding New York civil date;
- the final `M30` bar opens at `16:30` on the owned New York civil date;
- the final bar closes exactly at 17:00;
- the bar opening at 17:00 belongs to the next owner date.

Concrete test vectors:

```text
Summer final-bar open: 2026-07-06 16:30 America/New_York = 2026-07-06T20:30:00Z
Winter first-week open: 2026-01-04 17:00 America/New_York = 2026-01-04T22:00:00Z
```

These examples prove that implementation MUST NOT use a fixed UTC offset.

## 6.5 Week Boundaries

- The final normal weekly interval opens Friday at `16:30` New York and closes Friday at 17:00.
- No interval opens after Friday 17:00 and before Sunday 17:00.
- The first normal weekly interval opens Sunday at 17:00 and is owned by Monday.
- A provider row inside the weekend closure is not canonical FX `M30` evidence unless a named exception exists.

## 6.6 Daylight-Saving Treatment

New York daylight-saving transitions normally occur during the weekend closure, before the Sunday 17:00 reopen.

The applicable IANA offset MUST be used at every interval open and close.

No duplicate, skipped, or stretched intraday bar may be invented to preserve a fixed UTC wall-clock grid.

## 6.7 Partial Intervals

A shortened or incomplete interval caused by provider outage, acquisition interruption, instrument launch, exceptional closure, or incomplete source coverage MUST NOT be silently promoted to a complete bar.

It MAY be retained as `PARTIAL` or `PROVISIONAL` with visible provenance.

There is no generic FX early-close rule.

---

# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `INTERVAL OPEN`  
**Canonical Storage Timezone:** `UTC`

The canonical timestamp is the exact UTC instant at which the interval opens.

Example form:

```text
YYYY-MM-DDTHH:MM:SSZ
```

It is not a provider receipt time, interval-close label, session-date label, or local wall-clock string.

## 7.2 Required Companion Ownership

Every canonical row MUST also resolve:

- `session_date`: New York close-date owner;
- `interval_end`: canonical UTC close instant;
- `source_timezone`;
- `source_timestamp_meaning`;
- `timestamp_mapping_method`.

The canonical timestamp alone does not replace session ownership.

## 7.3 Provider Timestamp Mapping

| Source | Source Timestamp Meaning | Source Timezone | Canonical Mapping | Conditions |
|---|---|---|---|---|
| Twelve Data `30min` | Interval-open local datetime under this authority | Request MUST specify `America/New_York` | Interpret as aligned local interval open, convert to exact UTC instant | Symbol, alignment, price basis, response metadata, and effective range MUST validate |
| Operator-supplied direct `M30` file | Declared interval open or unambiguous equivalent | MUST be declared in manifest | Convert declared interval open to UTC and calculate session owner | Ambiguous timestamps are not accepted |
| Existing accepted immutable `M30` evidence | Existing accepted interval-open meaning | As recorded | Preserve canonical UTC open and ownership | Original provenance remains immutable |
| Derived evidence | Canonical contributing interval opens | UTC | Use the first contributing interval's canonical open | All contributors MUST satisfy Section 10 |

## 7.4 Twelve Data Interpretation Rule

For Fragarach Version 1, an aligned Twelve Data intraday `datetime` returned from a request with `timezone=America/New_York` is interpreted as the interval-open local datetime.

A response that does not conform to this interpretation is incompatible with this provider contract and MUST stop only that provider path with a compatibility report.

Implementation MUST NOT reinterpret the same label as interval close merely to make rows fit.

## 7.5 Date-Only Values

**Date-Only Allowed:** `NO`

A date without a time cannot identify an FX `M30` interval and MUST NOT enter an active `M30` lane.

## 7.6 Ambiguous or Invalid Timestamps

Implementation MUST NOT guess when:

- timezone is absent;
- day/month order is ambiguous;
- source meaning could be open or close;
- the local time is not aligned;
- a timestamp lies in the weekend closure;
- an impossible or ambiguous local wall time cannot be resolved from provenance;
- a timestamp lies outside the effective range.

The candidate MUST be rejected for active use and retained with validation proof.

---

# 8. Trading-Day and Session Ownership

## 8.1 Inherited Rule

This authority inherits Sections 6 and 7 of `FX_BASE_DOCTRINE_V1`.

An FX trading day is owned by the New York civil date on which the session closes at 17:00.

## 8.2 Timeframe-Specific Ownership

A `M30` interval belongs to owner date `D` only when its complete interval lies within:

```text
[D-1 17:00 America/New_York,
 D   17:00 America/New_York)
```

An interval MUST NOT cross an owner-date boundary.

## 8.3 Overnight Session

FX `M30` intervals routinely cross New York civil midnight as a sequence, but each individual fixed-duration interval retains one owner date.

Ownership is determined by the enclosing 17:00-to-17:00 session, never by UTC date or local open date alone.

## 8.4 Week and Month Boundaries

- Sunday 17:00 intervals are owned by Monday.
- Friday final intervals are owned by Friday.
- An interval belongs to the calendar month of its session owner date.
- An interval opening in the preceding month may belong to the next month when its owner date is in that next month.
- Public holidays do not automatically remove expected FX intraday intervals.

---

# 9. Bar Price and Field Meaning

## 9.1 OHLC

For a direct provider bar, OHLC retains the provider's declared `M30` aggregation and price basis.

For an authorised derived bar:

- **Open** MUST equal the first eligible source-bar open.
- **High** MUST equal the maximum eligible source-bar high.
- **Low** MUST equal the minimum eligible source-bar low.
- **Close** MUST equal the final eligible source-bar close before interval end.

## 9.2 Twelve Data Price Basis

Direct Twelve Data FX bars under Version 1 SHALL be classified as:

```text
PROVIDER_AGGREGATE
```

unless a separately approved provider authority establishes a more specific bid, ask, midpoint, or last-price basis.

They MUST NOT be relabelled `BID`, `ASK`, `MIDPOINT`, or `LAST` by inference.

## 9.3 Volume

Spot FX has no universal consolidated volume.

Provider volume retains its declared provider meaning.

Derived volume MAY be summed only when all contributors share one provider, one additive volume meaning, and one price basis.

Otherwise volume MUST be null or unavailable.

Zero, null, and absent volume are distinct states and do not invalidate otherwise valid OHLC evidence.

---

# 10. Bar Construction Authority

## 10.1 Approved Construction Source

**Approved Construction Source:** `EITHER`

FX `M30` evidence may be accepted from an approved direct `M30` source or constructed from the approved lower timeframes listed below.

Approved construction methods are:

```text
DIRECT_PROVIDER_M30
DIRECT_OPERATOR_M30
DERIVED_FROM_M5
```

## 10.2 Lower-Timeframe Construction

An M30 bar may be derived from exactly 6 canonical M5 bars. The contributing sequence MUST begin at the canonical M30 open and end at the canonical M30 close without gaps, overlaps, provider changes, or price-basis changes.

A derived `M30` bar may be classified `CLOSED` only when all 6 M5 bars are present, canonical, closed, contiguous, and eligible.

## 10.3 Source Timeframe Eligibility

| Source Timeframe | Permitted | Conditions | Notes |
|---|---|---|---|
| `M5` | YES, CONDITIONAL | `FX_M5_AUTHORITY_V1` approved; exactly 6 eligible M5 bars; same instrument, provider, price basis, and session owner | Only approved Version 1 rollup source |
| `M1`, `M3`, `M15`, tick | NO under Version 1 | Separate authority required | Retain evidence but do not construct canonical M30 |
| `H1` or higher | NO | Downsampling cannot construct M30 evidence | Not permitted |

## 10.4 Direct Provider Authority

Twelve Data `30min` bars are approved as direct FX `M30` evidence only when:

- the instrument and provider symbol are registered;
- the request uses Section 12 exactly;
- the response timestamp maps as interval open;
- alignment and session ownership validate;
- the price basis is `PROVIDER_AGGREGATE` or another separately approved value;
- the row lies within the materialised effective segment;
- `FX_M30_VALIDATOR_V1` passes.

## 10.5 Direct Versus Derived Precedence

Direct and derived bars remain independent immutable evidence. An existing accepted valid bar retains continuity; validated direct Twelve Data evidence fills uncovered intervals before operator-supplied direct evidence, followed by complete derived evidence. Conflicts never authorise silent overwrite.

## 10.6 Missing Source Bars

If one or more of the required 6 M5 bars are missing, the partial aggregate MAY be retained as `PARTIAL` or `PROVISIONAL`, but it MUST NOT be promoted as a complete canonical `M30` bar.

## 10.7 Cross-Provider Construction

**Cross-Provider Construction Allowed:** `NO`

One derived bar MUST NOT combine providers, price bases, provider symbols, or incompatible effective segments.

## 10.8 Higher-Timeframe Use

Complete eligible `M30` evidence MAY support approved H1 and D1 construction, but only under those higher-timeframe authorities.

---

# 11. Bar Completion Authority

## 11.1 Logical Completion

A canonical `M30` interval is logically closed when:

```text
current instant >= canonical interval end
```

At 16:59:59 New York, the 16:30 M30 interval is still open. At 17:00:00, it is logically closed and the 17:00 interval begins under the next trading-day owner.

Provider publication lag does not alter logical closure.

It alters evidence freshness and acquisition status.

## 11.2 Evidence Completion

A candidate is complete only when:

- its logical interval is closed;
- it is not identified as the provider's current partial bar;
- timestamp, alignment, owner date, and effective range validate;
- OHLC validates;
- source and price basis are declared;
- direct or derived construction requirements pass;
- immutable provenance is complete.

## 11.3 Latest Expected Closed Bar

The latest expected closed `M30` interval is the greatest canonical interval inside the operational week whose interval end is less than or equal to the current instant.

During the weekend closure it remains the Friday interval that closed at 17:00 New York.

After Sunday 17:00, new intervals become expected as they close.

## 11.4 Status Model

| Status | Meaning |
|---|---|
| `OPEN` | Canonical interval has begun but not ended |
| `PARTIAL` | Evidence covers only part of the interval |
| `PROVISIONAL` | Interval ended but source coverage or revision uncertainty remains |
| `CLOSED` | Interval ended and mandatory validation passed |
| `REVISED` | New immutable comparable evidence differs from prior evidence |
| `NOT_EXPECTED` | Interval lies outside the canonical session or approved effective range |

An `OPEN`, `PARTIAL`, or `PROVISIONAL` row MUST NOT be represented as the latest accepted closed bar.

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
| `interval` | `30min` |
| `timezone` | `America/New_York` |
| `order` | `asc` |
| `format` | `JSON` |
| `start_date` | Desired first canonical interval-open local datetime |
| `end_date` | Desired final canonical interval-open local datetime plus 30 minutes |
| `outputsize` | MUST be omitted when both bounded dates are supplied |
| authentication | Approved secret mechanism; secret MUST NOT enter logs or evidence payloads |

For desired inclusive canonical opens `[S, E]`:

```text
start_date = S represented in America/New_York
end_date   = E + 30 minutes represented in America/New_York
```

The response MUST then be canonically filtered to:

```text
S <= canonical interval open <= E
```

This rule removes dependency on undocumented edge inclusivity.

## 12.2 Chunk Ceiling

Twelve Data documents a maximum of 5,000 returned records.

Fragarach's constitutional ceiling is:

```text
maximum 4,000 expected M30 intervals per request
```

The default chunk span MUST NOT exceed:

```text
80 full FX trading days
```

and MUST be shortened when required to keep expected rows at or below 4,000.

## 12.3 Chunk Overlap

Adjacent chunks MUST overlap by at least:

```text
96 expected M30 intervals
```

which equals two full FX trading days.

Overlap provides deterministic reassembly and revision evidence.

## 12.4 Incremental Acquisition

An incremental request SHOULD begin at least `96` expected intervals before the latest accepted closed interval and continue through the interval immediately after the latest expected closed open time, followed by canonical filtering.

This preserves a two-trading-day revision overlap.

## 12.5 Response Semantics

An approved response MUST satisfy all of the following:

- response metadata and error status are distinguished from value rows;
- each row contains a parseable intraday `datetime`;
- each label maps to an aligned interval open under Section 7;
- ascending order is verified rather than assumed;
- numeric strings are parsed without avoidable precision loss;
- rows inside the weekend closure are rejected for active use;
- rows later than the latest expected closed interval are retained only as `OPEN` or `PARTIAL`;
- an empty successful values set means no evidence returned, not proof of market closure;
- an error payload is an acquisition failure, not an empty interval;
- a response reaching a provider row ceiling without complete requested coverage is potentially truncated.

## 12.6 Chunk Reassembly

Chunk responses MUST be reassembled by:

1. preserving every immutable response block;
2. mapping every row to canonical UTC interval open and session owner;
3. filtering to requested canonical opens;
4. sorting ascending by canonical open;
5. comparing overlap rows;
6. collapsing exact repeats only in read models while retaining provenance;
7. retaining conflicting overlap rows as conflict evidence;
8. proving requested, received, duplicate, conflict, future, and uncovered ranges.

## 12.7 Request Coverage Proof

Every acquisition run MUST record:

- instrument and provider symbol;
- provider interval;
- request timezone;
- requested local and UTC start/end;
- expected canonical interval count;
- response source and canonical ranges;
- returned row count;
- accepted closed count;
- open or future count;
- weekend or misaligned count;
- exact duplicate and conflict counts;
- uncovered expected intervals;
- overlap range;
- truncation risk;
- acquisition outcome;
- immutable evidence-block identity.

## 12.8 Provider Limits

Rate limits are account-dependent and are not assigned a fixed constitutional number.

Implementation MUST obey configured entitlement and provider responses and expose throttling, quota, or entitlement failures as acquisition outcomes.

---

# 13. Effective Historical Range

## 13.1 Range Model

**Effective Range Start:** Instrument-, provider-, and timeframe-specific  
**Effective Range End:** `OPEN`

There is no universal FX `M30` start date.

## 13.2 Mandatory Materialisation

Before an evidence lane becomes `ACTIVE`, the exact direct-provider effective start MUST be materialised in lane authority or an authority-linked manifest.

`UNKNOWN`, "provider default", and "all available" are not valid active-lane start values.

The materialised start is the latest of:

1. the registered instrument/regime start;
2. the provider-symbol mapping start;
3. the earliest timestamp returned by Twelve Data `/earliest_timestamp` for the registered symbol and `30min`;
4. the first successfully acquired aligned row at or after that timestamp;
5. any approved instrument/provider exception start.

## 13.3 Provider-Specific Rules

| Source | Effective Start | Effective End | Rule |
|---|---|---|---|
| Twelve Data | Exact immutably recorded result of the procedure above | OPEN through latest available, subject to latest-closed filtering | Earliest endpoint result alone does not prove a valid aligned row |
| Operator-supplied direct file | First validated aligned interval in the file and approved manifest range | Last validated closed interval | Checksum, source identity, timezone, timestamp meaning, and price basis required |
| Existing accepted immutable evidence | Existing accepted first interval | Existing accepted end or OPEN through later evidence | Preserve original provenance |
| Derived evidence | Latest of source-lane effective starts and first fully covered target interval | Latest fully covered target interval | Source authority and complete construction required |

## 13.4 Effective Segments

A material provider aggregation, symbol mapping, price-basis, or timestamp-semantic change creates a new effective segment.

Evidence across incompatible segments MUST NOT be silently treated as one homogeneous series.

## 13.5 History Acquisition

A full backfill SHALL begin at the materialised effective start and proceed in Section 12 chunks through the latest expected closed interval.

A backfill is complete only when every chunk has coverage proof and all uncovered expected intervals are classified.

---

# 14. Expected Bars and Gap Authority

## 14.1 Expected Interval Rule

Within an active effective segment, one `M30` bar is expected at every canonical alignment point from Sunday 17:00 through Friday 17:00 New York, excluding only intervals named by an approved exception.

Expected counts are `48` per trading day and `240` per normal week.

## 14.2 Valid Non-Bar Periods

The following are not gaps:

- Friday 17:00 through Sunday 17:00 weekend closure;
- intervals before effective start;
- intervals after effective end or retirement;
- the current open interval;
- an approved exceptional non-trading interval;
- an interval excluded by a named instrument exception.

## 14.3 Gap Classification

| Classification | Meaning | Operational Consequence |
|---|---|---|
| `NOT_EXPECTED` | No canonical interval should exist | No repair action |
| `EXPECTED_MISSING` | A closed expected interval lacks accepted complete evidence | Warning and repair candidate |
| `SOURCE_UNAVAILABLE` | Requested source could not provide evidence | Continue with best available evidence |
| `PARTIAL_COVERAGE` | Evidence exists but is incomplete | Retain partial; do not promote |
| `CONFLICTING_COVERAGE` | Comparable evidence disagrees | Retain all; no silent overwrite |
| `AUTHORITY_MISSING` | Expectedness, mapping, or range cannot be resolved | Stop only affected path and report compatibility |

## 14.4 Gap Materiality

Every `EXPECTED_MISSING` interval remains a real evidence gap.

Priority is assigned as follows:

- a gap among the latest `96` expected closed `M30` intervals is `HIGH` operational priority;
- consecutive gaps spanning one hour or more are at least `MEDIUM` priority;
- a gap that prevents complete approved higher-timeframe construction is at least `MEDIUM` materiality;
- an older isolated gap with surrounding coverage may be `LOW` materiality;
- no isolated gap invalidates unrelated accepted evidence or blocks the lane read path.

## 14.5 Repair Authority

Permitted repair attempts, in order, are:

1. re-acquire the same interval from the same provider and price basis;
2. use existing accepted immutable evidence;
3. accept a compatible operator-supplied direct `M30` file;
4. use complete approved lower-timeframe construction where Section 10 permits;
5. use another provider only after separate provider authority approval.

Repair MUST create new immutable evidence.

Interpolation, forward-fill, adjacent-bar copying, or fabricated OHLC is prohibited.

---

# 15. Duplicate and Overlap Authority

## 15.1 Comparable Identity

```text
instrument registration
+ timeframe M30
+ canonical UTC interval open
+ session owner
+ price basis
+ provider/source identity
+ construction method
+ effective segment
```

Evidence-block identity remains separately immutable.

## 15.2 Exact Duplicate

Comparable rows are exact duplicates only when aligned identity, OHLC, volume value/null state, volume semantics, completion state, and timestamp mapping are equal after approved numeric normalisation.

Repeated acquisition remains separate provenance even when a read model presents one logical bar.

## 15.3 Conflict

Comparable rows conflict when any OHLC, volume state, completion state, or timestamp mapping differs.

Later acquisition does not automatically win.

## 15.4 Parallel Evidence

Rows for the same interval but different provider, price basis, construction method, or source role are parallel evidence and MUST NOT be silently collapsed as identical authority.

## 15.5 Resolution

Conflicts MUST NOT be resolved by silent overwrite.

The previously accepted valid selected bar MAY continue to serve with visible conflict status until an auditable resolution decision exists.

---

# 16. Price and Volume Semantics

## 16.1 Price Rule

No `M30`-specific smoothing, inversion, interpolation, synthetic-cross creation, or adjustment is authorised.

Each bar remains one declared price basis from one source.

## 16.2 Derived Volume

Derived volume is permitted only under Section 9.3.

## 16.3 Null and Zero

`0`, `NULL`, and absent volume are distinct and MUST remain distinguishable where the source format permits.

---

# 17. Validation Authority

## 17.1 Validator Identity

**Validator Authority:** `FX_M30_VALIDATOR_V1`

This section is normative.

Implementation may encode it but MUST NOT change its meaning.

## 17.2 Mandatory Validation Rules

Every candidate MUST be evaluated for:

- registered FX instrument identity;
- exact `M30` timeframe identity;
- approved source and provider mapping;
- declared price basis;
- parseable source timestamp;
- canonical interval-open UTC mapping;
- minute `00` or `30`, second `00`, and fractional second `0`;
- 17:00 close-date ownership;
- operational-week membership;
- effective-segment eligibility;
- logical completion;
- finite numeric OHLC;
- OHLC consistency;
- monotonic ordering within candidate sets;
- exact duplicate or conflict classification;
- direct or derived source eligibility;
- immutable provenance completeness.

## 17.3 OHLC Rules

```text
high >= open
high >= close
low  <= open
low  <= close
high >= low
```

Additionally:

- OHLC MUST be finite;
- NaN and infinity are invalid;
- zero or negative FX prices are invalid unless a named exception exists;
- null OHLC is invalid for a complete bar;
- precision MUST be sufficient to reproduce accepted source values.

## 17.4 Alignment Validation

A candidate passes alignment only when:

1. its local source open satisfies `local minute ∈ {00, 30} and local second = 00`;
2. its canonical UTC timestamp is the exact conversion of that local open;
3. its end is exactly 30 minutes later;
4. both boundaries lie within one owned FX trading day;
5. it does not lie inside the weekend closure;
6. a derived candidate contains only contiguous eligible contributors inside `[start, end)`.

## 17.5 Count and Sequence Validation

For a complete normal owner date, the validator expects `48` aligned intervals.

For a complete normal week, it expects `240` aligned intervals.

Count mismatch triggers coverage classification; it does not permit fabricated bars.

## 17.6 Severity

| Condition | Severity | Consequence |
|---|---|---|
| Valid closed bar | `INFO` | Eligible for acceptance |
| Valid exact duplicate | `INFO` | Reuse logical bar; retain provenance |
| Latest bar within delayed threshold | `WARNING` | Continue with visible delay |
| Older isolated expected gap | `WARNING` | Continue; expose repair candidate |
| Open current bar | `INFO` | Retain separately; not closed truth |
| Partial past bar | `WARNING` | Retain; do not promote |
| Provider unavailable or quota-limited | `WARNING` | Continue with best available evidence |
| Conflicting comparable duplicate | `CONFLICT` | Retain all; no silent replacement |
| Misaligned, weekend, impossible timestamp, or invalid OHLC | `REJECT` | Reject affected candidate; retain proof |
| Missing provider semantics, price basis, effective start, or parent authority | `BLOCKED` | Stop only affected path; emit compatibility report |

## 17.7 Non-Blocking Doctrine

A rejected or blocked candidate MUST NOT unnecessarily disable unrelated intervals, instruments, timeframes, or operations.

Previously accepted evidence remains available with visible warnings.

**Operations is King.**

---

# 18. Evidence Lane Contract

## 18.1 Lane Identity

```text
registered FX instrument / M30
```

Every evidence row MUST additionally retain provider/source identity, provider symbol, price basis, construction method, effective segment, evidence-block identity, and validation status.

## 18.2 Activation Gate

An FX `M30` lane may become `ACTIVE` only when:

- the instrument is registered as FX;
- `FX_BASE_DOCTRINE_V1` is approved;
- `FX_M30_AUTHORITY_V1` is approved;
- provider/source role and symbol mapping are approved;
- price basis is explicit;
- exact effective start is materialised;
- session and alignment authority resolve;
- request and response contract is implemented exactly;
- `FX_M30_VALIDATOR_V1` is implemented without semantic change.

## 18.3 Lane Status

| Status | Meaning |
|---|---|
| `REGISTERED` | Lane exists but operation is not yet authorised |
| `ACTIVE` | Acquisition, validation, and evidence acceptance are authorised |
| `SUSPENDED` | New acquisition paused; accepted evidence remains readable |
| `RETIRED` | Operation ended; evidence remains immutable |
| `BLOCKED` | Required authority or compatibility fact is incomplete |

`BLOCKED` applies only to the affected path and MUST NOT hide accepted evidence.

## 18.4 Required Provenance

Every accepted bar MUST trace to instrument registration, lane, evidence block, provider/source, source symbol, acquisition run, requested/received range, parser version, source timestamp, canonical mapping, price basis, validation result, construction method, contributing evidence where derived, and conflict history.

---

# 19. Operational Freshness Authority

## 19.1 Reference

Freshness is measured against the latest expected closed `M30` interval from Section 11.3.

It uses expected canonical intervals, not raw civil-time differences.

## 19.2 States

| State | Definition | Operational Meaning |
|---|---|---|
| `CURRENT` | Latest accepted complete interval equals latest expected closed interval | Normal operation |
| `DELAYED` | Latest accepted interval is one or two expected closed `M30` intervals behind | Continue with visible warning |
| `STALE` | Latest accepted interval is three or more expected closed `M30` intervals behind | Continue with prominent warning and repair priority |
| `UNKNOWN` | Expected or accepted latest interval cannot be determined | Display authority/evidence uncertainty; stop only affected update path if authority is missing |

## 19.3 Current-As-Of Truth

The operator-facing Current-As-Of Truth value is the canonical close instant and interval-open identity of the latest accepted complete selected bar.

It MUST remain distinct from:

- current wall-clock time;
- acquisition time;
- latest provider response timestamp;
- latest open or partial interval.

## 19.4 Non-Blocking Operation

`DELAYED` and `STALE` are warnings, not reasons to hide accepted history.

Where usable evidence exists, Fragarach MUST continue to serve it with Current-As-Of Truth, freshness state, and reason.

---

# 20. Provider Precedence

| Priority | Source | Role | Conditions |
|---|---|---|---|
| 1 | Existing accepted valid evidence | Continuity source | Remains selected until explicit resolution changes selection |
| 2 | Twelve Data direct `30min` | Primary automated acquisition and uncovered-interval source | Contract, mapping, range, and validation pass |
| 3 | Operator-supplied direct `M30` file | Manual backfill or supplementary source | Manifest, checksum, timezone, timestamp meaning, price basis, and validation required |
| 4 | Complete derived `M30` evidence | Uncovered-interval or verification source | Only where Section 10 permits; one provider and complete contributors |

Priority permits acquisition and uncovered-interval filling.

It does not authorise silent replacement of conflicting accepted evidence.

---

# 21. Exceptions

Initial exceptions:

```text
NONE
```

Every future exception MUST identify affected instruments, source/provider, interval range, substituted rule, reason, approval identity, effective range, review/expiry date, operational impact, and required provenance.

No undocumented exception is valid.

---

# 22. Compatibility Requirements

Before implementation begins, it MUST prove:

- Constitution and parent doctrine applicability;
- approval of `FX_M30_AUTHORITY_V1`;
- registered FX instrument and lane;
- exact 30-minute duration;
- alignment to the New York 17:00 owner-day grid;
- canonical UTC interval-open timestamps;
- close-date session ownership;
- provider/source role and provider symbol;
- `PROVIDER_AGGREGATE` or another approved price basis;
- exact request, response, chunk, overlap, and reassembly semantics;
- exact materialised effective start for each active lane;
- expected-bar, gap, duplicate, conflict, completion, and freshness rules;
- validator implementation without semantic change;
- no missing implementation-critical authority.

Failure requires a compatibility report and stops only the affected specification or operational path.

---

# 23. Specification Boundary

Specifications MAY define schemas, clients, adapters, parsers, storage, orchestration, validation code, derived-bar code, native operations, migrations, tests, and reports.

Specifications MUST NOT redefine:

- `M30` duration or interval meaning;
- 17:00 New York-relative alignment;
- boundary inclusion;
- UTC interval-open timestamp meaning;
- session ownership;
- direct or derived eligibility;
- complete-bar or latest-closed rules;
- Twelve Data interval, timezone, date-range, chunk, or overlap contract;
- effective-range materialisation;
- expected-bar and gap meaning;
- duplicate/conflict meaning;
- freshness thresholds;
- validator semantics;
- provider precedence.

---

# 24. Implementation Prohibitions

Implementation MUST NOT:

- align FX `M30` bars to an unrelated UTC epoch grid without New York-session validation;
- store provider local timestamps as UTC without conversion;
- infer interval-close meaning from interval-open labels;
- use fixed UTC offsets for New York;
- create bars inside the weekend closure;
- let one bar cross the 17:00 owner boundary;
- accept date-only values;
- guess source timezone or timestamp meaning;
- infer bid, ask, midpoint, or last basis for Twelve Data aggregate bars;
- accept open or partial bars as closed;
- activate a lane with unknown effective start;
- combine providers or price bases in a derived bar;
- fabricate, interpolate, forward-fill, or copy missing intervals;
- silently overwrite conflicts;
- operate outside approved effective segments;
- use unapproved source timeframes;
- block unrelated operations because one interval or source path is unresolved.

---

# 25. Amendment and Versioning

## 25.1 Version Rule

A new authority version is required when a change affects duration, alignment, owner-date mapping, timestamp meaning, provider interval code, construction eligibility, closure logic, request/response semantics, chunking, overlap, effective-range rules, expected counts, gap/conflict rules, validator meaning, freshness thresholds, or provider precedence.

## 25.2 Amendment Record

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| 1.0 | 2026-07-11 | Initial FX `M30` constitutional authority drafted | Establish approved `M30` operational truth before implementation | PENDING |

## 25.3 Supersession

A superseded authority remains immutable and auditable.

A replacement MUST state what it supersedes, effective date, historical re-evaluation requirements, evidence compatibility, migration needs, and continued accessibility of prior evidence.

---

# 26. Approval Gate

This authority may be marked **APPROVED** only when:

- `FX_BASE_DOCTRINE_V1` is approved;
- thirty minutes duration and New York alignment are accepted;
- UTC interval-open timestamp meaning is accepted;
- close-date ownership is accepted;
- expected daily and weekly counts are accepted;
- direct and derived construction rules are accepted;
- Twelve Data `30min` request and response contract is accepted;
- 4,000-row constitutional ceiling, `80`-day chunk cap, and `96`-interval overlap are accepted;
- exact effective-start materialisation is accepted;
- gap, duplicate, conflict, and repair rules are accepted;
- `FX_M30_VALIDATOR_V1` is accepted;
- freshness thresholds and Current-As-Of Truth are accepted;
- provider precedence is accepted;
- exceptions and approval identity are recorded;
- no unresolved template placeholder remains.

---

# 27. Acceptance Statement

Upon approval:

> `FX_M30_AUTHORITY_V1` is the approved constitutional authority for `M30` evidence lanes within the Foreign Exchange market ecosystem of Fragarach II. All specifications, implementations, acquisitions, validations, constructions, migrations, lane operations, and acceptance proofs for FX `M30` MUST conform to it.

---

# 28. Provider Reference Record

The Version 1 draft uses the following official provider material:

1. Twelve Data API Documentation — `time_series`, timezone, ordering, and response parameters:  
   `https://twelvedata.com/docs`
2. Twelve Data Support — *How to get historical prices*, updated January 12, 2026, documenting `30min` support as an intraday interval, `/earliest_timestamp`, bounded `start_date` and `end_date` requests, omission of `outputsize` for bounded ranges, and a maximum `outputsize` of 5,000:  
   `https://support.twelvedata.com/en/articles/5656039-how-to-get-historical-prices`
3. Twelve Data Support — *Getting historical data*, documenting the 5,000-data-point maximum:  
   `https://support.twelvedata.com/en/articles/5214728-getting-historical-data`

Provider documentation describes external behaviour at drafting time.

Once approved, this document is Fragarach's versioned constitutional contract. A material provider change requires compatibility review and, where necessary, an authority amendment.

---

# 29. Governing Principle

> An FX `M30` bar is not merely a provider row labelled `30min`.  
> It is an exact 30-minute interval, aligned to New York rollover authority, owned by a trading day, timestamped by its UTC open instant, and proven by immutable evidence.

Provider data may map into that contract.

Specifications may implement it.

Implementation must never invent it.

**Operations is King.**
