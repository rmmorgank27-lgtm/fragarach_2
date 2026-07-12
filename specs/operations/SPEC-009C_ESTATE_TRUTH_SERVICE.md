# SPEC-009C — Estate Truth Service

**Document ID:** `SPEC-009C_ESTATE_TRUTH_SERVICE`

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`

**Status:** Implementation

**Authority:** Candidate Authority

**Doctrine:** Operations is King

**Push:** Forbidden

---

# 1. Purpose

SPEC-010 correctly identified a missing operational service boundary.

The Truth Console is specified as a thin read-only client.

The current Truth Engine produces deterministic `TruthState` objects for individual Symbol × Timeframe authority lanes, but no operational service exists that exposes the complete estate as one deterministic object.

This specification creates that missing service.

No UI is implemented.

---

# 2. Objective

Implement one read-only service that produces the complete operational state of the Fragarach estate.

The service becomes the sole producer of estate-wide operational truth.

Every consumer requiring estate-level operational information shall consume this service.

No consumer shall independently calculate estate summaries.

---

# 3. Scope

Implement:

* Estate Truth Service
* Estate Truth State
* Read-only JSON command
* Native bridge
* Cached deterministic output

Do not implement:

* SwiftUI
* Heat maps
* Charts
* Maintenance
* Provider management
* Gap repair
* New database schema
* Database migration

---

# 4. Service Contract

The service shall produce one object.

```text
EstateTruthState
```

Version:

```text
fragarach_ii.estate_truth_state.v1
```

Every request returns one complete operational snapshot.

---

# 5. Estate Summary

The Estate Summary shall contain:

```text
Overall Truth Score

Overall Authority State

Overall CAODT

Total Symbols

GREEN count

AMBER count

RED count

Authority Version

Generated At
```

The service owns all calculations.

Consumers never calculate estate statistics.

---

# 6. Truth Matrix

Return every authoritative Symbol × Timeframe.

Each entry contains:

```text
Symbol

Timeframe

TruthState
```

TruthState shall be the exact object produced by the Truth Engine.

No duplication.

No recalculation.

---

# 7. Search Metadata

Each Symbol shall expose:

* canonical symbol
* display name
* aliases
* market
* asset class
* exchange
* provider family

This metadata shall originate from existing authority.

SwiftUI shall perform filtering only.

---

# 8. Provider Summary

Each lane shall expose:

```text
Provider

Provider Freshness

Provider Confidence

Entitlement

Unknown values
```

No inference.

Unknown remains explicit.

---

# 9. Gap Summary

Each lane shall expose:

```text
Current Gap Count

Recent Gap Count

Historical Gap Count

Total Gap Count

Gap Classification

Operational Impact
```

Gap information is informational only.

The service performs no repair.

---

# 10. Estate Aggregation

The Estate Truth Service owns:

* overall Truth Score
* overall Authority State
* GREEN/AMBER/RED counts
* overall CAODT
* estate statistics

No consumer may derive these independently.

Aggregation must be deterministic.

---

# 11. Caching

The service shall support cached operation.

Launch behaviour:

```text
Load EstateTruthState

↓

Cache

↓

Render

↓

Manual Refresh replaces cache
```

No recomputation during rendering.

---

# 12. Native Bridge

Expose EstateTruthState through OperationsCore.

SwiftUI receives:

```text
EstateTruthState
```

No additional joins.

No SQL.

No authority calculations.

No business logic.

---

# 13. Read-only Rules

The service shall:

* open SQLite read-only
* perform deterministic ordering
* never mutate authority
* never acquire data
* never validate
* never repair

Read-only only.

---

# 14. Performance

EstateTruthState shall be generated once.

Consumers perform:

* filtering
* sorting
* selection

Only.

The service owns all expensive work.

---

# 15. Explicit Exclusions

Do not implement:

Truth Console

Charts

Heat Maps

Snapshots

Backups

Maintenance

Provider Updates

Gap Repair

Epoch Weighting

Consumer Suitability

Forecasting

Research

Trading

Database Changes

Schema Changes

Migration

---

# 16. Tests

Add tests proving:

* deterministic EstateTruthState
* repeatable output
* stable ordering
* one TruthState per authoritative lane
* no duplicated calculations
* unknown values preserved
* read-only operation
* consumer independence
* cached output identical to live output

All previous tests shall remain green.

---

# 17. Acceptance

Acceptance requires:

✓ EstateTruthState exists.

✓ Estate Summary deterministic.

✓ Truth Matrix deterministic.

✓ Search metadata available.

✓ Provider summaries available.

✓ Gap summaries available.

✓ Native bridge operational.

✓ No schema changes.

✓ No migration.

✓ Existing Truth Engine unchanged.

✓ Existing Authority Service unchanged except consuming EstateTruthState where appropriate.

✓ Previous acceptance suites remain green.

✓ Native build passes.

✓ No push.

---

# 18. Reports

Produce:

```text
SPEC-009C_PREFLIGHT_REPORT.md

SPEC-009C_IMPLEMENTATION_REPORT.md

SPEC-009C_ACCEPTANCE_REPORT.md
```

If blocked:

```text
SPEC-009C_ESTATE_SERVICE_BLOCKER.md
```

---

# 19. Local Checkpoint

After successful acceptance:

Create one reviewed local checkpoint.

No push.

---

# 20. Completion Statement

SPEC-009C completes the operational service layer required by the Truth Console.

After acceptance:

* Truth Engine owns lane confidence.
* Estate Truth Service owns estate confidence.
* Truth Console becomes a thin presentation client.

No UI shall contain operational calculations.

No consumer shall reconstruct operational truth independently.

The Estate Truth Service becomes the single authoritative operational view of the entire Fragarach II estate.

**Operations is King.**
