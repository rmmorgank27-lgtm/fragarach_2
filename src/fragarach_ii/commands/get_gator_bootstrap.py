"""Return one bounded Gator bootstrap bundle as compact JSON."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence

from fragarach_ii.gator_bootstrap_service import (
    GatorBootstrapError,
    GatorBootstrapService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--bar-capacity", type=int, default=270)
    parser.add_argument("--json", action="store_true", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        payload = GatorBootstrapService(arguments.database).build(
            bar_capacity=arguments.bar_capacity
        )
    except (GatorBootstrapError, FileNotFoundError, RuntimeError, sqlite3.Error) as error:
        payload = {
            "contract": "fragarach.gator_bootstrap.v1",
            "status": "AUTHORITY_UNAVAILABLE",
            "warnings": [str(error)],
            "symbols": [],
            "lanes": [],
        }
        exit_code = 1
    else:
        exit_code = 0
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
