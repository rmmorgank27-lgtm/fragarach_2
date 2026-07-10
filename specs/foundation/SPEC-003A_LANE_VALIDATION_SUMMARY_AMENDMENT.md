# SPEC-003A — Lane-State Validation Summary Foundation Amendment

**Classification:** Foundation Specification amendment

**Authorization:** Approved by Ray

**Dependency:** SPEC-001, SPEC-001A, SPEC-002

**Status:** Implemented candidate

**Scope:** Storage contract only; SPEC-003 remains paused

## 1. Purpose and boundary

The SPEC-003 compatibility gate proved that the existing `lane_state` row could not hold a versioned factual validation summary without overwriting canonical lane or ingestion facts. This amendment adds one nullable field to the existing table and no new authority.

SPEC-003A does not implement calendars, session validation, gap classification, commands, consumer interpretation, or ingestion behavior. It does not modify canonical bars, raw evidence, provenance, ingest history, or existing lane-state meanings. The application table boundary remains exactly seven.

## 2. Schema amendment

Migration 3 adds:

```text
lane_state.validation_summary TEXT NULL
```

Existing rows receive `NULL`. The migration does not update `high_watermark_open_time_utc`, `state_version`, `last_ingest_run_id`, or `updated_at_utc`. A null summary means no persisted validation summary is present; it does not mean validation passed, failed, or was attempted.

No existing column may be repurposed. Future validation persistence updates only `validation_summary` unless a later specification separately authorizes a direct factual recalculation.

## 3. Versioned JSON contract

Every non-null value has format:

```text
fragarach_ii.lane_validation_summary.v1
```

It contains exactly these keys:

```text
format
symbol
timeframe
calendar_id
calendar_version
calendar_checksum
gap_doctrine_id
gap_doctrine_version
gap_doctrine_checksum
validator_version
through_date
expected_session_count
present_expected_session_count
missing_expected_session_count
outside_expected_session_count
empty_week_count
empty_month_count
latest_expected_session
latest_expected_session_present
material_gap_count
non_material_gap_count
result_checksum
validation_observed_at
```

The summary is intentionally smaller than the full future validation result. It stores the exact factual persistence boundary authorized by SPEC-003 and a checksum that identifies the complete deterministic result.

## 4. Structural enforcement

Insert and update triggers reject a non-null summary when:

- it is not valid JSON;
- its format or exact key set differs from V1;
- symbol or timeframe differs from the containing lane row;
- calendar, gap-doctrine, or validator identity is absent;
- calendar or gap-doctrine version is not a positive integer;
- definition or result checksums are not lowercase 64-character hexadecimal SHA-256 text;
- boundary, latest-expected-session, or observation metadata has the wrong JSON shape;
- counts are not non-negative integers;
- present plus missing does not equal expected sessions; or
- latest-expected-session presence is not a JSON boolean.

The Python value object additionally requires canonical ISO calendar dates and an offset-bearing ISO observation timestamp before serialization.

These checks validate structure and contract version only. They do not calculate or endorse calendar facts.

## 5. Canonical serialization

`LaneValidationSummary` is an immutable value object. It emits UTF-8 JSON with:

- lexicographically sorted keys;
- no insignificant whitespace;
- stable Unicode handling;
- native JSON integers, booleans, strings, and null; and
- no extension or interpretation keys.

Equivalent summary values therefore produce identical JSON text. `validation_observed_at` remains metadata inside the persisted summary; SPEC-003 must exclude it from the future factual-result checksum as already specified.

## 6. Migration contract

Migration 3 is forward-only, versioned, and independently checksummed. Migrations 1 and 2 are unchanged. It runs inside one `BEGIN IMMEDIATE` transaction:

1. add the nullable column;
2. create insert-boundary validation;
3. create update-boundary validation;
4. record migration version, name, checksum, and application time; and
5. commit.

Any exception rolls back the column, triggers, and migration record together. Reopening recognizes the matching checksum and refuses drift.

## 7. Read and write boundary

Consumers read `validation_summary` using the existing direct read-only SQLite contract. A consumer cannot persist, clear, or replace it.

Only the registered writer may update the field. The later SPEC-003 command must default to no persistence and acquire the same process-held writer lock only when explicit persistence is selected.

The field is replaceable factual state, not append-only evidence. Historical full results and retention policy are outside this amendment and require later authorization; the result checksum makes the persisted summary attributable to a specific deterministic result.

## 8. Integrity, backup, and restoration

Current structural verification requires all three migration identities and checksums, exact seven-table membership, `integrity_check=ok`, and an empty `foreign_key_check` result.

SQLite online backup must preserve non-null summary text exactly. A restored backup must pass full current verification and return the identical summary through a read-only connection.

## 9. Acceptance proof

Automated tests must prove:

- version-2 databases migrate without evidence or existing lane-field changes;
- existing lane rows receive null summaries;
- injected interruption restores the complete version-2 schema and data;
- canonical serialization is deterministic;
- malformed, wrong-version, incomplete, mismatched, and factually inconsistent structures are rejected;
- valid summaries cross the writer boundary without changing other lane fields;
- read-only consumers can read but cannot mutate summaries;
- raw blocks, bars, provenance, and ingest runs remain identical;
- backup and restoration preserve summary text;
- foreign keys, integrity, migration checksums, and exactly seven tables pass; and
- all SPEC-001 through SPEC-002 regression tests remain passing.

Passing SPEC-003A proves only that the existing lane row can safely hold the later validator's versioned factual summary. SPEC-003 must restart from its compatibility gate before calendar implementation begins.

Fragarach II remains a candidate authority. No consumer migration is authorized.

**Operations is King.**
