# METALS D1 AUTHORITY V1

**Document Class:** Constitutional Timeframe Authority  
**Authority Layer:** Market Timeframe  
**Authority Name:** `METALS_D1_AUTHORITY_V1`  
**Market Name:** Spot Precious Metals  
**Market Code:** `METALS`  
**Timeframe:** `D1`  
**Version:** 1.0  
**Status:** DRAFT FOR APPROVAL  
**Repository Location:** `constitution/authorities/metals/METALS_D1_AUTHORITY_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Authority:** `constitution/doctrines/METALS_BASE_DOCTRINE_V1.md`  
**Effective From:** Not effective until approved  
**Effective Until:** OPEN  
**Supersedes:** NONE  
**Approved By:** PENDING  
**Approval Date:** PENDING

---

# 1. Purpose

This authority defines the approved operational truth for `D1` evidence within the Spot Precious Metals market ecosystem of Fragarach II.

It establishes:

- what one metals `D1` bar represents;
- the canonical New York rollover interval;
- close-date trading-day ownership;
- canonical date and timestamp representation;
- direct-provider and lower-timeframe construction authority;
- bar completion and latest-closed-bar rules;
- Twelve Data request and response semantics;
- historical-range determination;
- expected-bar, gap, duplicate, conflict, and repair rules;
- the `METALS_D1_VALIDATOR_V1` validation contract;
- operational freshness and evidence-lane eligibility.

This authority does not define database schemas, API client architecture, storage implementation, application layout, or migration procedure.

Those matters belong to implementation specifications that consume this authority.

---

# 2. Constitutional Position

```text
Constitution

↓

METALS_BASE_DOCTRINE_V1

↓

METALS_D1_AUTHORITY_V1

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

Where conflict exists:

1. the Constitution overrides all subordinate documents;
2. `METALS_BASE_DOCTRINE_V1` overrides this authority;
3. this authority overrides implementation specifications;
4. specifications override implementation;
5. implementation MUST NOT invent missing operational facts.

Legacy code, provider defaults, existing sample files, and historical application behaviour are not authority unless expressly adopted here or by the parent doctrine.

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

- instruments registered under market code `METALS`;
- timeframe code `D1`;
- evidence whose provider, source scope, price basis, pricing unit, timestamp meaning, and effective range are known;
- direct `D1` provider evidence;
- derived `D1` evidence constructed under this authority from approved lower-timeframe evidence.

## 4.2 Excluded Scope

This authority does not govern:

- foreign-exchange currency pairs;
- cryptoassets;
- exchange-traded metal futures and options;
- metal ETFs, trusts, benchmarks, fixings, and mining equities;
- weekly or monthly bars;
- `H1`, `M30`, `M5`, or any other intraday interval;
- synthetic metal crosses not separately authorised;
- a provider/timeframe combination whose semantics are not approved.

## 4.3 Inherited Market Truth

This authority inherits without modification:

- metals market identity;
- base-metal, quote-asset, and troy-ounce unit semantics;
- decentralised multi-venue OTC market status;
- `America/New_York` calendar timezone;
- Sunday 17:00 New York operational-week open;
- Friday 17:00 New York operational-week close;
- 17:00 New York daily rollover;
- close-date trading-day ownership;
- provider roles;
- immutable evidence doctrine;
- declared price-basis and source-scope requirements;
- canonical troy-ounce unit authority;
- non-centralised volume doctrine;
- market-wide validation and structural-event rules.

---

# 5. Canonical Timeframe Definition

## 5.1 Timeframe Identity

**Timeframe Code:** `D1`  
**Nominal Duration:** One canonical metals trading day  
**Time Unit:** `DAY`  
**Interval Type:** `SESSION-DERIVED`

## 5.2 Approved Definition

One canonical metals `D1` bar represents one owned metals trading day under `METALS_24X5_NEW_YORK_ROLLOVER_V1`.

For an owned New York civil date `D`:

```text
D1 start = 17:00 America/New_York on the preceding civil date
D1 end   = 17:00 America/New_York on D
D1 owner = D
```

The canonical interval is:

```text
[start, end)
```

Therefore, an observation occurring exactly at the 17:00 boundary belongs to the next metals trading day.

## 5.3 Bar Meaning

A complete metals `D1` bar contains the approved provider's declared price-basis OHLC for the owned trading day.

A bar MAY originate from:

1. an approved direct provider-side `D1` aggregation; or
2. an approved Fragarach-side rollup from lower-timeframe evidence.

The origin MUST remain explicit in provenance.

Direct and derived bars are not assumed to be numerically identical.

A provider-side `D1` bar is accepted as that provider's declared daily aggregation for the mapped owner date. A derived `D1` bar is accepted only when its contributing evidence conforms to the canonical 17:00 New York interval defined here.

There is no constitutional extended-hours category for spot precious metals. Provider maintenance or publication breaks are evidence conditions, not separate market sessions.

## 5.4 Actual Elapsed Duration

`D1` is not defined as a fixed number of UTC seconds.

Because the interval is anchored to `America/New_York`, an interval crossing a daylight-saving transition MAY contain 23, 24, or 25 elapsed hours while remaining one valid metals trading day.

Implementation MUST NOT replace the session-derived definition with a fixed `86,400`-second rule.

---

# 6. Interval Alignment Authority

## 6.1 Alignment Origin

Each bar is aligned independently to the 17:00 New York close of its owned trading date.

There is no Unix-epoch or UTC-midnight alignment origin for the physical interval.

## 6.2 Boundary Rule

