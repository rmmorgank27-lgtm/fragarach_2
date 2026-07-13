"""Run one explicit bounded provider acquisition operation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from fragarach_ii.providers import AcquisitionError
from fragarach_ii.providers.resolution import acquire_resolved
from fragarach_ii.providers.config import load_provider_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--provider", choices=("AUTO", "TWELVE_DATA"), default="AUTO")
    parser.add_argument("--asset", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--through-date", required=True)
    parser.add_argument("--conflict-mode", choices=("preserve", "correct"), default="preserve")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    config = load_provider_config(timeframe=arguments.timeframe)
    credential = os.environ.get(config.authentication_environment)
    try:
        if arguments.provider=="TWELVE_DATA" and not credential:
            raise AcquisitionError("MISSING_CREDENTIAL","required provider credential is absent")
        result = acquire_resolved(
            arguments.database,
            asset=arguments.asset,
            timeframe=arguments.timeframe,
            from_date=arguments.from_date,
            through_date=arguments.through_date,
            merge_mode=arguments.conflict_mode,
            credential=credential,
        )
    except AcquisitionError as error:
        payload = {
            "code": error.code,
            "error": str(error),
            "evidence_committed": error.evidence_committed,
        }
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 1
    if arguments.json_output:
        print(json.dumps(result,sort_keys=True,separators=(",", ":")))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
