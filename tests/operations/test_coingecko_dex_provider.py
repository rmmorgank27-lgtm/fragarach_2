from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import fragarach_ii.providers.coingecko_dex as provider
from fragarach_ii.providers.twelve_data import AcquisitionError


NOW = datetime(2026, 8, 15, 13, tzinfo=UTC)
SYMBOL = (
    "eth:0xa43fe16908251ee70ef74718545e4fe6c5ccec9f:base:"
    "0x6982508145454ce325ddbe47a25d4ec3d2311933"
)


def _payload(*, count: int = 30, gap_at: int | None = None, address: str | None = None) -> bytes:
    first = int(datetime(2026, 8, 15, 10, 30, tzinfo=UTC).timestamp())
    rows = []
    for index in range(count):
        if index == gap_at:
            continue
        opened = 0.0000026 + index / 1_000_000_000_000
        rows.append([first + index * 300, opened, opened + 0.00000001, opened - 0.00000001, opened + 0.000000005, 100 + index])
    return json.dumps({
        "data": {"attributes": {"ohlcv_list": list(reversed(rows))}},
        "meta": {
            "base": {"address": address or "0x6982508145454ce325ddbe47a25d4ec3d2311933"},
            "quote": {"address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"},
        },
    }).encode()


def _capture(monkeypatch):
    captured = {}

    def ingest(_database, *, batch, evidence, **kwargs):
        captured.update(batch=batch, evidence=evidence, kwargs=kwargs)
        return SimpleNamespace(
            inserted=len(batch.bars), corrected=0,
            as_dict=lambda: {"inserted": len(batch.bars), "corrected": 0, "unchanged": 0},
        )

    monkeypatch.setattr(provider, "ingest_staged_batch", ingest)
    monkeypatch.setattr(
        provider, "persist_committed_lane_validation",
        lambda *_args, **_kwargs: SimpleNamespace(as_dict=lambda: {"calendar_id": "CRYPTO_24X7_V1"}),
    )
    return captured


def test_m5_pool_candles_are_identity_checked_continuous_and_ingested(monkeypatch) -> None:
    captured = _capture(monkeypatch)
    requested = []
    result = provider.acquire_coingecko_dex(
        "unused.sqlite3", asset="PEPEUSD", timeframe="M5", provider_symbol=SYMBOL,
        from_date="2026-08-15T10:30:00+00:00",
        through_date="2026-08-15T13:00:00+00:00",
        fetch=lambda url: requested.append(url) or _payload(), clock=lambda: NOW,
    )
    assert result["provider_id"] == "COINGECKO_DEX"
    assert result["completed_observations_received"] == 30
    assert len(captured["batch"].bars) == 30
    assert all(bar.provider == "COINGECKO_DEX" for bar in captured["batch"].bars)
    assert "include_empty_intervals=true" in requested[0]
    assert "currency=usd" in requested[0]


def test_missing_interval_is_rejected_before_ingestion(monkeypatch) -> None:
    _capture(monkeypatch)
    with pytest.raises(AcquisitionError) as raised:
        provider.acquire_coingecko_dex(
            "unused.sqlite3", asset="PEPEUSD", timeframe="M5", provider_symbol=SYMBOL,
            from_date="2026-08-15T10:30:00+00:00",
            through_date="2026-08-15T13:00:00+00:00",
            fetch=lambda _url: _payload(gap_at=10), clock=lambda: NOW,
        )
    assert raised.value.code == "INVALID_CHRONOLOGY"


def test_pool_token_identity_mismatch_is_rejected(monkeypatch) -> None:
    _capture(monkeypatch)
    with pytest.raises(AcquisitionError) as raised:
        provider.acquire_coingecko_dex(
            "unused.sqlite3", asset="PEPEUSD", timeframe="M5", provider_symbol=SYMBOL,
            from_date="2026-08-15T10:30:00+00:00",
            through_date="2026-08-15T13:00:00+00:00",
            fetch=lambda _url: _payload(address="0x0000000000000000000000000000000000000001"),
            clock=lambda: NOW,
        )
    assert raised.value.code == "ORIENTATION_MISMATCH"