For owner date `D`:

```text
[previous civil date at 17:00 America/New_York,
 D at 17:00 America/New_York)
```

## 6.3 Alignment Mapping

Let `owner_date` be a Monday-through-Friday New York civil date that lies within the lane's approved effective range.

```text
interval_start(owner_date)
    = local_datetime(owner_date - 1 civil day, 17:00, America/New_York)

interval_end(owner_date)
    = local_datetime(owner_date, 17:00, America/New_York)
```

Timezone conversion MUST use the applicable IANA timezone rules for the historical date.

## 6.4 Session, Week, and Month Crossing

A canonical `D1` bar:

- MUST NOT cross its 17:00 New York daily boundary;
- normally crosses New York civil midnight;
- MAY cross a UTC calendar-day boundary;
- MUST NOT combine two owned metals trading days;
- belongs to the week containing its owned close date;
- belongs to the month containing its owned close date.

The Monday-owned bar begins Sunday at 17:00 New York.

The Friday-owned bar ends Friday at 17:00 New York.

## 6.5 Partial Intervals

A shortened or incomplete evidence interval caused by provider outage, provider maintenance or publication break, acquisition interruption, instrument launch, suspension, or incomplete source coverage MUST NOT be silently promoted to a complete derived `D1` bar.

Such evidence MAY be retained as `PARTIAL` or `PROVISIONAL` with visible provenance.

There is no generic global spot-metals early-close rule.

Any exceptional global spot-metals closure or shortened trading day requires a documented exception under Section 21.

---

# 7. Timestamp Authority

## 7.1 Canonical Timestamp Meaning

**Timestamp Meaning:** `SESSION DATE`  
**Canonical Storage Timezone:** `UTC`

The canonical `D1` timestamp is a stable encoding of the owned New York close date.

For owned date `YYYY-MM-DD`, the canonical timestamp is:

```text
YYYY-MM-DDT00:00:00Z
```

This timestamp is a semantic date label.

It is **not**:

- the physical session open instant;
- the physical session close instant;
- UTC midnight market ownership;
- proof that the interval was aggregated from UTC midnight.

The physical interval is determined only by Section 6.

## 7.2 Canonical Session Date

Every canonical row MUST also resolve an unambiguous `session_date` equal to the owned New York close date.

Where storage exposes only one timestamp field, the midnight-UTC canonical timestamp defined above is authoritative and its semantic meaning MUST remain documented.

## 7.3 Provider Timestamp Mapping

| Source | Source Timestamp Meaning | Source Timezone | Canonical Mapping | Conditions |
|---|---|---|---|---|
| Twelve Data `1day` | Provider daily label | Request MUST specify `America/New_York` | Date component becomes `session_date`; encode as `session_dateT00:00:00Z` | Symbol mapping, declared price basis, and response semantics MUST validate |
| Operator-supplied direct `D1` file | Declared source date or datetime | MUST be declared in file manifest or accepted provenance | Map to owned New York close date, then encode at midnight UTC | Ambiguous semantics are not accepted |
| Existing accepted immutable `D1` evidence | Existing accepted date meaning | As recorded in provenance | Preserve the accepted owner date and canonical midnight-UTC encoding | Original provenance remains immutable |
| Derived lower-timeframe evidence | Canonical contributing intervals | `America/New_York` ownership with UTC instants | Use the owner date of the 17:00 New York interval end | All contributing evidence MUST be eligible under Section 10 |

## 7.4 Date-Only Values

**Date-Only Allowed:** `CONDITIONAL`

A date-only value is valid only when:

1. it is an unambiguous ISO calendar date in `YYYY-MM-DD` form;
2. the source is approved for metals `D1`;
3. provenance declares the date to be the provider's daily label or the metals close-date owner;
4. the date resolves to an expected Monday-through-Friday metals trading date or a documented exception;
5. normalisation to midnight UTC does not change its semantic owner date.

A valid date-only value MUST be normalised to:

```text
YYYY-MM-DDT00:00:00Z
```

with the normalisation method retained in provenance.

## 7.5 Ambiguous or Invalid Timestamps

Implementation MUST NOT guess when:

- day and month ordering is ambiguous;
- timezone is absent from an intraday datetime;
- a file does not declare whether its date is open-date, close-date, or UTC-date;
- a provider datetime maps to more than one plausible owner date;
- the source label is Saturday or Sunday without an approved exception;
- the timestamp lies outside the effective range.

Ambiguous values MUST be rejected for active lane use and retained with a validation or compatibility report.

---

# 8. Trading-Day and Session Ownership

## 8.1 Inherited Rule

This authority inherits Sections 6 and 7 of `METALS_BASE_DOCTRINE_V1`.

The canonical metals trading day is owned by the New York civil date on which the session closes at 17:00.

## 8.2 Timeframe-Specific Ownership

Exactly one canonical `D1` owner date exists for each expected Monday-through-Friday metals trading day.

```text
Sunday 17:00 → Monday 17:00 = Monday owner date
Monday 17:00 → Tuesday 17:00 = Tuesday owner date
...
Thursday 17:00 → Friday 17:00 = Friday owner date
```

There is no canonical Saturday or Sunday `D1` owner date.

## 8.3 Overnight Session

The metals `D1` session crosses New York midnight by design.

Ownership is never assigned by the civil date on which the interval opens.

Ownership is always assigned by the New York civil date on which the interval closes.

## 8.4 Week and Month Boundaries

