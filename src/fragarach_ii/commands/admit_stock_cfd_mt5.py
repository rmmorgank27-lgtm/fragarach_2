"""Admit the reviewed XOM Global Prime MT5 stock-CFD overlay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fragarach_ii.external_consumer_service import canonical_database_path
from fragarach_ii.stock_cfd_mt5 import admit_xom_stock_cfd_overlay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=canonical_database_path())
    parser.add_argument("--bundle", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(
        admit_xom_stock_cfd_overlay(arguments.database, arguments.bundle),
        sort_keys=True, separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
