"""Run the loopback-only Fragarach replica publication service."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from fragarach_ii.replica_publication import DEFAULT_PUBLISHER_PORT, ReplicaControlError, ReplicaPaths
from fragarach_ii.replica_publisher_service import serve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--support")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PUBLISHER_PORT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        serve(
            ReplicaPaths.for_database(arguments.database, support=arguments.support),
            host=arguments.host,
            port=arguments.port,
        )
    except (ReplicaControlError, FileNotFoundError, OSError) as error:
        print(
            json.dumps(
                {"code": getattr(error, "code", "REPLICA_PUBLISHER_FAILED"), "error": str(error)},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
