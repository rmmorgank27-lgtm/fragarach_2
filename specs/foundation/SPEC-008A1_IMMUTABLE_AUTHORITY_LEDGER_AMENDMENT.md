# SPEC-008A1 — Immutable Authority Ledger Amendment

**Document ID:** `SPEC-008A1_IMMUTABLE_AUTHORITY_LEDGER_AMENDMENT`
**Repository:** `/Users/raymorgan/VSC/Fragarach_2`
**Date:** `2026-07-11`
**Status:** `DRAFT FOR OPERATOR APPROVAL`
**Classification:** `Foundation Implementation Specification Amendment`
**Authority State:** `CANDIDATE AUTHORITY`
**Doctrine:** `Operations is King`
**Push:** `FORBIDDEN`

---

# 1. Executive Decision

This amendment resolves the persistence incompatibility recorded in:

```text
docs/reports/SPEC-008A_SCHEMA_MAPPING_PREFLIGHT.md
docs/reports/SPEC-008A_NINE_TABLE_COMPATIBILITY_BLOCKER.md
```

The exact nine-application-table boundary is superseded by:

```text
Application tables = exactly 10
```

The sole authorised new application table is:

```text
authority_events
```

`authority_events` is a generic, append-only, immutable authority ledger. It supplies versioned multiplicity for registration declarations, provider mappings, evidence-lane declarations, compatibility findings, entitlement changes, effective-range changes, authority bindings, rejections, conflicts, and supersession without modifying accepted authority rows in place.

No other new table is authorised.

This amendment does not implement the ledger. Implementation begins only after operator approval of this specification.

---

# 2. Governing Authority

Implementation MUST conform to:

```text
constitution/CONSTITUTION.md
constitution/CONSTITUTIONAL_AUTHORITY_MANIFEST_V1.md
constitution/doctrines/*.md
constitution/authorities/*/*_AUTHORITY_V1.md
```

It also inherits and preserves SPEC-001 through SPEC-007 and amends only the persistence boundary that blocked SPEC-008A.

The governing constitutional rules include:

- authority ownership and non-invention;
- affected-path-only compatibility stopping;
- immutable evidence and visible supersession;
- Instrument Registration → Evidence Lane Authority → Evidence order;
- deterministic identity and interpretation;
- effective dating;
- immutable prior versions;
- preservation of accepted evidence and Current-As-Of Truth;
- non-blocking operation;
- prohibition on secret disclosure.

This specification defines storage mechanics. It does not create market, instrument, provider, venue, session, unit, adjustment, calendar, timestamp, index-variant, contract-roll, validation, or effective-range truth.

---

# 3. Amendment Relationship

SPEC-008A remains the governing implementation specification for registration metadata, provider mappings, generic D1/H1/M30/M5 lane declaration, provider-contract assets, compatibility gates, CLI/service operations, read-only inspection, and native presentation.

SPEC-008A1 supersedes only these SPEC-008A rules:

```text
Application tables = exactly 9
No new database tables
```

They become:

```text
Application tables = exactly 10
Exactly one new table: authority_events
No other new table
```

Where SPEC-008A proposes adding mutable metadata to an existing authority row, this amendment controls: new or changed authority facts MUST be appended as immutable ledger events. Existing rows MUST NOT be updated in place to solve metadata, revision, mapping, conflict, entitlement, effective-range, or supersession requirements.

All other SPEC-008A scope exclusions remain in force, including no Stage A acquisition, intraday bar ingestion, validation, replay acquisition, overlap acquisition, backfill, derived construction, Stage B work, provider-plan upgrade, constitutional amendment, or push.

---

# 4. Absolute Invariants

Implementation MUST preserve:

1. all existing nine tables, names, columns, primary keys, constraints, and accepted semantics;
2. all existing instrument-registration rows and identity checksums;
3. all existing evidence-lane rows;
4. every accepted D1 bar value, raw block, provenance event, ingest run, lane state, and validation summary;
5. all five existing migration names, executable statements, and SHA-256 checksums;
6. existing D1 acquisition, ingestion, validation, read-only access, Current-As-Of, and native behavior;
7. registered-writer and single-writer discipline;
8. affected-path-only stopping and unrelated-lane availability;
9. established secure credential loading and non-disclosure rules;
10. rollback by restoration, not destructive reverse migration.

Implementation MUST NOT:

- add an eleventh application table;
- add specialist tables for registrations, mappings, lanes, revisions, conflicts, entitlements, ranges, or bindings;
- change an existing primary key;
- update an existing registration or evidence-lane row to append authority;
- rewrite, delete, compact, or squash a ledger event;
- infer missing authority while constructing an event;
- treat ledger insertion time as the effective time of a fact;
- relabel a venue-specific BTC/USD mapping as an aggregate;
- substitute a proxy for an unresolved index or instrument;
- hide rejected, conflicting, superseded, unresolved, or expired authority;
- make a blocked entity prevent unrelated reads or declarations;
- print, log, persist, or commit credentials;
- push.

---

# 5. Exact Table Purpose

`authority_events` is the single append-only journal of versioned operational authority introduced by SPEC-008A and this amendment.

It MAY record:

- instrument-registration declarations and revisions;
- provider-mapping discovery, review, approval, rejection, and supersession;
- multiple provider mappings belonging to one registration;
- evidence-lane candidates, declarations, revisions, rejection, conflict, and supersession;
- entitlement-state changes;
- effective-range declarations and changes;
- authority-document bindings and changes;
- compatibility findings and their resolution or supersession;
- immutable bindings from ledger entities to legacy registration and lane rows.

It MUST NOT record:

- market bars or derived bars;
- raw provider payload bytes;
- bar-level provenance or merge actions;
- mutable lane high-water marks;
- authentication material;
- UI state, caches, or maintenance convenience state;
- facts owned by constitutional documents unless the payload binds to the owning document rather than redefining it.

The table is a ledger, not a mutable current-state table. Current authority is reconstructed as a deterministic read model from immutable events.

---

# 6. Exact Physical Schema

Migration 6 SHALL create exactly this semantic column set. SQL formatting may follow repository house style, but names, meanings, nullability, and constraints are normative.

```sql
CREATE TABLE authority_events (
    authority_event_id TEXT PRIMARY KEY,
    ledger_contract TEXT NOT NULL,
    ledger_contract_version INTEGER NOT NULL,
    entity_kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    supersedes_event_id TEXT,
    effective_from_utc TEXT NOT NULL,
    effective_to_utc TEXT,
    canonical_payload TEXT NOT NULL,
    payload_checksum_sha256 TEXT NOT NULL,
    event_checksum_sha256 TEXT NOT NULL,
    recorded_at_utc TEXT NOT NULL,
    recorded_by TEXT NOT NULL,
    FOREIGN KEY (supersedes_event_id)
        REFERENCES authority_events(authority_event_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    UNIQUE (event_checksum_sha256),
    CHECK (length(authority_event_id)=64
           AND authority_event_id NOT GLOB '*[^0-9a-f]*'),
    CHECK (ledger_contract='AUTHORITY_EVENT_LEDGER_V1'
           AND ledger_contract_version=1),
    CHECK (entity_kind IN (
        'INSTRUMENT_REGISTRATION',
        'PROVIDER_MAPPING',
        'EVIDENCE_LANE'
    )),
    CHECK (length(entity_id)>0 AND entity_id=trim(entity_id)),
    CHECK (event_kind IN (
        'LEGACY_REGISTRATION_BOUND',
        'REGISTRATION_DECLARED',
        'REGISTRATION_REVISED',
        'REGISTRATION_REJECTED',
        'REGISTRATION_SUPERSEDED',
        'PROVIDER_MAPPING_DISCOVERED',
        'PROVIDER_MAPPING_REVIEWED',
        'PROVIDER_MAPPING_APPROVED',
        'PROVIDER_MAPPING_REJECTED',
        'PROVIDER_MAPPING_SUPERSEDED',
        'LEGACY_LANE_BOUND',
        'LANE_CANDIDATE_RETAINED',
        'LANE_DECLARED',
        'LANE_REVISED',
        'LANE_REJECTED',
        'LANE_SUPERSEDED',
        'ENTITLEMENT_CHANGED',
        'EFFECTIVE_RANGE_CHANGED',
        'AUTHORITY_BINDING_CHANGED',
        'COMPATIBILITY_FINDING_RECORDED',
        'COMPATIBILITY_FINDING_SUPERSEDED'
    )),
    CHECK (supersedes_event_id IS NULL
           OR supersedes_event_id<>authority_event_id),
    CHECK (effective_from_utc=trim(effective_from_utc)
           AND julianday(effective_from_utc) IS NOT NULL
           AND substr(effective_from_utc,-6)='+00:00'),
    CHECK (effective_to_utc IS NULL OR (
        effective_to_utc=trim(effective_to_utc)
        AND julianday(effective_to_utc) IS NOT NULL
        AND substr(effective_to_utc,-6)='+00:00'
        AND julianday(effective_to_utc)>julianday(effective_from_utc)
    )),
    CHECK (json_valid(canonical_payload)
           AND json_type(canonical_payload)='object'),
    CHECK (length(payload_checksum_sha256)=64
           AND payload_checksum_sha256 NOT GLOB '*[^0-9a-f]*'),
    CHECK (length(event_checksum_sha256)=64
           AND event_checksum_sha256 NOT GLOB '*[^0-9a-f]*'),
    CHECK (length(recorded_by)>0 AND recorded_by=trim(recorded_by)),
    CHECK (recorded_at_utc=trim(recorded_at_utc)
           AND julianday(recorded_at_utc) IS NOT NULL
           AND substr(recorded_at_utc,-6)='+00:00')
) STRICT;
```

