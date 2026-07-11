# MARKET AUTHORITY TEMPLATE V1

**Document Class:** Constitutional Authority Template  
**Authority Layer:** Market Ecosystem  
**Version:** 1.0  
**Status:** TEMPLATE  
**Repository Location:** `constitution/templates/MARKET_AUTHORITY_TEMPLATE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`

---

# 1. Purpose

This template defines the mandatory structure for every Fragarach II market-level authority document.

A market authority establishes the approved operational truth for a market ecosystem.

It defines:

- what the market is;
- which instruments belong to it;
- which calendars and session models govern it;
- which provider semantics are acceptable;
- which market-wide validation rules apply;
- which operational facts may be inherited by timeframe authorities;
- which facts must never be invented by implementation.

A market authority does not define software behaviour.

It defines the operational facts that software specifications must consume.

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

Where conflict exists:

1. the Constitution overrides this authority;
2. this authority overrides all subordinate timeframe authorities;
3. approved timeframe authorities override implementation specifications;
4. implementation must never invent missing authority.

---

# 3. Template Use

Each market authority created from this template shall replace all bracketed placeholders.

Examples:

```text
[MARKET_NAME]
[MARKET_CODE]
[AUTHORITY_VERSION]
[EFFECTIVE_FROM]
```

No authority may be approved while unresolved placeholders remain.

Delete all drafting guidance before approval.

---

# 4. Document Identity

**Authority Name:** `[MARKET_NAME]_BASE_DOCTRINE_V[AUTHORITY_VERSION]`  
**Market Name:** `[MARKET_NAME]`  
**Market Code:** `[MARKET_CODE]`  
**Version:** `[AUTHORITY_VERSION]`  
**Status:** `[DRAFT | REVIEW | APPROVED | SUPERSEDED | RETIRED]`  
**Effective From:** `[YYYY-MM-DD or repository checkpoint]`  
**Effective Until:** `[OPEN or YYYY-MM-DD]`  
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

# 6. Market Definition

## 6.1 Market Identity

Define the market ecosystem in operational terms.

The definition shall state:

- the market’s economic and trading identity;
- the venue model or decentralised model;
- whether instruments trade through one venue, multiple venues, dealer networks, or continuous networks;
- the relationship between the market and its recognised trading sessions;
- any material regional or legal distinctions.

**Approved Definition:**

`[INSERT APPROVED MARKET DEFINITION]`

## 6.2 Market Boundary

State what is inside and outside this authority.

**Included:**

- `[INCLUDED INSTRUMENT CLASS OR VENUE]`
- `[INCLUDED INSTRUMENT CLASS OR VENUE]`

**Excluded:**

- `[EXCLUDED INSTRUMENT CLASS OR VENUE]`
- `[EXCLUDED INSTRUMENT CLASS OR VENUE]`

## 6.3 Market Classification

**Asset Class:** `[ASSET CLASS]`  
**Instrument Type Family:** `[INSTRUMENT TYPE FAMILY]`  
**Venue Model:** `[CENTRALISED | MULTI-VENUE | OTC | DECENTRALISED | HYBRID]`  
**Trading Model:** `[SESSION-BASED | CONTINUOUS | NEAR-CONTINUOUS | OTHER]`  
**Primary Quote Convention:** `[QUOTE CONVENTION]`

---

# 7. Instrument Membership Authority

## 7.1 Membership Rule

Define the constitutional rule determining whether an instrument belongs to this market.

`[INSERT MEMBERSHIP RULE]`

## 7.2 Required Instrument Metadata

Every registered instrument governed by this authority MUST have approved values for:

- canonical symbol;
- display name;
- asset class;
- instrument type;
- market code;
- exchange or venue identity where applicable;
- base currency where applicable;
- quote currency where applicable;
- price precision;
- quantity precision where applicable;
- timezone authority;
- session authority reference;
- calendar authority reference;
- provider symbol mappings;
- operational status.

Additional required metadata:

`[INSERT MARKET-SPECIFIC REQUIRED METADATA]`

## 7.3 Prohibited Assumptions

Implementation MUST NOT infer market membership from symbol spelling alone.

Implementation MUST NOT invent:

- venue identity;
- exchange identity;
- asset class;
- instrument type;
- quote convention;
- timezone;
- session ownership;
- calendar ownership.

Missing values require a compatibility report.

---

