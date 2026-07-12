# SPEC-012 Preflight Report

**Specification:** `SPEC-012_MARKET_DISCOVERY_AND_INSTRUMENT_ONBOARDING`

**Date:** `2026-07-12`

**Result:** `PASS — REPLACEMENT AUTHORISED`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Course Correction

The standalone SPEC-011 Resolve Instrument screen is too narrow for operator onboarding. Its provider-free identity resolver remains valid as an internal capability, but the operator-facing workflow must be replaced by market intent discovery.

SPEC-012 can be implemented with a non-persistent canonical market/representation catalogue, informational provider-mapping knowledge, existing read-only registration authority, and existing TruthState context. No schema, migration, persistence, constitutional, authority, registration, acquisition, or validation change is required.

## Boundaries

- Discovery starts from the underlying market and preserves ambiguous markets for operator selection.
- Exact representation input selects the recommendation: CFD, ETF, futures, index, spot, FX, or company equity.
- Provider discovery is informational. Known mappings expose D1 support; unresolved mappings remain `DISCOVERY_REQUIRED`; entitlement remains `NOT_MEASURED`.
- Recommendations never register or mutate authority.
- Existing registrations expose version, authority state, Truth Score, and CAODT, and direct the UI to Open Existing.
- Unknown is returned only after canonical names, aliases, abbreviations, representation symbols, and ISO currency conventions are exhausted.

## Native Replacement

The Resolve Instrument destination and view may be removed and replaced with Discover Market. The new page must remain selection-driven and informational, showing lifecycle stages without implementing future mutation actions.

**Operations is King.**
