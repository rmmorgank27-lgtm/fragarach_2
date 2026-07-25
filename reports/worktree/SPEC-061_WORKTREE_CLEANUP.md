# SPEC-061 Worktree Cleanup

Generated: 2026-07-17T13:25:11Z

## Current State Capture

Command: `git branch --show-current`

```text
main
```

Command: `git rev-parse --show-toplevel`

```text
/Users/raymorgan/VSC/Fragarach_2
```

Command: `git status --short` after staging the SPEC-061 identified set, before staging this report.

```text
 M .gitignore
 M README.md
 M Sources/FragarachII/App/FragarachIIApp.swift
M  Sources/FragarachII/Stores/ConsoleStore.swift
 M Sources/FragarachII/Support/TruthPresentation.swift
 M Sources/FragarachII/Views/ContentView.swift
M  Sources/FragarachII/Views/DataOperationsView.swift
 M Sources/FragarachII/Views/DiscoverMarketView.swift
 M Sources/FragarachII/Views/MarketHistoryView.swift
 M Sources/FragarachII/Views/OperationsView.swift
 M Sources/FragarachII/Views/SystemWorkspaceView.swift
 M Sources/FragarachII/Views/TruthConsoleView.swift
 M Sources/FragarachII/Views/TruthContextDetailView.swift
 M Sources/FragarachII/Views/TruthDetailView.swift
 M Sources/FragarachII/Views/TruthEstateSummaryView.swift
 M Sources/FragarachII/Views/TruthMatrixView.swift
 M Sources/OperationsCore/ControlledInputs.swift
 M Sources/OperationsCore/EstateHierarchy.swift
M  Sources/OperationsCore/Models.swift
M  Sources/OperationsCore/ProcessBridge.swift
 M Sources/OperationsCoreChecks/main.swift
 M config/calendars/calendar_registry.v1.json
 M config/calendars/crypto_d1.v1.json
 M config/calendars/fx_d1.v1.json
 M config/calendars/metals_d1.v1.json
 M pyproject.toml
A  reports/worktree/SPEC-061_scheduler_daemon_untracked.patch
A  reports/worktree/SPEC-061_scheduler_service_untracked.patch
A  reports/worktree/SPEC-061_spec060_test_untracked.patch
A  reports/worktree/SPEC-061_tracked_changes.patch
 M script/build_and_run.sh
 M src/fragarach_ii/authority_service.py
 M src/fragarach_ii/calendars/models.py
 M src/fragarach_ii/calendars/registry.py
 M src/fragarach_ii/calendars/rules.py
 M src/fragarach_ii/calendars/sessions.py
M  src/fragarach_ii/commands/acquire.py
 M src/fragarach_ii/commands/ingest_file.py
 M src/fragarach_ii/commands/register_instrument.py
 M src/fragarach_ii/commands/search_instrument.py
 M src/fragarach_ii/commands/truth_state.py
 M src/fragarach_ii/estate_truth_service.py
 M src/fragarach_ii/external_consumer_service.py
 M src/fragarach_ii/ingestion/manual.py
 M src/fragarach_ii/ingestion/pipeline.py
 M src/fragarach_ii/lane_commissioning.py
 M src/fragarach_ii/market_discovery.py
 M src/fragarach_ii/providers/__init__.py
 M src/fragarach_ii/providers/http.py
 M src/fragarach_ii/providers/instrument_search.py
 M src/fragarach_ii/providers/resolution.py
 M src/fragarach_ii/providers/twelve_data.py
 M src/fragarach_ii/providers/twelve_data_adapter.py
 M src/fragarach_ii/providers/yahoo_finance.py
 M src/fragarach_ii/retirement.py
A  src/fragarach_ii/scheduler_daemon.py
A  src/fragarach_ii/scheduler_service.py
 M src/fragarach_ii/storage/database.py
 M src/fragarach_ii/storage/registrations.py
 M src/fragarach_ii/storage/writer.py
 M src/fragarach_ii/truth_engine.py
 M src/fragarach_ii/validation/d1_sessions.py
 M tests/calendars/test_calendar_rules.py
 M tests/ingestion/test_manual_ingestion.py
 M tests/operations/test_authority_service.py
 M tests/operations/test_estate_truth_service.py
 M tests/operations/test_external_consumer_service.py
 M tests/operations/test_market_discovery.py
 M tests/operations/test_market_registry.py
 M tests/operations/test_retirement.py
 M tests/operations/test_spec025_intraday.py
A  tests/operations/test_spec060_required_set_acquisition.py
 M tests/operations/test_truth_engine.py
 M tests/providers/test_provider_resolution.py
 M tests/providers/test_twelve_data.py
 M tests/validation/test_d1_session_validation.py
?? FRAGARACH_II_CONSTITUTION_FIX_V1.zip
?? FRAGARACH_II_CONSTITUTION_FIX_V1/
?? Sources/FragarachII/Views/DiscoverMarketComponents.swift
?? Sources/FragarachII/Views/ManageDataWorkspaceView.swift
?? Sources/FragarachII/Views/MarketLifecycleSheets.swift
?? Sources/FragarachII/Views/OverviewView.swift
?? Sources/FragarachII/Views/ProviderFactsView.swift
?? Sources/FragarachII/Views/SchedulerMonitorView.swift
?? Sources/OperationsCore/MarketDiscoveryPresentation.swift
?? Sources/OperationsCore/SchedulerBridge.swift
?? config/calendars/australian_equities_d1.v1.json
?? config/calendars/uk_equities_d1.v1.json
?? config/calendars/us_equities_d1.v1.json
?? config/providers/acquisition_orchestrator.v1.json
?? config/synthetic/
?? data/
?? docs/build_reports/
?? docs/operations/PERSISTENT_SCHEDULER_SERVICE.md
?? docs/operations/SCHEDULED_ACQUISITION.md
?? docs/reports/SPEC-040_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-041_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-042_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-043_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-044_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-045_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-046_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-047_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-048_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-049A_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-049B_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-049_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-050_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-051_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-056_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-059_IMPLEMENTATION_REPORT.md
?? docs/reports/SPEC-060_IMPLEMENTATION_REPORT.md
?? docs/reports/spec025/
?? docs/reports/spec025a/
?? docs/reports/spec040/
?? docs/reports/spec047/
?? docs/reports/spec048/
?? reports/worktree/SPEC-061_WORKTREE_CLEANUP.md
?? specs/operations/SPEC-041_SCHEDULED_ACQUISITION_AND_SCHEDULER_MONITOR.md
?? specs/operations/SPEC-042_MARKET_ACQUISITION_ORCHESTRATOR_PHASE_2.md
?? src/fragarach_ii/acquisition_orchestrator.py
?? src/fragarach_ii/adaptive_scheduler.py
?? src/fragarach_ii/commands/audit_spec025_timeframes.py
?? src/fragarach_ii/commands/cli.py
?? src/fragarach_ii/commands/credentials.py
?? src/fragarach_ii/commands/get_catalogue.py
?? src/fragarach_ii/commands/lane_freshness.py
?? src/fragarach_ii/commands/provider_facts.py
?? src/fragarach_ii/commands/scheduler.py
?? src/fragarach_ii/commands/synthetic.py
?? src/fragarach_ii/commissioning_authority.py
?? src/fragarach_ii/credentials.py
?? src/fragarach_ii/estate_timeframe_audit.py
?? src/fragarach_ii/execution_trace.py
?? src/fragarach_ii/freshness.py
?? src/fragarach_ii/history_depth.py
?? src/fragarach_ii/lane_freshness_service.py
?? src/fragarach_ii/onboarding.py
?? src/fragarach_ii/operational_schedule.py
?? src/fragarach_ii/provider_facts.py
?? src/fragarach_ii/providers/binance.py
?? src/fragarach_ii/providers/coingecko.py
?? src/fragarach_ii/providers/maximum_history.py
?? src/fragarach_ii/providers/orchestrated.py
?? src/fragarach_ii/providers/yahoo_symbols.py
?? src/fragarach_ii/scheduler_integrity.py
?? src/fragarach_ii/synthetic_repository.py
?? src/fragarach_ii/twelve_data_credit.py
?? tests/conftest.py
?? tests/operations/test_spec025a_initial_fetch.py
?? tests/operations/test_spec040_freshness.py
?? tests/operations/test_spec041_scheduler.py
?? tests/operations/test_spec042_orchestrator.py
?? tests/operations/test_spec044_queue_drain.py
?? tests/operations/test_spec045_synthetic_repository.py
?? tests/operations/test_spec046_operational_integrity.py
?? tests/operations/test_spec047_unified_acquisition.py
?? tests/operations/test_spec048_provider_facts.py
?? tests/operations/test_spec049_scheduler_service.py
?? tests/operations/test_spec049a_scheduler_recovery.py
?? tests/operations/test_spec049b_manual_reconciliation.py
?? tests/operations/test_spec050_provider_authority_regression.py
?? tests/operations/test_spec051_caodt_lineage.py
?? tests/operations/test_spec052_adaptive_scheduler.py
?? tests/operations/test_spec053_commissioning_priority.py
?? tests/operations/test_spec054_credential_authority.py
?? tests/operations/test_spec055_execution_trace.py
?? tests/operations/test_spec056_atomic_onboarding.py
?? tests/operations/test_spec056_twelve_data_throughput.py
?? tests/operations/test_spec057_legacy_provider_recovery.py
?? tests/operations/test_spec058_manual_commissioning_separation.py
?? tests/operations/test_spec059_indices_update_planning.py
?? tests/operations/test_spec060_scheduler_health.py
?? tests/providers/test_yahoo_finance.py
?? tests/providers/test_yahoo_symbols.py
```

