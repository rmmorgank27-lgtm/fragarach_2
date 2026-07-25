"""User-owned operational settings bounded by reviewed provider contracts."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path


CONTRACT = "fragarach_ii.provider_runtime_settings.v1"
DEFAULT_PATH = Path("~/Library/Application Support/Fragarach II/provider-runtime-settings.json").expanduser()


def settings_path(path: str | Path | None = None) -> Path:
    return Path(path).expanduser() if path else DEFAULT_PATH


def load_provider_overrides(path: str | Path | None = None) -> dict[str, dict[str, object]]:
    try:
        value = json.loads(settings_path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    providers = value.get("providers") if value.get("contract") == CONTRACT else None
    if not isinstance(providers, dict):
        return {}
    return {
        str(provider).upper(): dict(values)
        for provider, values in providers.items() if isinstance(values, dict)
    }


def update_provider_override(
    provider: str,
    *,
    enabled: bool,
    operational_limit: int,
    concurrency_limit: int,
    contract_request_limit: int,
    contract_concurrency_limit: int,
    path: str | Path | None = None,
) -> dict[str, object]:
    if not 1 <= operational_limit <= contract_request_limit:
        raise ValueError(f"operational limit must be between 1 and {contract_request_limit}")
    if not 1 <= concurrency_limit <= contract_concurrency_limit:
        raise ValueError(f"concurrency limit must be between 1 and {contract_concurrency_limit}")
    target = settings_path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = target.with_suffix(f"{target.suffix}.lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            overrides = load_provider_overrides(target)
            overrides[provider.upper()] = {
                "enabled": bool(enabled),
                "operational_limit": int(operational_limit),
                "concurrency_limit": int(concurrency_limit),
            }
            payload = {"contract": CONTRACT, "providers": overrides}
            descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return {"contract": CONTRACT, "provider": provider.upper(), **overrides[provider.upper()]}
