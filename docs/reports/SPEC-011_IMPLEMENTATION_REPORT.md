# SPEC-011 Implementation Report

**Specification:** `SPEC-011_INSTRUMENT_IDENTITY_RESOLUTION_ENGINE`

**Date:** `2026-07-12`

**Result:** `IMPLEMENTED`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Resolver

`fragarach_ii.identity_resolver` produces deterministic `fragarach_ii.instrument_identity_resolution.v1` responses. It resolves:

- exact existing registration identities and aliases;
- arbitrary supported ISO currency pairs such as AUDJPY and AUD/JPY;
- established commodity, crypto, index, company, ticker, and alias knowledge;
- partial established names as lower-confidence LIKELY results;
- multiple identities such as ASX:BHP and NYSE:BHP without automatic selection;
- unknown input with suggested searches, aliases, and a provider-discovery next-step message.

Each match exposes canonical name/symbol, type, market, asset class, 0–100 identity confidence, aliases, exchange, currency/base/quote, timezone, sessions, reason, identity status, registration state, and optional current authority/Truth/CAODT.

Confidence rules are explicit and deterministic: exact canonical symbol 100, exact alias 98, exact canonical name 96, recognized ISO pair 99, and partial established name/alias 82. Confidence never represents provider confidence.

The JSON command has no credential or network path. Database access uses the existing read-only boundary.

## Native Integration

OperationsCore now decodes identity results and exposes a provider-free `resolveInstrument` bridge intent. The sidebar destination is renamed Resolve Instrument. The previous provider-search/register/acquire screen is replaced by an informational, selection-driven review surface showing confidence, ambiguity, aliases, preliminary metadata, registration/truth context, unknown guidance, and the next lifecycle stage.

No onboarding mutation action remains on this screen.

The macOS SwiftUI patterns skill influenced the result by using explicit match selection, a lightweight native list with detail pane, focused metadata groups, and no modal or provider-driven workflow.

## Exclusions Preserved

Provider discovery, registration, acquisition, validation, Truth calculation, console changes, maintenance, forecasting, consumer behavior, schema, and migrations remain outside SPEC-011.

**Operations is King.**