## Critical File Investigation

Initial pre-staging command: `git ls-files src/fragarach_ii/scheduler_service.py src/fragarach_ii/scheduler_daemon.py`

```text
(no output)
```

Initial pre-staging command: `git log --oneline -- src/fragarach_ii/scheduler_service.py src/fragarach_ii/scheduler_daemon.py`

```text
(no output)
```

Initial pre-staging command: `git status --short -- src/fragarach_ii/scheduler_service.py src/fragarach_ii/scheduler_daemon.py`

```text
?? src/fragarach_ii/scheduler_daemon.py
?? src/fragarach_ii/scheduler_service.py
```

Post-tracking command: `git status --short -- src/fragarach_ii/scheduler_service.py src/fragarach_ii/scheduler_daemon.py`

```text
A  src/fragarach_ii/scheduler_daemon.py
A  src/fragarach_ii/scheduler_service.py
```

Command: `find . \( -name "scheduler_service.py" -o -name "scheduler_daemon.py" \) -print`

```text
./src/fragarach_ii/scheduler_daemon.py
./src/fragarach_ii/scheduler_service.py
```

Classification:

| File | Classification | Decision |
| --- | --- | --- |
| `src/fragarach_ii/scheduler_service.py` | new intended canonical source | Added to git index as a new source file. No tracked predecessor or duplicate path exists by filename. |
| `src/fragarach_ii/scheduler_daemon.py` | new intended canonical source | Added to git index as a new source file. No tracked predecessor or duplicate path exists by filename. |

