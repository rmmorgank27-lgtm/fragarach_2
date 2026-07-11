# Fragarach II Cross-Market Stage A — Compatibility Report

**Date:** 2026-07-11
**Status:** Superseded credential conclusion; mapping stops revised
**Scope:** Stage A only; 9 instruments × 4 timeframes
**Preflight:** `docs/reports/FRAGARACH_II_CROSS_MARKET_STAGE_A_PREFLIGHT_REPORT.md`

## Outcome

Stage A acceptance acquisition did not begin. The original credential-unavailable conclusion was incorrect and is superseded by `FRAGARACH_II_CROSS_MARKET_STAGE_A_MAPPING_MANIFEST.md`. Material mapping, entitlement, manifest-field, and executable-authority gaps remain; registering identities, declaring lanes, or acquiring evidence would still require unresolved facts or redefinition of accepted D1 behavior.

## Exact 36-lane outcome matrix

The code in each cell is the primary stopping outcome from the acceptance manifest. A D1 registration already present in the runtime is not equivalent to passing this Stage A proof.

| Candidate | D1 | H1 | M30 | M5 | Exact reason |
|---|---|---|---|---|---|
| AUDUSD | `SOURCE_CONTRACT_PROBLEM` | `SOURCE_CONTRACT_PROBLEM` | `SOURCE_CONTRACT_PROBLEM` | `SOURCE_CONTRACT_PROBLEM` | Live entitlement unavailable; required mapping-manifest fields/effective range incomplete. Intraday contracts and execution paths absent. |
| BTC/USD provider aggregate | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | Existing `BTC/USD` registration is scoped to `Coinbase Pro`, not the requested provider aggregate; aggregate scope/methodology cannot be inferred. |
| XAUUSD | `SOURCE_CONTRACT_PROBLEM` | `SOURCE_CONTRACT_PROBLEM` | `SOURCE_CONTRACT_PROBLEM` | `SOURCE_CONTRACT_PROBLEM` | Live entitlement unavailable; provider price/source scope, unit record, adjustment basis, session identity, and effective range incomplete. Intraday contracts and execution paths absent. |
| USOIL provider-derived WTI reference | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | No authenticated reference result; exact provider symbol, type, WTI/source methodology, unit, adjustment basis, session, and effective range unresolved. |
| S&P 500 Price Return, USD | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | No authenticated reference result; administrator/methodology, price-return variant, currency/publication scope, symbol, session, and effective range unresolved. |
| AAPL — Nasdaq primary listing | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | No authenticated reference result; exact Nasdaq/XNAS primary-listing mapping, session scope, adjustment basis, entitlement, and effective range unresolved. |
| SHEL — London primary listing | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | No authenticated reference result; exact XLON ordinary-share mapping, GBX display unit, session scope, adjustment basis, entitlement, and effective range unresolved. |
| SAP — Xetra primary listing | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | No authenticated reference result; exact XETR (not Frankfurt/ADR) mapping, session scope, adjustment basis, entitlement, and effective range unresolved. |
| BHP — ASX primary quotation | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | `INCOMPATIBLE_PROVIDER_MAPPING` | No authenticated reference result; exact XASX security form/quotation mapping, normal-trading and auction scope, adjustment basis, entitlement, and effective range unresolved. |

For AUDUSD and XAUUSD intraday lanes, `SOURCE_CONTRACT_PROBLEM` is primary because a canonical D1 identity exists but no executable intraday source contract exists. For every unmapped candidate, `INCOMPATIBLE_PROVIDER_MAPPING` remains primary across all timeframes even though intraday source-contract gaps also apply.

## Proofs safely completed

### Provider discovery isolation

The `USOIL` discovery path returned `PROVIDER_UNAVAILABLE` because authentication was unavailable. Immediately afterward, an unrelated read-only `AUDUSD` discovery succeeded from registered authority and returned `REGISTERED_WITH_EVIDENCE`. Thus one blocked candidate did not block an unrelated candidate.

### Read-only access and database preservation

- Read-only AUDUSD lane lookup succeeded.
- Read-only AUDUSD canonical-bar count: 14,262.
- Application-table count: exactly 9.
- SQLite integrity result: `ok`.
- Runtime database SHA-256 before read-only proof: `b39e9e521ea7f55d2c47011db3744d5494d28bd73761c8e60167173a093b5221`.
- Runtime database SHA-256 after read-only proof: `b39e9e521ea7f55d2c47011db3744d5494d28bd73761c8e60167173a093b5221`.

This proves affected-path isolation and hash-preserving read access for existing accepted evidence. It does not claim Stage A first-acquisition, replay, overlap, validation, or Current-As-Of acceptance for the requested 36 lanes.

## Mutation and scope preservation

- No instrument registration was inserted or changed.
- No evidence lane was inserted or changed.
- No provider request, acquisition, replay, overlap, merge, validation, or backfill was run.
- No Stage B work began.
- No constitutional document was altered.
- Existing user/untracked files were preserved.
- No push was performed.

## Exact inputs required to resume affected paths

1. Make an entitled Twelve Data credential available through `TWELVE_DATA_API_KEY` and approve reference discovery for all nine candidates.
2. Review and approve a complete mapping manifest with exact identity, provider type/symbol, venue/source/aggregate scope, currency, unit, session profile, adjustment basis, effective ranges, and entitlement results.
3. Resolve the requested BTC/USD aggregate as a distinct identity from the existing Coinbase Pro registration.
4. Materialise checksummed executable H1, M30, and M5 provider contracts, including timestamp semantics, limits, paging/chunking, overlap, response behavior, effective range, and entitlement constraints.
5. Implement and accept registration-backed lane declaration, acquisition, staging, validation, Current-As-Of, and read-only paths for H1/M30/M5 without changing existing accepted D1 identities or historical migrations.
6. Supply or implement the schema authority required to persist unit, session profile, adjustment basis, and effective range without mutating immutable existing registrations by inference.

**Operations is King.**
