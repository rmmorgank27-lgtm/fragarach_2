# SPEC-066 — MT5 Tick-Activity Backfill and Continuous Delivery

## Status

Implemented and live on 2026-09-14. The resumable historical backfill is
active; continuous delivery and consumer projection are enabled. Final estate-
wide history completion remains observable through the gates in section 9.
Route expansion is not implied. Price routing remains governed by the amended
SPEC-065/SPEC-067 estate default and exact-lane overrides; this specification
does not create an exception to that authority.

## Objective

Provide one consistent, broker-native activity series for every approved MT5
Forex, metals, energy, and index lane at `D1`, `H1`, `M30`, and `M5`.

The selected metric is **Fusion MT5 tick volume**. It is used for comparative
analysis within the same canonical symbol, timeframe, broker route, and
continuous feed. It is not represented as global traded volume, exchange
volume, order flow, or a cross-broker comparable quantity.

The work has two independent, compatible delivery paths:

1. an immutable, resumable historical tick-activity backfill; and
2. continuous tick-activity admission from every normal completed-bar MT5
   bridge delivery.

This specification extends the bridge evidence contract in SPEC-065. It does
not replace canonical OHLC authority, modify provider routing, or permit MT5
activity to silently rewrite an existing price bar.

---

## 1. Governing decisions

1. `tick_volume` is the canonical comparative activity metric for this scope.
2. `real_volume` is retained when supplied, but is auxiliary broker-reported
   trade volume. It is never substituted for tick activity and is never
   presented as market-wide volume.
3. Tick activity is native to the requested MT5 timeframe. `D1`, `H1`, `M30`,
   and `M5` must each be obtained directly from MT5; Fragarach must not derive
   one timeframe's activity by summing another.
4. Activity is additive evidence. It does not alter OHLC, bar identity, price
   freshness, price-source provenance, or the price provider selected for the
   lane.
5. An approved terminal alias, live catalogue capability, route-manifest
   review, and registered Fragarach symbol must all agree before activity is
   requested or admitted. A terminal suffix is not authority by itself.
6. Only completed bars are admitted. The forming bar is excluded exactly as it
   is for ordinary bridge price evidence.
7. The visible label is always explicit: `Fusion MT5 tick activity`. The UI
   must not display this value merely as `Volume`.

---

## 2. Scope

Included market classes:

| Market class | Timeframes | Activity source |
| --- | --- | --- |
| FX | D1, H1, M30, M5 | Approved Fusion MT5 terminal symbol |
| Metals | D1, H1, M30, M5 | Approved Fusion MT5 terminal symbol |
| Energy | D1, H1, M30, M5 | Approved Fusion MT5 terminal symbol |
| Indices and broker index CFDs | D1, H1, M30, M5 | Approved Fusion MT5 terminal symbol |

The actual eligible set is the intersection of:

```text
registered Fragarach symbol/timeframe
∩ reviewed route-manifest alias
∩ live MT5 catalogue capability
∩ completed-bar availability
```

US equities, cryptocurrencies, unreviewed aliases, and an alternate broker
family are out of scope unless separately approved.

### 2.1 Price-routing alignment

The presence of MT5 tick activity does not select the OHLC provider. A lane
without an override inherits the same estate-wide default order:

```text
MT5 -> BINANCE / COINGECKO -> YAHOO_FINANCE -> TWELVE_DATA
```

Only reviewed, timeframe-capable representations participate. The
Binance/CoinGecko tier is crypto-only. An activated exact-lane override may
disable or reorder any reviewed price candidate under SPEC-065/SPEC-067. If an
MT5 price request falls through to a lower tier, the MT5 activity series
remains separately attributed and may be attached only under the alignment
rules in section 7. Activity availability cannot alter the effective price
order, enable or disable a candidate, or change the lane override.

---

## 3. Data meaning and presentation

### 3.1 Canonical metrics

For a completed broker bar, the bridge records:

| Field | Meaning | Consumer label |
| --- | --- | --- |
| `tick_volume` | Number of MT5 quote ticks recorded by Fusion during the native bar | Fusion MT5 tick activity |
| `real_volume` | Broker-reported trade volume, when non-zero and supplied | Fusion broker-reported trade volume |
| `spread` | Broker bar spread observation | Fusion MT5 spread |

`real_volume = 0` or absent means **unavailable**, not zero market activity.
The selected comparative measure remains `tick_volume` even when a non-zero
`real_volume` is present.

