# SPEC-009A — Operational Authority Service Contract (Commissioning)

**Document ID:** `SPEC-009A_OPERATIONAL_AUTHORITY_SERVICE_CONTRACT`

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`

**Status:** Draft

**Authority:** Candidate Authority

**Doctrine:** Operations is King

**Push:** Forbidden

---

# 1. Purpose

SPEC-009 established Fragarach II as the laboratory's Operational Historical Authority.

This specification commissions that authority by defining the single operational service contract presented to every consumer.

This specification intentionally delivers the minimum operational capability required for production use.

It does **not** attempt to complete the Truth Console, Maintenance Console, or advanced operational analytics.

---

# 2. Mission

After implementation every consumer shall retrieve historical market data through one identical operational authority contract.

Consumers shall never need to know:

* provider
* storage format
* acquisition method
* repair history
* database layout

Consumers request historical authority.

Fragarach supplies historical authority.

---

# 3. Scope

This specification implements:

* Standard Authority Service
* Version 1 Truth Score
* Version 1 Gap Summary
* CAODT everywhere
* Consumer-independent responses
* Operational availability

It deliberately excludes:

* Truth Console
* Heat Maps
* Charts
* Estate Maintenance
* Snapshot Management
* Archive Management
* Automatic Gap Repair
* Consumer-specific optimisation

Those belong to future operational phases.

---

# 4. Operational Principles

Implementation shall follow:

## Operations is King

The authority shall maximise truthful operational service.

It shall never maximise reasons to refuse service.

---

## Consumer Agnostic

The authority shall never know:

* Morphix
* Signal Bar
* HARP
* Ferret.plus

Every consumer receives exactly the same response.

---

## Best Available Truth

Perfect data is not required.

Best available truthful authority is required.

Known uncertainty shall be measured.

Known uncertainty shall never be hidden.

Historical bars shall never be fabricated.

---

## Non-Blocking

Historical gaps shall not prevent delivery of usable authority.

Blocked providers shall not prevent unrelated symbols or timeframes from being served.

Only the requested authority may report degraded confidence.

---

# 5. Standard Request

Every request shall identify only:

```text
Symbol

Timeframe

Optional Date Range
```

No consumer-specific request fields are permitted.

---

# 6. Standard Response

Every successful response shall contain:

```text
Historical Bars

Current-As-Of Date Time (CAODT)

Authority State

Validation State

Truth Score

Gap Summary

Provider Summary

Operational Metadata
```

The response format shall remain identical regardless of the consumer.

---

# 7. Version 1 Truth Score

Version 1 Truth Score is intentionally simple.

Its purpose is operational confidence.

Not historical perfection.

Version 1 shall consider:

* Authority
* Freshness
* Validation
* Coverage

The implementation must remain explainable.

Every Truth Score shall expose the values contributing to the result.

Black-box scoring is forbidden.

---

# 8. Version 1 Gap Summary

Gap Summary is informational.

It shall not prevent authority delivery.

Each response shall expose:

* current gaps
* recent gaps
* historical gaps
* operational impact

Operational impact shall initially classify:

```text
NONE

LOW

MEDIUM

HIGH
```

Gap Summary Version 1 does not perform repair.

---

# 9. Current-As-Of Date Time

Every authority response shall contain CAODT.

CAODT becomes mandatory.

Consumers shall never need to infer freshness.

---

# 10. Authority State

Authority shall expose one operational state.

Example values:

```text
GREEN

AMBER

RED
```

Authority state shall describe confidence.

It shall not block consumers.

---

# 11. Validation

Every response shall expose validation state.

Examples:

```text
PASS

WARNING

LIMITED
```

Validation shall describe authority quality.

It shall not unnecessarily prevent authority delivery.

---

# 12. Provider Summary

Every response shall identify:

* provider
* provider freshness
* provider confidence
* provider entitlement where relevant

Provider failures affecting other symbols shall never block unrelated authority requests.

---

# 13. Operational Metadata

Version 1 metadata shall include:

* row count
* earliest bar
* latest bar
* timeframe
* symbol
* authority version

Future metadata extensions remain compatible.

---

# 14. Explicit Exclusions

SPEC-009A shall not implement:

Truth Console

Heat Maps

Balanced Scorecard

Epoch Scoring

Maintenance Console

Automatic Snapshots

Automatic Backups

Gap Repair Engine

Archive Engine

Consumer Suitability

Morphix integration logic

Signal Bar integration logic

HARP integration logic

Forecasting

Research

Market analysis

Trading logic

---

# 15. Success Criteria

The specification is accepted when all questions answer YES.

## Authority

Can every consumer request historical authority through one identical service contract?

---

## Availability

Does the authority continue serving usable historical data despite known gaps?

---

## Transparency

Does every response include:

* CAODT
* Truth Score
* Validation
* Gap Summary

---

## Independence

Does the authority remain completely consumer agnostic?

---

## Non-Blocking

Can one degraded symbol or timeframe exist without preventing unrelated authority requests?

---

## Truth

Is every uncertainty visible?

Is every limitation explained?

Is no historical data fabricated?

---

# 16. Operational Acceptance

Fragarach II shall successfully demonstrate:

Morphix can retrieve historical authority.

Signal Bar can retrieve historical authority.

Future HARP engines can retrieve historical authority.

without requiring application-specific behaviour.

---

# 17. Reports

Implementation shall produce:

```text
SPEC-009A_PREFLIGHT_REPORT.md

SPEC-009A_IMPLEMENTATION_REPORT.md

SPEC-009A_ACCEPTANCE_REPORT.md
```

If blocked:

```text
SPEC-009A_OPERATIONAL_BLOCKER_REPORT.md
```

---

# 18. Local Checkpoint

After successful acceptance:

Create one reviewed local checkpoint.

Verify:

* implementation
* tests
* reports
* native application

No push.

---

# 19. Completion Statement

SPEC-009A commissions Fragarach II as a production Operational Historical Authority.

It deliberately delivers the minimum operational capability required for consumers to depend upon Fragarach.

Future specifications improve operational maturity.

This specification establishes operational service.

**Operations is King.**
