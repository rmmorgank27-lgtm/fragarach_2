"""Audit chartability of every commissioned crypto H1 and M5 lane."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from fragarach_ii.crypto_intraday_quality import audit_crypto_intraday_quality


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--window", type=int, default=270)
    arguments = parser.parse_args(argv)
    result = audit_crypto_intraday_quality(arguments.database, window=arguments.window)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 1 if result["status_counts"].get("UNUSABLE", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
