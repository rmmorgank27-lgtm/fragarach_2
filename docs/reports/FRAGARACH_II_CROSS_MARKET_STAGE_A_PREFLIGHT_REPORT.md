# Fragarach II Cross-Market Stage A — Preflight Report

**Date:** 2026-07-11
**Acceptance manifest:** `FRAGARACH_II_CROSS_MARKET_TEST_UNIVERSE_V1`
**Scope:** Stage A only
**Decision:** Superseded credential conclusion; see reviewed discovery manifest

> **Correction, 2026-07-11:** The authorised credential was present at the previously approved secure path and was subsequently loaded through the established in-memory mechanism. The statements below that describe the credential as unavailable and external request count as zero are superseded by `FRAGARACH_II_CROSS_MARKET_STAGE_A_MAPPING_MANIFEST.md`. They are retained only as the original preflight record.

## Executive decision

Stage A cannot proceed cleanly. No provider credential is available to the process, the accepted executable provider contract is D1-only, and the registered writer can declare only a D1 lane. H1, M30, and M5 acquisition, staging, validation, and lane-declaration paths are not implemented. The required exact mapping facts (including source/venue scope, unit, adjustment basis, session profile, and effective range) are not materialised for six candidates and are incomplete for the three existing registrations.

In accordance with affected-path-only stopping, no new instrument or evidence lane will be registered and no acquisition will be run. Existing accepted D1 evidence for AUDUSD, BTCUSD, and XAUUSD remains untouched.

## Provider-reference discovery

Discovery was attempted in the required order with the repository's bounded `search_instrument` operation against the runtime authority database. The operation resolved three existing registrations locally. The other six stopped before a network request because `TWELVE_DATA_API_KEY` is absent.

| Candidate | Exact provider facts found | Material unresolved facts | Gate |
|---|---|---|---|
| AUDUSD | Twelve Data; `AUD/USD`; `Physical Currency`; OTC; USD; existing `FX_D1_V1` registration | provider price basis, exact session-profile identity, adjustment basis/non-applicability record, provider/timeframe effective ranges; all intraday executable contracts | STOP affected H1/M30/M5 and new proof acquisition |
| BTC/USD provider aggregate | Twelve Data; `BTC/USD`; `Digital Currency`; existing registration says `Coinbase Pro`; USD; `CRYPTO_D1_V1` | requested aggregate identity conflicts with venue-specific existing scope; aggregate methodology/scope, adjustment basis, effective ranges; all intraday executable contracts | STOP entire requested aggregate candidate |
| XAUUSD | Twelve Data; `XAU/USD`; `Precious Metal`; OTC; USD; existing `METALS_D1_V1` registration | provider price basis/source scope, explicit troy-ounce mapping record, adjustment basis, exact session profile, effective ranges; all intraday executable contracts | STOP affected proof paths |
| USOIL provider-derived WTI reference | None; authentication unavailable | exact symbol/type, WTI relationship, source methodology/scope, USD-per-barrel unit, session profile, adjustment basis, effective ranges and entitlement | STOP candidate |
| S&P 500 Price Return, USD | None; authentication unavailable | exact provider symbol/type; administrator/methodology; price-return (not total/net return) variant; USD; publication/source/session profile; adjustment basis; effective ranges and entitlement | STOP candidate |
| AAPL — Nasdaq primary listing | None; authentication unavailable | exact provider symbol/type; Nasdaq/XNAS primary-listing scope; USD; regular-session profile; adjustment basis; effective ranges and entitlement | STOP candidate |
| SHEL — London primary listing | None; authentication unavailable | exact provider symbol/type; LSE/XLON ordinary-share identity; GBX price-display unit; source/session profile; adjustment basis; effective ranges and entitlement | STOP candidate |
| SAP — Xetra primary listing | None; authentication unavailable | exact provider symbol/type; Xetra/XETR (not Frankfurt or ADR) scope; EUR; session profile; adjustment basis; effective ranges and entitlement | STOP candidate |
| BHP — ASX primary quotation | None; authentication unavailable | exact provider symbol/type; ASX/XASX security-form and primary-quotation scope; AUD; normal-trading/auction scope; adjustment basis; effective ranges and entitlement | STOP candidate |

