# SPEC-068 - TradingView Provider Authority and M5 External Archive

## Status

Draft for operator review, dated 2026-09-23.

This document specifies the implementation but does not itself authorise code
deployment, provider activation, subscription cancellation, live database
mutation, or the first archive cutover. TradingView provider activation and M5
archiving are separate acceptance gates. Either may pass while the other
remains inactive.

## Objective

Implement two related updates to Fragarach II:

1. add the official TradingView MCP service as a governed read-only market-data
   transport, while retaining the actual exchange, venue, or broker feed as the
   provider identity for every exact `symbol x timeframe` lane; and
2. retain only the most recent 12 calendar months of canonical M5 data in the
   live authority, moving older M5 evidence to a verified external archive that
   remains queryable through the Fragarach Market History Service.

This specification extends SPEC-018, SPEC-026, SPEC-041, SPEC-063, SPEC-065,
SPEC-066, and SPEC-067. It does not weaken canonical identity, immutable
provenance, source separation, completed-bar admission, the Scheduler's
single-writer boundary, or the rule that consumers never determine historical
truth.

---

## 1. Governing decisions

1. **TradingView MCP is a transport, not the market source.** Every observation
   records both `TRADINGVIEW_MCP` and the exact source identity, for example
   `BINANCE:BTCUSDT`, `COINBASE:BTC-USD`, a named DEX pool, or an exact broker
   feed returned by TradingView discovery.
2. **Every lane is explicit.** TradingView eligibility is stored per canonical
   symbol, timeframe, exact source symbol, venue/broker, representation class,
   entitlement, timestamp policy, and volume meaning. There is no generic
   `TradingView supports crypto` or `TradingView supports FX` grant.
3. **Crypto market evidence is exchange-led.** The target default order is
   Binance, then Coinbase, then Bybit, then a specifically reviewed DEX venue.
   Eightcap MT5 remains a separately visible execution-reference stream. It is
   not silently blended into exchange price or exchange-volume history.
4. **USD and USDT remain distinct.** A Binance or Bybit USDT pair may serve a
   canonical USD-labelled research lane only through the existing explicit
   `APPROVED_EQUIVALENT_REPRESENTATION` review, with source quote currency and
   equivalence visible in routing, history, and provenance.
5. **FX is broker-ranked.** The target order for every approved FX lane is
   FXCM, OANDA, Eightcap, Global Prime, then Fusion Markets. Each broker is a
   separate source identity; unavailable exact pair/timeframe candidates are
   omitted rather than inferred or replaced by a generic FX composite.
6. **Listed stocks are direct-exchange-led.** TradingView must identify the
   exact primary listing exchange, such as NASDAQ, NYSE, NYSE Arca, ASX, LSE,
   or XETRA. A consolidated, alternate-exchange, broker-CFD, or synthetic feed
   is not silently substituted for direct-exchange price or volume.
7. **No source splicing.** A provider transition begins a new visible source
   segment. Existing bars are not overwritten merely because a preferred
   source later returns. Conflicts remain evidence for review.
8. **Volume is typed evidence.** Exchange-reported volume, broker tick volume,
   broker real volume, and unresolved provider volume are different metrics.
   They are never merged or displayed under an unqualified `Volume` label.
9. **TradingView account writes are out of scope.** Fragarach may use only
   approved read-only MCP tools. It cannot create, update, stop, or delete
   TradingView alerts or watchlists.
10. **MCP beta reliability is an activation gate.** An interactive Codex
   connection does not prove unattended Scheduler operation. Production use
   requires a durable OAuth path, bounded rate policy, repeatable receipts,
   and an observation period without manual reauthentication.
11. **The current 5,000-bar limit is binding.** The documented `get_ohlcv`
    operation accepts a count of at most 5,000 and does not document OHLCV
    date-range pagination. It may supply the live tail and ongoing updates, but
    cannot be claimed as a complete long-history replacement until a governed
    pagination or bounded-range contract is proven.
12. **Twelve Data retirement is lane-by-lane.** No existing Twelve Data route
    is removed until its replacement passes identity, timeframe, history,
    volume, reliability, and Scheduler acceptance for that lane. Historical
    Twelve Data provenance remains immutable.
13. **M5 live retention is 12 calendar months.** Rows with canonical M5 open
    time strictly earlier than the UTC cutoff are archive-eligible. The cutoff
    boundary itself remains live.
14. **Archive before removal.** No live row is removed until all related bars,
    typed activity/volume, provenance, raw receipts, and required parent
    records exist in a verified archive batch.
