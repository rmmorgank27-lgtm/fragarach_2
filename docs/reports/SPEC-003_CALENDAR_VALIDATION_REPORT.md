# SPEC-003 Calendar Validation — Implementation Report

**Report date:** 2026-07-11

**Repository:** `/Users/raymorgan/VSC/fragarach_2`

**Validation boundary:** 2026-07-10 inclusive

**Authority:** `data/runtime/spec002_real_evidence_acceptance.sqlite3`

## Outcome

SPEC-003 is implemented and proven for AUDUSD, XAUUSD, and BTCUSD native D1 lanes. Validation compares immutable canonical evidence with explicit versioned session expectations, reports weekly/monthly and gap facts, and persists only the SPEC-003A factual lane summary when explicitly requested.

The results include substantial historical gaps and outside-session bars. They were not concealed, deleted, synthesized, corrected, or used to patch calendar rules.

This proves deterministic internal comparison only. Fragarach II remains a candidate authority. No consumer migration is authorized.

## Compatibility gate

The first SPEC-003 gate correctly failed because `lane_state` had no summary field. SPEC-003A was separately implemented, proven, reported, and checkpointed.

The fresh gate then passed:

- 39 pre-SPEC-003 tests passed;
- migration versions 1, 2, and 3 matched checksums;
- `lane_state.validation_summary` existed and was null for all three lanes;
- the application table set remained exactly seven;
- read-only mode, integrity, and foreign keys passed; and
- tracked source was clean, with operator data intentionally outside Git.

## Files added and changed

- Added six versioned JSON assets under `config/`.
- Added Calendar Doctrine V1 and Gap Doctrine V1.
- Added `SPEC-003_VERSIONED_ASSET_CALENDARS.md`.
- Added calendar models, registry validation, Gregorian Easter/Good Friday rules, and session generation.
- Added deterministic D1 validation, coverage summaries, gap classification, result checksum, and summary projection.
- Added `fragarach_ii.commands.validate_lane` with explicit persist/no-persist modes.
- Added calendar, validation, determinism, persistence, and command tests.
- Added README command usage.

No acquisition, provider, calendar download, bar mutation, synthetic evidence, repair, rollup, H1 validation, scheduler, service, dashboard, consumer interpretation, or legacy integration was added.

## Calendar rules and exceptions

### FX_D1_V1

- Explicit initial symbol: AUDUSD.
- UTC Monday through Friday expected.
- Closed recurring dates: 1 January and 25 December.
- No invented observed-weekday closure when either falls on a weekend.
- Good Friday and other reduced-liquidity dates remain expected in V1.

### METALS_D1_V1

- Explicit initial symbol: XAUUSD only.
- UTC Monday through Friday expected.
- Closed recurring dates: 1 January and 25 December.
- Gregorian Good Friday is calculated deterministically and closed.
- Early-close weekdays remain expected.

### CRYPTO_D1_V1

- Explicit initial symbol: BTCUSD.
- Every Gregorian UTC calendar date expected.
- No weekend or holiday closures in V1.

All definitions support `EXPECTED_OVERRIDE` and `CLOSED_OVERRIDE`, which take precedence and require a factual reason. Initial V1 files contain no dated overrides. Missing evidence never generates an override.

## Definition checksums

| Definition | SHA-256 |
|---|---|
| Calendar registry | `368421535ded1e952b3d44e0d8533b18a17c0d84a47d52f1d3e2b9b3bf20275a` |
| Symbol registry | `4c14a8a08af532790be70ddd100e499075980cd89a4d624718c3da36deb68c2f` |
| FX_D1_V1 | `a19ab5557787748619e7130c3cf89aa524a117073f08aa4c9b97e432db5e0926` |
| METALS_D1_V1 | `38e099907749091ac3b3d0038ff4814b0f0f5d5f4dca0b7fbd0dc46f3730a1a9` |
| CRYPTO_D1_V1 | `b9debf8c139437c0ba3c7505dcea8423452565a255fefee4d35f98529ab887c6` |
| Gap Doctrine V1 | `c86382fc8099c3f27af2976592dd1b39e6fdb1f9065da0b134ba351e2340ad28` |

