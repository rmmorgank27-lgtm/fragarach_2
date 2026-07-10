# SPEC-003 — Versioned Asset Calendars and Factual Session Validation

**Classification:** Foundation Specification

**Dependencies:** SPEC-001, SPEC-001A, SPEC-002, SPEC-003A

**Status:** Implemented candidate

## 1. Purpose and boundary

SPEC-003 compares canonical D1 evidence with explicit versioned session expectations and reports facts. It does not modify bars, synthesize evidence, acquire data, repair gaps, create rollups, schedule work, migrate consumers, or decide readiness, promotion, tradability, safety, or provider preference.

The validator supports AUDUSD, XAUUSD, and BTCUSD through explicit symbol registry entries. Unknown symbols and non-D1 timeframes fail without mutation. Every request requires a canonical ISO `through_date`; wall-clock time never chooses the boundary.

## 2. Versioned definitions

Project JSON assets define:

- `FX_D1_V1`: Monday–Friday, closed 1 January and 25 December;
- `METALS_D1_V1`: Monday–Friday, closed 1 January, Gregorian Good Friday, and 25 December;
- `CRYPTO_D1_V1`: every Gregorian UTC date;
- explicit symbol assignments; and
- `FRAGARACH_II_D1_GAP_DOCTRINE_V1`.

Each asset embeds a checksum over canonical JSON excluding that checksum field. Registry loading rejects drift, unknown IDs, wrong formats, unsupported versions, and invalid overrides. No dated override exists in the initial definitions, but `EXPECTED_OVERRIDE` and `CLOSED_OVERRIDE` are implemented, take precedence, require factual reasons, and are reported when used.

Changing any definition requires a new version. Missing data never changes a calendar.

## 3. Validation range and present sessions

Validation begins at the earliest canonical D1 date for the requested lane and ends at `through_date` inclusive. Nothing before the earliest supplied evidence is asserted.

One canonical bar resolving to an expected UTC date is present. Missing expected dates are reported. Bars on closed dates within the boundary are `OUTSIDE_EXPECTED_SESSION`; bars after the boundary are `BEYOND_DECLARED_BOUNDARY`. Both remain canonical evidence. Multiple D1 keys resolving to one UTC calendar date produce an explicit structural validation error.

## 4. Coverage and gap facts

Every expected ISO week and calendar month reports expected, present, and missing counts plus whether any expected session is present.

Missing expected dates receive material reasons `CURRENT_EDGE_MISSING`, `EMPTY_EXPECTED_WEEK`, and/or `EMPTY_EXPECTED_MONTH` exactly as defined in Gap Doctrine V1. A date with any material reason uses wording `MATERIAL_BY_GAP_DOCTRINE_V1`. Remaining missing dates use `ISOLATED_EXPECTED_SESSION_MISSING` and wording `NON_MATERIAL_BY_GAP_DOCTRINE_V1`.

Material and non-material counts count missing session dates, never reason assignments. A date with multiple reasons counts once. Full per-date reasons and lossless expected-session ranges are returned.

## 5. Deterministic result

The full result contains calendar, registries, doctrine, validator and boundary identities; present/expected/missing/outside/beyond facts; weekly and monthly summaries; overrides; gap classifications; and deterministic lists and ranges.

Canonical JSON uses stable key and list ordering. `result_checksum` is SHA-256 of the full factual payload before observation metadata and checksum are added. Process, file location, row-return order, insertion order, formatting, and `validation_observed_at` do not affect it.

## 6. Persistence

The command defaults to `--no-persist` and uses the direct read-only contract. Explicit `--persist` acquires the registered writer, reads and updates in one immediate transaction, and writes only the SPEC-003A `lane_state.validation_summary` field. Existing lane facts and every evidence table remain unchanged.

The persisted summary records version/checksum identities, boundary, key counts, latest expected presence, material/non-material counts, full-result checksum, and observation metadata. It does not store a status label or consumer interpretation.

## 7. Command

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.validate_lane \
  --database /path/to/authority.sqlite3 \
  --symbol AUDUSD --timeframe D1 --through-date 2026-07-10 \
  --no-persist --json
```

`--persist` must be explicit. Unknown symbol, unsupported timeframe, invalid boundary, absent lane, calendar drift, and structural date collision are factual errors.

## 8. Acceptance

Automated and real-evidence proofs must establish calendar rules, holidays, Good Friday, override precedence, checksum drift detection, missing/outside/beyond behavior, edge/week/month doctrine, no double counting, weekly/monthly reconciliation, deterministic checksums, read-only default, summary-only persistence, full regression integrity, and exact seven-table retention.

Passing SPEC-003 proves only deterministic comparison with published internal expectations. It does not prove provider correctness, automated operation, consumer readiness, or production trust.

Fragarach II remains a candidate authority. No consumer migration is authorized.

**Operations is King.**
