"""Validate one canonical D1 lane against explicit versioned expectations."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from fragarach_ii.validation import ValidationError, validate_lane


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--through-date", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--persist", action="store_true")
    mode.add_argument("--no-persist", action="store_false", dest="persist")
    parser.set_defaults(persist=False)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    database = str(Path(arguments.database).expanduser().resolve())
    try:
        result = validate_lane(
            database,
            symbol=arguments.symbol,
            timeframe=arguments.timeframe,
            through_date=arguments.through_date,
            persist=arguments.persist,
        )
    except ValidationError as error:
        payload = {"code": error.code, "error": str(error), "persisted": False}
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    payload = {"database_path": database, "persisted": arguments.persist, **result.as_dict()}
    if arguments.json_output:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
