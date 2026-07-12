# SPEC-009B — Truth Engine Version 1

**Document ID:** `SPEC-009B_TRUTH_ENGINE_V1`

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`

**Status:** Implementation

**Authority:** Candidate Authority

**Doctrine:** Operations is King

**Push:** Forbidden

---

# 1. Objective

Implement the first operational Truth Engine.

The Truth Engine becomes the single authority responsible for calculating operational confidence for every Symbol × Timeframe.

This specification implements the engine only.

It does not implement the Truth Console UI.

---

# 2. Purpose

Every Symbol × Timeframe shall have a continuously calculated operational truth state.

The Truth Engine converts authority metadata into operational confidence.

Consumers never calculate Truth.

They consume Truth.

---

# 3. Inputs

The engine shall consume existing authority only.

It shall not acquire data.

It shall not perform repairs.

It shall use existing:

* registrations
* authority ledger
* evidence lanes
* canonical bars
* provider metadata
* validation summaries
* CAODT
* gap summaries

No schema changes are authorised.

---

# 4. Outputs

For every Symbol × Timeframe produce:

```text
TruthState
```

Containing:

```text
Truth Score

Authority Score

Freshness Score

Coverage Score

Continuity Score

Validation Score

Provider Score

Authority State

CAODT

Gap Impact

Provider Summary

Explanation
```

This object becomes the operational truth model.

---

# 5. Explainability

Every score shall be explainable.

Example:

```text
Truth Score

94

Components

Authority

100

Freshness

96

Coverage

92

Continuity

90

Validation

100

Provider

88
```

No hidden calculations.

No opaque weighting.

---

# 6. Authority State

Truth Engine shall classify:

```text
GREEN

AMBER

RED
```

State shall describe confidence.

State shall never unnecessarily block authority delivery.

---

# 7. Gap Classification

Classify gaps as:

```text
NONE

HISTORICAL

RECENT

CURRENT
```

and

```text
LOW

MEDIUM

HIGH
```

operational impact.

No repair logic.

Classification only.

---

# 8. Coverage

Version 1 shall calculate:

* earliest bar
* latest bar
* row count
* expected range
* available range

Coverage must be measurable.

---

# 9. Freshness

Freshness derives from:

CAODT

latest expected session

latest available session

No consumer-specific rules.

---

# 10. Validation

Truth Engine shall consume existing validation.

It shall never perform validation itself.

---

# 11. Provider Confidence

Calculate provider confidence from persisted facts only.

Do not infer.

Unknown remains:

```text
NOT_MEASURED
```

---

# 12. Epoch Support

Implement framework only.

Do not implement weighting.

Return:

```text
Epoch

UNKNOWN
```

or configured epoch.

Future specifications extend this.

---

# 13. Service Integration

Replace Version 1 Truth Score in SPEC-009A.

Authority Service shall consume Truth Engine.

Authority Service shall never calculate scores itself.

Single source of truth.

---

# 14. Native Integration

Expose TruthState through native read-only interfaces.

No UI implementation.

Only data model.

---

# 15. Explicit Exclusions

Do not implement:

Heat Maps

Truth View

Charts

Maintenance

Snapshots

Backups

Gap Repair

Consumer Suitability

Morphix logic

Signal Bar logic

HARP logic

Epoch weighting

Machine learning

Forecasting

---

# 16. Tests

Add tests proving:

* deterministic TruthState
* repeatable calculations
* identical output for identical authority
* explanation always present
* unknown values remain unknown
* no fabricated values
* read-only operation
* consumer independence

---

# 17. Acceptance

Acceptance requires:

* Truth Engine replaces inline scoring.
* One TruthState exists for every Symbol × Timeframe.
* Authority Service consumes TruthState.
* Existing SPEC-009A tests remain green.
* All previous acceptance tests remain green.
* Native build passes.
* No schema change.
* No migration.
* No push.

---

# 18. Reports

Produce:

```text
SPEC-009B_PREFLIGHT_REPORT.md

SPEC-009B_IMPLEMENTATION_REPORT.md

SPEC-009B_ACCEPTANCE_REPORT.md
```

If blocked:

```text
SPEC-009B_TRUTH_ENGINE_BLOCKER.md
```

---

# 19. Local Checkpoint

After successful acceptance:

Create one reviewed local checkpoint.

No push.

---

## Final Engineering Instruction

Build the **Truth Engine** as an independent operational engine.

It must become the **single producer of operational confidence** for the entire Fragarach II estate.

No other component shall calculate Truth independently.

The engine shall remain deterministic, explainable, read-only, and consumer agnostic.

**Operations is King.**
