"""List histories available through the read-only external-consumer service."""

from __future__ import annotations

import json
import sqlite3
import sys

from fragarach_ii.external_consumer_service import list_histories


def main() -> int:
    try:
        payload = list_histories()
    except (FileNotFoundError, RuntimeError, sqlite3.Error) as error:
        payload = {"status": "AUTHORITY_UNAVAILABLE", "reason": str(error)}
        exit_code = 1
    else:
        exit_code = 0
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
