# SPEC-012R Preflight Report

Date: 2026-07-12
Repository: `/Users/raymorgan/VSC/Fragarach_2`
Schema migration authorised: no

## Findings

- SPEC-012 used a deterministic but narrow catalogue and a permanent master/detail layout.
- `XAGUSD` and Alphabet were absent; prefix-based unknown suggestions could be unrelated.
- representations were static and the Discover screen had no mutation path.
- the existing `register_instrument` command is transactionally safe, append-aware, read-back verified, and prevents canonical/provider collisions.
- the existing registration contract requires provider identity fields for every registration. This is compatible with catalogue-backed XAGUSD, GOOG, GOOGL, FX and other known mappings, but not with provider-unmapped representations such as US30.

## Protected Boundaries

No Constitution, doctrine, Truth contract, immutable ledger guarantee, schema, or migration was changed.

## Planned Gates

- deterministic market-aware catalogue and ranking
- interactive representation selection
- reviewed registration plan
- existing immutable registration command
- duplicate prevention and acquisition handoff
- responsive full-width single-result/unknown layouts
- Python regression suite, Swift build/checks, signed launch, operator screenshots
