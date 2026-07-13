# SPEC-026 — Market History Service and Consumer Authority Contract

**Document ID:** `SPEC-026_MARKET_HISTORY_SERVICE_AND_CONSUMER_AUTHORITY_CONTRACT`

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`

**Date:** `2026-07-13`

**Baseline:** `Fragarach II v1.0a` plus the commissioned `SPEC-025 Revision 1` implementation scope

**Status:** `APPROVED AND IMPLEMENTED — DIRECT HISTORY COMMISSIONED; H4/M15 CONSTRUCTION INACTIVE`

**Revision:** `1 — Consumer Ownership Amendment`

**Classification:** `Ecosystem Operational Architecture`

**Doctrine:** `Operations is King / Authority First / Consumers Never Determine Historical Truth`

---

# 1. Executive Decision

Fragarach II shall be the Market History Service for the ecosystem.

Fragarach alone owns the determination of historical market truth, including:

- canonical OHLC;
- timeframe construction;
- session ownership;
- timestamp meaning and alignment;
- Current-As-Of Date Time (`CAODT`);
- historical availability, completeness, and warnings.

Consumers request history and perform analysis. They do not acquire, select, validate, repair, align, count, resample, roll up, or reconstruct market history.

The permanent service boundary is:

```text
Fragarach
    answers: What happened?

Consumer
    answers: What does it mean?
```

`H4` from `H1` and `M15` from `M5` are initial internal construction cases. They are not the purpose or public identity of this specification.

Functional implementation of Revision 1 was authorised by the operator on `2026-07-13`. That approval commissions the consumer-neutral service and direct-history paths. It does not commission H4 or M15 construction authority.

---

# 2. Governing Authorities and Specifications

This specification consumes and remains subordinate to:

- `FRAGARACH_II_CONSTITUTION_V1`;
- any approved target-timeframe or transformation authority governing duration, alignment, session ownership, timestamp meaning, construction eligibility, and completion;
- `CALENDAR_DOCTRINE_V1`;
- `TRUTH_STORE_DOCTRINE`;
- `FRAGARACH_II_D1_GAP_DOCTRINE_V1` and every applicable approved timeframe gap authority;
- `SPEC-009A_OPERATIONAL_AUTHORITY_SERVICE_CONTRACT`;
- `SPEC-009B_TRUTH_ENGINE_V1`;
- `SPEC-009C_ESTATE_TRUTH_SERVICE`;
- `SPEC-018_EXTERNAL_CONSUMER_DATA_CONTRACT`;
- `SPEC-025_CORE_MULTI_TIMEFRAME_AUTHORITY`.

The exact market and source-timeframe authorities governing the current specification scope are:

| Market | Base Doctrine | Applicable source Timeframe Authorities |
|---|---|---|
| Forex | `FX_BASE_DOCTRINE_V1` | `FX_D1_AUTHORITY_V1`, `FX_H1_AUTHORITY_V1`, `FX_M30_AUTHORITY_V1`, `FX_M5_AUTHORITY_V1` |
| Metals | `METALS_BASE_DOCTRINE_V1` | `METALS_D1_AUTHORITY_V1`, `METALS_H1_AUTHORITY_V1`, `METALS_M30_AUTHORITY_V1`, `METALS_M5_AUTHORITY_V1` |
| Energy | `ENERGY_BASE_DOCTRINE_V1` | `ENERGY_D1_AUTHORITY_V1`, `ENERGY_H1_AUTHORITY_V1`, `ENERGY_M30_AUTHORITY_V1`, `ENERGY_M5_AUTHORITY_V1` |
| Indices | `INDICES_BASE_DOCTRINE_V1` | `INDICES_D1_AUTHORITY_V1`, `INDICES_H1_AUTHORITY_V1`, `INDICES_M30_AUTHORITY_V1`, `INDICES_M5_AUTHORITY_V1` |
| Crypto | `CRYPTO_BASE_DOCTRINE_V1` | `CRYPTO_D1_AUTHORITY_V1`, `CRYPTO_H1_AUTHORITY_V1`, `CRYPTO_M30_AUTHORITY_V1`, `CRYPTO_M5_AUTHORITY_V1` |
| United States Equities | `US_EQUITIES_BASE_DOCTRINE_V1` | `US_EQUITIES_D1_AUTHORITY_V1` |
| United Kingdom Equities | `UK_EQUITIES_BASE_DOCTRINE_V1` | `UK_EQUITIES_D1_AUTHORITY_V1` |
| German Equities | `GERMAN_EQUITIES_BASE_DOCTRINE_V1` | `GERMAN_EQUITIES_D1_AUTHORITY_V1` |
| Australian Equities | `AUSTRALIAN_EQUITIES_BASE_DOCTRINE_V1` | `AUSTRALIAN_EQUITIES_D1_AUTHORITY_V1` |

Stock intraday authorities remain outside commissioned source policy under SPEC-025 even where constitutional documents exist. Adding another market, representation, source timeframe, or transformation requires a compatibility amendment that cites its exact approved authority before activation.

Authority applicability does not imply operational capability. The service may fulfil a request only from lanes commissioned and servable under SPEC-025 and later accepted activation work.

This specification does not invent constitutional facts. In particular, it does not itself establish an `H4` or `M15` duration, alignment grid, owner-day rule, timestamp meaning, partial-session rule, or construction eligibility. Where that authority is absent, the affected derived timeframe remains unavailable while unrelated history continues to operate.

After approval, this specification supersedes only the following consumer-facing details of earlier specifications:

- provider summary and operational implementation metadata are not part of the analysis response;
- consumers request authority-owned time windows rather than implementation-owned bar counts;
- a versioned successor to `get_history(symbol, timeframe)` may add a history window without breaking the existing SPEC-018 D1 or SPEC-025 contracts.

Internal evidence, provenance, validation, Truth, Estate Truth, provider, and operational-console obligations remain unchanged.

---

# 3. Architectural Doctrine

> **Consumers never determine historical truth. They consume it.**

This doctrine applies equally to SignalBar, Sea Eagle, Market Scout, HARP, Morphix, and every future consumer.

No consumer-specific historical-data path is permitted. Every consumer receives the same historical meaning for the same symbol, timeframe, window, authority state, and `CAODT`.

The doctrine is independent of transport, provider, storage engine, application language, and future timeframe expansion.

---

# 3A. Market History Ownership

The Market History Service owns historical market truth.

Consumers own only the analysis they derive from that history.

Ownership is permanently divided:

```text
Fragarach
==========
Owns:

