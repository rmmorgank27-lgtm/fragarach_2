from __future__ import annotations

import argparse
import json

from fragarach_ii.scheduler_daemon import ServicePaths, make_command, send_service_request
from fragarach_ii.credentials import CredentialAuthority

from fragarach_ii.provider_facts import (
    ProviderFactsError,
    probe_twelve_data_capability,
    provider_facts_snapshot,
    record_material_decision,
    resolve_twelve_data_facts,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve and inspect Twelve Data provider facts.")
    parser.add_argument("--database", required=True)
    parser.add_argument("--mode", choices=("status", "resolve", "probe", "decision"), default="status")
    parser.add_argument("--symbol")
    parser.add_argument("--timeframe", choices=("M5", "M30", "H1", "D1"))
    parser.add_argument("--decision", choices=("APPROVE_EXACT", "APPROVE_ALIAS", "MARK_NOT_EQUIVALENT", "DEFER"))
    parser.add_argument("--candidate-symbol")
    parser.add_argument("--json", action="store_true", required=True)
    arguments = parser.parse_args(argv)
    credential = CredentialAuthority().credential_for("TWELVE_DATA")
    try:
        if arguments.mode == "resolve":
            result = resolve_twelve_data_facts(
                arguments.database, credential=credential,
                symbols=(arguments.symbol.upper(),) if arguments.symbol else None,
            )
        elif arguments.mode == "probe":
            if not arguments.symbol or not arguments.timeframe:
                raise SystemExit("--symbol and --timeframe are required for probe mode")
            result = probe_twelve_data_capability(
                arguments.database, canonical_symbol=arguments.symbol,
                timeframe=arguments.timeframe, credential=credential,
            )
        elif arguments.mode == "decision":
            if not arguments.symbol or not arguments.decision or not arguments.candidate_symbol:
                raise SystemExit("--symbol, --decision, and --candidate-symbol are required for decision mode")
            result = record_material_decision(
                arguments.database, canonical_symbol=arguments.symbol,
                decision=arguments.decision, candidate_symbol=arguments.candidate_symbol,
            )
        else:
            result = provider_facts_snapshot(arguments.database, credential=credential)
        if arguments.mode != "status":
            _notify_scheduler(arguments.database)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except ProviderFactsError as error:
        print(json.dumps({
            "contract": "fragarach_ii.provider_facts_error.v1",
            "outcome": error.code,
            "reason": str(error),
            "available_actions": ["Configure Twelve Data", "Retry Now"] if "CREDENTIAL" in error.code else ["Retry Now", "Review Candidates"],
        }, sort_keys=True, separators=(",", ":")))
        return 1


def _notify_scheduler(database: str) -> None:
    """Wake the persistent owner after a provider-authority commit."""

    paths = ServicePaths.create(database)
    if not paths.socket.exists():
        return
    try:
        send_service_request(paths, make_command("PROVIDER_FACT_REFRESH"), timeout=1.0)
    except (OSError, ValueError, TimeoutError):
        # The Scheduler also polls provider-fact revisions every five seconds.
        pass


if __name__ == "__main__":
    raise SystemExit(main())
