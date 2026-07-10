# SPEC-002 Real-Evidence Acceptance Proof

**Proof date:** 2026-07-10

**Repository:** `/Users/raymorgan/VSC/fragarach_2`

**Acceptance database:** `data/runtime/spec002_real_evidence_acceptance.sqlite3`

**Status:** Candidate authority runtime evidence; not production readiness

## Objective and boundary

Three operator-selected D1 files from `data/inbox` were inspected without modification, ingested through the implemented SPEC-002 manual pipeline, repeated byte-for-byte for idempotency, and reconciled against canonical storage through the read-only connection contract.

No legacy Fragarach path was accessed. No SPEC-003 work, automated provider, calendar, gap analysis, rollup, scheduler, service, or consumer integration was started.

## Source immutability evidence

Metadata and SHA-256 were captured before inspection and after all ingestion and verification. Size, inode, modification timestamp, mode, and checksum were identical at both observations.

| Explicit command identity | Source file | Bytes | SHA-256 |
|---|---|---:|---|
| AUDUSD D1 | `FX_AUDUSD, 1D_8cdf5.csv` | 601,444 | `562be4abe8eb712e380c3515aa2845d380d3581ae309720135b31f94e398c5f5` |
| XAUUSD D1 | `FX_XAUUSD, 1D_963fd.csv` | 505,614 | `f4e12f8a823cd576c93b3fc364bfea1b3dd0a91fa47a813e0d3b2073f8b9165e` |
| BTCUSD D1 | `INDEX_BTCUSD, 1D_b7b7c.csv` | 268,168 | `573e65e61ad8c8a9320d0938aee929666ce77d8a3ccb7591fd008c8d8fdf511b` |

The files were treated as read-only CSV inputs. Their exact payloads, lengths, filenames, and digests were independently compared with the stored `raw_blocks` values and matched byte-for-byte.

## Boundary compatibility finding

All three files contained physical headers:

```text
time,open,high,low,close
```

SPEC-002 defines `timestamp` as the logical staging field. Before database creation, the manual CSV boundary was boundedly amended to map physical `time` to logical `timestamp`. Supplying both headers is rejected as a duplicate logical field. This mapping does not change source bytes, infer symbol identity, implement provider acquisition, or alter post-staging behavior.

The mapping and duplicate-header rule pass the complete 34-test suite and are checkpointed at:

```text
4fc0c51c5edc5f39893810b38e96ed71d0850738
```

## Structural preflight

The exact source bytes were staged with explicit operator-command identities and `provider=MANUAL` before database mutation.

| Lane | Source rows | Staged | Exact duplicates | Conflicting duplicates | Rejections | First key | Last key |
|---|---:|---:|---:|---:|---:|---|---|
| AUDUSD D1 | 14,260 | 14,260 | 0 | 0 | 0 | 1971-01-04 | 2026-07-10 |
| XAUUSD D1 | 13,256 | 13,256 | 0 | 0 | 0 | 1970-02-27 | 2026-07-10 |
| BTCUSD D1 | 6,031 | 6,031 | 0 | 0 | 0 | 2009-10-05 | 2026-07-10 |

This is structural evidence only. The early dates, market-session meaning, expected coverage, and economic correctness were not interpreted.

## Runtime commands

Each file was imported twice using the same command shape and explicit identity:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python3 -m fragarach_ii.commands.ingest_file \
  --database data/runtime/spec002_real_evidence_acceptance.sqlite3 \
  --file "$selected_file" \
  --symbol "$symbol" \
  --timeframe D1 \
  --provider MANUAL \
  --merge-mode preserve \
  --json
