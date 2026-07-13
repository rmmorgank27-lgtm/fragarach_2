# SPEC-021 GBPJPY Workflow Trace

Date: 2026-07-13 (Australia/Brisbane)

## Pre-repair trace

| Stage | Result | Reason | Elapsed |
|---|---|---|---:|
| Discover Market / Search | SUCCESS | One reviewed `GBPJPY` registry match | 10–12 ms |
| GBPJPY located | SUCCESS | Canonical identity `FX:GBPJPY` | included above |
| Operator selects instrument | SUCCESS | FX spot representation selected | <1 ms |
| Registration created | SUCCESS | `INSERTED` | 3 ms |
| Registration state | SUCCESS | `REGISTERED_UNMAPPED` as designed | <1 ms |
| Provider resolution | SUCCESS | Twelve Data selected deterministically | included below |
| Provider request | SUCCESS | `GBP/JPY`, D1, UTC, ascending | included below |
| HTTP request/response | SUCCESS | HTTP 200 JSON, provider `status=ok` | ~1.9 s |
| Payload parsed | SUCCESS | JSON/meta/3,698 observations accepted | included above |
| Canonical bar staging | **FAILED** | observation 1,737: `low is above close` | immediate |
| Ingestion onward | NOT REACHED | transaction was not started | — |

Last successful stage: **provider payload parsing after a valid HTTP response**.
First failed stage: **structural canonical-bar staging**.

## Post-repair complete trace

| Stage | Result | Reason |
|---|---|---|
| Discover Market | SUCCESS | `KNOWN` reviewed market |
| Search | SUCCESS | GBPJPY located |
| Operator selection | SUCCESS | GBPJPY D1 selected |
| Registration created | SUCCESS | `INSERTED` |
| Registration state | SUCCESS | `REGISTERED_UNMAPPED` |
| Provider resolution | SUCCESS | Twelve Data / `GBP/JPY` |
| Provider request | SUCCESS | `/time_series`, D1, UTC, ascending, bounded 5,000-day window |
| HTTP response | SUCCESS | 200 JSON, 376,270 bytes in focused trace |
| Payload parsed | SUCCESS | 3,698 observations |
| Canonical bars created | SUCCESS | 3,691 valid; seven invalid OHLC rows rejected |
| Ingestion pipeline | SUCCESS | `COMPLETED_WITH_WARNINGS` |
| Evidence committed | SUCCESS | immutable raw block, provenance, committed ingest receipt |
| Registration confirmation | SUCCESS | first evidence timestamp recorded |
| Provider mapping confirmation | SUCCESS | receipt records `TWELVE_DATA / GBP/JPY / CONFIRMED_BY_VALID_EVIDENCE` |
| Validation | SUCCESS | persisted; strict missing/outside-session warnings retained |
| Truth calculation | SUCCESS | GREEN 87 |
| CAODT update | SUCCESS | 2026-07-12 |
| Authority refresh | SUCCESS | GBPJPY added to estate Truth matrix |
| Native UI refresh | SUCCESS | running app changed from 10 to 11 symbols; GBPJPY GREEN appeared without restart |
| SPEC-018 contract | SUCCESS | `AVAILABLE`, 3,691 bars |
| External catalog | SUCCESS | GBPJPY immediately discoverable to consumers |
| Morphix request | SUCCESS | canonical history received directly from Fragarach |
| Morphix display | SUCCESS | native chart rendered 3,691 D1 bars with latest date and GREEN authority |

The completed journey used normal discovery, registration, acquisition, writer,
Truth, read-only service, and native refresh paths. No CSV or manual database
operation was used.
