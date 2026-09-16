from __future__ import annotations

from fragarach_ii.crypto_intraday_quality import assess_crypto_intraday_rows


def _rows(count: int, *, flat: bool = False, zero_volume: bool = False, step: int = 300):
    rows = []
    for index in range(count):
        opened = 100.0 + index / 100
        high = opened if flat else opened + 0.02
        low = opened if flat else opened - 0.01
        rows.append((index * step, opened, high, low, opened, 0.0 if zero_volume else 10.0))
    return rows


def test_mostly_flat_intraday_candles_are_unusable() -> None:
    result = assess_crypto_intraday_rows(
        asset="ETHUSD", timeframe="M5", rows=_rows(30, flat=True),
        provider="BINANCE", provider_symbol="ETHUSD",
    )
    assert result["status"] == "UNUSABLE"
    assert "MOST_CANDLES_HAVE_NO_PRICE_RANGE" in result["reason_codes"]


def test_missing_volume_does_not_reject_good_price_candles() -> None:
    result = assess_crypto_intraday_rows(
        asset="SUIUSD", timeframe="M5", rows=_rows(30, zero_volume=True),
        provider="TWELVE_DATA", provider_symbol="SUI/USD",
    )
    assert result["status"] == "USABLE_PRICE_ONLY"
    assert result["reason_codes"] == ["VOLUME_UNAVAILABLE"]


def test_liquid_usdt_route_is_usable() -> None:
    result = assess_crypto_intraday_rows(
        asset="ETHUSD", timeframe="H1", rows=_rows(30, step=3600),
        provider="BINANCE", provider_symbol="ETHUSDT",
    )
    assert result["status"] == "USABLE"


def test_discontinuous_h1_series_is_unusable_after_a_route_change() -> None:
    rows = []
    for index in range(30):
        opened = 100.0 + index * 2
        rows.append((index * 3600, opened, opened + 1, opened - 1, opened + 0.5, 10.0))
    result = assess_crypto_intraday_rows(
        asset="ETHUSD", timeframe="H1", rows=rows,
        provider="BINANCE", provider_symbol="ETHUSDT",
    )
    assert result["status"] == "UNUSABLE"
    assert "DISCONTINUOUS_H1_CANDLE_SERIES" in result["reason_codes"]


def test_missing_intraday_interval_is_unusable() -> None:
    rows = _rows(30)
    rows[15] = (rows[15][0] + 300, *rows[15][1:])
    result = assess_crypto_intraday_rows(
        asset="PEPEUSD", timeframe="M5", rows=rows,
        provider="COINGECKO_DEX", provider_symbol="reviewed-pool",
    )
    assert result["status"] == "UNUSABLE"
    assert "MISSING_OR_MISALIGNED_INTRADAY_INTERVALS" in result["reason_codes"]
