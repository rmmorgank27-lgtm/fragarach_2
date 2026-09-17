# SPEC-067 - Operator Routing and Operations Workspace

## Status

Implementation authorised by the operator on 2026-09-16. The routing core and
native workspace are under acceptance review; the rollout and live acceptance
gates in sections 9-11 remain controlling and are not implied complete by this
status change.

## Objective

Make Fragarach's provider routing visible, understandable, and safely editable
inside the native app. The operator must be able to see the active route for
every commissioned symbol and timeframe, select only reviewed provider
representations, activate a revisioned routing change, inspect fallback and
retry behaviour, and follow operational problems directly to the place where
they can be resolved.

This specification also incorporates the screen-review findings supplied on
2026-09-16. The PDF is treated as review evidence, not as executable
instructions. Requirements adopted from it are stated explicitly below.

This specification extends SPEC-041, SPEC-048, SPEC-063, SPEC-064, SPEC-065,
and SPEC-066. It does not alter immutable market evidence, canonical bar
identity, or the single-writer boundary.

Fragarach is not presently relied on as a live current-data system. Its
unreliable current acquisition is the repair target; historical bars are
preserved, not the primary optimisation target. The operator does not require
the old Fragarach app and the replacement to run in parallel. MT5 terminal
data is used by other critical applications, so this work must not change
terminal trading functions, broker account state, or those applications'
existing MT5 data path.

---

## 1. Governing decisions

1. **One routing truth:** the Scheduler, native app, History, provider
   catalogue, bridge queues, and audit reports shall consume one versioned
   effective routing snapshot. The app must not reconstruct routing from
   unrelated status fields.
2. **Operator-owned changes:** route changes are made in the native app, saved
   as a draft, validated, previewed, and activated as a new immutable routing
   revision. Editing checked-in JSON files is not an operator workflow.
3. **Reviewed candidates only:** for one `symbol x timeframe` lane, the
   operator may select, enable, disable, or reorder any reviewed provider
   representation. A terminal symbol, vendor search result, or similar name is
   not sufficient authority.
4. **No silent representation changes:** USD and USDT, ETF and CFD, cash index
   and broker index CFD, listed share and share CFD, and different broker feeds
   remain distinct representations. Any approved equivalence is named and
   visible.
5. **One estate-wide default order:** new and non-overridden lanes inherit
   `MT5 -> BINANCE / COINGECKO -> YAHOO_FINANCE -> TWELVE_DATA` after
   applicability checks. A revisioned lane override may disable or reorder any
   reviewed candidate for that exact lane. Binance/CoinGecko remains
   crypto-only, and an override cannot invent an unsupported representation.
6. **Fallback is lane-specific:** every `symbol x timeframe` cell records an
   ordered primary and zero or more approved fallbacks. A class-level default
   is only a template; the effective lane route is authoritative.
7. **Historical truth is preserved:** activating a route affects future
   acquisition only. It cannot rewrite admitted bars, provenance, receipts, or
   history.
8. **Operational status must lead to action:** every critical, behind,
   blocked, stale, or bridge-degraded state links to the relevant route,
   Scheduler lane, History lane, or managed recovery control.
9. **Automatic attempts are bounded:** no lane may retry indefinitely within
   one expected boundary. The UI displays the exact attempt count, provider,
   last outcome, next action, and cap.
10. **Provider catalogue scope is bounded:** the catalogue shows the current
   Fragarach estate and reviewed candidates. For large crypto catalogues it
   states that more symbols are available through Discover, but never lists
   every Binance, CoinGecko, CoinGecko DEX, Eightcap, or Fusion symbol.
11. **Presentation may group related products; authority may not:** the Estate
    view may present cash indices, ETFs, and broker index CFDs in one Indices
    family, but their canonical identities, histories, routes, and provider
    representations remain separate.

---

## 2. Current-estate baseline and target routing model

The baseline was read from the live authority and provider/bridge projections
on 2026-09-16. It contains 191 recorded lanes: 187 active routes and four
retired or invalidated D1 lanes retained for historical visibility. The
inactive lanes must remain visible but cannot be edited or acquired.
This section records the starting point for migration; the implemented screen
must always render the current effective snapshot rather than hard-code this
table.

