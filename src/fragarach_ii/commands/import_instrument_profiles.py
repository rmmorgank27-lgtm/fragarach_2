"""Import reviewed instrument-profile events one at a time into authority."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.storage import (
    InstrumentProfileError,
    InstrumentProfileEventCandidate,
    initialize_database,
    record_instrument_profile_event,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument(
        "--catalogue",
        default="config/instrument_profiles/events.v1.json",
    )
    parser.add_argument("--symbol", help="Import only one canonical symbol")
    arguments = parser.parse_args(argv)
    try:
        payload = json.loads(Path(arguments.catalogue).read_text(encoding="utf-8"))
        if payload.get("contract") != "fragarach.instrument_profile_event_catalogue.v1":
            raise ValueError("invalid instrument-profile event catalogue contract")
        initialize_database(arguments.database)
        recorded = datetime.now(UTC).isoformat()
        results = []
        for value in payload.get("events") or []:
            if arguments.symbol and value.get("asset") != arguments.symbol.upper():
                continue
            results.append(record_instrument_profile_event(
                arguments.database,
                InstrumentProfileEventCandidate(**value),
                recorded_at_utc=recorded,
            ))
        if arguments.symbol and not results:
            raise ValueError(f"no reviewed profile events for {arguments.symbol.upper()}")
        print(json.dumps({"contract": "fragarach.instrument_profile_import.v1",
                          "imported": len(results), "events": results},
                         sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ValueError, TypeError, sqlite3.Error, InstrumentProfileError) as error:
        print(json.dumps({"code": getattr(error, "code", "PROFILE_IMPORT_FAILED"),
                          "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    sys.exit(main())
