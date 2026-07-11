# SPEC-008A Schema Mapping Preflight

**Date:** 2026-07-11
**Specification:** `SPEC-008A_REGISTRATION_METADATA_AND_INTRADAY_EVIDENCE_LANE_FOUNDATION`
**Decision:** Incompatible within the authorised migration shape; stop before migration

## Runtime baseline

The runtime database contains exactly these nine application tables:

```text
bars
evidence_lanes
ingest_runs
instrument_registrations
lane_state
provenance
raw_blocks
rollup_state
schema_migrations
```

Migration history contains versions 1 through 5. Migration 4 created immutable D1 registration authority. Migration 5 created immutable registration-backed evidence lanes. Existing authority contains three registration rows and three D1 lane rows.

## Current authority keys and multiplicity

| Table | Current primary key | Material constraint |
|---|---|---|
| `instrument_registrations` | `(asset, timeframe)` | `timeframe='D1'`; one row per canonical asset; provider identity and checksum unique; immutable identity trigger; deletion prohibited |
| `evidence_lanes` | `(asset, timeframe)` | one row per asset/timeframe; registration reference fixed to D1; all updates and deletes prohibited |
| `provenance` | `provenance_event_id` | bar-evidence events only; every row requires an ingest run, raw block, and canonical bar FK |
| `ingest_runs` | `ingest_run_id` | ingestion lifecycle and outcome contract; not registration/lane authority |
| `lane_state` | `(asset, timeframe)` | mutable derived operational state, not immutable declaration authority |
| `raw_blocks` | `raw_block_id` | immutable source payloads; no structured registration/lane authority identity |
| `bars` | `(asset,timeframe,open_time_utc)` | canonical market evidence only |
| `rollup_state` | `(asset,source_timeframe,target_timeframe)` | derived rollup state only |
| `schema_migrations` | `version` | migration history only |

No existing table supplies an append-only parent key for registration revisions, provider mappings, lane declaration versions, rejected candidates, or supersession chains.

## Exact current columns

### `instrument_registrations`

```text
asset, timeframe, registration_contract, registration_contract_version,
instrument_family, local_symbol, aliases_json, display_name, instrument_type,
asset_class, representation_type, underlying_reference, contract_or_series,
semantic_equivalence, jurisdiction, trading_currency, exchange_name, exchange_mic,
provider_id, provider_contract, provider_symbol, provider_exchange,
provider_country, provider_instrument_type, provider_identity_key, calendar_id,
calendar_version, gap_doctrine_id, gap_doctrine_version, registration_status,
registered_at_utc, evidence_confirmed_at_utc, identity_json,
identity_checksum_sha256
```

### `evidence_lanes`

```text
asset, timeframe, registration_timeframe, lane_contract,
lane_contract_version, created_at_utc
```

## Section 7 semantic mapping

### Registration facts

| Semantic fact | Physical mapping or blocker |
|---|---|
| instrument registration ID | Existing `(asset,timeframe)` only; no version-stable surrogate ID. **BLOCKER for revision identity.** |
| canonical symbol | `instrument_registrations.asset` |
| controlled display name | `display_name` |
| market family | `asset_class` and `instrument_family`, with incomplete separation |
| instrument type / asset class | `instrument_type`, `asset_class` |
| base asset/security identity | Partial: `instrument_family`, `underlying_reference`; complete typed identity requires a new column/JSON payload |
| quote currency/denomination | `trading_currency` |
| canonical unit | Approved new column or controlled JSON payload is physically possible |
| security form, share class, identifiers, ratio | Approved new columns or controlled JSON payload are physically possible |
| benchmark/index/energy identity facts | Approved new columns or controlled JSON payload are physically possible |
| authority document ID | Approved new column is physically possible |
| registration status | Existing `registration_status` is evidence state only; reviewed/approved/rejected/superseded needs a new controlled field |
| effective range | Approved new columns are physically possible |
| supersedes registration ID | A new column can store a reference, but the current primary key prevents inserting another row for the same `(asset,timeframe)`. **BLOCKER.** |
| evidence checksum, approval timestamp/actor | Approved new columns are physically possible |

