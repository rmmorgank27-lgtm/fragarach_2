# Fragarach II Cross-Market Stage A — Reviewed Provider Mapping Manifest

**Date:** 2026-07-11
**Status:** Reviewed; partial approval prohibited by unresolved material fields
**Provider:** Twelve Data
**Scope:** Stage A only

## Credential and discovery control

The credential was read only from the previously authorised file `/Users/raymorgan/VSC/Morphix_Data_Hot/runtime_state/secrets/local.env`, using its established `TWELVEDATA_API_KEY` name and injecting the value into child-process memory as `TWELVE_DATA_API_KEY`. Verification returned only `present/non-empty`. The value was not displayed, logged, copied, written to the repository, or passed as a command argument.

Provider symbol search was executed for all nine candidates. Targeted searches were also executed for WTI and S&P 500 variants. Dedicated `earliest_timestamp` discovery was executed for each interval where an unambiguous mapping and entitlement permitted it.

## Reviewed mapping table

`UNRESOLVED` means the field is material and registration is prohibited. Constitutional session profiles listed below are proposed authority assignments, not claims that provider data has passed alignment validation.

| Canonical identity | Provider symbol/type | Venue/source scope | Currency | Unit | Proposed session profile | Adjustment basis | Provider effective range discovered | Review decision |
|---|---|---|---|---|---|---|---|---|
| AUDUSD spot pair | `AUD/USD`; Physical Currency | Provider physical-currency reference; returned exchange `PHYSICAL CURRENCY`, MIC-like code `PHYSICAL_CURRENCY`; decentralised OTC scope | USD quote | 1 AUD priced in USD | FX New York rollover authority; exact persisted profile identity `UNRESOLVED` | Non-corporate-action price basis; exact provider price basis `UNRESOLVED` | D1 1979-12-24; H1 2020-01-29 14:00; M30 2020-01-29 14:30; M5 2020-03-19 00:00 (provider-returned timestamps) | STOP: required persisted fields/price basis incomplete |
| BTC/USD provider aggregate | `BTC/USD`; Digital Currency | Provider search returned three distinct venue rows: Coinbase Pro, Binance, Bitfinex; no aggregate row | USD quote | 1 BTC priced in USD | Continuous UTC | `UNRESOLVED` | Not queried as aggregate because no aggregate identity resolved | STOP: requested aggregate mapping not found |
| XAUUSD spot pair | `XAU/USD`; Precious Metal | Provider commodity reference; exchange/MIC-like value `COMMODITY`; exact provider price/source basis `UNRESOLVED` | USD quote | One troy ounce of gold priced in USD (constitutional unit; provider unit confirmation `UNRESOLVED`) | Metals New York rollover authority; exact persisted profile identity `UNRESOLVED` | `UNRESOLVED` | D1 1979-12-26; H1 2020-01-24 13:00; M30 2020-01-24 13:00; M5 2020-03-16 12:10 | STOP: source/price basis, unit confirmation, and persisted fields incomplete |
| USOIL provider-derived WTI reference | `WTI/USD`; Energy Resource; provider name `Crude Oil WTI Spot / US Dollar` | Provider commodity reference; exchange/MIC-like value `COMMODITY`; exact source methodology remains `UNRESOLVED` | USD | USD per barrel is the constitutional candidate; provider unit confirmation `UNRESOLVED` | Energy New York rollover authority; exact persisted profile identity `UNRESOLVED` | Provider-derived continuity/roll/adjustment methodology `UNRESOLVED` | D1 1983-03-30; H1/M30/M5 2020-10-05 09:00 | STOP: methodology, unit confirmation, adjustment basis, and persisted fields incomplete |
| S&P 500 Price Return, USD | None approved | No administrator/index result found. `SPX` returned unrelated equities/ETFs; `S&P 500` returned proxies; `GSPC`, `SPX:IND`, and `SPX500USD` did not resolve the required index | USD required | Index points | S&P publication profile required | Price Return variant required; unresolved | Not available without an exact mapping | STOP: exact administrator, methodology, return variant, and provider mapping absent |
| AAPL Nasdaq primary listing | `AAPL`; Common Stock | NASDAQ; provider MIC `XNGS`; United States | USD | USD per share | US regular-session authority; exact persisted profile identity `UNRESOLVED` | Adjusted/unadjusted provider basis `UNRESOLVED` | D1 1980-12-12; H1 2019-01-07 09:00; M30 2019-09-16 09:30; M5 2020-01-08 14:30 | STOP: adjustment basis and required persisted fields incomplete |
| SHEL London primary listing | `SHEL`; Common Stock | LSE; MIC `XLON`; United Kingdom | Provider returned `GBp` (pence); doctrine requires reviewed GBX display-unit treatment | Pence per share (`GBp` provider spelling; canonical GBX mapping requires explicit approval) | UK regular continuous session authority; exact persisted profile identity `UNRESOLVED` | Adjusted/unadjusted provider basis `UNRESOLVED` | D1 1996-08-29; H1/M30/M5 2020-05-20 08:00 | STOP: unit normalization approval, adjustment basis, and persisted fields incomplete |
| SAP Xetra primary listing | `SAP`; Common Stock | XETR; MIC `XETR`; Germany | EUR | EUR per share | `XETRA_REGULAR_CONTINUOUS_V1` | Adjusted/unadjusted provider basis `UNRESOLVED` | D1 1998-04-09; H1/M30/M5 2020-09-28 09:00 | STOP: adjustment basis and required persisted fields incomplete |
| BHP ASX primary quotation | `BHP`; Common Stock | ASX; MIC `XASX`; Australia | AUD | AUD per share | ASX normal-trading-only authority; exact persisted profile identity `UNRESOLVED` | Adjusted/unadjusted provider basis `UNRESOLVED` | Entitlement blocked. D1/H1/M30 returned provider code 404: Pro or Venture plan required. M5 then hit the per-minute credit ceiling and does not override the entitlement result. | STOP: `SOURCE_CONTRACT_PROBLEM` plus unresolved adjustment/persisted fields |

