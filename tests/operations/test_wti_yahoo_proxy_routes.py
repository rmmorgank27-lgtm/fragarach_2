from __future__ import annotations

from pathlib import Path

from fragarach_ii.acquisition_orchestrator import load_provider_profiles, mapping_authority
from fragarach_ii.lane_commissioning import resolved_calendar_id
from fragarach_ii import provider_route_settings


def test_wti_etf_and_us_oil_proxy_are_reviewed_yahoo_daily_routes() -> None:
    yahoo = next(profile for profile in load_provider_profiles() if profile.provider == "YAHOO_FINANCE")
    uso = mapping_authority(yahoo, symbol="USO", timeframe="D1", primary_provider=None, primary_symbol=None)
    usoil = mapping_authority(yahoo, symbol="USOIL", timeframe="D1", primary_provider=None, primary_symbol=None)

    assert yahoo.supported_asset_classes.count("ENERGY") == 1
    assert (uso["provider_symbol"], uso["mapping_class"], uso["direct_real_eligible"]) == ("USO", "EXACT_REPRESENTATION", True)
    assert (usoil["provider_symbol"], usoil["mapping_class"], usoil["direct_real_eligible"]) == ("USO", "APPROVED_EQUIVALENT_REPRESENTATION", True)
    assert resolved_calendar_id(asset_class="ENERGY", calendar_id="REGISTRY_D1_V1", exchange_name="OTC", canonical_symbol="USOIL") == "US_EQUITIES_D1_V1"


def test_operator_route_override_replaces_mapping_and_calendar(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "provider-routes.json"
    monkeypatch.setattr(provider_route_settings, "DEFAULT_PATH", path)
    route = provider_route_settings.update_provider_route(
        provider="YAHOO_FINANCE", asset="USOIL", provider_symbol="USO",
        timeframe="D1", mapping_class="APPROVED_EQUIVALENT_REPRESENTATION",
        calendar_id="US_EQUITIES_D1_V1",
    )
    assert route["authority_source"] == "OPERATOR_CONFIGURED_PROVIDER_ROUTE"
    assert provider_route_settings.configured_calendar_for_symbol("USOIL") == "US_EQUITIES_D1_V1"