### 2.1 Twelve Data remains materially active in the pre-migration estate

Twelve Data is enabled, its credential is available, its reviewed operational
budget is 55 requests per 60 seconds, and its concurrency limit is 4. It is
still used in three roles:

* primary provider for `HYPEUSD` at D1, H1, M30, and M5 because no
  higher-priority reviewed candidate is currently executable;
* primary ahead of Yahoo for AMZN, META, NVDA, QQQ, and TSLA at D1 under the
  legacy runtime ordering, which must be migrated to Yahoo before Twelve Data;
  and
* approved MT5 failure fallback for the FX, metals, energy, and selected crypto
  lanes listed below.

The current Provider Facts inventory reports only one configured Twelve Data
mapping even though the live resolver exposes many reviewed current-estate
representations. The replacement catalogue must distinguish shipped mappings,
resolved representation facts, active lane routes, and last-used provenance
instead of presenting one ambiguous mapping count.

### 2.2 Estate-wide default provider priority

The routing workspace, Scheduler, bridge failover grants, and acquisition
orchestrator shall all use this estate-wide default:

```text
1. approved and available MT5 lane
2. approved Binance / CoinGecko candidate for crypto
3. approved Yahoo Finance representation
4. approved Twelve Data representation
5. fail closed / attention required
```

Within the Binance/CoinGecko tier, the lane revision records the deterministic
order. For example, Binance may lead for a reviewed exchange intraday pair,
while CoinGecko DEX may be the only reviewed candidate for a particular pool.

The order is conditional on applicability. A normal FX lane therefore skips
the crypto tier. An intraday lane skips Yahoo when Yahoo has only D1 authority.
A broker index CFD with no equivalent fallback fails closed after MT5. Twelve
Data may become the effective primary only when every higher tier is
inapplicable or unavailable under the active route revision, or when an
explicit lane override disables or moves those candidates below Twelve Data.
The app must label that outcome as a lane override, not as the estate default.

### 2.3 Pre-migration effective routing table

Provider symbols are shown because the canonical symbol alone is insufficient
to explain the route.

| Canonical symbols | Timeframes | Primary | Approved fallback(s) | Current boundary |
| --- | --- | --- | --- | --- |
| AUDCAD, AUDJPY, AUDNZD, AUDSGD, AUDUSD, EURAUD, EURJPY, EURNZD, EURUSD, GBPAUD, GBPCHF, GBPJPY, GBPNZD, GBPUSD, NZDJPY, NZDUSD, USDCAD, USDCHF, USDJPY | D1, H1, M30, M5 | Fusion MT5 `<symbol>.r` | Twelve Data direct FX pair | No Yahoo fallback |
| XAUUSD, XAGUSD | D1, H1, M30, M5 | Fusion MT5 `XAUUSD.r` / `XAGUSD.r` | Twelve Data `XAU/USD` / `XAG/USD` | Exact metal identity retained |
| UKOIL, USOIL | D1, H1, M30, M5 | Fusion MT5 `XBRUSD.r` / `XTIUSD.r` | Twelve Data `XBR/USD` / `WTI/USD` | `USO` ETF is not a fallback |
| NAS100, US30, US500 | D1, H1, M30, M5 | Fusion MT5 `.r` broker CFD | None | Fail closed; no ETF or cash-index substitution |
| XOM | H1, M30, M5 | Fusion MT5 `ExxonMobil.r` CFD | None | D1 listed share is a separate route |
| ADAUSD, BNBUSD, BTCUSD, SOLUSD, XRPUSD | D1, H1, M30, M5 | Eightcap MT5 exact USD CFD | None in the live failover path | Binance/CoinGecko capability exists but is not currently executable failover |
| AVAXUSD, DOGEUSD, DOTUSD, LINKUSD, PEPEUSD, SUIUSD | D1, H1, M30, M5 | Eightcap MT5 exact USD CFD | Twelve Data direct USD representation | Do not silently substitute USD/USDT |
| ETHUSD | D1 | Eightcap MT5 `ETHUSD` | Twelve Data `ETH/USD` | D1 only has the Twelve Data grant |
| ETHUSD | H1, M30, M5 | Eightcap MT5 `ETHUSD` | None | Fail closed |
| HYPEUSD | D1, H1, M30, M5 | Twelve Data `HYPE/USDT` | None | Explicit reviewed USD/USDT equivalence |
| AMZN, META, NVDA, QQQ, TSLA | D1 | Twelve Data exact symbol | Yahoo exact symbol | Legacy order; migrate to Yahoo before Twelve Data |
| AAPL, AMD, ASXBHP, ASXCBA, CAT, DE, DIS, DJI, FDX, GOOGL, JPM, LLY, MSFT, PFE, SHOP, SPY, UBER, USO, XOM | D1 | Yahoo reviewed symbol | None | DJI uses `^DJI`; BHP/CBA retain `.AX`; USO is the ETF |
| NAS100, US30, US500, XOM | M15 | Derived from governed M5 | None | Internal derived lane; no provider request |
| JPYCHF, LSEHSBA, LSERIO, XAGUSDCFD | D1 | None | None | No executable route; operator review required |

