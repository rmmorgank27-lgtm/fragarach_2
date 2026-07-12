# SPEC-012 Implementation Report

**Specification:** `SPEC-012_MARKET_DISCOVERY_AND_INSTRUMENT_ONBOARDING`

**Date:** `2026-07-12`

**Result:** `IMPLEMENTED`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Market Discovery Service

`fragarach_ii.market_discovery` produces deterministic `fragarach_ii.market_discovery.v1` results containing underlying market, canonical identity, confidence, market type, asset class, description, aliases, tradable representations, provider discovery, recommendation, metadata, existing registration context, acquisition readiness, and explanation.

The initial operational catalogue covers:

- Dow Jones via DJI, US30, DIA, ^DJI, and YM;
- S&P 500 via SPX, US500/SPX500, SPY, ^GSPC, and ES;
- Gold via XAUUSD/XAU/USD, CFD, GLD, and GC;
- WTI via USOIL, USO, and CL;
- arbitrary supported ISO currency pairs;
- Apple/AAPL, Tesla/TSLA, and ambiguous BHP Australian/US listings.

Exact representation input controls the recommendation. Market-name input selects the canonical default representation. Alternatives remain visible and operator-controlled.

Provider mappings are read-only catalogue facts. Twelve Data mappings expose known symbol and D1 support; unresolved forms remain explicit. Entitlement is never inferred. Existing registrations are matched against canonical/provider symbols and enriched through the existing Truth Engine without mutation.

## Native Workflow

OperationsCore adds MarketDiscovery DTOs and a secret-free `discoverMarket` bridge intent. Resolve Instrument is removed from the sidebar and replaced by Discover Market.

The guided page displays:

1. Market Identity
2. Tradable Representations
3. Provider Discovery
4. Registration Recommendation
5. Preliminary Metadata and Readiness
6. Existing Authority with Open Existing when applicable

No registration or acquisition buttons are introduced. The lifecycle footer makes future steps visible without implementing them.

The macOS SwiftUI patterns skill influenced the replacement through explicit market selection, a native list/detail split, focused numbered stages, and direct navigation to existing Truth authority.

## Non-Changes

No schema, migration, persistence, constitutional, authority, Truth calculation, registration mutation, acquisition, validation, maintenance, forecasting, or consumer-specific behavior changed.

**Operations is King.**
