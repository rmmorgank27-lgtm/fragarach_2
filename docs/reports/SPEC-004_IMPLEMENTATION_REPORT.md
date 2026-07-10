# SPEC-004 Twelve Data Acquisition — Implementation Report

**Report date:** 2026-07-11

**Repository:** `/Users/raymorgan/VSC/fragarach_2`

**Implementation checkpoint:** `779adbed969ccd77da319c695cc6e7539c94746d`

## Outcome

SPEC-004 is implemented and structurally proven against controlled, secret-free provider responses. The Twelve Data boundary adapter performs bounded HTTPS acquisition, preserves an eligible response byte-for-byte, converts it to the common staging contract, and invokes the same canonical ingestion pipeline as manual CSV evidence.

No schema migration or table was added. No legacy Fragarach runtime was accessed. The subsequently authorized bounded live proof is recorded in `SPEC-004_LIVE_ACCEPTANCE_REPORT.md`.

Fragarach II remains a **CANDIDATE AUTHORITY**. No consumer migration is authorized.

## Compatibility gate

Before implementation:

- all 58 existing tests passed;
- the tracked tree was clean, with operator `data/` intentionally outside Git;
- the acceptance database passed integrity and foreign-key checks;
- migrations 1 through 3 matched their recorded checksums;
- the application table set was exactly the seven foundation tables; and
- canonical counts were 33,547 bars, 3 raw blocks, 67,094 provenance events, 6 ingest runs, and 3 lanes.

Provider request identity, contract identity, and bounded factual request details fit the existing `ingest_runs.detail` contract. Exact response bytes fit `raw_blocks`; staged bars and provenance fit the existing contracts. No foundation amendment was required.

## Implemented boundary

- Provider: `TWELVE_DATA`
- Contract: `TWELVE_DATA_TIME_SERIES_D1_V1`
- Endpoint: `https://api.twelvedata.com/time_series`
- Interval: native D1 (`1day`)
- Explicit mappings: AUDUSD to `AUD/USD`, XAUUSD to `XAU/USD`, BTCUSD to `BTC/USD`
- Authentication: `Authorization` header populated only from `TWELVE_DATA_API_KEY`
- Deterministic UTC, ascending, JSON requests with explicit inclusive boundaries
- Maximum requested range: 5,000 calendar dates; larger ranges fail rather than improvise paging
- Connect/read timeouts: 10/20 seconds
- Attempts: at most 3 with bounded 0/1/2-second backoff
- Response limit: 5 MiB
- Redirect rejection, exact-host verification, and JSON media-type enforcement

The provider configuration is `config/providers/twelve_data_time_series_d1.v1.json`. Its declared canonical configuration checksum is:

```text
d372a15a3541d56903e276355a65038cc3ce9fb12bbd71d80cf01f0a8f1ff9c5
```

Its file-byte SHA-256 is:

```text
67891b43a28e66211ce587982e7f921c776516e5d56529ebe3b37d407e314458
```

## Evidence and pipeline behavior

Only a complete HTTP 200 JSON response with matching provider metadata, provider status `ok`, and valid in-range observations is eligible evidence. Its exact body is stored as one immutable `application/json` raw block. Error and malformed bodies are not stored as market evidence.

The adapter emits existing `StagedBar` records. Missing volume remains null. Decimal, OHLC, ordering, duplicate, identity, preserve/correct, provenance, transaction, and lane-state behavior is owned by the shared pipeline in `src/fragarach_ii/ingestion/pipeline.py`. Both manual CSV and provider acquisition call this pipeline; the adapter does not write canonical bars directly.

Successful ingestion commits before SPEC-003 validation. A later validation failure reports that evidence was committed and clears a possibly stale validation summary. Final verification reopens the database through the read-only contract and reconciles exact raw bytes, run state, provenance-event count, and the validation summary.

## Failure guarantees

Credential, mapping, boundary, timeframe, transport, HTTP, host, media-type, size, provider-error, malformed-payload, and staging failures occur before writer acquisition. They create no raw block, ingest run, canonical bar, provenance event, lane-state change, or validation-summary change.

Interruption after receipt but before ingestion also leaves authority state unchanged. Repeating an identical successful response reuses the raw block and does not duplicate canonical bars. Credentials are excluded from request targets, configuration, database detail, raw evidence, CLI output, reports, and fixtures.

## Automated proof

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

```text
Ran 72 tests
OK
```

The 14 added tests cover explicit mappings; rejected assets, timeframes, dates, and oversized ranges; deterministic secret-free requests; exact-byte preservation; ascending/descending response handling; optional volume; raw-block reuse; duplicate handling; preserve/correct behavior; malformed and provider-error responses; bounded retries; HTTP, timeout, media, host, size, and redirect failures; interruption; post-ingest validation failure; absent credentials; configuration checksum drift; read-only verification; integrity; and the exact seven-table boundary. All 58 earlier tests remain green.

Controlled fixture byte checksums:

| Fixture | SHA-256 |
|---|---|
| AUDUSD | `212f03d98ff51e0adc2b946f30268365fe693f78e79eb815ec77b9afa0a409e5` |
| XAUUSD | `dedb607d14ab95801c2fb4da37aaf7e6fc1b8f36ba1a2334f52e19ad4e15f257` |
| BTCUSD | `82ef3134e1121ed25fc2d4f3ff5428dd8d8d2d9e5868e5e979786b2ed0d21dba` |

These fixtures contain fabricated evidence and no credential.

## Deferred operational proof

The implementation does not prove live provider behavior, service availability, entitlement, symbol coverage, historical depth, rate-limit behavior, or operational trust. Paging is not implemented. Acquisition is operator-invoked only; no scheduler, service, provider fallback, repair path, consumer interface, or migration was added.

The final live-acceptance report records the later bounded runtime proof and its limitations. **Operations is King.**