• Market History
• Historical Truth
• Canonical OHLC
• Timeframes
• Sessions
• Alignment
• CAODT
• Historical Warnings

↓

Consumers
==========
Own:

• Signal Bars
• Pin Bars
• Active Range
• Potential Scan
• ADR
• C24
• Rankings
• Forecasts
• Research
• Visualisation
```

Historical ownership never passes to a consumer.

Analytical ownership never passes to Fragarach.

No application may assume responsibility owned by the other.

---

# 3B. Market History Identity

Throughout this specification, the externally visible service is the:

```text
Market History Service
```

The externally visible product supplied to consumers is:

```text
Market History
```

The service is intentionally independent of the internal implementation used to construct that history.

Internally, Fragarach may use:

- direct canonical authority;
- deterministic derived views;
- future authority mechanisms;
- future providers.

Externally, every successful response is simply:

```text
Market History
```

Consumers must not determine or infer how the history was produced.

---

# 4. Authority Boundary

## 4.1 Fragarach responsibility

Fragarach exclusively determines:

- canonical instrument identity;
- requested timeframe meaning;
- canonical source history;
- direct or derived fulfilment;
- provider and evidence precedence;
- provenance and effective segments;
- validation and gap classification;
- session and trading-day ownership;
- calendar, holiday, closure, and daylight-saving interpretation;
- target interval alignment and completion;
- deterministic OHLC construction where authorised;
- freshness and `CAODT`;
- service status and historical warnings;
- the exact bounded history returned.

These responsibilities may be implemented by existing authority, Truth, Estate Truth, calendar, validation, and history-service components. They remain one Fragarach responsibility at the ecosystem boundary.

## 4.2 Consumer responsibility

Consumers receive historical OHLC and perform analysis only.

A consumer may calculate, for example:

- Signal Bars;
- Pin Bars;
- Active Range;
- Potential Scan;
- ADR;
- C24;
- rankings;
- analysis diagnostics.

A consumer never determines or requests:

- provider;
- evidence selection;
- provenance;
- validation policy;
- gap policy;
- derivation method;
- source timeframe;
- rollup mechanics;
- session alignment;
- calendar-day conversion;
- bar count needed to represent a time window.

Fragarach shall not perform consumer analysis. Consumers shall not reconstruct history.

---

# 5. Consumer Request Contract

## 5.1 Logical request

The logical request is:

```text
get_history(
    symbol,
    timeframe,
    window
)
```

A request identifies only:

```text
Symbol
Timeframe
Authority-owned time window
```

Examples:

```text
AUDUSD
H1
Last 21 trading days
```

```text
XAUUSD
M15
Last 5 trading days
```

```text
AUDUSD
D1
Last 365 trading days
```

```text
AUDUSD
H4
Between A and B
```

## 5.2 Permitted window forms

The versioned service contract shall support:

```text
LAST_TRADING_DAYS(n)
BETWEEN(start, end)
LAST_TRADING_DAYS_ENDING_AT_LATEST_CAODT(n)
```

`LAST_TRADING_DAYS(n)` defaults to ending at the latest `CAODT` available for the requested history.

The contract may later add other time-based window forms through normal versioning. It must not expose source-bar requirements or derivation controls.

## 5.3 Forbidden request fields

Consumers must never send:

```text
bar_count
output_size
provider
provider_contract
source_timeframe
derive_from
rollup_method
alignment
session
calendar
gap_policy
validation_policy
```

Requests such as these are outside the authority contract:

```text
486 bars
derive H4 from H1
derive M15 from M5
use Twelve Data
fill missing bars
```

They are Fragarach implementation decisions, not consumer choices.

---

# 5A. Market History Request

The conceptual request is:

```text
Market History

