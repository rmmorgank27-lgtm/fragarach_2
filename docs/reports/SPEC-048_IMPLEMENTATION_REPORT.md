# SPEC-048 Implementation Report

## Outcome

SPEC-048 is implemented and accepted. Fragarach now retrieves Twelve Data representation facts once per canonical representation/provider pair, records timeframe capabilities separately, refreshes the shared acquisition projection, and presents only genuine economic ambiguity to the operator.

The operational evidence journal is the mode-0600 sidecar `<authority database>.provider-facts.json`. It is non-canonical, atomically replaced, and contains no credential or full provider response. The canonical database remains the same ten-table authority.

## Delivered repair

- `provider_facts.py` implements bounded Twelve Data reference lookup, exact Forex/metal matching, representation-scoped mappings, four independent timeframe facts, read-only probes, controlled failures, decision recording, prior D1 mapping provenance, and reconciliation.
- `acquisition_orchestrator.py` makes the resolved facts authoritative for Discover, Acquire & Import, Scheduler, Estate, manual work, and provider diagnostics.
- The signed app, provider resolver, manual Scheduler controls, and app-owned Scheduler resolve the same credential chain: process environment, macOS Keychain, then the approved external credential file. Only `Configured`, `Missing`, or `Invalid` is exposed.
- `scheduler_integrity.py` classifies a CFD absent from the active Estate registry as retired/non-actionable without changing its registration or evidence.
- Manage Data → System → Provider Facts provides automatic mappings, candidate review, credential repair, lookup retry, bounded probes, reconciliation, and retired history using native SwiftUI controls.

The provider contract choices were verified against Twelve Data's official [Forex coverage](https://twelvedata.com/forex), [historical price guidance](https://support.twelvedata.com/en/articles/5656039-how-to-get-historical-prices), and [API usage header guidance](https://support.twelvedata.com/en/articles/5713553-control-over-api-usage).

## Live acceptance

- Six standard FX representations resolved automatically: `AUDSGD`, `EURUSD`, `GBPAUD`, `GBPJPY`, `USDCAD`, and `USDCHF`.
- Each mapping serves `M5`, `M30`, `H1`, and `D1`; 24 capability facts are supported.
- Prior D1 confirmed-evidence mappings were retained in resolution evidence with their ingest-run identifiers and migrated to representation scope.
- `DJI` and `USOIL` remain as two representation/provider decisions. The USOIL candidate screen distinguishes Twelve Data `WTI/USD` Energy Resource from unrelated stocks and ETFs.
- A live and a signed-native `EURUSD/M5` probe requested three rows, returned two closed rows, excluded one open row, reported one API credit, recorded `canonical_publication: NONE`, and left the database SHA-256 unchanged.
- Discover, Acquire projection, Scheduler, and Estate all showed `EUR/USD`, `EXACT_REPRESENTATION`, `SUPPORTED`, and `ELIGIBLE` without restart.
- `XAGUSDCFD` produced zero active Scheduler lanes and zero capability rows; it appeared only under Retired / Non-Actionable.
- The final signed bundle passed strict signature verification, launched with its app-owned Scheduler child, and quit with no orphan application or Scheduler process.

## Verification

- Focused Python verification: 45 passed.
- Native core verification: 31 checks passed.
- Swift debug build: passed.
- Swift release build and signed app bundle: passed.
- `codesign --verify --deep --strict`: passed.
- Canonical database: 10 tables, `integrity_check=ok`, zero foreign-key violations.
- Canonical database SHA-256 before and after provider resolution/probes: `4b438948e42d92ed18d8b89f28be49ab9ef5175d6c87a16d71920c1995dab304`.

The before/after counts are recorded in [SPEC-048_RECONCILIATION.md](spec048/SPEC-048_RECONCILIATION.md).