15. **External-volume absence fails closed.** If the exact archive volume is
    missing, read-only, low on space, or has the wrong UUID, archiving pauses,
    live data remains intact, and the operator receives a factual backlog.
16. **Archived history remains Fragarach history.** Consumers request Market
    History from Fragarach. They do not open the external archive directly or
    choose between live and archived stores.

---

## 2. Verified baseline and constraints

### 2.1 TradingView MCP contract

The reviewed official beta documentation supplied on 2026-09-22 defines:

```text
endpoint: https://mcp.tradingview.com/mcp
transport: streamable HTTP
authentication: OAuth 2.1
plan: Essential or above; trial excluded
approximate account limit: 100 tool calls per minute
OHLCV tool: get_ohlcv
symbol identity: EXCHANGE:TICKER
intervals: 1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W, M
maximum bars per OHLCV call: 5,000
OHLCV output: UTC unix time plus o, h, l, c, v
```

The implementation must re-discover the tool contract at activation and fail
closed if the supported intervals, maximum count, response shape, or access
requirements differ. The governing public reference is
`https://www.tradingview.com/mcp/docs`.

For continuous 24-hour markets, 5,000 bars represent approximately:

| Timeframe | Maximum time represented by one full call |
| --- | ---: |
| M5 | 17 days 8 hours 40 minutes |
| M30 | 104 days 4 hours |
| H1 | 208 days 8 hours |
| D1 | 13.7 years |

These are request ceilings, not guarantees of availability, completeness, or
session coverage.

### 2.2 Live estate baseline

The 2026-09-23 read-only inventory contains these relevant active/candidate
lanes:

| Market family | Symbols | Direct timeframes |
| --- | --- | --- |
| Crypto | ADAUSD, AVAXUSD, BNBUSD, BTCUSD, DOGEUSD, DOTUSD, ETHUSD, HYPEUSD, LINKUSD, PEPEUSD, SOLUSD, SUIUSD, XRPUSD | D1, H1, M30, M5 |
| FX | AUDCAD, AUDJPY, AUDNZD, AUDSGD, AUDUSD, EURAUD, EURJPY, EURNZD, EURUSD, GBPAUD, GBPCHF, GBPJPY, GBPNZD, GBPUSD, NZDJPY, NZDUSD, USDCAD, USDCHF, USDJPY | D1, H1, M30, M5 |
| Metals | XAUUSD, XAGUSD | D1, H1, M30, M5 |
| Energy CFDs | UKOIL, USOIL | D1, H1, M30, M5 |
| Broker index CFDs | NAS100, US30, US500 | D1, H1, M30, M5 |
| Stock CFD overlay | XOM | H1, M30, M5 |
| Listed equities/ETFs/indices | Existing commissioned D1 estate | D1 |
| Derived lanes | NAS100, US30, US500, XOM | M15 derived from governed M5 |

`JPYCHF`, `LSEHSBA`, `LSERIO`, and `XAGUSDCFD` remain inactive or unresolved
and gain no TradingView route merely by appearing in search results.

### 2.3 M5 storage baseline

At the 2026-09-23 UTC boundary:

```text
live authority database: approximately 51 GiB
runtime footprint including replicas: approximately 67 GiB
M5 bars in authority: 3,798,689
M5 bars older than 2025-09-23T00:00:00Z: 875,573
M5 bars retained on/after cutoff: 2,923,117
oldest M5 bar: 2021-09-13T09:50:00Z
linked old-M5 provenance events: 934,230
linked old-M5 MT5 activity rows: 123,900
distinct raw receipts directly linked to old M5: 492
payload bytes in those receipts: approximately 0.15 GiB
```

These figures are point-in-time planning evidence, not hard-coded acceptance
counts. Physical file shrinkage is expected to be materially smaller than the
current database size unless unreferenced raw receipts are also removable and
the authority is compacted or rebuilt.

### 2.4 External archive authority

The approved archive destination is:

```text
mount path: /Volumes/WD2TB-2
volume UUID: 1714C6BB-4F88-3F19-990D-04EDE8900EC8
filesystem: Journaled HFS+
archive root: /Volumes/WD2TB-2/Archive-VSC/Fragarach_2
observed free capacity on 2026-09-23: approximately 972 GiB
```

The volume UUID is authoritative. The mount path alone is insufficient because
macOS may reuse a volume name. The job must reject symlinks, a different UUID,
NTFS, a read-only mount, a Time Machine destination, or a local directory that
happens to use the same pathname after the drive is absent.

---

## 3. TradingView provider model

### 3.1 Identity layers

Every accepted response carries all of these identities:

