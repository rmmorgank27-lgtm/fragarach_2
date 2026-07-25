# SPEC-059 Implementation Report

## Result

Accepted. The indices Update regression was repaired in the shared D1 operational-calendar resolution and native acquisition-planning path. No provider mapping, alias, Scheduler cadence, budget, credential, commissioning, canonical schema, Forex calendar, or Metals calendar was changed.

## Deterministic failure point

The first incorrect value was produced at operational-calendar resolution, before provider planning.

Both commissioned lanes were registered with the legacy `REGISTRY_D1_V1` placeholder:

| Lane | Representation | Stored venue | Canonical edge before | Pre-repair result |
| --- | --- | --- | --- | --- |
| DJI D1 | INDEX | Index namespace | `2026-07-13T00:00:00+00:00` | `OPERATIONAL_CALENDAR_UNAVAILABLE`; expected edge absent |
| SPY D1 | ETF | NYSE Arca | `2026-07-13T00:00:00+00:00` | `OPERATIONAL_CALENDAR_UNAVAILABLE`; expected edge absent |

The resolver translated that placeholder only for stock asset classes. It did not consult the existing reviewed market identity for an `INDICES` registration. Consequently, freshness and the operational schedule stopped before a calendar-derived expected edge existed. Provider fallback itself was already deterministic and correct.

## Repair

The shared calendar resolver now:

- preserves every explicit non-placeholder calendar;
- resolves a specific reviewed US venue to `US_EQUITIES_D1_V1`;
- when the stored venue is generic, resolves the canonical symbol and asset class through the existing reviewed market registry and uses that reviewed venue;
- passes the canonical symbol through freshness, schedule, commissioning, validation, Scheduler integrity, and Estate publication call sites.

This resolves DJI through its reviewed `US index market` identity and SPY through its stored `NYSE Arca` venue. It does not contain symbol-specific dates or new provider aliases.

The freshness projection also publishes an explicit expected-edge classification:

- `EXPECTED_EDGE_AVAILABLE`
- `NO_NEW_COMPLETED_SESSION`
- `MARKET_CLOSED`
- `INSTRUMENT_CALENDAR_UNRESOLVED`
- `CALENDAR_UNAVAILABLE`

The Swift planner consumes that classification. It displays explicit request bounds, a factual no-update reason, or a factual calendar failure; it no longer presents an unexplained blank expected edge.

## Provider decisions

### DJI D1

- Twelve Data evaluated: **yes**.
- Twelve Data decision: **ineligible — `NO_APPROVED_MAPPING`**.
- Reason: the current provider-fact revision has no approved Twelve Data symbol proving the same DJI index representation. Candidate discovery remains available for operator review; no candidate was silently promoted.
- Yahoo Finance decision: **eligible — `APPROVED_PROVIDER_ALIAS`**.
- Reviewed mapping: `DJI` -> `^DJI`.
- Selected provider: `YAHOO_FINANCE`.

### SPY D1

- Twelve Data evaluated: **yes**.
- Twelve Data decision: **ineligible — `NO_APPROVED_MAPPING`**.
- Reason: provider facts classify the Twelve Data candidates as representation-ambiguous for the registered ETF lane; no candidate was auto-approved.
- Yahoo Finance decision: **eligible — `EXACT_REPRESENTATION`**.
- Reviewed mapping: `SPY` -> `SPY`.
- Selected provider: `YAHOO_FINANCE`.

Yahoo selection did not require a preferred-provider mapping. The orchestrator evaluated Twelve Data, retained its rejection evidence, then selected the next eligible provider by the existing deterministic priority order.

### Complete D1 provider projection

All projected providers reported credential and entitlement state `AVAILABLE`. “Rank” below is the evaluated canonical order; the configured numeric priority is shown in parentheses.

| Lane | Rank | Provider | Provider symbol / representation | Mapping state | D1 capability | Eligibility | Exact decision |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| DJI D1 | 1 (10) | TWELVE_DATA | none | `MAPPING_REQUIRED` | `UNBOUNDED_BY_CONTRACT` | Ineligible | `NO_APPROVED_MAPPING` |
| DJI D1 | 2 (20) | YAHOO_FINANCE | `^DJI` / approved alias | `APPROVED_PROVIDER_ALIAS` | `UNBOUNDED_BY_CONTRACT` | Eligible, selected | reviewed provider configuration |
| DJI D1 | 3 (20) | BINANCE | none | `MAPPING_REQUIRED` | `UNBOUNDED_BY_CONTRACT` | Ineligible | `ASSET_CLASS_UNSUPPORTED` |
| DJI D1 | 4 (30) | COINGECKO | none | `MAPPING_REQUIRED` | `30_CALENDAR_DAYS` | Ineligible | `ASSET_CLASS_UNSUPPORTED` |
| SPY D1 | 1 (10) | TWELVE_DATA | none | `MAPPING_REQUIRED` | `UNBOUNDED_BY_CONTRACT` | Ineligible | `NO_APPROVED_MAPPING` |
| SPY D1 | 2 (20) | YAHOO_FINANCE | `SPY` / exact ETF representation | `EXACT_REPRESENTATION` | `UNBOUNDED_BY_CONTRACT` | Eligible, selected | reviewed provider configuration |
| SPY D1 | 3 (20) | BINANCE | none | `MAPPING_REQUIRED` | `UNBOUNDED_BY_CONTRACT` | Ineligible | `ASSET_CLASS_UNSUPPORTED` |
| SPY D1 | 4 (30) | COINGECKO | none | `MAPPING_REQUIRED` | `30_CALENDAR_DAYS` | Ineligible | `ASSET_CLASS_UNSUPPORTED` |