### 3.2 Comparison boundary

Tick activity may be compared:

```text
same canonical symbol + same timeframe + same broker family + same route generation
```

It must not be used to compare absolute liquidity between symbols, broker
families, or unrelated asset classes. A route or broker-family change begins a
new visible comparison segment; it does not silently blend distributions.

---

## 4. Bridge receipt contract

The normal MT5 completed-bar response is extended, not duplicated. Each bar
retains its raw bridge evidence and includes the following activity payload:

```json
{
  "time": "2026.09.14 10:00:00",
  "open": 1.08000,
  "high": 1.08020,
  "low": 1.07980,
  "close": 1.08010,
  "tick_volume": 1338,
  "real_volume": 0,
  "spread": 5
}
```

The receipt must also retain the existing request identity, canonical symbol,
terminal alias, timeframe, broker/node identity, timestamp semantics,
completed-bar proof, capture time, and content hashes.

The bridge must obtain these values from the native MT5 `MqlRates`/`CopyRates`
result for the requested timeframe. A request or response that omits
`tick_volume` is classified `ACTIVITY_FIELD_UNAVAILABLE`; it may still be
valid price evidence, but cannot advance activity coverage.

---

## 5. Canonical activity admission model

Activity is stored as an attributed companion observation keyed by:

```text
canonical symbol
timeframe
canonical bar open time
activity source identity
route-manifest revision / broker family
immutable bridge receipt and ingestion-run identity
```

The activity record contains at minimum:

```text
tick_volume                 required, non-negative integer
real_volume                 nullable, non-negative integer
spread                      nullable, non-negative integer
activity_kind               MT5_TICK_ACTIVITY
activity_source_label       Fusion MT5 tick activity
provider and terminal alias
broker family and node identity
source timestamp semantics
raw receipt hash
admission run identity
observed/captured time
```

The existing `bars.volume` field must not become an unlabelled mixture of
vendor volume, broker trade volume, and tick activity. A consumer projection
may expose a selected `tick_activity` value, but the canonical activity record
keeps its kind and source explicit.

An activity observation may attach only to a matching existing canonical bar
for the same symbol, timeframe, and opening timestamp. If price evidence is
absent or its timestamp cannot be matched, retain the receipt and record an
`ACTIVITY_PRICE_ALIGNMENT_UNRESOLVED` outcome. Do not create a replacement
OHLC bar from the activity operation.

Corrections are append-only evidence operations. They must preserve the prior
receipt, explain the revised source value, and be visible to consumers.

---

## 6. Historical backfill

### 6.1 Planning

Backfill plans are created per approved `symbol × timeframe` lane. Each plan
records:

```text
route-manifest revision and terminal alias
earliest/latest completed MT5 availability discovered
requested native-timeframe range
accepted activity edge
unresolved alignment range
receipt count, row count, and retry state
```

Ranges are bounded and chunked. A completed chunk is immutable and checkpointed
before the next chunk begins, making restart safe after a bridge, terminal, or
network interruption.

### 6.2 Admission

For every chunk, Fragarach shall:

1. enqueue one ordinary immutable bridge request;
2. validate request/response identity, broker capability, timestamp semantics,
   completed-bar evidence, and non-negative activity fields;
3. match returned native bars to existing canonical price-bar openings;
4. admit only the matching additive activity observations;
5. persist the checkpoint, receipt hash, accepted edge, and any alignment
   exceptions; and
6. publish an activity-coverage delta without republishing or changing OHLC.

Backfill may run concurrently across independent terminal routes only within
the bridge's reviewed capacity. It must never compete with the sole canonical
admission writer or create a direct SQLite writer on Windows.

### 6.3 Completion states

| State | Meaning |
| --- | --- |
| `ACTIVITY_BACKFILL_CURRENT` | All available completed broker bars through the planned edge are attached |
| `ACTIVITY_BACKFILL_PARTIAL` | Work remains, with a durable next range or retry |
| `ACTIVITY_PRICE_ALIGNMENT_UNRESOLVED` | A broker activity bar cannot safely attach to canonical price evidence |
| `ACTIVITY_SOURCE_UNAVAILABLE` | Terminal lacks the reviewed historical range or activity field |
| `ACTIVITY_ROUTE_REVIEW_REQUIRED` | Alias, capability, or route authority is not approved |

No completion state may be inferred from a current price lane.

---

