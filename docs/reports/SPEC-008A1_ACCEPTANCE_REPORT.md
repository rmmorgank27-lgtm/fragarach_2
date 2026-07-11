# SPEC-008A1 Acceptance Report

**Date:** 2026-07-11
**Final Outcome:** PASS
**Push:** NOT PERFORMED

## Acceptance decision

The single generic immutable authority ledger survives implementation without violating the Constitution or weakening legacy authority.

```text
Application tables: exactly 10
Original tables preserved: exactly 9
Sole new table: authority_events
Migration 6: accepted
Bootstrap: accepted
```

## Required proof

| Requirement | Result |
|---|---|
| Exact ten-table boundary | PASS |
| Original nine tables unchanged | PASS |
| Existing primary keys unchanged | PASS |
| Migrations 1–5 checksums unchanged | PASS |
| Migration 6 checksum verified | PASS — `a8b2645460c5f62bdf5dd9d7cc0e6ae25d477ca755fd9ffb0d1efdb238e94cf1` |
| Existing registrations and lanes preserved | PASS — 3 and 3, exact digests unchanged |
| Accepted D1 evidence preserved | PASS — 33,551 bars, exact digest unchanged |
| Ledger update/delete rejection | PASS |
| Canonical JSON/checksum verification | PASS |
| Exact replay/idempotency | PASS — 6 bootstrap events unchanged on replay |
| Supersession/non-forking | PASS |
| Conflict/rejection retention | PASS |
| Multiple provider mappings | PASS |
| Effective/as-of reconstruction | PASS |
| Affected-path-only operation | PASS |
| 9 families × 4 fixture lanes | PASS — 36 declarations in isolated databases |
| H1/M30/M5 declaration without activation | PASS |
| Provider limits 5,000/4,000 distinguished | PASS |
| Read-only native inspection | PASS |
| Runtime integrity | PASS — `ok`, 0 FK violations |
| Secret scan | PASS — only intentional fake fixture literal matched |
| Push | PASS — none |

## Test and runtime summary

- Python unit/integration/regression suite: **101 passed**.
- Swift build: **passed**.
- OperationsCoreChecks: **11 passed**.
- Native application bundle build and launch verification: **passed**.
- Runtime file SHA-256 after accepted migration/bootstrap: `b9ceafa7b714ad202a4b067f6f11d9bf74b6e54b786a4526100b439a6a10d38b`.
- Pre-migration backup SHA-256: `a36f1c438b228a9597a07a09cff4849dc7bfe0b7f65d8fd13a2098d81e3d78c7`.

## Current authority scope

The runtime ledger contains six legacy-binding events. Their absent SPEC-008A metadata remains explicit `UNRESOLVED`; no new Stage A registration or intraday lane was promoted or activated. Existing D1 evidence remains readable.

## Checkpoint

One reviewed local checkpoint is required and is created after this report is finalized. Its exact Git SHA is reported in the final Codex handoff because a commit cannot truthfully contain its own SHA without changing that SHA. Runtime databases, backups, credentials, unrelated user files, and generated application bundles are excluded.

No remote push, branch publication, pull request, release, or deployment was performed.

**Operations is King.**
