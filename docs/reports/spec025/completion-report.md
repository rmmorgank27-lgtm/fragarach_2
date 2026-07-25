# SPEC-025 Completion Report

## A. Import Activity

**Status:** Implementation complete; strict acceptance remains pending a captured native click-through of the success and controlled-failure journeys.

### State model

`DataOperationState` now has `idle`, `preparing`, `reading`, `validating`, `ingesting`, `refreshingAuthority`, `completed`, and `failed` states. Active stages are driven by real command boundaries emitted by `ingest_file`; no percentage or animation timer is used.

Presented labels:

- Preparing import
- Reading file
- Validating observations
- Writing history
- Refreshing authority
- Import complete
- Import failed

The selected matrix lane and operation area both show activity. Duplicate submission is rejected while the bridge owns an active process. The prior receipt and lane metadata remain available during work. Process results are committed to the UI only after Estate Truth and the SQLite snapshot have both reloaded.

### Failure behavior

The spinner stops in `failed`, the exact row rejection is presented, the failed receipt is retained, and the prior canonical lane remains unchanged. Controlled GBPJPY M5 failure: `high is below low`; canonical count remained 2,305.

### Journeys and verification

- GBPJPY M5 successful immutable import: 0.084 seconds, one unchanged real observation, stages `reading → validating → ingesting`.
- BTCUSD D1 large successful immutable import: 0.352 seconds, 6,031 unchanged real observations; native authority refresh adds the visible `Refreshing authority` interval.
- GBPJPY M5 controlled failure: 0.069 seconds, one rejected observation, zero inserts, prior 2,305 rows preserved.
- Focused lifecycle/progress protocol check: passed.
- Focused duplicate-submission check: passed.
- Focused manual-ingestion progress test: passed.
- Swift debug build: passed.
- Signed release bundle launch and eight-second process verification: passed.
- `codesign --verify --deep --strict`: passed.

Native launch screenshot: [native-launch.png](native-launch.png)

## B. Crypto, Energy, and Indices Timeframe Completion

**Status:** Partially completed; not accepted.

### Estate scope

The live Estate registry supplied five commissioned symbols:

- Crypto: BTCUSD
- Energy: USO, USOIL
- Indices: DJI, SPY

Expected lanes: 20 (five symbols × D1/H1/M30/M5).

Declared evidence lanes after work: 8. Populated lanes: 7. Operationally available target lanes: 4. All four available lanes belong to BTCUSD.

### Completed lanes

| Symbol | Timeframe | Rows | Earliest bar | Latest bar | CAODT | Provider |
|---|---:|---:|---|---|---|---|
| BTCUSD | D1 | 6,032 | 2009-10-05 00:00 UTC | 2026-07-11 00:00 UTC | 2026-07-11T00:00:00+00:00 | Twelve Data |
| BTCUSD | H1 | 3,937 | 2026-01-29 00:00 UTC | 2026-07-12 00:00 UTC | 2026-07-12T01:00:00+00:00 | Twelve Data |
| BTCUSD | M30 | 3,937 | 2026-04-21 00:00 UTC | 2026-07-12 00:00 UTC | 2026-07-12T00:30:00+00:00 | Twelve Data |
| BTCUSD | M5 | 3,457 | 2026-06-30 00:00 UTC | 2026-07-12 00:00 UTC | 2026-07-12T00:05:00+00:00 | Twelve Data |

All BTCUSD lanes were acquired at their native timeframe through the existing Twelve Data evidence pipeline. No synthetic candles, placeholder rows, D1 duplication, or application-side resampling were used. All four return canonical history through Market History, with existing gap/authority warnings retained.

### Unresolved authority stops

- USO D1: `CALENDAR_AUTHORITY_REQUIRED:REGISTRY_D1_V1`.
- USO H1/M30/M5: `ENERGY_INTRADAY_EXCLUDES_ETF`.
- USOIL D1: no usable evidence, provider mapping required, and approved D1 calendar required.
- USOIL H1/M30/M5: `PROVIDER_MAPPING_REQUIRED`.
- DJI D1: `CALENDAR_AUTHORITY_REQUIRED:REGISTRY_D1_V1`.
- DJI H1/M30/M5: `PROVIDER_MAPPING_REQUIRED` (an index calculation/publication profile is also required after mapping).
- SPY D1: `CALENDAR_AUTHORITY_REQUIRED:REGISTRY_D1_V1`.
- SPY H1/M30/M5: `INDICES_INTRADAY_EXCLUDES_ETF`.

The ETF registrations were not silently treated as Energy references or calculated indices. `REGISTRY_D1_V1` was not converted into a fabricated market calendar. The blocked lanes remain independent and do not affect BTCUSD or existing canonical rows.

### Verification artifacts

- [Pre-expansion audit](pre-expansion-estate-audit.json)
- [Post-expansion audit](post-expansion-estate-audit.json)
- Focused commissioning, Crypto validation, manual ingestion, and Market History tests: passed.
- BTCUSD Market History D1/H1/M30/M5: available with factual authority/gap warnings.
- Energy and Indices Market History D1 smoke requests: correctly report unavailable because their placeholder calendar is not approved.

## Overall disposition

SPEC-025 is **not fully accepted**. Crypto timeframe completion succeeded. Energy and Indices require reviewed instrument representations, provider mappings, and instrument/region-specific calendar or calculation-window authorities before their remaining lanes can be commissioned without inventing facts. Import Activity also needs one recorded native success/failure UI journey to close its strict visual acceptance evidence.
