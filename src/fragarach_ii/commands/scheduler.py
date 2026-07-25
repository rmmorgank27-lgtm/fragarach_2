"""Run or inspect the Fragarach II scheduled-acquisition service."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import uuid
from pathlib import Path
from collections.abc import Sequence

from fragarach_ii.credentials import CredentialAuthority, resolve_scheduler_credential
from fragarach_ii.scheduler_daemon import (
    COMMAND_CONTRACT,
    AcquisitionOwnership,
    PersistentSchedulerRuntime,
    ServicePaths,
    install_service,
    cancel_service_mutation,
    force_reconcile_service_state,
    manage_service_lifecycle,
    make_command,
    ownership_is_active,
    repair_service,
    repair_monitor_transport,
    reconcile_service_mutation,
    record_restart,
    send_service_request,
    service_action,
    service_status,
    service_diagnostics,
)
from fragarach_ii.scheduler_service import (
    SchedulerService,
    pause_acquisition,
    request_retry,
    request_run_queue,
    resume_acquisition,
    audit_estate,
    scheduler_snapshot,
    update_manual_request,
    update_queue_bandwidth,
    update_scheduler_policy,
    update_freshness_override,
    run_operator_fetch,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument(
        "--mode",
        choices=(
            "run", "status", "service-run", "service-status", "send-command",
            "install", "enable", "disable", "start", "stop", "restart", "update", "repair", "uninstall",
            "force-reconcile", "repair-monitor", "diagnostics", "cancel-operation", "reconcile-mutation",
            "manual-request", "run-queue", "retry", "fetch", "m5-freshness", "scheduler-policy", "queue-bandwidth", "pause", "resume", "audit-estate",
        ),
        default="run",
    )
    parser.add_argument("--journal")
    parser.add_argument("--support-dir")
    parser.add_argument("--repository", default=str(Path.cwd()))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--app-build", default="Development")
    parser.add_argument("--app-instance")
    parser.add_argument("--operation-id")
    parser.add_argument("--target-generation")
    parser.add_argument("--command-id")
    parser.add_argument("--command-type")
    parser.add_argument("--payload", default="{}")
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--recovery", action="store_true")
    parser.add_argument("--monitor-only", action="store_true")
    parser.add_argument("--request-id")
    parser.add_argument("--action", choices=("acknowledge", "dismiss"))
    parser.add_argument("--lane-id")
    parser.add_argument("--percentage", type=int)
    parser.add_argument("--policy", choices=("CONSERVATIVE", "BALANCED", "HIGH_THROUGHPUT", "MAXIMUM_CATCH_UP"))
    parser.add_argument("--publication-delay-seconds", type=int)
    parser.add_argument("--critical-after-closed-boundaries", type=int)
    parser.add_argument("--scope-type", choices=("ALL", "MARKET_OR_GROUP", "SYMBOL"))
    parser.add_argument("--scope-identifier")
    parser.add_argument("--reason", choices=("MANUAL_INGESTION", "OPERATOR_MAINTENANCE", "PROVIDER_CONFIGURATION", "ESTATE_REPAIR", "OTHER_OPERATOR_REASON"))
    parser.add_argument("--temporary", action="store_true")
    parser.add_argument("--ingestion-session")
    parser.add_argument("--pause-identifier")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    paths = ServicePaths.create(
        arguments.database, journal=arguments.journal, support=arguments.support_dir
    )
    authority_credential = CredentialAuthority().credential_for("TWELVE_DATA")
    if arguments.mode == "service-run":
        credential, _source = resolve_scheduler_credential()
        runtime = PersistentSchedulerRuntime(
            paths, credential=credential, monitor_only=arguments.monitor_only,
            credential_provider=lambda: CredentialAuthority().credential_for("TWELVE_DATA"),
        )
        signal.signal(signal.SIGTERM, lambda *_: runtime.scheduler.stop())
        signal.signal(signal.SIGINT, lambda *_: runtime.scheduler.stop())
        if hasattr(signal, "SIGUSR1"):
            signal.signal(signal.SIGUSR1, lambda *_: runtime.scheduler.wake())
        if hasattr(signal, "SIGUSR2"):
            signal.signal(signal.SIGUSR2, lambda *_: runtime.request_monitor_repair())
        try:
            runtime.run()
            return 0
        except RuntimeError as error:
            if str(error) == "SERVICE_OWNS_ACQUISITION":
                print("SERVICE_OWNS_ACQUISITION", file=sys.stderr)
                return 0
            primary_error = error
        except BaseException as error:
            primary_error = error
        print(f"SCHEDULER_SERVICE_FAILURE: {type(primary_error).__name__}: {primary_error}", file=sys.stderr)
        try:
            recovery = record_restart(paths, f"{type(primary_error).__name__}: {primary_error}")
        except BaseException as recording_error:
            print(
                f"SCHEDULER_RESTART_RECORDING_FAILURE: {type(recording_error).__name__}: {recording_error}",
                file=sys.stderr,
            )
            return 1
        if recovery["service_state"] == "CRASH_LOOP_PROTECTED":
            return 0
        time.sleep(min(2 ** int(recovery["restart_count"]), 30))
        return 1
    if arguments.mode == "service-status":
        print(json.dumps(service_status(paths, app_build=arguments.app_build), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode in {"install", "enable", "disable", "start", "stop", "restart", "update", "repair", "uninstall"}:
        print(json.dumps(manage_service_lifecycle(
            paths, arguments.mode.upper(), python=arguments.python,
            repository=arguments.repository, app_build=arguments.app_build,
            app_instance=arguments.app_instance,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "force-reconcile":
        print(json.dumps(force_reconcile_service_state(
            paths, app_build=arguments.app_build, app_instance=arguments.app_instance,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "repair-monitor":
        print(json.dumps(repair_monitor_transport(paths), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "diagnostics":
        print(json.dumps(service_diagnostics(paths, app_build=arguments.app_build), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "cancel-operation":
        print(json.dumps(cancel_service_mutation(paths, arguments.operation_id), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "reconcile-mutation":
        print(json.dumps(reconcile_service_mutation(paths), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "send-command":
        if not arguments.command_type:
            raise SystemExit("--command-type is required for send-command mode")
        try:
            payload = json.loads(arguments.payload)
        except ValueError as error:
            raise SystemExit("--payload must be a JSON object") from error
        request = make_command(
            arguments.command_type,
            app_build=arguments.app_build,
            target_generation=arguments.target_generation,
            payload=payload,
            command_identifier=arguments.command_id,
        )
        print(json.dumps(send_service_request(paths, request), sort_keys=True, separators=(",", ":")))
        return 0

    # Existing native controls now become versioned service commands whenever a
    # persistent owner is active. This preserves their CLI spelling while
    # preventing direct journal competition.
    command = _legacy_service_command(arguments)
    if command is not None and ownership_is_active(paths):
        print(json.dumps(send_service_request(paths, command), sort_keys=True, separators=(",", ":")))
        return 0
    if command is not None and not (arguments.development or arguments.recovery):
        print(json.dumps({
            "contract": COMMAND_CONTRACT,
            "result": "rejected",
            "reason": "SCHEDULER_SERVICE_NOT_RUNNING",
        }, sort_keys=True, separators=(",", ":")))
        return 2
    if arguments.mode == "pause":
        if not arguments.scope_type:
            raise SystemExit("--scope-type is required for pause mode")
        print(json.dumps(pause_acquisition(
            arguments.database, scope_type=arguments.scope_type,
            scope_identifier=arguments.scope_identifier,
            reason=arguments.reason or "OPERATOR_MAINTENANCE",
            temporary=arguments.temporary,
            related_ingestion_session=arguments.ingestion_session,
            journal_path=arguments.journal,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "resume":
        print(json.dumps(resume_acquisition(
            arguments.database, pause_identifier=arguments.pause_identifier,
            scope_type=arguments.scope_type, scope_identifier=arguments.scope_identifier,
            related_ingestion_session=arguments.ingestion_session,
            journal_path=arguments.journal,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "audit-estate":
        print(json.dumps(audit_estate(arguments.database), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "run-queue":
        print(json.dumps(request_run_queue(
            arguments.database, journal_path=arguments.journal,
            credential=authority_credential,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "fetch":
        if not arguments.lane_id or ":" not in arguments.lane_id:
            raise SystemExit("--lane-id SYMBOL:TIMEFRAME is required for fetch mode")
        symbol, timeframe = arguments.lane_id.rsplit(":", 1)
        print(json.dumps(run_operator_fetch(
            arguments.database, symbol=symbol, timeframe=timeframe,
            credential=authority_credential, requested_mode="update",
            operator_reason="ESTATE_M5_REFRESH", journal_path=arguments.journal,
            defer_dispatch=True,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "m5-freshness":
        if arguments.publication_delay_seconds is None or arguments.critical_after_closed_boundaries is None:
            raise SystemExit("--publication-delay-seconds and --critical-after-closed-boundaries are required")
        print(json.dumps(update_freshness_override(
            arguments.database, timeframe="M5",
            publication_delay_seconds=arguments.publication_delay_seconds,
            critical_after_closed_boundaries=arguments.critical_after_closed_boundaries,
            journal_path=arguments.journal,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "retry":
        print(json.dumps(request_retry(
            arguments.database, lane_id=arguments.lane_id,
            request_id=arguments.request_id, journal_path=arguments.journal,
            credential=authority_credential,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "queue-bandwidth":
        if arguments.percentage is None:
            raise SystemExit("--percentage is required for queue-bandwidth mode")
        print(json.dumps(update_queue_bandwidth(
            arguments.database, arguments.percentage, journal_path=arguments.journal,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "scheduler-policy":
        if arguments.policy is None:
            raise SystemExit("--policy is required for scheduler-policy mode")
        print(json.dumps(update_scheduler_policy(
            arguments.database, arguments.policy, journal_path=arguments.journal,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "manual-request":
        if not arguments.request_id or not arguments.action:
            raise SystemExit("--request-id and --action are required for manual-request mode")
        print(json.dumps(update_manual_request(
            arguments.database, request_id=arguments.request_id,
            action=arguments.action, journal_path=arguments.journal,
        ), sort_keys=True, separators=(",", ":")))
        return 0
    if arguments.mode == "status":
        if ownership_is_active(paths):
            print(json.dumps(service_status(paths, app_build=arguments.app_build), sort_keys=True, separators=(",", ":")))
            return 0
        print(
            json.dumps(
                scheduler_snapshot(
                    arguments.database, journal_path=arguments.journal,
                    credential=authority_credential,
                ),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    if not (arguments.development or arguments.recovery):
        print(json.dumps({"outcome": "SERVICE_OWNS_ACQUISITION", "reason": "Standalone Scheduler execution requires --development or --recovery"}, sort_keys=True, separators=(",", ":")))
        return 2
    if ownership_is_active(paths):
        print(json.dumps({"outcome": "SERVICE_OWNS_ACQUISITION"}, sort_keys=True, separators=(",", ":")))
        return 2
    service = SchedulerService(
        arguments.database,
        credential=authority_credential,
        journal_path=arguments.journal,
    )
    signal.signal(signal.SIGTERM, lambda *_: service.stop())
    signal.signal(signal.SIGINT, lambda *_: service.stop())
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, lambda *_: service.wake())
    runner = service.run_monitor_only if os.environ.get("FRAGARACH_SCHEDULER_MONITOR_ONLY") == "1" else service.run_forever
    owner = AcquisitionOwnership(paths, instance=f"standalone-{uuid.uuid4()}", generation=str(uuid.uuid4()))
    with owner:
        runner(
            lambda snapshot: print(
                json.dumps(snapshot, sort_keys=True, separators=(",", ":")),
                flush=True,
            )
        )
    return 0


def _legacy_service_command(arguments: argparse.Namespace) -> dict[str, object] | None:
    payload: dict[str, object] = {}
    scope: dict[str, object] = {}
    command_type: str | None = None
    if arguments.mode == "pause":
        command_type = "PAUSE"
        scope = {"scope_type": arguments.scope_type, "scope_identifier": arguments.scope_identifier}
        payload = {"reason": arguments.reason or "OPERATOR_MAINTENANCE", "temporary": arguments.temporary, "ingestion_session": arguments.ingestion_session}
    elif arguments.mode == "resume":
        command_type = "RESUME"
        scope = {"scope_type": arguments.scope_type, "scope_identifier": arguments.scope_identifier}
        payload = {"pause_identifier": arguments.pause_identifier, "ingestion_session": arguments.ingestion_session}
    elif arguments.mode == "run-queue":
        command_type = "RUN_QUEUE_NOW"
    elif arguments.mode == "retry":
        command_type = "RETRY_NOW"
        payload = {"lane_id": arguments.lane_id, "request_id": arguments.request_id}
    elif arguments.mode == "fetch":
        if not arguments.lane_id or ":" not in arguments.lane_id:
            return None
        symbol, timeframe = arguments.lane_id.rsplit(":", 1)
        command_type = "OPERATOR_FETCH"
        payload = {"symbol": symbol, "timeframe": timeframe, "requested_mode": "update", "operator_reason": "ESTATE_M5_REFRESH"}
    elif arguments.mode == "m5-freshness":
        command_type = "M5_FRESHNESS"
        payload = {"publication_delay_seconds": arguments.publication_delay_seconds, "critical_after_closed_boundaries": arguments.critical_after_closed_boundaries}
    elif arguments.mode == "queue-bandwidth":
        command_type = "QUEUE_BANDWIDTH"
        payload = {"percentage": arguments.percentage}
    elif arguments.mode == "scheduler-policy":
        command_type = "SCHEDULER_POLICY"
        payload = {"policy": arguments.policy}
    elif arguments.mode == "manual-request":
        command_type = "MANUAL_REQUEST"
        payload = {"request_id": arguments.request_id, "action": arguments.action}
    if command_type is None:
        return None
    value = make_command(
        command_type,
        app_build=arguments.app_build,
        target_generation=arguments.target_generation,
        scope=scope,
        payload=payload,
        command_identifier=arguments.command_id,
    )
    return value


if __name__ == "__main__":
    sys.exit(main())