```

The database path did not exist before the first command. No correction mode was used.

## First-import results

| Lane | Ingest run | Inserted | Unchanged | Corrected | Preserved conflicts | Rejected | Raw reused |
|---|---|---:|---:|---:|---:|---:|---|
| AUDUSD D1 | `f04fae4bacf945e6878466f27299a4f5` | 14,260 | 0 | 0 | 0 | 0 | false |
| XAUUSD D1 | `04657017d5104f19a2a7be7fd9b4dc56` | 13,256 | 0 | 0 | 0 | 0 | false |
| BTCUSD D1 | `d8dd842afe3b46baa899eacc1b6c2a48` | 6,031 | 0 | 0 | 0 | 0 | false |

All three runs ended `committed`. Each accepted count equalled its source and staged count.

## Repeat-import idempotency

| Lane | Repeat ingest run | Inserted | Unchanged | Corrected | Preserved conflicts | Rejected | Raw reused |
|---|---|---:|---:|---:|---:|---:|---|
| AUDUSD D1 | `ca3e2763299d40e2adf8d20b2b01c3ca` | 0 | 14,260 | 0 | 0 | 0 | true |
| XAUUSD D1 | `e3c372aaf50b42c0ad681ddaeb6525b8` | 0 | 13,256 | 0 | 0 | 0 | true |
| BTCUSD D1 | `e7486fd900b0485b8316a366b4547a3a` | 0 | 6,031 | 0 | 0 | 0 | true |

Every repeat created a distinct committed ingest run and distinct `UNCHANGED` provenance events while reusing its checksum-identified immutable raw block. Canonical row counts did not increase. Lane versions remained 1 because repeats made no canonical mutation.

## Read-only canonical reconciliation

The acceptance database was closed after ingestion and reopened using `open_read_only`, which reported:

```text
query_only = 1
foreign_keys = 1
journal_mode = wal
```

For every staged source row, the complete ordered tuple `(timestamp, open, high, low, close, volume)` was compared with the corresponding ordered canonical `bars` tuple. All 33,547 rows matched exactly after the documented deterministic decimal normalization.

| Lane | Bars reconciled | INSERT events | UNCHANGED events | Missing provenance | Raw bytes equal |
|---|---:|---:|---:|---:|---|
| AUDUSD D1 | 14,260 | 14,260 | 14,260 | 0 | true |
| XAUUSD D1 | 13,256 | 13,256 | 13,256 | 0 | true |
| BTCUSD D1 | 6,031 | 6,031 | 6,031 | 0 | true |

Aggregate read-only facts:

```text
bars:                   33,547
raw_blocks:              3
ingest_runs:             6
non-committed runs:      0
provenance events:      67,094
lane_state rows:         3
foreign-key violations:  0
```

An attempted `lane_state` update through the same consumer failed with `attempt to write a readonly database`.

## Factual lane state

| Lane | High watermark | State version | Last mutating run |
|---|---|---:|---|
| AUDUSD D1 | 2026-07-10 00:00:00 UTC | 1 | `f04fae4bacf945e6878466f27299a4f5` |
| XAUUSD D1 | 2026-07-10 00:00:00 UTC | 1 | `04657017d5104f19a2a7be7fd9b4dc56` |
| BTCUSD D1 | 2026-07-10 00:00:00 UTC | 1 | `d8dd842afe3b46baa899eacc1b6c2a48` |

These are stored-key facts. They are not freshness, expected-session, gap, trading-fitness, or readiness judgments.

## Integrity and regression proof

Full `verify_integrity` returned true. `PRAGMA integrity_check` returned only `ok`; `foreign_key_check` returned no rows; the seven-table boundary and both migration checksums matched.

After the boundary mapping and runtime exercise, the complete automated command was rerun:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

```text
Ran 34 tests
OK
```

## Limits of acceptance

- Operator selection establishes the evidence used for this proof; it does not prove the source values are economically correct.
- No calendar or session doctrine was applied. Missing dates and apparent history depth were not classified.
- No expected-session coverage, material-gap status, freshness, tradability, consumer fitness, or engine readiness was calculated.
- Volume was absent in all three files and remains null.
- The `time` header mapping is a manual boundary translation only, not a network provider integration.
- The acceptance database is local runtime evidence and is excluded from Git by the repository's SQLite ignore rules.
- The operator-supplied inbox files remain untracked and were not added to a commit.

## Acceptance statement

The operator-selected raw bytes were preserved immutably. Every structurally accepted canonical D1 bar reconciled to its staged source value and has both initial and repeated-attempt provenance. Repeating each import was idempotent and produced no silent overwrite, conflict, correction, rejection, or history truncation.

This is SPEC-002 real-evidence acceptance evidence only. Fragarach II remains a candidate authority.

**Operations is King.**
