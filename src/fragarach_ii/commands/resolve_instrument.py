"""Resolve instrument identity without provider access or authority mutation."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from fragarach_ii.identity_resolver import resolve_instrument


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--json", action="store_true", required=True)
    arguments = parser.parse_args(argv)
    try:
        result = resolve_instrument(Path(arguments.database).expanduser().resolve(), arguments.query)
    except (ValueError, FileNotFoundError, RuntimeError, sqlite3.Error) as error:
        print(json.dumps({"code": "IDENTITY_RESOLUTION_FAILED", "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    print(result.as_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
