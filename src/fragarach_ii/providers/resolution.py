"""Compatibility facade for the unified Scheduler acquisition authority.

Production callers should use :func:`scheduler_service.run_operator_fetch`.
This name remains importable for integrations written before SPEC-047, but it
contains no provider selection, fallback, mapping, or publication logic.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fragarach_ii.scheduler_service import run_operator_fetch


def acquire_resolved(
    database_path: str | Path,
    *,
    asset: str,
    timeframe: str = "D1",
    from_date: str,
    through_date: str,
    merge_mode: str,
    credential: str | None,
    intent: str = "custom",
    progress=None,
    acquirer: Callable[..., dict[str, object]] | None = None,
    provider_profiles=None,
    journal_path: str | Path | None = None,
    twelve_transport=None,
    yahoo_fetch=None,
) -> dict[str, object]:
    """Submit legacy requests to the same serialized OPERATOR_FETCH executor."""

    if twelve_transport is not None or yahoo_fetch is not None:
        raise ValueError(
            "LEGACY_PROVIDER_INJECTION_REMOVED: pass one unified acquirer and reviewed provider profiles"
        )
    kwargs: dict[str, object] = {}
    if acquirer is not None:
        kwargs["acquirer"] = acquirer
    if provider_profiles is not None:
        kwargs["provider_profiles"] = provider_profiles
    return run_operator_fetch(
        database_path,
        symbol=asset,
        timeframe=timeframe,
        credential=credential,
        requested_mode=intent,
        requested_start=from_date,
        requested_end=through_date,
        reviewed_historical_range=intent in {"initial", "custom"},
        operator_reason="LEGACY_CALLER_UNIFIED_BY_SPEC_047",
        merge_mode=merge_mode,
        journal_path=journal_path,
        progress=progress,
        **kwargs,
    )
