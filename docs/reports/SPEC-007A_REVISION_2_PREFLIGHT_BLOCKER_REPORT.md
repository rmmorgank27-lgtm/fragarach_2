# SPEC-007A Market Authority and Trading Session Foundation — Revision 2 Preflight

**Date:** 2026-07-11

**Status:** Blocked before implementation

**Authority:** Candidate Authority

## Outcome

Revision 2 defines a sound separation of Evidence Time, Market Authority, Trading Session Authority, Trading Day Convention, and Display Time. It also defines the fields a future framework must represent. It does not provide the operational values required to populate the mandated immutable, checksummed authority assets or prove meaningful deterministic classification and trading-day assignment.

Implementing populated assets would still require Codex to choose market facts. Implementing only a type/schema framework with empty or illustrative assets would not satisfy the acceptance tests for deterministic timestamp classification and trading-day assignment. No authority implementation was started.

## Unresolved blockers

### Required asset set is undefined

`FX_MARKET_V1`, `CRYPTO_MARKET_V1`, `US_EQUITY_MARKET_V1`, and `METALS_MARKET_V1` are explicitly described as examples. The specification does not state which market, session, and trading-day assets must exist at acceptance. Consequently the required closure of checksummed assets is not defined.

### Operational rule values remain absent

No exact values are supplied for:

- FX weekly open and close;
- FX maintenance windows;
- FX session timezone and named DST authority;
- FX trading-day and interval-alignment boundaries;
- metals market/venue scope or any metals session rule;
- exchange scope, regular hours, extended-hours doctrine, holidays, early closes, or exceptional closures;
- effective-from and effective-to dates.

The specification requires every operational rule to be explicit and says no field may be implied. Therefore implementation cannot source these values from convention.

### Classification precedence is still absent

The specification says precedence shall be explicit but does not state it. `HOLIDAY`, `MARKET_CLOSED`, `OUTSIDE_SESSION`, `MAINTENANCE`, and `EARLY_CLOSE` can overlap. The exact meaning of the latter two closure classifications also remains undefined. Any precedence chosen in code would become invented authority.

### Authority relationships are not operationally defined

The three asset families must work together, but the specification does not define their reference graph or identity rules:

- whether a market asset references session and trading-day assets, or vice versa;
- whether one market may expose multiple sessions;
- how a session references its holiday and exceptional-closure authority;
- how existing calendar IDs map to these new assets;
- how referential closure is checksummed and verified;
- whether orphan or overlapping effective ranges are prohibited.

Registration references are deferred to a future specification, so there is currently no authoritative route from an accepted instrument/calendar to a new session asset. Runtime classification could only be invoked by directly naming an asset, which does not prove integration with existing authority.

### Holiday and DST “support” is ambiguous

Acceptance requires explicit DST and holiday authority support. This could mean merely representing opaque identifiers, implementing deterministic transition/holiday rules, or loading complete versioned date closures. Those approaches have materially different authority and historical-correctness properties. The required behavior and effective range must be selected explicitly.

### Runtime proof has no accepted fixtures

No authoritative timestamp/classification/trading-day examples are supplied. Without fixtures at regular boundaries, maintenance periods, DST transitions, holidays, early closes, and exceptional closures, tests would only prove that implementation agrees with values it invented itself.

## Minimum decisions required to resume

1. Enumerate the exact V1 market, session, and trading-day assets required for acceptance.
2. Supply every operational field value and effective range for each required asset.
3. State total classification precedence and precise category semantics.
4. Define the reference graph, referential-integrity rules, checksum closure, and effective-range constraints among assets.
5. Define how DST and holiday authorities are represented and resolved without network access or inference.
6. Supply accepted boundary fixtures with expected classification and trading-day ownership.

## Preservation proof

- Existing evidence, registrations, provider contracts, validation contracts, provenance, migrations, and application code were not changed.
- Existing D1 authority behavior was not executed or modified.
- The pre-existing untracked `data/` directory remains untouched.
- No secrets were accessed.
- No remote push was performed.

Fragarach II remains **CANDIDATE AUTHORITY**. **Operations is King.**
