"""Command-line entry point for one manual CSV ingestion attempt."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from fragarach_ii.ingestion.manual import IngestionFailure, ingest_manual_file


def _emit_progress(stage: str) -> None:
    print(json.dumps({"fragarach_operation_stage": stage}, separators=(",", ":")), file=sys.stderr, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--symbol")
    parser.add_argument("--timeframe")
    parser.add_argument("--provider", default="MANUAL")
    parser.add_argument("--source-timezone")
    parser.add_argument(
        "--d1-date-format",
        choices=("auto", "day-first", "month-first"),
        default="auto",
        help="calendar order for slash-formatted daily dates; never applies a timezone",
    )
    parser.add_argument("--merge-mode", choices=("preserve", "correct"), default="preserve")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    progress = _emit_progress if os.environ.get("FRAGARACH_OPERATION_PROGRESS") == "1" else None
    try:
        result = ingest_manual_file(
            arguments.database,
            arguments.file,
            symbol=arguments.symbol,
            timeframe=arguments.timeframe,
            provider=arguments.provider,
            source_timezone=arguments.source_timezone,
            d1_date_format=arguments.d1_date_format,
            merge_mode=arguments.merge_mode,
            progress=progress,
        )
    except IngestionFailure as error:
        payload = {
            "checksum": error.checksum,
            "error": str(error.cause),
            "ingest_run_id": error.ingest_run_id,
            "raw_block_id": error.raw_block_id,
            "transaction_state": "failed",
        }
        if arguments.json_output:
            print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        else:
            for key in sorted(payload):
                print(f"{key}: {payload[key]}")
        return 1

    if arguments.json_output:
        print(result.as_json())
    else:
        for key, value in result.as_dict().items():
            print(f"{key}: {value}")
    return 0 if result.transaction_state in {"committed","COMPLETED_WITH_WARNINGS"} else 2


if __name__ == "__main__":
    sys.exit(main())
