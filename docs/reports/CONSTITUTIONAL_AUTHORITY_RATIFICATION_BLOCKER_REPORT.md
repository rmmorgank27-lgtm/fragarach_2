# Constitutional Authority Ratification — Blocker Report

**Review date:** 2026-07-11

**Baseline:** `33ff795` — `Gate SPEC-008 H1 implementation`

**Decision:** Ratification stopped because nine timeframe authorities contain material request-overlap contradictions. No constitutional document was approved and no runtime implementation was attempted.

## Mechanical repair proof

The corrected brief's authorized repair is complete:

- canonical root installed at `constitution/CONSTITUTION.md`;
- corrected manifest installed;
- doctrines moved to `constitution/doctrines/`;
- corrected brief installed at repository root;
- duplicate market-template claimant preserved at `docs/archive/constitutional_import/Fragarach_II_Constitution_duplicate_market_template.md`;
- confirmed accidental `constitution/cons.txt` deleted under explicit owner authorization;
- all `.DS_Store` files removed from `constitution/`;
- no `constitution/doctrine/`, temporary `cons.txt`, or duplicate claimant remains inside the authority tree.

These repairs changed paths and housekeeping only; they did not alter doctrine meaning.

## Controlled inventory

| Category | Count | Result |
|---|---:|---|
| Constitutional Root | 1 | Present |
| Controlled templates | 2 | Present; status `TEMPLATE` |
| Base Doctrines | 9 | Present at canonical paths |
| Timeframe Authorities | 36 | Present at canonical paths |
| Manifest | 1 | Present; `PENDING RATIFICATION` |
| Controlled total | 49 | Exact |
| Symlinks | 0 | Clean |

All 36 parent-doctrine references and every governing-Constitution reference resolve.

## Structural audit

Read-only validation of all 49 controlled documents passed:

- UTF-8 readability;
- canonical filename/document identity agreement;
- repository-location metadata;
- market family and timeframe identity;
- expected validator identity;
- governing and parent references;
- ordered, non-duplicated major numbered sections;
- balanced fenced code blocks;
- unique controlled identities;
- no unresolved placeholders outside intentional template fields;
- no secrets, credentials, tokens, or private keys.

SHA-256 was computed for all 49 controlled documents. Final ratification digests were not issued because approval statuses did not change.

## Material semantic blocker — copied US overlap mathematics

US regular trading has 7 H1, 13 M30, and 78 M5 intervals, so its two-session overlaps of 14, 26, and 156 are internally correct. Nine UK, German, and Australian authorities copy those totals despite defining different ordinary session counts.

### UK Equities

The UK authorities correctly define an ordinary 08:00–16:30 London session as:

- H1: 9 bars;
- M30: 17 bars;
- M5: 102 bars.

Therefore two normal sessions contain 18 H1, 34 M30, and 204 M5 intervals. The following normative rules instead use 14, 26, and 156:

| File | Sections | Unsupported statement | Required owner decision |
|---|---|---|---|
| `constitution/authorities/equities_uk/UK_EQUITIES_H1_AUTHORITY_V1.md` | 12.3, 12.4 | `14 expected H1 intervals`, described as two normal sessions | Approve 18, or explicitly redefine the overlap doctrine |
| `constitution/authorities/equities_uk/UK_EQUITIES_M30_AUTHORITY_V1.md` | 12.3, 12.4 | `26 expected M30 intervals`, described as two normal sessions | Approve 34, or explicitly redefine the overlap doctrine |
| `constitution/authorities/equities_uk/UK_EQUITIES_M5_AUTHORITY_V1.md` | 12.3, 12.4 | `156 expected M5 intervals`, described as two normal sessions | Approve 204, or explicitly redefine the overlap doctrine |

### German Equities

The German authorities correctly define `XETRA_REGULAR_CONTINUOUS_V1`, 09:00–17:30 Europe/Berlin, as 9 H1, 17 M30, and 102 M5 bars. Two sessions are therefore 18, 34, and 204. These files instead repeat 14, 26, and 156 in Sections 12.3 and 12.4:

- `constitution/authorities/equities_de/GERMAN_EQUITIES_H1_AUTHORITY_V1.md`
- `constitution/authorities/equities_de/GERMAN_EQUITIES_M30_AUTHORITY_V1.md`
- `constitution/authorities/equities_de/GERMAN_EQUITIES_M5_AUTHORITY_V1.md`

Owner decision: approve 18/34/204 respectively, or explicitly authorize different overlap semantics and remove the false “equal to two normal regular sessions” claim.

### Australian Equities

The Australian authorities correctly define `ASX_NORMAL_TRADING_V1`, 10:00–16:00 Australia/Sydney, as 6 H1, 12 M30, and 72 M5 bars. Two sessions are therefore 12, 24, and 144. These files instead repeat 14, 26, and 156 in Sections 12.3 and 12.4:

- `constitution/authorities/equities_au/AUSTRALIAN_EQUITIES_H1_AUTHORITY_V1.md`
- `constitution/authorities/equities_au/AUSTRALIAN_EQUITIES_M30_AUTHORITY_V1.md`
- `constitution/authorities/equities_au/AUSTRALIAN_EQUITIES_M5_AUTHORITY_V1.md`

Owner decision: approve 12/24/144 respectively, or explicitly authorize different overlap semantics and remove the false “equal to two normal regular sessions” claim.

### Operational consequence

Sections 12.3 and 12.4 govern chunk overlap and incremental acquisition start. Incorrect counts change request boundaries, correction-detection coverage, and reassembly evidence. An implementation following these documents would not implement the stated two-session doctrine for the affected markets.

The values cannot be silently corrected during ratification because that would alter normative constitutional meaning.

## Other semantic audit results

The audit found the following internally consistent outside the blocker above:

- universal authority and evidence-lane hierarchy;
- Current-As-Of and latest-closed-bar doctrine;
- direct/derived evidence separation;
- affected-path-only stopping behavior;
- no fabricated no-trade bars or silent gap fills;
- immutable correction and conflict evidence;
- D1 → H1/M30/M5, H1 → M30/M5, M30 → M5, and direct-only M5 construction chain;
- provider documented 5,000-row maximum distinguished from the 4,000-row Fragarach ceiling across all timeframe authorities;
- FX New York rollover and close-date ownership;
- Crypto continuous UTC and venue/quote/aggregate separation;
- Metals troy-ounce and product-scope separation;
- Energy benchmark, unit, source, roll, settlement, CFD, and negative-price doctrine;
- Indices administrator/methodology, official/indicative, proxy, volume, and flat-OHLC prohibitions;
- US regular session, final H1 interval, early-close, and adjustment doctrine;
- UK, German, and Australian ordinary/early-close session grids apart from the copied overlap counts identified above.

No unaffected family was separately ratified because partial ratification was not authorized.

## Verification

- Python suite: **89 passed**.
- Native Swift checks: **11 passed**.
- Swift build: **passed**.
- Native application launch/process verification: **passed** through `./script/build_and_run.sh --verify`.
- SQLite: exact **nine-table** boundary, integrity, foreign keys, read-only contract, and five migration checksums passed.
- Runtime database SHA-256 before and after verification: `b39e9e521ea7f55d2c47011db3744d5494d28bd73761c8e60167173a093b5221`.
- Secret scan: **clean**.
- Runtime behavior, Python, Swift, SQL, schema, configuration, and database changes: **none**.
- Acquisition, ingestion, registration, validation, and evidence-lane operations: **none**.
- Push: **not performed**.

## Ratification state

- Constitutional Root: `DRAFT FOR APPROVAL`.
- 9 doctrines: `DRAFT FOR APPROVAL`.
- 36 timeframe authorities: `DRAFT FOR APPROVAL`.
- 2 templates: `TEMPLATE`.
- Manifest: `PENDING RATIFICATION`.
- Fragarach II: **CANDIDATE AUTHORITY**.

The authorized mechanical repair is clean and changes no constitutional meaning. It may be checkpointed separately from ratification together with this blocker evidence. No approval status is included in that checkpoint.

> Ratification stopped because constitutional authority remains materially contradictory. No implementation was attempted.

**Operations is King.**