### 2.4 Known routing inconsistencies to remove

1. The route manifest advertises crypto order `MT5 -> BINANCE -> COINGECKO`,
   but the live MT5 failure-grant contract can release only Twelve Data. The
   effective route shown above is the live behaviour and must remain the truth
   until this specification's unified route engine is activated.
2. CoinGecko DEX is reviewed for PEPEUSD M5/H1 and Binance/CoinGecko are
   reviewed for current-estate crypto, but those candidates cannot currently
   participate after an MT5-primary failure unless the separate orchestration
   path is selected.
3. The Fusion receiver previously used the index-CFD authority for FX,
   metals, energy, and XOM. On 2026-09-16 Windows staged the versioned
   non-index market-data authority and Mac issuance/validation was cut over,
   while the index reference remained unchanged. Live new-reference receipts
   remain unverified because the Fusion terminal is absent; old non-index
   receipts remain accepted during the compatibility window. Route activation
   stays gated until both remote receipt classes are proven.
4. Several lane retry counters are lifetime-like totals in the hundreds. They
   do not express bounded attempts for the current expected boundary.
5. Provider Facts, MT5 terminal catalogues, class policy, operator D1
   overrides, and dynamic representation facts are separate sources. The app
   cannot currently display one authoritative effective route revision.

---

## 3. Information architecture

### 3.1 Manage Data navigation

Manage Data shall contain four primary sections in this order:

```text
Discover | Routing & Providers | Acquire & Import | System
```

`Routing & Providers` replaces System > Provider Facts as the normal operator
surface. System may retain a read-only technical projection for diagnostics,
but it must link back to the editable routing workspace and must not present a
second route editor.

### 3.2 Cross-screen navigation context

Every route link carries:

```text
canonical symbol
optional timeframe
origin screen
optional expected boundary / audit / operation identifier
```

The destination opens Routing & Providers with the symbol selected and the
requested timeframe highlighted. A Back action returns to the originating
screen without losing its filters.

Required links:

| Origin | Link/action | Destination |
| --- | --- | --- |
| Overview - last failed update | `Open symbol route` | Routing & Providers, symbol/timeframe selected |
| Overview - Due now | `Open Scheduler` | Scheduler filtered to due lanes |
| Overview - Critical | `Review critical lanes` | Estate/Scheduler critical list with actions |
| Estate Truth symbol/timeframe cell | `Manage route` | Routing & Providers, exact cell selected |
| Scheduler lane | `Open route` | Routing & Providers, exact lane selected |
| Scheduler lane | `Open history` | History, exact lane selected |
| History symbol | `View current routing` | Routing & Providers, symbol with all timeframes |
| History provenance row | `View acquisition receipt` | Immutable operation/audit detail |
| Audit finding | `Open affected route` | Routing & Providers, affected lane selected |

History must label the link **current routing**. It must not imply that the
current route was the source of older bars; historical provider identity comes
from provenance.

---

## 4. Routing workspace

### 4.1 Default overview

The default screen is a searchable symbol-by-timeframe matrix. It shows all
timeframes for a symbol at once, including derived lanes.

