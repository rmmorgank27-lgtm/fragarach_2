from __future__ import annotations

from fragarach_ii.acquisition_orchestrator import load_provider_profiles, mapping_authority


def test_commissioned_crypto_assets_have_binance_intraday_and_coingecko_daily_routes() -> None:
    profiles = {profile.provider: profile for profile in load_provider_profiles()}
    expected = {
        "AVAXUSD": ("AVAXUSDT", "avalanche-2"),
        "DOGEUSD": ("DOGEUSDT", "dogecoin"),
        "DOTUSD": ("DOTUSDT", "polkadot"),
        "LINKUSD": ("LINKUSDT", "chainlink"),
    }

    for symbol, (binance_symbol, coingecko_symbol) in expected.items():
        intraday = mapping_authority(
            profiles["BINANCE"],
            symbol=symbol,
            timeframe="H1",
            primary_provider="TWELVE_DATA",
            primary_symbol=f"{symbol[:-3]}/USD",
        )
        daily = mapping_authority(
            profiles["COINGECKO"],
            symbol=symbol,
            timeframe="D1",
            primary_provider="TWELVE_DATA",
            primary_symbol=f"{symbol[:-3]}/USD",
        )

        assert intraday["provider_symbol"] == binance_symbol
        assert intraday["direct_real_eligible"] is True
        assert intraday["quote_equivalence"] == "USD_USDT_CRYPTO"
        assert daily["provider_symbol"] == coingecko_symbol
        assert daily["direct_real_eligible"] is True

    hype = mapping_authority(
        profiles["TWELVE_DATA"], symbol="HYPEUSD", timeframe="H1",
        primary_provider=None, primary_symbol=None,
    )
    assert hype["provider_symbol"] == "HYPE/USDT"
    assert hype["direct_real_eligible"] is True


def test_reviewed_twelve_data_fx_mapping_inherits_intraday_contract_support() -> None:
    profile = next(item for item in load_provider_profiles() if item.provider == "TWELVE_DATA")
    route = mapping_authority(
        profile, symbol="GBPCHF", timeframe="H1", primary_provider=None, primary_symbol=None,
        resolved_mapping={
            "status": "OPERATOR_RESOLVED",
            "mapping_class": "EXACT_REPRESENTATION",
            "provider_symbol": "GBP/CHF",
            "provider_asset_class": "FX",
            "provider_instrument_type": "Physical Currency",
            "timeframe_capabilities": {"D1": {"supported": True}},
        },
    )
    assert route["direct_real_eligible"] is True
    assert route["timeframe_supported"] is True
    assert route["timeframe_capability"]["verification_method"] == "TWELVE_DATA_REVIEWED_FX_CONTRACT"
