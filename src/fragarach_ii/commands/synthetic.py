"""Manage and consume the dedicated Synthetic Repository."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from fragarach_ii.synthetic_repository import (
    SyntheticConsumerService,
    SyntheticRepository,
    SyntheticRepositoryError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--repository")
    parser.add_argument("--registry")
    parser.add_argument("--mode", choices=("list", "generate", "rebuild", "consume"), default="list")
    parser.add_argument("--registration-id")
    parser.add_argument("--symbol")
    parser.add_argument("--timeframe")
    parser.add_argument("--consumer")
    parser.add_argument("--evidence-requirement", choices=("REAL_ONLY", "SYNTHETIC_PERMITTED"), default="REAL_ONLY")
    parser.add_argument("--json", action="store_true", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    repository = SyntheticRepository(
        arguments.database, arguments.repository, arguments.registry
    )
    try:
        if arguments.mode == "list":
            repository.activate_registry()
            products = repository.list_products()
            payload = {
                "contract": "fragarach_ii.synthetic_monitor.v1",
                "repository": str(repository.path),
                "products": products,
                "summary": {
                    "total": len(products),
                    **{status.lower(): sum(item["status"] == status for item in products) for status in ("Available", "Stale", "Incomplete", "Unavailable")},
                },
            }
        elif arguments.mode == "generate":
            repository.activate_registry(generate_on_activation=False)
            payload = repository.generate(arguments.registration_id) if arguments.registration_id else repository.generate_all()
        elif arguments.mode == "rebuild":
            payload = repository.rebuild()
        else:
            if not all((arguments.symbol, arguments.timeframe, arguments.consumer)):
                raise SyntheticRepositoryError("INVALID_REQUEST", "symbol, timeframe, and consumer are required")
            payload = SyntheticConsumerService(repository).get_product(
                symbol=arguments.symbol, timeframe=arguments.timeframe,
                consumer=arguments.consumer,
                evidence_requirement=arguments.evidence_requirement,
            )
    except SyntheticRepositoryError as error:
        payload = {"status": error.code, "reason": str(error)}
        code = 2
    else:
        code = 0
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
