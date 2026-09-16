from fragarach_ii.acquisition_orchestrator import (
    load_provider_profiles,
    mapping_authority,
)


def test_tsla_has_reviewed_yahoo_d1_fallback() -> None:
    yahoo = next(
        profile
        for profile in load_provider_profiles(apply_runtime_overrides=False)
        if profile.provider == "YAHOO_FINANCE"
    )

    route = mapping_authority(
        yahoo,
        symbol="TSLA",
        timeframe="D1",
        primary_provider="TWELVE_DATA",
        primary_symbol="TSLA",
    )

    assert route["direct_real_eligible"] is True
    assert route["provider_symbol"] == "TSLA"
    assert route["mapping_class"] == "EXACT_REPRESENTATION"
    assert route["authority_source"] == (
        "OPERATOR_APPROVED_TSLA_D1_FALLBACK_2026-08-24"
    )


def test_tsla_yahoo_fallback_is_d1_only() -> None:
    yahoo = next(
        profile
        for profile in load_provider_profiles(apply_runtime_overrides=False)
        if profile.provider == "YAHOO_FINANCE"
    )

    route = mapping_authority(
        yahoo,
        symbol="TSLA",
        timeframe="H1",
        primary_provider="TWELVE_DATA",
        primary_symbol="TSLA",
    )

    assert route["direct_real_eligible"] is True
    assert route["timeframe_supported"] is False
