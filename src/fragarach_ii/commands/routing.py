"""Read and edit the revisioned SPEC-067 routing authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fragarach_ii.routing_service import (
    RoutingServiceError,
    activate_draft,
    provider_catalogue_snapshot,
    restore_estate_default,
    routing_snapshot,
    save_draft,
    validate_draft,
)


def _csv(value: str | None) -> list[str]:
    return [item.strip().upper() for item in (value or "").split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--mode", choices=("status", "catalogue", "draft", "validate", "preview", "activate", "restore-default"), default="status")
    parser.add_argument("--symbol")
    parser.add_argument("--timeframe")
    parser.add_argument("--providers")
    parser.add_argument("--disabled")
    parser.add_argument("--operator-reason")
    parser.add_argument("--draft-id")
    parser.add_argument("--restore-default", action="store_true")
    parser.add_argument("--json", action="store_true", required=True)
    arguments = parser.parse_args(argv)
    try:
        if arguments.mode == "status":
            result = routing_snapshot(arguments.database)
        elif arguments.mode == "catalogue":
            result = provider_catalogue_snapshot(arguments.database)
        elif arguments.mode == "draft":
            if not arguments.symbol or not arguments.timeframe or not arguments.operator_reason:
                parser.error("draft requires symbol, timeframe, and operator reason")
            result = save_draft(
                arguments.database, symbol=arguments.symbol, timeframe=arguments.timeframe,
                provider_order=_csv(arguments.providers), disabled_providers=_csv(arguments.disabled),
                operator_reason=arguments.operator_reason, draft_id=arguments.draft_id,
                restore_default=arguments.restore_default,
            )
        elif arguments.mode in {"validate", "preview"}:
            if not arguments.draft_id:
                parser.error(f"{arguments.mode} requires draft id")
            result = validate_draft(arguments.database, arguments.draft_id)
        elif arguments.mode == "activate":
            if not arguments.draft_id:
                parser.error("activate requires draft id")
            result = activate_draft(arguments.database, arguments.draft_id)
        else:
            if not arguments.symbol or not arguments.timeframe or not arguments.operator_reason:
                parser.error("restore-default requires symbol, timeframe, and operator reason")
            result = restore_estate_default(
                arguments.database, symbol=arguments.symbol, timeframe=arguments.timeframe,
                operator_reason=arguments.operator_reason,
            )
    except RoutingServiceError as error:
        print(json.dumps({"outcome": "REJECTED", "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