## Provider availability and effective-range interpretation

For AUDUSD, XAUUSD, WTI/USD, AAPL/NASDAQ, SHEL/LSE, and SAP/XETR, one-observation time-series probes succeeded for D1, H1, M30, and M5. The timestamps returned by those probes were latest observations and were not used as effective starts. Effective starts in the table come only from Twelve Data's dedicated `earliest_timestamp` endpoint.

An earliest provider timestamp proves provider-reported availability, not automatic constitutional eligibility. Each lane's approved effective start remains the maximum of instrument identity, listing/quotation, provider semantics, session/adjustment segment, and entitlement boundaries required by its authority.

## Reviewed registration decision

No candidate is approved for registration from this manifest revision:

- BTC/USD aggregate and S&P 500 Price Return lack an exact provider identity.
- BHP is not entitled under the current source contract/plan.
- AUDUSD, XAUUSD, WTI/USD, AAPL, SHEL, and SAP have reference mappings and provider ranges, but required adjustment, price/source basis, unit confirmation or normalization, exact persisted session identity, and effective-segment fields are not completely materialised.
- The current immutable registration schema does not contain explicit unit, session-profile, adjustment-basis, or effective-range fields demanded by the acceptance manifest.
- H1, M30, and M5 executable provider contracts and registered lane-declaration/acquisition/validation paths remain absent.

Accordingly, the registration and evidence-lane mutation gate remains closed. This is an affected-path compatibility decision, not permission to substitute proxies or infer missing facts.

## Request accounting

- Repository discovery adapter: 9 attempts; 3 local existing-registration results, 1 no-match, 5 calendar-unsupported responses.
- Direct provider symbol-reference searches: 9 primary searches plus 8 targeted disambiguation searches.
- Latest-observation entitlement probes: 28 requests across 7 unambiguous candidates × 4 intervals.
- Earliest-timestamp probes: 28 requests across the same set.
- No acquisition, raw-evidence preservation, ingestion, validation, registration, or lane-declaration request was made.

## Preservation

- No runtime database mutation occurred.
- No instrument or evidence lane was registered.
- No constitutional document was modified.
- No Stage B work began.
- No push was performed.

**Operations is King.**
