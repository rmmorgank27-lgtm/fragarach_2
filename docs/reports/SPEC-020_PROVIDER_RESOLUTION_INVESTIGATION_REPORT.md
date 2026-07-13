# SPEC-020 Provider Resolution Bootstrap — Investigation Report

Date: 2026-07-13 (Australia/Brisbane)

## Conclusion

Provider identity bootstrap was not the failing boundary. Fragarach II resolved
the correct provider symbols, generated correct requests, received HTTP 200 and
valid Twelve Data payloads, and staged valid canonical bars. The transaction
then failed in the common ingestion pipeline when it attempted to overwrite an
unmapped registration's already-recorded first-evidence timestamp.

CSV import succeeded because it performed the first permitted transition from
`evidence_confirmed_at_utc=NULL` to a timestamp. A later provider fetch tried to
perform that transition again. The immutable registration trigger rejected the
second update as `invalid registration status transition`, rolling back the
otherwise-valid provider ingestion.

The suspected circular bootstrap did not exist:

```text
REGISTERED_UNMAPPED
→ deterministic operation-time provider identity
→ provider request
→ valid response
→ immutable ingest receipt confirms mapping
```

The defect was the repeated evidence-confirmation update after this bootstrap.

## Pre-repair trace

| Fact | AUDCAD | AUDNZD | USDJPY |
|---|---|---|---|
| Operator request | AUDCAD D1 | AUDNZD D1 | USDJPY D1 |
| Canonical symbol | AUDCAD | AUDNZD | USDJPY |
| Registration | `REGISTERED_UNMAPPED` | `REGISTERED_UNMAPPED` | `REGISTERED_WITH_EVIDENCE` |
| Registration provider identity | none | none | `TWELVE_DATA / USD/JPY` |
| Known registry aliases | `AUD/CAD`, common name | `AUD/NZD`, common name | ISO pair convention |
| Selected provider | Twelve Data | Twelve Data | Twelve Data |
| Provider symbol used | `AUD/CAD` | `AUD/NZD` | `USD/JPY` |
| Generated target | `/time_series?...&symbol=AUD%2FCAD&...` | `/time_series?...&symbol=AUD%2FNZD&...` | `/time_series?...&symbol=USD%2FJPY&...` |
| HTTP response | 200, JSON, provider `status=ok` | 200, JSON, provider `status=ok` | 200, JSON, provider `status=ok` |
| Outcome before repair | rolled back | rolled back | succeeded |
| Failure reason | `invalid registration status transition` | `invalid registration status transition` | no failure reproduced |

Yahoo fallback also used the deterministic identities `AUDCAD=X` and
`AUDNZD=X` and received HTTP 200. AUDCAD then reached the same common-ingestion
transition failure. AUDNZD's fallback payload separately failed strict OHLC
validation (`high is below close`); that did not cause the primary Twelve Data
failure and was not changed.

USDJPY's reported earlier failure could not be reproduced from the current
database state: its registration already contains the reviewed Twelve Data
mapping, and the pre-repair trace succeeded. The defective transition applies
to any lane while it is `REGISTERED_UNMAPPED` with a non-null first-evidence
timestamp, which explains the observed AUDCAD/AUDNZD post-CSV behavior without
inventing a separate USDJPY cause.

## Previous implementation comparison

The previous Fragarach `CanonicalSymbolMapper` translates six-letter canonical
FX identity deterministically to `BASE/QUOTE`. Its Twelve Data service submits
that value as the `symbol` parameter to
`https://api.twelvedata.com/time_series`, with interval, UTC, ascending order,
date boundaries, output size, JSON format, and authentication.

Fragarach II generated the same FX symbols and request family. It sends the
credential in the authorization header instead of the query string, a supported
transport difference proven by the successful responses. Fragarach II's Yahoo
fallback deterministically uses `PAIR=X`. No canonical symbol was sent directly
to either provider, and no arbitrary-name retry occurred.

The divergence was therefore after request translation and HTTP response, in
Fragarach II registration-evidence bookkeeping.
