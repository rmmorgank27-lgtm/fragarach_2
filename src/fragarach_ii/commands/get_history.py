"""Return one SPEC-018 external-consumer history response as JSON."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence

from fragarach_ii.external_consumer_service import (
    ExternalConsumerServiceError,
    get_history,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--json", action="store_true", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        payload = get_history(arguments.symbol, arguments.timeframe)
    except ExternalConsumerServiceError as error:
        payload = {"status": error.code, "reason": str(error)}
        exit_code = 2
    except (FileNotFoundError, RuntimeError, sqlite3.Error) as error:
        payload = {"status": "AUTHORITY_UNAVAILABLE", "reason": str(error)}
        exit_code = 1
    else:
        exit_code = 0
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
