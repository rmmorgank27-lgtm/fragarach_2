# SPEC-042 Implementation and Acceptance Report

## Result

SPEC-042 is implemented as a provider-aware extension of the SPEC-041 scheduler. Provider routing is operational sidecar state; every successful provider result still enters authority only through the existing immutable staging, validation, and ingestion path.

## Delivered

- Controlled capability profiles for Twelve Data, Yahoo Finance, Binance, and CoinGecko, including explicit approved mappings, timeframes, asset classes, credentials, entitlements, limits, row ceilings, cost, priority, and cooldown policy.
- Missing-edge acquisition plans with deterministic selection by priority, cost, health, request count, and stable provider identifier.
- Independent thread-safe sliding-window budgets driven by a monotonic clock, persisted without credentials or response bodies, with Twelve Data capped at 55 calls per minute.
- Sequential provider execution, bounded request chunking, classified failover, per-boundary attempt control, health degradation, cooldown, and isolated lane failures.
- A persistent controlled queue ordered by retry state, missed boundaries, expected edge, and lane, plus timeframe rotation for bounded-work starvation prevention.
- Deduplicated manual acquisition requests with Required, Acknowledged, Resolved, and Dismissed states. Resolution requires the canonical edge to reach the requested boundary; file selection alone cannot resolve a request.
- Scheduler monitor contract `fragarach_ii.scheduler_monitor.v2`, retaining all version 1 fields and adding providers, rate budgets, acquisition queue, routing decisions, manual requests, and lane routing detail.
- Native provider-health, queue, manual-request, and lane-detail surfaces. Open Manage Data pre-fills symbol, timeframe, and required range; Dismiss updates operational state.
- Normal app lifecycle startup, bounded one-task startup catch-up, live monitor emission, authority/estate refresh on revision change, and clean scheduler termination.

## Automated verification

- 12 focused SPEC-041/042 scheduler tests passed.
- 22 provider tests passed.
- Release `swift build -c release` passed.
- `OperationsCoreChecks`: 28 checks passed, including version 1 recovery decoding and version 2 provider/budget decoding.
- Canonical verification: integrity OK, foreign keys OK, migration checksums OK, and exactly ten authority tables.

## Signed live acceptance — 2026-07-14

- The ad-hoc signed release bundle launched and remained alive.
- All 74 commissioned lanes loaded into a version 2 live snapshot.
- Startup identified 52 due lanes, executed only one initial task, and retained a controlled queue.
- GOOGL D1 planned the exact missing range `2026-07-11` through `2026-07-13`.
- Twelve Data made one accounted attempt, failed in isolation, and deterministically failed over to Yahoo Finance.
- Yahoo Finance made one accounted attempt and immutably published one observation.
- GOOGL D1 advanced from `2026-07-10` to `2026-07-13`, its authority revision changed from `sha256:44f54156d8ba462fcbb08dbf1eb09e11737fd04923f4ecd2166632b142a35f64` to `sha256:e1fd7e791fe527ed81c32ec99a787dffb40b6c240f97f607ac15a83135e5e400`, and freshness became `Current`.
- The post-publication monitor recorded Yahoo as the current provider and publication status as `PUBLISHED`.
- Recovery validation retained 51 unique queued lanes, did not queue or repeat completed GOOGL D1 work, and made no provider call.
- The final signed bundle passed strict code-signature verification and normal quit completed without an orphan scheduler process.
- The authority database remained exactly ten tables.

No historical evidence discovery, filesystem searching, speculative repair, mapping creation, or canonical schema change was introduced.