`authority_event_id` SHALL equal `event_checksum_sha256`. A trigger SHALL reject an insert when they differ.

SQLite cannot independently recompute SHA-256. The registered Python writer SHALL recompute both checksums before insert and immediately after readback. Tests SHALL prove that arbitrary SQL cannot admit malformed checksum grammar and that the registered service rejects checksum-content mismatch.

---

# 7. Entity Identity

## 7.1 Instrument Registration

`entity_kind = INSTRUMENT_REGISTRATION`.

`entity_id` is a stable, controlled registration-ledger identifier. It is not a display symbol and MUST NOT be derived from provider symbol text alone.

For an existing registration, its first `LEGACY_REGISTRATION_BOUND` payload SHALL bind the stable ledger identity to the exact legacy key:

```json
{"asset":"AUDUSD","registration_timeframe":"D1"}
```

For a new registration, `REGISTRATION_DECLARED` establishes the identity. Revisions retain the same `entity_id` and supersede the preceding registration head.

## 7.2 Provider Mapping

`entity_kind = PROVIDER_MAPPING`.

Each mapping receives its own stable `entity_id`. The canonical payload MUST contain `instrument_registration_entity_id`. Multiple mapping entity IDs MAY reference the same registration. A mapping is never an alias and never changes canonical instrument identity.

## 7.3 Evidence Lane

`entity_kind = EVIDENCE_LANE`.

Each lane identity is stable across revisions and MUST bind one registration entity, one timeframe, one provider-mapping entity, one source scope, and all authority required by SPEC-008A.

An existing lane is introduced to the ledger through `LEGACY_LANE_BOUND`, binding its ledger identity to the exact legacy `(asset,timeframe)` key without rewriting the legacy row.

---

# 8. Event-Kind Semantics

## 8.1 Registration Events

- `LEGACY_REGISTRATION_BOUND`: exact immutable bridge to an existing registration row. Unknown new metadata remains explicit `UNRESOLVED`.
- `REGISTRATION_DECLARED`: first complete declaration for a new registration-ledger identity.
- `REGISTRATION_REVISED`: approved replacement metadata for the same identity; MUST supersede the current compatible registration head.
- `REGISTRATION_REJECTED`: retains a rejected registration candidate or revision; MUST NOT become current approved authority.
- `REGISTRATION_SUPERSEDED`: closes a registration authority segment and points to the superseded head and replacement identity/event where applicable.

## 8.2 Provider-Mapping Events

- `PROVIDER_MAPPING_DISCOVERED`: immutable provider reference result; state is `DISCOVERED` only.
- `PROVIDER_MAPPING_REVIEWED`: operator-reviewed mapping, including exact unresolved facts and evidence checksum.
- `PROVIDER_MAPPING_APPROVED`: explicit approval; discovery or review alone MUST NOT produce it.
- `PROVIDER_MAPPING_REJECTED`: retained rejected or incompatible mapping and exact reason codes.
- `PROVIDER_MAPPING_SUPERSEDED`: closes one mapping segment without deleting prior mapping history.

## 8.3 Evidence-Lane Events

- `LEGACY_LANE_BOUND`: bridge to an accepted existing lane and its readable D1 evidence.
- `LANE_CANDIDATE_RETAINED`: preserves a reviewed candidate, including incomplete or conflicting candidates, without declaration.
- `LANE_DECLARED`: declares a complete compatible lane. Under SPEC-008A, a new intraday lane may be `DECLARED` but not `ACTIVE`.
- `LANE_REVISED`: approved replacement declaration for the same lane identity.
- `LANE_REJECTED`: retains a rejected candidate/declaration and exact compatibility reasons.
- `LANE_SUPERSEDED`: closes the superseded lane segment while leaving history and evidence readable.