No provider suffix, index shorthand, venue, aggregate, unit, session, adjustment value, or effective range has been inferred.

## Entitlement and source-contract limitations

- Provider authentication is unavailable; zero external discovery requests were issued.
- Entitlement and per-symbol/per-interval availability therefore remain unproven for all requested live acquisitions.
- The only checksummed executable provider asset is `TWELVE_DATA_TIME_SERIES_D1_V1`, fixed to Twelve Data `time_series`, interval `1day`, UTC, ascending order, and a maximum request span of 5,000 calendar days.
- No checksummed executable H1, M30, or M5 provider contracts exist.
- Provider observation ceilings, pagination/chunking, intraday history limits, effective ranges, and plan-dependent restrictions are not materialised as executable authority.

## Proposed registrations (not approved for mutation)

The requested canonical identities are AUDUSD; a distinct BTC/USD provider-aggregate identity; XAUUSD; USOIL provider-derived WTI reference; S&P 500 Price Return, USD; AAPL Nasdaq primary listing; SHEL London primary listing; SAP Xetra primary listing; and BHP ASX primary quotation.

Only AUDUSD and XAUUSD currently align at a high level with existing D1 registrations, but required manifest fields remain incomplete. The existing BTCUSD registration is venue-specific (`Coinbase Pro`) and must not be relabelled as the requested provider aggregate. The six other identities have no reviewed provider mapping. Therefore none of the proposed new/changed registrations is approved.

## Proposed evidence lanes (not declared)

The requested set is exactly 36 lanes: D1, H1, M30, and M5 for each of the nine instruments. The runtime currently contains only AUDUSD D1, BTCUSD D1, and XAUUSD D1. The registered writer validates registration timeframe as D1 and automatically declares D1 only; there is no authorised operational command for declaring the other 33 requested lanes.

## Expected request counts and data volumes

| Operation | Expected/actual count | Volume conclusion |
|---|---:|---|
| Provider discovery | 9 attempted; 3 local resolutions; 6 authentication stops; 0 external requests | No provider payload downloaded |
| Stage A D1 proof | At least one bounded request per approved lane, plus authority-approved overlap | Exact count cannot be approved until all mappings/effective ranges are known; the executable D1 contract would fit a 90-day window within one request per lane |
| Stage A H1/M30/M5 proof | Undefined | Request counts cannot be calculated without interval-specific ceilings, chunking/overlap rules, effective ranges, and executable contracts |
| Canonical bars | D1: at most 90 requested-window bars per lane before overlap; intraday depends on approved session grids | Exact volume cannot be stated without inventing sessions, exceptional calendars, overlaps, and effective ranges |

A minimum theoretical requested-window ceiling is 810 D1 bars across nine candidates before overlap. Intraday row counts are intentionally not estimated because session ownership and effective-range facts are lane-specific authority.

## Compatibility blockers

1. Six provider mappings cannot be discovered without authentication; all nine live entitlements remain unproven.
2. BTCUSD's existing venue-specific identity does not satisfy the requested provider-aggregate identity.
3. Required manifest fields are absent from the current registration schema: explicit unit, session profile, adjustment basis, and effective range.
4. The executable provider contract, acquisition adapter, staging contract, and validator support D1 only.
5. No executable H1/M30/M5 provider-contract assets or interval-specific bounded-request rules exist.
6. No registered writer operation is authorised to declare the remaining 33 evidence lanes.
7. Current-As-Of Truth, replay, overlap, validation, and read-only acceptance cannot be honestly proven for lanes that cannot be mapped, declared, or acquired.

## Preservation baseline

- Runtime application tables: exactly nine.
- SQLite `integrity_check`: `ok`.
- SQLite foreign-key check: no rows returned.
- Runtime database SHA-256 before any report mutation: `b39e9e521ea7f55d2c47011db3744d5494d28bd73761c8e60167173a093b5221`.
- Existing runtime authority: three registrations and three D1 evidence lanes.
- No database, configuration, implementation, constitutional document, or provider state was mutated during preflight.
- No push was performed.

**Operations is King.**
