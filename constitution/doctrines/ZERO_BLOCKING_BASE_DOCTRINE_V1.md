# ZERO BLOCKING BASE DOCTRINE V1

**Document Class:** Cross-Cutting Constitutional Base Doctrine  
**Authority Layer:** Constitutional Operations  
**Authority Name:** `ZERO_BLOCKING_BASE_DOCTRINE_V1`  
**Version:** 1.0  
**Status:** `APPROVED`  
**Repository Location:** `constitution/doctrines/ZERO_BLOCKING_BASE_DOCTRINE_V1.md`  
**Governing Constitution:** `constitution/CONSTITUTION.md`  
**Effective From:** `2026-07-12`  
**Effective Until:** `OPEN`  
**Supersedes:** `NONE`  
**Approved By:** `Ray Morgan`  
**Approval Date:** `2026-07-12`  
**Governing Principle:** `Operations is King`

---

# 1. Purpose

This doctrine establishes the mandatory zero-blocking operating behaviour of Fragarach II.

Fragarach exists to provide the best available truthful historical market authority while exposing uncertainty, incompleteness, incompatibility, and risk.

The system MUST continue every operation that can be performed truthfully and safely.

A missing optional fact, incomplete capability, absent convenience feature, partial provider contract, limited history window, warning state, or implementation gap MUST NOT become a general stop.

The governing rule is:

> **Register what is known. Preserve what is received. Serve what is safe. Expose what is unknown. Continue every unaffected operation.**

---

# 2. Constitutional Position

```text
Constitution
↓
ZERO_BLOCKING_BASE_DOCTRINE_V1
↓
Market-Family Base Doctrine
↓
Timeframe and Other Authority
↓
Specification
↓
Implementation
↓
Acceptance Proof
```

This doctrine is cross-cutting.

Every market family, timeframe, provider contract, registration workflow, acquisition workflow, validation service, Truth service, maintenance service, native workflow, and acceptance proof inherits it.

This doctrine implements and tightens the Constitution's path-scoped compatibility boundary and `Operations is King` requirements.

It does not permit fabrication, silent overwrite, evidence corruption, or false claims.

---

# 3. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

No subordinate authority, specification, schema, service, user interface, or implementation convenience may weaken this doctrine.

---

# 4. Definition of Blocking

A block occurs when Fragarach prevents an operator or authorised service from continuing an otherwise safe operation.

Blocking includes:

- disabling all actions because one optional capability is unavailable;
- returning a blocker report instead of performing a safe reduced operation;
- preventing registration because acquisition is not ready;
- preventing one valid timeframe because another timeframe is unavailable;
- preventing bounded acquisition because maximum-history proof is unavailable;
- preventing import because provider acquisition is unavailable;
- blanking usable Truth because one quality warning exists;
- stopping unrelated instruments, lanes, providers, or operations;
- treating missing implementation code as missing constitutional authority;
- treating a lower-layer schema restriction as authority when higher authority already permits the operation.

A warning, limitation, partial result, unavailable lane, or explicit unknown is not automatically a block.

---

# 5. Zero-Blocking Rule

For every requested operation, Fragarach MUST follow this order:

```text
1. Execute the full requested operation when safe and authorised.
2. Otherwise execute every safe authorised subset.
3. Otherwise offer and execute the nearest truthful reduced operation.
4. Preserve accepted evidence and completed work.
5. Expose limitations, warnings, unknowns, and deferred work.
6. Stop only the exact unsafe action when no truthful reduced operation exists.
7. Continue every unaffected instrument, lane, provider, timeframe, and workflow.
```

The system MUST prefer useful partial operation over administrative perfection.

A partial success is an operational success with warnings.

---

# 6. Hard Safety Blocks

A hard block is permitted only where continuing would create a material risk of false authority, corrupted evidence, destructive mutation, or invalid identity.

Permitted hard-block conditions are limited to:

1. unresolved or contradictory instrument identity;
2. exact provider identity or orientation mismatch;
3. retired or quarantined authority attempting new acquisition or serving;
4. checksum failure or raw-evidence corruption;
5. transaction, locking, or writer-safety failure that risks inconsistent mutation;
6. schema incompatibility that would corrupt or overwrite immutable evidence;
7. invalid timestamp, unit, venue, session, or adjustment interpretation where no safe raw-only preservation path exists;
8. explicit operator cancellation;
9. authentication or provider rejection that makes the requested provider call impossible;
10. absence of any safe truthful reduced operation.

A hard block MUST be scoped to the smallest affected unit:

```text
operation
instrument
provider mapping
timeframe lane
date segment
evidence block
```

A hard block on one unit MUST NOT stop unrelated units.

---