## 8.4 Cross-Cutting Events

- `ENTITLEMENT_CHANGED`: immutable transition in entitlement state for a provider mapping or lane.
- `EFFECTIVE_RANGE_CHANGED`: immutable effective-range segment change; prior ranges remain queryable.
- `AUTHORITY_BINDING_CHANGED`: immutable change to constitutional or subordinate authority-document bindings.
- `COMPATIBILITY_FINDING_RECORDED`: affected-path finding with exact field, authority, supplied value, required state, consequence, and owner decision.
- `COMPATIBILITY_FINDING_SUPERSEDED`: resolves or replaces a prior finding without deleting it.

Every event kind SHALL be legal only for an explicitly enumerated entity kind. The registered writer and insert-validation trigger SHALL enforce the event-kind/entity-kind matrix. Cross-cutting events are legal only where their canonical schema defines relevance.

---

# 9. Canonical Payload Contract

## 9.1 Common Envelope Payload Fields

Every `canonical_payload` MUST contain exactly these common fields plus the event-kind-specific body:

```text
format
entity_kind
entity_id
event_kind
authority_bindings
compatibility_state
compatibility_reasons
body
```

The common `format` is:

```text
fragarach_ii.authority_event_payload.v1
```

`authority_bindings` is a sorted array of objects containing exact document ID, version, repository path, and SHA-256. It MUST include the applicable Constitution, Base Doctrine, Timeframe Authority where applicable, and owning registration/provider/calendar/session/validator authority referenced by the event.

`compatibility_reasons` is a deterministically sorted array. An empty array is valid only when compatibility is explicitly `COMPATIBLE`.

## 9.2 Canonical JSON Rules

Canonical payload bytes SHALL be:

- UTF-8;
- one JSON object;
- lexicographically key-sorted at every object depth;
- compact, with separators `,` and `:` and no insignificant whitespace;
- encoded without ASCII escaping except where JSON requires escaping;
- explicit about `null` and controlled `NOT_APPLICABLE`/`UNRESOLVED` values;
- free of floating-point numbers; exact decimals are strings and counts/versions are integers;
- free of duplicate object keys;
- deterministic in arrays whose semantics are sets: those arrays SHALL use contract-defined sort keys;
- prohibited from containing credentials, tokens, raw secret-bearing headers, or unbounded provider response bodies.

Empty strings MUST NOT mean unknown or not applicable.

## 9.3 Event-Specific Bodies

Registration bodies SHALL support every SPEC-008A Section 7.1 fact.

Provider-mapping bodies SHALL support every SPEC-008A Section 7.2 fact and MUST include the owning registration entity ID, provider identity key, source-scope kind/identifier, reference-evidence checksum, mapping state, review/approval actor, and effective boundaries.

Lane bodies SHALL support every SPEC-008A Section 7.3 fact and MUST include registration entity ID, provider-mapping entity ID, timeframe, provider contract, source scope, venue/MIC, session, calendar, timestamp meaning, timezone, units, normalization, price/adjustment basis, validator, authority documents, ranges, entitlement, compatibility, activation, and construction method.

Event-specific JSON Schemas or deterministic Python validators SHALL be versioned repository assets. Schema files are not database tables.

---

# 10. Checksums and Event Identity

`payload_checksum_sha256` is SHA-256 over the exact UTF-8 canonical-payload bytes.

The event identity source is compact canonical JSON containing exactly:

```text
ledger_contract
ledger_contract_version
entity_kind
entity_id
event_kind
supersedes_event_id
effective_from_utc
effective_to_utc
payload_checksum_sha256
recorded_by
```

`event_checksum_sha256` is SHA-256 over those event-identity bytes.

`recorded_at_utc` is excluded from event identity so an exact retry at a later wall-clock time remains idempotent. It remains immutable audit metadata on the first successful insert.

`authority_event_id` SHALL equal `event_checksum_sha256`.

Changing any material fact, effective boundary, actor, event kind, entity identity, or supersession link produces a different event ID. A service MUST never accept a caller-supplied checksum without recomputation.

---

# 11. Supersession Rules