| Symbol | D1 | H1 | M30 | M15 | M5 | Attention |
| --- | --- | --- | --- | --- | --- | --- |
| GBPCHF | Fusion -> Twelve Data | Fusion -> Twelve Data | Fusion -> Twelve Data | - | Fusion -> Twelve Data | Healthy |
| US500 | Fusion only | Fusion only | Fusion only | Derived M5 | Fusion only | Behind |

Each route cell displays:

* primary provider and provider symbol;
* ordered fallback providers;
* estate-default or lane-override state;
* mapping class or explicit equivalence;
* active routing revision;
* capability/credential/bridge availability;
* last provider actually used and receipt time;
* current attempt state, for example `Attempt 2 of 3`;
* next scheduled action; and
* attention reason when the route is not executable.

The matrix supports filters for market family, route provider, no fallback,
fail-closed, no executable route, unhealthy provider, pending draft, and
attention severity. Technical hashes and raw payloads live in a disclosure,
not in the default table.

### 4.2 Route detail and editing

Selecting a cell opens a route editor containing:

```text
canonical identity and representation
timeframe and calendar/session authority
ordered provider candidates
provider symbol and representation class
credential, entitlement, capability, and bridge state
fallback trigger classification
last-used provider and immutable receipt link
current revision and effective time
```

Allowed operator actions:

* reorder any reviewed candidates for the selected lane;
* add a reviewed catalogue candidate to the fallback chain;
* enable or disable a candidate for future requests;
* remove a candidate from the lane route;
* choose fail-closed after the last candidate;
* copy one reviewed route to selected timeframes only after per-timeframe
  validation;
* save as draft;
* validate and preview impact;
* activate a revision with an operator reason;
* restore the lane to estate-wide defaults; or
* restore a prior revision by creating a new activation event.

The operator may disable every provider candidate for a lane. After explicit
confirmation and an operator reason, the lane activates as `No provider - fail
closed`, remains visible as attention required, and does not fall back through
an unlisted or disabled provider.

Not allowed in the route editor:

* typing an arbitrary provider symbol;
* approving a new economic equivalence;
* converting USD/USDT or ETF/CFD implicitly;
* enabling an unsupported timeframe;
* bypassing a missing credential or entitlement;
* changing canonical identity; or
* altering historical provenance.

New aliases or equivalent representations use a separate **Review
representation** workflow. The result becomes a selectable catalogue candidate
only after its identity, mapping class, calendar, capability, and authority
receipt pass review.

### 4.3 Draft validation and activation

Saving a route never activates it immediately. Activation requires:

1. structural validation of symbol, timeframe, candidate order, and duplicate
   providers;
2. representation validation for every provider symbol;
3. capability and credential validation;
4. calendar/session validation for D1;
5. resolution of the effective order from estate defaults plus the proposed
   lane override;
6. fallback-trigger validation;
7. a shadow plan showing affected lanes and pending requests;
8. an operator reason; and
9. atomic activation of a new routing revision.

Pending provider/bridge requests remain pinned to the routing revision under
which they were created. The activation preview offers either:

* **allow existing request to finish**, preserving its revision; or
* **cancel and re-plan**, producing a visible cancellation receipt.

There is no silent mutation of in-flight work.

Every overridden lane displays `Lane override`, the changed order, disabled
providers, operator reason, activation time, and routing revision. **Restore
estate defaults** removes the lane override in a new revision, re-evaluates the
currently applicable providers, previews the resulting order, and requires
normal activation. It does not restore stale provider capabilities or rewrite
history.

For example, an operator may disable MT5 for `GBPCHF x H1` while retaining its
reviewed Twelve Data representation. Twelve Data then becomes the effective
provider for that lane only; `GBPCHF` at other timeframes and all other symbols
remain unchanged unless they have their own activated overrides.

### 4.4 Revision storage

Shipped configuration remains a versioned seed. Operator revisions are stored
outside the source checkout under the Fragarach application-support directory:

```text
routing/revisions/<routing-revision>.json
routing/active.json
routing/audit/<activation-id>.json
```

Each immutable revision contains:

```text
contract and schema version
routing revision and parent revision
created/activated timestamps
operator reason
estate-wide default order
lane overrides, disabled candidates, and inheritance state
complete effective lane routes
representation authority references
provider-capability revision references
content hash
```

