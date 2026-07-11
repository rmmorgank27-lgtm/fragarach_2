# SPEC-007A Provider Contract Authority — Preflight Blocker Report

**Date:** 2026-07-11

**Status:** Compatibility stop required by specification

**Authority:** Candidate Authority

## Decision

Implementation stopped before creating Provider Contract Authority code or assets. The specification defines the fields a contract must contain, but no approved provider contract document containing those values was supplied. Its compatibility rules require an immediate stop when provider behavior, timestamp alignment, request limits, supported intervals, or authentication are undocumented or ambiguous.

## Existing accepted contract audit

Fragarach II already has the checksummed operational file `config/providers/twelve_data_time_series_d1.v1.json` and immutable registrations naming `TWELVE_DATA_TIME_SERIES_D1_V1`. That accepted file explicitly defines:

- provider identity and endpoint;
- D1/`1day` interval;
- UTC request timezone;
- API-key environment name;
- connect and read timeouts;
- three attempts with retry backoffs;
- maximum response bytes;
- maximum calendar-day range;
- request ordering and user agent.

It does not contain all fields mandated by the new specification. Treating behavior in Python code or historical tests as implicit authority would violate the prohibition on inference.

## Missing approved provider facts

### Contract identity and relationship

- No approved V1 contract asset is supplied.
- The examples use `TWELVE_DATA_D1_V1`, while accepted registrations reference `TWELVE_DATA_TIME_SERIES_D1_V1`.
- The specification does not say whether the existing checksummed configuration becomes the Provider Contract asset, references a new asset, or remains a lower-level execution configuration.
- Registration identity is immutable, so renaming the referenced contract is not authorized.

### Effective range

- `effective_from` is not defined.
- `effective_to` is not defined or explicitly open-ended.
- Effective-version selection and overlap rules are not defined.

### Timestamp and response semantics

- `INTERVAL_OPEN` versus `INTERVAL_CLOSE` is not approved.
- The canonical provider timestamp grammar is not specified as authority.
- Missing-value behavior is not fully defined.
- Provider duplicate and correction behavior is not distinguished from Fragarach merge policy.
- Response media type and timezone representation are not approved contract fields.

### Scope and capability

- Supported markets are not explicitly approved.
- Supported symbols or a deterministic symbol-capability rule are not approved.
- Only D1 is present in the existing configuration; no approved intraday contract exists.
- Required provider capability flags and their meanings are not enumerated.

### Limits, paging, and chunking

- Maximum provider observation count is not defined.
- Maximum historical availability is not defined.
- Paging support and continuation behavior are not defined.
- Chunk size, chunk boundary rules, and request ordering are not defined.
- Whether D1 explicitly prohibits chunking is not stated.
- Retryable status/error classes are implemented in code but are not authored as approved contract facts.

### Authentication and maintenance

- The current environment variable is known, but the authentication type, credential scope, and transport placement are not authored as contract values.
- Scheduled maintenance policy is absent; it is not explicitly declared `NONE`.
- Expected interruption behavior is absent.

## Inputs required to resume

1. Supply an approved, complete contract document for the existing `TWELVE_DATA_TIME_SERIES_D1_V1` identity, or explicitly define how it references a new Provider Contract asset without changing registration checksums.
2. Populate every mandatory field, including effective range, timestamp alignment, response semantics, markets, symbols, capabilities, paging, chunking, authentication, and maintenance.
3. Define effective-version and referential-integrity rules for immutable Provider Contract assets.
4. Supply accepted boundary fixtures for limits, timestamp alignment, paging/chunking rejection or behavior, retry classification, and response parsing.
5. Supply separate approved contract documents before any intraday interval is enabled.

## Preservation proof

- Existing provider configuration and checksum were not changed.
- Existing acquisition logic was not changed.
- Existing registrations and identity checksums were not changed.
- Existing evidence, provenance, validation, migrations, and application behavior were not changed.
- The pre-existing untracked `data/` directory remains untouched.
- No credential or secret was accessed.
- No remote push was performed.

Fragarach II remains **CANDIDATE AUTHORITY**. **Operations is King.**
