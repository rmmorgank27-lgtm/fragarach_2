"""Bootstrap USOIL and UKOIL D1 from reviewed TradingView TVC exports."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from fragarach_ii.oil_history import bootstrap_tradingview_oil_history


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--usoil-file", required=True)
    parser.add_argument("--ukoil-file", required=True)
    parser.add_argument("--confirm-reviewed-correction", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    arguments = parser.parse_args(argv)
    if not arguments.confirm_reviewed_correction:
        parser.error("--confirm-reviewed-correction is required")
    try:
        result = bootstrap_tradingview_oil_history(
            arguments.database,
            usoil_file=arguments.usoil_file,
            ukoil_file=arguments.ukoil_file,
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"code": "OIL_BOOTSTRAP_FAILED", "error": str(error)}, sort_keys=True))
        return 1
    if arguments.json_output:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        for symbol, detail in result["results"].items():
            print(f"{symbol}: {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
