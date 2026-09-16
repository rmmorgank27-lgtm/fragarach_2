"""Reviewed TradingView bootstrap for canonical oil CFD D1 lanes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .ingestion.manual import ingest_manual_file
from .lane_commissioning import ensure_manual_acquisition_lane
from .storage import RegistrationCandidate, register_instrument


OIL_IDENTITIES = {
    "USOIL": ("US Oil CFD", "COMMODITY:WTI", "TVC_USOIL"),
    "UKOIL": ("UK Oil CFD", "COMMODITY:BRENT", "TVC_UKOIL"),
}


def oil_candidate(symbol: str) -> RegistrationCandidate:
    canonical = symbol.strip().upper()
    try:
        display_name, underlying, _ = OIL_IDENTITIES[canonical]
    except KeyError as error:
        raise ValueError(f"unsupported canonical oil symbol: {canonical}") from error
    return RegistrationCandidate(
        asset=canonical,
        timeframe="D1",
        instrument_family=canonical,
        local_symbol=canonical,
        display_name=display_name,
        instrument_type="CFD",
        asset_class="ENERGY",
        representation_type="CFD",
        trading_currency="USD",
        exchange_name="OTC",
        provider_id=None,
        provider_contract=None,
        provider_symbol=None,
        provider_instrument_type=None,
        calendar_id="REGISTRY_D1_V1",
        calendar_version=1,
        gap_doctrine_id="FRAGARACH_II_D1_GAP_DOCTRINE_V1",
        gap_doctrine_version=1,
        underlying_reference=underlying,
    )


def bootstrap_tradingview_oil_history(
    database_path: str | Path,
    *,
    usoil_file: str | Path,
    ukoil_file: str | Path,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Correct both canonical D1 lanes from reviewed immutable TVC exports.

    Registration remains provider-unmapped and the lanes are explicitly marked
    not commissioned. This prevents HTTP fallbacks from overwriting the TVC
    bootstrap while Global Prime MT5 D1 deliveries await seam admission.
    """

    observed = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC)
    files = {"USOIL": Path(usoil_file), "UKOIL": Path(ukoil_file)}
    results: dict[str, object] = {}
    for symbol, source in files.items():
        expected_prefix = OIL_IDENTITIES[symbol][2]
        if not source.name.upper().startswith(expected_prefix):
            raise ValueError(
                f"{symbol} source filename must start with {expected_prefix}: {source.name}"
            )
        registration = register_instrument(
            database_path,
            oil_candidate(symbol),
            registered_at_utc=observed.isoformat(),
        )
        ensure_manual_acquisition_lane(
            database_path, symbol, "D1", observed_at=observed.isoformat()
        )
        result = ingest_manual_file(
            database_path,
            source,
            symbol=symbol,
            timeframe="D1",
            provider="TRADINGVIEW_TVC",
            merge_mode="correct",
            d1_date_format="DAY_FIRST",
            clock=lambda: observed,
        )
        if result.transaction_state not in {"committed", "COMPLETED_WITH_WARNINGS"}:
            raise RuntimeError(f"{symbol} bootstrap did not commit: {result.transaction_state}")
        results[symbol] = {
            "registration": registration.outcome,
            "raw_block_id": result.raw_block_id,
            "source_rows": result.source_rows,
            "accepted": result.accepted,
            "inserted": result.inserted,
            "corrected": result.corrected,
            "unchanged": result.unchanged,
            "rejected": result.rejected,
            "canonical_count": result.canonical_count,
            "transaction_state": result.transaction_state,
        }
    return {
        "contract": "fragarach_ii.tradingview_oil_bootstrap.v1",
        "provider": "TRADINGVIEW_TVC",
        "merge_mode": "correct",
        "scheduler_commissioning": "NOT_COMMISSIONED",
        "results": results,
    }


__all__ = ["bootstrap_tradingview_oil_history", "oil_candidate"]