1. A superseding event MUST reference an already-existing event.
2. The predecessor MUST have the same `entity_kind` and `entity_id`, except an explicit registration replacement may name a different replacement entity inside the payload while superseding the closing event of the old identity.
3. Declaration/revision state changes MUST follow an allowed event-kind transition matrix.
4. A partial unique index on `supersedes_event_id WHERE supersedes_event_id IS NOT NULL` SHALL prohibit two accepted successors from claiming the same predecessor. Rejected candidates do not supersede accepted heads; they use their own event identity and reference the compared head inside `body.conflicts_with_event_id`.
5. A superseding event MUST have `effective_from_utc` greater than or equal to the predecessor's effective start and MUST NOT create an overlapping accepted segment unless the applicable authority explicitly permits parallel source scopes.
6. Because predecessors must exist before successors and rows are immutable, cycles are structurally impossible; the writer SHALL additionally prove acyclicity during readback.
7. Supersession never deletes, updates, or hides the predecessor.
8. A superseded D1 registration/lane remains sufficient to interpret evidence accepted under its effective segment.

---

# 12. Effective Dating

`effective_from_utc` and `effective_to_utc` describe the event's authority segment, not insertion time.

Date-only authority values SHALL be normalized to `00:00:00+00:00` only for ledger comparison, while the canonical payload preserves the owning authority's original date precision and timezone/ownership semantics.

Open-ended authority uses `effective_to_utc = NULL`.

For evidence lanes, the payload MUST separately preserve:

```text
provider_earliest_timestamp
constitutionally_eligible_from
approved_effective_from
approved_effective_to
latest_approved_closed_boundary
```

The approved start remains the maximum of all applicable identity, listing, provider, interval, session, adjustment, methodology, entitlement, and authority boundaries. `UNRESOLVED` in any material boundary prevents compatible declaration or activation.

As-of reconstruction SHALL select events by effective segment and supersession chain, never merely by highest row ID or latest insertion time.

---

# 13. Replay and Idempotency

Before insertion, the writer SHALL canonicalize the payload and recompute payload checksum, event checksum, and event ID.

If `authority_event_id` already exists and every stored column is byte-for-byte identical, the result is:

```text
UNCHANGED
```

No row is inserted or updated.

If the ID exists but any stored byte differs, the result is a checksum-integrity failure and the transaction rolls back.

If a different event attempts to claim an already-superseded predecessor, it is retained as a non-superseding rejected/conflicting candidate when valid for retention; it MUST NOT replace the accepted successor.

Replaying one entity MUST NOT acquire locks or alter state outside the normal short registered-writer transaction, and failure MUST NOT affect unrelated entities.

---

# 14. Conflict and Rejection Retention

Conflicting or rejected candidates are first-class immutable events.

They MUST include:

- compared entity and accepted-head event ID;
- exact material fields in conflict;
- governing authority-document bindings;
- supplied values;
- required or unresolved values;
- compatibility reason codes;
- operational consequence;
- owner decision required;
- candidate checksum and evidence checksum;
- review actor and effective context.

Rejected events MUST NOT:

- supersede an accepted head;
- become an approved read-model head;
- declare or activate a lane;
- block unrelated declarations or reads.

The ledger SHALL preserve incompatible Stage A findings, including venue-specific BTC/USD versus requested aggregate, unresolved S&P 500 Price Return identity, and BHP entitlement limits, without promoting them to approved authority.

---

# 15. Immutability Enforcement

Migration 6 SHALL create:

```text
authority_events_no_update
authority_events_no_delete
```

Both triggers SHALL unconditionally abort every update or delete.

No maintenance, supersession, correction, reclassification, retention, compaction, or rollback path may disable those triggers in normal operation.

Corrections and state changes append new events. Database rollback is restoration of a verified pre-migration backup, never deletion of migration 6 or ledger rows from an accepted runtime.

---

# 16. Indexing

Only indexes supporting deterministic integrity and bounded read reconstruction are authorised:

```sql
CREATE INDEX authority_events_entity_order
ON authority_events(entity_kind,entity_id,effective_from_utc,recorded_at_utc,authority_event_id);

CREATE INDEX authority_events_kind_effective
ON authority_events(event_kind,effective_from_utc,effective_to_utc);

CREATE INDEX authority_events_payload_checksum
ON authority_events(payload_checksum_sha256);

CREATE UNIQUE INDEX authority_events_one_successor
ON authority_events(supersedes_event_id)
WHERE supersedes_event_id IS NOT NULL;
```