- The Friday-owned bar is the final normal bar of the metals week.
- The Monday-owned bar is the first normal bar of the next metals week.
- A bar belongs to the calendar month of its owner date, even when it opened in the preceding month.
- A public holiday or futures-exchange closure does not automatically remove an expected owner date.
- An exceptional non-trading date requires explicit constitutional evidence or an approved exception.

---

# 9. Bar Price and Field Meaning

## 9.1 OHLC

For a direct provider bar, OHLC retains the provider's declared `D1` aggregation and price basis.

For a derived bar:

- **Open** MUST equal the first eligible observation or source-bar open in the canonical interval.
- **High** MUST equal the maximum eligible high or observation in the canonical interval.
- **Low** MUST equal the minimum eligible low or observation in the canonical interval.
- **Close** MUST equal the final eligible observation or source-bar close before the interval end.

## 9.2 Price Basis

Each bar MUST retain one declared price basis and one declared source scope. Approved price-basis values include:

- `BID`;
- `ASK`;
- `MIDPOINT`;
- `LAST`;
- `PROVIDER_AGGREGATE`;
- another separately approved basis.

Unlike price bases or source scopes MUST NOT be silently combined or treated as exact substitutes. Every canonical price MUST represent the registered quote amount per one troy ounce of the base metal unless an approved unit transformation is explicitly recorded.

Unless a separately approved provider mapping establishes a more specific basis, direct Twelve Data metals evidence under Version 1 MUST retain:

```text
source_scope = TWELVE_DATA_PROVIDER_AGGREGATE
price_basis  = PROVIDER_AGGREGATE
pricing_unit = QUOTE_ASSET_PER_TROY_OUNCE
```

These labels describe Fragarach provenance. They do not assert a universal consolidated spot-metal market price.

## 9.3 Volume

Spot precious metals have no universal consolidated volume.

A direct provider volume field MUST retain its provider-declared meaning.

For a derived bar, volume MAY be summed only when all contributing rows:

- come from one compatible source basis;
- use the same declared volume semantics;
- use the same source scope and pricing unit;
- define volume as additive across the source intervals.

Otherwise, derived volume MUST be null or marked unavailable.

Zero, null, and absent volume are distinct states and MUST NOT invalidate otherwise valid OHLC evidence.

---

# 10. Bar Construction Authority

## 10.1 Approved Construction Source

**Approved Construction Source:** `EITHER`

Metals `D1` evidence MAY be accepted from:

1. an approved direct provider `D1` bar; or
2. a Fragarach-side rollup from a lower timeframe whose own authority is approved.

The construction method MUST be recorded as one of:

```text
DIRECT_PROVIDER_D1
DERIVED_FROM_H1
DERIVED_FROM_M30
DERIVED_FROM_M5
```

No other method is approved by Version 1.

## 10.2 Source Timeframe Eligibility

| Source Timeframe | Permitted | Conditions | Notes |
|---|---|---|---|
| `H1` | YES, CONDITIONAL | `METALS_H1_AUTHORITY_V1` approved; same instrument; compatible provider, source scope, price basis, and pricing unit; complete interval coverage | May construct `D1` after H1 authority approval |
| `M30` | YES, CONDITIONAL | `METALS_M30_AUTHORITY_V1` approved; same instrument; compatible provider, source scope, price basis, and pricing unit; complete interval coverage | May construct `D1` after M30 authority approval |
| `M5` | YES, CONDITIONAL | `METALS_M5_AUTHORITY_V1` approved; same instrument; compatible provider, source scope, price basis, and pricing unit; complete interval coverage | Preferred fine-grained rollup source when complete |
| `M1`, `M3`, `M15`, `H4`, tick | NO under Version 1 | Separate approved authority required | Retain evidence but do not construct canonical `D1` under this version |

## 10.3 Direct Provider Authority

Twelve Data `1day` bars are approved as direct metals `D1` evidence when:

- the registered provider symbol resolves;
- the request uses the contract in Section 12;
- the response date maps under Section 7;
- the price basis, source scope, and troy-ounce pricing unit are declared;
- the row validates under `METALS_D1_VALIDATOR_V1`;
- the row lies within the instrument and provider effective range.

Direct provider evidence MUST remain identified as provider-side aggregation.

It MUST NOT be represented as a Fragarach 17:00 lower-timeframe rollup unless it was actually constructed that way.

## 10.4 Direct Versus Derived Precedence

Direct and derived bars are independent immutable evidence.

The default operational selection rule is:

1. retain an already accepted valid bar for continuity;
2. use a validated Twelve Data direct `D1` bar for a previously uncovered owner date;
3. use validated operator-supplied direct `D1` evidence for an uncovered owner date;
4. use a complete validated derived bar for an uncovered owner date;
5. retain all conflicting evidence without silent overwrite.

A lower-priority source MAY fill an uncovered date.

It MUST NOT silently replace a higher-priority accepted bar.

## 10.5 Missing Source Bars

A derived `D1` bar may be classified `CLOSED` only when every expected contributing interval is present, except intervals excluded by the approved lower-timeframe authority.

When expected contributing bars are missing:

- the partial rollup MAY be retained as `PARTIAL` or `PROVISIONAL`;
- the missing coverage MUST be recorded;
- the row MUST NOT be promoted as a complete canonical derived bar;
- direct provider evidence MAY still independently supply the owner date.

## 10.6 Cross-Provider Construction

**Cross-Provider Construction Allowed:** `NO`

One derived `D1` bar MUST NOT combine observations or source bars from multiple providers.

Cross-provider evidence may coexist and be compared, but it may not be blended into one bar under this authority.

