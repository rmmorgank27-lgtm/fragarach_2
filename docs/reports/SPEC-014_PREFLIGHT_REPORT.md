# SPEC-014 Preflight Report

Date: 2026-07-12

1. Acquire used a free-text `asset` state in `AcquireView` and always emitted D1.
2. Import Evidence used view-local static picker data.
3. The three entries were the literal Swift array `AUDUSD`, `XAUUSD`, `BTCUSD`; they were not authority-derived.
4. Active registration data is in immutable `instrument_registrations`; lifecycle exclusion is represented by `LANE_SUPERSEDED` authority events. `SQLiteReadService` already projected active lane state and the Estate Truth command projected active Truth.
5. `ConsoleStore.run` calls `refresh()` after every authority mutation. The new selector is rebuilt from that refreshed read-only snapshot and has no startup cache.
6. Acquisition CLI arguments are database, provider, asset, timeframe, from date, inclusive through date, conflict mode, and JSON output.
7. Registration and database checks constrain timeframe to D1. The Twelve Data contract has a provider maximum of 5,000 rows and a Fragarach request ceiling of 4,000 rows.
8. No approved history pagination, earliest-boundary, terminal-stop, or resume contract exists.
9. No approved update-overlap authority exists.
10. D1 validation/calendar authority exists, but acquisition exposes no operational latest-completed-bar resolver.
11. Manual import uses `fragarach_ii.commands.ingest_file` with file, symbol, timeframe, and merge mode.
12. Provider and manual sources both enter the existing immutable raw-block, ingestion, provenance, merge, and Truth stores; no second pipeline is required.
13. SPEC-013 is exposed by `retire_instrument` plan and confirmed execution commands, bridged by `retirementPlan` and `retireInstrument` intents.
14. Retirement existed only in Discover Market details; Acquire and Import had no native lifecycle entry point.
15. Successful operations call `ConsoleStore.refresh()`, reloading both Estate Truth and the database snapshot.
16. A UI plan can coordinate lanes without schema change, but authority currently permits only D1 and the execution service is single-lane.
17. Unsupported lanes are blocked exactly by the `instrument_registrations.timeframe = 'D1'` database check, registration validation, and D1-only acquisition contract.

No schema or migration change was made.