Implementation MAY add no other index without documenting its purpose and proving it does not encode a competing authority decision. Indexes do not count as application tables.

---

# 17. Read-Model Reconstruction

Read models are projections, not authority rows. They MUST be reconstructable from the ledger plus the preserved legacy tables without caches or writes.

## 17.1 Registration Projection

For each registration entity, return:

- legacy binding where applicable;
- full immutable declaration/revision history;
- accepted as-of head and effective segment;
- provider mapping entities and their states;
- unresolved facts and compatibility findings;
- approval/rejection/supersession chain;
- payload and event checksums;
- continued legacy D1 evidence availability.

## 17.2 Provider-Mapping Projection

Return every discovered, reviewed, approved, rejected, and superseded mapping separately. Never collapse identical symbol text across venues, source scopes, administrators, variants, units, adjustments, or effective segments.

## 17.3 Lane Projection

For each lane entity, return:

- registration and provider-mapping bindings;
- timeframe and source scope;
- provider contract, session, calendar, timestamp, unit, adjustment, validator, and authority bindings;
- effective range and entitlement;
- compatibility and activation state;
- declaration/revision/rejection/supersession history;
- whether a legacy lane and accepted evidence remain readable;
- Current-As-Of only from accepted evidence, never from declaration alone.

## 17.4 Deterministic Head Selection

The current accepted head is the terminal non-rejected event in the valid same-entity supersession chain for the requested as-of instant. Insertion order is not precedence. Parallel provider mappings remain separate heads. Ambiguous forks, overlaps, missing predecessors, invalid transitions, or checksum failures produce an affected-entity compatibility stop.

## 17.5 Stage A Matrix

The read service SHALL reconstruct nine candidates × four timeframes and show registration, mapping, declaration, entitlement, compatibility, exact blocker, authority binding, effective range, and accepted-evidence readability independently per lane.

Read-model queries MUST be bounded and indexed. They MUST open SQLite read-only with `mode=ro`, `SQLITE_OPEN_READONLY`, and `PRAGMA query_only=ON`.

---

# 18. Registered Writer and Commands

One generic authority-event service SHALL be used by registration, mapping, lane, CLI, tests, and native-triggered operations.

It SHALL:

1. validate event-kind/entity-kind legality;
2. validate the event-specific payload schema;
3. resolve referenced legacy rows and ledger entities;
4. resolve and checksum authority documents;
5. validate provider contract, session, calendar, timestamp, unit, adjustment, entitlement, and effective range as applicable;
6. reject `UNRESOLVED` material facts from approved/declaration events;
7. compute canonical bytes and checksums;
8. verify predecessor and transition legality;
9. perform exact replay detection;
10. append one immutable event in one registered-writer transaction;
11. read back and recompute integrity;
12. return an exact result without affecting unrelated paths.

All mutating SPEC-008A commands SHALL support `--dry-run`. Dry run performs every validation and checksum calculation but opens no write transaction and inserts no event.

The native application remains read-only with respect to SQLite authority except through the existing registered Python command boundary.

---

# 19. Legacy Bootstrap

Migration 6 creates the empty ledger and enforcement only. It MUST NOT infer or write new market metadata.

After migration, one explicit registered-writer bootstrap operation SHALL append:

- one `LEGACY_REGISTRATION_BOUND` event for each existing registration;
- one `LEGACY_LANE_BOUND` event for each existing evidence lane.

Each payload SHALL copy only exact existing row facts and checksums. Newly required facts absent from legacy rows SHALL be explicit `UNRESOLVED`. Bootstrap events MUST NOT change the existing rows, claim new approval, activate intraday lanes, or reinterpret Coinbase Pro BTC/USD as an aggregate.

Bootstrap is exactly replay-safe. A second run returns `UNCHANGED` for every binding.

Existing D1 operations MUST remain available before, during, and after bootstrap. Missing ledger metadata cannot hide or invalidate accepted historical evidence.

---

# 20. Migration 6 and Backup Procedure

Implementation SHALL add exactly one forward migration:

```text
Version: 6
Name: SPEC-008A1 immutable authority ledger amendment
```

Before runtime migration:

1. stop mutating operations through the existing writer boundary;
2. checkpoint WAL safely;
3. create a fresh SQLite backup using the registered backup operation;
4. record backup path, size, SHA-256, integrity result, foreign-key result, table count, migration inventory, and row counts;
5. record canonical digests for bars, registrations, evidence lanes, raw blocks, provenance, ingest runs, lane state, and rollup state;
6. verify the backup independently before migration.