---

# 11. Bar Completion Authority

## 11.1 Complete Bar Definition

A logical metals `D1` interval is closed when its canonical interval end has passed:

```text
current instant >= owner date at 17:00 America/New_York
```

An evidence bar is complete only when:

- its logical interval is closed;
- it is not the provider's current partial daily bar;
- its timestamp and owner date validate;
- its OHLC validates;
- its source, source scope, price basis, and pricing unit are declared;
- its effective range validates;
- direct-provider or derived-construction requirements are satisfied.

## 11.2 Latest Expected Closed Bar

The latest expected closed `D1` owner date is the greatest Monday-through-Friday New York civil date whose 17:00 New York interval end is less than or equal to the current instant, excluding only approved exceptional non-bar dates.

Examples:

- before Monday 17:00 New York, the latest expected closed owner date is normally the preceding Friday;
- at or after Monday 17:00 New York, Monday becomes the latest expected closed owner date;
- during Saturday, the latest expected closed owner date remains Friday;
- after Sunday 17:00 New York, Monday is open but is not yet closed, so Friday remains the latest expected closed owner date.

Provider lag does not change which bar is logically closed.

Provider lag changes freshness and coverage status.

## 11.3 Status Model

| Status | Meaning |
|---|---|
| `OPEN` | The canonical session has begun but has not reached its 17:00 New York end |
| `PARTIAL` | Evidence covers only part of an open or closed canonical interval |
| `PROVISIONAL` | Provider evidence is closed but carries unresolved coverage or revision uncertainty |
| `CLOSED` | Interval ended and evidence passed mandatory validation |
| `REVISED` | New immutable evidence differs from previously accepted evidence for the same comparable identity |
| `NOT_EXPECTED` | No canonical `D1` bar is expected for that owner date |

An `OPEN`, `PARTIAL`, or `PROVISIONAL` bar MUST NOT be represented as the latest accepted closed bar.

## 11.4 Revision Window

No finite universal provider revision window is assumed.

A provider may publish corrected `D1` evidence after the interval closes.

A revision MUST:

- be stored as new immutable evidence;
- retain acquisition and provider provenance;
- be compared with existing comparable evidence;
- be classified exact duplicate or conflict;
- never mutate or silently replace prior evidence.

---

# 12. Request and Response Authority

## 12.1 Twelve Data Request Contract

The approved direct automated request uses the Twelve Data `/time_series` endpoint with the following constitutional parameters:

| Parameter | Approved Value or Rule |
|---|---|
| `symbol` | Registered Twelve Data provider symbol for the metals instrument |
| `interval` | `1day` |
| `timezone` | `America/New_York` |
| `order` | `asc` |
| `format` | `JSON` |
| `start_date` | Start owner date at `00:00:00` in `America/New_York` |
| `end_date` | Civil day after the final requested owner date at `00:00:00` in `America/New_York` |
| `outputsize` | MUST be omitted for a bounded `start_date` + `end_date` request |
| authentication | Approved secret mechanism; secret MUST NOT enter logs or evidence payloads |

For a desired inclusive owner-date range `[S, E]`, Fragarach MUST request:

```text
start_date = S at 00:00:00 America/New_York
end_date   = E + 1 civil day at 00:00:00 America/New_York
```

The response MUST then be canonically filtered to:

```text
S <= mapped session_date <= E
```

This rule avoids dependence on undocumented edge inclusivity at midnight.

## 12.2 Provider Limits and Chunking

Twelve Data currently documents a maximum of 5,000 data points per request.

Fragarach's constitutional chunk ceiling is therefore:

```text
4,000 expected D1 owner dates per bounded request
```

The lower ceiling provides headroom for overlap, unexpected rows, and provider behaviour changes.

Each adjacent chunk MUST overlap by at least:

```text
2 expected metals trading days
```

The overlap is evidence for deterministic reassembly and revision detection.

Rate limits are subscription- and account-dependent.

No fixed numerical rate limit is constitutional under this version.

Implementation MUST obey the configured account entitlement and provider responses, and MUST expose throttling or quota failures as acquisition outcomes.

## 12.3 Incremental Acquisition

An incremental acquisition SHOULD request:

- from at least five expected trading days before the latest accepted owner date;
- through the civil day after the latest expected closed owner date.

This overlap permits detection of provider revisions without mutating prior evidence.

## 12.4 Response Semantics

For an approved Twelve Data response:

- the JSON response status and metadata MUST be distinguished from value rows;
- value rows MUST contain a parseable `datetime` or equivalent daily label;
- requested ascending order MUST be verified rather than assumed;
- numeric strings MUST be parsed without loss of declared precision;
- duplicate dates MUST be classified under Section 15;
- rows later than the latest expected closed owner date MUST be retained only as `OPEN` or `PARTIAL`, not accepted as closed;
- an empty successful values set means no evidence was returned for the request and does not prove market closure;
- an error payload is an acquisition failure, not an empty market interval;
- any response that reaches a provider row limit without full requested coverage MUST be treated as potentially truncated.

## 12.5 Chunk Reassembly

Chunk responses MUST be reassembled by:

1. preserving every immutable response block;
2. mapping every row to canonical `session_date` and timestamp;
3. filtering to the requested canonical coverage range;
4. sorting by canonical owner date ascending;
5. comparing overlap rows;
6. collapsing exact repeated evidence only at the read-model level while retaining source provenance;
7. retaining conflicting overlap rows as conflict evidence;
8. proving requested, received, duplicate, conflicting, and uncovered ranges.

