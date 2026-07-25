"""Read one compact SPEC-009B TruthState as structured JSON."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.truth_engine import TruthEngineError, truth_state_for_lane


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--json", action="store_true", required=True)
    arguments = parser.parse_args(argv)
    try:
        authority_generated = datetime.now(UTC)
        state = truth_state_for_lane(
            Path(arguments.database).expanduser().resolve(),
            symbol=arguments.symbol,
            timeframe=arguments.timeframe,
            as_of=authority_generated,
            authority_generated=authority_generated.isoformat(),
        )
    except TruthEngineError as error:
        print(json.dumps({"code": error.code, "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 2
    except (FileNotFoundError, RuntimeError, sqlite3.Error) as error:
        print(json.dumps({"code": "TRUTH_ENGINE_FAILED", "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(state, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
