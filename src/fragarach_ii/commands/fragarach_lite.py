"""Configure, synchronise, inspect, and serve Fragarach Lite."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from fragarach_ii.replica_lite import (
    FragarachLiteError, LitePaths, configure_lite, lite_status, market_history,
    clear_lane_request, request_lane, store_client_token, sync_lite, sync_selective,
)
from fragarach_ii.replica_lite_daemon import (
    LiteLifecyclePaths, install_lite_service, lite_service_status, start_lite_service,
    stop_lite_service, uninstall_lite_service,
)
from fragarach_ii.replica_lite_service import DEFAULT_LITE_PORT, serve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    configure = commands.add_parser("configure")
    configure.add_argument("--endpoint", required=True)
    configure.add_argument("--client-id", required=True)
    commands.add_parser("store-token", help="read the one-time token from standard input")
    sync = commands.add_parser("sync")
    sync.add_argument("--allow-unsigned", action="store_true")
    sync.add_argument("--allow-insecure-transport", action="store_true")
    selective = commands.add_parser("sync-selective")
    selective.add_argument("--allow-unsigned", action="store_true")
    selective.add_argument("--allow-insecure-transport", action="store_true")
    history = commands.add_parser("history")
    history.add_argument("--symbol", required=True)
    history.add_argument("--timeframe", required=True)
    history.add_argument("--start-utc", required=True)
    history.add_argument("--end-utc-exclusive", required=True)
    history.add_argument("--as-of-utc", required=True)
    service = commands.add_parser("serve")
    service.add_argument("--host", default="127.0.0.1")
    service.add_argument("--port", type=int, default=DEFAULT_LITE_PORT)
    service.add_argument("--sync-interval", type=float, default=300.0)
    service.add_argument("--allow-unsigned", action="store_true")
    commands.add_parser("service-status")
    install = commands.add_parser("service-install")
    install.add_argument("--python", required=True)
    install.add_argument("--repository", required=True)
    install.add_argument("--port", type=int, default=DEFAULT_LITE_PORT)
    install.add_argument("--sync-interval", type=int, default=300)
    install.add_argument("--allow-unsigned", action="store_true")
    commands.add_parser("service-start")
    commands.add_parser("service-stop")
    commands.add_parser("service-uninstall")
    request = commands.add_parser("request-lane")
    request.add_argument("--symbol", required=True)
    request.add_argument("--timeframe", required=True)
    clear = commands.add_parser("clear-lane-request")
    clear.add_argument("--symbol", required=True)
    clear.add_argument("--timeframe", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    paths = LitePaths.create(arguments.root)
    lifecycle = LiteLifecyclePaths.create(paths)
    try:
        if arguments.command == "status":
            result = lite_status(paths)
        elif arguments.command == "configure":
            result = configure_lite(paths, endpoint=arguments.endpoint, client_id=arguments.client_id)
        elif arguments.command == "store-token":
            store_client_token(paths, sys.stdin.readline())
            result = {"stored": True, "path": str(paths.token)}
        elif arguments.command == "sync":
            result = sync_lite(paths, allow_unsigned=arguments.allow_unsigned,
                               allow_insecure_transport=arguments.allow_insecure_transport)
        elif arguments.command == "sync-selective":
            result = sync_selective(paths, allow_unsigned=arguments.allow_unsigned,
                                    allow_insecure_transport=arguments.allow_insecure_transport)
        elif arguments.command == "history":
            result = market_history(
                paths, symbol=arguments.symbol, timeframe=arguments.timeframe,
                start_utc=arguments.start_utc,
                end_utc_exclusive=arguments.end_utc_exclusive, as_of_utc=arguments.as_of_utc,
            )
        elif arguments.command == "serve":
            serve(paths, host=arguments.host, port=arguments.port,
                  sync_interval=arguments.sync_interval, allow_unsigned=arguments.allow_unsigned)
            return 0
        elif arguments.command == "service-status":
            result = lite_service_status(lifecycle)
        elif arguments.command == "service-install":
            result = install_lite_service(
                lifecycle, python=arguments.python, repository=arguments.repository,
                port=arguments.port, sync_interval=arguments.sync_interval,
                allow_unsigned=arguments.allow_unsigned,
            )
        elif arguments.command == "service-start":
            result = start_lite_service(lifecycle)
        elif arguments.command == "service-stop":
            result = stop_lite_service(lifecycle)
        elif arguments.command == "request-lane":
            result = {"requests": request_lane(paths, symbol=arguments.symbol, timeframe=arguments.timeframe)}
        elif arguments.command == "clear-lane-request":
            result = {"requests": clear_lane_request(paths, symbol=arguments.symbol, timeframe=arguments.timeframe)}
        else:
            result = uninstall_lite_service(lifecycle)
    except (FragarachLiteError, OSError) as error:
        print(json.dumps(
            {"code": getattr(error, "code", "FRAGARACH_LITE_FAILED"), "error": str(error)},
            sort_keys=True, separators=(",", ":"),
        ), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