## 12.6 Request Coverage Proof

Every acquisition run MUST record:

- instrument and provider symbol;
- interval code;
- request timezone;
- requested start and end;
- canonical requested owner-date range;
- provider response range;
- canonical mapped response range;
- row count;
- exact duplicate count;
- conflict count;
- uncovered expected owner dates;
- overlap range;
- possible truncation;
- partial or future-row count;
- acquisition status;
- immutable evidence-block identity.

---

# 13. Effective Historical Range

## 13.1 Timeframe Effective Range

**Effective Range Start:** Instrument- and provider-specific  
**Effective Range End:** `OPEN`

There is no universal start date for all metals `D1` lanes.

For each instrument and evidence source, the effective start is the latest of:

1. the instrument start approved under `METALS_BASE_DOCTRINE_V1`;
2. the registered metal, quote-asset, and pricing-unit regime start;
3. the provider-symbol mapping start;
4. the provider's earliest available reliable `1day` bar;
5. the earliest compatible immutable evidence;
6. any instrument-specific exception date.

## 13.2 Provider-Specific Range Rules

| Source | Earliest Reliable Bar | Latest Supported Bar | Authority Rule |
|---|---|---|---|
| Twelve Data | Result of `/earliest_timestamp` for the registered symbol and `1day`, captured with provenance and confirmed by successful acquisition | Latest available bar, subject to latest-closed filtering | Provider coverage does not override metal-pair and unit-regime authority |
| Operator-supplied direct file | Earliest row whose source identity, date semantics, and price basis validate | Latest validated row not later than the latest expected closed owner date | File manifest and checksum required |
| Existing accepted immutable evidence | Existing accepted start | Existing accepted end or OPEN through later evidence | Original evidence remains immutable |
| Derived lower-timeframe evidence | Latest of source-lane effective starts and first complete `D1` coverage | Latest complete derived interval | Source timeframe authority must be approved |

## 13.3 Instrument-Specific Range

The approved range MUST be recorded in Instrument Registration or an authority-linked instrument exception.

Implementation MUST NOT infer continuity through:

- quote-currency introduction, withdrawal, or redenomination;
- base-metal or quote-asset identity change;
- pricing-unit or conversion-factor change;
- provider symbol remapping;
- conversion between spot, benchmark, futures, ETF, trust, or CFD basis;
- material quote convention, source-scope, or aggregation-method change.

## 13.4 Historical Regime Changes

Historical timezone rules MUST use the applicable `America/New_York` IANA history for each date.

A material change in provider aggregation, symbol mapping, or price basis creates a new effective segment or exception.

Evidence outside an approved segment MAY be retained but MUST NOT silently enter the active canonical lane.

---

# 14. Gap Authority

## 14.1 Expected Bar Rule

Within the approved effective range, one `D1` bar is expected for every Monday-through-Friday New York owner date unless a documented exception declares the date `NOT_EXPECTED`.

A holiday in one country is not sufficient to declare a metals date `NOT_EXPECTED`.

Provider silence is not proof that no market existed.

## 14.2 Valid Non-Bar Periods

The following MUST NOT be classified as `D1` gaps:

- Saturday or Sunday owner dates;
- dates before the lane's effective start;
- dates after an instrument's retirement or effective end;
- the current open owner date;
- an approved exceptional closure date;
- a date excluded by an instrument-specific constitutional exception.

## 14.3 Gap Classification

| Classification | Meaning | Operational Consequence |
|---|---|---|
| `NOT_EXPECTED` | No canonical bar should exist | No gap and no repair action |
| `EXPECTED_MISSING` | A closed expected owner date has no accepted complete bar | Visible warning and repair candidate |
| `SOURCE_UNAVAILABLE` | The requested source could not provide evidence | Retain best available evidence and visible uncertainty |
| `PARTIAL_COVERAGE` | Evidence exists but does not cover a complete canonical interval | Retain as partial; do not promote to complete |
| `CONFLICTING_COVERAGE` | Comparable evidence disagrees on existence or OHLC | Retain conflict and require resolution |
| `AUTHORITY_MISSING` | Expectedness, mapping, or effective range cannot be determined | Stop only the affected path and emit compatibility report |

## 14.4 Gap Materiality

Every `EXPECTED_MISSING` date remains a real evidence gap.

Gap materiality affects operational priority, not historical truth.

The following materiality rules apply:

- a missing owner date among the latest 30 expected closed `D1` bars is `HIGH` priority;
- a gap that leaves an entire metals trading week with no valid `D1` evidence is `HIGH` historical materiality;
- a gap that leaves an owned calendar month with no valid `D1` evidence is `HIGH` historical materiality;
- an isolated older gap with surrounding weekly and monthly coverage is `LOW` materiality but remains visible;
- multiple consecutive expected missing dates are at least `MEDIUM` materiality regardless of age;
- no gap automatically invalidates all other accepted evidence in the lane.

Weekly and monthly coverage flags are downstream-operational aids.

They do not fabricate or excuse a missing `D1` bar.

## 14.5 Gap Repair Authority

Permitted repair attempts, in order, are:

1. re-acquire the same date from the same provider and price basis;
2. use existing accepted immutable evidence for that date;
3. accept an operator-supplied direct `D1` file with compatible semantics;
4. construct a complete derived `D1` bar from one approved lower-timeframe source;
5. use another provider only after a new approved provider authority exists.

A repair MUST create new immutable evidence and provenance.

Implementation MUST NOT fabricate OHLC values, interpolate, forward-fill, or silently copy an adjacent bar.

