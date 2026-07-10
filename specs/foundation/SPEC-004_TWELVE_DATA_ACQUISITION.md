# SPEC-004 — Twelve Data Provider Acquisition and Common Staging Foundation

**Classification:** Foundation Specification

**Dependencies:** SPEC-001 through SPEC-003

**Status:** Implemented; live acceptance blocked pending credential

## Contract

The sole network adapter is `TWELVE_DATA` contract `TWELVE_DATA_TIME_SERIES_D1_V1`, using official HTTPS host `api.twelvedata.com`, endpoint `/time_series`, and interval `1day`.

Explicit mappings are AUDUSD → `AUD/USD`, XAUUSD → `XAU/USD`, and BTCUSD → `BTC/USD`. No asset or timeframe is inferred. Every request requires asset, D1, inclusive `from_date`, inclusive `through_date`, and existing preserve/correct merge mode.

Requests use the recommended `Authorization: apikey …` header. The credential comes only from `TWELVE_DATA_API_KEY`; it never enters a target URL, configuration, database, raw evidence, output, report, or project-generated command history.

## Bounded acquisition

The V1 contract allows one response covering no more than 5,000 requested calendar dates. Larger ranges fail explicitly. Paging is not silently improvised.

The request target is deterministic and includes endpoint, provider symbol, `1day`, UTC, ascending order, JSON, exact boundaries, and output size. Transport uses configured connect/read timeouts, three bounded attempts, bounded backoff, a stable user agent, no redirect following, exact-host verification, JSON media-type enforcement, and a 5 MiB response limit.

Transport failures and HTTP 429/5xx statuses retry only within policy. Credential, boundary, mapping, HTTP, error-payload, malformed, host, media, size, and staging failures occur before writer acquisition and do not mutate authority state.

## Evidence and staging

Only a complete HTTP 200 JSON response with provider status `ok`, exact symbol/interval metadata, a non-empty observations array, and structurally valid in-range observations is eligible evidence.

Exact response body bytes are SHA-256 identified and stored as one immutable `application/json` raw block. No normalization or prettification occurs. Error bodies are not market evidence and are not persisted.

The adapter emits the existing immutable `StagedBar` with source `TWELVE_DATA_TIME_SERIES_D1_V1` and provider `TWELVE_DATA`. Provider observations map datetime and OHLCV only. Missing volume remains null. Shared Decimal/OHLC, duplicate, ordering, and identity validation remain authoritative.

Manual CSV and provider evidence both call `ingest_staged_batch`, which owns raw preservation, run state, canonical merge, provenance, lane refresh, rollback, and factual outcomes. Adapters do not write bars.

## Commit, validation, and verification

Successful ingestion commits before SPEC-003 validation. Validation then runs with the same explicit `through_date` and persists only the authorized lane summary. A post-commit validation failure leaves evidence committed, clears the possibly stale summary, and reports `POST_INGEST_VALIDATION_FAILED`.

The operation finishes by reopening through the read-only contract and reconciling exact raw bytes, run state, provenance-event count, and non-null validation summary.

## Failure and restart

No pre-ingestion failure creates a raw block, run, bar, provenance event, lane change, or summary change. Interruption after response receipt but before writer acquisition leaves no authority state. An identical rerun reuses exact bytes if previously committed and cannot duplicate canonical bars.

No fallback, repair, deletion, calendar mutation, scheduling, service, sidecar, additional table, legacy access, or consumer interpretation is authorized.

Passing automated SPEC-004 tests proves deterministic adapter and storage mechanics against controlled responses. Live provider acceptance requires an operator credential and separate factual proof.

Fragarach II remains a candidate authority. **Operations is King.**
