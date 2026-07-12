"""Central Zero Blocking operational outcome classification contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class OperationalStatus(StrEnum):
    SUCCESS = "SUCCESS"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    DEGRADED_OPERATION_AVAILABLE = "DEGRADED_OPERATION_AVAILABLE"
    HARD_BLOCK_AFFECTED_PATH = "HARD_BLOCK_AFFECTED_PATH"
    OPERATOR_CANCELLED = "OPERATOR_CANCELLED"


@dataclass(frozen=True)
class OperationalDecision:
    status: OperationalStatus
    hard_block: bool
    affected_scope: str
    reason: str
    warnings: tuple[str, ...] = ()
    safe_fallbacks: tuple[str, ...] = ()
    fallback_executed: str | None = None
    unaffected_operations: tuple[str, ...] = ()
    repair_owner: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def degraded(
    scope: str,
    reason: str,
    *,
    safe_fallbacks: tuple[str, ...],
    unaffected_operations: tuple[str, ...] = (),
    repair_owner: str = "IMPLEMENTATION",
) -> OperationalDecision:
    if not safe_fallbacks:
        raise ValueError("a degraded decision requires a safe fallback")
    return OperationalDecision(
        OperationalStatus.DEGRADED_OPERATION_AVAILABLE,
        False,
        scope,
        reason,
        (reason,),
        safe_fallbacks,
        None,
        unaffected_operations,
        repair_owner,
    )


def hard_block(
    scope: str,
    reason: str,
    *,
    unaffected_operations: tuple[str, ...] = (),
    repair_owner: str | None = None,
) -> OperationalDecision:
    return OperationalDecision(
        OperationalStatus.HARD_BLOCK_AFFECTED_PATH,
        True,
        scope,
        reason,
        (),
        (),
        None,
        unaffected_operations,
        repair_owner,
    )


def aggregate(decisions: tuple[OperationalDecision, ...]) -> OperationalDecision:
    completed = tuple(d for d in decisions if d.status is OperationalStatus.SUCCESS)
    warnings = tuple(w for d in decisions for w in d.warnings)
    fallbacks = tuple(dict.fromkeys(f for d in decisions for f in d.safe_fallbacks))
    unaffected = tuple(dict.fromkeys(o for d in decisions for o in d.unaffected_operations))
    if completed and len(completed) != len(decisions):
        return OperationalDecision(
            OperationalStatus.COMPLETED_WITH_WARNINGS,
            False,
            "REQUESTED_PLAN",
            "Safe completed work was preserved; one or more paths were limited.",
            warnings,
            fallbacks,
            None,
            unaffected,
            "IMPLEMENTATION",
        )
    if decisions and all(d.hard_block for d in decisions):
        return decisions[0]
    return OperationalDecision(
        OperationalStatus.SUCCESS,
        False,
        "REQUESTED_PLAN",
        "Requested operation completed.",
        warnings,
        fallbacks,
        None,
        unaffected,
        None,
    )
