# SPEC-056 — Atomic Provider-Aware Symbol Onboarding

## Result

Fragarach II acceptance is complete. The Morphix FC continuation is blocked by
the running Morphix process's publication-refresh contract; no prohibited
Refresh, cache clear, rebuild, or restart was performed.

## Deterministic root cause

Discover carried the reviewed representation in its registration candidate,
but registration persisted only the canonical row. Existing unmapped symbols
could not be completed because the immutable registration checksum correctly
rejected a second, provider-enriched identity, while unified acquisition read
provider authority from the separate provider-facts projection. CAT therefore
remained `REGISTERED_UNMAPPED` and Yahoo `CAT` never became approved provider
authority.

The native Initial History path independently defaulted to the UI's reviewed
date range (normally 30 days) rather than the operational expected edge and the
governed stock D1 ten-year horizon.

## Repair

- Added one provider-aware onboarding operation that validates the reviewed
  representation and D1 capability, persists provider facts, performs canonical
  registration when needed, and requires unified-authority readback before
  reporting success.
- Provider-fact writes are restored byte-for-byte if canonical registration
  fails. A provider-fact failure occurs before registration. Replays with the
  same identity and representation do not duplicate a row, mapping, or revision.
- Existing CAT completion preserves its immutable identity checksum and original
  `registered_at_utc`; its effective provider authority now comes from the
  approved representation-scoped fact instead of rewriting the legacy row.
- Discover reports `PROVIDER_SETUP_INCOMPLETE` / `Complete Provider Setup` for
  an existing unmapped symbol and changes to `OPEN_EXISTING` only after approved
  mapping readback.
- Default provider onboarding now requires a reviewed representation. The old
  unmapped writer remains only behind the explicit `--manual-only` option.
- Fetch Initial History now resolves the expected edge through operational
  calendar authority and derives governed bounds independently of Custom Range.
  Stock D1 uses ten years; CAT resolves to `2016-07-15 → 2026-07-15`.
- Estate publication now exposes provider-fact and composite Estate revisions
  without changing canonical Truth authority.

## Focused verification

- `tests/operations/test_spec056_atomic_onboarding.py`: **5 passed**
  - fresh exact Yahoo onboarding and authoritative readback;
  - idempotent replay;
  - existing incomplete CAT completion without recreation;
  - mapping-write failure with no orphan registration;
  - registration-write failure with byte-exact provider-fact rollback;
  - unreviewed onboarding guard.
- `FOCUSED_SPEC056=1 swift run OperationsCoreChecks`: **1 focused check passed**
  - Yahoo selection;
  - nil canonical edge and resolved expected edge;
  - ten-year CAT bounds;
  - manual 30-day range cannot override Initial History;
  - displayed bounds equal dispatched bounds;
  - native `Complete Provider Setup` presentation.
- One release build: `./script/build_and_run.sh verify`: **passed**.
- Ad-hoc bundle signature verification: **valid on disk and satisfies its
  designated requirement**.
- Signed native smoke: **passed**. The released app displayed CAT as Active and
  Commissioned, Yahoo Finance as provider, `Fetch Initial History`, historical
  depth `10 years`, and request bounds `2016-07-15 → 2026-07-15`.

No full regression suite was run.

## Live CAT acceptance

| Fact | Verified value |
|---|---|
| Canonical registration count | 1 |
| Original registration time | `2026-07-16T02:18:01.950622+00:00` |
| Identity checksum | `89ebb5bc2dbbdf0866409e1fd56cb993d5a10b4eddeb15b0db5feb3fbfd6cce5` |
| Approved provider | `YAHOO_FINANCE` |
| Provider symbol / mapping | `CAT` / `EXACT_REPRESENTATION` |
| Provider status / D1 capability | `OPERATOR_RESOLVED` / supported |
| Unified eligibility | `ELIGIBLE` |
| Provider-fact revision | 22 |
| Canonical D1 bars | 2,513 |
| Canonical range | `2016-07-15 → 2026-07-15` |
| Scheduler / freshness | `Current` / `Current` |
| Latest canonical observation | `2026-07-15T00:00:00+00:00` |
| SPEC-018 | `AVAILABLE`, 2,513 bars, same range and CAODT |
| Estate revision | `sha256:53e0da7a18f4a56bb8b15aa304731df63b0770981f7d74ec536e56b4d7905d1e` |

## Morphix continuation boundary

The already-running Morphix FCv1 process remained PID 99705 throughout. Live
inspection after CAT publication showed 25 active symbols and no CAT row; CAT
should have appeared alphabetically between AAPL and GBPAUD.

The running app's source has no cross-process authority watcher or polling loop.
It rebuilds its presentation only on startup, operator Reload, an in-process
`NotificationCenter` event, or completion of an engine run. A Fragarach
authority change cannot deliver that process-local notification. Since CAT is
not in the running publication, the UI correctly prevents selecting CAT and
therefore cannot launch AAFE, SEE, or r3L Classic or publish CAT in Explore.

Running those engines would require Refresh/restart or a Morphix-side
cross-process observation repair. Both are outside SPEC-056 scope and the
explicit continuation constraints, so no engine result was fabricated.