Symbol

Timeframe

Time Window
```

The implementation may expose this through a versioned API.

The request deliberately avoids:

- provider;
- evidence;
- provenance;
- derivation;
- source timeframe;
- alignment;
- implementation details.

The request asks only for Market History.

---

# 6. Window Semantics

Fragarach converts a time window into the exact required source range and returned target intervals using the approved calendar, session, owner-day, alignment, and completion authorities.

## 6.1 Trading-day windows

`LAST_TRADING_DAYS(n)` means the latest `n` expected trading-day owners in the applicable approved market calendar, ending at the request's effective `CAODT`.

It does not mean:

- `n` calendar days;
- `n` observed days containing at least one bar;
- a consumer-calculated number of bars;
- an instruction to widen the window until a desired bar count is reached.

If expected history inside the requested trading-day window is missing, Fragarach returns the usable history in that same window with the factual status and warnings. It does not silently extend the window to compensate.

## 6.2 Between windows

`BETWEEN(start, end)` is interpreted by Fragarach under the requested timeframe's approved timestamp, boundary, timezone, session, and owner-day authority.

The public contract must state whether each boundary is inclusive or exclusive. That rule shall be stable within a contract version and shall not depend on the consumer.

## 6.3 Bounded conversion

Fragarach may retrieve the minimal additional canonical source context required to establish an authorised target boundary. It must not perform unbounded reads or return history outside the requested target window.

Consumers never calculate source range, overlap, expected intervals, or bar counts.

---

# 7. Response Contract

## 7.1 Analysis response

The analysis response contains:

```text
OHLC
CAODT
Status
Warnings
```

This is the complete required analysis surface.

Each OHLC bar contains the canonical target timestamp plus:

```text
Open
High
Low
Close
```

Bars are returned in strictly increasing canonical timestamp order.

## 7.2 Optional factual metadata

Versioned responses may add consumer-relevant factual metadata such as:

- historical warnings;
- unavailable reason codes;
- freshness state;
- the canonical symbol, requested timeframe, and resolved window when required for request correlation.

Optional metadata must not expose implementation mechanics. In particular, the analysis response does not identify provider, source lane, evidence block, provenance chain, derivation path, storage location, validation algorithm, request chunking, or rollup implementation.

Fragarach retains that information internally wherever required by governing authority and operational auditability.

## 7.3 Status

The response status is factual and non-fabricating. At minimum, the versioned contract shall distinguish:

```text
AVAILABLE
AVAILABLE_WITH_WARNINGS
NOT_REGISTERED
TIMEFRAME_NOT_AUTHORISED
TIMEFRAME_NOT_ACTIVE
NO_HISTORY
RETIRED
REMOVED
```

An unavailable response contains no fabricated bars and includes a stable reason code. A warning does not blank usable historical authority.

---

# 7A. Market History Response

The Market History Service returns only the information required for analysis:

```text
Market History