The active pointer is replaced atomically under an exclusive lock. The app
never writes the checked-in orchestrator or MT5 manifest files. Existing D1
operator overrides are migrated into the first routing revision and preserved
as migration evidence.

---

## 5. Provider catalogue

### 5.1 Required provider card

Each provider card displays:

```text
provider and broker identity
enabled / disabled state
credential and entitlement state
supported asset classes and timeframes
current-estate reviewed symbols
active primary / fallback lane counts
rate and concurrency policy
live health and last verified time
capability revision and source
whether additional symbols may be available through Discover
```

The catalogue must never equate "listed by provider" with "approved for
Fragarach". MT5 cards distinguish total terminal symbols, current-estate
matches, and bridge-authorised routes.

### 5.2 Current-estate catalogue baseline

| Provider | Current-estate capability | Timeframes | Catalogue note |
| --- | --- | --- | --- |
| Fusion MT5 - Markets | 19 FX pairs; XAUUSD, XAGUSD; UKOIL, USOIL; NAS100, US30, US500; XOM intraday | D1/H1/M30/M5, except XOM H1/M30/M5 | Terminal reported 250 symbols; show only the current estate and state that more reviewed symbols may be available |
| Eightcap MT5 - Crypto | ADAUSD, AVAXUSD, BNBUSD, BTCUSD, DOGEUSD, DOTUSD, ETHUSD, LINKUSD, PEPEUSD, SOLUSD, SUIUSD, XRPUSD | D1/H1/M30/M5 | Terminal reported 134 symbols and 12 authorised current-estate mappings; do not enumerate the other crypto symbols |
| Binance | ADAUSD, AVAXUSD, BNBUSD, BTCUSD, DOGEUSD, DOTUSD, ETHUSD, LINKUSD, SOLUSD, XRPUSD through reviewed USD/USDT equivalence | D1/H1/M30/M5 | Additional Binance symbols exist; do not list them until added to the estate and reviewed |
| CoinGecko | ADAUSD, AVAXUSD, BNBUSD, BTCUSD, DOGEUSD, DOTUSD, ETHUSD, LINKUSD, SOLUSD, XRPUSD | D1 | Additional coins exist; current-estate only |
| CoinGecko DEX | PEPEUSD reviewed pool | M5/H1 | Additional pools exist; current-estate only and pool identity remains explicit |
| Yahoo Finance | AAPL, AMD, AMZN, ASXBHP, ASXCBA, CAT, DE, DIS, DJI, FDX, GOOGL, JPM, LLY, META, MSFT, NVDA, PFE, QQQ, SHOP, SPY, TSLA, UBER, USO, XOM | D1 | Current-estate list only |
| Twelve Data | Current reviewed/resolved FX, metals, energy, selected equities/ETFs, and selected crypto listed in the effective route table | D1/H1/M30/M5 where individually verified | Final external fallback; more symbols may be available through bounded Discover review |
| Fragarach derived data | NAS100, US30, US500, XOM M15 derived from governed M5 | M15 | Internal derivation, not an external provider |

### 5.3 Catalogue selection rules

A provider representation is selectable for a lane only when all are true:

```text
symbol is in the active estate
representation review is approved
timeframe capability is verified
credential/entitlement requirements can be satisfied
calendar/session authority is defined where required
provider or bridge identity is current
route authority scope includes the market class
```

An unavailable candidate remains visible with a plain-language reason, but it
cannot be activated.

---

## 6. Retry, fallback, and recovery behaviour

### 6.1 Per-cadence attempt budget

The Scheduler records an attempt budget keyed by:

```text
canonical symbol + timeframe + expected boundary + routing revision
```

The maximum is **3 automatic provider/bridge dispatch attempts in total** for
that key. The first dispatch is attempt 1; there is no automatic attempt 4.
Switching to a fallback counts as another attempt. Scheduler evaluation,
credit-window waiting, node-capacity waiting, and provider cooldown waiting do
not increment the attempt count because no provider request was sent.

MT5 queue and HTTP Scheduler dispatch must debit the same Fragarach-owned
operational attempt ledger. The ledger is separate from the signed MT5 request
and response payloads so that routing metadata cannot weaken receipt checksum
validation or alter the Windows terminal contract. An MT5 request counts once
when it is handed to the bridge transport; expiry, repeated polling, and
receipt admission must not count it again. The HTTP fallback planner consumes
that recorded attempt before selecting its first HTTP provider.