---

# 15. Duplicate and Overlap Authority

## 15.1 Canonical Identity

The canonical comparable-bar identity is:

```text
instrument_registration
+ timeframe D1
+ canonical session_date
+ price_basis
+ provider/source identity
+ construction_method
```

The evidence-block identity remains separately immutable.

## 15.2 Exact Duplicate

Two evidence rows are exact duplicates only when their comparable-bar identities match and all of the following are equal after approved numeric normalisation:

- open;
- high;
- low;
- close;
- volume value;
- volume-null state;
- volume semantics;
- source timestamp mapping;
- completion status.

Separate acquisitions of an exact duplicate remain separate provenance events even when a read model presents one logical bar.

## 15.3 Conflicting Duplicate

Two rows are conflicting duplicates when:

- their comparable-bar identities match; and
- one or more OHLC, volume-state, timestamp-mapping, or completion values differ.

A later provider response is not automatically correct.

## 15.4 Parallel Non-Comparable Evidence

Bars for the same instrument, timeframe, and owner date are parallel evidence rather than exact duplicates when they differ by:

- provider;
- price basis;
- source scope;
- pricing unit;
- construction method;
- authorised source role.

Parallel evidence MAY be compared but MUST NOT be silently collapsed as identical authority.

## 15.5 Provider Overlap

Repeated requests and chunk overlaps are expected acquisition behaviour.

Every overlap row MUST be classified as:

- exact duplicate;
- conflicting duplicate;
- new previously uncovered evidence;
- non-comparable parallel evidence.

## 15.6 Resolution Rule

Conflicts MUST NOT be resolved by silent overwrite.

The operational read model MAY continue to serve the previously accepted valid bar while displaying conflict status.

A replacement selection requires an explicit, auditable resolution decision under an approved specification.

---

# 16. Price and Volume Semantics

## 16.1 Inherited Price Basis

This authority inherits Section 10 of `METALS_BASE_DOCTRINE_V1`.

A metals `D1` bar represents one provider's declared price basis, not a universal consolidated market price.

## 16.2 Timeframe-Specific Price Rule

No `D1`-specific transformation of OHLC is authorised.

Price inversion, synthetic cross construction, smoothing, adjustment, interpolation, and corporate-action-style adjustment are prohibited unless separately authorised.

## 16.3 Volume Aggregation

Direct volume retains provider meaning.

Derived volume may be summed only under Section 9.3.

## 16.4 Null and Zero Volume

- `0` means the source measured or supplied zero under its declared semantics.
- `NULL` means no numeric value is available.
- absent means the source did not provide the field.

These states MUST remain distinguishable where the evidence format permits.

---

# 17. Validation Authority

## 17.1 Validator Authority

**Validator Authority:** `METALS_D1_VALIDATOR_V1`

This section is the normative validator contract.

Implementation may encode it but MUST NOT change its meaning.

## 17.2 Mandatory Validation Rules

Every candidate bar MUST be evaluated for:

- registered metals instrument identity;
- canonical `D1` timeframe identity;
- approved source and provider mapping;
- declared price basis;
- timestamp parseability;
- canonical date mapping;
- midnight-UTC semantic timestamp encoding;
- Monday-through-Friday owner-date eligibility;
- canonical 17:00 New York interval mapping;
- effective-range eligibility;
- logical completion status;
- numeric validity;
- OHLC consistency;
- monotonic canonical ordering within the candidate set;
- exact duplicate or conflict status;
- source coverage and construction eligibility;
- provenance completeness.

## 17.3 OHLC Rules

At minimum:

```text
high >= open
high >= close
low <= open
low <= close
high >= low
```

Additionally:

- OHLC MUST be finite numeric values;
- NaN and infinity are invalid;
- negative metals prices are invalid unless a named constitutional exception exists;
- zero metals prices are invalid unless a named constitutional exception exists;
- null OHLC values are invalid for a complete bar;
- numeric parsing MUST preserve sufficient provider precision to reproduce the accepted evidence value.

## 17.4 Alignment Validation

A candidate passes alignment only when:

1. its `session_date` is explicit;
2. its canonical timestamp equals `session_dateT00:00:00Z`;
3. the physical interval resolves to previous civil date 17:00 through owner date 17:00 in `America/New_York`;
4. its owner date is expected or documented by exception;
5. a derived bar contains no source observation outside `[start, end)`.

## 17.5 Session Validation

A candidate passes session validation when:

- the owner date is Monday through Friday, unless an approved exception applies;
- the interval is not wholly inside the Friday-to-Sunday weekend closure;
- the bar does not combine two owner dates;
- a derived bar's contributors all belong to the same canonical owner date;
- the applicable historical New York timezone offset is used.

## 17.6 Validation Severity

| Condition | Severity | Consequence |
|---|---|---|
| Valid closed bar | `INFO` | Eligible for acceptance |
| Valid exact duplicate | `INFO` | Reuse logical bar; retain acquisition provenance |
| Latest accepted bar one expected date behind | `WARNING` | Continue with delayed warning |
| Older isolated expected gap | `WARNING` | Continue; expose repair candidate and materiality |
| Partial current bar | `INFO` | Retain separately; do not accept as closed |
| Partial past bar | `WARNING` | Retain; do not promote as complete |
| Provider unavailable or quota-limited | `WARNING` | Continue with best available evidence |
| Conflicting comparable duplicate | `CONFLICT` | Retain all evidence; no silent replacement |
| Invalid OHLC, invalid timestamp, weekend owner date, or impossible mapping | `REJECT` | Reject affected candidate; retain proof |
| Missing provider semantics, price basis, effective range, or parent authority | `BLOCKED` | Stop only the affected path; emit compatibility report |

