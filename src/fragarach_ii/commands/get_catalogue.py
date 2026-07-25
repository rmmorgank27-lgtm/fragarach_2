"""Return the versioned, read-only Fragarach active-Estate catalogue as JSON."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence

from fragarach_ii.external_consumer_service import get_catalogue


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    try:
        payload = get_catalogue()
    except (FileNotFoundError, RuntimeError, sqlite3.Error, ValueError) as error:
        payload = {"contract": "fragarach.catalogue.v1", "status": "AUTHORITY_UNAVAILABLE", "reason": str(error)}
        exit_code = 1
    else:
        exit_code = 0
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