## Execution Path Evidence

- LaunchAgent/service path: `src/fragarach_ii/scheduler_daemon.py` defines `PersistentSchedulerRuntime`, `SERVICE_LABEL`, and `launch_agent_definition`, whose `ProgramArguments` run `-m fragarach_ii.commands.scheduler`.
- Scheduler CLI path: `src/fragarach_ii/commands/scheduler.py` imports `PersistentSchedulerRuntime` and service lifecycle helpers from `fragarach_ii.scheduler_daemon`, and scheduler controls from `fragarach_ii.scheduler_service`.
- Acquire CLI path: `src/fragarach_ii/commands/acquire.py` imports `ServicePaths`, `make_command`, `ownership_is_active`, and `send_service_request` from `scheduler_daemon`; it imports `run_operator_fetch` and `run_required_set_fetch` from `scheduler_service`.
- Required-set command path: `src/fragarach_ii/commands/acquire.py` exposes `--required-set`, sends `OPERATOR_FETCH_REQUIRED_SET` to the service when ownership is active, and calls `run_required_set_fetch` in standalone recovery mode.
- Swift path: `Sources/OperationsCore/ProcessBridge.swift` maps `.acquireRequiredSet` to `fragarach_ii.commands.acquire --required-set`; `Sources/FragarachII/Views/DataOperationsView.swift` exposes `Fetch Required Set`; `ConsoleStore.swift` treats `.acquireRequiredSet` as provider acquisition.
- Tests: `tests/operations/test_spec060_required_set_acquisition.py` imports `required_set_acquisition_plan` and `run_required_set_fetch` from `fragarach_ii.scheduler_service`.

## Backup Patches

Created before staging by the SPEC-061 requested commands:

- `reports/worktree/SPEC-061_tracked_changes.patch`
- `reports/worktree/SPEC-061_scheduler_service_untracked.patch`
- `reports/worktree/SPEC-061_scheduler_daemon_untracked.patch`
- `reports/worktree/SPEC-061_spec060_test_untracked.patch`

