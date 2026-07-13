# SPEC-025 Revision 1 — Commissioning Report

Date: 2026-07-13  
Baseline: Fragarach II v1.0a  
Status: Accepted implementation scope complete; local authority-fact stops remain isolated

## Implemented scope

- Preserved one immutable canonical `D1` registration anchor per instrument.
- Added independently declared `H1`, `M30`, and `M5` Evidence Lane Authority for eligible Forex and Metals instruments.
- Bound each core timeframe to its exact checksummed `TWELVE_DATA_TIME_SERIES_<timeframe>_V1` contract. Yahoo remains `D1`-only.
- Added common intraday staging, provider-local timestamp normalization, immutable raw evidence, row-local quarantine, exact interval close timestamps, incomplete-current-interval rejection, New York 24×5 session validation, gap/freshness/CAODT validation, Truth, Estate Truth capability projection, and SPEC-018 v2 intraday serving.
- Added native timeframe capability, selection, reviewed acquisition, result, Truth, and CAODT presentation. Stocks remain intentionally `D1`-only with no intraday acquisition controls or warnings.

## Migration 8

- Applied: `SPEC-025 intraday validation summary coexistence amendment`.
- Application-table boundary remains exactly 10 tables; no table or column was added.
- Existing `fragarach_ii.lane_validation_summary.v1` rows remain valid and unchanged.
- Intraday lanes use `fragarach_ii.lane_validation_summary.v2`.
- Integrity and forward-migration gates passed.

## Commissioned authority

The active reviewed Forex cohort is `AUDUSD`, `EURAUD`, `NZDUSD`, and `USDJPY`. Eligible Metals are `XAUUSD` and `XAGUSD`. Each has authoritative `H1`, `M30`, and `M5` evidence.

Representative canonical ranges:

| Lane | First open UTC | Last open UTC | Latest close / CAODT UTC | Bars | Truth |
|---|---|---|---|---:|---|
| AUDUSD H1 | 2026-06-14 21:00 | 2026-07-13 02:00 | 2026-07-13 03:00 | 486 | 100 GREEN |
| AUDUSD M30 | 2026-06-14 21:00 | 2026-07-13 02:00 | 2026-07-13 02:30 | 971 | 100 GREEN |
| AUDUSD M5 | 2026-07-01 04:00 | 2026-07-13 02:35 | 2026-07-13 02:40 | 2,288 | 100 GREEN |
| XAUUSD H1 | 2026-06-14 21:00 | 2026-07-13 01:00 | 2026-07-13 02:00 | 485 | 100 GREEN |
| XAUUSD M30 | 2026-06-14 21:00 | 2026-07-13 02:00 | 2026-07-13 02:30 | 971 | 100 GREEN |
| XAUUSD M5 | 2026-07-01 04:00 | 2026-07-13 02:40 | 2026-07-13 02:45 | 2,289 | 100 GREEN |
| XAGUSD H1 | 2026-06-14 21:00 | 2026-07-13 01:00 | 2026-07-13 02:00 | 485 | 100 GREEN |
| XAGUSD M30 | 2026-06-14 21:00 | 2026-07-13 02:00 | 2026-07-13 02:30 | 971 | 100 GREEN |
| XAGUSD M5 | 2026-07-01 04:00 | 2026-07-13 02:40 | 2026-07-13 02:45 | 2,289 | 100 GREEN |

## Quarantine evidence

The final signed-native `AUDUSD/H1` update received 168 observations and committed with 0 inserts, 119 unchanged observations, and 49 row-local quarantines:

- `OUTSIDE_EXPECTED_SESSION`: 48
- `INCOMPLETE_CURRENT_INTERVAL`: 1

Valid observations remained available. Focused fixtures separately prove `MISALIGNED_INTERVAL_OPEN`, structural OHLC quarantine, and conflicting duplicate rejection. No synthesis, resampling, gap filling, or realignment is performed.

## Truth, Estate Truth, and SPEC-018

- Estate Truth: 94 / GREEN; 36 authoritative lanes; 35 GREEN, 1 AMBER, 0 RED.
- Estate capability projection: 22 symbols with independent policy and lane-authority states.
- SPEC-018 catalog: `fragarach_ii.external_consumer_catalog.v2`, 36 available histories, 22 capability records.
- Existing `AUDUSD/D1` remains on `fragarach_ii.external_consumer_history.v1` with its original 14,263 bars and semantics.
- `AUDUSD/H1`, `M30`, and `M5` serve through `fragarach_ii.external_consumer_history.v2`, are AVAILABLE/GREEN, and exactly match canonical stored ranges and counts.
- `AAPL/H1` returns `INTENTIONALLY_DEFERRED`, no bars, and no warning state.

## D1 non-regression fingerprint

Pre- and post-implementation D1 row counts and SHA-256 fingerprints are identical:

| Boundary | Rows | SHA-256 |
|---|---:|---|
| bars | 166,999 | `8eb80ba2696cfefd2cf7885bccc3e2fd0d0ce9a027551bb8aa9682a5fa8cef4d` |
| evidence_lanes | 22 | `7acd58b0c7609adf2601d1728d359f20815d7d2de6235b072b1bcf7c774d4e6d` |
| lane_state | 19 | `f0df1a7fa515ef8f6702a3473c264e6321b12793afce042ef2f9a1438d6879de` |
| provenance | 267,290 | `950687febe566b3f0179257141ef47ba7f5ce60cc25abcdf4c4e191e5e5683be` |
| instrument_registrations | 22 | `bf2e9847ad665cc4817fe5bf2d800375edbc640388f077d1604ccd5c149ec8fc` |

The provenance fingerprint is ordered by canonical lane/timestamp/event identity. No accepted D1 value, timestamp, registration, validation summary, or evidence row changed.

## Verification

- Focused Python storage/provider/ingestion/validation/Truth/Estate/SPEC-018/lifecycle gates: 148 passed.
- Native `OperationsCoreChecks`: 26 passed.
- Release-style Swift build: passed.
- Signed bundle: `com.raymorgan.fragarach-ii.operations`, ad-hoc signature verified.
- Signed-native operator journey: passed for timeframe selection, review, confirmation, acquisition, quarantine result, Truth, CAODT, and UI refresh without restart or command-line intervention.
- Operator evidence: [signed native AUDUSD/H1 workflow](evidence/SPEC-025_signed_native_AUDUSD_H1.png).

## Remaining local market stops

- Energy: representation must be resolved as `PROVIDER_DERIVED_REFERENCE` before intraday commissioning.
- Indices: exact calculated-index identity, administrator, methodology, session, and provider facts require approval.
- Crypto: exact Twelve Data venue or aggregate scope requires approval.

These stops do not affect commissioned Forex or Metals lanes. No constitutional incompatibility was found in the implemented scope.
