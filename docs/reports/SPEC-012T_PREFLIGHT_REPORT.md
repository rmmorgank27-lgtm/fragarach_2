# SPEC-012T Preflight Report

Date: 2026-07-12

## Findings

1. ISO synthesis occurred in `_currency_market` in `market_discovery.py`.
2. It constructed `base + '/' + quote` as `provider_symbol`.
3. Any constructed symbol was consequently labelled `KNOWN_MAPPING`.
4. Discovery, registration, and acquisition did not independently validate ordered orientation.
5. Current reviewed mapping authority confirms EURAUD as `EUR/AUD` in `TWELVE_DATA_FX_DIRECT_PAIRS_V1`.
6. No authority confirms AUDEUR as `AUD/EUR`; EURAUD is its authoritative inverse.
7. Runtime FX registrations inspected: AUDUSD/D1, EURAUD/D1, JPYCHF/D1.
8. AUDUSD and JPYCHF have canonical bars; EURAUD has none. All three stored symbols match their ordered identities.
9. Timeframe capability is now joined only after exact ordered-pair mapping resolution.
10. No schema or migration change is required for orientation validation.

## Implementation Boundary

One exact provider mapping service is rechecked independently by discovery, registration, acquisition, and audit. Reciprocal data generation remains out of scope.