```text
transport_id            TRADINGVIEW_MCP
transport_contract      TRADINGVIEW_MCP_STREAMABLE_HTTP_OAUTH21_V1
tool_name               get_ohlcv
source_kind             EXCHANGE | BROKER | DEX
source_id               BINANCE | COINBASE | BYBIT | FXCM | OANDA |
                        EIGHTCAP | GLOBAL_PRIME | FUSION_MARKETS |
                        NASDAQ | NYSE | ASX | <reviewed venue/broker/exchange>
source_symbol           exact EXCHANGE:TICKER returned by discovery
canonical_symbol        Fragarach symbol
timeframe               D1 | H1 | M30 | M5
source_interval          1D | 1h | 30m | 5m
representation_class    exact or explicitly approved equivalent
quote_currency          exact source quote currency
entitlement_state       real-time, delayed, unavailable, or unresolved
```

The route editor, Scheduler, receipt viewer, History, and archive use the same
identity. A display may say `TradingView / Binance`, but provenance must retain
the exact source symbol.

### 3.2 Provider identifiers

The provider catalogue shall expose separate candidates rather than one broad
`TRADINGVIEW` provider:

```text
TV_BINANCE
TV_COINBASE
TV_BYBIT
TV_BROKER_FXCM
TV_BROKER_OANDA
TV_BROKER_EIGHTCAP
TV_BROKER_GLOBAL_PRIME
TV_BROKER_FUSION_MARKETS
TV_DEX_<VENUE_ID>
TV_EXCHANGE_<EXCHANGE_ID>
```

`TRADINGVIEW_MCP` remains the transport metadata attached to each candidate.
Provider health is both transport-wide and source-specific. A working MCP
session does not prove that a requested venue symbol is entitled or available.

### 3.3 Read-only tool allowlist

The production gateway allowlist is initially:

```text
search_symbols
get_ohlcv
get_symbol_data
get_symbol_data_batch
get_screener_columns
get_technicals_rating
```

Only `search_symbols` and `get_ohlcv` may participate in canonical acquisition.
The other read operations are research/catalogue capabilities and cannot create
bars. Any MCP tool marked write-capable is denied by policy even if the OAuth
grant exposes it.

### 3.4 OAuth and credential boundary

The local TradingView gateway owns OAuth interaction. It stores no password,
cookie, authorization code, access token, or refresh token in the repository,
SQLite authority, Scheduler journal, logs, receipts, or archive. Secrets use
the approved macOS credential authority/Keychain boundary.

Activation requires proof that:

1. the Scheduler can establish and refresh the session without an interactive
   Codex task;
2. a process restart preserves or safely renews authorization;
3. an expired/revoked grant becomes `TRADINGVIEW_AUTH_REQUIRED`, never an
   empty successful response;
4. the account identity and granted read-only tool set are observable without
   exposing token material; and
5. no account-write tool can be invoked through Fragarach.

If unattended OAuth cannot meet these requirements, TradingView remains a
manual research source and cannot enter production routing.

### 3.5 Rate and concurrency policy

The documented approximate limit is an outer ceiling, not an operating target.
Initial production policy is:

```text
maximum concurrency: 1
initial operational budget: 30 calls per minute
maximum configured budget before a new review: 60 calls per minute
documented hard ceiling: approximately 100 calls per minute per account
```

The gateway honors retry metadata when supplied, uses bounded exponential
backoff with jitter, and never fans out unbounded lane requests. Authentication,
rate limiting, transport failure, source unavailability, and invalid response
shape are distinct outcomes.

---

## 4. Lane and broker routing requirements

### 4.1 Per-lane manifest

Implementation adds a versioned reviewed manifest with one row for every exact
candidate:

```text
config/providers/tradingview_lane_manifest.v1.json
```

Each row contains:

```text
canonical_symbol
timeframe
canonical_asset_class
transport_id
provider_id
source_kind
source_id
source_symbol
source_base_asset
source_quote_asset
representation_class
equivalence_authority, nullable
source_interval
volume_kind
volume_unit
session/calendar authority
entitlement state and observed time
search/discovery receipt hash
OHLCV capability receipt hash
reviewed status, reviewer, and review time
enabled state
```

No Scheduler route may be inferred directly from fuzzy search. Discovery
creates a candidate; review creates authority; activation creates an effective
route revision.

### 4.2 Crypto market routes

Every crypto symbol has four independent routes: D1, H1, M30, and M5. The
target default for each is:

```text
1. TV_BINANCE exact discovered pair
2. TV_COINBASE exact discovered pair
3. TV_BYBIT exact discovered pair
4. one or more specifically named and reviewed TV DEX venues
5. fail closed for market evidence
```

This order applies separately to:

```text
ADAUSD   AVAXUSD  BNBUSD   BTCUSD   DOGEUSD  DOTUSD   ETHUSD
HYPEUSD  LINKUSD  PEPEUSD  SOLUSD   SUIUSD   XRPUSD
```

The manifest may omit an unavailable candidate for a symbol. It may not skip
from `TV_BINANCE` to a generic unnamed DEX. Each DEX candidate identifies the
chain, venue, pool/pair, quote asset, and liquidity/volume meaning.

Eightcap is projected alongside these routes as:

```text
stream_role: BROKER_EXECUTION_REFERENCE
provider: MT5_BRIDGE
broker_family: EIGHTCAP_MT5
provider_symbol: exact admitted Eightcap symbol
activity_kind: Eightcap MT5 tick activity
```

It does not occupy the exchange-market fallback chain by default. An operator
may add it only through an exact-lane override that visibly declares a broker
CFD representation change.

### 4.3 FX, metals, energy, and broker-index CFDs

Every FX pair and timeframe has its own reviewed route. The target default is:

```text
1. TV_BROKER_FXCM exact pair
2. TV_BROKER_OANDA exact pair
3. TV_BROKER_EIGHTCAP exact pair
4. TV_BROKER_GLOBAL_PRIME exact pair
5. TV_BROKER_FUSION_MARKETS exact pair
6. fail closed
```

FXCM and OANDA are the two primary FX broker feeds. Eightcap, Global Prime,
and Fusion Markets are independent fallbacks in that order; the slash or tier
relationship between the latter brokers never collapses their identities.
Each candidate may use a reviewed TradingView broker feed or that same broker's
governed direct bridge. Transport choice does not create a new market source,
and two transports carrying the same broker feed must not be mistaken for
independent fallback diversity.

If an exact broker pair or timeframe is unavailable, that manifest candidate
is marked `STRUCTURALLY_INAPPLICABLE` and routing advances to the next named
broker. It does not fuzzy-match a ticker, infer a broker, or use a generic FX
composite. Source discovery must also determine the broker's suffix, quote
convention, session, timestamp policy, and volume meaning.

For metals, energy, broker-index CFDs, and the stock-CFD overlay, the existing
approved Fusion MT5 representation remains primary until a separately reviewed
exact TradingView broker representation is activated for the lane. The
following substitutions are forbidden without a separately approved economic-
representation authority:

```text
cash index for broker index CFD
ETF for CFD or commodity reference
futures contract for spot/CFD
listed share for share CFD
generic composite FX for a named broker feed
```

Required direct lane inventory:

| Family | Symbols | Timeframes | Existing broker reference |
| --- | --- | --- | --- |
| FX | 19 active pairs listed in section 2.2 | D1, H1, M30, M5 | FXCM -> OANDA -> Eightcap -> Global Prime -> Fusion Markets |
| Metals | XAUUSD, XAGUSD | D1, H1, M30, M5 | Fusion MT5 |
| Energy | UKOIL, USOIL | D1, H1, M30, M5 | Fusion MT5 XBRUSD.r / XTIUSD.r |
| Broker index CFDs | NAS100, US30, US500 | D1, H1, M30, M5 | Fusion MT5 `.r` symbols |
| Stock CFD overlay | XOM | H1, M30, M5 | Fusion MT5 ExxonMobil.r |

M15 broker-index and XOM lanes remain derived from governed M5. TradingView
M15 availability does not silently convert them into direct lanes.

### 4.4 Listed equities, ETFs, and indices

For the commissioned D1 estate, the target review order is:

```text
exact TradingView direct primary-listing exchange with required entitlement
-> reviewed Yahoo exact representation
-> existing Twelve Data representation during transition only
-> fail closed
```

The canonical instrument registration determines the direct exchange; examples
include NASDAQ, NYSE, NYSE Arca, ASX, LSE, and XETRA. A TradingView ticker is
not accepted until discovery and instrument metadata agree on the exact listing
exchange. Multi-listed securities have separate exchange-specific candidates.

Default US stock data from Cboe, an alternate exchange, a consolidated feed,
or a composite is not assumed equivalent to the primary listing for volume-
sensitive work. Any such feed requires its own explicit representation review
and cannot masquerade as the direct-exchange route. The manifest must record
the exact exchange prefix, listing currency, entitlement, delay state, session,
and exchange-volume scope.

`USO` remains an ETF and is not a USOIL fallback. `QQQ`/`SPY` remain ETFs and
are not broker-index CFD replacements.

### 4.5 Twelve Data transition