After attempt 3 fails, the lane enters `ATTENTION_REQUIRED` with:

* last provider/node and outcome;
* all three attempt receipts;
* next normal cadence boundary;
* available operator actions; and
* whether a healthy reviewed fallback remains.

A new expected boundary receives a new budget. A manual action against the
same boundary is recorded as an operator attempt and must not silently reset
or erase the automatic count.

### 6.2 User-visible actions

The ambiguous `Queue M...` control is replaced with actions whose outcomes are
clear:

* **Attempt now** - enqueue one idempotent attempt for the selected lane;
* **Try next fallback** - available only when a reviewed next route exists;
* **Review route** - opens the exact routing cell;
* **Open issue details** - shows receipts, failure classification, and next
  automatic action; and
* **Acknowledge attention** - records acknowledgement without pretending the
  lane is healthy.

The Scheduler lane row always shows `Attempt n of 3`, last attempt time,
provider, result, retry-not-before time, and next fallback.

### 6.3 Managed MT5 bridge recovery

System and Scheduler show each bridge separately. Replace the misleading
`Active lanes` count with:

```text
authorised current-estate routes
pending requests
completed/expired receipt counts
last accepted receipt
bridge and terminal heartbeat
watchdog state and reason
accepted vs required authority revision
last restart and restart count
```

When a bridge is degraded or critical, offer **Request managed restart**. The
app sends a signed, idempotent control request to the owning Windows watchdog;
it does not kill a remote process directly. The UI displays request ID,
accepted/rejected state, progress, final status, and refreshed heartbeat. The
control is rate-limited and disabled while a restart is already active.

Restarting a bridge does not change a provider route, reset lane attempt
evidence, enable trading, or bypass receipt validation.

---

## 7. Screen changes adopted from the structure review

### 7.1 Overview

* Move critical attention near the top of the screen.
* Increase the critical count/status typography by 4 points relative to the
  current presentation, while retaining the existing compact visual hierarchy.
* Make Last failed update, Due now, and Critical actionable using the links in
  section 3.2.
* Provide an **Attempt recovery** action only after the affected lane and
  proposed action are shown.

### 7.2 Estate Truth

* Present cash/index products, ETFs, and broker index CFDs in one **Indices**
  market-family collection.
* Inside the collection, retain representation labels such as `Cash index`,
  `ETF`, and `Broker CFD` and separate canonical symbols.
* Do not merge scores, histories, route identities, or health solely because
  products share an underlying market.
* Increase critical typography by 4 points and make critical cells open their
  affected lanes.

### 7.3 Acquire & Import

* Remove the permanently expanded all-instrument sidebar from the acquisition
  workflow.
* Replace it with a compact searchable symbol selector and recent selections.
* Move route inspection and editing to Routing & Providers.
* Retain a concise read-only route summary for the selected acquisition lane,
  with a `Manage route` link.
* Reduce default technical detail to decision-relevant facts. Raw candidate
  matrices remain available in a disclosure.
* Every Fetch/Update/Force Refresh action shows an activity indicator,
  operation ID, stage, progress where available, and final receipt or error.

### 7.4 Scheduler

* Retain the existing overall layout.
* Make lane rows link to routing and history.
* Show per-boundary attempt counts and the 3-attempt cap.
* Make `Run Queue Now` visibly active while work is being accepted and report
  the operation outcome rather than only refreshing the page.

### 7.5 History and estate audit

* Place `View current routing` beside the symbol/timeframe summary.
* For each audit finding, display whether automatic repair was eligible,
  attempted, succeeded, failed, or was not attempted.
* Show attempt time, action, affected lane count, result, reason, operation ID,
  and immutable receipt link.
* Do not describe a finding as repaired without a successful verification
  result.

### 7.6 System and provider facts

* Replace Provider Facts with the live Provider Catalogue and route revision
  summary defined in section 5.
* Display generation and verification times prominently and label stale data.
* Keep credentials redacted; show only state.
* Give bridge failures a plain-language cause and managed restart path.

---

