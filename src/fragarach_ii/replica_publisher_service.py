"""Localhost-only HTTP transport for verified read-only publications."""

from __future__ import annotations

import json
import os
import base64
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .replica_publication import (
    ReplicaControlError,
    ReplicaPaths,
    authenticate_client,
    client_allows_manifest,
    client_control,
    latest_manifest,
    list_publications,
    publication_manifest,
    publication_payload,
    registry_status,
    record_client_report,
    utc_now,
    _atomic_json,
)
from .selective_replication import (
    artifact_manifest,
    artifact_payload,
    recover_registry,
    registry_projection,
    submit_request,
    update_request,
)
from .market_discovery import discover_market
from .providers.instrument_search import candidate_from_dict
from .storage import RegistrationError
from .mt5_bridge_queue import (
    MT5BridgeQueueError,
    authorised_client_id as mt5_authorised_client_id,
    poll_request as poll_mt5_request,
    receive_response as receive_mt5_response,
)
from .mt5_catalogue import accept_catalogue as accept_mt5_catalogue
from .mt5_bridge_health import accept_health as accept_mt5_health
from .mt5_route_manifest import bridge_node
from .index_cfd_mt5 import IndexCFDAdmissionError


SERVICE_CONTRACT = "fragarach_ii.replica_publisher_service.v1"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _mt5_node_path(path: str) -> tuple[str, str] | None:
    parts = path.strip("/").split("/")
    if len(parts) < 5 or parts[:3] != ["v1", "mt5", "nodes"]:
        return None
    node_id = parts[3]
    return (node_id, "/".join(parts[4:])) if bridge_node(node_id) is not None else None