# 8. Calendar Authority

## 8.1 Governing Calendar Model

Define the approved market calendar model.

**Calendar Type:** `[EXCHANGE CALENDAR | OTC CALENDAR | CONTINUOUS CALENDAR | HYBRID]`  
**Calendar Identifier:** `[CALENDAR AUTHORITY IDENTIFIER]`  
**Timezone:** `[IANA TIMEZONE]`

**Approved Rule:**

`[INSERT CALENDAR RULE]`

## 8.2 Trading-Day Ownership

Define which civil date owns a trading session.

Examples include:

- session-open date;
- session-close date;
- exchange-local date;
- UTC date;
- provider-labelled date only where constitutionally approved.

**Approved Trading-Day Ownership Rule:**

`[INSERT RULE]`

## 8.3 Week and Month Ownership

Define how trading weeks and trading months are assigned.

**Trading Week Rule:**

`[INSERT RULE]`

**Trading Month Rule:**

`[INSERT RULE]`

## 8.4 Holidays and Closures

Define the authority for:

- full-day closures;
- partial-day sessions;
- early closes;
- unscheduled closures;
- daylight-saving transitions;
- venue-specific exceptions.

**Approved Holiday Authority:**

`[INSERT AUTHORITY AND RULE]`

## 8.5 Calendar Amendment Rule

Calendar corrections MUST be versioned and auditable.

An implementation MUST NOT silently alter historical session ownership.

---

# 9. Session Authority

## 9.1 Session Model

Define the market-wide session model.

**Session Model Name:** `[SESSION MODEL]`  
**Session Timezone:** `[IANA TIMEZONE]`

**Approved Session Definition:**

`[INSERT SESSION DEFINITION]`

## 9.2 Session Components

Where applicable, define:

- pre-market;
- regular trading session;
- post-market;
- overnight session;
- settlement window;
- maintenance break;
- weekend closure;
- auction periods;
- half-day sessions.

`[INSERT APPROVED COMPONENTS]`

## 9.3 Session Precedence

Where instrument, venue, and market-level session rules differ, define precedence.

**Approved Precedence:**

```text
[HIGHEST AUTHORITY]

↓

[SECONDARY AUTHORITY]

↓

[DEFAULT AUTHORITY]
```

## 9.4 Continuous and Near-Continuous Markets

Where the market is continuous or near-continuous, define:

- operational day boundary;
- maintenance windows;
- provider rollover treatment;
- weekend treatment;
- session-gap classification.

`[INSERT RULE]`

---

# 10. Provider Authority

## 10.1 Approved Provider Roles

Providers MUST be classified by role.

Possible roles include:

- primary acquisition provider;
- secondary acquisition provider;
- historical backfill provider;
- verification provider;
- manual evidence source;
- emergency fallback provider.

| Provider | Approved Role | Instruments | Timeframes | Effective Range | Notes |
|---|---|---|---|---|---|
| `[PROVIDER]` | `[ROLE]` | `[SCOPE]` | `[SCOPE]` | `[RANGE]` | `[NOTES]` |

## 10.2 Provider Semantics

For each approved provider, define:

- timestamp meaning;
- interval start or end semantics;
- timezone;
- session assumptions;
- inclusion or exclusion of extended hours;
- partial-bar behaviour;
- revision behaviour;
- history limits;
- request limits;
- chunking constraints;
- ordering guarantees;
- duplicate behaviour;
- null-volume behaviour;
- adjusted versus unadjusted prices;
- corporate-action treatment where applicable.

Provider semantics shall be recorded in subordinate provider authority records or directly in this authority.

## 10.3 Provider Precedence

Define the approved precedence when multiple providers supply overlapping evidence.

`[INSERT PRECEDENCE RULE]`

## 10.4 Provider Conflict Rule

Provider disagreement MUST NOT be resolved by silent replacement.

Conflicting evidence MUST be retained and evaluated according to approved validation authority.

---

# 11. Evidence Authority

## 11.1 Evidence Principle

Evidence is immutable once accepted into the evidence layer.

Corrections MUST be represented by new evidence, new provenance, and an auditable decision.

## 11.2 Acceptable Evidence Sources

Define acceptable evidence source classes.

- `[PROVIDER API]`
- `[PROVIDER FILE]`
- `[MANUAL FILE]`
- `[EXCHANGE PUBLICATION]`
- `[OTHER APPROVED SOURCE]`

