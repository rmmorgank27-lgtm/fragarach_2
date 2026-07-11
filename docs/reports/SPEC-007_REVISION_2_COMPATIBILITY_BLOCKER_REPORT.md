# SPEC-007 Multi-Timeframe Evidence Authority — Revision 2 Compatibility Blocker

**Date:** 2026-07-11

**Status:** Blocked by accepted executable authority

**Authority:** Candidate Authority

## Decision

Implementation stopped before modifying authority code. Revision 2 requires M5, M30, H1, and D1 while simultaneously requiring the existing D1 provider contract, registrations, migrations, validation, and accepted authority to remain unchanged. Those requirements are mutually incompatible in the current executable system.

## Executable contradictions

### Existing provider contract is D1-only

The checksummed accepted contract `TWELVE_DATA_TIME_SERIES_D1_V1` explicitly fixes:

- `timeframe` to `D1`;
- provider `interval` to `1day`;
- the endpoint family and request bounds for that D1 operation.

The configuration loader verifies those exact values. Executing M5, M30, or H1 under that contract identity would make the actual provider request disagree with the immutable contract named by registration and provenance.

### Existing acquisition rejects intraday

The accepted acquisition path rejects every timeframe except D1. Its request builder always uses the contract's `1day` interval. Its response adapter requires provider metadata interval `1day`, validates D1 date timestamps, and stages bars with explicit timeframe `D1`.

Changing only a request parameter is therefore not possible. Changing all these checks while preserving the D1 contract would silently redefine an accepted checksummed contract.

### Existing validation is intentionally D1-only

The accepted validator rejects non-D1 timeframes, identifies itself as `SPEC-003_D1_VALIDATOR_V1`, persists `fragarach_ii.d1_session_validation.v1`, and enforces one canonical bar per date. Its calendar authority defines expected dates, not intraday timestamps or session hours.

M5, M30, and H1 completeness cannot reuse those semantics unchanged. No accepted Market Session Authority currently exists from which exact intraday timestamps could be derived.

### Registration enforcement is exact-lane today

Existing registration rows are immutable and constrained to `timeframe='D1'`. Both Python ingestion and SQLite bar triggers require an exact registration match on `(asset,timeframe)`. Intraday evidence is therefore correctly rejected by both authority layers.

One instrument-wide registration can authorize multiple lanes only after changing those enforcement semantics. That requires an explicitly authorized forward migration and corresponding Python lookup changes while preserving existing registration rows and identity checksums.

### “Migrations unchanged” prohibits the required authority change

The specification requires existing migrations to remain unchanged. Historical migrations can and should remain immutable, but a new forward migration is necessary to replace the exact-lane registration triggers. If “migrations unchanged” also prohibits adding a migration, the requested lanes cannot be admitted by SQLite authority.

### Intraday request bounds remain undefined

The accepted D1 contract permits up to 5,000 calendar days. Applied to M5, that could imply roughly 1.44 million observations before market closures and exceed provider or response limits. Interval-specific bounds, paging, and chunking semantics are not approved. The specification requires bounded acquisition but provides no factual intraday bound.

## Minimum compatible amendment

Implementation can resume only if an amendment explicitly authorizes:

1. immutable intraday provider-contract facts or a new checksummed contract identity for M5, M30, and H1;
2. interval-specific provider request, response, paging/chunking, and bounded-history rules;
3. a versioned intraday validation contract backed by approved Market Session timestamp authority;
4. a forward migration changing registration enforcement from exact lane registration to instrument-wide asset authorization while preserving all existing registration rows and checksums;
5. addition of new migration history while preserving every existing migration unchanged.

## Preservation proof

- Existing D1 evidence and accepted hashes were not touched.
- Existing registrations, provider contracts, migrations, provenance, validation, and application behavior were not changed.
- No acquisition, import, merge, or validation operation was run.
- The pre-existing untracked `data/` directory remains untouched.
- No credential or secret was accessed.
- No remote push was performed.

Fragarach II remains **CANDIDATE AUTHORITY**. **Operations is King.**