Load-time verification recomputes canonical JSON checksums and rejects drift.

## Gap classification semantics

Material reasons are exactly `CURRENT_EDGE_MISSING`, `EMPTY_EXPECTED_WEEK`, and `EMPTY_EXPECTED_MONTH`, with result wording `MATERIAL_BY_GAP_DOCTRINE_V1`.

Remaining expected-session gaps are `ISOLATED_EXPECTED_SESSION_MISSING`, with wording `NON_MATERIAL_BY_GAP_DOCTRINE_V1`.

Counts represent missing expected dates. A date with multiple material reasons is counted once; its result entry retains every reason.

## Automated proof

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

```text
Ran 58 tests
OK
```

The tests cover seven-day crypto weeks; FX/metals weekends; recurring holidays; Good Friday across 2024–2026; early-close weekday treatment; override precedence; unknown calendars; checksum drift; complete/missing/outside/beyond ranges; current edges; empty weeks/months; non-material isolated gaps; multiple reasons without double counting; weekly/monthly reconciliation; insertion-order and wall-clock determinism; read-only default; summary-only persistence; factual command errors; and every prior storage/ingestion regression.

## Runtime commands

Each lane was first run read-only, then explicitly persisted:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python3 -m fragarach_ii.commands.validate_lane \
  --database data/runtime/spec002_real_evidence_acceptance.sqlite3 \
  --symbol "$symbol" --timeframe D1 \
  --through-date 2026-07-10 --no-persist --json