For DJI, the reviewed candidate evidence did not establish `DJI`, `DJIA`, `DJI:INDEX`, `^DJI`, or `US30` as a Twelve Data representation of the registered cash index. `^DJI` remains approved only in the Yahoo Finance namespace. The unresolved Twelve Data candidates remain review material rather than installed mappings.

## Required acceptance fields

| Field | DJI D1 | SPY D1 |
| --- | --- | --- |
| Authoritative failure point | Placeholder operational calendar did not resolve for reviewed US index-market identity | Placeholder operational calendar did not resolve for reviewed US venue |
| Was Twelve Data evaluated? | Yes | Yes |
| Twelve Data decision | Ineligible | Ineligible |
| Twelve Data reason | `NO_APPROVED_MAPPING` | `NO_APPROVED_MAPPING` / representation ambiguous |
| Yahoo Finance decision | Eligible, approved provider alias | Eligible, exact representation |
| Operational calendar selected | `US_EQUITIES_D1_V1` | `US_EQUITIES_D1_V1` |
| Expected edge before repair | Absent | Absent |
| Expected edge after repair | `2026-07-14T00:00:00+00:00` | `2026-07-14T00:00:00+00:00` |
| Provider selected | `YAHOO_FINANCE` (`^DJI`) | `YAHOO_FINANCE` (`SPY`) |
| Bounded request | `2026-07-14` through `2026-07-14` | `2026-07-14` through `2026-07-14` |
| Canonical advancement | `2026-07-13T00:00:00+00:00` -> `2026-07-14T00:00:00+00:00` | `2026-07-13T00:00:00+00:00` -> `2026-07-14T00:00:00+00:00` |
| Publication result | `PUBLISHED`; inserted 1; corrected 0 | `PUBLISHED`; inserted 1; corrected 0 |
| Final freshness | `Current`; lag 0 trading days | `Current`; lag 0 trading days |
| Final Estate acquisition state | `AUTOMATED_UPDATE_AVAILABLE`; eligible provider `YAHOO_FINANCE` | `AUTOMATED_UPDATE_AVAILABLE`; eligible provider `YAHOO_FINANCE` |

The committed ingest outcomes record `YAHOO_FINANCE_CHART_D1_V1`, the reviewed mapping class, the exact `from_date` and `through_date`, one inserted observation, and immutable raw/provenance lineage.

## Regression protection

Focused Python coverage proves:

- DJI and SPY resolve the US equities D1 calendar through reviewed venue authority;
- the expected edge is the latest completed US market session;
- Twelve Data rejection does not block Yahoo fallback;
- a bounded Yahoo publication advances canonical truth and Estate freshness;
- AUDUSD retains `FX_D1_V1` planning;
- XAUUSD retains `METALS_D1_V1` planning.

Focused Swift coverage proves:

- DJI selects Yahoo after retaining the Twelve Data rejection;
- expected edge and bounds are explicit;
- an unresolved calendar is an explicit failure;
- canonical edge equal to expected edge is an informational no-update state.

## Verification

- SPEC-059 Python tests: **3 passed**.
- Adjacent focused Python checks: **9 passed** total, including calendar, D1 validation, orchestrator routing/failover, provider-fact ambiguity, and manual-authority separation.
- `OperationsCoreChecks`: **35 passed**.
- One signed release build: **passed**.
- Native launch/liveness verification: **passed**.
- Native DJI journey: selected DJI D1 and Update; the plan exposed canonical and expected edges as `2026-07-14T00:00:00+00:00`, selected `YAHOO_FINANCE`, retained Twelve Data as `No Approved Mapping`, and rendered `No update required — no new completed market session.` after publication.

The live bounded acquisitions for DJI and SPY selected Yahoo Finance, inserted the 14 July observation, advanced canonical publication, and left both lanes `Current`. The native UI displayed the advanced DJI CAODT and no longer blocked Update because the expected edge was blank.

## Recurrence prevention

The repair is in the shared reviewed-venue calendar resolver used by freshness, scheduling, validation, commissioning, Estate, and native planning inputs. The regression tests exercise both the generic reviewed-index venue and a specific US exchange venue, while Swift checks require every blank-edge case to carry an explicit classification. A future loss of either calendar lineage or fallback visibility therefore fails focused tests instead of reverting to an unexplained blank plan.
