# SPEC-006A Instrument Registration Authority — Preflight Blocker Report

**Report date:** 2026-07-11

**Preflight commit:** `1c0660b93093c4f250dca5c6c296677868fe0ca8`

**Outcome:** Blocked before backup, implementation, or migration

## Decision

SPEC-006A is authorized in principle, but its mandatory three-row backfill manifest cannot yet be completed without guessing material identity fields. The amendment explicitly requires `exchange_name` to be non-null and explicitly prohibits inventing an unknown exchange or venue.

Accepted provider evidence contains no exchange for AUDUSD or XAUUSD. No existing contract, doctrine, raw block, ingest detail, calendar assignment, or validation summary establishes an OTC/global venue name for either lane. Therefore the migration coverage gate cannot truthfully construct all required rows.

Implementation stopped before:

- creating the external pre-migration backup;
- editing schema or migration code;
- writing a manifest;
- changing runtime lookup;
- modifying the acceptance database; or
- adding or applying migration 4.

No partial amendment is present.

## Passed preflight work

The accepted baseline passed:

```text
Ran 75 Python tests
OK

OperationsCoreChecks: 10 checks passed

swift build
Build complete

Fragarach II.app launch verified
```

Tracked Git state was clean except intentional operator `data/`. The real authority remained at the exact seven-table, three-migration boundary with integrity `ok` and zero foreign-key violations.

The current authority baseline remains the one recorded in `SPEC-006_COMPATIBILITY_GATE_REPORT.md`:

- 33,551 canonical bars;
- 6 raw blocks;
- 81,419 provenance events;
- 14 ingest runs; and
- 3 lane-state rows.

## Facts available for the manifest

### AUDUSD D1

Accepted contracts and live evidence establish:

```text
asset: AUDUSD
timeframe: D1
provider_id: TWELVE_DATA
provider_contract: TWELVE_DATA_TIME_SERIES_D1_V1
provider_symbol: AUD/USD
provider currency_base: Australian Dollar
provider currency_quote: US Dollar
provider type: Physical Currency
calendar_id: FX_D1_V1
calendar_version: 1
gap_doctrine_id: FRAGARACH_II_D1_GAP_DOCTRINE_V1
gap_doctrine_version: 1
earliest factual evidence time: 2026-07-10T13:55:08.321103+00:00
```

Not established:

```text
exchange_name
exchange_mic
provider_exchange
jurisdiction/provider_country
reviewed controlled display_name
reviewed broad instrument_type and asset_class labels
```

### XAUUSD D1

Accepted contracts and live evidence establish:

```text
asset: XAUUSD
timeframe: D1
provider_id: TWELVE_DATA
provider_contract: TWELVE_DATA_TIME_SERIES_D1_V1
provider_symbol: XAU/USD
provider currency_base: Gold Spot
provider currency_quote: US Dollar
provider type: Precious Metal
calendar_id: METALS_D1_V1
calendar_version: 1
calendar-definition asset_class: METALS_XAUUSD
gap_doctrine_id: FRAGARACH_II_D1_GAP_DOCTRINE_V1
gap_doctrine_version: 1
earliest factual evidence time: 2026-07-10T13:55:08.686443+00:00
```

Not established:

```text
exchange_name
exchange_mic
provider_exchange
jurisdiction/provider_country
reviewed controlled display_name
whether registration asset_class is METALS or METALS_XAUUSD
reviewed controlled instrument_type label
```

The live accepted response says `Precious Metal`; a controlled fixture says `Commodity`. The live immutable evidence is the stronger factual source, but selecting the registration label still requires the manifest contract to state its normalization.

### BTCUSD D1

Accepted contracts and live evidence establish:

```text
asset: BTCUSD
timeframe: D1
provider_id: TWELVE_DATA
provider_contract: TWELVE_DATA_TIME_SERIES_D1_V1
provider_symbol: BTC/USD
provider currency_base: Bitcoin
provider currency_quote: US Dollar
provider type: Digital Currency
provider exchange: Coinbase Pro
calendar_id: CRYPTO_D1_V1
calendar_version: 1
calendar-definition asset_class: CRYPTO
gap_doctrine_id: FRAGARACH_II_D1_GAP_DOCTRINE_V1
gap_doctrine_version: 1
earliest factual evidence time: 2026-07-10T13:55:09.027943+00:00
```

MIC and country remain absent and can be explicit nulls. BTCUSD is otherwise sufficiently disambiguated if the reviewed manifest adopts the provider's exact live labels.

## Required Ray decision

To resume SPEC-006A without weakening constraints, Ray must authorize the reviewed V1 backfill semantics for at least these fields:

| Asset | Required decision |
|---|---|
| AUDUSD | Exact factual `exchange_name` representing its non-exchange/global/OTC venue |
| XAUUSD | Exact factual `exchange_name` representing its spot-metal venue |
| All three | Approved deterministic display-name construction from the accepted base/quote facts, or explicit display names |
| All three | Controlled `instrument_type` and broad `asset_class` values |
| XAUUSD | Whether registration class is `METALS` or preserves `METALS_XAUUSD` |
| All three | Whether `registered_at_utc` and `evidence_confirmed_at_utc` both use the earliest committed INSERT provenance time shown above |

A coherent example policy would be reviewed explicit venue constants for non-centralized markets, display names formed as `<provider currency_base> / <provider currency_quote>`, provider type retained verbatim in `provider_instrument_type`, separate controlled registration types/classes, and null MIC/jurisdiction when absent. This report does not adopt that policy; doing so without Ray's approval would violate the amendment.

## Unchanged boundary

No secret was displayed or persisted. No legacy Fragarach path was accessed. No provider request occurred. No tracked implementation/configuration file or authority record changed.

SPEC-006 and SPEC-006A remain paused. Fragarach II remains a **CANDIDATE AUTHORITY**. No consumer migration is authorized. **Operations is King.**
