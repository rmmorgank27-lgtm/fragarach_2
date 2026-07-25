# Performance Phase 3 — Operator Workflow & Publication Completeness

## Outcome

Fragarach now treats the Required Set as the symbol-level recovery workflow.
The operator can resume an incomplete set without re-fetching canonical data:
current/published lanes are skipped, incomplete lanes plan forward from their
canonical edge, and failed publication is retried as projection-only work.

The Acquire & Import Required Set matrix now shows the per-lane publication
state and exposes **Resume Required Set** when a lane is blocked or its
publication failed. Scheduler snapshots include the same publication state,
so a selected lane can distinguish canonical acquisition from publication.

## Publication completeness

Explicit asynchronous publication hooks now cover:

| Operator mutation | Publication trigger |
| --- | --- |
| Manual CSV import | `MANUAL_CSV_IMPORT` |
| Registration | `SYMBOL_REGISTRATION` |
| Provider mapping approval | `PROVIDER_MAPPING_APPROVAL` |
| Manual lane declaration / commissioning | `MANUAL_LANE_DECLARATION` / `LANE_COMMISSIONING` |
| Required Set and resume | `REQUIRED_SET_JOB` / `REQUIRED_SET_RESUME_PUBLICATION` |
| Retirement, reactivation, removal | lifecycle-specific trigger |

Each hook runs only after the canonical mutation. The dirty state is durable,
but the publisher remains asynchronous; no hook rolls back canonical evidence.

`lane_publication_detail` exposes state, revision, timestamp, failure reason,
and job identifier. `retry_publication` retries only lanes in
`FAILED_RETRYABLE`; it leaves already-running publication alone, preserving
publication ordering.

## Operator states and guidance

The selected Required Set shows `Published`, `Publishing`, `Publication
Failed`, or `Pending Publication` beside each required lane. A failed lane is
actionable through Resume Required Set. Existing blocker text remains visible
in the lane matrix and provider setup controls; the new workflow makes
`PARTIAL_EVIDENCE` and `PUBLICATION_FAILED` resumable without selecting
individual timeframes.

Long Required Set jobs retain their live Scheduler job facts: current lane,
completed and remaining lanes, partial failures, provider usage, and canonical
edges. This is surfaced in Acquire & Import while the grouped operation runs.

## Priority and safety

Required Set, resume, and one-lane Fetch Now continue to use the existing
`OPERATOR_FETCH` work class. Scheduler dispatch ranks that class ahead of
background catch-up while retaining provider budgets, per-lane writer guards,
canonical authority, and publication ordering.

## Verification

- Added focused Phase 3 coverage for failed-publication retry and manual-import
  publication marking.
- Phase 1/2 Required Set, publication, manual-ingestion, onboarding, and
  retirement selections were run. One existing retirement test is sensitive to
  the current wall clock: it requests registration at `2026-07-15` after a
  removal stamped with the current date, so its immutable-ledger predecessor
  check correctly rejects the backdated supersession.
