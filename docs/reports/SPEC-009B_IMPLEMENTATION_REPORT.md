# SPEC-009B Implementation Report

**Specification:** `SPEC-009B_TRUTH_ENGINE_V1`

**Date:** `2026-07-12`

**Result:** `IMPLEMENTED`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Engine

`fragarach_ii.truth_engine` is the single producer of `fragarach_ii.truth_state.v1`. It exposes one-lane and all-authoritative-lanes operations. Both use query-only database access and deterministic ordering.

TruthState contains the total Truth Score; Authority, Freshness, Coverage, Continuity, Validation, and Provider component scores; GREEN/AMBER/RED state; CAODT; gap classification and impact; measurable coverage ranges and counts; provider summary; epoch placeholder; and a complete explanation.

The total score is the rounded equal-weight mean of measured components. Null components are excluded and listed explicitly as limitations. This prevents unknown provider or validation facts from becoming invented zeroes or confidence values.

Gap classification is:

* `NONE` when persisted validation finds no missing or outside-session observations;
* `CURRENT` when the latest expected session is missing;
* `RECENT` when material gaps exist but the latest expected session is present;
* `HISTORICAL` for non-material missing history;
* `NOT_MEASURED` when no validation summary exists.

## Service Integration

SPEC-009A now obtains scoring, authority state, validation state, and gap impact exclusively from TruthState. Its existing response fields remain available, and the full `truth_state` is added. Truth is calculated over the complete lane, so consumer date-range filtering cannot alter operational confidence.

## Native Integration

OperationsCore now provides Codable, Equatable, Sendable TruthState models and a compact read-only `readTruth` process intent. The bridge invokes `fragarach_ii.commands.truth_state`; it transports the engine object without reproducing calculations or adding UI.

## Scope Confirmation

No schema, migration, acquisition, validation execution, repair, epoch weighting, Truth View, chart, maintenance, snapshot, backup, consumer suitability, forecasting, research, or trading logic was added.

**Operations is King.**