OHLC

CAODT

Status

Warnings
```

This constitutes the complete analytical contract.

Consumers require no additional operational knowledge to perform deterministic analysis.

Operational evidence, provenance, provider identity, validation reasoning, and derivation mechanics remain internal Fragarach responsibilities.

---

# 8. One External Market History Abstraction

Consumers never distinguish direct history from derived history.

Internally, an authorised implementation may resolve:

```text
D1   → direct canonical authority
H1   → direct canonical authority
M30  → direct canonical authority
M5   → direct canonical authority
H4   → bounded construction from H1
M15  → bounded construction from M5
```

Externally, every successful result is:

```text
Market History
```

The public response shape, window semantics, status doctrine, and consumer obligations remain the same regardless of fulfilment path.

SignalBar and every other consumer shall behave identically whether Fragarach fulfilled a request directly, through authorised deterministic construction, through a future provider, or through another future authority-compliant internal path.

---

# 8A. Market History Invariant

The following invariant is permanent ecosystem doctrine:

> **The same Market History request shall always produce the same historical answer for every consumer operating against the same Fragarach authority and CAODT.**

Therefore:

```text
SignalBar

AUDUSD

H1

Last 21 Trading Days
```

must receive identical Market History to:

```text
Sea Eagle

AUDUSD

H1

Last 21 Trading Days
```

and:

```text
HARP

AUDUSD

H1