## 11.3 Evidence Identity

Every evidence block MUST identify:

- source provider;
- source symbol;
- canonical instrument;
- requested range;
- received range;
- timeframe;
- row count;
- checksum;
- acquisition timestamp;
- parser or adapter version;
- source metadata;
- evidence status.

## 11.4 Evidence Retention

Accepted, rejected, conflicting, superseded, and duplicate evidence MUST remain auditable according to repository retention policy.

## 11.5 Evidence Prohibitions

Implementation MUST NOT:

- fabricate missing bars;
- silently mutate accepted evidence;
- discard conflicting evidence without record;
- relabel provider timestamps without approved transformation authority;
- convert adjusted data to unadjusted data by assumption;
- merge venue data without approved aggregation authority.

---

# 12. Market-Wide Validation Authority

## 12.1 Validation Scope

Define validation rules that apply to every timeframe in this market.

Possible rules include:

- canonical identity validation;
- timestamp parseability;
- timezone validity;
- OHLC consistency;
- numeric validity;
- duplicate classification;
- monotonic ordering;
- session membership;
- calendar membership;
- price precision;
- volume semantics;
- provider-range validation.

## 12.2 Mandatory Market-Wide Rules

`[INSERT APPROVED RULES]`

## 12.3 Severity Model

Define approved validation severities.

| Severity | Meaning | Operational Consequence |
|---|---|---|
| `INFO` | Observed condition | Retain and report |
| `WARNING` | Non-fatal uncertainty | Continue with visible warning |
| `REJECT` | Evidence is not acceptable | Reject affected evidence |
| `CONFLICT` | Valid evidence disagrees | Retain all evidence and require resolution |
| `BLOCKED` | Constitutional authority is missing | Stop affected implementation path and emit compatibility report |

A market authority MAY define additional severities.

## 12.4 Non-Blocking Doctrine

Operational uncertainty SHOULD remain visible without unnecessarily denying access to usable evidence.

However, implementation MUST stop where required constitutional authority is absent.

The distinction is:

- uncertain evidence may remain operational with warnings where approved;
- missing authority may not be invented.

---

# 13. Corporate Actions and Structural Events

Where applicable, define authority for:

- stock splits;
- reverse splits;
- dividends;
- symbol changes;
- mergers;
- demergers;
- delistings;
- contract rolls;
- index reconstitutions;
- redenominations;
- token migrations;
- forks;
- market suspensions.

**Approved Rule:**

`[INSERT RULE OR STATE NOT APPLICABLE]`

---

# 14. Price and Volume Semantics

## 14.1 Price Authority

Define whether approved price evidence is:

- trade price;
- bid;
- ask;
- midpoint;
- last;
- indicative;
- settlement;
- official close;
- adjusted close;
- venue aggregate.

`[INSERT RULE]`

## 14.2 Volume Authority

Define the meaning of volume.

Possible meanings include:

- units traded;
- contracts traded;
- quote volume;
- tick count;
- provider-estimated volume;
- unavailable.

`[INSERT RULE]`

## 14.3 Zero and Null Volume

Define whether zero, null, or absent volume is valid.

`[INSERT RULE]`

---

# 15. Effective Historical Range

## 15.1 Market-Level Effective Range

Define the earliest date from which this authority may be applied.

**Effective Range Start:** `[YYYY-MM-DD or instrument-specific rule]`  
**Effective Range End:** `[OPEN or YYYY-MM-DD]`

## 15.2 Instrument-Specific Exceptions

| Instrument or Class | Effective From | Reason | Authority Reference |
|---|---|---|---|
| `[INSTRUMENT]` | `[DATE]` | `[REASON]` | `[REFERENCE]` |

## 15.3 Historical Uncertainty

Where historical market structure changed, the authority MUST state:

- the change date;
- the previous regime;
- the replacement regime;
- whether evidence requires reclassification;
- whether one authority version may span both regimes.

---

# 16. Timeframe Authority Inheritance

Every timeframe authority under this market MUST inherit:

- market identity;
- instrument membership rules;
- calendar authority;
- session authority;
- provider roles;
- market-wide evidence rules;
- market-wide validation rules;
- effective historical constraints;
- amendment and approval rules.

A timeframe authority MAY narrow or specialise inherited rules only where this market authority explicitly permits it.