### Provider mapping facts

| Semantic fact | Physical mapping or blocker |
|---|---|
| one provider mapping | Existing provider columns cover part of one mapping |
| multiple mappings per registration | No child multiplicity exists. JSON on the registration row would require mutating immutable authority to attach/review/reject later mappings. **BLOCKER.** |
| mapping ID and exact lane binding | No independent mapping identity exists. A JSON array element cannot be protected by SQLite FK or bound exactly from a lane. **BLOCKER.** |
| source scope, unit, price/adjustment basis, entitlement | New columns/JSON can represent one snapshot but not append-only mapping revisions |
| mapping evidence checksum/reviewer/state/reasons | New columns/JSON can represent one snapshot but not multiple immutable reviewed mappings |

### Evidence-lane facts

| Semantic fact | Physical mapping or blocker |
|---|---|
| evidence lane ID | Existing `(asset,timeframe)` only; no declaration-version ID |
| registration identity/timeframe | Existing asset FK and `timeframe` |
| provider mapping identity | No independent mapping ID exists. **BLOCKER.** |
| provider contract/session/calendar/timestamp/unit/validator/authority/range states | Approved new columns are physically possible for one declaration snapshot |
| compatibility/activation/construction | Approved new columns are physically possible |
| declaration checksum/actor/time | Checksum/actor need new columns; time partially maps to `created_at_utc` |
| exact replay | Possible for one immutable row after adding a checksum |
| conflicting/rejected candidate retention | Current PK prevents a second row; current table forbids update. **BLOCKER.** |
| supersession | A reference column can be added, but the current PK prevents a new version for the same asset/timeframe. **BLOCKER.** |

## Constraints and indexes

- `instrument_registrations` has its primary-key index plus unique constraints on `(provider_identity_key,timeframe)` and `identity_checksum_sha256`.
- `evidence_lanes` has only its primary-key index.
- Registration identity fields are protected from update; only the evidence-status transition is permitted.
- Evidence lanes reject every update and delete.
- Canonical bars require an exact evidence-lane row.
- Historical migration checksums are verified and cannot be changed.

## Evaluated nine-table designs

### Add scalar/JSON columns to existing rows

This can represent one metadata snapshot but cannot satisfy append-only mapping attachment, registration revision, rejected declaration retention, or lane supersession. Updating a JSON array would mutate authority in place and cannot provide relational identity/FK enforcement for an exact provider mapping.

### Reuse `provenance` or `ingest_runs`

Rejected. Their accepted contracts and foreign keys describe bar ingestion. A registration or lane event without a canonical bar/raw block cannot be inserted, and redefining them would alter accepted provenance semantics.

### Reuse `lane_state`

Rejected. It is mutable operational state with the same identity-only key and cannot hold immutable declaration history or registration/provider-mapping authority.

### Rebuild either authority table with a versioned primary key

This would enable multiplicity but violates SPEC-008A Section 8.2, which prohibits changing existing primary keys. It would also require changing accepted foreign-key semantics and migration assumptions.

## Nine-table proof and decision

The exact nine-table count can be preserved mechanically by adding columns. It cannot be preserved **semantically while meeting every Section 7, 10, and 11 requirement** under the prohibition on changing primary keys.

At minimum, the model requires append-only multiplicity for:

1. registration revisions;
2. provider mappings and their review history;
3. lane declaration versions/rejections/supersession.

That multiplicity requires either new authority tables or version-bearing primary keys. Both are forbidden by the current specification.

Per Section 8.1, implementation stops and `SPEC-008A_NINE_TABLE_COMPATIBILITY_BLOCKER.md` is issued. No migration, provider-contract asset, service, CLI, native change, or runtime mutation is authorised after this failed persistence gate.

**Operations is King.**
