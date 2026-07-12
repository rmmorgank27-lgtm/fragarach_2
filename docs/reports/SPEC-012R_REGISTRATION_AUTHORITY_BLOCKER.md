# SPEC-012R Registration Authority Blocker

Date: 2026-07-12

## Exact Incompatibility

`RegistrationCandidate` and `_validate` in `src/fragarach_ii/storage/registrations.py` require non-empty:

- `provider_id`
- `provider_contract`
- `provider_symbol`
- `provider_instrument_type`

`canonical_registration` also makes those values part of the immutable provider identity key. The current schema therefore cannot persist a Fragarach-owned instrument identity independently of a provider mapping.

For US30, the deterministic catalogue knows the representation identity but has no authoritative provider mapping. Supplying a plausible provider or symbol would fabricate provider authority and violate SPEC-012R sections 3 and 15. Supplying placeholder provider values would permanently ledger-bind non-provider data as provider identity and risk collisions.

## Scope of Block

- Identity discovery, representation review, warnings, and readiness remain available.
- Registration is available for catalogue-backed known mappings such as XAGUSD, GOOG, GOOGL, supported FX, and supported crypto pairs.
- Registration is intentionally unavailable for US30 and other provider-unmapped representations.

## Required Authority Decision

Authorise a future schema/contract revision that permits provider mapping to be absent or represented in a separate mapping authority. SPEC-012R explicitly forbids that migration, so this implementation does not alter the contract.

## Checkpoint

The required final local checkpoint was not created because the specification permits it only after all acceptance gates pass. No push was performed.
