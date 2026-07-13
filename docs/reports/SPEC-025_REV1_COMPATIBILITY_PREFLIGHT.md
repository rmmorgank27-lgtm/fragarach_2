# SPEC-025 Revision 1 — Compatibility Preflight

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`  
**Inspected commit:** `3562e4dd91f91bfbee07504a89171d122cd6d53d` (`v1.0a`, `main`)  
**Date:** `2026-07-13`  
**Scope:** Read-only preflight and reporting  
**Result:** `CONDITIONALLY COMPATIBLE — IMPLEMENTATION NOT AUTHORISED`

## Executive finding

The v1.0a architecture can support H1, M30, and M5 without a parallel registration or evidence system. The accepted storage keys for evidence lanes, bars, provenance, and lane state are already timeframe-generic and bind back to one D1 canonical registration anchor.

Activation is nevertheless not a configuration-only change. D1 assumptions exist through acquisition, staging, validation, Truth, consumer service, lifecycle, and native operation planning. A forward-only migration is mandatory because the accepted validation-summary enforcement admits only D1 date-based summaries.

No new application table is required or recommended. One market-specific constitutional compatibility stop was found: the current Energy candidates do not represent the Version 1 `PROVIDER_DERIVED_REFERENCE` authorised by the Energy doctrine, and that controlled representation is absent from the registration schema. Energy must not be activated until a separate foundation amendment or an explicitly approved compatible representation decision resolves this.

The recommended first vertical slice is `AUDUSD / H1`, after migration and implementation authority are separately approved.

## 1. Confirmed architecture and persistence boundary

Read-only inspection of `data/runtime/spec002_real_evidence_acceptance.sqlite3` confirmed:

- migrations 1 through 7 are applied and match the current migration registry;
- `PRAGMA integrity_check` returns `ok`;
- `PRAGMA foreign_key_check` returns no rows;
- the current accepted application-table boundary is exactly 10 tables:
  - `schema_migrations`;
  - `ingest_runs`;
  - `raw_blocks`;
  - `bars`;
  - `provenance`;
  - `lane_state`;
  - `rollup_state`;
  - `instrument_registrations`;
  - `evidence_lanes`;
  - `authority_events`.

The effective persistence model is:

```text
instrument_registrations(asset, D1)
        ↓ foreign-key anchor
evidence_lanes(asset, D1|H1|M30|M5, registration_timeframe=D1)
        ↓ required by trigger
bars / provenance / lane_state(asset, timeframe)
        ↓