No new lane uses Twelve Data as a preferred source after this specification is
activated. Existing routes remain executable until their exact replacement is
accepted. Removal requires, per lane:

```text
reviewed TradingView source identity
supported timeframe and interval mapping
successful bounded OHLCV receipt
typed volume result or explicit unavailable state
calendar/session validation
seven-day shadow reliability acceptance
successful Scheduler fallback exercise
History/provenance projection acceptance
activated route revision
```

After all required lanes pass, Fragarach publishes a Twelve Data retirement
report. Cancelling the external subscription remains an operator billing action
and is not performed by Fragarach.

---

## 5. TradingView acquisition and evidence contract

### 5.1 Request

Each request records:

```text
request_id
route revision
canonical symbol and timeframe
exact source symbol and source interval
requested bar count
expected completed boundary
overlap policy
issued_at_utc
gateway release identity
```

The request never asks TradingView to choose an exchange or broker implicitly.

### 5.2 Response admission

For each raw bar `{t,o,h,l,c,v}`, admission verifies:

1. exact requested source identity;
2. integer UTC timestamp and strict ordering;
3. approved interval-to-timeframe mapping;
4. completed-bar boundary;
5. numeric finite OHLC and OHLC consistency;
6. duplicate and gap state;
7. non-negative volume when supplied;
8. response count does not exceed the request or documented maximum;
9. deterministic raw-response checksum; and
10. provider, venue/broker, entitlement, and route identities.

Partial/forming bars are retained only in the raw receipt and do not enter
canonical history. Missing `v` does not invalidate a price bar, but produces a
typed `VOLUME_UNAVAILABLE` fact.

### 5.3 Typed volume model

TradingView `v` is admitted as a companion observation, not an unlabelled
cross-provider quantity. The schema must support at least:

```text
EXCHANGE_REPORTED_VOLUME
BROKER_REPORTED_VOLUME
PROVIDER_REPORTED_VOLUME_UNIT_UNRESOLVED
MT5_TICK_ACTIVITY
MT5_BROKER_REPORTED_REAL_VOLUME
```

Every observation retains source venue/broker, exact source symbol, unit when
known, raw receipt, and route segment. If TradingView does not define whether
`v` is base, quote, contracts, ticks, or another unit for a source, the value is
preserved with `PROVIDER_REPORTED_VOLUME_UNIT_UNRESOLVED` and cannot be used by
volume-dependent production logic.

The existing `market_activity_observations` contract may be amended or a new
typed `market_volume_observations` table may be introduced. The implementation
must not weaken the existing MT5 tick-activity meaning.

### 5.4 Long-history boundary

Until TradingView exposes and Fragarach validates deterministic pagination or
date-bounded OHLCV:

* TradingView supplies only a bounded current tail;
* existing canonical long history remains unchanged;
* no lane is marked maximum-history complete from one 5,000-bar response;
* archive restoration never depends on re-downloading from TradingView; and
* gaps older than the reachable tail remain explicit rather than fabricated.

---

## 6. TradingView reliability gate

TradingView is `RESEARCH_ONLY` until all gates pass.

### 6.1 Shadow period

Run at least seven consecutive days, including a weekend for crypto, with:

```text
no manual OAuth repair
no source identity drift
no malformed successful responses
no silent empty or zero-filled response
at least 99.5% successful eligible requests after bounded retry
p95 completed call latency <= 10 seconds
rate-limit outcomes correctly deferred, not failed or blocked
process restart and host-login recovery proven
```

The observation report separates MCP transport availability from each venue or
broker source's availability.

### 6.2 Representative data checks

At minimum, compare and receipt:

```text
BTCUSD: Binance, Coinbase, Bybit at D1/H1/M30/M5
ETHUSD: Binance and Coinbase at D1/H1/M30/M5
SOLUSD: Binance, Coinbase, Bybit at D1/H1/M30/M5
one lower-liquidity current-estate crypto across all available venues
EURUSD and one FX cross through FXCM and OANDA at D1/H1/M30/M5
one exercised exact fallback through each available Eightcap, Global Prime,
and Fusion Markets broker path
XAUUSD broker feed at D1/H1/M30/M5
one NASDAQ direct-exchange equity at D1
one NYSE direct-exchange equity at D1
one ASX direct-exchange equity at D1 when included in the commissioned estate
```

Checks include timestamps, OHLC, volume presence/meaning, source symbol,
entitlement/delay, first/last returned boundary, and stable repeated checksum
for an unchanged completed window.

### 6.3 Failure classification

Required outcomes include:

```text
TRADINGVIEW_AUTH_REQUIRED
TRADINGVIEW_RATE_LIMIT_WAIT
TRADINGVIEW_TRANSPORT_FAILURE
TRADINGVIEW_TOOL_CONTRACT_CHANGED
TRADINGVIEW_SOURCE_NOT_FOUND
TRADINGVIEW_ENTITLEMENT_REQUIRED
TRADINGVIEW_DELAYED_FEED
TRADINGVIEW_TIMEFRAME_UNSUPPORTED
TRADINGVIEW_INVALID_RESPONSE
TRADINGVIEW_HISTORY_LIMIT_REACHED
TRADINGVIEW_VOLUME_UNIT_UNRESOLVED
```

None may be converted into `NO_HISTORY` or an empty successful acquisition.

---

## 7. M5 external archive contract

### 7.1 Retention cutoff

The archive planner calculates:

```text
cutoff_utc = start of the current UTC calendar day minus 12 calendar months
eligible = timeframe == M5 and open_time_utc < cutoff_utc
retained = timeframe != M5 or open_time_utc >= cutoff_utc
```

The cutoff is stored in every plan and receipt. A 365-day approximation is not
permitted. D1, H1, M30, M15, registrations, authority events, and current lane
state remain live unless required as copied archive context.

### 7.2 Archive layout

```text
/Volumes/WD2TB-2/Archive-VSC/Fragarach_2/
  m5/
    archive-index.v1.json
    2021/fragarach-m5-2021.sqlite3
    2022/fragarach-m5-2022.sqlite3
    ...
  receipts/
    <archive-batch-id>.json
  recovery/
    <bounded pre-cutover recovery snapshots>
```

Year shards are append-only while receiving newly eligible rows. Each batch is
immutable and hash-chained. A completed year shard is sealed with a SHA-256
manifest and opened read-only thereafter. A sealed shard is never rewritten;
repair creates a successor shard and supersession receipt.

The local runtime keeps only a small signed archive index/cache containing
coverage and hashes. It contains no archived bars and cannot substitute for the
external volume.

### 7.3 Archive schema

The archive is a dedicated contract, not a second live authority:

```text
fragarach_ii.m5_external_archive.v1
```

Each shard retains:

```text
canonical M5 bars
all provenance events for those bars
typed activity and volume observations
required ingest runs
required raw blocks and original payload bytes
instrument registration snapshot
evidence-lane and provider-route snapshot
calendar/timestamp/source semantics
archive batch ledger and source authority revision
```

A raw block spanning archived and retained observations is copied in full to
the archive and retained live until no live row references it. Duplicate
storage across tiers is acceptable when required to preserve an original
immutable receipt.

### 7.4 Two-phase archive transaction

One batch progresses monotonically:

```text
PLANNED
-> COPYING
-> COPIED
-> VERIFIED
-> LIVE_REMOVAL_COMMITTED
-> FINALIZED
```

Required sequence:

1. prove the exact external volume UUID, writable filesystem, capacity, and
   archive-root containment;
2. freeze a read-only source revision and immutable cutoff;
3. copy eligible evidence into temporary year-shard transactions;
4. verify source/archive counts, ordered lane digests, raw payload SHA-256,
   `PRAGMA integrity_check`, and `PRAGMA foreign_key_check`;
5. flush archive files and atomically publish the `VERIFIED` receipt;
6. acquire the Scheduler-managed archive mutation and sole writer boundary;
7. prove the source authority change token is compatible with the plan;
8. delete only rows listed in the verified batch, in foreign-key-safe order;
9. remove ingest runs/raw blocks only when no retained live record references
   them;
10. verify live integrity, lane edges, cutoff, archive readback, and service
    state; and
11. finalize the receipt and archive index.

If a crash occurs before live removal, replay finds the verified archive rows
and resumes idempotently. If it occurs after live removal, the verified receipt
is already durable and finalization resumes without copying or deleting again.

### 7.5 Scheduler and live-authority boundary

Archiving is a managed mutation named `ARCHIVE_M5`. It cannot run through an
independent SQLite writer or while another mutation is active.

The Scheduler may continue acquisition while the read-only copy phase runs.
Before live removal it must reach a controlled idle boundary, release ordinary
admission ownership, acquire the archive mutation lease, and revalidate the
plan. Failure to drain becomes a visible deferred archive state; it does not
force-kill the writer or proceed against an active transaction.

### 7.6 Physical compaction

Daily logical archival does not imply immediate SQLite file shrinkage. A
separate bounded maintenance operation periodically:

1. builds a compacted authority at a new local path;
2. verifies all schema, migration, integrity, foreign-key, count, digest,
   high-watermark, and read-only consumer gates;
