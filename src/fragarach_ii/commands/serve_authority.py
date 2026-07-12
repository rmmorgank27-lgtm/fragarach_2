"""Serve one SPEC-009A historical-authority response as structured JSON."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

from fragarach_ii.authority_service import AuthorityServiceError, serve_historical_authority


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--start-time-utc", type=int)
    parser.add_argument("--end-time-utc", type=int)
    parser.add_argument("--json", action="store_true", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        payload = serve_historical_authority(
            Path(arguments.database).expanduser().resolve(),
            symbol=arguments.symbol,
            timeframe=arguments.timeframe,
            start_time_utc=arguments.start_time_utc,
            end_time_utc=arguments.end_time_utc,
        )
    except AuthorityServiceError as error:
        print(json.dumps({"code": error.code, "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 2
    except (FileNotFoundError, RuntimeError, sqlite3.Error) as error:
        print(json.dumps({"code": "AUTHORITY_SERVICE_FAILED", "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