Last 21 Trading Days
```

Historical truth is unique.

Analysis is application-specific.

Consumers may legitimately reach different conclusions from the same Market History. They must never receive different historical truth.

---

# 9. Derived History Views

## 9.1 Nature of a derived view

A derived history view is:

- deterministic;
- read-only;
- bounded by the request;
- calculated only from eligible canonical source history;
- governed by approved target-timeframe construction authority;
- reproducible from the same source evidence and authority versions;
- never persisted as canonical market evidence;
- never activated as a canonical authority lane merely because it was requested;
- never included as independent Symbol × Timeframe Truth;
- never included as an independent Estate Truth lane.

It exists only to satisfy an analysis request.

## 9.2 Authority inheritance without promotion

Canonical historical Truth remains owned by the source authority lanes. A derived response inherits authority from its eligible source history and governing construction authority, but it does not promote its target bars into canonical evidence or a new Truth lane.

For a consumer, the returned history is Fragarach's authoritative historical answer as of the returned `CAODT`:

```text
Fragarach returned it.
Therefore it is Truth for analysis,
as of CAODT.
```

This consumer guarantee does not alter the internal constitutional distinction between canonical evidence and a bounded derived view.

## 9.3 Deterministic OHLC construction

Where approved authority permits construction, each complete target interval is calculated from its exact ordered eligible contributors:

```text
Open  = first contributor Open
High  = maximum contributor High
Low   = minimum contributor Low
Close = last contributor Close
```

Every contributing interval must be canonical, closed, contiguous, correctly aligned, session-compatible, unit-compatible, price-basis-compatible, and inside one permitted effective construction segment.

A target interval is unavailable if its required contributors are missing, overlapping, conflicting, incomplete, ineligible, or cross a forbidden authority boundary. Fragarach returns the remaining usable history with factual status and warnings where permitted. It never fills, interpolates, copies, guesses, or silently realigns a bar.

## 9.4 Initial construction cases

The initial candidates are:

```text
H4  ← H1
M15 ← M5
```

They may be activated only per market and representation after approved authority fixes:

- target duration and alignment;
- session and trading-day ownership;
- timestamp meaning;
- contributor eligibility and required count;
- short or exceptional session behaviour;
- completion and latest-closed rules;
- effective-range compatibility;
- gap and warning semantics;
- `CAODT` calculation.

Authority for one market or representation does not activate another by symbol resemblance.

---

# 10. CAODT

Every response contains one Fragarach-calculated `CAODT`.

Consumers never infer `CAODT` from the final returned timestamp, wall-clock time, requested end, provider freshness, or expected bar count.

For direct history, `CAODT` is determined by the canonical requested lane under its approved Truth and completion authority.

For a derived view, `CAODT` is the latest completed target-history point supported by eligible canonical contributors, capped by the applicable source authority and target completion rules. It must never claim knowledge later than its source authority supports.

A request window may end before the service's latest available history. The response must distinguish the history represented in the response from the service's broader freshness state through stable versioned semantics.

---

# 11. Internal Auditability and External Encapsulation

Consumer ignorance of implementation is deliberate encapsulation, not loss of operational evidence.

Internally, Fragarach must remain able to reproduce and explain:

- the authority versions applied;
- the canonical source observations used;
- the requested and resolved window;
- the interval boundaries constructed;
- every omitted interval and reason;
- the `CAODT`, status, and warning decision;
- the deterministic result checksum where implementation requires one.

This information belongs to Fragarach operations, acceptance evidence, and diagnostics. It is not required by an analysis consumer and must not become a consumer decision input.

The implementation should prefer deterministic recomputation and request-scoped observability over persistence of derived target bars. Any audit record must not masquerade as canonical evidence, Truth, or Estate Truth.

---

# 12. Consumer-Agnostic Service

Fragarach shall not know or branch on whether a request originated from:

- SignalBar;
- Sea Eagle;
- Market Scout;
- HARP;
- Morphix;
- a future application.

The following are forbidden:

- consumer-specific providers;
- consumer-specific source timeframes;
- consumer-specific alignment;
- consumer-specific history repair;
- consumer-specific window conversion;
- consumer-specific OHLC values;
- consumer-specific warning suppression;
- consumer-specific historical Truth.

Transport authentication, authorisation, rate control, and observability may identify a caller operationally. They must not change historical meaning.

---

# 13. Compatibility and Versioning

## 13.1 Existing contracts

The accepted SPEC-018 D1 response and the accepted SPEC-025 direct-timeframe service remain backward compatible for existing consumers.

The time-window request is introduced through a versioned additive successor contract. Existing `get_history(symbol, timeframe)` callers remain supported during a documented migration period and must not silently receive a different historical range.

## 13.2 Contract evolution

A contract version must define:

- request window grammar;
- boundary inclusion;
- canonical timestamp encoding;
- OHLC numeric encoding;
- `CAODT` meaning;
- status and warning codes;
- unavailable-response shape;
- ordering and determinism;
- legacy migration behaviour.

No contract version may require a consumer to understand provider, evidence, provenance, validation, gaps, derivation, rollups, session alignment, or source bar counts.

## 13.3 Earlier metadata

Earlier operational contracts may continue to expose richer authority metadata to operational clients. Analysis consumers shall use the Market History Service response and shall not make analytical availability or reconstruction decisions from operational metadata.

---

# 14. Implementation Preflight

Before implementation, a compatibility preflight must identify:

1. the exact SPEC-018 successor contract and transport changes;
2. all legacy consumers and their migration behaviour;
3. existing calendar and session APIs capable of resolving trading-day windows;
4. the authoritative source-lane selection boundary;
5. the absence or presence of approved `H4` and `M15` construction authority per market and representation;
6. exact target timestamp, alignment, completion, gap, and `CAODT` rules;
7. bounded-read and memory limits;
8. internal observability without canonical derived persistence;
9. Truth and Estate Truth non-promotion protections;
10. signed native operational visibility and diagnostics;
11. affected Python, Swift, storage, command, test, and consumer integration boundaries;
12. a D1/H1/M30/M5 non-regression fingerprint.

No broad rewrite is authorised. Missing target construction authority stops only the affected derived timeframe, market, representation, and effective segment.

---

# 15. Delivery Order

Implementation shall proceed through these gates:

```text
1. Versioned time-window request and response contract
2. Calendar-owned trading-day window resolution
3. Direct-history bounded serving and non-regression
4. Internal derived-view engine behind an inactive capability gate
5. H4 authority and one-market vertical slice (separate approval)
6. M15 authority and one-market vertical slice (separate approval)
7. Cross-market activation only where separately authorised
8. Consumer migration beginning with SignalBar
9. Sea Eagle, Market Scout, HARP, and future consumers
```

Each gate requires focused acceptance before the next gate begins. Direct history remains operational while derived capabilities are absent or under commissioning.

---

# 16. Acceptance

SPEC-026 is accepted only when deterministic evidence proves:

- a consumer can request direct D1, H1, M30, and M5 history using trading-day and between windows without calculating bar counts;
- the same Market History request against the same Fragarach authority and `CAODT` returns the same OHLC, `CAODT`, status, warnings, and deterministic historical meaning for every consumer;
- consumer identity does not alter the Market History response or its deterministic result checksum;
- `LAST_TRADING_DAYS(n)` is resolved from approved expected trading days, not calendar days or observed-bar counts;
- a gap does not cause silent window widening;
- direct responses remain backward compatible with accepted SPEC-018 and SPEC-025 history;
- until separately authorised, `H4` and `M15` return `TIMEFRAME_NOT_ACTIVE` with no fabricated OHLC and a stable construction-authority warning;
- after separate commissioning, an authorised `H4` request is deterministically satisfied from eligible `H1` history without changing the external contract;
- after separate commissioning, an authorised `M15` request is deterministically satisfied from eligible `M5` history without changing the external contract;
- direct and derived responses share the same analysis-facing abstraction;
- provider, provenance, source timeframe, validation mechanics, and derivation mechanics are absent from the analysis response;
- derived target bars are not persisted as canonical evidence;
- derived target timeframes do not become independent Truth or Estate Truth lanes;
- incomplete, misaligned, gapped, conflicting, or cross-boundary contributors never produce a fabricated target bar;
- status, warnings, unavailable reasons, freshness, and `CAODT` remain factual;
- SignalBar performs analysis from returned OHLC without any history reconstruction path;
- Fragarach contains no Signal Bar, Pin Bar, Active Range, Potential Scan, ADR, C24, ranking, forecast, research, visualisation, or other consumer-analysis implementation introduced by this specification;
- unrelated symbols, markets, timeframes, and consumers remain operational when one request cannot be fulfilled.

The commissioning report must record contract versions, authority versions, representative markets and session profiles, request windows, returned ranges, result checksums, statuses, warnings, `CAODT`, non-persistence proof, Truth/Estate non-promotion proof, and consumer-boundary tests.

---

# 17. Forbidden

Do not:

- make a consumer determine historical truth;
- allow a consumer to choose provider, evidence, provenance, source timeframe, validation, gap policy, derivation, rollup, session, alignment, or source bar count;
- require a consumer to convert trading days into bars;
- expose implementation mechanics as required analysis metadata;
- return different historical meaning to different consumers;
- persist bounded derived views as canonical evidence;
- create canonical target lanes merely because derived history was requested;
- include derived views as independent Truth or Estate Truth;
- implement `H4`, `M15`, or another target timeframe without approved construction authority;
- assume a fixed UTC grid where market authority defines session-relative alignment;
- cross owner-day, session, price-basis, unit, provider, or effective-segment boundaries without authority;
- fill, interpolate, forward-fill, copy, or silently realign missing history;
- widen a requested time window to reach a desired bar count;
- let Fragarach perform consumer analysis;
- let SignalBar or another consumer acquire or reconstruct history;
- break accepted direct-history consumers while introducing window semantics;
- block unrelated history because one derived view is unavailable.

---

# 18. Completion State

SPEC-026 is complete when every ecosystem consumer can ask Fragarach for a symbol, timeframe, and time window; receive authoritative OHLC, `CAODT`, status, and warnings; and perform analysis without knowing or controlling how historical truth was established.

The defining contract is:

> **Consumers never determine historical truth. They consume it.**

Fragarach answers:

> **What happened?**

Consumers answer:

> **What does it mean?**

Revision 1's consumer-authority boundary and direct-history service are accepted. The separately governed construction capabilities remain:

```text
H4 — TIMEFRAME_NOT_ACTIVE
M15 — TIMEFRAME_NOT_ACTIVE
```

---

# 18A. Ecosystem Doctrine

The permanent ecosystem contract is:

> **Consumers consume Market History. They own only the analysis they derive from it.**

Fragarach answers:

> **What happened?**

Consumers answer:

> **What does it mean?**

There is exactly one Market History.

There may be many analyses.
