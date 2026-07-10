# SPEC-004 Live Provider Acceptance — Blocked Report

**Report date:** 2026-07-11

**Authority:** `data/runtime/spec002_real_evidence_acceptance.sqlite3`

**Status:** Blocked before network access

## Outcome

Live Twelve Data acceptance was not performed. `TWELVE_DATA_API_KEY` was absent, and no operator-approved live proof range was supplied. The acquisition command stopped at its credential gate with:

```json
{"code":"MISSING_CREDENTIAL","error":"required provider credential is absent","evidence_committed":false}
```

No HTTP request was made. No writer lock or authority transaction was entered. No live response, raw block, ingest run, canonical bar, provenance event, lane-state change, or validation-summary change was created.

This is a factual blocked result, not a live-provider pass. Fragarach II remains a **CANDIDATE AUTHORITY**. No consumer migration is authorized.

## Pre-attempt safety backup

A SQLite backup was created and verified before the credential-gate attempt:

```text
data/runtime/spec004_pre_live_backup.sqlite3
```

| Fact | Value |
|---|---|
| Size | 26,583,040 bytes |
| SHA-256 | `ad570de6ea23773d86487d944006105dcde60d8e65e52903becb69af7e0725be` |
| Integrity check | `ok` |
| Foreign-key violations | 0 |

The backup is runtime evidence and remains intentionally outside Git.

## Before-and-after authority proof

The acceptance database was byte-identical before and after the stopped attempt:

| Fact | Before | After |
|---|---:|---:|
| File size | 26,583,040 | 26,583,040 |
| File mtime (ns) | 1783722716457020580 | 1783722716457020580 |
| File SHA-256 | `969e88a3f3bbf97a5c975839c6d6f5cf97414cb3cd7a080a36e574679dab0a96` | identical |
| Canonical bars | 33,547 | 33,547 |
| Raw blocks | 3 | 3 |
| Provenance events | 67,094 | 67,094 |
| Ingest runs | 6 | 6 |
| Lane rows | 3 | 3 |

The application table set remained exactly:

```text
bars
ingest_runs
lane_state
provenance
raw_blocks
rollup_state
schema_migrations
```

`PRAGMA integrity_check` returned `ok`; `PRAGMA foreign_key_check` returned no rows. Per-lane counts, high-water marks, and all three persisted validation result checksums were unchanged.

## Source-evidence invariants

The three operator-selected source files were inspected by metadata and hash only for this comparison. Their bytes, modes, and mtimes remained unchanged:

| Source | Bytes | SHA-256 |
|---|---:|---|
| `data/inbox/FX_AUDUSD, 1D_8cdf5.csv` | 601,444 | `562be4abe8eb712e380c3515aa2845d380d3581ae309720135b31f94e398c5f5` |
| `data/inbox/FX_XAUUSD, 1D_963fd.csv` | 505,614 | `f4e12f8a823cd576c93b3fc364bfea1b3dd0a91fa47a813e0d3b2073f8b9165e` |
| `data/inbox/INDEX_BTCUSD, 1D_b7b7c.csv` | 268,168 | `573e65e61ad8c8a9320d0938aee929666ce77d8a3ccb7591fd008c8d8fdf511b` |

## Required continuation boundary

Live acceptance may resume only when an operator supplies `TWELVE_DATA_API_KEY` through the environment and explicitly approves the symbol and inclusive proof date range. The key must not be pasted into a tracked file, command argument, report, or chat transcript.

Until then, no live-provider acceptance, live idempotency, live canonical reconciliation, or live operational trust is claimed. **Operations is King.**
