# SPEC-007 Multi-Timeframe Authority Foundation — Preflight Blocker Report

**Date:** 2026-07-11

**Status:** Blocked before implementation

**Authority:** Candidate Authority

## Outcome

SPEC-007 cannot be implemented deterministically against the accepted SPEC-001 through SPEC-006 authority without inventing material facts. No schema, acquisition, validation, evidence, registration, or native application code was changed during this preflight.

## Blocking incompatibilities

### 1. Existing calendars cannot define intraday expectations

The accepted calendar definitions contain expected weekdays, full-day closures, calculated full-day closures, and date overrides. They do not contain:

- session open and close timestamps;
- session timezone rules;
- daylight-saving transitions;
- intraday breaks;
- early-close times;
- whether interval timestamps identify opens or closes;
- boundary behavior for sessions spanning UTC dates.

Consequently `FX_D1_V1` and `METALS_D1_V1` can determine whether a date is expected, but cannot determine which M5, M30, or H1 timestamps are expected on that date. Assuming a 24-hour UTC grid would invent market facts and would make completeness results false around daily breaks, weekends, holidays, and DST transitions.

SPEC-007 says calendar assignment must remain instrument-wide and that no duplicate timeframe calendars may be introduced. A compatible amendment therefore needs to extend the existing versioned calendar model with checksummed intraday session rules while preserving the accepted D1 interpretation and checksums.

### 2. The accepted provider contract is explicitly D1

`TWELVE_DATA_TIME_SERIES_D1_V1` is checksummed with:

- `endpoint_family=time_series`;
- `interval=1day`;
- `timeframe=D1`;
- a 5,000-calendar-day request bound.

Every immutable instrument registration names that D1 provider contract. Changing only a request parameter would cause the executed request to disagree with the registered, checksummed contract. Reusing the D1 contract name for M5, M30, or H1 would make provenance factually incorrect.

SPEC-007 needs an explicit contract doctrine: either one new checksummed multi-timeframe provider contract referenced instrument-wide, or immutable per-lane acquisition-contract metadata outside the registration identity. Existing registration identity checksums must remain unchanged.

### 3. Intraday acquisition bounds are unspecified

The D1 acquisition bounds requests by calendar days and response bytes. The same 5,000-day bound is not safe for M5: it can imply roughly 1.44 million observations before closures. SPEC-007 requires reuse of the bounded acquisition engine, but does not define interval-specific maximum spans, provider output limits, or whether one operator request may be split into multiple independently preserved provider responses.

An amendment must define deterministic bounds for M5, M30, H1, and D1 and the evidence/provenance semantics of any required chunking.

### 4. Registration enforcement is currently lane-specific

The existing registration row is immutable and constrained to `timeframe='D1'`. Both ingestion code and SQLite triggers currently authorize evidence only when an exact `(asset,timeframe)` registration exists. That correctly rejects every proposed intraday bar today.

Supporting one instrument registration across many lanes requires a forward migration that changes only the authorization triggers and operational lookup semantics to match registration by canonical asset, while leaving all existing registration rows and identity checksums unchanged. SPEC-007 should explicitly authorize this migration because “registration SHALL NOT change” could otherwise be read as prohibiting it.

### 5. Validation contracts are D1-specific

The accepted validator contract and persisted result format are named `SPEC-003_D1_VALIDATOR_V1` and `fragarach_ii.d1_session_validation.v1`. Its gap classifications, weekly/monthly coverage, and “one bar per date” invariant are intentionally D1-specific. Intraday lanes require a versioned result contract defining timestamp-level missing ranges, materiality, partial current intervals, and session-edge behavior. Reusing the D1 result name would misstate what was validated.

## Decisions required to resume

1. Accept a calendar amendment defining checksummed intraday session hours, timezone/DST rules, breaks, and early closes without duplicating calendars per timeframe.
2. Define the checksummed provider-contract identity used for M5, M30, and H1 while preserving existing registration identity checksums.
3. Define interval-specific acquisition bounds and whether bounded chunking is authorized.
4. Explicitly authorize a forward migration changing registration enforcement from exact `(asset,timeframe)` matching to instrument-wide asset authorization, with existing rows unchanged.
5. Define an intraday validation result/version contract and timestamp-level Gap Doctrine behavior.

## Preservation proof

- Worktree authority code is unchanged by this preflight.
- The pre-existing untracked `data/` directory remains untouched.
- No database was opened for writing.
- No evidence was acquired, imported, merged, validated, or rewritten.
- No secret was accessed.
- No remote push was performed.

Fragarach II remains **CANDIDATE AUTHORITY**. **Operations is King.**
