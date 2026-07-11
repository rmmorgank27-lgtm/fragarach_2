# SPEC-007A Market Authority Implementation Foundation — Compatibility Blocker

**Date:** 2026-07-11

**Status:** Compatibility stop required by specification

**Authority:** Candidate Authority

## Decision

Implementation stopped before code or authority assets were created. SPEC-007A explicitly requires an immediate stop when a Market Authority document is incomplete, an operational value is missing, authority relationships are ambiguous, classification precedence is undefined, or trading-day ownership cannot be determined.

The three supplied initial Market Authority documents do not pass that gate.

## Source-document audit

### FX Market Authority V1 — incomplete

The document marks weekly open `Sunday 22:00 UTC` and weekly close `Friday 22:00 UTC` as subject to operator approval before V1 acceptance. It does not provide:

- an accepted market timezone and DST authority;
- DST transition rules and effective dates;
- a daily trading-day boundary sufficient for deterministic ownership;
- a maintenance rule or an explicit declaration of none;
- holiday and exceptional-closure rules with effective ranges;
- interval-open or interval-close alignment;
- classification precedence;
- concrete `effective_from` and `effective_to` values.

It therefore cannot generate an immutable Trading Session Authority or Trading Day Convention.

### Crypto Market Authority V1 — incomplete

The document explicitly supplies continuous UTC trading, UTC-day ownership, no DST, no maintenance, and no holidays. It still does not provide:

- a concrete `effective_from` value;
- a concrete `effective_to` value or explicit open-ended value;
- whether interval timestamps represent interval opens or interval closes.

The value `Explicit` under Interval Alignment describes a requirement, not an operational alignment value. The document also does not distinguish continuous market classification from future resolution-specific interval-grid membership.

### Metals Market Authority V1 — incomplete

The document delegates Trading Day Convention, Market Clock, Maintenance, and Holiday Authority to an unspecified “approved authority” and says everything else follows the incomplete FX document. It does not identify a market venue or supply the operational rules needed for classification or ownership.

## Cross-authority blockers

The supplied documents also do not define:

- the exact Market Authority → Trading Session Authority → Trading Day Convention reference graph;
- immutable identifiers for the generated session and convention assets;
- total classification precedence where categories overlap;
- checksum-closure and provenance rules for generated assets;
- effective-range overlap and selection rules;
- accepted timestamp fixtures proving classification and trading-day ownership.

## Required inputs to resume

1. Replace the FX document’s provisional and placeholder clauses with approved operational values, precedence, and effective range.
2. Add Crypto’s effective range and choose `INTERVAL_OPEN` or `INTERVAL_CLOSE`.
3. Replace all Metals delegations with a selected market scope and complete approved operational values.
4. Approve the cross-authority identifiers, relationship graph, classification precedence, checksum closure, and effective-version selection rules.
5. Supply accepted boundary fixtures for runtime proof.

## Preservation proof

- No Market Authority, Trading Session Authority, or Trading Day Convention code or asset was created.
- Existing evidence, registrations, provider contracts, validation contracts, provenance, migrations, and application behavior remain unchanged.
- The pre-existing untracked `data/` directory remains untouched.
- No secret was accessed.
- No remote push was performed.

Fragarach II remains **CANDIDATE AUTHORITY**. **Operations is King.**