def _handler(paths: ReplicaPaths):
    class ReplicaPublisherHandler(BaseHTTPRequestHandler):
        server_version = "FragarachReplicaPublisher/1"

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            # Authorization values and request payloads must never reach stdout.
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

        def _client(self):
            value = self.headers.get("Authorization", "")
            if not value.startswith("Bearer "):
                return None
            return authenticate_client(paths, value[7:])

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                status = registry_status(paths)
                self._json(
                    HTTPStatus.OK,
                    {
                        "contract": SERVICE_CONTRACT,
                        "state": "READY" if status["publisher_enabled"] else "DISABLED",
                        "generated_at_utc": utc_now(),
                    },
                )
                return
            status = registry_status(paths)
            if not status["publisher_enabled"]:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"code": "PUBLISHER_DISABLED"})
                return
            client = self._client()
            if client is None:
                self._json(HTTPStatus.UNAUTHORIZED, {"code": "CLIENT_UNAUTHORISED"})
                return
            try:
                self._serve_authorised(parsed, client)
            except (ReplicaControlError, MT5BridgeQueueError) as error:
                self._json(HTTPStatus.CONFLICT, {"code": error.code, "error": str(error)})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            status = registry_status(paths)
            if not status["publisher_enabled"]:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"code": "PUBLISHER_DISABLED"})
                return
            client = self._client()
            if client is None:
                self._json(HTTPStatus.UNAUTHORIZED, {"code": "CLIENT_UNAUTHORISED"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                node_path = _mt5_node_path(parsed.path)
                maximum = 50_000_000 if (
                    parsed.path == "/v1/mt5/evidence/responses"
                    or (node_path is not None and node_path[1] == "evidence/responses")
                ) else 5_000_000
                if length < 2 or length > maximum:
                    raise ReplicaControlError("INVALID_CLIENT_REPORT", "report size is invalid")
                payload = json.loads(self.rfile.read(length))
                if parsed.path == "/v1/mt5/evidence/responses":
                    if client.get("client_id") != mt5_authorised_client_id():
                        self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                        return
                    result = receive_mt5_response(paths.support, payload)
                    # Transport remains non-authoritative, but a durable
                    # receipt must wake the sole canonical writer promptly.
                    # Otherwise the Scheduler can remain in an idle wait while
                    # the bridge inbox accumulates acknowledged responses.
                    from .commands.register_instrument import _notify_scheduler
                    _notify_scheduler(str(paths.database))
                elif node_path is not None and node_path[1] == "evidence/responses":
                    node_id = node_path[0]
                    if client.get("client_id") != mt5_authorised_client_id(node_id):
                        self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                        return
                    result = receive_mt5_response(paths.support, payload, node_id=node_id)
                    from .commands.register_instrument import _notify_scheduler
                    _notify_scheduler(str(paths.database))
                elif parsed.path == "/v1/mt5/catalogue":
                    if client.get("client_id") != mt5_authorised_client_id():
                        self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                        return
                    result = accept_mt5_catalogue(paths.support, payload)
                elif parsed.path == "/v1/mt5/health":
                    if client.get("client_id") != mt5_authorised_client_id():
                        self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                        return
                    result = accept_mt5_health(
                        paths.support, payload, client_id=str(client["client_id"])
                    )
                elif node_path is not None and node_path[1] == "catalogue":
                    node_id = node_path[0]
                    if client.get("client_id") != mt5_authorised_client_id(node_id):
                        self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                        return
                    result = accept_mt5_catalogue(paths.support, payload, node_id=node_id)
                elif node_path is not None and node_path[1] == "health":
                    node_id = node_path[0]
                    if client.get("client_id") != mt5_authorised_client_id(node_id):
                        self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                        return
                    result = accept_mt5_health(
                        paths.support, payload, client_id=str(client["client_id"])
                    )
                elif parsed.path == "/v1/replica/report":
                    record_client_report(paths, client, payload)
                    result = {"state": "RECORDED", "received_at_utc": utc_now()}
                elif parsed.path == "/v2/replication/requests":
                    result = submit_request(paths, str(client["client_id"]), payload)
                elif parsed.path == "/v2/replication/onboarding":
                    candidate_payload = json.loads(
                        base64.urlsafe_b64decode(str(payload["candidate"]).encode()).decode()
                    )
                    candidate = candidate_from_dict(candidate_payload)
                    allowed = set(client.get("symbols") or [])
                    if "*" not in allowed and candidate.asset not in allowed:
                        raise ReplicaControlError("CLIENT_SCOPE_DENIED", candidate.asset)
                    from .commands.register_instrument import (
                        _notify_scheduler, _register_once, _retry_when_writer_busy,
                    )
                    result = _retry_when_writer_busy(
                        lambda: _register_once(str(paths.database), candidate, False)
                    )
                    _notify_scheduler(str(paths.database))
                else:
                    parts = parsed.path.strip("/").split("/")
                    if len(parts) == 5 and parts[:3] == ["v2", "replication", "requests"] and parts[4] == "events":
                        result = update_request(paths, str(client["client_id"]), parts[3], payload)
                    else:
                        self._json(HTTPStatus.NOT_FOUND, {"code": "NOT_FOUND"})
                        return
            except (ValueError, TypeError, json.JSONDecodeError, ReplicaControlError, MT5BridgeQueueError,
                    IndexCFDAdmissionError,
                    RegistrationError) as error:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"code": getattr(error, "code", "INVALID_CLIENT_REPORT"), "error": str(error)},
                )
                return
            self._json(HTTPStatus.OK, result)

        def _serve_authorised(self, parsed, client) -> None:
            node_path = _mt5_node_path(parsed.path)
            if node_path is not None and node_path[1] == "evidence/requests/next":
                node_id = node_path[0]
                if client.get("client_id") != mt5_authorised_client_id(node_id):
                    self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                    return
                request = poll_mt5_request(paths.support, node_id=node_id)
                if request is None:
                    self.send_response(HTTPStatus.NO_CONTENT)
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                else:
                    self._json(HTTPStatus.OK, request)
                return
            if parsed.path == "/v1/mt5/evidence/requests/next":
                if client.get("client_id") != mt5_authorised_client_id():
                    self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                    return
                request = poll_mt5_request(paths.support)
                if request is None:
                    self.send_response(HTTPStatus.NO_CONTENT)
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                else:
                    self._json(HTTPStatus.OK, request)
                return
            if parsed.path == "/v2/replication/registry":
                self._json(HTTPStatus.OK, registry_projection(paths, str(client["client_id"])))
                return
            if parsed.path == "/v2/replication/discovery":
                query = (parse_qs(parsed.query).get("q") or [""])[0]
                try:
                    result = discover_market(
                        paths.database, query, resolve_crypto_catalogue=True
                    )
                except (ValueError, RuntimeError, OSError) as error:
                    raise ReplicaControlError("MARKET_DISCOVERY_FAILED", str(error)) from error
                self._json(HTTPStatus.OK, result)
                return
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 5 and parts[:3] == ["v2", "replication", "artifacts"]:
                artifact_id, resource = parts[3], parts[4]
                manifest = artifact_manifest(paths, artifact_id)
                if manifest is None:
                    self._json(HTTPStatus.NOT_FOUND, {"code": "ARTIFACT_NOT_FOUND"})
                    return
                registry = registry_projection(paths, str(client["client_id"]))
                if not any(item.get("artifact_id") == artifact_id for item in registry["requests"]):
                    self._json(HTTPStatus.FORBIDDEN, {"code": "ARTIFACT_NOT_REQUESTED"})
                    return
                if resource == "manifest":
                    self._json(HTTPStatus.OK, manifest)
                    return
                if resource == "payload":
                    payload = artifact_payload(paths, artifact_id)
                    if payload is None:
                        self._json(HTTPStatus.NOT_FOUND, {"code": "PAYLOAD_NOT_FOUND"})
                        return
                    self._lane_payload(payload, manifest)
                    return
            if parsed.path == "/v1/replica/control":
                self._json(HTTPStatus.OK, client_control(paths, client))
                return
            if parsed.path == "/v1/replica/head":
                manifest = latest_manifest(paths)
                if manifest is None:
                    self._json(HTTPStatus.NOT_FOUND, {"code": "NO_PUBLICATION"})
                elif not client_allows_manifest(client, manifest):
                    self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                else:
                    self._json(HTTPStatus.OK, manifest)
                return
            if parsed.path == "/v1/replica/publications":
                after = (parse_qs(parsed.query).get("after") or [None])[0]
                manifests = [
                    manifest
                    for manifest in list_publications(paths, after=after)
                    if client_allows_manifest(client, manifest)
                ]
                self._json(HTTPStatus.OK, {"publications": manifests})
                return
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 5 and parts[:3] == ["v1", "replica", "publications"]:
                publication_id, resource = parts[3], parts[4]
                manifest = publication_manifest(paths, publication_id)
                if manifest is None:
                    self._json(HTTPStatus.NOT_FOUND, {"code": "PUBLICATION_NOT_FOUND"})
                    return
                if not client_allows_manifest(client, manifest):
                    self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                    return
                if resource == "manifest":
                    self._json(HTTPStatus.OK, manifest)
                    return
                if resource == "payload":
                    payload = publication_payload(paths, publication_id)
                    if payload is None:
                        self._json(HTTPStatus.NOT_FOUND, {"code": "PAYLOAD_NOT_FOUND"})
                        return
                    self._payload(payload, manifest)
                    return
            if len(parts) == 4 and parts[:3] == ["v1", "replica", "snapshots"]:
                revision = parts[3]
                manifest = next(
                    (item for item in list_publications(paths) if item.get("authority_revision") == revision),
                    None,
                )
                if manifest is None:
                    self._json(HTTPStatus.NOT_FOUND, {"code": "SNAPSHOT_NOT_FOUND"})
                    return
                if not client_allows_manifest(client, manifest):
                    self._json(HTTPStatus.FORBIDDEN, {"code": "CLIENT_SCOPE_DENIED"})
                    return
                payload = publication_payload(paths, str(manifest["publication_id"]))
                if payload is None:
                    self._json(HTTPStatus.NOT_FOUND, {"code": "PAYLOAD_NOT_FOUND"})
                    return
                self._payload(payload, manifest)
                return
            self._json(HTTPStatus.NOT_FOUND, {"code": "NOT_FOUND"})

        def _payload(self, payload: Path, manifest: dict) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/vnd.sqlite3+gzip")
            self.send_header("Content-Length", str(payload.stat().st_size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-SHA256", str(manifest["payload"]["sha256"]))
            self.end_headers()
            with payload.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    self.wfile.write(block)

        def _lane_payload(self, payload: Path, manifest: dict) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/vnd.sqlite3+gzip")
            self.send_header("Content-Length", str(payload.stat().st_size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-SHA256", str(manifest["payload"]["sha256"]))
            self.end_headers()
            with payload.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    self.wfile.write(block)

    return ReplicaPublisherHandler


def serve(paths: ReplicaPaths, *, host: str = "127.0.0.1", port: int = 9462) -> None:
    if host not in LOOPBACK_HOSTS:
        raise ReplicaControlError(
            "NON_LOOPBACK_BIND_FORBIDDEN",
            "the replica publisher must bind to loopback and be exposed only through the approved private proxy",
        )
    paths.prepare()
    recover_registry(paths)
    server = ThreadingHTTPServer((host, port), _handler(paths))
    actual_port = int(server.server_address[1])
    _atomic_json(
        paths.service_status,
        {
            "contract": SERVICE_CONTRACT,
            "state": "RUNNING",
            "host": host,
            "port": actual_port,
            "pid": os.getpid(),
            "started_at_utc": utc_now(),
        },
    )
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
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
