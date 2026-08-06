"""Manage read-only replica clients and immutable publications."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence

from fragarach_ii.replica_publication import (
    ReplicaControlError,
    ReplicaPaths,
    add_client,
    create_full_snapshot,
    registry_status,
    revoke_client,
    rotate_client_token,
    request_client_refresh,
    set_client_lane_paused,
    set_client_enabled,
    set_client_sync_paused,
    set_publisher_enabled,
)
from fragarach_ii.replica_publisher_daemon import (
    PublisherLifecyclePaths,
    install_publisher_service,
    publisher_service_status,
    start_publisher_service,
    stop_publisher_service,
    uninstall_publisher_service,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--support")
    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "status",
            "publisher-enable",
            "publisher-disable",
            "add",
            "enable",
            "disable",
            "revoke",
            "rotate-token",
            "pause-sync",
            "resume-sync",
            "refresh-client",
            "pause-lane",
            "resume-lane",
            "publish-snapshot",
            "service-install",
            "service-start",
            "service-stop",
            "service-uninstall",
        ),
    )
    parser.add_argument("--client-id")
    parser.add_argument("--display-name")
    parser.add_argument("--symbols", default="*")
    parser.add_argument("--timeframes", default="*")
    parser.add_argument("--symbol")
    parser.add_argument("--timeframe")
    parser.add_argument("--python")
    parser.add_argument("--repository")
    parser.add_argument("--json", action="store_true", required=True)
    return parser


def _required(value: str | None, name: str) -> str:
    if value is None:
        raise ReplicaControlError("INVALID_REQUEST", f"{name} is required")
    return value


def _scope(value: str) -> list[str]:
    return [item for item in value.split(",") if item.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    paths = ReplicaPaths.for_database(arguments.database, support=arguments.support)
    lifecycle = PublisherLifecyclePaths.create(paths)
    try:
        if arguments.mode == "status":
            payload = registry_status(paths)
            payload["service"] = publisher_service_status(lifecycle)
        elif arguments.mode == "publisher-enable":
            payload = set_publisher_enabled(paths, True)
        elif arguments.mode == "publisher-disable":
            payload = set_publisher_enabled(paths, False)
        elif arguments.mode == "add":
            payload = add_client(
                paths,
                client_id=_required(arguments.client_id, "client-id"),
                display_name=_required(arguments.display_name, "display-name"),
                symbols=_scope(arguments.symbols),
                timeframes=_scope(arguments.timeframes),
            )
        elif arguments.mode == "enable":
            payload = set_client_enabled(paths, _required(arguments.client_id, "client-id"), True)
        elif arguments.mode == "disable":
            payload = set_client_enabled(paths, _required(arguments.client_id, "client-id"), False)
        elif arguments.mode == "revoke":
            payload = revoke_client(paths, _required(arguments.client_id, "client-id"))
        elif arguments.mode == "rotate-token":
            payload = rotate_client_token(paths, _required(arguments.client_id, "client-id"))
        elif arguments.mode == "pause-sync":
            payload = set_client_sync_paused(paths, _required(arguments.client_id, "client-id"), True)
        elif arguments.mode == "resume-sync":
            payload = set_client_sync_paused(paths, _required(arguments.client_id, "client-id"), False)
        elif arguments.mode == "refresh-client":
            payload = request_client_refresh(paths, _required(arguments.client_id, "client-id"))
        elif arguments.mode in {"pause-lane", "resume-lane"}:
            payload = set_client_lane_paused(
                paths,
                _required(arguments.client_id, "client-id"),
                _required(arguments.symbol, "symbol"),
                _required(arguments.timeframe, "timeframe"),
                arguments.mode == "pause-lane",
            )
        elif arguments.mode == "publish-snapshot":
            payload = create_full_snapshot(
                paths,
                symbols=_scope(arguments.symbols),
                timeframes=_scope(arguments.timeframes),
            )
        elif arguments.mode == "service-install":
            payload = install_publisher_service(
                lifecycle,
                python=_required(arguments.python, "python"),
                repository=_required(arguments.repository, "repository"),
            )
        elif arguments.mode == "service-start":
            payload = start_publisher_service(lifecycle)
        elif arguments.mode == "service-stop":
            payload = stop_publisher_service(lifecycle)
        else:
            payload = uninstall_publisher_service(lifecycle)
    except (ReplicaControlError, FileNotFoundError, OSError, sqlite3.Error) as error:
        print(
            json.dumps(
                {
                    "code": getattr(error, "code", "READ_ONLY_CLIENT_CONTROL_FAILED"),
                    "error": str(error),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