## 8. Service and data contracts

### 8.1 Effective routing snapshot

Introduce `fragarach_ii.routing_snapshot.v2`:

```json
{
  "contract": "fragarach_ii.routing_snapshot.v2",
  "routing_revision": "sha256:...",
  "generated_at_utc": "...",
  "active_revision": {"parent": "...", "activated_at_utc": "..."},
  "providers": [],
  "lanes": [],
  "attention": [],
  "source_revisions": {}
}
```

Each lane contains canonical identity, timeframe, derivation state, ordered
route candidates, provider symbols, mapping classes, authority references,
capability state, last-used provenance, attempt state, and next action.

### 8.2 Routing commands

Introduce an app-facing command contract with these operations:

```text
read snapshot
create/update draft
validate draft
preview activation
activate draft
restore lane to estate defaults
restore prior revision
review representation
```

All mutating commands return an operation ID and immutable receipt. Commands
are serialized through the routing service owner and use atomic sidecar writes.
The native app remains a client and never writes canonical SQLite directly.

### 8.3 Provider catalogue snapshot

Introduce `fragarach_ii.provider_catalogue.v2`, generated from:

```text
configured provider contracts
reviewed representation facts
current active estate
live MT5 catalogues and health
credential/entitlement state
active routing revision
last successful provenance
```

The snapshot records source timestamps and marks itself stale when any required
live input exceeds its freshness budget. It does not reuse an old provider
fact projection without a stale warning.

### 8.4 Attempt and repair evidence

Every provider attempt, automatic repair, operator repair, bridge restart, and
route activation records:

```text
operation and correlation IDs
symbol, timeframe, expected boundary
routing revision
provider, provider symbol, and node
automatic or operator origin
attempt ordinal and cap
start/end timestamps
classified outcome
next action
verification result
receipt/evidence references
```

---

## 9. Authority repair required before route editing goes live

The present `MT5_BROKER_FAMILY_INDEX_CFD_AUTHORITY_V1` reference must not
remain the general receipt authority for Fusion FX, metals, energy, equities,
and indices.

Before editable routes can activate:

1. create a correctly scoped, versioned Fusion read-only market-data receipt
   authority, or separate authorities by representation family;
2. retain the index-CFD identity authority for index-CFD representation
   decisions only;
3. migrate the Fusion bridge trusted reference with an explicit compatibility
   window and receipt;
4. prove a non-index and an index request under the new scope;
5. expose required and accepted authority revisions in bridge status; and
6. reject a route candidate whose authority scope does not include its asset
   class and timeframe.

This is an authority naming/scope repair, not permission to broaden terminal
access, weaken receipt validation, or enable trading.

Staged cutover references (2026-09-16): non-index Fusion requests use
`MT5_FUSION_MARKET_DATA_NON_INDEX_AUTHORITY_V1:110b82bfb8154b75e3916b3e102e8682d768353cf44a5aed3c8287244ac3ec92`;
NAS100/US30/US500 retain
`MT5_BROKER_FAMILY_INDEX_CFD_AUTHORITY_V1:2c5dc7e112b1a3ca761efb2bcb467a862e477fe74a3d9b69601c588b72b0da09`.
The Mac validator still accepts already-issued legacy non-index requests.
Do not disable Windows `legacy_non_index_accepted` until the old pending queue
has cleared and fresh remote receipts under both current references pass.

---

## 10. Migration and rollout

### Phase A - unify read-only truth

* implement the v2 routing and provider-catalogue snapshots;
* reconcile manifest policy, D1 overrides, representation facts, live MT5
  catalogues, failover grants, and last-used provenance;
* surface disagreements as findings rather than choosing silently;
* repair the Fusion authority scope; and
* verify the baseline routing table against live Scheduler behaviour.

### Phase B - native read-only workspace and links

* add Routing & Providers under Manage Data;
* implement the all-timeframe matrix and provider catalogue;
* link Overview, Estate Truth, Scheduler, History, and Audit;
* rework Indices presentation without merging canonical identities; and
* replace ambiguous bridge and queue metrics.

### Phase C - controlled editing

* migrate current operator D1 overrides into revision 1;
* add draft, validate, preview, activate, restore-estate-default, and
  restore-prior-revision workflows;