```

The same command with `--persist` wrote only `lane_state.validation_summary`. Read-only and persisted executions produced identical factual result checksums.

## Real-evidence summary

| Fact | AUDUSD | XAUUSD | BTCUSD |
|---|---:|---:|---:|
| Earliest present | 1971-01-04 | 1970-02-27 | 2009-10-05 |
| Latest present | 2026-07-10 | 2026-07-10 | 2026-07-10 |
| Expected sessions | 14,407 | 14,569 | 6,123 |
| Present expected | 14,246 | 13,209 | 6,031 |
| Missing expected | 161 | 1,360 | 92 |
| Outside expected | 14 | 47 | 0 |
| Beyond boundary | 0 | 0 | 0 |
| Empty ISO weeks | 1 | 197 | 8 |
| Empty months | 0 | 1 | 0 |
| Material missing dates | 5 | 979 | 56 |
| Non-material missing dates | 156 | 381 | 36 |

For all three lanes, the latest expected session is 2026-07-10 and is present. Therefore `CURRENT_EDGE_MISSING` count is zero.

### AUDUSD D1

Calendar: `FX_D1_V1`.

- One empty ISO week: `1971-W33`.
- Five material missing dates: 1971-08-16 through 1971-08-20, all `EMPTY_EXPECTED_WEEK`.
- 156 isolated non-material missing dates across 150 missing expected-session ranges.
- Fourteen outside-session dates under the V1 recurring closure rules:

```text
1990-12-25, 1995-12-25, 1996-01-01, 1996-12-25,
1997-01-01, 1997-12-25, 1998-01-01, 1998-12-25,
1999-01-01, 2000-12-25, 2001-01-01, 2006-12-25,
2007-01-01, 2018-01-01
```

Result checksum:

```text
f59ef6de1fcae4f9b828a7a3b0c8e0fa55539e6953a7a314dd7ad31aa23709df
```

### XAUUSD D1

Calendar: `METALS_D1_V1`.

- 197 empty ISO weeks, concentrated in sparse 1970–1974 evidence plus `2009-W38`.
- One empty calendar month: `1972-03`.
- 976 material dates carry `EMPTY_EXPECTED_WEEK`; 22 carry `EMPTY_EXPECTED_MONTH`; 19 carry both. Unique material-date count is 979.
- 381 isolated non-material dates; 181 missing expected-session ranges in total.
- Forty-seven outside-session dates under New Year, Christmas, and Good Friday rules:

```text
1972-03-31, 1994-04-01, 1995-04-14, 1995-12-25,
1996-04-05, 1996-12-25, 1997-01-01, 1997-03-28,
1997-12-25, 1998-01-01, 1998-04-10, 1999-01-01,
1999-04-02, 2000-04-21, 2000-12-25, 2001-01-01,
2001-04-13, 2001-12-25, 2002-01-01, 2002-03-29,
2002-12-25, 2003-01-01, 2003-04-18, 2003-12-25,
2004-01-01, 2004-04-09, 2005-03-25, 2006-04-14,
2006-12-25, 2007-01-01, 2007-04-06, 2007-12-25,
2008-01-01, 2008-03-21, 2008-12-25, 2009-01-01,
2009-04-10, 2010-04-02, 2011-04-22, 2012-04-06,
2014-04-18, 2015-04-03, 2016-03-25, 2021-04-02,
2022-04-15, 2024-03-29, 2026-04-03
```

Result checksum:

```text
3359b92fbec07bd1a4a98ecb8d784f9bddaca685a73d63fb681fcdb0554536e1
```

### BTCUSD D1

Calendar: `CRYPTO_D1_V1`.

- Eight empty ISO weeks: `2010-W10` through `2010-W15`, `2010-W22`, and `2011-W25`.
- 56 material dates, all carrying `EMPTY_EXPECTED_WEEK`.
- 36 isolated non-material dates across 18 missing ranges.
- No outside-session date exists because every Gregorian date is expected.

Result checksum:

```text
713ebb30d3855d5ada42cb529f90e0edffdd40703a4c08decfe28ea722715e62
```

## Before-and-after authority invariants

| Authority content | Count | Before SHA-256 | After SHA-256 |
|---|---:|---|---|
| Canonical bars | 33,547 | `0d5071b2df747bcc14b06f71b8e50ab178fa78a33ab7902620756840ebdb8c81` | identical |
| Raw blocks | 3 | `3c47f31744539392dba745b3e66d207de07f44fdb0306909445718a6e3705ccf` | identical |
| Provenance events | 67,094 | `9968c3de348858ca0d3cd242ab5edccdf22fae25fd1d32be90243697127414c2` | identical |
| Ingest runs | 6 | `481cd4efca5f9b267cc64a42ff81b3a6ad1c090b27ce34aa48c511484cc0d1c5` | identical |
| Existing lane facts | 3 | `8555877970df7169f69096d71935bb02ab561dcea31a2f2c3216e6cb073eef34` | identical |

Only the three previously null `validation_summary` fields changed. Each stores format V1, boundary 2026-07-10, and the corresponding full-result checksum.

After persistence, integrity passed, foreign keys returned no violations, migration checksums matched, and the application table set remained exactly seven.

## Known limitations and deferred work

- V1 validates D1 dates only. It does not define intraday sessions, H1 completion, daylight-saving boundaries, live completion, or provider cutoffs.
- V1 recurring closures are deliberately small and may differ from a venue or provider's historical publication. Outside-session results are rule disagreements, not proof the bars are wrong.
- No automatic holiday source or calendar correction exists.
- Full validation results are returned by the command; only the compact current summary is persisted. Historical result retention is not authorized.
- No repair priority, substitution, acquisition, rollup, scheduler, service, dashboard, Morphix integration, or consumer sufficiency is implemented.
- The material/non-material wording is doctrine-specific and is not a universal importance or readiness judgment.

## Git identity

```text
SPEC-003A implementation: c54f611264374d045cab587f7ee21601ec3a5e76
SPEC-003A report:         c8aef76d9fe2b450a0d88ff43e5a963d799a1dbd
SPEC-003 implementation: e3d08bd906ad97f0f333a43079db0c3e8b9b3ae7
```

This report is committed separately so it can record the implementation identity. Nothing was pushed.

## Acceptance statement

Fragarach II can compare stored D1 evidence against explicit, versioned session expectations and report the resulting facts deterministically. It does not prove provider correctness, automated operation, consumer readiness, or production trust.

**Operations is King.**
