"""Loopback-only Market History service backed by an admitted Lite replica."""

from __future__ import annotations

import json
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .replica_lite import (
    FragarachLiteError,
    LitePaths,
    _atomic_json,
    _read_json,
    lane_catalogue,
    lite_status,
    control_lane_request,
    market_history,
    pull_control,
    report_status,
    request_lane,
    sync_selective,
    utc_now,
)


DEFAULT_LITE_PORT = 9463
SERVICE_CONTRACT = "fragarach_lite.market_history_service.v1"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _handler(paths: LitePaths, wake_sync: threading.Event | None = None):
    request_lock = threading.Lock()

    class LiteHandler(BaseHTTPRequestHandler):
        server_version = "FragarachLite/1"

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

        def _json(self, status: HTTPStatus, payload: object) -> None:
            body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                status = lite_status(paths)
                self._json(
                    HTTPStatus.OK,
                    {
                        "contract": SERVICE_CONTRACT,
                        "state": status["state"],
                        "active_replica": status["active_replica"],
                        "generated_at_utc": utc_now(),
                    },
                )
                return
            if parsed.path == "/v1/replica/status":
                self._json(HTTPStatus.OK, lite_status(paths))
                return
            if parsed.path == "/v1/catalogue":
                self._json(HTTPStatus.OK, lane_catalogue(paths))
                return
            if parsed.path != "/v1/market-history":
                self._json(HTTPStatus.NOT_FOUND, {"code": "NOT_FOUND"})
                return
            query = parse_qs(parsed.query)
            required = ("symbol", "timeframe", "start_utc", "end_utc_exclusive", "as_of_utc")
            missing = [name for name in required if not (query.get(name) or [""])[0]]
            if missing:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"code": "MISSING_QUERY_PARAMETER", "parameters": missing},
                )
                return
            try:
                result = market_history(
                    paths,
                    symbol=query["symbol"][0],
                    timeframe=query["timeframe"][0],
                    start_utc=query["start_utc"][0],
                    end_utc_exclusive=query["end_utc_exclusive"][0],
                    as_of_utc=query["as_of_utc"][0],
                )
            except FragarachLiteError as error:
                self._json(HTTPStatus.BAD_REQUEST, {"code": error.code, "error": str(error)})
                return
            self._json(HTTPStatus.OK, result)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path not in {"/v1/request-lane", "/v1/request-action"}:
                self._json(HTTPStatus.NOT_FOUND, {"code": "NOT_FOUND"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                with request_lock:
                    if parsed.path == "/v1/request-lane":
                        requests = request_lane(
                            paths, symbol=str(payload["symbol"]), timeframe=str(payload["timeframe"])
                        )
                        response_state = "REQUESTED"
                    else:
                        updated = control_lane_request(
                            paths, symbol=str(payload["symbol"]), timeframe=str(payload["timeframe"]),
                            action=str(payload["action"])
                        )
                        requests = _read_json(paths.requests, [])
                        response_state = str(updated["state"])
            except (ValueError, KeyError, TypeError, FragarachLiteError) as error:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"code": getattr(error, "code", "INVALID_REQUEST"), "error": str(error)},
                )
                return
            if wake_sync is not None:
                wake_sync.set()
            self._json(
                HTTPStatus.OK,
                {"state": response_state, "requests": requests, "report_warning": None},
            )

    return LiteHandler


def serve(
    paths: LitePaths,
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_LITE_PORT,
    sync_interval: float = 300.0,
    allow_unsigned: bool = False,
) -> None:
    if host not in LOOPBACK_HOSTS:
        raise FragarachLiteError(
            "NON_LOOPBACK_BIND_FORBIDDEN",
            "Fragarach Lite may only serve engines on the local Mac",
        )
    paths.prepare()
    stopped = threading.Event()
    wake_sync = threading.Event()
    server = ThreadingHTTPServer((host, port), _handler(paths, wake_sync))
    actual_port = int(server.server_address[1])
    status_lock = threading.Lock()
    previous_status = _read_json(paths.service_status, {})
    status_value = previous_status if isinstance(previous_status, dict) else {}

    def write_status(**updates: object) -> None:
        with status_lock:
            status_value.update(
                {
                    "contract": SERVICE_CONTRACT,
                    "state": "RUNNING",
                    "host": host,
                    "port": actual_port,
                    "pid": os.getpid(),
                    **updates,
                }
            )
            _atomic_json(paths.service_status, status_value)

    def synchronise() -> None:
        next_sync = 0.0
        while not stopped.is_set():
            try:
                control = pull_control(paths)
                refresh_generation = int(control.get("refresh_generation") or 0)
                received_generation = int(status_value.get("refresh_generation_received") or 0)
                completed_generation = int(status_value.get("refresh_generation_completed") or 0)
                refresh_requested = refresh_generation > completed_generation
                if refresh_generation > received_generation:
                    write_status(
                        sync_phase="RECEIVED",
                        refresh_generation_received=refresh_generation,
                    )
                    report_status(paths)
                if control.get("sync_paused"):
                    write_status(
                        sync_phase="PAUSED",
                        last_sync_outcome="PAUSED",
                        last_sync_error=None,
                    )
                elif refresh_requested or time.monotonic() >= next_sync:
                    write_status(
                        sync_phase="SYNCHRONISING",
                        sync_started_at_utc=utc_now(),
                        refresh_generation_received=refresh_generation,
                    )
                    report_status(paths)
                    selective_result = sync_selective(paths, allow_unsigned=allow_unsigned)
                    outcome = "SELECTIVE_ADMITTED" if selective_result["admitted"] else "ALREADY_CURRENT"
                    write_status(
                        sync_phase="COMPLETED",
                        last_sync_at_utc=utc_now(),
                        last_sync_outcome=outcome,
                        last_sync_error=None,
                        refresh_generation_completed=refresh_generation,
                    )
                    next_sync = time.monotonic() + max(sync_interval, 1.0)
                report_status(paths)
            except FragarachLiteError as error:
                write_status(
                    sync_phase="FAILED",
                    last_sync_at_utc=utc_now(),
                    last_sync_outcome="FAILED",
                    last_sync_error={"code": error.code, "error": str(error)},
                )
            if sync_interval <= 0:
                return
            woken = wake_sync.wait(min(sync_interval, 15.0))
            wake_sync.clear()
            if stopped.is_set():
                return
            if woken:
                next_sync = 0.0

    write_status(
        started_at_utc=utc_now(),
        sync_phase="IDLE",
        refresh_generation_received=int(status_value.get("refresh_generation_received") or 0),
        refresh_generation_completed=int(status_value.get("refresh_generation_completed") or 0),
    )
    worker = threading.Thread(target=synchronise, name="fragarach-lite-sync", daemon=True)
    worker.start()
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        stopped.set()
        wake_sync.set()
        server.server_close()
        worker.join(timeout=2)
        _atomic_json(
            paths.service_status,
            {
                "contract": SERVICE_CONTRACT,
                "state": "STOPPED",
                "host": host,
                "port": actual_port,
                "pid": os.getpid(),
                "stopped_at_utc": utc_now(),
            },
        )
