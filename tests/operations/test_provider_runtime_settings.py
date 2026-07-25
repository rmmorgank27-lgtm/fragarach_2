from __future__ import annotations

from pathlib import Path

from fragarach_ii.acquisition_orchestrator import load_provider_profiles
from fragarach_ii import provider_settings


def test_runtime_provider_settings_are_bounded_and_applied(tmp_path: Path, monkeypatch) -> None:
    settings = tmp_path / "provider-settings.json"
    monkeypatch.setattr(provider_settings, "DEFAULT_PATH", settings)

    provider_settings.update_provider_override(
        "TWELVE_DATA", enabled=False, operational_limit=42, concurrency_limit=2,
        contract_request_limit=55, contract_concurrency_limit=4,
    )
    effective = {item.provider: item for item in load_provider_profiles()}["TWELVE_DATA"]
    contract = {item.provider: item for item in load_provider_profiles(apply_runtime_overrides=False)}["TWELVE_DATA"]

    assert (effective.enabled, effective.operational_limit, effective.concurrency_limit) == (False, 42, 2)
    assert (contract.enabled, contract.operational_limit, contract.concurrency_limit) == (True, 55, 4)
