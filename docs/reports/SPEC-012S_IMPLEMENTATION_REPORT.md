# SPEC-012S Implementation Report

Date: 2026-07-12

## Implemented

- `OIL` deterministically returns WTI and Brent as an unselected ambiguous choice.
- WTI exposes USOIL, CL, and USO; Brent exposes UKOIL and BZ.
- SOL, Solana, SOLUSD, SOL/USD, SOLUSDT, and SOL/USDT resolve to canonical Solana.
- SOLUSD and SOLUSDT remain distinct representations.
- `solanna` uses a one-edit, same-entity restricted correction and requires explicit confirmation.
- Short symbols remain exact-only; unrelated fuzzy suggestions remain disabled.
- Every selected representation exposes D1, H1, M30, and M5 rows with provider capability, mapping, registration state, authority state, acquisition readiness, and evidence-backed reason.
- FX and crypto intraday capability is sourced from approved Twelve Data timeframe contracts.
- Stocks show D1 plus explicit `CAPABILITY_UNKNOWN` intraday rows rather than hiding them.
- Existing D1 lanes are detected independently from intraday rows.
- Native single-result layout now includes a horizontal full-width timeframe matrix.
- Native ambiguity leaves both markets unselected until the operator chooses.

## Authority-Safe Limitation

H1/M30/M5 rows are marked `BLOCKED_BY_AUTHORITY`. No invalid or fabricated intraday mutation is offered. See `SPEC-012S_MULTI_TIMEFRAME_AUTHORITY_BLOCKER.md`.

## Verification

- Python: 130 passed.
- Swift build: passed.
- OperationsCoreChecks: 15 passed.
- Signed native app: launched and remained running.
- No schema or migration files changed.
- No push performed.