* pin pending work to its routing revision; and
* publish activation audit receipts.

### Phase D - bounded recovery

* enforce the 3-attempt per-boundary budget;
* implement executable ordered fallbacks from the same routing snapshot;
* add Attempt now, Try next fallback, and managed bridge restart controls; and
* publish attempt and repair evidence in Scheduler and Audit.

### Phase E - acceptance and release

* replay recorded lane decisions offline against the proposed routing policy;
  do not run an unreliable old Fragarach app in parallel as an acceptance gate;
* require zero unexplained lane decisions before enabling the replacement;
* package the native app and services from an identified release;
* retain a one-click restore to the previous routing revision; and
* monitor fourteen continuous days of replacement operation for current-bar
  freshness, unbounded retries, silent source changes, duplicate admissions,
  and stale catalogue presentation.

---

## 11. Acceptance gates

The update is accepted only when automated and live evidence proves:

1. all 191 recorded lanes appear once in the routing matrix, including the
   187 active routes, four non-editable inactive lanes, and explicit derived
   and no-route states;
2. every Scheduler route decision cites the same active routing revision shown
   by the app;
3. current MT5 primary lanes retain exact broker symbols and node identity;
4. NAS100, US30, and US500 fail closed when Fusion is unavailable unless a new
   equivalent representation is separately reviewed;
5. crypto fallbacks shown in the UI exactly match executable runtime
   fallbacks and, when no lane override exists, follow MT5, then the reviewed
   Binance/CoinGecko candidates, then Yahoo, then Twelve Data; the
   manifest/runtime disagreement no longer exists;
6. USD/USDT, ETF/CFD, cash-index/CFD, and share/share-CFD substitutions cannot
   activate without explicit reviewed authority;
7. a user can draft, validate, preview, activate, and restore a route without
   editing source files or instructing Codex;
8. activation creates a new immutable revision and cannot alter prior bars or
   provenance;
9. in-flight work either completes under its pinned revision or is explicitly
   cancelled and re-planned with a receipt;
10. one expected boundary cannot generate an automatic attempt 4;
11. capacity waits and scheduler evaluations do not consume the 3-attempt
    provider-dispatch budget;
12. Overview, Estate Truth, Scheduler, History, and Audit links open the exact
    affected symbol/timeframe route;
13. a Fetch/Run Queue/Attempt action displays accepted, active, completed, or
    failed state with an operation ID;
14. audit detail proves whether repair was attempted and whether verification
    succeeded;
15. bridge status reports authorised routes rather than a misleading zero
    active-lane count;
16. a degraded bridge can receive a managed restart request and report its
    final watchdog outcome without enabling trading or bypassing validation;
17. provider catalogue data carries live source times and visibly becomes
    stale when its freshness budget is exceeded;
18. crypto provider cards list only current-estate symbols and state that
    additional symbols may be available through Discover;
19. Indices presentation combines the family visually while preserving each
    product's canonical identity and route;
20. the correctly scoped Fusion receipt authority set admits the approved
    index and non-index requests and rejects out-of-scope requests;
21. a non-overridden D1 equity/ETF lane with no executable MT5 candidate
    chooses reviewed Yahoo before reviewed Twelve Data;
22. a lane can disable MT5 while retaining an approved Twelve Data candidate,
    and the override affects only that exact symbol/timeframe lane;
23. a lane can reorder reviewed candidates across the estate-default tiers,
    and every affected surface shows the effective order, disabled providers,
    operator reason, and routing revision;
24. **Restore estate defaults** removes the exact-lane override, previews the
    inherited order using current capability facts, and activates it through a
    new audited routing revision; and
25. disabling every provider in a lane produces an explicit fail-closed lane
    with an attention state and never causes an implicit provider selection.

---

## 12. Non-goals

This update does not:

* add new market symbols merely because a provider lists them;
* enumerate entire crypto exchange, aggregator, pool, or MT5 catalogues;
* enable order placement or any trading control;
* blend providers to manufacture one bar;
* rewrite or reconcile historical bars automatically after a route change;
* treat similarly named products as economically identical;
* make Codex part of the normal routing-change workflow; or
* replace immutable provenance with the current route configuration.