# 7. Conditions That Must Not Cause General Blocking

The following are non-blocking unless they produce one of the hard safety conditions in Section 6:

- provider entitlement unknown;
- provider capability unknown;
- provider mapping not yet established;
- incomplete metadata;
- unknown optional venue or exchange display detail;
- no evidence yet acquired;
- stale evidence;
- gaps;
- validation warnings;
- incomplete maximum-history knowledge;
- no pagination contract;
- no earliest-history proof;
- no automatic update-overlap rule;
- no resume cursor;
- only a bounded request being available;
- one unsupported timeframe;
- one failed timeframe;
- one failed provider;
- one failed chunk after prior chunks succeeded;
- a missing UI component;
- a missing DTO, service, cache, adapter, or coordinator;
- a lower-layer implementation that has not yet caught up with approved authority;
- a schema check narrower than ratified authority;
- absence of a convenience default;
- inability to claim `Maximum Available`;
- inability to calculate an automatic range;
- AMBER quality;
- partial Truth;
- maintenance work pending.

These conditions MUST produce explicit status and a safe fallback, not a terminal project stop.

---

# 8. Status Semantics

## 8.1 GREEN

```text
Usable normally.
No material warning affecting the requested operation.
```

## 8.2 AMBER

```text
Usable with visible limitation, uncertainty, staleness, incompleteness, or repair pending.
Operation continues.
```

AMBER MUST NOT disable the operation.

## 8.3 RED

```text
Unsafe for the exact affected operation or lane.
Only that affected path stops.
Unrelated operations continue.
```

RED MUST identify the hard safety reason and the smallest affected scope.

## 8.4 UNKNOWN

```text
The fact has not been established.
```

UNKNOWN MUST NOT be silently converted to supported or unsupported.

UNKNOWN is non-blocking unless the unknown fact is mandatory to avoid false authority or evidence corruption.

---

# 9. Registration Doctrine

A valid instrument identity MAY be registered before provider acquisition is available.

Registration MUST distinguish:

```text
REGISTERED_READY
REGISTERED_UNMAPPED
REGISTERED_CAPABILITY_UNKNOWN
REGISTERED_NO_EVIDENCE
REGISTERED_WITH_EVIDENCE
RETIRED
```

or equivalent controlled states.

The absence of a provider mapping MUST NOT prevent Fragarach from owning a valid canonical identity.

A provider-backed acquisition plan still requires exact provider evidence.

Instrument registration and timeframe-lane declaration are separate operational facts.

One unavailable timeframe MUST NOT prevent registration of the instrument or other valid lanes.

---

# 10. Timeframe Doctrine

Ratified timeframe authority controls which timeframes Fragarach recognises.

A lower-layer schema or validator that permits fewer timeframes than ratified authority is an implementation incompatibility, not missing authority.

The implementation MUST be repaired to conform to higher authority.

Until repair completes:

- supported existing lanes continue;
- the instrument remains registerable;
- available timeframes continue;
- unavailable timeframes remain visible with explicit state;
- unrelated acquisition and import continue;
- the system MUST NOT claim that the higher authority does not exist.

---

# 11. Acquisition Doctrine

## 11.1 Best Available Before Maximum Available

When truthful maximum-history proof exists, Fragarach MAY offer:

```text
Maximum Available
```

When maximum-history proof does not exist, Fragarach MUST offer a truthful reduced operation such as:

```text
Best Available Now
Bounded Provider Fetch
Custom Range
Import File
```

It MUST report the actual acquired range and terminal reason.

It MUST NOT disable all acquisition merely because the word `maximum` cannot be proven.

## 11.2 Update Operations

When automatic overlap and completed-bar authority exist, Fragarach MAY offer:

```text
Update to Current
```

When automatic range authority is incomplete, Fragarach MUST offer a truthful fallback:

```text
Bounded Recent Fetch
Custom Range
Import File
```

It MUST NOT claim correction reconciliation that was not performed.

## 11.3 Per-Lane Operation

Every timeframe lane is planned and executed independently.

One blocked or failed lane MUST NOT roll back, hide, or invalidate successful lanes.

Every lane receives a deterministic result.

## 11.4 Evidence Preservation

Every accepted provider response or imported file remains immutable raw evidence.

A reduced acquisition is still valid evidence when its exact range and limitations are recorded.

---

# 12. Validation, Gaps, and Truth

Validation informs operational confidence.

It does not become an administrative stop unless a hard safety condition exists.

Required behaviour:

```text
Detect
Classify
Expose
Serve best available
Schedule repair where authorised
Continue
```

Public holidays, closed sessions, old isolated gaps, stale-but-usable evidence, and incomplete coverage MUST be classified according to their materiality.

