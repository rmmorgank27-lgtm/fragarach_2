# SPEC-006A Instrument Registration Authority — Implementation and Proof Report

**Report date:** 2026-07-11

**Implementation checkpoint:** `3537fdbd5f2c11b20f85d55d5bdc1cc149bd1073`

**Authority:** `data/runtime/spec002_real_evidence_acceptance.sqlite3`

## Outcome

SPEC-006A Revision 2 is implemented and proven. Migration 4 added the canonical `instrument_registrations` authority, backfilled the three accepted D1 lanes, changed the exact table boundary from seven to eight, moved provider/calendar/doctrine operational lookup to SQLite, and enforced registration before canonical evidence.

No canonical bar, raw block, provenance event, ingest run, lane fact, validation summary, or rollup state was rewritten. The migration ledger received only its authorized append-only version 4 row.

SPEC-006 remains paused until it begins again from a fresh compatibility gate. No AAPL work, discovery, US-equity calendar, Add Symbol UI, or new evidence was added.

## Preflight and restoration boundary

At checkpoint `342b652119656adadfa292dcd58a17fb14274f46`, all 75 Python tests, 10 Swift checks, native build, and app launch passed. The tracked tree was clean except intentional `data/`.

A verified pre-migration online backup was created outside Git:

```text
/Users/raymorgan/Documents/Fragarach II Backups/spec006a_pre_migration_20260711.sqlite3
```

| Fact | Value |
|---|---|
| Size | 31,293,440 bytes |
| SHA-256 | `1cc1e6531f0e9aef344bdc93bd638bc957b72901db7ef198cef1e5f078d10b8b` |
| Integrity | `ok` |
| Foreign-key violations | 0 |
| Tables | exact historical seven |
| Migrations | versions 1–3 verified |

Before real migration, the backup was restored through SQLite's online backup API to a separate temporary database. The restored target reproduced the seven tables, three migration identities, integrity, foreign keys, counts, and deterministic content hashes. After real migration, restoration was repeated independently and produced the same historical state without affecting the migrated authority.

## Migration 4

```text
Name: SPEC-006A instrument registration authority foundation amendment
SHA-256: 08dea76586be94049f8bd82272c84946ed2beaaafaf611bacaf3ad90b3e0c138
```

Migration 4 transactionally:

1. created the strict `instrument_registrations` table;
2. inserted the reviewed AUDUSD, XAUUSD, and BTCUSD manifest identities;
3. assigned evidence status from existing canonical evidence;
4. verified bar and lane coverage;
5. installed alias, identity, delete, status, and bar-registration triggers; and
6. appended its checksummed ledger row.

Injected interruption after migration statements proved rollback leaves no eighth table and retains migration version 3.

## Registration contract

`INSTRUMENT_REGISTRATION_V1` canonical JSON is sorted, compact UTF-8 with explicit nulls. It contains immutable canonical, family, alias, representation, provider, calendar, and Gap Doctrine identity and excludes timestamps and status. The stored checksum is SHA-256 over the exact JSON bytes.

Provider identity keys are canonical JSON arrays ordered by provider ID, exact provider symbol, provider exchange, provider instrument type, trading currency, and provider country. Nulls remain explicit.

The table enforces:

- unique `(asset,timeframe)`;
- unique `(provider_identity_key,timeframe)`;
- unique identity checksum;
- uppercase canonical/family/local codes and D1 only;
- controlled representations and `DISTINCT_INSTRUMENT` semantics;
- typed canonical aliases and normalized naming collision triggers;
- currency, MIC, version, JSON, timestamp, checksum, and status constraints;
- futures contract/series discrimination;
- immutable identity and registered-at time;
- delete prohibition; and
- one factual no-evidence to with-evidence transition that cannot regress.

Family membership never permits cross-representation evidence merge, repair, substitution, or equivalence.

## Backfilled authority

