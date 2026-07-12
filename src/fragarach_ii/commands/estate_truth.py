"""Read the complete SPEC-009C EstateTruthState as structured JSON."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

from fragarach_ii.estate_truth_service import estate_truth_state


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--json", action="store_true", required=True)
    arguments = parser.parse_args(argv)
    try:
        result = estate_truth_state(Path(arguments.database).expanduser().resolve())
    except (FileNotFoundError, RuntimeError, sqlite3.Error, ValueError) as error:
        print(json.dumps({"code": "ESTATE_TRUTH_SERVICE_FAILED", "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
