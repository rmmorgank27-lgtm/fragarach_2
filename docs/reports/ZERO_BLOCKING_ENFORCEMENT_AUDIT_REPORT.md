# Zero Blocking Enforcement Audit

## Enforcement contract

Python backend and native OperationsCore now expose the same `OperationalDecision` fields and controlled statuses. Degraded results require a non-empty safe fallback. Partial plans retain completed work and resolve to `COMPLETED_WITH_WARNINGS`.

## Production-path reconciliation

| Path | Classification | Scope and continuation |
|---|---|---|
| Registration D1-only implementation | IMPLEMENTATION_INCOMPATIBILITY | Intraday lanes stay visible; existing D1, discovery, import, retirement, and Truth continue. Ratified intraday authority is acknowledged. |
| Discover Market direct mapping missing | DEGRADED_CAPABILITY, or HARD_SAFETY_BLOCK for the exact provider call | Canonical identity remains visible; unrelated registrations and operations continue. Exact acquisition waits for mapping. |
| Data Operations maximum proof missing | DEGRADED_CAPABILITY | Maximum claim unavailable; Custom Range and Import File are primary continuations. |
| Data Operations automatic overlap missing | IMPLEMENTATION_INCOMPATIBILITY | Automatic update unavailable; Custom Range and Import File continue. |
| Provider authentication/rejection | HARD_SAFETY_BLOCK | Exact provider call only; Import File, retirement, Truth, and audit continue. |
| Manual import invalid identity/timestamps/checksum | HARD_SAFETY_BLOCK | Exact file/lane only; another file or provider fetch remains available. |
| Retired or quarantined authority | HARD_SAFETY_BLOCK | Exact retired instrument/lane cannot acquire, import, or actively serve; audit remains available and unrelated instruments continue. |
| Validation unsupported implementation | IMPLEMENTATION_INCOMPATIBILITY | Exact validator feature unavailable; accepted immutable evidence and existing Truth remain visible with limitations. |
| AMBER Truth, stale data, or gaps | WARNING | Truth remains readable and data operations remain available. |
| Explicit cancellation | HARD_SAFETY_BLOCK / OPERATOR_CANCELLED | Active operation stops at its safe boundary; committed immutable work remains. |

## Remaining hard blocks

Remaining hard blocks are limited to unresolved/contradictory identity for an exact mutation, provider orientation mismatch for the exact acquisition, retired/quarantined scope, checksum or raw corruption, invalid mandatory evidence interpretation, writer/transaction safety, authentication/provider rejection, and explicit cancellation. Each matches Section 6 of the doctrine, is scoped to the smallest affected unit, and has no safe truthful way to perform that exact action. Unrelated workflows remain available.

Legacy backend error codes such as `UNSUPPORTED_TIMEFRAME` remain technical codes at narrow service boundaries. Native and discovery presentation no longer interpret the D1-only implementation as absent higher authority or as a general stop.