## 17.7 Non-Blocking Validation Doctrine

A rejected or blocked candidate MUST NOT unnecessarily disable unrelated owner dates, instruments, timeframes, or operations.

Previously accepted usable evidence remains available with visible warnings.

**Operations is King.**

---

# 18. Evidence Lane Contract

## 18.1 Lane Identity

The constitutional lane identity is:

```text
registered metals instrument / D1
```

Evidence within the lane MUST additionally retain:

- provider or source identity;
- provider symbol;
- price basis;
- source scope;
- pricing unit;
- construction method;
- effective segment;
- evidence-block identity;
- validation status.

These dimensions preserve evidence meaning and MUST NOT be discarded merely because the operator view presents one selected bar per owner date.

## 18.2 Lane Eligibility

A metals `D1` lane may become `ACTIVE` only when:

- the instrument is registered as METALS;
- `METALS_BASE_DOCTRINE_V1` is approved;
- `METALS_D1_AUTHORITY_V1` is approved;
- the provider or source role is approved;
- provider symbol mapping exists;
- price basis is declared;
- the instrument and provider effective range are known;
- calendar and session authority resolve;
- `METALS_D1_VALIDATOR_V1` is implemented without semantic change.

## 18.3 Lane Status

| Status | Meaning |
|---|---|
| `REGISTERED` | Lane identity exists but operation is not yet authorised |
| `ACTIVE` | Acquisition, validation, and evidence acceptance are authorised |
| `SUSPENDED` | New operations are paused; accepted evidence remains available |
| `RETIRED` | Lane is no longer operational; evidence remains immutable and readable |
| `BLOCKED` | A required authority or compatibility fact is incomplete |

`BLOCKED` applies only to the affected path.

It MUST NOT erase or hide accepted evidence.

## 18.4 Lane Provenance

Every accepted bar MUST remain traceable to:

- instrument registration;
- evidence lane;
- evidence block;
- provider or source;
- source symbol;
- acquisition run;
- requested and received range;
- parser or adapter version;
- timestamp mapping;
- price basis;
- source scope;
- pricing unit;
- validation result;
- construction method;
- contributing evidence where derived;
- conflict or resolution history.

---

# 19. Operational Freshness Authority

## 19.1 Freshness Reference

Freshness is measured against the latest expected closed metals `D1` owner date determined by Section 11.2.

Freshness MUST use expected trading dates, not raw civil-day differences.

## 19.2 Freshness States

| State | Definition | Operational Meaning |
|---|---|---|
| `CURRENT` | Latest accepted complete owner date equals latest expected closed owner date | Normal operation |
| `DELAYED` | Latest accepted complete owner date is exactly one expected `D1` bar behind | Use best available evidence with visible warning |
| `STALE` | Latest accepted complete owner date is two or more expected `D1` bars behind | Use best available evidence with prominent warning and repair priority |
| `UNKNOWN` | Latest expected closed date or latest accepted date cannot be determined | Display authority or evidence uncertainty; stop only affected update path if authority is missing |

## 19.3 Current-As-Of Truth

The operator-facing Current-As-Of Truth Date for a metals `D1` lane is the owner date of the latest accepted complete selected bar.

It MUST be displayed independently from:

- the current civil date;
- the latest provider response date;
- the latest open or partial bar;
- the most recent acquisition timestamp.

## 19.4 Non-Blocking Operation

`DELAYED` and `STALE` are operational warnings, not reasons to hide valid historical evidence.

Where usable accepted evidence exists, Fragarach MUST continue to serve it with freshness state, Current-As-Of Truth Date, and visible reason.

Missing constitutional authority remains a compatibility stop for the affected operation only.

---

# 20. Provider Precedence for METALS D1

| Priority | Source | Role | Conditions |
|---|---|---|---|
| 1 | Existing accepted valid evidence | Continuity source | Remains selected unless an explicit resolution changes selection |
| 2 | Twelve Data direct `1day` | Primary automated acquisition and uncovered-date source | Request and response contract, mapping, range, and validation must pass |
| 3 | Operator-supplied direct `D1` file | Manual backfill or supplementary source | Declared origin, checksum, timestamp meaning, price basis, and validation required |
| 4 | Complete derived `D1` | Construction source for uncovered dates and verification | One approved lower-timeframe source; complete coverage; no cross-provider blend |

## 20.1 Conflict Rule

Priority permits acquisition and uncovered-date filling.

Priority does not authorise silent replacement of conflicting accepted evidence.

When comparable sources disagree:

- all evidence MUST be retained;
- the previously selected valid bar MAY continue to serve;
- conflict MUST remain visible;
- replacement requires an explicit auditable resolution decision.

---

# 21. Exceptions

Initial exceptions:

```text
NONE
```

Every future exception MUST include:

- exception identifier;
- affected instruments;
- affected provider or source;
- affected owner-date range;
- substituted alignment, mapping, expectedness, or validation rule;
- reason;
- approval identity;
- effective range;
- review or expiry date;
- operational impact;
- required provenance.

No undocumented exception is valid.

---

# 22. Compatibility Requirements

Before an implementation specification begins, it MUST prove that:

- the Constitution is present and applicable;
- `METALS_BASE_DOCTRINE_V1` is approved;
- `METALS_D1_AUTHORITY_V1` is approved;
- the instrument is registered under `METALS`;
- base and quote currencies are explicit;
- the evidence lane exists or is validly proposed;
- interval meaning and 17:00 New York boundaries are explicit;
- session-date timestamp encoding is explicit;
- provider role and symbol mapping are valid;
- price basis is explicit;
- direct or derived construction method is authorised;
- provider request and response semantics are implemented exactly;
- instrument and provider effective ranges are known;
- gap, duplicate, conflict, freshness, and validation rules resolve;
- no implementation-critical authority is missing.

Failure requires a compatibility report and stops only the affected specification or operational path.

---

# 23. Specification Boundary

Specifications consuming this authority MAY define:

- database schemas;
- evidence-block formats;
- acquisition clients;
- request chunk orchestration;
- parsers and adapters;
- validation code;
- evidence storage;
- lane registration workflow;
- derived-bar calculation code;
- application operations;
- migrations;
- tests and acceptance reports.

Specifications MUST NOT redefine:

- what `D1` means;
- the 17:00 New York interval;
- close-date ownership;
- canonical date and timestamp meaning;
- direct or derived eligibility;
- complete-bar or latest-closed rules;
- Twelve Data request semantics;
- effective-range determination;
- expected-bar and gap meaning;
- duplicate and conflict meaning;
- freshness thresholds;
- validator meaning;
- provider precedence.

---

# 24. Implementation Prohibitions

Implementation MUST NOT:

- align metals `D1` to UTC midnight as a physical market interval;
- treat the canonical midnight-UTC timestamp as the actual session boundary;
- use a fixed UTC offset for New York rollover;
- create Saturday or Sunday owner dates;
- assume every public holiday is a global spot-metals closure;
- classify provider silence as proof of market closure;
- accept an open or partial provider bar as closed;
- guess source timestamp meaning;
- infer price basis from numeric values;
- silently merge direct and derived bars;
- combine multiple providers into one derived bar;
- fabricate, interpolate, or forward-fill missing bars;
- silently overwrite conflicts;
- operate outside the approved effective range;
- use an unapproved lower timeframe for construction;
- claim acceptance without immutable provenance and validation proof;
- block unrelated operations because one date, source, or lane path is unresolved.

---

# 25. Amendment and Versioning

## 25.1 Version Rule

A new authority version is required when a change affects:

- the definition of metals `D1`;
- 17:00 New York alignment or boundary inclusion;
- close-date ownership;
- canonical timestamp meaning or encoding;
- direct-provider eligibility;
- lower-timeframe construction eligibility;
- complete-bar or latest-closed rules;
- provider request or response semantics;
- chunking or overlap rules;
- effective-range determination;
- expected-bar, gap, duplicate, or conflict rules;
- validation severity or meaning;
- freshness thresholds;
- provider precedence.

## 25.2 Amendment Record

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| 1.0 | 2026-07-11 | Initial metals `D1` constitutional authority drafted | Establish approved D1 operational truth before further timeframe implementation | PENDING |

## 25.3 Supersession

A superseded authority remains immutable and auditable.

A replacement MUST state:

- the authority it supersedes;
- its effective date;
- whether historical bars require re-evaluation;
- whether existing evidence remains compatible;
- whether lane or timestamp migration is required;
- how previously accepted evidence remains accessible.

---

# 26. Approval Gate

This authority may be marked **APPROVED** only when:

- `METALS_BASE_DOCTRINE_V1` is approved;
- market scope and inheritance are accepted;
- the New York 17:00 interval is accepted;
- close-date ownership is accepted;
- the midnight-UTC semantic timestamp encoding is accepted;
- direct provider and derived construction rules are accepted;
- Twelve Data request and response semantics are accepted;
- effective-range determination is accepted;
- gap materiality and repair rules are accepted;
- duplicate and conflict rules are accepted;
- `METALS_D1_VALIDATOR_V1` is accepted;
- freshness and Current-As-Of Truth rules are accepted;
- provider precedence is accepted;
- exceptions and approval identity are recorded;
- no unresolved template placeholder remains.

---

# 27. Acceptance Statement

Upon approval:

> `METALS_D1_AUTHORITY_V1` is the approved constitutional authority for `D1` evidence lanes within the Spot Precious Metals market ecosystem of Fragarach II. All specifications, implementations, acquisitions, validations, constructions, migrations, lane operations, and acceptance proofs for metals `D1` MUST conform to it.

---

# 28. Provider Reference Record

The following official provider documents informed the Version 1 draft request contract:

1. Twelve Data API Documentation — `time_series` parameters, supported ordering, timezone parameter, and response options:  
   `https://twelvedata.com/docs`
2. Twelve Data Support — *How to get historical prices*, including supported `1day` interval, `start_date`, `end_date`, `outputsize`, and bounded-range guidance:  
   `https://support.twelvedata.com/en/articles/5656039-how-to-get-historical-prices`
3. Twelve Data Support — *Getting historical data*, including the documented 5,000-data-point request maximum:  
   `https://support.twelvedata.com/en/articles/5214728-getting-historical-data`

Provider documentation describes external behaviour at drafting time.

Once approved, this document is the versioned Fragarach constitutional request contract. A material provider change requires compatibility review and, where necessary, an authority amendment.

---

# 29. Governing Principle

> An METALS daily bar is not merely a provider row labelled `1day`.  
> It is an owned New York rollover session, a declared evidence basis, a stable date identity, and a validated operational contract.

Provider data may map into that contract.

Specifications may implement it.

Implementation must never invent it.

**Operations is King.**
