"""Admit reviewed Global Prime oil M5 and roll it into M15, H1, and D1."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from fragarach_ii.energy_mt5 import admit_energy_mt5


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--xtiusd-file", required=True)
    parser.add_argument("--xbrusd-file", required=True)
    parser.add_argument("--confirm-reviewed-primary", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    arguments = parser.parse_args(argv)
    if not arguments.confirm_reviewed_primary:
        parser.error("--confirm-reviewed-primary is required")
    try:
        result = admit_energy_mt5(
            arguments.database, usoil_file=arguments.xtiusd_file,
            ukoil_file=arguments.xbrusd_file,
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"code": "ENERGY_MT5_ADMISSION_FAILED", "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")) if arguments.json_output else result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