## Tracking Decisions

| Path | Status | Decision |
| --- | --- | --- |
| `Sources/FragarachII/Stores/ConsoleStore.swift` | tracked modified | Intentional SPEC-059/SPEC-060 operations surface; staged. |
| `Sources/FragarachII/Views/DataOperationsView.swift` | tracked modified | Intentional Acquire & Import required-set UI; staged. |
| `Sources/OperationsCore/Models.swift` | tracked modified | Intentional operation model/status decoding support; staged. |
| `Sources/OperationsCore/ProcessBridge.swift` | tracked modified | Intentional `.acquireRequiredSet` CLI bridge; staged. |
| `src/fragarach_ii/commands/acquire.py` | tracked modified | Intentional CLI/service route for required-set acquisition; staged. |
| `src/fragarach_ii/scheduler_daemon.py` | new canonical source | Added and staged. |
| `src/fragarach_ii/scheduler_service.py` | new canonical source | Added and staged. |
| `tests/operations/test_spec060_required_set_acquisition.py` | new regression test | Added and staged. |
| Other dirty files | mixed modified/untracked backlog | Not staged by SPEC-061. Left untouched. |

## Clean Scoped Diff

Command: `git diff --stat --cached`

```text
 Sources/FragarachII/Stores/ConsoleStore.swift      |  477 +-
 Sources/FragarachII/Views/DataOperationsView.swift |  219 +-
 Sources/OperationsCore/Models.swift                |  628 +-
 Sources/OperationsCore/ProcessBridge.swift         |  115 +-
 .../SPEC-061_scheduler_daemon_untracked.patch      | 1956 +++++
 .../SPEC-061_scheduler_service_untracked.patch     | 4164 ++++++++++
 .../worktree/SPEC-061_spec060_test_untracked.patch |  330 +
 reports/worktree/SPEC-061_tracked_changes.patch    | 8028 ++++++++++++++++++++
 src/fragarach_ii/commands/acquire.py               |   94 +-
 src/fragarach_ii/scheduler_daemon.py               | 1950 +++++
 src/fragarach_ii/scheduler_service.py              | 4158 ++++++++++
 .../test_spec060_required_set_acquisition.py       |  324 +
 12 files changed, 22335 insertions(+), 108 deletions(-)
```

Command: `git diff --cached --name-only`

```text
Sources/FragarachII/Stores/ConsoleStore.swift
Sources/FragarachII/Views/DataOperationsView.swift
Sources/OperationsCore/Models.swift
Sources/OperationsCore/ProcessBridge.swift
reports/worktree/SPEC-061_scheduler_daemon_untracked.patch
reports/worktree/SPEC-061_scheduler_service_untracked.patch
reports/worktree/SPEC-061_spec060_test_untracked.patch
reports/worktree/SPEC-061_tracked_changes.patch
src/fragarach_ii/commands/acquire.py
src/fragarach_ii/scheduler_daemon.py
src/fragarach_ii/scheduler_service.py
tests/operations/test_spec060_required_set_acquisition.py
```

Command: `git diff --stat`

