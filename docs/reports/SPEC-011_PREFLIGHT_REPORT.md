# SPEC-011 Preflight Report

**Specification:** `SPEC-011_INSTRUMENT_IDENTITY_RESOLUTION_ENGINE`

**Date:** `2026-07-12`

**Result:** `PASS — IMPLEMENTATION AUTHORISED`

**Authority State:** `CANDIDATE AUTHORITY`

**Push:** `FORBIDDEN`

## Decision

Instrument identity can be resolved before provider discovery through a deterministic read-only engine combining existing immutable registrations, registered aliases, a non-persistent canonical market catalogue, and ISO currency-pair conventions.

No schema, migration, constitutional change, provider request, credential, registration, acquisition, validation, or authority mutation is required.

## Boundaries

- Existing registration identity has first priority and may include current TruthState when canonical bars exist.
- ISO base/quote recognition resolves supported six-letter currency pairs without a catalogue entry.
- Canonical symbols, names, and established aliases are ranked deterministically.
- Multiple equally strong identities remain separate operator-selectable matches.
- Unknown input returns guidance rather than provider discovery or invented authority.
- Preliminary timezone/session values are returned only where catalogue knowledge exists; otherwise they remain null/unknown.
- Registration state is distinct from identity status. `REGISTERED` does not weaken the required KNOWN/LIKELY/AMBIGUOUS/UNKNOWN identity contract.

## Native Boundary

The existing provider-backed Add Instrument UI may be replaced by a Resolve Instrument review surface. The surface may invoke only the identity command and may not expose registration, acquisition, or validation actions.

**Operations is King.**