Migration 6 SHALL atomically:

1. create `authority_events`;
2. create its four authorised indexes;
3. create immutable update/delete triggers;
4. create insert validation triggers for ID/checksum equality and event-kind/entity-kind legality where expressible in SQLite;
5. insert migration 6 history with the executable-statement checksum;
6. commit.

No legacy table or row is altered by migration 6.

After migration:

1. verify migration history 1–6;
2. prove checksums 1–5 unchanged;
3. prove exactly ten application tables;
4. run integrity and foreign-key checks;
5. prove every pre-existing table schema and primary key unchanged;
6. prove every pre-existing row count and canonical digest unchanged;
7. run explicit legacy bootstrap and replay;
8. verify all D1 operations and native reads remain green;
9. record the new database SHA-256 and explain that the change is limited to migration 6 and authorised ledger events.

Historical migration source MUST NOT be edited.

---

# 21. Rollback by Restoration

There is no reverse migration.

If migration 6, bootstrap, verification, or acceptance fails before approval:

1. stop the registered writer;
2. preserve the failed database and diagnostics as compatibility evidence without exposing secrets;
3. restore the verified pre-migration backup as a complete SQLite database;
4. verify integrity, foreign keys, nine-table identity, migrations 1–5, row counts, and canonical digests;
5. verify existing D1 behavior and native read-only launch;
6. record the restoration report.

Individual ledger events are never deleted to simulate rollback.

---

# 22. Ten-Table Acceptance Proof

Acceptance MUST prove:

```text
Application tables = exactly 10
New tables = exactly {authority_events}
```

It MUST also prove:

- the original nine table names remain exact;
- original table SQL, primary keys, and accepted triggers remain semantically unchanged;
- migrations 1–5 names and checksums remain exact;
- migration 6 checksum matches implementation;
- pre-existing row IDs, row counts, and canonical content digests remain exact;
- accepted D1 bars and Current-As-Of Truth remain readable;
- authority events reject update and delete;
- exact replay inserts zero rows;
- checksum mismatch is rejected;
- invalid event/entity combinations are rejected;
- a supersession chain is immutable and reconstructable;
- a rejected/conflicting candidate remains queryable but never becomes current authority;
- multiple provider mappings remain distinct under one registration;
- entitlement and effective-range changes create events, not updates;
- one blocked lane does not block unrelated reads or declarations;
- read-only verification preserves the runtime database hash;
- no secret is present in source, reports, fixtures, command arguments, logs, or SQLite;
- no eleventh table exists;
- no push occurred.

---

# 23. Required Tests

## 23.1 Schema and Migration

- migration 6 creates only `authority_events`;
- exactly nine tables before and ten after;
- interruption at every migration statement rolls back migration 6 completely;
- migration replay is safe;
- migrations 1–5 checksums remain unchanged;
- all legacy primary keys and table SQL remain unchanged;
- existing data digests remain unchanged;
- update/delete triggers reject all ledger mutation;
- restoration returns the exact nine-table baseline.

## 23.2 Canonicalization and Checksums

- key-order variants canonicalize identically;
- explicit nulls and controlled values remain material;
- duplicate keys, floats, noncanonical arrays, and empty unknowns are rejected;
- payload and event checksums match accepted fixtures;
- altered payload with reused checksum is rejected;
- event ID equals event checksum;
- credentials and credential-shaped fields are rejected from payloads.

## 23.3 Registration and Provider Mapping

- legacy registration binding preserves the original checksum;
- complete registration declaration succeeds;
- unresolved approved registration is rejected;
- multiple mappings attach to one registration as distinct entities;
- discovery, review, approval, rejection, and supersession transitions validate;
- exact replay returns `UNCHANGED`;
- conflicting mapping remains retained and non-authoritative;
- existing Coinbase Pro BTC/USD is not relabelled as aggregate.

## 23.4 Evidence Lanes

- complete D1, H1, M30, and M5 declarations succeed in fixture databases;
- new intraday declarations remain `DECLARED`, never `ACTIVE`;
- exact lane replay is unchanged;
- material conflict is retained as rejected without altering accepted head;
- lane revision and supersession chains reconstruct correctly;
- invalid timeframe, authority, session, unit, adjustment, provider mapping, entitlement, or effective range is rejected;
- unresolved effective boundary blocks declaration/activation;
- 9 fixture registrations × 4 timeframes reconstruct as 36 declared fixture lanes without bar acquisition.

