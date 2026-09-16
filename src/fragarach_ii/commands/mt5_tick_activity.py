"""Plan, start, inspect, or wake the governed MT5 tick-activity backfill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fragarach_ii.external_consumer_service import canonical_database_path
from fragarach_ii.mt5_tick_activity import (
    activity_coverage,
    activity_paths,
    plan_activity_backfill,
    queue_activity_backfill_requests,
    start_activity_backfill,
)
from fragarach_ii.replica_publication import ReplicaPaths


def _read_state(support: Path) -> dict:
    path = activity_paths(support)["state"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "NOT_STARTED", "lanes": {}}
    return value if isinstance(value, dict) else {"status": "INVALID_STATE", "lanes": {}}


def main() -> int:
    canonical = canonical_database_path()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("status", "plan", "start", "queue"))
    parser.add_argument("--database", type=Path, default=canonical)
    parser.add_argument("--support", type=Path)
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--timeframe", action="append", default=[])
    parser.add_argument("--max-requests", type=int, default=1)
    arguments = parser.parse_args()
    support = arguments.support or ReplicaPaths.for_database(arguments.database).support
    symbols = set(arguments.symbol) or None
    timeframes = set(arguments.timeframe) or None
    if arguments.mode == "plan":
        result = plan_activity_backfill(
            arguments.database, support, symbols=symbols, timeframes=timeframes,
        )
    elif arguments.mode == "start":
        result = start_activity_backfill(
            arguments.database, support, symbols=symbols, timeframes=timeframes,
        )
    elif arguments.mode == "queue":
        result = queue_activity_backfill_requests(
            arguments.database, support, max_requests=arguments.max_requests,
        )
    else:
        result = {"backfill": _read_state(support), **activity_coverage(arguments.database)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