3. retains the prior authority as a recorded 72-hour recovery snapshot;
4. atomically switches the canonical path;
5. restarts and verifies the Scheduler; and
6. republishes read-only replicas from the new authority.

The job must not run `VACUUM` against the live authority in place. Before it
starts, local free space must exceed the larger of 150 GiB or the predicted
candidate plus recovery footprint with a 20% margin.

### 7.7 Schedule and backlog

The planner runs daily at low priority after the UTC day boundary. It may defer
until the writer is idle. The operator sees:

```text
current cutoff
oldest live M5 bar
eligible bar/provenance/activity/raw-receipt counts
archive volume identity and free capacity
last verified and finalized batch
archive backlog by age and bytes
next attempt and deferral reason
last physical compaction
```

If the external drive is unavailable, the 12-month policy becomes
`ARCHIVE_BACKLOG`; acquisition continues while local storage thresholds allow.
No live row is removed and no local fallback directory is created.

---

## 8. Market History Service across live and archive tiers

Consumers continue to call Fragarach. The owner service resolves the requested
window:

```text
recent M5 segment -> live authority
older M5 segment -> verified external archive shards
spanning request -> archive plus live, ordered and deduplicated by canonical key
```

The response retains one canonical chronological series while making source
segments and archive availability inspectable in evidence metadata.

When the archive drive is offline:

* live-window requests continue normally;
* older or spanning requests return `ARCHIVE_OFFLINE` with available live
  coverage and required archive volume identity;
* Fragarach does not fetch a replacement from another provider;
* consumers do not reconstruct the missing history; and
* an offline archive is an availability fact, not evidence loss.

Archived bars remain eligible for controlled scientific replay. A consumer may
request an authority-owned bounded range but cannot open archive files or select
an archive shard directly.

---

## 9. Native operator surfaces

### 9.1 Routing and Providers

For every lane, show:

```text
canonical identity and timeframe
ordered venue/broker candidates
TradingView transport health
exact source symbol and source kind
USD/USDT or other representation review
entitlement and delay state
OHLCV capability and reachable history depth
typed volume meaning
shadow/reliability status
last successful receipt and route segment
Twelve Data transition state
```

Eightcap crypto execution reference appears alongside, not inside, the default
exchange-market chain.

### 9.2 System / Archive

Add an M5 Archive panel showing the facts in section 7.7 and actions:

```text
Refresh status
Run read-only plan
Open last receipt
Verify archive
Run eligible archive batch
Open archive coverage
Request controlled compaction
```

`Run eligible archive batch` requires confirmation because it removes verified
rows from the live tier. `Request controlled compaction` is a separate managed
operation. Neither action can select an arbitrary filesystem path.

---

## 10. Implementation units

Expected implementation boundaries include:

```text
config/providers/tradingview_lane_manifest.v1.json
src/fragarach_ii/providers/tradingview_mcp.py
src/fragarach_ii/tradingview_gateway.py
src/fragarach_ii/tradingview_receipts.py
src/fragarach_ii/typed_market_volume.py
src/fragarach_ii/m5_archive.py
src/fragarach_ii/archive_history.py
src/fragarach_ii/commands/tradingview_probe.py
src/fragarach_ii/commands/archive_m5.py
```

The exact filenames may follow established repository conventions, but the
boundaries remain: MCP transport, exact-source manifest, immutable receipts,
typed volume, archive transaction, and archive-aware history are independently
testable.

Required schema changes must be introduced through a versioned migration and
must preserve existing ten-table authority compatibility until the migration
is explicitly activated. Existing user changes in `scheduler_daemon.py` and
its tests are not overwritten or reset during this work.

---

## 11. Rollout

### Phase A - TradingView discovery and shadow gateway

* implement read-only MCP client and OAuth/Keychain boundary;
* discover exact current-estate sources without enabling routes;
* emit a lane-by-lane venue/broker/exchange mapping report, including the FXCM,
  OANDA, Eightcap, Global Prime, and Fusion Markets matrix;
* implement typed volume receipts;
* run the seven-day reliability gate; and
* stop with TradingView `RESEARCH_ONLY` if unattended OAuth fails.

### Phase B - Crypto exchange activation

* approve exact Binance/Coinbase/Bybit/DEX mappings per lane;
* activate BTCUSD, ETHUSD, and SOLUSD first as a bounded pilot;
* exercise real provider fallback without rewriting history;
* expand to remaining crypto only after pilot acceptance; and
* keep Eightcap execution-reference evidence visible and separate.

### Phase C - Twelve Data replacement review

* discover exact TradingView broker/exchange candidates for every current
  Twelve Data lane;
