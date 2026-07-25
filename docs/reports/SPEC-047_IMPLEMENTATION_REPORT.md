# SPEC-047 Implementation Report

## Outcome

SPEC-047 is implemented and accepted in the signed native Fragarach II build. Scheduler and operator Fetch now use one acquisition authority; all capability surfaces consume its projection; crypto freshness contributes to operational health; and representation mappings are explicit and enforced before provider execution.

The signed bundle is `dist/Fragarach II.app` (`com.raymorgan.fragarach-ii.operations`, bundle build `c7d17898a0e7`).

## Delivered authority

- `acquisition_orchestrator.py` owns the shared `OPERATOR_FETCH` plan, deterministic provider ordering, eligibility, reviewed mapping authority, last-success facts, and the first-launch reconciliation contract.
- Scheduler and operator Fetch enter the same `run_due_acquisitions` executor under one per-journal acquisition lock. Active work is deduplicated and rate limits, pause state, cooldowns, fallback ordering, immutable ingestion, and manual escalation are shared.
- Discover, Acquire & Import, Scheduler, and Estate consume `fragarach_ii.acquisition_capability_projection.v1`; no surface keeps a private crypto capability list.
- Provider results expose every considered provider with structured eligibility and rejection reasons. Exhaustion creates one deduplicated manual request; success stops fallback.
- `SOLUSD` is canonical SOL/USD. Binance `SOLUSD` is a reviewed `EXACT_REPRESENTATION`; CoinGecko `solana` with USD is a reviewed `APPROVED_PROVIDER_ALIAS` for D1. Binance `SOLUSDT` is not an alias for `SOLUSD`; `NOT_EQUIVALENT` and `CONVERSION_REQUIRED` are rejected before execution.
- Binance ingestion excludes an open kline before immutable publication and records `incomplete_rows_excluded` in the outcome.

## Freshness and health

- `CRYPTO_24X7_UTC_V1` supplies continuous UTC boundaries and per-timeframe M5, M30, H1, and D1 thresholds.
- Integrity, freshness, acquisition, and overall operational state are separate projections. A stale lane cannot remain GREEN because integrity is healthy.
- Estate and hierarchy headlines use the most material active child condition: RED outranks AMBER, which outranks GREEN. Numeric mean scores remain separate informational metrics.
- Every successful publication reloads authority, Scheduler, Estate, and Discover last-success facts without restarting the application.

## First-launch reconciliation

The live first-launch report audited 108 active lanes, found 56 previous display contradictions, and left 27 ambiguous mappings for operator review. Canonical observations were `RETAINED_UNCHANGED`; provider mapping archive action was `NONE`.

The complete required lane-by-lane report is [SPEC-047_CAPABILITY_RECONCILIATION.md](spec047/SPEC-047_CAPABILITY_RECONCILIATION.md).

For SOLUSD, the reconciled projection is:

| Lane | Previous display | Eligible reviewed provider facts | Exact ineligible facts | Operator decision |
|---|---|---|---|---|
| SOLUSD:D1 | SUPPORTED | Binance `SOLUSD` exact; CoinGecko `solana` approved alias | Twelve Data credential missing; Yahoo asset unsupported | NONE |
| SOLUSD:H1 | CAPABILITY_UNKNOWN | Binance `SOLUSD` exact | Twelve Data credential missing; Yahoo asset unsupported; CoinGecko timeframe unsupported | NONE |
| SOLUSD:M30 | CAPABILITY_UNKNOWN | Binance `SOLUSD` exact | Twelve Data credential missing; Yahoo asset unsupported; CoinGecko timeframe unsupported | NONE |
| SOLUSD:M5 | CAPABILITY_UNKNOWN | Binance `SOLUSD` exact | Twelve Data credential missing; Yahoo asset unsupported; CoinGecko timeframe unsupported | NONE |

## Signed SOLUSD acceptance

One signed native journey searched `Solana`, showed distinct active `SOLUSD` and `SOLUSDT` identities, inspected all four timeframe projections, selected commissioned `SOLUSD:M5`, reviewed the provider plan, and ran Fetch / Update.

The signed Fetch considered all four providers: Twelve Data was ineligible because its credential was missing, Yahoo Finance was ineligible because the asset class is unsupported, Binance was eligible through reviewed exact symbol `SOLUSD`, and CoinGecko was ineligible for M5 because the timeframe is unsupported. Binance published three closed observations through immutable ingestion and stopped fallback.

Live evidence:

- Operation: `operator-fetch-de1cd1fe239a4a53a65176fd315510cb`
- Ingest run: `efb4cef481bb4dea9def485389190d0d`
- Raw evidence: `raw-d118f29ece48d84d158b29653accc6194b52182b6123db8cc4bca331d6c1f24b`
- Provider contract / symbol / mapping: `BINANCE_KLINES_V1` / `SOLUSD` / `EXACT_REPRESENTATION`
- Canonical edge: `2026-07-14T08:30:00+00:00` → `2026-07-14T08:45:00+00:00`
- Expected edge: `2026-07-14T08:45:00+00:00`
- Freshness after publication: `Current`, `HEALTHY`, zero closed-interval lag
- Published observations: 3; unchanged: 94; conflicts preserved: 8; corrected: 0
- Open provider rows excluded before staging: 1
- Authority revision after publication: `sha256:8e88f088ba465222213273bf30b0d516fb7f2527d34a4659358c4ac7a01191f6`

An earlier command-line probe exposed that Binance could return the still-open five-minute kline. That probe was not used as final acceptance. The adapter was repaired and regression-tested before the signed journey above; its committed outcome proves `incomplete_rows_excluded: 1` and the published latest bar closes at 08:45 UTC.

Scheduler refreshed to zero Behind lanes after publication. Estate refreshed without restart. A final signed native drill-down showed Crypto RED with one Critical child, rather than allowing the mean score of 79 to present a GREEN headline.

## Verification

- Python: `246 passed, 2 subtests passed`
- Native core: `OperationsCoreChecks: 28 checks passed`
- Swift release build: passed
- Signed app build/run verification: passed
- `codesign --verify --deep --strict`: passed
- Canonical verification: exactly ten tables, integrity OK, foreign keys OK, migration checksums OK
- Evidence Discovery: not implemented

The canonical schema remains the required ten tables, and immutable raw evidence, ingest runs, bars, and provenance paths remain in force.
