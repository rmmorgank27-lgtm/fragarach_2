# TIMEFRAME AUTHORITY TEMPLATE V1

**Document Class:** Constitutional Authority Template  
**Authority Layer:** Market Timeframe  
**Version:** 1.0  
**Status:** TEMPLATE  
**Repository Location:** `constitution/templates/TIMEFRAME_AUTHORITY_TEMPLATE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Parent Market Authority:** `[MARKET_BASE_DOCTRINE_REFERENCE]`

---

# 1. Purpose

This template defines the mandatory structure for every Fragarach II timeframe authority document.

A timeframe authority establishes the approved operational truth for one timeframe within one market ecosystem.

It defines:

- what one bar represents;
- how intervals are aligned;
- which timestamp owns the bar;
- which sessions may contribute evidence;
- when a bar is complete;
- how provider data maps into the canonical interval;
- which historical ranges are valid;
- how gaps, duplicates, overlaps, and partial bars are classified;
- which validation rules govern the lane.

A timeframe authority does not define software architecture or database implementation.

It defines the facts that implementation specifications must consume.

---

# 2. Constitutional Position

The governing hierarchy is:

```text
Constitution

↓

Market Authority

↓

Timeframe Authority

↓

Specification

↓

Implementation

↓

Acceptance Proof
```

This timeframe authority MUST conform to its parent market authority.

Where conflict exists:

1. the Constitution overrides all subordinate documents;
2. the parent market authority overrides this timeframe authority;
3. this timeframe authority overrides implementation specifications;
4. implementation must never invent missing operational facts.

---

# 3. Template Use

Each timeframe authority created from this template shall replace all bracketed placeholders.

Examples:

```text
[MARKET_CODE]
[TIMEFRAME_CODE]
[INTERVAL_DURATION]
[BAR_TIMESTAMP_RULE]
```

No timeframe authority may be approved while unresolved placeholders remain.

Delete all drafting guidance before approval.

---

# 4. Document Identity

**Authority Name:** `[MARKET_CODE]_[TIMEFRAME_CODE]_AUTHORITY_V[AUTHORITY_VERSION]`  
**Market:** `[MARKET_NAME]`  
**Market Code:** `[MARKET_CODE]`  
**Timeframe:** `[TIMEFRAME_CODE]`  
**Version:** `[AUTHORITY_VERSION]`  
**Status:** `[DRAFT | REVIEW | APPROVED | SUPERSEDED | RETIRED]`  
**Effective From:** `[YYYY-MM-DD or repository checkpoint]`  
**Effective Until:** `[OPEN or YYYY-MM-DD]`  
**Parent Authority:** `[MARKET_BASE_DOCTRINE_REFERENCE]`  
**Supersedes:** `[NONE or prior authority identifier]`  
**Approved By:** `[APPROVING AUTHORITY]`  
**Approval Date:** `[YYYY-MM-DD]`

---

# 5. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

- **MUST / SHALL** indicates a mandatory constitutional requirement.
- **MUST NOT / SHALL NOT** indicates a prohibited action.
- **SHOULD** indicates the expected default unless a documented exception exists.
- **MAY** indicates permitted but optional behaviour.

Implementation specifications shall not weaken normative requirements defined here.

---

# 6. Timeframe Definition

## 6.1 Canonical Timeframe

**Timeframe Code:** `[TIMEFRAME_CODE]`  
**Nominal Duration:** `[INTERVAL_DURATION]`  
**Time Unit:** `[MINUTE | HOUR | DAY | WEEK | MONTH | OTHER]`

**Approved Definition:**

`[INSERT APPROVED TIMEFRAME DEFINITION]`

## 6.2 Bar Meaning

Define what one canonical bar represents.

A complete definition shall state:

- the interval covered;
- whether the interval is fixed-duration or calendar/session-derived;
- whether the bar represents trades, quotes, midpoint, settlement, or another approved price basis;
- whether extended-hours data is included;
- whether provider-side aggregation is accepted;
- whether Fragarach-side aggregation is permitted.

**Approved Bar Meaning:**

`[INSERT RULE]`

## 6.3 Fixed-Duration or Calendar-Derived

**Interval Type:** `[FIXED-DURATION | SESSION-DERIVED | CALENDAR-DERIVED | HYBRID]`

`[INSERT EXPLANATION]`

---

# 7. Interval Alignment Authority

## 7.1 Alignment Origin

Define the origin from which intervals are aligned.

Possible origins include:

- Unix epoch;
- UTC midnight;
- exchange-local midnight;
- session open;
- trading-day boundary;
- week boundary;
- month boundary;
- instrument-specific boundary.

**Approved Alignment Origin:**

`[INSERT RULE]`

## 7.2 Boundary Rule

Define the exact interval boundary rule.

Examples:

```text
[start, end)
```

or

```text
(session open, session close]
```

**Approved Boundary Rule:**

`[INSERT RULE]`

## 7.3 Alignment Formula

Where fixed-duration alignment applies, define the formula or unambiguous mapping.

`[INSERT FORMULA OR RULE]`

## 7.4 Session Crossing

Define whether a bar may cross:

- session boundaries;
- calendar days;
- week boundaries;
- month boundaries;
- daylight-saving transitions;
- maintenance breaks.

`[INSERT RULE]`

## 7.5 Partial Intervals

Define the treatment of intervals shortened by:

- early close;
- late open;
- market halt;
- provider outage;
- daylight-saving transition;
- instrument launch;
- delisting;
- incomplete acquisition.

`[INSERT RULE]`

---

# 8. Timestamp Authority

## 8.1 Canonical Timestamp Meaning

A canonical bar timestamp MUST have one approved meaning.

**Timestamp Meaning:** `[INTERVAL OPEN | INTERVAL CLOSE | SESSION DATE | OTHER]`  
**Canonical Timezone:** `[UTC or IANA TIMEZONE]`

**Approved Rule:**

`[INSERT RULE]`

## 8.2 Provider Timestamp Mapping

Define how each provider timestamp maps to the canonical bar timestamp.

| Provider | Provider Timestamp Meaning | Provider Timezone | Canonical Mapping | Notes |
|---|---|---|---|---|
| `[PROVIDER]` | `[MEANING]` | `[TIMEZONE]` | `[MAPPING]` | `[NOTES]` |

## 8.3 Date-Only Values

Define whether date-only values are valid.

**Date-Only Allowed:** `[YES | NO | CONDITIONAL]`

**Approved Rule:**

`[INSERT RULE]`

## 8.4 Ambiguous or Invalid Timestamps

Implementation MUST NOT guess when a provider timestamp is ambiguous.

The authority shall define:

- rejection rules;
- normalisation rules;
- exception rules;
- required provenance.

`[INSERT RULE]`

---

# 9. Trading-Day and Session Ownership

## 9.1 Inherited Market Rule

State the parent market rule inherited by this timeframe.

`[INSERT PARENT RULE REFERENCE]`

## 9.2 Timeframe-Specific Ownership

Define which trading day owns each bar.

**Approved Rule:**

`[INSERT RULE]`

## 9.3 Overnight Sessions

Define how bars are assigned when the session crosses midnight.

`[INSERT RULE OR NOT APPLICABLE]`

## 9.4 Week and Month Boundary Interaction

Define how this timeframe behaves at:

- final session of the week;
- first session of the week;
- final session of the month;
- first session of the month;
- holidays adjacent to boundaries.

`[INSERT RULE]`

---

# 10. Bar Construction Authority

## 10.1 Source of Construction

**Approved Construction Source:** `[DIRECT PROVIDER BAR | LOWER-TIMEFRAME ROLLUP | EITHER | OTHER]`

**Approved Rule:**

`[INSERT RULE]`

## 10.2 OHLC Construction

Where Fragarach-side aggregation is permitted:

- **Open** MUST equal `[RULE]`.
- **High** MUST equal `[RULE]`.
- **Low** MUST equal `[RULE]`.
- **Close** MUST equal `[RULE]`.
- **Volume** MUST equal `[RULE]`.

## 10.3 Source Timeframe Eligibility

List which lower timeframes may support construction.

| Source Timeframe | Permitted | Conditions | Notes |
|---|---|---|---|
| `[SOURCE TF]` | `[YES | NO]` | `[CONDITIONS]` | `[NOTES]` |

## 10.4 Direct Versus Derived Precedence

Define precedence where direct and derived bars both exist.

`[INSERT RULE]`

## 10.5 Missing Source Bars

Define whether a canonical bar may be constructed when one or more expected source bars are missing.

`[INSERT RULE]`

## 10.6 Cross-Provider Construction

Define whether one bar may be constructed from multiple providers.

**Cross-Provider Construction Allowed:** `[YES | NO | CONDITIONAL]`

`[INSERT RULE]`

---

# 11. Bar Completion Authority

## 11.1 Complete Bar Definition

A bar is complete only when:

`[INSERT COMPLETE BAR RULE]`

## 11.2 Latest Closed Bar

Define how Fragarach determines the latest closed bar.

The rule shall account for:

- current time;
- market timezone;
- session calendar;
- maintenance breaks;
- early closes;
- provider lag;
- delayed feeds;
- continuous markets.

**Approved Rule:**

`[INSERT RULE]`

## 11.3 Partial Bar Status

Define the approved status for a current, incomplete, or provisional bar.

Possible statuses include:

- `OPEN`;
- `PARTIAL`;
- `PROVISIONAL`;
- `CLOSED`;
- `FINAL`;
- `REVISED`.

**Approved Status Model:**

`[INSERT RULE]`

## 11.4 Revision Window

Define whether a closed bar may be revised by a provider and for how long.

`[INSERT RULE]`

---

# 12. Request and Response Authority

## 12.1 Provider Request Semantics

For every approved provider, define:

- request interval code;
- requested start meaning;
- requested end meaning;
- inclusive or exclusive boundaries;
- maximum rows;
- maximum time span;
- pagination or cursor semantics;
- chunking requirements;
- overlap requirements;
- rate limits;
- provider ordering.

| Provider | Interval Code | Start Rule | End Rule | Inclusivity | Limit | Chunk Rule |
|---|---|---|---|---|---|---|
| `[PROVIDER]` | `[CODE]` | `[RULE]` | `[RULE]` | `[RULE]` | `[LIMIT]` | `[RULE]` |

## 12.2 Response Semantics

Define:

- response timestamp meaning;
- ordering;
- duplicate behaviour;
- partial-bar inclusion;
- empty-response meaning;
- provider truncation behaviour;
- revision fields;
- error payload distinction.

`[INSERT RULE]`

## 12.3 Chunk Reassembly

Define how chunked responses are reassembled and validated.

`[INSERT RULE]`

## 12.4 Request Coverage Proof

An acquisition run MUST prove:

- requested range;
- received range;
- uncovered range;
- overlap range;
- row count;
- provider limit behaviour;
- whether the latest bar is partial.

---

# 13. Effective Historical Range

## 13.1 Timeframe Effective Range

**Effective Range Start:** `[YYYY-MM-DD or instrument-specific rule]`  
**Effective Range End:** `[OPEN or YYYY-MM-DD]`

## 13.2 Provider-Specific Ranges

| Provider | Instrument Scope | Earliest Reliable Bar | Latest Supported Bar | Notes |
|---|---|---|---|---|
| `[PROVIDER]` | `[SCOPE]` | `[DATE]` | `[RULE]` | `[NOTES]` |

## 13.3 Instrument-Specific Exceptions

| Instrument | Effective From | Reason | Authority Reference |
|---|---|---|---|
| `[INSTRUMENT]` | `[DATE]` | `[REASON]` | `[REFERENCE]` |

## 13.4 Historical Regime Changes

Define any period where alignment, session structure, provider quality, or market structure changed.

`[INSERT RULE OR NONE]`

---

# 14. Gap Authority

## 14.1 Expected Bar Rule

Define when a bar is expected to exist.

`[INSERT RULE]`

## 14.2 Valid Non-Bar Periods

Define periods that MUST NOT be classified as gaps.

Examples:

- market closure;
- weekend closure;
- holiday;
- maintenance break;
- pre-launch period;
- post-delisting period;
- approved session exclusion.

`[INSERT RULE]`

## 14.3 Gap Classification

| Classification | Meaning | Operational Consequence |
|---|---|---|
| `NOT_EXPECTED` | No bar should exist | No gap |
| `EXPECTED_MISSING` | A bar should exist but does not | Warning or repair candidate |
| `SOURCE_UNAVAILABLE` | Provider could not supply evidence | Retain visible uncertainty |
| `CONFLICTING_COVERAGE` | Providers disagree on existence | Retain conflict |
| `AUTHORITY_MISSING` | Expectedness cannot be determined | Compatibility stop |

Additional classifications:

`[INSERT IF REQUIRED]`

## 14.4 Gap Materiality

Define when missing bars are operationally material.

`[INSERT RULE]`

## 14.5 Gap Repair Authority

Define permitted repair sources and precedence.

`[INSERT RULE]`

Implementation MUST NOT fabricate a bar to fill a gap.

---

# 15. Duplicate and Overlap Authority

## 15.1 Canonical Identity

Define the canonical uniqueness key.

```text
[INSTRUMENT KEY] + [TIMEFRAME] + [CANONICAL TIMESTAMP]
```

## 15.2 Exact Duplicate

Define when two bars are exact duplicates.

`[INSERT RULE]`

## 15.3 Conflicting Duplicate

Define when two bars conflict.

`[INSERT RULE]`

## 15.4 Provider Overlap

Define how overlapping requests and repeated acquisitions are classified.

`[INSERT RULE]`

## 15.5 Resolution Rule

Conflicts MUST NOT be resolved by silent overwrite.

**Approved Resolution Rule:**

`[INSERT RULE]`

---

# 16. Price and Volume Semantics

## 16.1 Inherited Price Basis

State the parent market price basis.

`[INSERT PARENT RULE REFERENCE]`

## 16.2 Timeframe-Specific Price Rule

Define any timeframe-specific requirement.

`[INSERT RULE OR NONE]`

## 16.3 Volume Aggregation

Define volume semantics for direct and derived bars.

`[INSERT RULE]`

## 16.4 Null and Zero Volume

Define valid treatment.

`[INSERT RULE]`

---

# 17. Validation Authority

## 17.1 Mandatory Validation Rules

Every bar MUST be evaluated for:

- canonical instrument identity;
- canonical timeframe identity;
- timestamp validity;
- interval alignment;
- session membership;
- calendar membership;
- OHLC validity;
- numeric validity;
- monotonic ordering;
- duplicate status;
- completion status;
- provider coverage;
- effective-range eligibility.

Additional mandatory rules:

`[INSERT RULES]`

## 17.2 OHLC Rules

At minimum:

```text
high >= open
high >= close
low <= open
low <= close
high >= low
```

Define treatment of zero, negative, null, NaN, and infinite values.

`[INSERT RULE]`

## 17.3 Alignment Validation

Define the exact test proving that a timestamp is correctly aligned.

`[INSERT RULE]`

## 17.4 Session Validation

Define the exact test proving that the interval belongs to an approved session.

`[INSERT RULE]`

## 17.5 Validation Severity

| Condition | Severity | Consequence |
|---|---|---|
| `[CONDITION]` | `[INFO | WARNING | REJECT | CONFLICT | BLOCKED]` | `[ACTION]` |

## 17.6 Validator Authority

Name the approved validator contract or rule set.

**Validator Authority:** `[VALIDATOR AUTHORITY IDENTIFIER]`

Implementation MAY encode this authority, but MUST NOT alter its meaning.

---

# 18. Evidence Lane Contract

## 18.1 Lane Identity

The canonical evidence lane is:

```text
[INSTRUMENT] / [TIMEFRAME]
```

Additional lane dimensions, where approved:

`[INSERT DIMENSIONS OR NONE]`

## 18.2 Lane Eligibility

A lane may exist only when:

- the instrument is registered;
- the parent market authority is approved;
- this timeframe authority is approved;
- provider mappings exist;
- effective range is known;
- session and calendar authority are resolvable.

## 18.3 Lane Status

Define permitted statuses.

| Status | Meaning |
|---|---|
| `REGISTERED` | Lane identity exists |
| `ACTIVE` | Acquisition and validation are permitted |
| `SUSPENDED` | New operations paused, evidence retained |
| `RETIRED` | Lane no longer operational, evidence retained |
| `BLOCKED` | Required authority is incomplete |

## 18.4 Lane Provenance

Every accepted bar MUST remain traceable to:

- evidence block;
- provider;
- source symbol;
- acquisition run;
- parser or adapter version;
- validation result;
- transformation or rollup rule where applicable.

---

# 19. Operational Freshness Authority

## 19.1 Freshness Reference

Define the timestamp against which freshness is measured.

Possible references:

- latest expected closed bar;
- latest provider-available bar;
- latest session close;
- current canonical interval boundary.

**Approved Reference:**

`[INSERT RULE]`

## 19.2 Freshness States

| State | Definition | Operational Meaning |
|---|---|---|
| `CURRENT` | `[RULE]` | Normal operation |
| `DELAYED` | `[RULE]` | Usable with warning |
| `STALE` | `[RULE]` | Use best available evidence with prominent warning |
| `UNKNOWN` | `[RULE]` | Authority or evidence insufficient |

## 19.3 Non-Blocking Operation

Where usable closed evidence exists, freshness degradation SHOULD be reported without unnecessarily denying access to that evidence.

Missing constitutional authority remains a compatibility stop.

---

# 20. Provider Precedence for This Timeframe

Define timeframe-specific precedence only where the parent market authority permits it.

| Priority | Provider | Role | Conditions |
|---|---|---|---|
| `1` | `[PROVIDER]` | `[ROLE]` | `[CONDITIONS]` |

**Approved Conflict Rule:**

`[INSERT RULE]`

---

# 21. Exceptions

Any timeframe exception MUST include:

- exception identifier;
- affected instruments;
- affected provider;
- affected date range;
- affected session or interval;
- reason;
- approval;
- expiry or review date;
- required provenance.

| Exception ID | Scope | Rule | Effective Range | Approval | Status |
|---|---|---|---|---|---|
| `[ID]` | `[SCOPE]` | `[RULE]` | `[RANGE]` | `[APPROVER]` | `[STATUS]` |

No undocumented exception is valid.

---

# 22. Compatibility Requirements

Before implementation begins, the responsible specification MUST prove that:

- the parent market authority is approved;
- this timeframe authority is approved;
- interval duration is explicit;
- alignment origin is explicit;
- boundary rule is explicit;
- canonical timestamp meaning is explicit;
- session and trading-day ownership are explicit;
- complete-bar definition is explicit;
- latest-closed-bar rule is explicit;
- provider request semantics are explicit;
- provider response semantics are explicit;
- chunking rules are explicit;
- effective range is explicit;
- validator authority is explicit;
- gap rules are explicit;
- duplicate and conflict rules are explicit;
- no implementation-critical placeholder remains unresolved.

Where any requirement fails, implementation MUST produce a compatibility report and stop the affected path.

---

# 23. Specification Boundary

Specifications consuming this authority MAY define:

- schemas;
- acquisition clients;
- chunk orchestration;
- parsing code;
- validation code;
- evidence storage;
- lane registration workflow;
- application operations;
- migrations;
- tests;
- acceptance reports.

Specifications MUST NOT redefine:

- interval meaning;
- timestamp meaning;
- interval alignment;
- trading-day ownership;
- session ownership;
- complete-bar rules;
- provider request semantics;
- provider response semantics;
- effective historical range;
- gap meaning;
- duplicate conflict meaning;
- validator meaning.

---

# 24. Implementation Prohibitions

Implementation MUST NOT:

- guess interval alignment;
- infer timestamp meaning from sample data alone;
- assume provider bars are open-stamped or close-stamped;
- silently shift timestamps;
- silently drop partial bars;
- silently include partial bars as closed bars;
- silently merge providers;
- fabricate missing bars;
- resolve conflicting duplicates by overwrite;
- apply a calendar not approved by the parent authority;
- operate outside the approved effective range;
- claim lane acceptance without provenance and validation proof.

---

# 25. Amendment and Versioning

## 25.1 Version Rule

A new authority version is required when a change affects:

- interval duration;
- alignment origin;
- boundary semantics;
- timestamp meaning;
- session ownership;
- trading-day ownership;
- bar completion;
- provider request or response semantics;
- chunking rules;
- effective range;
- gap classification;
- duplicate resolution;
- validation meaning;
- construction or rollup rules.

## 25.2 Amendment Record

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| `[VERSION]` | `[DATE]` | `[CHANGE]` | `[REASON]` | `[APPROVER]` |

## 25.3 Supersession

A superseded timeframe authority remains immutable and auditable.

The replacement authority MUST state:

- which version it supersedes;
- its effective date;
- whether historical bars must be re-evaluated;
- whether existing evidence lanes remain compatible;
- whether migrations are required.

---

# 26. Approval Gate

This authority may be marked **APPROVED** only when:

- every placeholder is resolved;
- the parent authority is approved;
- bar meaning is explicit;
- interval alignment is explicit;
- timestamp meaning is explicit;
- trading-day ownership is explicit;
- session interaction is explicit;
- bar construction is explicit;
- completion rules are explicit;
- provider request and response semantics are explicit;
- effective ranges are explicit;
- gap rules are explicit;
- duplicate and conflict rules are explicit;
- validation authority is explicit;
- operational freshness rules are explicit;
- exceptions are documented;
- approval is recorded.

---

# 27. Acceptance Statement

Upon approval, the following statement shall be completed.

> `[MARKET_CODE]_[TIMEFRAME_CODE]_AUTHORITY_V[AUTHORITY_VERSION]` is the approved constitutional authority for `[TIMEFRAME_CODE]` evidence lanes within the `[MARKET_NAME]` market ecosystem. All specifications, implementations, acquisitions, validations, migrations, lane operations, and acceptance proofs for this market and timeframe MUST conform to it.

---

# 28. Governing Principle

> A timeframe is not merely a provider interval code.  
> It is an approved operational contract governing time, session, evidence, completion, and validation.

Implementation may encode that contract.

Implementation must never invent it.

**Operations is King.**
