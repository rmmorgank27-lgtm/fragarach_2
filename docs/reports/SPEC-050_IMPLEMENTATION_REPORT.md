# SPEC-050 — Provider Authority Regression Repair

## Outcome

Accepted. The affected commissioned FX lanes no longer evaluate Twelve Data as
`NO_APPROVED_MAPPING` when previously confirmed provider authority exists.

## Deterministic root cause

The first incorrect point was representation lookup. SPEC-047 correctly marked
AUDCAD and AUDJPY as requiring no provider-mapping review because immutable
committed ingest runs already proved the exact `AUD/CAD` and `AUD/JPY`
representations. During SPEC-048 migration, the default resolver narrowed its
targets to only SPEC-047 rows that required review whenever that set was
non-empty. That predicate excluded the already-proven rows, so no
representation-scoped provider fact was stored. Runtime acquisition planning
then received `None` from representation lookup and emitted
`NO_APPROVED_MAPPING` before timeframe, credential, entitlement, budget, or
cooldown authority could be evaluated.

## Minimal repair

- The SPEC-048 migration target set now includes both rows requiring review and
  active representations carrying prior approved mapping evidence.
- Missing facts can be migrated without a network lookup only when immutable
  committed runs consistently prove the exact FX base/quote representation.
- Only timeframes actually proven by committed evidence are marked supported.
- Existing provider facts are never overwritten, and no symbol is hard-coded.

Scheduler, Queue, acquisition planning, canonical authority, provider doctrine,
synthetic storage, Evidence Discovery, and market data behavior were not changed.

## Verification

- Focused SPEC-048/SPEC-049B/SPEC-050 tests: `15 passed`.
- Full Python regression suite: `275 passed, 2 subtests passed`.
- Native release build and signed-bundle verification:
  `./script/build_and_run.sh --verify` succeeded and the app remained alive.
- Live provider-facts revision advanced to `5`.
- `AUDCAD` resolves to `AUD/CAD` and `AUDJPY` resolves to `AUD/JPY` as
  `EXACT_REPRESENTATION`, each with visible `M5`, `M30`, `H1`, and `D1`
  capability facts.
- AUDCAD M5, AUDCAD M30, and AUDJPY H1 no longer contain
  `NO_APPROVED_MAPPING`. Their stale manual work was automatically restored to
  `QUEUE` items.

The live scheduler has no currently retrievable Twelve Data credential, so its
next deterministic gate is `CREDENTIAL_MISSING` and the restored items are in
`Credential Repair Required`. The focused valid-credential regression proves
the complete accepted transition: Twelve Data eligible, stale requests
archived, and ready `QUEUE` items restored.

## Regression protection

The mixed SPEC-047 review-set condition that caused the omission is reproduced
directly in SPEC-050 coverage. The test uses AUDCAD M5, AUDCAD M30, and AUDJPY
H1, verifies representation and timeframe authority, then proves provider
eligibility and automatic Manual Request archival/queue restoration. Future
unproven or inconsistent symbols remain unmapped rather than being fabricated.
