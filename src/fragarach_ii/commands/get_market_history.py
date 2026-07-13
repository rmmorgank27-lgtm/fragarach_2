"""Return one SPEC-026 Market History response as JSON."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence

from fragarach_ii.market_history_service import (
    MarketHistoryService,
    MarketHistoryServiceError,
    MarketHistoryWindow,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    window = parser.add_mutually_exclusive_group(required=True)
    window.add_argument("--last-trading-days", type=int)
    window.add_argument("--between-start")
    parser.add_argument("--between-end")
    parser.add_argument("--json", action="store_true", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.last_trading_days is not None:
            if arguments.between_end is not None:
                raise MarketHistoryServiceError(
                    "INVALID_TIME_WINDOW", "between-end requires between-start"
                )
            requested_window = MarketHistoryWindow.last_trading_days(
                arguments.last_trading_days
            )
        else:
            if arguments.between_end is None:
                raise MarketHistoryServiceError(
                    "INVALID_TIME_WINDOW", "between-end is required"
                )
            requested_window = MarketHistoryWindow.between(
                arguments.between_start, arguments.between_end
            )
        payload = MarketHistoryService(arguments.database).get_market_history(
            arguments.symbol,
            arguments.timeframe,
            requested_window,
        )
    except MarketHistoryServiceError as error:
        payload = {
            "OHLC": [],
            "CAODT": None,
            "Status": error.code,
            "Warnings": [str(error)],
        }
        exit_code = 2
    except (FileNotFoundError, RuntimeError, sqlite3.Error) as error:
        payload = {
            "OHLC": [],
            "CAODT": None,
            "Status": "AUTHORITY_UNAVAILABLE",
            "Warnings": [str(error)],
        }
        exit_code = 1
    else:
        exit_code = 0
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