authority_events (immutable declarations and current-head reconstruction)
```

Important confirmed facts:

- `instrument_registrations` intentionally enforces `timeframe='D1'`.
- `evidence_lanes` already accepts arbitrary uppercase timeframes and requires a D1 registration anchor.
- `bars`, `provenance`, and `lane_state` already use Symbol × Timeframe keys.
- `bars_require_evidence_lane_insert/update` already replaces the old same-timeframe registration trigger. SPEC-025 must not recreate or duplicate registrations.
- `bars.close_time_utc` already exists and can hold the exact intraday interval end.
- no intraday evidence lanes or bars currently exist in the inspected authority.
- the ledger physically supports intraday lane events, but Python validation deliberately forbids declaring H1/M30/M5 as active.

The D1 read-only baseline checks remained operational:

- `AUDUSD / D1` Truth: score 92, GREEN, CAODT `2026-07-11T00:00:00+00:00`;
- Estate Truth: contract v1, 18 D1 lanes, 18 symbols, score 88, GREEN;
- SPEC-018 `AUDUSD / D1`: AVAILABLE, 14,263 bars, unchanged v1 response contract.

These observations are evidence for preflight only and do not redefine accepted D1 truth.

## 2. Exact affected boundaries

| Boundary | Current condition and required evolution | Exact surfaces |
|---|---|---|
| Canonical registration | Correctly remains D1-only. Intraday services incorrectly query registration using the requested timeframe. All lane reads must resolve `evidence_lanes.registration_timeframe` back to the D1 anchor. | `src/fragarach_ii/storage/registrations.py`, `src/fragarach_ii/ingestion/pipeline.py`, `src/fragarach_ii/market_discovery.py`, `src/fragarach_ii/providers/instrument_search.py`, `src/fragarach_ii/identity_resolver.py`, `src/fragarach_ii/retirement.py` |
| Discovery and policy | Discovery partially advertises four timeframes but conflates policy, registration, implementation compatibility, and provider capability. It supports intraday only for FX/Crypto heuristically and reports all provider mappings as D1-only elsewhere. Replace inference with one policy/capability projection. | `src/fragarach_ii/market_discovery.py`, `src/fragarach_ii/fx_orientation.py`, `src/fragarach_ii/market_registry.py`, `config/market_registry/registry.v1.json` and related registry/mapping assets |
| Evidence lane and bar enforcement | Generic physical storage is usable. The registered writer checks lifecycle and physical lane existence but not a deterministic current lane head with REQUIRED policy and ACTIVE authority. Evidence confirmation still looks for a registration at the evidence timeframe. | `src/fragarach_ii/storage/schema.py`, `src/fragarach_ii/storage/migrations.py`, `src/fragarach_ii/ingestion/pipeline.py`, `src/fragarach_ii/storage/registrations.py` |
| Authority ledger | `LANE_DECLARED` explicitly raises `INTRADAY_ACTIVATION_FORBIDDEN` unless state is DECLARED. Policy is not represented separately from lane lifecycle. Current-head queries vary by service and sometimes inspect only legacy-key payloads. | `src/fragarach_ii/storage/authority_ledger.py`, `src/fragarach_ii/commands/authority.py`, `src/fragarach_ii/retirement.py` |
| Twelve Data contracts | Checksummed D1/H1/M30/M5 authority assets exist with interval codes `1day`, `1h`, `30min`, `5min`, ceiling 4,000 and hard maximum 5,000. The runtime loader reads only `twelve_data_time_series_d1.v1.json`; the operational acquisition path does not consume the intraday authority assets. | `config/providers/authority/TWELVE_DATA_TIME_SERIES_{D1,H1,M30,M5}_V1.json`, `config/providers/twelve_data_time_series_d1.v1.json`, `src/fragarach_ii/providers/contracts.py`, `src/fragarach_ii/providers/config.py` |
| Acquisition and fallback | Twelve Data rejects non-D1; its adapter hardcodes `1day`, D1 source identity, D1 timestamps, and D1 verification lookup. Provider resolution ignores the command's timeframe and always calls D1. Yahoo is entirely D1 and must remain so. Intraday request sizing must count bars, chunk at the contract ceiling, use authority-specific timezone/bounds, and detect truncation. | `src/fragarach_ii/providers/twelve_data.py`, `src/fragarach_ii/providers/twelve_data_adapter.py`, `src/fragarach_ii/providers/resolution.py`, `src/fragarach_ii/providers/yahoo_finance.py`, `src/fragarach_ii/commands/acquire.py` |
| Row quarantine | Common CSV staging already quarantines row-level validation failures, but the Twelve Data adapter treats invalid timestamp, missing OHLC, and out-of-range observations as whole-payload failures; only structural OHLC errors are quarantined. Payload-level symbol/interval/schema failure should remain whole-payload; row-local failures must become retained row rejections. | `src/fragarach_ii/staging/contract.py`, `src/fragarach_ii/staging/csv_adapter.py`, `src/fragarach_ii/ingestion/validation.py`, `src/fragarach_ii/providers/twelve_data_adapter.py` |
| Timestamp normalization | The common parser can parse explicit UTC datetimes but rejects all non-D1 timeframes before parsing. Twelve Data intraday authority requires provider-local labels to be interpreted under the lane timezone, aligned locally, then converted to UTC with source text and mapping method retained. D1 date semantics must remain on the existing path. | `src/fragarach_ii/ingestion/validation.py`, `src/fragarach_ii/providers/twelve_data_adapter.py`, `src/fragarach_ii/staging/contract.py`, provenance construction in `src/fragarach_ii/ingestion/pipeline.py` |
| Calendar/session loading | Runtime calendars are D1 date sets only; the parser rejects any non-D1 calendar. Only FX, Metals, and Crypto D1 assets exist. There is no session-open/close, maintenance, publication window, DST interval grid, early-close, or effective-dated intraday profile model. | `src/fragarach_ii/calendars/models.py`, `src/fragarach_ii/calendars/registry.py`, `src/fragarach_ii/calendars/sessions.py`, `config/calendars/*`, `config/symbol_calendars.v1.json` |
| Alignment and closed bars | No runtime intraday alignment or latest-closed-interval validator exists. Current acquisition commits before post-ingest validation, so an open or misaligned intraday observation must be rejected during staging rather than discovered after immutable admission. `close_time_utc` must be populated for every intraday canonical row. | new timeframe-dispatched validation components under `src/fragarach_ii/validation/`, plus `twelve_data_adapter.py`, `ingestion/validation.py`, `ingestion/pipeline.py` |
| Gap, freshness, CAODT | The validator counts civil dates; the summary stores `latest_expected_session` as an ISO date. Truth freshness is a boolean date-presence test and CAODT is `max(open_time_utc)`. Intraday requires expected closed intervals, interval-level gaps, and CAODT from the latest accepted closed interval end. | `src/fragarach_ii/validation/d1_sessions.py`, `src/fragarach_ii/validation/gaps.py`, `src/fragarach_ii/validation/result.py`, `src/fragarach_ii/storage/validation_summary.py`, `src/fragarach_ii/truth_engine.py` |
| Truth and authority service | Truth and SPEC-009A both require a registration at `(symbol, requested_timeframe)`, which makes an otherwise valid intraday evidence lane appear unregistered. Ledger lookup only recognizes legacy-key lanes. D1 and intraday CAODT semantics need explicit dispatch. | `src/fragarach_ii/truth_engine.py`, `src/fragarach_ii/authority_service.py`, `src/fragarach_ii/commands/truth_state.py`, `src/fragarach_ii/commands/serve_authority.py` |
| Estate Truth | The join to the D1 anchor is already correct, but only lanes with bars are returned. There is no policy/capability projection for deferred, declared, active-no-evidence, or blocked lanes. Aggregation would therefore omit required failures and cannot exclude intentionally deferred Stock lanes by policy. | `src/fragarach_ii/estate_truth_service.py`, `src/fragarach_ii/commands/estate_truth.py` |
| SPEC-018 | Service has `SUPPORTED_TIMEFRAME='D1'`; registration and alias lookup use requested timeframe; the catalog filters D1 bars only. It lacks capability metadata and the approved new factual response states. | `src/fragarach_ii/external_consumer_service.py`, `src/fragarach_ii/commands/get_history.py`, `src/fragarach_ii/commands/list_histories.py`, `specs/operations/SPEC-018_EXTERNAL_CONSUMER_DATA_CONTRACT.md` |
| Lifecycle | Retirement impact derives lanes from registration rows, so it sees D1 only. Discovery retirement also hardcodes `['D1']`. Reactivation can preserve multiple lanes only if selection and current-head projection first become lane-based. | `src/fragarach_ii/retirement.py`, `src/fragarach_ii/commands/retire_instrument.py`, `Sources/FragarachII/Views/DiscoverMarketView.swift`, `Sources/FragarachII/Views/DataOperationsView.swift` |
| Native bridge | `OperationIntent.acquire` has no timeframe and `ProcessBridge` always emits `--timeframe D1`. Reviewed operation identity contains a timeframe but fetch discards it. | `Sources/OperationsCore/Models.swift`, `Sources/OperationsCore/ControlledInputs.swift`, `Sources/OperationsCore/ProcessBridge.swift`, `Sources/FragarachII/Stores/ConsoleStore.swift` |
| Native operations | Data Operations is registration-selected, therefore D1-selected; fetch intent, boundaries, copy, lane matrix, and fallback text are D1-specific. It needs a separately selected eligible timeframe supplied by backend capability. | `Sources/FragarachII/Views/DataOperationsView.swift`, `Sources/OperationsCore/DataOperationsSelection.swift`, `Sources/OperationsCore/SQLiteReadService.swift` |
| Native Truth/discovery | Truth Matrix can render multiple timeframe lanes, but there is no capability model for non-servable/deferred lanes. Search chooses the first matching lane rather than a deterministic preferred timeframe. Discovery's timeframe matrix is display-only. Legacy Lanes picker lists D1 only. Swift currently calculates market/subgroup summaries, which must not be extended for SPEC-025 capability or policy calculations. | `Sources/OperationsCore/Models.swift`, `Sources/OperationsCore/EstateHierarchy.swift`, `Sources/FragarachII/Views/TruthConsoleView.swift`, `TruthMatrixView.swift`, `TruthContextDetailView.swift`, `DiscoverMarketView.swift`, `LanesView.swift` |

## 3. Migration finding

### Required: forward-only Migration 8

Migration 8 is required, but it does not require a new table or column.

Reason: migration 3's `lane_state_validation_summary_insert/update` triggers accept exactly `fragarach_ii.lane_validation_summary.v1`, require exactly 23 D1-oriented keys, and require `latest_expected_session` to be a 10-character ISO date. An honest intraday summary needs an exact latest expected closed interval instant and interval-level counts. It cannot be stored without either misusing D1 fields or bypassing accepted enforcement.

The smallest migration proposal is:

1. keep all 10 tables and every existing row unchanged;
2. keep `validation_summary` in `lane_state`;
3. drop and recreate only the two validation-summary triggers;
4. continue accepting the exact v1 contract for existing D1 summaries;
5. additionally accept a checksummed `fragarach_ii.lane_validation_summary.v2` with:
   - Symbol × Timeframe identity;
   - calendar/session profile identity and checksums;
   - exact validation boundary instant;
   - expected, present, missing, and outside interval counts;
   - latest expected closed interval open and end instants;
   - latest expected closed interval presence;
   - material/non-material gap counts;
   - validator identity, result checksum, and observation instant;
6. add migration 8 to the migration runner and verification list without changing migrations 1–7;
7. prove atomic interruption rollback and exact v1 D1 readback.

No migration is required for:

- canonical registration anchoring;
- adding H1/M30/M5 evidence lanes;
- bar/provenance/lane-state primary keys;
- `close_time_utc`;
- authority-ledger events;
- capability policy, which should be a checksummed read model/configuration plus immutable lane authority events.

The registered writer, not a new table, should enforce `policy_state=REQUIRED`, current lane authority `ACTIVE_NO_EVIDENCE|ACTIVE`, compatible mapping/contract, and non-retired lifecycle before acquisition or ingestion. SQLite must continue enforcing physical evidence-lane existence.

Migration 8 requires a separate foundation amendment and explicit implementation approval before execution.

## 4. D1 non-regression risks

| Risk | Required guard |
|---|---|
| Reinterpreting D1 midnight UTC labels as physical interval opens | Keep the D1 adapter, parser, validator, summary v1, Truth CAODT, and provider request semantics on an explicit D1 dispatch path. No D1 row migration. |
| Looking up intraday mapping by mutating immutable D1 provider fields | Resolve timeframe provider contracts and mappings from immutable ledger authority; leave registration identity and D1 mapping fields unchanged. |
| Converting all summaries to v2 | Coexistence only: retain every accepted D1 v1 summary byte-for-byte. |
| Using intraday interval-end CAODT for D1 | Dispatch CAODT by timeframe contract; D1 retains accepted semantic date behaviour. |
| Changing existing SPEC-018 D1 output | Freeze the D1 v1 contract, ordering, values, ranges, statuses, and acceptance symbols. Add intraday capability through versioned output without changing the request shape. |
| Whole-payload quarantine regression | Preserve payload-fatal conditions while widening row-local rejection handling; run existing D1 fixture assertions unchanged. |
| Estate score changes merely because deferred lanes exist | Aggregate only REQUIRED lanes; `INTENTIONALLY_DEFERRED` Stock lanes remain outside Truth/failure denominators. |
| Lifecycle affecting only D1 after intraday exists | Derive lifecycle scope from evidence lanes/current authority heads, not registration rows. |
| Provider config dispatch accidentally changes D1 timezone/range behaviour | Retain the current D1 operational config as its own immutable branch; do not make a generic default silently replace it. |

Before each vertical slice, capture a deterministic D1 fingerprint containing registration checksums, D1 bar canonical rows, raw-block checksums, provenance identity/counts, lane summaries, Truth responses, Estate summary, and SPEC-018 acceptance responses. Compare it after the slice; any unexpected difference rejects the checkpoint.

## 5. Session and representation commissioning matrix

| Market | Commissionable representation/profile | Required session/alignment authority | Current readiness and stop condition |
|---|---|---|---|
| Forex | `FX_SPOT_PAIR` only | OTC 24×5, Sunday 17:00 to Friday 17:00 `America/New_York`; daily 17:00 owner; H1/M30/M5 interval-open UTC after local-grid validation; historical IANA DST | Authority documents and direct mapping registry exist. Runtime session profiles do not. `AUDUSD` is the best first representative. |
| Metals | registered spot precious-metal pair (`SPOT` / constitutional spot-metal identity) | OTC near-continuous 24×5 New York rollover; same interval families as FX but Metals-specific source scope, unit, price basis, and exception authority | `XAUUSD` and `XAGUSD` are candidate spot registrations. CFDs, futures, ETFs, trusts, and fixings are not the same profile and must not commission it. |
| Energy | `PROVIDER_DERIVED_REFERENCE` with explicit benchmark relationship, unit, source nature, price basis, mapping, and effective range | `ENERGY_REFERENCE_24X5_NEW_YORK_ROLLOVER_V1` and `ENERGY_REFERENCE_DAILY_SESSION_V1`; provider-specific maintenance/exception evidence | **Foundation stop.** Current `USO` is an ETF and `USOIL` is a CFD. Both are constitutionally different from the authorised provider-derived reference. The registration representation enum has no `PROVIDER_DERIVED_REFERENCE`. Do not activate Energy until amended/decided. |
| Indices | one exact `INDEX` calculated series per administrator/methodology/variant | Index-specific calculation calendar, publication timezone, calculation window, cadence, delay/publication state, holiday and shortened-window rules; no universal index session | `DJI` is unmapped and lacks the required registered administrator/methodology/profile facts. `SPY` is an ETF and cannot stand in for SPX. Twelve Data identity and index-level scope must be proven per series. Each distinct index profile is separately commissioned. |
| Crypto | `CRYPTO_SPOT_PAIR` or separately approved aggregate with explicit venue/aggregate scope | continuous UTC grid; H1 top of hour, M30 minute 00/30, M5 minute divisible by five; no weekend/DST closures | `BTCUSD` is the candidate, but its current registration says Coinbase Pro while discovery describes digital-asset venues. Provider venue-versus-aggregate scope must be resolved before lane declaration. |
| Stocks | existing D1 `COMMON_STOCK` profiles only | existing accepted D1 authority | H1/M30/M5 policy is `INTENTIONALLY_DEFERRED`; create no intraday lane, warning, Truth penalty, or acquisition action. Use AAPL to verify policy projection. |

Distinct representations listed in Discovery—CFD, ETF, futures, cash index, spot pair, and provider-derived reference—must never share commissioning merely because their display symbols are related.

## 6. Smallest ordered implementation plan

No step below is authorised by this preflight.

1. **Foundation checkpoint:** approve the Migration 8 amendment and the exact validation-summary v2 contract. Resolve whether Energy receives a new controlled representation through a separate foundation amendment; Energy remains stopped meanwhile.
2. **Read-model checkpoint:** implement one policy/capability projection separating `REQUIRED|INTENTIONALLY_DEFERRED|NOT_AUTHORISED` from lane authority state. Make registration-anchor, ledger current-head, lifecycle, mapping, entitlement, evidence, validation, and servability reads share it. Prove D1 parity before acquisition changes.
3. **Generic service checkpoint:** add timeframe dispatch to provider config, acquisition command, staging, validation interface, Truth, Estate Truth, SPEC-018, lifecycle, Swift models, and bridge without activating a lane. Keep Yahoo D1-only and expose `NO_APPROVED_FALLBACK` for intraday.
4. **Forex H1 pilot:** commission `AUDUSD / H1` end to end in the signed application; then commission the reviewed Forex H1 cohort.
5. **Forex M30 pilot and cohort:** repeat the full gate for `AUDUSD / M30`, then the reviewed cohort.
6. **Forex M5 pilot and cohort:** repeat for `AUDUSD / M5`; do not derive it from higher timeframes.
7. **Metals:** repeat H1 → M30 → M5, beginning with one reviewed spot pair such as `XAUUSD`; keep CFD/futures/ETF representations out.
8. **Energy:** proceed only after the reported foundation/identity stop is resolved; commission one provider-derived reference H1 → M30 → M5.
9. **Indices:** commission one exact calculated-index profile H1 → M30 → M5, then each additional distinct profile independently.
10. **Crypto:** resolve BTCUSD venue/aggregate scope, then commission H1 → M30 → M5 on the continuous UTC profile.
11. **Stocks policy proof:** verify D1 remains active and intraday remains intentionally deferred and non-penalising.
12. **Consumer release gate:** only after signed-native acceptance and SPEC-018 evidence may paused consumer integration resume.

## 7. Focused verification per vertical slice

Every pilot slice must prove:

1. exact policy, lane head, provider mapping, contract, entitlement, session profile, and effective range;
2. request interval, timezone, bounds, chunk size, overlap, sorting, and truncation detection;
3. one valid payload plus deterministic mixed-row replay covering invalid OHLC, missing fields, misalignment, outside range/session, duplicate conflict, and an incomplete current interval;
4. immutable raw bytes/checksum, exact source-row provenance, row-level quarantine, idempotent retry, and affected-lane-only failure;
5. canonical UTC interval-open plus exact interval end, with no silent realignment or synthetic bar;
6. normal session, weekend/closure, DST boundary, exception/early-close where applicable, interval gaps, latest expected closed interval, freshness, and CAODT;
7. independent Truth for the new lane and unchanged Truth for D1 and unrelated lanes;
8. Estate capability and aggregation, including no Stock deferred penalty;
9. SPEC-018 catalog discovery and exact history response, with no fabricated unavailable bars;
10. native selection, acquisition/refresh, validation, Truth refresh, lifecycle preservation, search, and readable failure reasons;
11. pre/post deterministic D1 fingerprint equality;
12. focused Python tests, OperationsCore checks, focused Swift UI tests, one release-style build, and one signed launch only when implementation and build are later authorised.

Affected test suites to extend, not replace:

- `tests/storage/test_foundation.py`;
- `tests/storage/test_evidence_lane_foundation.py`;
- `tests/storage/test_lane_validation_summary_amendment.py`;
- `tests/storage/test_authority_ledger_amendment.py`;
- `tests/ingestion/test_csv_staging.py` and `test_manual_ingestion.py`;
- `tests/providers/test_twelve_data.py` and `test_provider_resolution.py`;
- `tests/validation/test_d1_session_validation.py` plus new timeframe/session-profile tests;
- `tests/operations/test_truth_engine.py`, `test_estate_truth_service.py`, `test_authority_service.py`, `test_external_consumer_service.py`, `test_market_discovery.py`, `test_retirement.py`, and `test_zero_blocking.py`;
- `Sources/OperationsCoreChecks/main.swift` plus focused native UI tests.

## 8. Blockers and operator decisions

1. **Migration 8 approval required.** It is mandatory for honest intraday validation persistence and must be specified as a foundation amendment before execution.
2. **Energy foundation decision required.** Approve a `PROVIDER_DERIVED_REFERENCE` registration representation and migration, or explicitly authorize another constitutionally accurate encoding. Reusing ETF, CFD, spot, or futures identity is forbidden.
3. **Capability contract approval required.** Approve the checksummed market-policy source and exact per-timeframe projection schema. Policy must not be inferred from bars or authority-document presence.
4. **SPEC-018 version decision required.** Recommended: preserve D1 history response v1 exactly; introduce capability catalog v2 and intraday/unavailable-state response v2 selected by requested timeframe, without changing `get_history(symbol,timeframe)`.
5. **Index pilot identity required.** Select one exact calculated index and approve administrator, official variant, methodology, calendar, publication window/timezone/state, provider mapping, and effective range. DJI is not ready merely because the provider knows the string `DJI`.
6. **Crypto scope decision required.** Resolve whether Twelve Data BTC/USD is Coinbase Pro, another venue, or an aggregate; bind the exact scope before activation.
7. **Entitlement evidence required per timeframe.** Existing `NOT_MEASURED`/unknown facts cannot be promoted by inference. Intraday may operate without fallback only when primary entitlement is proven; Yahoo remains D1-only.
8. **Native summary ownership repair required in scope.** Swift currently calculates market/subgroup summaries in `EstateHierarchy.swift`. SPEC-025 must consume backend projections for any new policy/capability and scorecard values; it must not expand UI calculation.

No constitutional incompatibility blocks the recommended Forex H1 pilot once Migration 8, capability contracts, and implementation are separately approved. The Energy incompatibility is an affected-market stop under Zero Blocking, not authority to bypass the market order silently.

## 9. Recommended first vertical slice

```text
AUDUSD / H1
```

Rationale:

- accepted D1 canonical identity, evidence, Truth, and SPEC-018 baseline already exist;
- direct Twelve Data `AUD/USD` mapping is recorded;
- FX H1 constitutional authority and provider contract exist;
- the 17:00 New York rollover profile exercises local-to-UTC mapping, weekend ownership, DST, closed-bar logic, gaps, freshness, and CAODT—the core hard problems that M30 and M5 reuse;
- failure is isolated from Metals, Energy, Indices, Crypto, Stocks, and all D1 lanes.

The slice must begin with a short bounded historical window containing ordinary sessions and a New York DST boundary in deterministic replay, followed by one genuine operator acquisition only during later signed-native acceptance. It must not begin until the operator authorises functional implementation and Migration 8.

## Preflight disposition

```text
Compatibility preflight: COMPLETE
Functional implementation: NOT AUTHORISED
Database migration: REQUIRED BUT NOT AUTHORISED
Database modified: NO
Application rebuilt or launched: NO
Provider acquisition performed: NO
Consumer integration resumed: NO
Commit/tag/push: NO
```