## 7. Continuous delivery

Every normal completed-bar MT5 request for an approved route shall deliver
tick activity in the same receipt as the price evidence.

For an MT5-primary price lane, price and activity are admitted from the same
receipt but retain separate authority facts. For a non-MT5-primary price lane
(for example a reviewed daily price lane), MT5 activity is attached only after
timestamp alignment with the already canonical price bar. It does not change
the selected OHLC provider.

Continuous activity freshness is independent:

```text
price lane current       ≠ tick activity current
tick activity current    ≠ price lane current
```

The native app must show both facts where activity is enabled:

```text
Price source: MT5 / Binance or CoinGecko / Yahoo / Twelve Data / derived
Tick activity: Fusion MT5 · current / behind / unavailable
```

The normal bridge cadence, pending-lane deduplication, expiry handling,
single-writer admission, and health monitor from SPEC-065 remain unchanged.

---

## 8. Operator and consumer surfaces

Management must show, per lane:

```text
activity route and terminal alias
metric kind: Fusion MT5 tick activity
historical available range and accepted edge
backfill state and next automatic action
continuous activity freshness
receipt/provenance drill-down
```

An operator may request a bounded historical activity backfill or retry a
failed range only on an approved route. A force request is deduplicated by
symbol/timeframe/range and goes through the same bridge queue and admission
path as ordinary work.

Chart and analytical surfaces display a unit-bearing label such as:

```text
Tick activity — Fusion MT5 (count)
```

They must not draw a global-volume conclusion, volume-profile claim, or
cross-broker comparison without a separate analysis contract.

---

## 9. Acceptance gates

Implementation is accepted only after all of the following pass:

1. One approved representative each from FX, metals, energy, and indices
   returns completed native `D1`, `H1`, `M30`, and `M5` activity receipts.
2. Each admitted activity observation has a valid request, response, raw
   receipt hash, terminal alias, broker identity, and completed-bar proof.
3. Tick activity is non-negative and labelled `Fusion MT5 tick activity`.
4. A non-zero `real_volume` remains separately inspectable; a zero/missing
   value is shown as unavailable, not as zero activity.
5. A historical backfill can stop mid-range, restart, and resume without
   duplicate canonical activity observations or lost receipt provenance.
6. An unmatched timestamp is retained as an explicit alignment exception and
   does not alter or create OHLC evidence.
7. An MT5 activity correction is append-only and leaves historical price
   provenance unchanged.
8. The continuous bridge delivery advances activity coverage for a newly
   completed native bar.
9. A current price lane with unavailable activity, and a current activity lane
   with stale price, are both represented honestly in management and Estate
   Truth.
10. Scheduler, bridge, native app, and replica consumers remain healthy under
    the intended backfill capacity; no second canonical writer is created.
11. Price fallback follows the active SPEC-065/SPEC-067 effective lane order,
    whether inherited from estate defaults or set by a lane override; activity
    availability cannot enable, disable, promote, demote, or reorder a price
    candidate.

---

## 10. Delivery sequence

1. Add the activity evidence/storage contract and receipt validation.
2. Extend continuous bridge admission and management/consumer projections.
3. Prove the four-market-class live acceptance set for one bounded recent
   range.
4. Add resumable historical planning, checkpoints, and backfill controls.
5. Run the full approved historical backfill in reviewed, observable batches.
6. Publish activity coverage and unresolved alignment reports.

Each stage requires its own focused tests and an immutable acceptance receipt.

---

## 11. Implemented operating controls

- SQLite migration 13 owns immutable, source-labelled companion activity
  observations and prevents update or deletion.
- Normal MT5 receipts admit OHLC and activity in one writer transaction while
  retaining distinct authority facts. Activity-only daily receipts attach to
  an existing canonical timestamp and cannot create or change OHLC.
- Historical state is restart-safe in the bridge support directory. Work is
  limited to one backfill request at a time, normal bridge traffic has dispatch
  priority, and chunks are paced at no more than one every 30 seconds.
- Current chunk ceilings are 365 days for `D1`, 30 days for `H1`, 14 days for
  `M30`, and 2 days for `M5`.
- Non-MT5-primary price lanes receive a bounded continuous activity request
  when their price edge advances beyond the attached activity edge.
- Native management and read-only history consumers expose the explicit
  `Fusion MT5 tick activity` label, independent activity freshness, terminal
  alias, optional broker-reported volume, and spread.
