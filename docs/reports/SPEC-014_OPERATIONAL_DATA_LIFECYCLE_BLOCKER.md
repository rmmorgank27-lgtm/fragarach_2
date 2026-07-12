# SPEC-014 Operational Data Lifecycle Classification (Superseded)

Status: superseded by `ZERO_BLOCKING_BASE_DOCTRINE_V1`. The earlier general blocker classification was incorrect.

The immutable `instrument_registrations` table has `CHECK (timeframe='D1')`; registration validation rejects every other timeframe. The acquisition command accepts one explicit bounded range and executes one provider request. The checksummed provider contract defines request ceilings, but it contains no earliest-history boundary, pagination/cursor method, controlled terminal proof, completed-bar resolver, correction overlap, or resume state.

Ratified H1/M30/M5 authority exists. The D1-only schema and services are implementation incompatibilities, not missing authority. Maximum Available and automatic Update remain unavailable because their claims cannot yet be proven, while bounded Custom Range D1 fetch, Import File, registration, retirement, Truth, and audit remain safe and operational.

Minimum authority change required: a reviewed, checksummed per-timeframe provider operation contract defining supported timeframes, completed-bar calculation, correction overlap, chunk/pagination behavior, earliest-boundary semantics, terminal reasons, and replayable resume/idempotence state. Supporting non-D1 registrations also requires an authorised schema/registration-contract revision, which SPEC-014 explicitly forbids.

The native UI now presents the unavailable capability, smallest affected scope, implementation reason, and primary safe continuations. It makes no maximum-history or overlap claim.
