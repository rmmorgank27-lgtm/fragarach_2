# SPEC-007A Market Session Authority Foundation — Preflight Blocker Report

**Date:** 2026-07-11

**Status:** Blocked before implementation

**Authority:** Candidate Authority

## Outcome

SPEC-007A establishes the correct conceptual separation between immutable UTC storage time, authoritative market-session time, and non-authoritative display time. It does not, however, provide the material market-session facts required to create deterministic, checksummed authority definitions. Implementing the requested assets would require choosing or inventing facts that the specification explicitly prohibits inferring.

No authority code, evidence, registrations, provider contracts, validation behavior, or application code was changed during this preflight.

## Missing authority facts

### FX session

The specification names a New York close convention and states that the market clock is UTC+2 in Northern Hemisphere winter and UTC+3 in summer, but does not define:

- the exact regular weekly open timestamp;
- the exact regular weekly close timestamp;
- the exact daily trading-day boundary;
- the exact daily maintenance window, if any;
- which jurisdiction or IANA timezone determines “Northern Hemisphere” DST;
- the transition instants and treatment of the weeks when US and European DST schedules differ;
- whether the UTC+2/+3 market clock is itself the authority or a consequence of a named timezone rule;
- interval alignment at session boundaries.

“Recognised market convention” cannot supply these values because the governing principle says every rule must be explicit and nothing may be inferred.

### Metals session

`METALS_SESSION_V1` is listed as an example, but no venue or instrument scope is selected and no regular hours, maintenance window, timezone, DST rule, early closes, or interval alignment is supplied. Spot OTC metals and exchange-traded metals do not necessarily share one session authority.

### Exchange session

The acceptance criteria require exchange markets to define regular sessions, while `US_EQUITY_SESSION_V1` is only an example. The specification does not identify:

- the authoritative exchange or consolidated-market scope;
- the IANA exchange timezone;
- regular-session open and close times;
- the authoritative holiday source and effective date range;
- observed-holiday rules;
- early-close dates and close times;
- exceptional closures;
- whether pre-market and after-hours evidence is expected or outside session.

These choices materially change timestamp classification and cannot be selected by implementation convention.

### Classification precedence

Every timestamp must receive exactly one classification, but several categories can overlap. For example, a timestamp may be both on a holiday and outside regular session, or after an early close and normally inside the regular session. The specification does not define precedence among:

`EXPECTED`, `MARKET_CLOSED`, `MAINTENANCE`, `HOLIDAY`, `EARLY_CLOSE`, and `OUTSIDE_SESSION`.

The meaning of `EARLY_CLOSE` is also ambiguous: it could classify the shortened expected session, the normally expected period removed by the early close, or only the boundary instant.

### Assignment authority

The specification says registrations do not change and market sessions extend calendars without duplicating authority, but does not define the authoritative mapping from an existing calendar or registered instrument to a market-session definition. A filename convention or asset-class inference would create an unversioned second authority.

### Effective range and revision policy

Checksummed definitions need an explicit effective-from date, optional effective-to date, and revision policy. Historical DST laws, exchange hours, holidays, and exceptional closures change. An unbounded V1 definition would incorrectly project current rules into periods where they may not have applied.

## Decisions required to resume SPEC-007A

1. Supply the exact FX weekly/daily session rules, maintenance interval, interval alignment, and named DST authority—including mismatched US/European transition weeks.
2. Select the metals market/venue and supply its complete session facts and effective range.
3. Select the exchange-market scope and supply its regular hours, timezone, holidays, early closes, exceptional closures, extended-hours doctrine, and effective range.
4. Define total classification precedence and the precise meaning of `EARLY_CLOSE` and `MARKET_CLOSED`.
5. Define a versioned, checksummed assignment from existing calendar IDs or canonical instruments to session-authority IDs without changing registration identity.
6. Define how authority revisions and historical effective ranges are represented.

## Preservation proof

- Existing D1 evidence and hashes were not touched.
- Existing registrations and identity checksums were not touched.
- Existing provider contracts and checksums were not touched.
- Existing validation behavior and reports were not touched.
- The pre-existing untracked `data/` directory remains untouched.
- No credential or secret was accessed.
- No remote push was performed.

Fragarach II remains **CANDIDATE AUTHORITY**. **Operations is King.**