A timeframe authority MUST NOT contradict this authority.

---

# 17. Required Timeframe Authorities

List the timeframe authorities required for this market.

| Timeframe | Required Authority | Status | Notes |
|---|---|---|---|
| `D1` | `[MARKET_CODE]_D1_AUTHORITY_V1` | `[STATUS]` | `[NOTES]` |
| `H1` | `[MARKET_CODE]_H1_AUTHORITY_V1` | `[STATUS]` | `[NOTES]` |
| `M30` | `[MARKET_CODE]_M30_AUTHORITY_V1` | `[STATUS]` | `[NOTES]` |
| `M5` | `[MARKET_CODE]_M5_AUTHORITY_V1` | `[STATUS]` | `[NOTES]` |

Add or remove rows only by approved market decision.

---

# 18. Compatibility Requirements

Before implementation begins, the responsible specification MUST prove that:

- this authority is approved;
- all required timeframe authorities are approved;
- every referenced provider authority exists;
- every referenced calendar and session authority exists;
- required instrument metadata is registered;
- effective ranges are known;
- no implementation-critical placeholder remains unresolved.

Where any requirement fails, implementation MUST produce a compatibility report and stop the affected path.

---

# 19. Specification Boundary

Specifications consuming this authority MAY define:

- database changes;
- API contracts;
- command behaviour;
- application workflows;
- adapters;
- validation implementation;
- migrations;
- acceptance tests;
- reports.

Specifications MUST NOT redefine:

- market identity;
- session ownership;
- calendar ownership;
- provider timestamp semantics;
- trading-day ownership;
- price meaning;
- volume meaning;
- effective historical range;
- authority precedence.

---

# 20. Implementation Prohibitions

Implementation MUST NOT:

- guess missing authority;
- infer constitutional facts from existing code;
- treat legacy behaviour as authority unless explicitly adopted;
- silently choose between conflicting providers;
- silently rewrite timestamps;
- silently alter trading-day ownership;
- silently expand the market boundary;
- use a timeframe before its authority is approved;
- claim acceptance without evidence.

---

# 21. Exceptions

Any exception MUST include:

- exception identifier;
- affected instruments;
- affected timeframes;
- reason;
- approving authority;
- effective range;
- expiry or review date;
- operational impact;
- evidence requirements.

| Exception ID | Scope | Rule | Effective Range | Approval | Status |
|---|---|---|---|---|---|
| `[ID]` | `[SCOPE]` | `[RULE]` | `[RANGE]` | `[APPROVER]` | `[STATUS]` |

No undocumented exception is valid.

---

# 22. Amendment and Versioning

## 22.1 Version Rule

A new authority version is required when a change affects:

- market boundary;
- calendar authority;
- session authority;
- trading-day ownership;
- provider semantics;
- validation meaning;
- price or volume semantics;
- effective historical range;
- subordinate timeframe inheritance.

## 22.2 Amendment Record

| Version | Date | Change | Reason | Approved By |
|---|---|---|---|---|
| `[VERSION]` | `[DATE]` | `[CHANGE]` | `[REASON]` | `[APPROVER]` |

## 22.3 Supersession

A superseded authority remains immutable and auditable.

The replacement authority MUST state:

- which version it supersedes;
- its effective date;
- whether historical evidence must be re-evaluated;
- whether existing implementations remain compatible.

---

# 23. Approval Gate

This authority may be marked **APPROVED** only when:

- every placeholder is resolved;
- scope is explicit;
- calendar authority is explicit;
- session authority is explicit;
- trading-day ownership is explicit;
- provider roles and semantics are explicit;
- evidence rules are explicit;
- validation rules are explicit;
- effective range is explicit;
- required timeframe authorities are listed;
- exceptions are documented;
- approval is recorded.

---

# 24. Acceptance Statement

Upon approval, the following statement shall be completed.

> `[MARKET_NAME]_BASE_DOCTRINE_V[AUTHORITY_VERSION]` is the approved constitutional authority for the `[MARKET_NAME]` market ecosystem within Fragarach II. All subordinate timeframe authorities, specifications, implementations, migrations, validations, and acceptance proofs MUST conform to it.

---

# 25. Governing Principle

> Constitution defines what is true.  
> Authority makes that truth operational.  
> Specifications define how Fragarach implements it.  
> Implementation must never invent authority.

**Operations is King.**
