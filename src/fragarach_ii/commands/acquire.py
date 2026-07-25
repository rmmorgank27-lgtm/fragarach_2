"""Run one explicit bounded provider acquisition operation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from fragarach_ii.providers import AcquisitionError
from fragarach_ii.providers.config import load_provider_config
from fragarach_ii.scheduler_daemon import ServicePaths, make_command, ownership_is_active, send_service_request
from fragarach_ii.scheduler_service import run_operator_fetch, resume_required_set_fetch, run_required_set_fetch
from fragarach_ii.credentials import CredentialAuthority

def _emit_progress(stage: str, **facts: object) -> None:
    payload = {"fragarach_operation_stage": stage, **facts}
    print(json.dumps(payload, separators=(",", ":")), file=sys.stderr, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--provider", choices=("AUTO", "TWELVE_DATA"), default="AUTO")
    parser.add_argument("--asset", required=True)
    parser.add_argument("--timeframe")
    parser.add_argument("--from-date")
    parser.add_argument("--through-date")
    parser.add_argument("--required-set", action="store_true")
    parser.add_argument("--resume-required-set", action="store_true")
    parser.add_argument("--conflict-mode", choices=("preserve", "correct"), default="preserve")
    parser.add_argument("--intent", choices=("initial", "update", "force", "custom"), default="custom")
    parser.add_argument("--operator-reason", default="OPERATOR_FETCH")
    parser.add_argument("--reviewed-historical-range", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.resume_required_set:
        arguments.required_set = True
    if not arguments.required_set and (
        not arguments.timeframe or not arguments.from_date or not arguments.through_date
    ):
        raise SystemExit("--timeframe, --from-date, and --through-date are required unless --required-set is used")
    config = (
        None if arguments.required_set
        else load_provider_config(timeframe=arguments.timeframe)
    )
    credential = CredentialAuthority().credential_for(
        "TWELVE_DATA" if arguments.required_set else config.provider_id
    )
    progress = _emit_progress if os.environ.get("FRAGARACH_OPERATION_PROGRESS") == "1" else None
    try:
        if arguments.provider=="TWELVE_DATA" and not credential:
            raise AcquisitionError("MISSING_CREDENTIAL","required provider credential is absent")
        paths = ServicePaths.create(arguments.database)
        if ownership_is_active(paths):
            if arguments.required_set:
                response = send_service_request(paths, make_command("OPERATOR_FETCH_REQUIRED_SET", payload={
                    "symbol": arguments.asset,
                    "merge_mode": arguments.conflict_mode,
                    "operator_reason": "RESUME_REQUIRED_TIMEFRAME_SET" if arguments.resume_required_set else arguments.operator_reason,
                }), timeout=900)
            else:
                response = send_service_request(paths, make_command("OPERATOR_FETCH", payload={
                    "symbol": arguments.asset,
                    "timeframe": arguments.timeframe,
                    "requested_start": arguments.from_date,
                    "requested_end": arguments.through_date,
                    "merge_mode": arguments.conflict_mode,
                    "requested_mode": arguments.intent,
                    "reviewed_historical_range": arguments.reviewed_historical_range or arguments.intent in {"initial", "force", "custom"},
                    "operator_reason": arguments.operator_reason,
                }), timeout=300)
            if response.get("result") not in {"accepted", "already applied"}:
                raise ValueError(str(response.get("reason") or "Scheduler Service rejected Operator Fetch"))
            result = response.get("detail") or response
        elif os.environ.get("FRAGARACH_STANDALONE_RECOVERY") != "1":
            raise ValueError("SCHEDULER_SERVICE_NOT_RUNNING")
        elif arguments.required_set:
            runner = resume_required_set_fetch if arguments.resume_required_set else run_required_set_fetch
            result = runner(
                arguments.database,
                symbol=arguments.asset,
                merge_mode=arguments.conflict_mode,
                credential=credential,
                operator_reason=arguments.operator_reason,
                progress=progress,
            )
        else:
            result = run_operator_fetch(
                arguments.database,
                symbol=arguments.asset,
                timeframe=arguments.timeframe,
                requested_start=arguments.from_date,
                requested_end=arguments.through_date,
                merge_mode=arguments.conflict_mode,
                credential=credential,
                requested_mode=arguments.intent,
                reviewed_historical_range=arguments.reviewed_historical_range or arguments.intent in {"initial", "force", "custom"},
                operator_reason=arguments.operator_reason,
                progress=progress,
            )
    except (AcquisitionError, ValueError) as error:
        payload = {
            "code": getattr(error, "code", "INVALID_ACQUISITION_REQUEST"),
            "error": str(error),
            "evidence_committed": getattr(error, "evidence_committed", False),
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
