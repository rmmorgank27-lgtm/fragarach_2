# Fragarach II Constitution

**Authority ID:** `FRAGARACH_II_CONSTITUTION_V1`  
**Version:** `1`  
**Status:** `DRAFT FOR APPROVAL`  
**Classification:** `Constitutional Root Authority`  
**Repository Location:** `constitution/CONSTITUTION.md`  
**Doctrine:** `Operations is King`  
**Approval Date:** `PENDING`  
**Effective Date:** `PENDING`  
**Constitutional Authority Owner:** `Ray Morgan`

---

# Article 1 — Purpose

This Constitution is the supreme authority of Fragarach II.

It defines the hierarchy by which operational truth is declared, inherited, implemented, verified, amended, and retired.

It does not define a market, timeframe, provider, schema, database, application screen, workflow, or implementation algorithm.

Those matters belong to subordinate authorities and specifications.

---

# Article 2 — Governing Hierarchy

The governing hierarchy is:

```text
Constitution
↓
Base Doctrine
↓
Timeframe and Other Authority Documents
↓
Specifications
↓
Implementation
↓
Acceptance Proof
```

Each layer MUST conform to every applicable higher layer.

A lower layer MUST NOT redefine, weaken, bypass, or silently reinterpret a higher layer.

---

# Article 3 — Supremacy

When two layers disagree, the higher layer is authoritative.

The order of supremacy is:

1. Constitution;
2. approved Base Doctrine;
3. approved Timeframe or other constitutional Authority;
4. approved Specification;
5. Implementation;
6. operational output or acceptance evidence.

When Implementation and constitutional authority disagree, Implementation MUST change.

Constitutional authority MUST NOT be rewritten merely to preserve existing implementation.

---

# Article 4 — Authority Classes

Fragarach II recognises the following constitutional classes.

## 4.1 Constitutional Root

The Constitutional Root defines hierarchy, supremacy, ratification, amendment, compatibility, and non-invention rules.

## 4.2 Base Doctrine

A Base Doctrine defines market-family truth.

It may define market identity, market structure, trading-day ownership, calendar doctrine, session doctrine, holiday doctrine, unit doctrine, and market-level evidence boundaries.

## 4.3 Timeframe Authority

A Timeframe Authority defines interval-specific truth for one market family and one timeframe.

It may define alignment, timestamp meaning, completion, construction, expected intervals, validation requirements, effective-range rules, and evidence-lane compatibility.

## 4.4 Other Constitutional Authorities

Provider, calendar, instrument, validation, transformation, corporate-action, contract-roll, or other constitutional authorities MAY be created when a fact does not properly belong to a Base Doctrine or Timeframe Authority.

## 4.5 Templates

Templates define mandatory document structure.

A template is not itself market truth and does not become `APPROVED`.

Its controlled status remains `TEMPLATE`, while its ratification disposition may be recorded as `ACCEPTED TEMPLATE`.

## 4.6 Specifications

Specifications are not constitutional authority.

They define how Fragarach II implements approved authority.

A Specification MUST cite every constitutional authority it consumes.

---

# Article 5 — Authority Ownership

Every constitutional fact MUST have exactly one owning authority.

A subordinate document MAY reference inherited authority, but MUST NOT restate it in a way that creates a competing source of truth.

Where ownership is unclear, ratification or implementation SHALL stop for the affected path until ownership is resolved.

---

# Article 6 — Non-Invention Rule

Implementation MUST NOT invent authority.

Implementation MUST NOT invent or silently infer:

- market identity;
- instrument identity;
- venue identity;
- session boundaries;
- calendars;
- holidays;
- trading-day ownership;
- timeframe alignment;
- timestamp meaning;
- provider semantics;
- adjustment basis;
- price or quantity units;
- index variant;
- contract-roll methodology;
- evidence precedence;
- validation rules;
- effective ranges.

When required authority is absent, incomplete, contradictory, or incompatible, the affected path SHALL stop with a compatibility report.

This stopping behaviour is correct constitutional behaviour.

---

# Article 7 — Compatibility Boundary

Compatibility is evaluated per affected authority path, instrument, evidence lane, provider mapping, venue, timeframe, or effective segment.

A compatibility failure MUST NOT automatically block unrelated approved operations.

The compatibility report MUST identify:

- the missing or competing authority;
- the exact affected path;
- the operational consequence;
- the evidence examined;
- the owner decision required.

---

# Article 8 — Operations Is King

Fragarach II exists to provide trustworthy, usable operational truth.

Accordingly:

1. accepted evidence remains readable during repair;
2. Current-As-Of Truth remains visible;
3. stale, provisional, conflicting, or incomplete conditions remain visible;
4. warning states do not blank usable evidence;
5. `AMBER` remains usable;
6. only the affected incompatible path stops;
7. unrelated operations continue;
8. maintenance state does not become operator truth;
9. silent failure is forbidden;
10. silent overwrite is forbidden.

Blocking unrelated operations is constitutionally incorrect.

---

# Article 9 — Evidence Doctrine

