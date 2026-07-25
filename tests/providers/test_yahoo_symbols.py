from __future__ import annotations

from fragarach_ii.providers.yahoo_symbols import (
    YAHOO_EQUITY_EXCHANGE_SUFFIXES,
    yahoo_equity_symbol_for_representation,
)


def test_exchange_suffix_table_derives_yahoo_equity_symbols() -> None:
    expected = {
        "NYSE": ("NYSE:RIO", "RIO"),
        "NASDAQ": ("NASDAQ:MSFT", "MSFT"),
        "AMEX": ("AMEX:SPY", "SPY"),
        "ARCA": ("ARCA:DIA", "DIA"),
        "ASX": ("ASX:BHP", "BHP.AX"),
        "LSE": ("LSE:RIO", "RIO.L"),
        "XETRA": ("XETRA:SAP", "SAP.DE"),
        "FRA": ("FRA:SAP", "SAP.DE"),
        "EPA": ("EPA:OR", "OR.PA"),
        "PAR": ("PAR:OR", "OR.PA"),
        "AMS": ("AMS:ASML", "ASML.AS"),
        "TSE": ("TSE:7203", "7203.T"),
        "JPX": ("JPX:7203", "7203.T"),
        "HKEX": ("HKEX:0005", "0005.HK"),
        "TSX": ("TSX:SHOP", "SHOP.TO"),
        "TSXV": ("TSXV:ABC", "ABC.V"),
    }
    assert set(expected).issubset(YAHOO_EQUITY_EXCHANGE_SUFFIXES)
    for _venue, (representation, yahoo_symbol) in expected.items():
        assert yahoo_equity_symbol_for_representation(representation) == yahoo_symbol


def test_unknown_yahoo_equity_venue_requires_mapping_review() -> None:
    assert yahoo_equity_symbol_for_representation("UNKNOWN:RIO") is None
    assert yahoo_equity_symbol_for_representation("RIO", "UNKNOWN") is None
