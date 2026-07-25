# SPEC-045 Implementation and Acceptance Report

## Result

SPEC-045 is implemented. Fragarach now registers, generates, stores, rebuilds, presents, and serves explicitly synthetic M15, H2, and H4 products while preserving the irreversible rule:

```text
REAL -> SYNTHETIC
SYNTHETIC -> SYNTHETIC
SYNTHETIC -/-> REAL
```

## Delivered

- Added the explicit `fragarach_ii.synthetic_registry.v1` registry with versioned, calendar/session-bound aggregation rules and initial AUDUSD registrations for:
  - M5 REAL -> M15 SYNTHETIC
  - M30 REAL -> H2 SYNTHETIC
  - H1 REAL -> H4 SYNTHETIC
- Added registration and graph validation that rejects missing rules, dynamic/unapproved source relationships, lineage cycles, calendar mismatches, originating-real mismatches, and any target evidence class other than SYNTHETIC.
- Added a dedicated five-table Synthetic Repository beside, but outside, the ten-table canonical authority:
  - `aggregation_rules`
  - `synthetic_registrations`
  - `synthetic_observations`
  - `synthetic_provenance`
  - `generation_failures`
- Added deterministic session-aligned aggregation using explicit source/target timeframes, timezone, session anchor, interval closure, component count, OHLC rule, volume rule, missing-component rule, and partial-current-period rule.
- Only complete, closed source component sets publish a closed synthetic observation. Missing components are recorded as failures and leave the product Incomplete; partial current targets remain unpublished.
- Added full provenance per synthetic observation: source bounds, real authority revision, parent synthetic revision, originating real revision, rule version, generation time, and the complete lineage chain.
- Added incremental generation when a source extends beyond its prior edge. Corrections at an unchanged edge trigger a complete affected-history recomputation. Source-revision notifications recurse through synthetic dependents.
- Added Available, Stale, Incomplete, and Unavailable states. Source revision advancement marks direct and transitive dependents Stale until regenerated.
- Added independent synthetic revisions and content checksums. Synthetic generation never advances real lane state, real authority revisions, real freshness, acquisition completion, provider health, or manual-request state.
- Added post-canonical-commit generation notifications. Synthetic failure is recorded separately and cannot roll back or reclassify real ingestion.
- Added rebuild support that deletes and recreates only the Synthetic Repository.
- Added an evidence-aware consumer contract:
  - REAL-only requests reject synthetic substitution.
  - SYNTHETIC-permitted requests return exact-timeframe observations and complete provenance.
  - Unauthorized consumers are rejected.
  - Unregistered timeframes return Unavailable and never fall back to another timeframe.
- Added a native Synthetic Products section in Market History showing SYNTHETIC identity, immediate and originating source, rule/version, calendar/session, status, source and synthetic revisions, latest observation, count, authorized consumers, Regenerate, Regenerate All, and Rebuild Repository.
- Kept real Market History responses unchanged: H4 and M15 still show `TIMEFRAME_NOT_ACTIVE` in the real-only service rather than silently returning synthetic data.

## Authority Boundaries

- The canonical database remains exactly ten tables and contains no synthetic observations.
- Synthetic products do not appear as provider-acquired lanes and do not affect Estate freshness totals.
- Synthetic work does not enter the acquisition queue, consume provider bandwidth, resolve manual acquisition requests, or change provider health.
- No SignalBar or MorphixFC mathematics or engines were changed. They are recorded only as authorized consumers.
- Evidence Discovery was not implemented or started.

## Automated Verification

- `PYTHONPATH=src python3 -m pytest -q tests/operations/test_spec045_synthetic_repository.py`
  - 9 passed.
  - Covers M15/H2/H4 generation, deterministic output, missing components, partial periods, real and synthetic lineage, transitive staleness, independent revisions, consumer evidence requirements, consumer authorization, incremental notifications, rebuild, canonical separation, and promotion rejection.
- Combined focused verification across SPEC-041/042/044/045, providers, ingestion, and existing consumer/history contracts
  - 91 passed, 2 subtests passed.
- `swift run OperationsCoreChecks`
  - 28 checks passed.
- Full Python suite
  - 229 passed, 2 subtests passed, 1 pre-existing stale assertion failed: `test_registration_command_migrates_v6_and_accepts_unmapped_fx` expects migration 7 although the repository's current default is migration 8 from SPEC-025.
- `swift build -c release`
  - Passed.
- Signed bundle
  - Strict code-signature verification passed.
  - Normal quit left no application or scheduler process.

## Live Synthetic Acceptance — 2026-07-14

- Activated the explicit AUDUSD registry against the current real authority without changing canonical table count or integrity.
- Generated current sidecar products:
  - AUDUSD M15: 6,820 observations, synthetic revision 2.
  - AUDUSD H2: 7,757 observations, synthetic revision 3 after a native operator regeneration.
  - AUDUSD H4: 5,352 observations, synthetic revision 2.
- All three products correctly reported Incomplete because recorded real histories contain component gaps. The generator published complete target intervals and recorded 3,334 missing-component failures; it did not interpolate, forward fill, or conceal the real gaps.
- REAL-only SignalBar H4 returned `SYNTHETIC_NOT_PERMITTED` with zero observations.
- SYNTHETIC-permitted SignalBar H4 returned the exact H4 product with complete lineage and matching source/originating real authority revisions.
- Deleting and rebuilding the Synthetic Repository reproduced the same registration content checksums and observation counts for the same source revisions and rule versions.
- During the signed native session, new real source publications automatically advanced the dependent M15/H2/H4 products without using the acquisition queue.
- The native History screen visually distinguished real inactive H4/M15 service rows from the separate purple SYNTHETIC product cards. Native Regenerate advanced AUDUSD H2 from synthetic revision 2 to 3.
- After generation, rebuild, automatic refresh, and native regeneration:
  - canonical table count remained 10;
  - `PRAGMA integrity_check` returned `ok`;
  - `PRAGMA foreign_key_check` returned no findings.

## Completion

Fragarach can explicitly register and serve synthetic timeframes with complete, irreversible lineage. Real evidence may create synthetic evidence; synthetic evidence may create further synthetic evidence; no path can create, promote, repair, or satisfy real evidence from synthetic observations.