Warnings MUST NOT blank usable evidence.

Truth MUST expose:

- CAODT;
- traffic-light state;
- confidence or Truth Score;
- coverage;
- gaps;
- compatibility warnings;
- provider state;
- known unknowns.

---

# 13. Blocker Classification

`BLOCKED_BY_AUTHORITY` is reserved for a genuine absence, contradiction, or incompatibility in higher authority where no safe truthful reduced operation exists.

The following MUST NOT be called an authority blocker:

- missing implementation code;
- absent UI;
- absent DTO;
- absent helper service;
- stale cache;
- D1-only code beneath approved H1/M30/M5 authority;
- a schema constraint narrower than ratified authority;
- missing pagination where bounded acquisition remains safe;
- missing maximum-history proof where a bounded range remains safe;
- missing automatic overlap where custom-range acquisition remains safe.

Those are implementation limitations or degraded capabilities.

Every blocker result MUST include:

```text
hard_block
affected_scope
exact_reason
evidence
safe_fallbacks
fallback_executed
unaffected_operations
repair_owner
```

A blocker report is not acceptance proof.

---

# 14. User Interface Doctrine

The native application MUST always show the next safe action.

Forbidden terminal presentation:

```text
Blocked
No action
See report
```

Required presentation:

```text
Unavailable capability
Reason
What remains safe
Primary safe action
Alternative safe action
Audit details
```

Examples:

```text
Maximum history cannot yet be proven.
[Fetch Best Available Now]
[Choose Custom Range]
[Import File]
```

```text
M5 provider mapping is unknown.
D1 and H1 remain available.
[Run 2 Available Lanes]
```

```text
Provider acquisition unavailable.
[Import File]
```

The UI MUST not require the operator to understand internal architecture before continuing.

---

# 15. Partial Success Doctrine

Multi-step and multi-lane operations MUST preserve completed valid work.

Example:

```text
D1   SUCCESS
H1   SUCCESS
M30  PROVIDER_LIMIT_REACHED
M5   MAPPING_REQUIRED
```

The overall result is:

```text
COMPLETED_WITH_WARNINGS
```

not:

```text
FAILED
```

unless no requested unit completed and the remaining action is a hard safety block.

---

# 16. Implementation Reconciliation

Implementation MUST conform upward to ratified authority.

When an implementation constraint conflicts with higher authority:

1. record the implementation incompatibility;
2. continue every safe existing operation;
3. provide a reduced operator path;
4. repair the implementation;
5. prove end-to-end operation;
6. do not demand new doctrine for authority that already exists.

Specifications are authorised to repair implementation constraints, including schema constraints, when required to implement already-ratified authority and when immutable evidence is preserved through a reviewed migration.

---

# 17. Acceptance Standard

A workflow is not accepted merely because:

- tests pass;
- a report exists;
- a backend command works;
- a blocker is documented;
- a screenshot shows a disabled control.

Acceptance requires the operator to complete the intended safe journey in the running application.

For new-symbol onboarding, minimum proof is:

```text
Discover valid symbol
→ register canonical identity
→ expose supported and unavailable lanes
→ acquire or import best available evidence
→ show per-lane result
→ refresh Truth
→ provide retirement path
```

Unavailable optional capabilities remain visible but MUST NOT prevent this journey.

---

# 18. Mandatory Regression Cases

The repository MUST test at least:

1. one unsupported lane does not block supported lanes;
2. one failed provider does not block import;
3. missing maximum-history proof still permits bounded acquisition;
4. missing automatic overlap still permits custom-range acquisition;
5. provider mapping unknown still permits canonical registration;
6. retired authority blocks only that instrument or lane;
7. an identity mismatch hard-blocks only the affected path;
8. AMBER Truth remains readable and operable;
9. partial success is preserved and reported;
10. newly registered symbols immediately appear in operations;
11. blocker output always includes safe fallbacks;
12. no lower-layer D1-only restriction is misreported as absent H1/M30/M5 authority.

---

# 19. Amendment and Versioning

A new version is required when changing:

- the hard safety block set;
- status semantics;
- registration-before-provider rules;
- safe fallback order;
- path-scoping rules;
- partial-success rules;
- blocker classification;
- acceptance requirements.

Historical versions remain auditable.

---

# 20. Governing Statements

> **Operations is King.**

> **Warnings route work; they do not stop work.**

> **AMBER is usable. RED stops only the unsafe affected path.**

> **Unknown is explicit, not automatically fatal.**

> **A missing convenience is not missing authority.**

> **A narrower implementation is not higher authority.**

> **Register what is known. Preserve what is received. Serve what is safe. Expose what is unknown. Continue.**
