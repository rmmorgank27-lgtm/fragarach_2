"""Central Yahoo Finance exchange-suffix derivation for listed equities."""
from __future__ import annotations

import re

YAHOO_EQUITY_EXCHANGE_SUFFIXES: dict[str, str] = {
    "NYSE": "",
    "NASDAQ": "",
    "AMEX": "",
    "ARCA": "",
    "NYSE ARCA": "",
    "US LISTED": "",
    "ASX": ".AX",
    "LSE": ".L",
    "XLON": ".L",
    "XETRA": ".DE",
    "XETR": ".DE",
    "FRA": ".DE",
    "EPA": ".PA",
    "PAR": ".PA",
    "AMS": ".AS",
    "TSE": ".T",
    "JPX": ".T",
    "HKEX": ".HK",
    "TSX": ".TO",
    "TSXV": ".V",
}


def yahoo_equity_symbol_for_representation(
    representation_symbol: str, exchange_or_venue: str | None = None
) -> str | None:
    """Derive a Yahoo equity symbol from the selected listed representation."""

    venue, ticker = split_listed_representation(representation_symbol)
    venue = venue or exchange_or_venue
    ticker = ticker.strip().upper()
    if not ticker:
        return None
    suffix = YAHOO_EQUITY_EXCHANGE_SUFFIXES.get(_normalize_exchange(venue or ""))
    if suffix is None:
        return None
    return f"{ticker}{suffix}"


def split_listed_representation(value: str) -> tuple[str | None, str]:
    text = value.strip().upper()
    if ":" not in text:
        return None, text
    venue, ticker = text.split(":", 1)
    return venue.strip() or None, ticker.strip()


def _normalize_exchange(value: str) -> str:
    text = re.sub(r"[^A-Z0-9]+", " ", value.strip().upper()).strip()
    aliases = {
        "NYSE AMERICAN": "AMEX",
        "NYSE MKT": "AMEX",
        "NYSEARCA": "ARCA",
        "LONDON STOCK EXCHANGE": "LSE",
        "FRANKFURT": "FRA",
        "DEUTSCHE BORSE XETRA": "XETRA",
        "EURONEXT PARIS": "EPA",
        "PARIS": "PAR",
        "EURONEXT AMSTERDAM": "AMS",
        "TOKYO STOCK EXCHANGE": "TSE",
        "JAPAN EXCHANGE GROUP": "JPX",
        "HONG KONG STOCK EXCHANGE": "HKEX",
        "TORONTO STOCK EXCHANGE": "TSX",
        "TSX VENTURE": "TSXV",
    }
    return aliases.get(text, text)
