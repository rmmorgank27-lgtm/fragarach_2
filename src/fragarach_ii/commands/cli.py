"""Fragarach II diagnostic command line."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from fragarach_ii.execution_trace import trace_for_lane


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fragarach-ii")
    subcommands = parser.add_subparsers(dest="command", required=True)
    trace = subcommands.add_parser(
        "execution-trace", help="read one Scheduler execution trace without dispatching work"
    )
    trace.add_argument("symbol")
    trace.add_argument("timeframe")
    trace.add_argument(
        "--database",
        default=os.environ.get(
            "FRAGARACH_DATABASE",
            "data/runtime/spec002_real_evidence_acceptance.sqlite3",
        ),
    )
    trace.add_argument("--journal")
    trace.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    database = Path(arguments.database).expanduser().resolve()
    journal = Path(arguments.journal).expanduser().resolve() if arguments.journal else Path(f"{database}.scheduler.json")
    try:
        payload = json.loads(journal.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Operational journal not found: {journal}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(f"Operational journal is unreadable: {error}", file=sys.stderr)
        return 2
    result = trace_for_lane(payload, arguments.symbol, arguments.timeframe)
    if arguments.json_output:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result["trace_id"] else 1
    labels = (
        ("Lane", result["lane"]),
        ("Trace ID", result["trace_id"]),
        ("Queue age", _duration(result["queue_age_seconds"])),
        ("Current stage", result["current_stage"]),
        ("Last successful stage", result["last_successful_stage"]),
        ("Stop reason", result["stop_reason"]),
        ("Attempt count", result["attempt_count"]),
        ("Provider", result["provider"]),
        ("Canonical edge before", result["canonical_edge_before"]),
        ("Canonical edge after", result["canonical_edge_after"]),
        ("Queue disposition", result["queue_disposition"]),
        ("Final lane state", result["final_lane_state"]),
    )
    for label, value in labels:
        print(f"{label}: {value if value is not None else '—'}")
    if result["events"]:
        print("\nEvents")
        for event in result["events"]:
            reason = f" · {event['reason_code']}" if event.get("reason_code") else ""
            provider = f" · {event['provider']}" if event.get("provider") else ""
            print(
                f"{event['timestamp']}  #{event['attempt_number']}  "
                f"{event['event']}  {event['result']}{reason}{provider}"
            )
    return 0 if result["trace_id"] else 1


def _duration(value: object) -> str:
    if value is None:
        return "—"
    seconds = int(float(value))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"


if __name__ == "__main__":
    raise SystemExit(main())
