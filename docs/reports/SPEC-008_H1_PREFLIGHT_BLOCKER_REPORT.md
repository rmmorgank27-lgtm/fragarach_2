# SPEC-008 H1 Evidence Lane — Preflight Blocker Report

**Date:** 2026-07-11

**Status:** Blocked by missing H1 operational authority

**Authority:** Candidate Authority

## Decision

Implementation stopped before declaring H1 lanes or changing acquisition, import, validation, native UI, or authority data. SPEC-008 requires an immutable H1 provider contract and deterministic H1 validation for AUDUSD, BTCUSD, and XAUUSD, but does not supply the operational provider and market-session facts needed to implement either without inference.

## H1 provider-contract blockers

The specification names `TWELVE_DATA_TIME_SERIES_H1_V1` but does not define its complete checksummed content. Missing facts include:

- the exact Twelve Data interval value and accepted response interval value;
- whether timestamps identify interval opens or interval closes;
- timezone representation and canonical timestamp grammar;
- maximum observations per response;
- maximum historical range and any plan-dependent limit;
- calendar/time-span request bounds;
- paging support and continuation rules;
- chunk size, boundary overlap, ordering, and evidence semantics;
- missing-value, duplicate, and correction response behavior;
- retryable provider statuses and payload error classes;
- effective-from and effective-to values;
- explicit supported markets and symbols;
- maintenance and expected-interruption policy.

The existing D1 contract cannot supply these facts: it is immutably checksummed with `timeframe=D1`, `interval=1day`, and D1 request bounds. Reusing or extrapolating those values for H1 would redefine accepted provider authority.

## H1 validation blockers

The existing calendar authority determines expected trading dates. It does not define expected hourly timestamps. No approved Market/Trading Session Authority has been implemented.

### AUDUSD

Deterministic validation requires approved FX weekly boundaries, daily trading-day boundaries, timezone/DST authority, provider interval alignment, holidays, and any maintenance exclusions. The supplied FX authority document remains provisional and incomplete.

### XAUUSD

The supplied Metals authority delegates all material rules to unspecified approved authority. It does not select a venue or define session hours, breaks, maintenance, holidays, DST, or hourly alignment.

### BTCUSD

Continuous UTC expectations are conceptually specified, but the Crypto authority still lacks an effective range and concrete interval-open/interval-close alignment. Even if completed, BTCUSD alone would not satisfy the mandated three-instrument scope.

The H1 validator also needs an approved result contract defining timestamp-level missing ranges, partial current intervals, hourly materiality, session-edge behavior, and how the existing Gap Doctrine applies at H1 resolution. None is supplied.

## Evidence-lane activation blocker

SPEC-007 made lanes immutable and registration-backed; it intentionally declared only D1. Activating H1 for the three instruments requires an authorized Python writer operation or forward migration that inserts exactly three immutable H1 lane rows. SPEC-008 says existing migrations remain unchanged but does not explicitly distinguish preserving migrations 1–5 from authorizing migration 6. Runtime-created authority also needs an approved lane declaration timestamp/provenance rule.

## Native and operational proof blocker

The native console can display H1 only after factual H1 lane state exists. Creating that state requires accepted H1 evidence, which in turn requires the missing provider and validation authority. A synthetic UI-only H1 row would not be SQLite authority and would violate the specification.

## Minimum inputs required to resume

1. Supply and approve the complete `TWELVE_DATA_TIME_SERIES_H1_V1` contract with all operational values, effective range, checksum doctrine, and boundary fixtures.
2. Complete and approve FX, Metals, and Crypto Market/Trading Session/Trading Day authority sufficient to generate exact H1 expectations.
3. Define `SPEC-008_H1_VALIDATOR_V1`, its persisted result contract, timestamp-level Gap Doctrine semantics, and accepted validation fixtures.
4. Explicitly authorize migration 6 or a registered Python lane-declaration operation for exactly AUDUSD H1, BTCUSD H1, and XAUUSD H1, including declaration timestamps/provenance.
5. Define the bounded runtime acquisition ranges used for acceptance proof.

## Preservation proof

- No H1 evidence lane was declared.
- Existing D1 evidence, hashes, registrations, provider contract, acquisition, validation, and native behavior were not changed.
- Existing migrations 1–5 were not changed and no migration 6 was created.
- The pre-existing untracked `data/` directory remains untouched.
- No provider credential was accessed.
- No remote push was performed.

Fragarach II remains **CANDIDATE AUTHORITY**. **Operations is King.**
