"""Publish the SPEC-040 Lane Freshness operational monitor."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

from fragarach_ii.lane_freshness_service import (
    lane_freshness_report,
    render_lane_freshness_markdown,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output")
    arguments = parser.parse_args(argv)
    try:
        report = lane_freshness_report(
            Path(arguments.database).expanduser().resolve()
        )
        rendered = (
            json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
            if arguments.format == "json"
            else render_lane_freshness_markdown(report)
        )
        if arguments.output:
            output = Path(arguments.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
    except (FileNotFoundError, RuntimeError, sqlite3.Error, ValueError) as error:
        print(
            json.dumps(
                {"code": "LANE_FRESHNESS_REPORT_FAILED", "error": str(error)},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
