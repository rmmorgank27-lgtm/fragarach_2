"""Explicit provider dispatch for scheduler-selected approved mappings."""

from __future__ import annotations

from pathlib import Path

from .binance import acquire_binance
from .coingecko import acquire_coingecko
from .twelve_data import acquire_twelve_data
from .yahoo_finance import acquire_yahoo


def acquire_from_provider(
    database_path: str | Path,
    *, provider: str, provider_symbol: str, asset_class: str,
    asset: str, timeframe: str, from_date: str, through_date: str,
    merge_mode: str, credential: str | None, mapping_class: str | None = None,
    provider_api_base_url: str | None = None,
    progress=None, credit_authority_managed: bool = False, **_: object,
) -> dict[str, object]:
    if provider == "TWELVE_DATA":
        if progress:
            progress("requesting")
        return acquire_twelve_data(
            database_path, asset=asset, timeframe=timeframe, from_date=from_date,
            through_date=through_date, merge_mode=merge_mode, credential=credential,
            provider_symbol_override=provider_symbol, mapping_class=mapping_class,
            progress=progress,
            credit_authority_managed=credit_authority_managed,
        ).as_dict()
    if provider == "YAHOO_FINANCE":
        if progress:
            progress("requesting")
        result = acquire_yahoo(
            database_path, asset=asset, asset_class=asset_class,
            from_date=from_date, through_date=through_date, merge_mode=merge_mode,
            provider_symbol_override=provider_symbol,
            mapping_class=mapping_class,
        )
        if progress:
            progress("validating"); progress("ingesting")
        return result
    if provider == "BINANCE":
        return acquire_binance(
            database_path, asset=asset, timeframe=timeframe,
            provider_symbol=provider_symbol, from_date=from_date,
            through_date=through_date, merge_mode=merge_mode, progress=progress,
            mapping_class=mapping_class,
            api_base_url=provider_api_base_url,
        )
    if provider == "COINGECKO":
        return acquire_coingecko(
            database_path, asset=asset, timeframe=timeframe,
            provider_symbol=provider_symbol, from_date=from_date,
            through_date=through_date, merge_mode=merge_mode, progress=progress,
            mapping_class=mapping_class,
        )
    raise ValueError(f"unsupported orchestrated provider: {provider}")