## 23.5 Effective Dating and Read Models

- as-of reads select the correct effective segment;
- insertion time cannot override effective truth;
- overlaps/forks stop only the affected entity;
- superseded history remains queryable;
- Stage A matrix exposes exact blockers independently;
- accepted legacy D1 evidence remains visible when ledger metadata is unresolved.

## 23.6 Non-Blocking and Security

- one rejected declaration does not roll back an unrelated valid declaration performed in a separate transaction;
- one blocked lane does not block read-only application launch;
- secret filters cover all new CLI results and errors;
- fake credentials never enter payloads or database fixtures;
- the established credential file is not read by tests that do not require provider access.

---

# 24. Native Read-Only Inspection

The Operations Console SHALL add read-only inspection for:

- registration authority history;
- provider mappings and lifecycle state;
- lane declarations, candidates, conflicts, and supersession;
- authority bindings;
- entitlement and effective-range history;
- compatibility findings;
- payload/event checksums;
- effective as-of selection;
- legacy D1 evidence availability and Current-As-Of Truth.

The UI MUST label `DISCOVERED`, `REVIEWED`, `APPROVED`, `REJECTED`, `DECLARED`, `ACTIVE`, `AMBER`, `SUSPENDED`, and `SUPERSEDED` distinctly. It MUST display `UNRESOLVED` explicitly and MUST never imply that declaration equals activation.

The UI SHALL continue rendering unrelated registrations and lanes if one ledger chain is invalid or blocked. A chain-specific read error appears as a compatibility finding for that entity, not a blank application.

No acquisition control is added by this amendment.

---

# 25. Required Reports

Implementation and acceptance SHALL produce:

```text
docs/reports/SPEC-008A1_PREFLIGHT_REPORT.md
docs/reports/SPEC-008A1_MIGRATION_REPORT.md
docs/reports/SPEC-008A1_IMPLEMENTATION_REPORT.md
docs/reports/SPEC-008A1_ACCEPTANCE_REPORT.md
```

If blocked, produce the applicable exact report:

```text
docs/reports/SPEC-008A1_CONSTITUTIONAL_COMPATIBILITY_BLOCKER.md
docs/reports/SPEC-008A1_SCHEMA_COMPATIBILITY_BLOCKER.md
docs/reports/SPEC-008A1_RUNTIME_COMPATIBILITY_BLOCKER.md
docs/reports/SPEC-008A1_RESTORATION_REPORT.md
```

The reports MUST identify authority inputs, implementation checkpoint, pre/post schemas, migration checksums, table counts, row counts, canonical digests, ledger event counts/kinds, replay results, integrity/FK checks, test results, native results, known limitations, exact affected paths, secret scan, and push status.

---

# 26. Local Checkpoint and Push Prohibition

After clean acceptance, create one intentional local Git checkpoint containing only reviewed SPEC-008A1 implementation, tests, assets, native changes, and reports.

Before committing:

- inspect the complete diff;
- exclude credentials, runtime databases, backups, WAL/SHM files, provider payloads, unrelated user files, and generated secrets;
- record the local commit ID in the acceptance report;
- verify the worktree treatment of pre-existing untracked files.

Do not push. No remote branch, pull request, release, or deployment is authorised.

---

# 27. Implementation Stop Rule

Implementation SHALL stop before mutation if one generic `authority_events` table cannot honestly provide:

- immutable entity history;
- multiple mappings;
- exact mapping-to-lane binding;
- retained rejected/conflicting candidates;
- deterministic replay;
- non-forking supersession;
- effective as-of reconstruction;
- affected-path-only stopping;
- preservation of legacy D1 authority and evidence;
- exact ten-table identity.

The stop report MUST identify the exact constitutional or schema contradiction and owner decision required. No eleventh table, mutable snapshot, specialist ledger, weakened checksum, disabled immutability trigger, or inferred authority is permitted as a workaround.

---

# 28. Completion Statement

SPEC-008A1 authorises one narrow architectural amendment:

```text
Nine immutable existing application tables
+ one generic append-only immutable authority ledger
= exactly ten application tables
```

The ledger makes revisions visible without rewriting history, permits multiple provider mappings without merging identity, retains conflict without promotion, effective-dates authority without confusing it with insertion time, and preserves accepted D1 operation while intraday authority is declared safely.

No implementation begins until this specification is approved.

**Operations is King.**
