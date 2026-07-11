"""Checksummed provider-contract configuration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class ProviderConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider_id: str
    provider_contract: str
    provider_host: str
    base_url: str
    endpoint_path: str
    endpoint_family: str
    timeframe: str
    interval: str
    timezone: str
    order: str
    authentication_environment: str
    connect_timeout_seconds: int
    read_timeout_seconds: int
    max_attempts: int
    retry_backoff_seconds: tuple[int, ...]
    max_response_bytes: int
    max_calendar_days: int
    user_agent: str
    configuration_checksum: str


def load_provider_config(config_root: str | Path | None = None) -> ProviderConfig:
    root = (
        Path(config_root).resolve()
        if config_root is not None
        else Path(__file__).resolve().parents[3] / "config"
    )
    path = root / "providers/twelve_data_time_series_d1.v1.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProviderConfigurationError(f"cannot load provider configuration: {error}") from error
    stored = raw.get("configuration_checksum")
    payload = {key: value for key, value in raw.items() if key != "configuration_checksum"}
    actual = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    if stored != actual:
        raise ProviderConfigurationError("provider configuration checksum drift")
    required = {
        "format": "fragarach_ii.provider_contract.v1",
        "provider_id": "TWELVE_DATA",
        "provider_contract": "TWELVE_DATA_TIME_SERIES_D1_V1",
        "provider_host": "api.twelvedata.com",
        "base_url": "https://api.twelvedata.com",
        "endpoint_path": "/time_series",
        "timeframe": "D1",
        "interval": "1day",
        "timezone": "UTC",
        "order": "ASC",
    }
    for key, value in required.items():
        if raw.get(key) != value:
            raise ProviderConfigurationError(f"unsupported provider configuration field: {key}")
    if raw.get("authentication_environment") != "TWELVE_DATA_API_KEY":
        raise ProviderConfigurationError("unsupported credential environment")
    return ProviderConfig(
        provider_id=raw["provider_id"], provider_contract=raw["provider_contract"],
        provider_host=raw["provider_host"], base_url=raw["base_url"],
        endpoint_path=raw["endpoint_path"], endpoint_family=raw["endpoint_family"],
        timeframe=raw["timeframe"], interval=raw["interval"], timezone=raw["timezone"],
        order=raw["order"], authentication_environment=raw["authentication_environment"],
        connect_timeout_seconds=raw["connect_timeout_seconds"],
        read_timeout_seconds=raw["read_timeout_seconds"], max_attempts=raw["max_attempts"],
        retry_backoff_seconds=tuple(raw["retry_backoff_seconds"]),
        max_response_bytes=raw["max_response_bytes"],
        max_calendar_days=raw["max_calendar_days"], user_agent=raw["user_agent"],
        configuration_checksum=stored,
    )