```text
 .gitignore                                         |   1 +
 README.md                                          |   8 +-
 Sources/FragarachII/App/FragarachIIApp.swift       |   7 +-
 .../FragarachII/Support/TruthPresentation.swift    |   9 +-
 Sources/FragarachII/Views/ContentView.swift        |  33 +-
 Sources/FragarachII/Views/DiscoverMarketView.swift | 575 +++++++++++++++++--
 Sources/FragarachII/Views/MarketHistoryView.swift  |  26 +
 Sources/FragarachII/Views/OperationsView.swift     |   2 +-
 .../FragarachII/Views/SystemWorkspaceView.swift    |   4 +-
 Sources/FragarachII/Views/TruthConsoleView.swift   |  43 +-
 .../FragarachII/Views/TruthContextDetailView.swift |   7 +-
 Sources/FragarachII/Views/TruthDetailView.swift    |  20 +-
 .../FragarachII/Views/TruthEstateSummaryView.swift |   9 +-
 Sources/FragarachII/Views/TruthMatrixView.swift    |  58 +-
 Sources/OperationsCore/ControlledInputs.swift      | 260 ++++++++-
 Sources/OperationsCore/EstateHierarchy.swift       |  15 +-
 Sources/OperationsCoreChecks/main.swift            | 611 ++++++++++++++++++++-
 config/calendars/calendar_registry.v1.json         |   7 +-
 config/calendars/crypto_d1.v1.json                 |  16 +-
 config/calendars/fx_d1.v1.json                     |   6 +-
 config/calendars/metals_d1.v1.json                 |   6 +-
 pyproject.toml                                     |   4 +-
 script/build_and_run.sh                            |  17 +-
 src/fragarach_ii/authority_service.py              |  64 ++-
 src/fragarach_ii/calendars/models.py               |   6 +-
 src/fragarach_ii/calendars/registry.py             |  21 +-
 src/fragarach_ii/calendars/rules.py                |  84 +++
 src/fragarach_ii/calendars/sessions.py             |   8 +-
 src/fragarach_ii/commands/ingest_file.py           |   7 +
 src/fragarach_ii/commands/register_instrument.py   |  16 +-
 src/fragarach_ii/commands/search_instrument.py     |   5 +-
 src/fragarach_ii/commands/truth_state.py           |   4 +
 src/fragarach_ii/estate_truth_service.py           | 545 +++++++++++++++++-
 src/fragarach_ii/external_consumer_service.py      | 204 +++++++
 src/fragarach_ii/ingestion/manual.py               |   7 +
 src/fragarach_ii/ingestion/pipeline.py             |  41 +-
 src/fragarach_ii/lane_commissioning.py             | 238 +++++++-
 src/fragarach_ii/market_discovery.py               | 122 +++-
 src/fragarach_ii/providers/__init__.py             |   3 +
 src/fragarach_ii/providers/http.py                 |  10 +
 src/fragarach_ii/providers/instrument_search.py    |   4 +-
 src/fragarach_ii/providers/resolution.py           |  90 +--
 src/fragarach_ii/providers/twelve_data.py          | 235 +++++---
 src/fragarach_ii/providers/twelve_data_adapter.py  |  22 +-
 src/fragarach_ii/providers/yahoo_finance.py        |  31 +-
 src/fragarach_ii/retirement.py                     |  21 +-
 src/fragarach_ii/storage/database.py               |  69 ++-
 src/fragarach_ii/storage/registrations.py          |   5 +-
 src/fragarach_ii/storage/writer.py                 |  29 +-
 src/fragarach_ii/truth_engine.py                   | 130 ++++-
 src/fragarach_ii/validation/d1_sessions.py         |   9 +-
 tests/calendars/test_calendar_rules.py             |  30 +
 tests/ingestion/test_manual_ingestion.py           |   7 +
 tests/operations/test_authority_service.py         |  52 +-
 tests/operations/test_estate_truth_service.py      |  44 +-
 tests/operations/test_external_consumer_service.py |  31 ++
 tests/operations/test_market_discovery.py          |  50 ++
 tests/operations/test_market_registry.py           |   2 +-
 tests/operations/test_retirement.py                |   4 +-
 tests/operations/test_spec025_intraday.py          |  15 +-
 tests/operations/test_truth_engine.py              |  19 +-
 tests/providers/test_provider_resolution.py        |  82 ++-
 tests/providers/test_twelve_data.py                |  94 +++-
 tests/validation/test_d1_session_validation.py     | 127 ++++-
 64 files changed, 3868 insertions(+), 463 deletions(-)
```

## Remaining Dirty Work

After staging the SPEC-061 identified set, `git status --short | wc -l` returned 174 before this report was staged, and 175 after this report was staged. Excluding the staged SPEC-061/SPEC-060 files, backup patches, and this report, 162 dirty status entries remain. They were not reverted, removed, or staged.

## Verification Results

- `swift run OperationsCoreChecks` passed. Output ended with `OperationsCoreChecks: 38 checks passed`.
- `swift build -c release --product FragarachII` passed. Output ended with `Build of product 'FragarachII' complete!`.
- `PYTHONPATH=src python3 -m pytest tests/operations/test_spec047_unified_acquisition.py tests/operations/test_spec060_required_set_acquisition.py -q` passed with `22 passed in 5.46s`.
- `./script/build_and_run.sh --verify` passed. Output ended with `Fragarach II signed bundle launched and remained alive`.

## Summary

`scheduler_service.py` and `scheduler_daemon.py` were not tracked and had no git history at their paths. They are classified as new intended canonical source and are staged as added files. No duplicate scheduler file path was found. Existing runtime, CLI, Swift bridge, UI, and regression-test paths execute through these files.
