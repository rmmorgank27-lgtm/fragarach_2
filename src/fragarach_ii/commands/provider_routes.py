"""Inspect or save an explicit reviewed provider alias/proxy route."""

from __future__ import annotations

import argparse
import json

from fragarach_ii.provider_route_settings import load_route_overrides, update_provider_route


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("status", "upsert"), default="status")
    parser.add_argument("--provider"); parser.add_argument("--asset"); parser.add_argument("--provider-symbol")
    parser.add_argument("--timeframe", default="D1"); parser.add_argument("--mapping-class")
    parser.add_argument("--calendar-id"); parser.add_argument("--json", action="store_true", required=True)
    arguments = parser.parse_args(argv)
    if arguments.mode == "status":
        print(json.dumps({"routes": load_route_overrides()}, sort_keys=True, separators=(",", ":"))); return 0
    required = (arguments.provider, arguments.asset, arguments.provider_symbol, arguments.mapping_class, arguments.calendar_id)
    if not all(required): parser.error("upsert requires provider, asset, provider symbol, mapping class, and calendar ID")
    try:
        result = update_provider_route(
            provider=arguments.provider, asset=arguments.asset, provider_symbol=arguments.provider_symbol,
            timeframe=arguments.timeframe, mapping_class=arguments.mapping_class, calendar_id=arguments.calendar_id,
        )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True, separators=(",", ":"))); return 0


if __name__ == "__main__":
    raise SystemExit(main())
