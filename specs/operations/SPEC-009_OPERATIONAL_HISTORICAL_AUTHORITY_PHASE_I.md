# SPEC-009 — Operational Historical Authority Phase I

**Document ID:** `SPEC-009_OPERATIONAL_HISTORICAL_AUTHORITY_PHASE_I`

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`

**Status:** Draft

**Authority:** Candidate Authority

**Doctrine:** Operations is King

**Push:** Forbidden

---

# 1. Purpose

This specification commissions Fragarach II as the laboratory's Operational Historical Authority.

Previous specifications established:

* constitutional authority
* immutable evidence
* immutable authority
* registration
* validation
* provider authority
* persistence

SPEC-009 establishes the operational service presented to every consumer.

It does **not** introduce forecasting, research, market interpretation or consumer-specific logic.

---

# 2. Mission

Fragarach II exists to provide the laboratory with the best available authoritative historical market data.

It shall:

* acquire
* register
* validate
* preserve
* maintain
* organise
* serve

historical market data.

It shall not:

* forecast
* analyse
* optimise
* trade
* interpret markets
* customise responses for applications

---

# 3. Operational Principles

Implementation shall follow these principles.

## Operations is King

The authority shall maximise truthful operational service.

It shall not maximise reasons to refuse service.

## Best Available Truth

Perfect historical data does not exist.

Fragarach shall always deliver the best available truthful authority.

Known limitations shall be measured.

Never hidden.

Never fabricated.

## Consumer Agnostic

Fragarach shall never know:

* Morphix
* Signal Bar
* HARP
* Ferret.plus

Consumer identity shall never alter historical truth.

## Administrator Above Automation

Routine maintenance shall be automatic.

The administrator shall always retain override authority.

---

# 4. Standard Authority Contract

Every consumer receives exactly the same response.

The authority contract shall contain:

```text
Historical Bars

Authority State

Validation State

Current-As-Of Date Time (CAODT)

Truth Score

Balanced Scorecard

Gap Summary

Provider Summary

Metadata

Provenance References
```

No consumer-specific fields are permitted.

---

# 5. Symbol Authority

Every symbol shall maintain:

* canonical identity
* aliases
* market
* asset class
* exchange
* timezone
* sessions
* providers
* authority state

---

# 6. Timeframe Authority

Every Symbol × Timeframe shall maintain:

* earliest bar
* latest bar
* row count
* CAODT
* continuity
* validation
* authority state
* Truth Score

---

# 7. Truth Score

Truth Score becomes a first-class operational property.

Truth Score measures operational confidence.

Not historical perfection.

It shall consider:

* freshness
* validation
* authority
* coverage
* continuity
* provider confidence

Truth Score shall be explainable.

No black-box calculations.

---

# 8. Balanced Scorecard

Every Symbol × Timeframe shall expose:

* Authority
* Freshness
* Coverage
* Continuity
* Validation
* Provider

Each dimension shall be independently visible.

---

# 9. Epoch Awareness

Operational confidence shall recognise historical epochs.

Older historical periods shall have different operational expectations.

Epochs influence confidence.

They never modify historical truth.

Different market families may define independent epoch boundaries.

---

# 10. Gap Management

Gap detection shall begin an operational workflow.

Detect.

Measure.

Classify.

Assess operational impact.

Attempt trusted repair.

If repair fails:

retain gap

record gap

continue serving authority.

Historical bars shall never be fabricated.

---

# 11. Truth View

The native application shall provide a Truth View.

Truth View becomes the operational dashboard.

It shall expose:

* overall Truth Score
* overall CAODT
* provider health
* market health
* Symbol × Timeframe heat maps
* Balanced Scorecards
* Truth trends
* Gap summaries
* authority summaries

The first operational question shall always be:

> Can I trust today's historical authority?

---

# 12. Maintenance

Maintenance becomes an operational service.

Maintenance includes:

* snapshots
* backups
* restore
* archive
* validation
* gap management
* metadata refresh
* provider monitoring
* integrity verification

Routine maintenance shall execute automatically.

---

# 13. Snapshots

Rolling operational snapshots shall execute automatically.

Rolling snapshots:

* overwrite according to retention policy
* support rapid operational rollback
* require no operator action

Protected snapshots shall automatically occur before:

* schema migration
* provider migration
* bulk imports
* market expansion
* mass repair

---

# 14. Backups

Backups remain separate from snapshots.

Backups shall:

* verify integrity
* verify checksums
* support restoration
* support long-term archive

Snapshots provide operational rollback.

Backups provide disaster recovery.

---

# 15. Administrator Override

Every automatic operation shall support administrator override.

The authority may recommend.

The administrator decides.

Every override shall be recorded in operational history.

---

# 16. Explicit Exclusions

SPEC-009 shall not implement:

* forecasting
* strategy
* trading logic
* market analysis
* research engines
* Behaviour Maps
* Morphix logic
* Signal Bar logic
* HARP logic
* Ferret.plus integration

---

# 17. Success Criteria

Fragarach shall become the operational historical authority.

The following questions shall all answer **YES**.

## Operational Service

Can every consumer retrieve authoritative historical data through one standard contract?

## Operational Confidence

Can the operator determine the health of the complete historical estate within five seconds?

## Truth

Does every response include:

* CAODT
* Truth Score
* Authority
* Validation

## Availability

Can truthful authority continue being served despite historical gaps?

## Transparency

Can every uncertainty be explained?

## Consumer Independence

Does Fragarach remain completely consumer agnostic?

## Maintenance

Can routine operational maintenance execute automatically without operator involvement?

## Administrator Authority

Can every automatic operation be overridden by the administrator?

---

# 18. Acceptance

SPEC-009 is accepted when Fragarach II demonstrably behaves as the laboratory's Operational Historical Authority.

Success is measured by operational trust rather than architectural complexity.

The authority shall quietly and reliably provide historical market data while exposing its confidence, uncertainty, and operational health.

Consumers shall simply request authoritative historical data.

Fragarach shall simply provide it.

---

## Final Statement

This specification marks the transition from **building Fragarach II** to **operating Fragarach II**.

Future specifications should extend operational capability without changing the fundamental role of the authority.

**Operations is King.**
