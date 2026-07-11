# SPEC-006 Symbol Registration — Compatibility Gate Report

**Report date:** 2026-07-11

**Gate commit:** `24cbce95f267b2579082fe50267c5bb57482096e`

**Outcome:** Blocked; Foundation amendment required

## Decision

The current seven-table authority cannot truthfully and durably represent a registered instrument identity. SPEC-006 must stop before discovery, AAPL configuration, registration, calendar implementation, acquisition, UI work, or database mutation.

The authority stores canonical bar identity and lane restart state, but it has no durable location for display name, instrument/asset class, jurisdiction, currency, exchange/MIC, provider identity and exact symbol, registration contract, assigned calendar and Gap Doctrine, registration state/timestamp, or canonical registration checksum.

Encoding those facts into `lane_state.validation_summary`, `ingest_runs.detail`, raw evidence, provenance, rollup state, `UserDefaults`, or tracked/untracked configuration would violate their existing contracts and create competing authority. Creating an empty lane row alone would not identify what was registered and would not enforce provider or canonical-asset collisions.

The required next work is a separately authorized Foundation amendment:

> **SPEC-006A — Instrument Registration Authority Foundation Amendment**

SPEC-006 remains paused until SPEC-006A is specified, implemented, proven, reported, and locally checkpointed. A fresh compatibility gate is required afterward.

## Baseline proof

The complete accepted baseline passed before any tracked or database change:

```text
Ran 75 Python tests
OK

OperationsCoreChecks: 10 checks passed

swift build
Build complete

Fragarach II.app process launch verified
```

Tracked Git state was clean except the intentionally untracked operator `data/` directory.

The acceptance authority passed integrity, foreign keys, all three migration checksums, WAL/read-only use, and the exact seven-table boundary.

| Authority content | Rows | Deterministic SHA-256 |
|---|---:|---|
| Canonical bars | 33,551 | `da9997448ad426ef696144575e276d768dc560b454160934b713d51bb268a871` |
| Raw blocks | 6 | `40d09aef164cafd5e848fc3d25e1010c0af6370f26a0d6a855615be6f9d84289` |
| Provenance events | 81,419 | `eeedfc829a12e961ca2e0310cc012facda4e94518c44c8babfb11e6c0276e308` |
| Ingest runs | 14 | `8698b0aab536ba2631f5cbc1013597accc9ff0659ab632bcfad90caf8ea15fb7` |
| Lane state | 3 | `96629a43e2c3f26fb55d6b145da1949b9a14e96c159f0572dbc5d4a8f34807f1` |

Database facts:

```text
Size: 31,293,440 bytes
SHA-256: c8027aaaa124d05aaf7e4affe3ae9bc9fdf9bc6c3c76f960bbcee116c952c73e
Integrity: ok
Foreign-key violations: 0
```

Migration checksums remained:

```text
1  88eba3e38ca6e013efcd1b545c49554f4b4be5a12a87a1daeb9bc650ebf65393
2  76c22b13fdd2941efbd86d75f71b42d24d34e9c2896d6308c66f70ed8bdfdb46
3  13b64f4e72b8c9897d616936cdb5cd526e9cbfbbbaf59cc01752973834594b39
```

## Existing identity locations

### SQLite

- `bars` knows only `(asset, timeframe, open_time_utc)` plus evidence values and run references.
- `lane_state` knows only `(asset, timeframe)`, high watermark, version, last run, update time, and nullable validation summary.
- `validation_summary` contains facts produced by a completed calendar comparison. It cannot represent a registration before evidence and its enforced JSON contract does not include instrument or provider identity.
- `ingest_runs`, `raw_blocks`, and `provenance` describe evidence operations. Using them would require a fake ingestion event or unrelated JSON detail.
- `rollup_state` is reserved exclusively for rollup restart state.

No database constraint currently rejects two conflicting real-world identities that share a ticker, or one provider identity mapped to two canonical assets.

### Tracked configuration

- `config/providers/twelve_data_time_series_d1.v1.json` defines the three authorized provider-symbol mappings.
- `config/symbol_calendars.v1.json` assigns the three current assets to calendars.
- `config/calendars/*.json` and `calendar_registry.v1.json` define available versioned calendars.
- `config/gap_doctrine.v1.json` defines the single current Gap Doctrine.

These files are versioned doctrine and initial configuration, not an operational registration authority. Editing them during app operation is explicitly forbidden by SPEC-006.

### Native application

The app reads `lane_state` and bars. Its asset selectors are currently explicit fixed choices. `UserDefaults` persists paths and presentation choices only and is prohibited from holding registration truth.

## Smallest safe Foundation amendment

SPEC-006A should authorize one dedicated canonical table, tentatively `instrument_registrations`, and increase the exact application-table boundary from seven to eight. Adding a nullable JSON field to `lane_state` is smaller mechanically but not semantically safe: it would combine instrument authority with per-lane restart/validation state and make instrument identity dependent on a timeframe row.

The new table should contain typed, constrained fields for:

- registration contract and version;
- canonical asset code and D1 timeframe;
- display name, instrument type, and asset class;
- country/jurisdiction and trading currency;
- exchange name and nullable MIC;
- provider, provider discovery/identity contract, and exact provider symbol;
- provider exchange/country/type identifiers needed for disambiguation;
- calendar identity/version and Gap Doctrine identity/version;
- factual registration status;
- registered-at UTC timestamp; and
- deterministic canonical registration checksum.

At minimum it needs:

- primary uniqueness for canonical `(asset, timeframe)`;
- unique provider identity across provider, exact symbol, exchange/MIC, type, and currency as defined by the registration contract;
- database checks for uppercase canonical codes, supported D1 timeframe, non-empty material identity, version bounds, checksum form, and factual status;
- immutable identity columns after insert;
- a narrowly authorized status transition from `REGISTERED_NO_EVIDENCE` to `REGISTERED_WITH_EVIDENCE` only after canonical evidence exists;
- update/delete triggers preventing rename, remap, deletion, or silent reinterpretation;
- backfilled registrations for AUDUSD, XAUUSD, and BTCUSD with deterministic checksums;
- registered-writer locking and one atomic registration transaction;
- database-level rejection of bars for an unregistered `(asset, timeframe)`, after safe backfill, so UI/API checks are not the sole enforcement;
- migration checksum, interruption recovery, online backup/restore proof, read-only proof, exact eight-table verification, collision tests, and preservation hashes for all current evidence/history.

SPEC-006A must define whether registration status is stored or deterministically derived. If stored as required by SPEC-006, its transition must be factual and must not permit identity edits.

No provider mapping should remain an operational authority in tracked configuration after migration. Static configuration may continue to define the provider contract itself, while lookup for registered assets must come from the new canonical table.

## Calendar compatibility

The existing calendar model can represent `US_EQUITY_D1_V1` without a schema amendment by using:

- `America/New_York` as the timezone basis;
- Monday through Friday expected weekdays;
- explicit versioned `CLOSED_OVERRIDE` dates for every supported full-day holiday and exceptional closure; and
- ordinary expected weekdays for half-days.

This requires a complete, checksummed local closure definition and tests for the declared effective range. It must not use weekday-only inference. This work remains within paused SPEC-006 and must not begin before SPEC-006A completes and the fresh gate passes.

## Unchanged boundary

No tracked implementation file, authority record, configuration, calendar, provider mapping, app UI, or secret was changed during the gate. No legacy Fragarach location was accessed. No discovery or live provider request was made.

Fragarach II remains a **CANDIDATE AUTHORITY**. No consumer migration is authorized. **Operations is King.**