Evidence is immutable once accepted into the evidence record.

Correction, replacement, conflict, supersession, or reclassification creates a new evidence event.

No authority permits silent destruction of prior evidence.

Direct evidence and derived evidence MUST remain distinguishable.

Derived evidence MUST retain complete provenance to its contributing evidence and governing authority.

---

# Article 10 — Evidence-Lane Order

The constitutional evidence order is:

```text
Instrument Registration
↓
Evidence Lane Authority
↓
Evidence
```

A timeframe is a property of an Evidence Lane.

Instrument Registration MUST NOT directly imply one specific timeframe.

An Evidence Lane MUST bind every material identity and authority required for its evidence to be interpreted deterministically.

---

# Article 11 — Determinism

Approved authority MUST be sufficiently complete that two conforming implementations reach the same material decision from the same evidence.

Nothing material may depend on:

- undocumented defaults;
- arrival order;
- filename guesswork;
- provider popularity;
- implementation convenience;
- hidden application state;
- operator memory;
- silent timezone assumptions.

Where deterministic interpretation is impossible, the authority is incomplete.

---

# Article 12 — Effective Dating

No constitutional authority is timeless.

Every approved authority MUST declare:

- version;
- approval date;
- effective date or effective range;
- amendment doctrine;
- supersession relationship when applicable.

Historical authority remains immutable and available for interpretation of historical evidence.

---

# Article 13 — Ratification

A constitutional document becomes effective only after ratification.

Ratification MUST prove:

- correct identity and repository path;
- resolvable parent and governing references;
- absence of material contradiction;
- deterministic scope;
- complete amendment and effective-date rules;
- consistency with higher authority;
- compatibility with sibling authorities where boundaries meet;
- immutable acceptance evidence.

Ratification MUST NOT be inferred from file presence.

Templates retain status `TEMPLATE`; they are accepted as controlled templates rather than converted to `APPROVED`.

---

# Article 14 — Amendment and Versioning

A material change requires:

- a new controlled version; or
- an expressly authorised effective-dated amendment where the governing document permits it.

Previous approved versions remain immutable.

Formatting-only corrections MAY be made without a semantic version change only when:

- meaning is unchanged;
- the correction is documented;
- before-and-after checksums are recorded;
- the correction is approved through the applicable review process.

---

# Article 15 — Structural Style

Constitutional meaning is not determined by Markdown heading depth.

The current Fragarach II constitutional house style MAY use multiple level-one headings for numbered Articles or Sections.

Heading normalization is optional mechanical cleanup and MUST NOT be treated as a material constitutional blocker unless it causes genuine ambiguity or broken machine processing.

Intentional placeholders inside controlled template files are valid template content.

Unresolved placeholders are forbidden in doctrines, authorities, specifications, manifests, and acceptance reports.

---

# Article 16 — Specification Boundary

A Specification MAY define:

- implementation sequence;
- schema usage within an approved boundary;
- API-client behaviour;
- acquisition mechanics;
- storage mechanics;
- projection mechanics;
- native workflow;
- validation implementation;
- acceptance tests.

A Specification MUST NOT redefine:

- market truth;
- timeframe truth;
- calendar truth;
- provider truth;
- instrument truth;
- evidence identity;
- constitutional precedence;
- compatibility rules.

---

# Article 17 — Implementation Boundary

Implementation MUST conform to the approved Constitution, applicable doctrines, authorities, and specifications.

Implementation MUST NOT:

- silently widen scope;
- silently merge authorities;
- create undeclared fallbacks;
- reinterpret timestamps;
- fabricate bars or prices;
- infer missing identity;
- convert units without authority;
- change evidence in place;
- make maintenance state authoritative;
- block unrelated operations.

---

# Article 18 — Acceptance Proof

Acceptance proves conformance.

Acceptance proof MUST identify:

- governing authorities;
- specification under test;
- implementation checkpoint;
- evidence and fixtures used;
- checksums where applicable;
- tests and operational checks;
- known limitations;
- exact accepted scope.

A passing test suite does not override a constitutional contradiction.

---

# Article 19 — Secrets and Security

Constitutional documents, specifications, reports, logs, and evidence MUST NOT expose secrets.

Authentication material is implementation configuration and does not belong in constitutional authority.

---

# Article 20 — Repository Authority

The canonical constitutional root is:

```text
constitution/CONSTITUTION.md
```

Canonical constitutional directories are:

```text
constitution/templates/
constitution/doctrines/
constitution/authorities/
```

A document located outside its declared canonical path is not ratifiable until the path conflict is resolved.

Duplicate or competing authority identities are forbidden.

---

# Article 21 — Completion Statement

This document establishes the constitutional root of Fragarach II.

It governs every doctrine, authority, specification, implementation, and acceptance proof.

> Constitution defines what is true.  
> Specification defines how Fragarach II implements that truth.  
> Implementation must conform to both.  
> Implementation must never invent authority.

Fragarach II remains **CANDIDATE AUTHORITY** until this Constitution and its subordinate authority set are ratified.

**Operations is King.**