| Asset | Family/local | Representation | Venue | Provider symbol | Calendar | Status | Identity SHA-256 |
|---|---|---|---|---|---|---|---|
| AUDUSD | AUDUSD / AUDUSD | FX_SPOT_PAIR | OTC | `AUD/USD` | FX_D1_V1 | REGISTERED_WITH_EVIDENCE | `20c0355ae9ca4b6e1ffe6f24f5dc7920d036757e132c3e33e1648d5a86b7730f` |
| BTCUSD | BITCOIN / BTCUSD | CRYPTO_SPOT_PAIR | Coinbase Pro | `BTC/USD` | CRYPTO_D1_V1 | REGISTERED_WITH_EVIDENCE | `f3bbb3d7770a3ae0668d8b2a68e0e224df91123c4cff96e226e0223429a1042b` |
| XAUUSD | GOLD / XAUUSD | SPOT | OTC | `XAU/USD` | METALS_D1_V1 | REGISTERED_WITH_EVIDENCE | `f296a6ed305bc12146b6ed84a2fee22fcb70f1697889100c6ebaaa06074d136a` |

All aliases are `[]`, MIC/country/jurisdiction remain null where not evidenced, and each historical registration/evidence time is the earliest committed INSERT provenance timestamp for that lane.

Every distinct bar and lane-state identity has exactly one registration. No coverage gap or provider/canonical collision exists.

## Existing authority preservation

| Existing table | Rows before/after | Deterministic SHA-256 before/after |
|---|---:|---|
| `bars` | 33,551 | `da9997448ad426ef696144575e276d768dc560b454160934b713d51bb268a871` |
| `raw_blocks` | 6 | `8d86c9d41d7aa58b5fad6da29fcc39883dbe9d5b02363257e9e1ebdfc44ea012` |
| `provenance` | 81,419 | `eeedfc829a12e961ca2e0310cc012facda4e94518c44c8babfb11e6c0276e308` |
| `ingest_runs` | 14 | `8698b0aab536ba2631f5cbc1013597accc9ff0659ab632bcfad90caf8ea15fb7` |
| `lane_state` | 3 | `96629a43e2c3f26fb55d6b145da1949b9a14e96c159f0572dbc5d4a8f34807f1` |
| `rollup_state` | 0 | SHA-256 of empty content |

Every listed hash was identical before and after. `schema_migrations` changed only by the required version 4 append.

The three operator CSV hashes, sizes, modes, mtimes, and evidence bytes remained unchanged.

## Operational lookup and ingestion

- Twelve Data acquisition obtains provider identity and exact symbol from the registration row.
- The provider adapter configuration no longer contains per-symbol mappings.
- Calendar validation obtains calendar and Gap Doctrine assignment from the registration row.
- `symbol_calendars.v1.json` is explicitly historical-only and is not loaded by runtime validation.
- Manual ingestion rejects an unregistered lane before raw, run, provenance, bar, or lane mutation.
- The canonical pipeline advances first-evidence status inside the ingestion transaction and verifies the evidence/status invariant before commit.
- SQLite rejects bars for unregistered lanes independently of UI or adapter code.

The existing three lanes retain identical operational validation results.

## Direct runtime enforcement

Controlled rollback-only attempts against the migrated real authority produced:

```text
immutable identity update: rejected
registration delete: rejected
evidence-status regression: rejected
unregistered bar insertion: rejected
read-only registration update: rejected
```

No attempted proof mutation committed.

## Automated and native proof

```text
Ran 83 Python tests
OK

OperationsCoreChecks: 11 checks passed

swift build
Build complete

Fragarach II.app launch and migrated-authority read verified
```

The new coverage includes migration checksum/rollback, strict eight tables, old-schema rejection, deterministic canonical JSON, registration idempotence and collisions, alias enforcement, family identity, immutability/delete, status transition/regression, unregistered evidence, read-only enumeration, manual pre-evidence rejection, operational SQLite mapping, backup/restoration, and native compatibility.

Post-proof integrity returned `ok`, foreign keys returned no rows, all four migration checksums matched, and the application table set was exactly eight.

No secret entered registration data, logs, tests, reports, Git, or SQLite. No legacy Fragarach path was accessed. Nothing was pushed and no consumer migration occurred.

Fragarach II remains a **CANDIDATE AUTHORITY**. **Operations is King.**