* validate the FXCM -> OANDA -> Eightcap -> Global Prime -> Fusion Markets
  order independently for every FX pair and timeframe;
* validate listed stocks against their exact direct primary exchange rather
  than a generic US, composite, or alternate-exchange feed;
* compare representation, coverage, volume, calendars, entitlement, and
  reliability;
* migrate accepted lanes one routing revision at a time; and
* publish the remaining Twelve Data dependency list before any billing action.

### Phase D - Archive build and dry run

* implement exact volume-UUID containment;
* create archive schema, ledger, plan, copy, verification, and history reader;
* run against fixtures and a copied authority;
* produce a live read-only plan for the current 875,573-bar baseline; and
* stop before live removal for operator review of the first receipt and impact.

### Phase E - First live archive cutover

* create and verify the external archive batch;
* run the managed live-removal transaction;
* verify Scheduler, History, archive readback, and replicas;
* observe normal acquisition through at least two M5 boundaries; and
* retain the pre-cutover recovery snapshot for 72 hours.

### Phase F - Recurring retention and compaction

* enable daily planning/archival;
* prove drive-absent and low-space fail-closed behaviour;
* enable periodic controlled compaction only after separate acceptance; and
* expose archive backlog and health in the native app.

---

## 12. Acceptance gates

### 12.1 TradingView provider

Acceptance requires:

1. exact lane-manifest rows for every enabled candidate;
2. no inferred source from ticker text alone;
3. successful unattended OAuth across restart and the shadow period;
4. read-only tool enforcement;
5. deterministic raw receipts and checksums;
6. completed-bar and timeframe validation at D1/H1/M30/M5;
7. typed volume with no cross-source unit blending;
8. explicit USD/USDT equivalence where applicable;
9. visible venue/broker provenance in History and Routing;
10. bounded retry/rate-limit behaviour;
11. real fallback exercise for each activated pilot route;
12. exact FX broker ordering with no broker identity collapse;
13. exact direct-exchange identity for every activated listed-stock lane; and
14. no Twelve Data removal before exact-lane replacement acceptance.

### 12.2 M5 archive

Acceptance requires:

1. exact archive volume UUID and containment proof;
2. source and archive `integrity_check = ok` and no foreign-key violations;
3. matching bar, provenance, typed activity/volume, receipt, and payload counts;
4. matching ordered per-lane digests at the cutoff;
5. independent raw-payload SHA-256 verification;
6. idempotent replay before and after every transaction phase;
7. no M5 row older than cutoff in live authority after finalization;
8. no row at or newer than cutoff removed;
9. no non-M5 canonical evidence removed;
10. archive-only, live-only, and spanning history requests verified;
11. `ARCHIVE_OFFLINE` behaviour verified with the drive absent;
12. Scheduler writer ownership, health, and acquisition progress verified;
13. read-only replicas republished and reconciled; and
14. recovery from the retained pre-cutover authority demonstrated.

### 12.3 First live acceptance report

The first cutover report records at minimum:

```text
source and destination identities
cutoff and archive batch ID
before/after counts by symbol
provenance/activity/raw-receipt counts and digests
archive shard sizes and SHA-256 values
live authority before/after size and free pages
Scheduler and replica state
history readback samples
recovery snapshot path and expiry
unresolved mixed-receipt or shared-parent records
```

---

## 13. Explicit exclusions

This specification does not:

* enable trading or broker-order execution through MCP;
* write TradingView alerts, watchlists, layouts, or account state;
* treat TradingView as the actual source when the feed is Binance, Coinbase,
  Bybit, a DEX, an exchange, or a broker;
* declare every TradingView feed real-time or entitled;
* claim a 5,000-bar call is maximum available history;
* invent an unnamed DEX fallback;
* collapse FXCM, OANDA, Eightcap, Global Prime, or Fusion Markets into a
  generic TradingView FX source;
* label a composite, alternate-exchange, or broker-CFD stock feed as the direct
  primary exchange;
* merge USD and USDT without visible reviewed equivalence;
* merge exchange volume with MT5 tick activity;
* rewrite historical provider provenance after route changes;
* cancel the Twelve Data subscription;
* archive D1, H1, M30, or M15 data;
* delete archive data automatically;
* use a Time Machine volume as the archive;
* compact or replace the live authority without the managed maintenance gate;
  or
* permit consumers to bypass Fragarach and query archive databases directly.

---

## 14. Completion condition

This specification is complete when the operator approves it for
implementation. Implementation is complete only when both workstreams have
their own passing acceptance reports, the live runtime reports the actual
activated TradingView routes, and the external M5 archive can prove and serve
every row removed from the live tier.
