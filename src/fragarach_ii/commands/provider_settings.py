"""Read or update bounded user Provider runtime settings."""

from __future__ import annotations

import argparse
import json

from fragarach_ii.acquisition_orchestrator import load_provider_profiles
from fragarach_ii.provider_settings import load_provider_overrides, update_provider_override


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("status", "update"), default="status")
    parser.add_argument("--provider")
    parser.add_argument("--enabled", choices=("true", "false"))
    parser.add_argument("--operational-limit", type=int)
    parser.add_argument("--concurrency-limit", type=int)
    parser.add_argument("--json", action="store_true", required=True)
    arguments = parser.parse_args(argv)
    if arguments.mode == "status":
        print(json.dumps({"providers": load_provider_overrides()}, sort_keys=True, separators=(",", ":")))
        return 0
    if not arguments.provider or arguments.enabled is None or arguments.operational_limit is None or arguments.concurrency_limit is None:
        parser.error("update requires provider, enabled, operational limit, and concurrency limit")
    profiles = {item.provider: item for item in load_provider_profiles(apply_runtime_overrides=False)}
    profile = profiles.get(arguments.provider.upper())
    if profile is None:
        parser.error(f"unsupported provider: {arguments.provider}")
    try:
        result = update_provider_override(
            profile.provider, enabled=arguments.enabled == "true",
            operational_limit=arguments.operational_limit,
            concurrency_limit=arguments.concurrency_limit,
            contract_request_limit=profile.request_limit,
            contract_concurrency_limit=profile.concurrency_limit,
        )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
