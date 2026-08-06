"""Fragarach Lite verified replica admission and local Market History service."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

LITE_STATUS_CONTRACT = "fragarach_lite.status.v1"
LITE_RECEIPT_CONTRACT = "fragarach_lite.replica_receipt.v1"
LITE_HISTORY_CONTRACT = "fragarach_lite.market_history.v1"
LITE_CATALOGUE_CONTRACT = "fragarach_lite.catalogue.v1"
PUBLICATION_CONTRACT = "fragarach.replica_publication.v1"
REPLICA_DATABASE_CONTRACT = "fragarach.replica_database.v1"
_REVISION = re.compile(r"^sha256:([0-9a-f]{64})$")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class FragarachLiteError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class LitePaths:
    root: Path
    revisions: Path
    staging: Path
    active: Path
    token: Path
    configuration: Path
    service_status: Path
    control: Path
    requests: Path
    selective_registry: Path
    active_lanes: Path
    lane_artifacts: Path

    @classmethod
    def create(cls, root: str | Path | None = None) -> "LitePaths":
        base = (
            Path(root).expanduser().resolve()
            if root is not None
            else Path.home() / "Library" / "Application Support" / "Fragarach Lite"
        )
        return cls(
            root=base,
            revisions=base / "revisions",
            staging=base / "staging",
            active=base / "active.json",
            token=base / "client-token",
            configuration=base / "configuration.json",
            service_status=base / "service-status.json",
            control=base / "control.json",
            requests=base / "requests.json",
            selective_registry=base / "selective-registry-v2.json",
            active_lanes=base / "active-lanes-v2.json",
            lane_artifacts=base / "lane-artifacts-v2",
        )

    def prepare(self) -> None:
        for path in (self.root, self.revisions, self.staging, self.lane_artifacts):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(path, 0o700)


def _atomic_bytes(path: Path, value: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_bytes(
        path,
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"),
    )


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def configure_lite(paths: LitePaths, *, endpoint: str, client_id: str) -> dict[str, Any]:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise FragarachLiteError("INVALID_ENDPOINT", endpoint)
    identifier = client_id.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", identifier):
        raise FragarachLiteError("INVALID_CLIENT_ID", client_id)
    paths.prepare()
    config = {
        "contract": "fragarach_lite.configuration.v1",
        "endpoint": endpoint.rstrip("/"),
        "client_id": identifier,
        "updated_at_utc": utc_now(),
    }
    _atomic_json(paths.configuration, config)
    return lite_status(paths)


def store_client_token(paths: LitePaths, token: str) -> None:
    value = token.strip()
    if not value.startswith("frg_ro_") or len(value) < 40:
        raise FragarachLiteError("INVALID_CLIENT_TOKEN", "token format is invalid")
    paths.prepare()
    _atomic_bytes(paths.token, (value + "\n").encode("utf-8"))


def _client_token(paths: LitePaths) -> str:
    try:
        value = paths.token.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise FragarachLiteError("CLIENT_TOKEN_UNAVAILABLE", str(paths.token)) from error
    if not value:
        raise FragarachLiteError("CLIENT_TOKEN_UNAVAILABLE", str(paths.token))
    return value


def _configuration(paths: LitePaths) -> dict[str, Any]:
    value = _read_json(paths.configuration, None)
    if not isinstance(value, dict) or value.get("contract") != "fragarach_lite.configuration.v1":
        raise FragarachLiteError("LITE_NOT_CONFIGURED", str(paths.configuration))
    return value


def _request_json(url: str, token: str, *, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read())
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read())
            reason = str(payload.get("code") or payload.get("error") or error.reason)
        except Exception:
            reason = str(error.reason)
        raise FragarachLiteError("UPSTREAM_REJECTED", reason) from error
    except (OSError, ValueError, urllib.error.URLError) as error:
        raise FragarachLiteError("UPSTREAM_UNAVAILABLE", str(error)) from error
    if not isinstance(value, dict):
        raise FragarachLiteError("INVALID_UPSTREAM_RESPONSE", "response must be an object")
    return value


def _post_json(url: str, token: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read())
    except (OSError, ValueError, urllib.error.HTTPError, urllib.error.URLError) as error:
        raise FragarachLiteError("REPORT_FAILED", str(error)) from error
    return value if isinstance(value, dict) else {}


def pull_control(paths: LitePaths, *, timeout: float = 15.0) -> dict[str, Any]:
    config = _configuration(paths)
    control = _request_json(
        f"{config['endpoint']}/v1/replica/control", _client_token(paths), timeout=timeout
    )
    if control.get("contract") != "fragarach.replica_control.v1":
        raise FragarachLiteError("INVALID_CONTROL_RESPONSE", str(control.get("contract")))
    _atomic_json(paths.control, control)
    return control


def report_status(paths: LitePaths, *, timeout: float = 15.0) -> dict[str, Any]:
    config = _configuration(paths)
    status = lite_status(paths)
    catalogue = lane_catalogue(paths)
    service = _read_json(paths.service_status, {})
    payload = {
        "contract": "fragarach_lite.report.v1",
        "reported_at_utc": utc_now(),
        "service": service if isinstance(service, dict) else {},
        "replica": status["active_replica"],
        "state": status["state"],
        "lanes": catalogue["lanes"],
        "control": _read_json(paths.control, {}),
        "requests": catalogue.get("requests") or [],
    }
    return _post_json(
        f"{config['endpoint']}/v1/replica/report", _client_token(paths), payload, timeout=timeout
    )


def request_lane(paths: LitePaths, *, symbol: str, timeframe: str) -> list[dict[str, Any]]:
    requested_symbol = symbol.strip().upper()
    requested_timeframe = timeframe.strip().upper()
    if not re.fullmatch(r"[A-Z0-9._-]+", requested_symbol):
        raise FragarachLiteError("INVALID_SYMBOL", symbol)
    if requested_timeframe not in {"D1", "H1", "M30", "M15", "M5"}:
        raise FragarachLiteError("INVALID_TIMEFRAME", timeframe)
    requests = _read_json(paths.requests, [])
    if not isinstance(requests, list):
        requests = []
    now = utc_now()
    lane = {
        "request_id": str(uuid.uuid4()),
        "symbol": requested_symbol,
        "timeframe": requested_timeframe,
        "state": "REQUESTED",
        "expected_bytes": 0,
        "transferred_bytes": 0,
        "verified_bytes": 0,
        "requested_at_utc": now,
        "updated_at_utc": now,
        "retention": "RETAIN",
    }
    requests = [
        item for item in requests
        if not isinstance(item, dict)
        or item.get("symbol") != requested_symbol
        or item.get("timeframe") != requested_timeframe
    ] + [lane]
    requests.sort(key=lambda item: (item["symbol"], item["timeframe"]))
    paths.prepare()
    _atomic_json(paths.requests, requests)
    return requests


def clear_lane_request(paths: LitePaths, *, symbol: str, timeframe: str) -> list[dict[str, Any]]:
    requested_symbol = symbol.strip().upper()
    requested_timeframe = timeframe.strip().upper()
    requests = _read_json(paths.requests, [])
    if not isinstance(requests, list):
        requests = []
    requests = [
        item for item in requests
        if not isinstance(item, dict)
        or item.get("symbol") != requested_symbol
        or item.get("timeframe") != requested_timeframe
    ]
    _atomic_json(paths.requests, requests)
    return requests


def control_lane_request(paths: LitePaths, *, symbol: str, timeframe: str,
                         action: str, timeout: float = 15.0) -> dict[str, Any]:
    requested_symbol = symbol.strip().upper()
    requested_timeframe = timeframe.strip().upper()
    requests = _read_json(paths.requests, [])
    request = next((item for item in requests if isinstance(item, dict)
                    and item.get("symbol") == requested_symbol
                    and item.get("timeframe") == requested_timeframe), None)
    if request is None or not request.get("request_id"):
        raise FragarachLiteError("REQUEST_NOT_FOUND", f"{requested_symbol}:{requested_timeframe}")
    command = action.strip().upper()
    expected = int(request.get("expected_bytes") or 0)
    transferred = int(request.get("transferred_bytes") or 0)
    verified = int(request.get("verified_bytes") or 0)
    if command == "PAUSE":
        state = "PAUSED"
    elif command == "RESUME":
        state = "ACTIVE" if expected and verified == expected else "ACCEPTED"
    elif command == "RETRY":
        state = "ACCEPTED"
    elif command == "CANCEL":
        state = "CANCELLED"
    elif command == "REMOVE":
        state = "REMOVED"
    else:
        raise FragarachLiteError("INVALID_REQUEST_ACTION", command)
    config = _configuration(paths)
    updated = _event(str(config["endpoint"]), _client_token(paths), str(request["request_id"]), state,
                     timeout=timeout, transferred_bytes=transferred, verified_bytes=verified)
    _write_local_request(paths, updated)
    registry = _read_json(paths.selective_registry, {})
    if isinstance(registry, dict):
        registry["requests"] = [updated if isinstance(item, dict)
                                and item.get("request_id") == updated.get("request_id") else item
                                for item in registry.get("requests") or []]
        _atomic_json(paths.selective_registry, registry)
    if state == "REMOVED":
        active = selective_active_lanes(paths)
        removed = [item for item in active if item.get("request_id") == request["request_id"]]
        retained = [item for item in active if item.get("request_id") != request["request_id"]]
        _atomic_json(paths.active_lanes, retained)
        referenced = {item.get("database") for item in retained}
        for item in removed:
            candidate = str(item.get("database") or "")
            if candidate and candidate not in referenced:
                Path(candidate).unlink(missing_ok=True)
    if state in {"CANCELLED", "REMOVED"}:
        for part in paths.staging.glob(f"{request.get('artifact_id', request['request_id'])}*.part"):
            part.unlink(missing_ok=True)
    return updated


def _download(url: str, token: str, destination: Path, *, timeout: float) -> str:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, destination.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
                digest.update(block)
            output.flush()
            os.fsync(output.fileno())
    except (OSError, urllib.error.HTTPError, urllib.error.URLError) as error:
        destination.unlink(missing_ok=True)
        raise FragarachLiteError("PAYLOAD_DOWNLOAD_FAILED", str(error)) from error
    return digest.hexdigest()


def _event(endpoint: str, token: str, request_id: str, state: str, *, timeout: float,
           transferred_bytes: int, verified_bytes: int = 0,
           error: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"state": state, "transferred_bytes": transferred_bytes,
                               "verified_bytes": verified_bytes}
    if error is not None:
        payload["error"] = error
    return _post_json(f"{endpoint}/v2/replication/requests/{request_id}/events",
                      token, payload, timeout=timeout)


def _write_local_request(paths: LitePaths, request: dict[str, Any]) -> None:
    requests = _read_json(paths.requests, [])
    if not isinstance(requests, list):
        requests = []
    requests = [item for item in requests if not isinstance(item, dict)
                or item.get("request_id") != request.get("request_id")]
    requests.append(request)
    requests.sort(key=lambda item: (str(item.get("requested_at_utc") or ""),
                                    str(item.get("symbol") or "")), reverse=True)
    _atomic_json(paths.requests, requests)


def _download_lane(url: str, token: str, destination: Path, request: dict[str, Any],
                   paths: LitePaths, endpoint: str, *, timeout: float, expected_bytes: int) -> str:
    http_request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    digest = hashlib.sha256()
    transferred = 0
    try:
        with urllib.request.urlopen(http_request, timeout=timeout) as response, destination.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
                digest.update(block)
                transferred += len(block)
                if transferred > expected_bytes:
                    raise FragarachLiteError("PAYLOAD_BYTE_COUNT_MISMATCH", str(transferred))
                request.update(state="TRANSFERRING", transferred_bytes=transferred,
                               verified_bytes=0, updated_at_utc=utc_now())
                _write_local_request(paths, request)
                _event(endpoint, token, str(request["request_id"]), "TRANSFERRING",
                       timeout=timeout, transferred_bytes=transferred)
            output.flush()
            os.fsync(output.fileno())
    except (OSError, urllib.error.HTTPError, urllib.error.URLError) as error:
        destination.unlink(missing_ok=True)
        raise FragarachLiteError("PAYLOAD_DOWNLOAD_FAILED", str(error)) from error
    return digest.hexdigest()


def _verify_lane_database(path: Path, manifest: dict[str, Any]) -> None:
    if path.stat().st_size != int(manifest["database"]["bytes"]):
        raise FragarachLiteError("DATABASE_BYTE_COUNT_MISMATCH", str(path.stat().st_size))
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["database"]["sha256"]:
        raise FragarachLiteError("DATABASE_FINGERPRINT_MISMATCH", str(manifest["artifact_id"]))
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise FragarachLiteError("LANE_DATABASE_INTEGRITY_FAILED", str(manifest["artifact_id"]))
        metadata = {key: json.loads(value) for key, value in
                    connection.execute("SELECT key,value FROM replica_metadata")}
        expected = {"contract": "fragarach.lane_database.v2",
                    "artifact_id": manifest["artifact_id"],
                    "source_revision": manifest["source_revision"],
                    "symbol": manifest["symbol"], "timeframe": manifest["timeframe"]}
        if any(metadata.get(key) != value for key, value in expected.items()):
            raise FragarachLiteError("LANE_METADATA_MISMATCH", str(manifest["artifact_id"]))
        row = connection.execute(
            "SELECT bar_count,data_fingerprint FROM lanes WHERE symbol=? AND timeframe=?",
            (manifest["symbol"], manifest["timeframe"]),
        ).fetchone()
        if row is None or int(row[0]) != int(manifest["bar_count"]):
            raise FragarachLiteError("LANE_MANIFEST_MISMATCH", str(manifest["artifact_id"]))
        digest = hashlib.sha256()
        count = 0
        for bar in connection.execute(
            """SELECT open_time_utc,close_time_utc,open,high,low,close,volume FROM bars
               WHERE symbol=? AND timeframe=? ORDER BY open_time_utc""",
            (manifest["symbol"], manifest["timeframe"]),
        ):
            digest.update(json.dumps([manifest["symbol"], manifest["timeframe"], *bar],
                                     ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
            count += 1
        if count != int(manifest["bar_count"]) or f"sha256:{digest.hexdigest()}" != manifest["lane_fingerprint"]:
            raise FragarachLiteError("LANE_FINGERPRINT_MISMATCH", str(manifest["artifact_id"]))
    except sqlite3.Error as error:
        raise FragarachLiteError("INVALID_LANE_DATABASE", str(error)) from error
    finally:
        connection.close()


def selective_active_lanes(paths: LitePaths) -> list[dict[str, Any]]:
    value = _read_json(paths.active_lanes, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)
            and Path(str(item.get("database") or "")).is_file()]


def selective_mode(paths: LitePaths) -> bool:
    """Return whether this client has crossed into the v2 selective contract."""

    registry = _read_json(paths.selective_registry, {})
    if isinstance(registry, dict) and registry.get("contract") == "fragarach.selective_registry.v2":
        return True
    requests = _read_json(paths.requests, [])
    return isinstance(requests, list) and any(
        isinstance(item, dict) and item.get("request_id") for item in requests
    )


def sync_selective(paths: LitePaths, *, allow_unsigned: bool = False,
                   allow_insecure_transport: bool = False,
                   timeout: float = 30.0) -> dict[str, Any]:
    """Submit requests and transactionally admit only their lane artifacts."""

    config = _configuration(paths)
    endpoint = str(config["endpoint"])
    if urlparse(endpoint).scheme != "https" and not allow_insecure_transport:
        raise FragarachLiteError("INSECURE_TRANSPORT_FORBIDDEN", endpoint)
    token = _client_token(paths)
    paths.prepare()
    local = _read_json(paths.requests, [])
    if not isinstance(local, list):
        local = []
    for request in list(local):
        if (isinstance(request, dict) and request.get("state") == "REQUESTED"
                and request.get("request_id")):
            accepted = _post_json(f"{endpoint}/v2/replication/requests", token, request, timeout=timeout)
            _write_local_request(paths, accepted)
    registry = _request_json(f"{endpoint}/v2/replication/registry", token, timeout=timeout)
    if registry.get("contract") != "fragarach.selective_registry.v2":
        raise FragarachLiteError("INVALID_SELECTIVE_REGISTRY", str(registry.get("contract")))
    _atomic_json(paths.selective_registry, registry)
    active_by_lane = {(item["symbol"], item["timeframe"]): item
                      for item in selective_active_lanes(paths)}
    admitted = 0
    for upstream in registry.get("requests") or []:
        if not isinstance(upstream, dict):
            continue
        _write_local_request(paths, upstream)
        if upstream.get("state") == "PAUSED" or registry.get("sync_paused"):
            continue
        current = active_by_lane.get((upstream.get("symbol"), upstream.get("timeframe")))
        if upstream.get("state") == "ACTIVE" and current and current.get("artifact_id") == upstream.get("artifact_id"):
            continue
        if upstream.get("state") not in {"ACCEPTED", "TRANSFERRING", "VERIFYING"}:
            continue
        if upstream.get("state") in {"TRANSFERRING", "VERIFYING"}:
            upstream = _event(endpoint, token, str(upstream["request_id"]), "ACCEPTED",
                              timeout=timeout, transferred_bytes=0)
            _write_local_request(paths, upstream)
        artifact_id = str(upstream["artifact_id"])
        manifest = _request_json(f"{endpoint}/v2/replication/artifacts/{artifact_id}/manifest",
                                 token, timeout=timeout)
        if manifest.get("contract") != "fragarach.lane_artifact.v2":
            raise FragarachLiteError("INVALID_LANE_ARTIFACT", artifact_id)
        if manifest.get("signature_state") != "SIGNED" and not allow_unsigned:
            raise FragarachLiteError("UNSIGNED_PUBLICATION_FORBIDDEN", artifact_id)
        expected = int(manifest["payload"]["bytes"])
        part = paths.staging / f"{artifact_id}.sqlite3.gz.part"
        expanded = paths.staging / f"{artifact_id}.sqlite3.part"
        try:
            _event(endpoint, token, str(upstream["request_id"]), "TRANSFERRING", timeout=timeout,
                   transferred_bytes=0)
            observed = _download_lane(
                f"{endpoint}/v2/replication/artifacts/{artifact_id}/payload", token, part,
                upstream, paths, endpoint, timeout=timeout, expected_bytes=expected)
            if part.stat().st_size != expected:
                raise FragarachLiteError("PAYLOAD_BYTE_COUNT_MISMATCH", str(part.stat().st_size))
            if observed != manifest["payload"]["sha256"]:
                raise FragarachLiteError("PAYLOAD_FINGERPRINT_MISMATCH", artifact_id)
            upstream = _event(endpoint, token, str(upstream["request_id"]), "VERIFYING",
                              timeout=timeout, transferred_bytes=expected)
            _write_local_request(paths, upstream)
            with gzip.open(part, "rb") as source, expanded.open("wb") as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            _verify_lane_database(expanded, manifest)
            destination = paths.lane_artifacts / f"{artifact_id}.sqlite3"
            if destination.exists():
                expanded.unlink()
            else:
                os.replace(expanded, destination)
                os.chmod(destination, 0o600)
            receipt = {"request_id": upstream["request_id"], "symbol": manifest["symbol"],
                       "timeframe": manifest["timeframe"], "artifact_id": artifact_id,
                       "database": str(destination), "source_revision": manifest["source_revision"],
                       "caodt": manifest["caodt"], "bar_count": manifest["bar_count"],
                       "lane_fingerprint": manifest["lane_fingerprint"],
                       "expected_bytes": expected, "transferred_bytes": expected,
                       "verified_bytes": expected, "active_at_utc": utc_now(),
                       "signature_state": manifest["signature_state"]}
            active_by_lane[(receipt["symbol"], receipt["timeframe"])] = receipt
            _atomic_json(paths.active_lanes, sorted(active_by_lane.values(),
                         key=lambda item: (item["symbol"], item["timeframe"])))
            upstream = _event(endpoint, token, str(upstream["request_id"]), "ACTIVE",
                              timeout=timeout, transferred_bytes=expected, verified_bytes=expected)
            _write_local_request(paths, upstream)
            admitted += 1
        except FragarachLiteError as error:
            try:
                failed = _event(endpoint, token, str(upstream["request_id"]), "FAILED",
                                timeout=timeout,
                                transferred_bytes=min(part.stat().st_size if part.exists() else 0, expected),
                                error={"code": error.code, "error": str(error)})
                _write_local_request(paths, failed)
            except FragarachLiteError:
                pass
            raise
        finally:
            part.unlink(missing_ok=True)
            expanded.unlink(missing_ok=True)
    latest = _request_json(f"{endpoint}/v2/replication/registry", token, timeout=timeout)
    _atomic_json(paths.selective_registry, latest)
    return {"contract": "fragarach_lite.selective_sync.v2", "admitted": admitted,
            "active_lanes": len(selective_active_lanes(paths)), "registry": latest}


def sync_lite(
    paths: LitePaths,
    *,
    allow_unsigned: bool = False,
    allow_insecure_transport: bool = False,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Pull, verify, and atomically admit one latest full snapshot."""

    config = _configuration(paths)
    endpoint = str(config["endpoint"])
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" and not allow_insecure_transport:
        raise FragarachLiteError("INSECURE_TRANSPORT_FORBIDDEN", endpoint)
    token = _client_token(paths)
    manifest = _request_json(f"{endpoint}/v1/replica/head", token, timeout=timeout)
    _validate_manifest(manifest, allow_unsigned=allow_unsigned)
    current = active_receipt(paths)
    if current and current.get("origin_authority_revision") == manifest["authority_revision"]:
        return {**current, "sync_outcome": "ALREADY_CURRENT"}
    paths.prepare()
    publication_id = str(manifest["publication_id"])
    compressed = paths.staging / f"{publication_id}.sqlite3.gz.part"
    expanded = paths.staging / f"{publication_id}.sqlite3.part"
    try:
        observed = _download(
            f"{endpoint}/v1/replica/publications/{publication_id}/payload",
            token,
            compressed,
            timeout=timeout,
        )
        expected = str(manifest["payload"]["sha256"])
        if observed != expected:
            raise FragarachLiteError(
                "PAYLOAD_FINGERPRINT_MISMATCH", f"expected {expected}, received {observed}"
            )
        with gzip.open(compressed, "rb") as source, expanded.open("wb") as output:
            while block := source.read(1024 * 1024):
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        _verify_replica_database(expanded, manifest)
        match = _REVISION.fullmatch(str(manifest["authority_revision"]))
        assert match is not None
        destination = paths.revisions / f"{match.group(1)}.sqlite3"
        if destination.exists():
            expanded.unlink()
        else:
            os.replace(expanded, destination)
            os.chmod(destination, 0o600)
        receipt = {
            "contract": LITE_RECEIPT_CONTRACT,
            "origin_authority": manifest["origin_authority"],
            "origin_authority_revision": manifest["authority_revision"],
            "publication_id": publication_id,
            "publication_generated_at_utc": manifest["generated_at_utc"],
            "replica_received_at_utc": utc_now(),
            "replica_database": str(destination),
            "payload_sha256": expected,
            "signature_state": manifest["signature_state"],
            "transport_state": "CONNECTED",
            "sync_outcome": "ADMITTED",
        }
        _atomic_json(paths.active, receipt)
        return receipt
    finally:
        compressed.unlink(missing_ok=True)
        expanded.unlink(missing_ok=True)


def _validate_manifest(manifest: dict[str, Any], *, allow_unsigned: bool) -> None:
    if manifest.get("contract") != PUBLICATION_CONTRACT:
        raise FragarachLiteError("INVALID_PUBLICATION_CONTRACT", str(manifest.get("contract")))
    if manifest.get("publication_kind") != "FULL_SNAPSHOT":
        raise FragarachLiteError("UNSUPPORTED_PUBLICATION_KIND", str(manifest.get("publication_kind")))
    if not _REVISION.fullmatch(str(manifest.get("authority_revision") or "")):
        raise FragarachLiteError("INVALID_AUTHORITY_REVISION", str(manifest.get("authority_revision")))
    payload = manifest.get("payload")
    if not isinstance(payload, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(payload.get("sha256") or "")):
        raise FragarachLiteError("INVALID_PAYLOAD_FINGERPRINT", "payload SHA-256 is required")
    signature_state = manifest.get("signature_state")
    if signature_state == "SIGNED":
        raise FragarachLiteError(
            "SIGNATURE_VERIFIER_NOT_COMMISSIONED",
            "signed replica admission requires the commissioned signature verifier",
        )
    if not allow_unsigned:
        raise FragarachLiteError("UNSIGNED_PUBLICATION_FORBIDDEN", str(manifest.get("publication_id")))


def _verify_replica_database(path: Path, manifest: dict[str, Any]) -> None:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise FragarachLiteError("REPLICA_INTEGRITY_FAILED", str(path))
        metadata = {
            key: json.loads(value)
            for key, value in connection.execute("SELECT key,value FROM replica_metadata")
        }
        if metadata.get("contract") != REPLICA_DATABASE_CONTRACT:
            raise FragarachLiteError("INVALID_REPLICA_CONTRACT", str(metadata.get("contract")))
        if metadata.get("publication_id") != manifest.get("publication_id"):
            raise FragarachLiteError("PUBLICATION_ID_MISMATCH", str(metadata.get("publication_id")))
        if metadata.get("authority_revision") != manifest.get("authority_revision"):
            raise FragarachLiteError("AUTHORITY_REVISION_MISMATCH", str(metadata.get("authority_revision")))
        data_hash = hashlib.sha256()
        actual_lanes: list[tuple[str, str, int, str]] = []
        for symbol, timeframe, expected_count, expected_fingerprint in connection.execute(
            "SELECT symbol,timeframe,bar_count,data_fingerprint FROM lanes ORDER BY symbol,timeframe"
        ):
            lane_hash = hashlib.sha256()
            count = 0
            for row in connection.execute(
                """SELECT open_time_utc,close_time_utc,open,high,low,close,volume
                   FROM bars WHERE symbol=? AND timeframe=? ORDER BY open_time_utc""",
                (symbol, timeframe),
            ):
                canonical = json.dumps(
                    [symbol, timeframe, *row], ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8") + b"\n"
                lane_hash.update(canonical)
                data_hash.update(canonical)
                count += 1
            if count != expected_count or lane_hash.hexdigest() != expected_fingerprint:
                raise FragarachLiteError("LANE_FINGERPRINT_MISMATCH", f"{symbol}:{timeframe}")
            actual_lanes.append((symbol, timeframe, count, expected_fingerprint))
        if f"sha256:{data_hash.hexdigest()}" != manifest.get("authority_revision"):
            raise FragarachLiteError("AUTHORITY_FINGERPRINT_MISMATCH", str(manifest.get("authority_revision")))
        expected_lanes = [
            (
                row.get("symbol"),
                row.get("timeframe"),
                row.get("bar_count"),
                str(row.get("data_fingerprint") or "").removeprefix("sha256:"),
            )
            for row in manifest.get("lanes") or []
        ]
        if actual_lanes != expected_lanes:
            raise FragarachLiteError("MANIFEST_LANE_MISMATCH", "replica lanes differ from manifest")
    except sqlite3.Error as error:
        raise FragarachLiteError("INVALID_REPLICA_DATABASE", str(error)) from error
    finally:
        connection.close()


def active_receipt(paths: LitePaths) -> dict[str, Any] | None:
    value = _read_json(paths.active, None)
    if not isinstance(value, dict) or value.get("contract") != LITE_RECEIPT_CONTRACT:
        return None
    database = Path(str(value.get("replica_database") or ""))
    return value if database.is_file() else None


def lite_status(paths: LitePaths) -> dict[str, Any]:
    config = _read_json(paths.configuration, None)
    receipt = active_receipt(paths)
    selective = selective_active_lanes(paths)
    is_selective = selective_mode(paths)
    return {
        "contract": LITE_STATUS_CONTRACT,
        "configured": isinstance(config, dict),
        "endpoint": config.get("endpoint") if isinstance(config, dict) else None,
        "client_id": config.get("client_id") if isinstance(config, dict) else None,
        "token_available": paths.token.is_file(),
        "active_replica": None if is_selective else receipt,
        "active_lanes": selective,
        "replication_mode": "SELECTIVE_V2" if is_selective else "FULL_SNAPSHOT_COMPATIBILITY",
        "state": "READY" if selective or (receipt and not is_selective) else "NO_REPLICA",
    }


def lane_catalogue(paths: LitePaths) -> dict[str, Any]:
    """Describe every lane already admitted into the local replica."""

    selective = selective_active_lanes(paths)
    local_requests = _read_json(paths.requests, [])
    registry = _read_json(paths.selective_registry, {})
    has_v2_registry = isinstance(registry, dict) and registry.get("contract") == "fragarach.selective_registry.v2"
    has_v2_requests = isinstance(local_requests, list) and any(
        isinstance(item, dict) and item.get("request_id") for item in local_requests
    )
    if selective or has_v2_requests or has_v2_registry:
        authoritative_requests = (
            registry.get("requests") or []
            if has_v2_registry
            else [item for item in local_requests
                  if isinstance(item, dict) and item.get("request_id")]
        )
        authoritative_ids = {
            item.get("request_id") for item in authoritative_requests if isinstance(item, dict)
        }
        pending_local = [
            item for item in local_requests
            if isinstance(item, dict)
            and item.get("request_id") not in authoritative_ids
            and item.get("state") in {"REQUESTED", "ACCEPTED", "TRANSFERRING", "VERIFYING"}
        ]
        requests = [*pending_local, *authoritative_requests]
        requests.sort(key=lambda item: str(item.get("requested_at_utc") or ""), reverse=True)
        state_by_lane = {(item.get("symbol"), item.get("timeframe")): item.get("state")
                         for item in requests if isinstance(item, dict)}
        available_lanes = registry.get("available_lanes") or [] if isinstance(registry, dict) else []
        available_by_lane = {
            (item.get("symbol"), item.get("timeframe")): item
            for item in available_lanes if isinstance(item, dict)
        }
        lanes = [{"symbol": item["symbol"], "timeframe": item["timeframe"],
                  "first_bar_utc": None, "caodt": item.get("caodt"),
                  "bar_count": item.get("bar_count", 0),
                  "data_fingerprint": item.get("lane_fingerprint"),
                  "source_revision": item.get("source_revision"),
                  "state": state_by_lane.get((item["symbol"], item["timeframe"]), "ACTIVE"),
                  "expected_bytes": item.get("expected_bytes", 0),
                  "transferred_bytes": item.get("transferred_bytes", 0),
                  "verified_bytes": item.get("verified_bytes", 0),
                  "asset_class": available_by_lane.get(
                      (item["symbol"], item["timeframe"]), {}
                  ).get("asset_class", "UNKNOWN")} for item in selective]
        return {"contract": "fragarach_lite.catalogue.v2", "state": "READY" if selective else "NO_REPLICA",
                "replication_mode": "SELECTIVE_V2", "lanes": lanes,
                "source_receipt": None,
                "available_lanes": available_lanes,
                "service": _read_json(paths.service_status, {}),
                "incoming_data": requests, "requests": requests}
    receipt = active_receipt(paths)
    if receipt is None:
        service = _read_json(paths.service_status, {})
        incoming = _reconcile_lane_requests(paths, set(), service)
        return {
            "contract": LITE_CATALOGUE_CONTRACT,
            "state": "NO_REPLICA",
            "lanes": [],
            "source_receipt": None,
            "available_lanes": [],
            "service": service if isinstance(service, dict) else {},
            "incoming_data": incoming,
            "requests": [item for item in incoming if item.get("state") not in {"AVAILABLE", "NOT_AVAILABLE"}],
        }
    database = Path(str(receipt["replica_database"]))
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            """SELECT l.symbol,l.timeframe,l.first_bar_utc,l.last_bar_utc,l.bar_count,
                      l.data_fingerprint,COALESCE(r.asset_class,'UNKNOWN')
               FROM lanes l LEFT JOIN registrations r ON r.symbol=l.symbol
               ORDER BY l.symbol,l.timeframe"""
        ).fetchall()
    finally:
        connection.close()
    control = _read_json(paths.control, {})
    paused = {
        (item.get("symbol"), item.get("timeframe"))
        for item in (control.get("paused_lanes") or [])
        if isinstance(item, dict)
    } if isinstance(control, dict) else set()
    lanes = [
        {
            "symbol": row[0],
            "timeframe": row[1],
            "first_bar_utc": _iso_epoch(row[2]) if row[2] is not None else None,
            "caodt": _iso_epoch(row[3]) if row[3] is not None else None,
            "bar_count": row[4],
            "data_fingerprint": f"sha256:{row[5]}",
            "state": "PAUSED" if (row[0], row[1]) in paused else "AVAILABLE",
            "asset_class": row[6],
        }
        for row in rows
    ]
    service = _read_json(paths.service_status, {})
    incoming = _reconcile_lane_requests(paths, {(lane["symbol"], lane["timeframe"]) for lane in lanes}, service)
    return {
        "contract": LITE_CATALOGUE_CONTRACT,
        "state": "READY",
        "lanes": lanes,
        "source_receipt": receipt,
        "available_lanes": control.get("available_lanes") or [] if isinstance(control, dict) else [],
        "service": service if isinstance(service, dict) else {},
        "incoming_data": incoming,
        "requests": [item for item in incoming if item.get("state") not in {"AVAILABLE", "NOT_AVAILABLE"}],
    }


def _reconcile_lane_requests(
    paths: LitePaths, local_lanes: set[tuple[str, str]], service: object
) -> list[dict[str, Any]]:
    requests = _read_json(paths.requests, [])
    if not isinstance(requests, list):
        requests = []
    status = service if isinstance(service, dict) else {}
    received = int(status.get("refresh_generation_received") or 0)
    completed = int(status.get("refresh_generation_completed") or 0)
    phase = str(status.get("sync_phase") or "WAITING")
    now = utc_now()
    reconciled: list[dict[str, Any]] = []
    for raw in requests:
        if not isinstance(raw, dict) or not raw.get("symbol") or not raw.get("timeframe"):
            continue
        item = dict(raw)
        key = (str(item["symbol"]), str(item["timeframe"]))
        expected = int(item.get("expected_generation") or received or completed or 1)
        item.setdefault("requested_at_utc", now)
        item["expected_generation"] = expected
        if key in local_lanes:
            item.update(state="AVAILABLE", progress=1.0)
            item.setdefault("completed_at_utc", now)
        elif phase == "FAILED" and received >= expected:
            item.update(state="FAILED", progress=1.0)
        elif completed >= expected:
            item.update(state="NOT_AVAILABLE", progress=1.0)
            item.setdefault("completed_at_utc", now)
        elif received >= expected and phase == "SYNCHRONISING":
            item.update(state="SYNCHRONISING", progress=0.7)
        elif received >= expected:
            item.update(state="ACKNOWLEDGED", progress=0.4)
        else:
            item.update(state="REQUESTED", progress=0.15)
        item["updated_at_utc"] = now
        reconciled.append(item)
    reconciled.sort(key=lambda item: (item["requested_at_utc"], item["symbol"], item["timeframe"]), reverse=True)
    if reconciled != requests:
        _atomic_json(paths.requests, reconciled)
    return reconciled


def market_history(
    paths: LitePaths,
    *,
    symbol: str,
    timeframe: str,
    start_utc: str,
    end_utc_exclusive: str,
    as_of_utc: str,
) -> dict[str, Any]:
    requested_symbol = symbol.strip().upper()
    requested_timeframe = timeframe.strip().upper()
    selective = next((item for item in selective_active_lanes(paths)
                      if item.get("symbol") == requested_symbol
                      and item.get("timeframe") == requested_timeframe), None)
    receipt = active_receipt(paths) if not selective_mode(paths) else None
    if receipt is None and selective is None:
        return _history_response("NO_REPLICA", ["NO_VERIFIED_REPLICA"])
    control = _read_json(paths.control, {})
    paused = control.get("paused_lanes") or [] if isinstance(control, dict) else []
    if any(
        isinstance(item, dict)
        and item.get("symbol") == requested_symbol
        and item.get("timeframe") == requested_timeframe
        for item in paused
    ):
        return _history_response("LANE_PAUSED", ["LANE_PAUSED_BY_OPERATOR"])
    start = _timestamp(start_utc, "start_utc")
    end = _timestamp(end_utc_exclusive, "end_utc_exclusive")
    as_of = _timestamp(as_of_utc, "as_of_utc")
    if end <= start:
        raise FragarachLiteError("INVALID_TIME_WINDOW", "end must follow start")
    upper = min(end, as_of)
    database = Path(str(selective["database"] if selective else receipt["replica_database"]))
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        canonical = _resolve_symbol(connection, requested_symbol)
        if canonical is None:
            return _history_response("NOT_REGISTERED", ["SYMBOL_NOT_REGISTERED"])
        lane = connection.execute(
            "SELECT data_fingerprint FROM lanes WHERE symbol=? AND timeframe=?",
            (canonical, requested_timeframe),
        ).fetchone()
        if lane is None:
            return _history_response("TIMEFRAME_NOT_ACTIVE", ["TIMEFRAME_NOT_ACTIVE"])
        rows = connection.execute(
            """SELECT open_time_utc,close_time_utc,open,high,low,close,volume
               FROM bars WHERE symbol=? AND timeframe=? AND open_time_utc>=?
                 AND open_time_utc<? AND (close_time_utc IS NULL OR close_time_utc<=?)
               ORDER BY open_time_utc""",
            (canonical, requested_timeframe, int(start.timestamp()), int(upper.timestamp()), int(as_of.timestamp())),
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        return _history_response("NO_HISTORY", ["NO_HISTORY_IN_REQUESTED_WINDOW"])
    digest = hashlib.sha256()
    bars = []
    for row in rows:
        canonical_row = json.dumps(
            [canonical, requested_timeframe, *row], ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8") + b"\n"
        digest.update(canonical_row)
        bars.append(
            {
                "timestamp": _iso_epoch(row[0]),
                "close_timestamp": _iso_epoch(row[1]) if row[1] is not None else None,
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "volume": row[6],
            }
        )
    source = selective if selective else receipt
    warnings = ["REPLICA_SIGNATURE_NOT_COMMISSIONED"] if source.get("signature_state") != "SIGNED" else []
    return {
        "contract": LITE_HISTORY_CONTRACT,
        "status": "AVAILABLE_WITH_WARNINGS" if warnings else "AVAILABLE",
        "warnings": warnings,
        "symbol": canonical,
        "timeframe": requested_timeframe,
        "requested_start_utc": start_utc,
        "requested_end_utc_exclusive": end_utc_exclusive,
        "as_of_utc": as_of_utc,
        "fulfilled_start_utc": bars[0]["timestamp"],
        "fulfilled_end_utc_exclusive": _iso_epoch(rows[-1][1]) if rows[-1][1] else None,
        "bar_count": len(bars),
        "bars": bars,
        "data_fingerprint": f"sha256:{digest.hexdigest()}",
        "source_receipt": selective if selective else receipt,
    }


def _history_response(status: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "contract": LITE_HISTORY_CONTRACT,
        "status": status,
        "warnings": warnings,
        "bar_count": 0,
        "bars": [],
    }


def _resolve_symbol(connection: sqlite3.Connection, symbol: str) -> str | None:
    direct = connection.execute("SELECT symbol FROM registrations WHERE symbol=?", (symbol,)).fetchone()
    if direct:
        return str(direct[0])
    matches = []
    for canonical, aliases_json in connection.execute("SELECT symbol,aliases_json FROM registrations"):
        aliases = json.loads(aliases_json)
        if any(alias.get("normalized_alias") == symbol for alias in aliases if isinstance(alias, dict)):
            matches.append(str(canonical))
    if len(matches) > 1:
        raise FragarachLiteError("AMBIGUOUS_SYMBOL", symbol)
    return matches[0] if matches else None


def _timestamp(value: str, name: str) -> datetime:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except (TypeError, ValueError) as error:
        raise FragarachLiteError("INVALID_TIMESTAMP", f"{name} must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise FragarachLiteError("INVALID_TIMESTAMP", f"{name} requires a timezone")
    return parsed.astimezone(UTC)


def _iso_epoch(value: int) -> str:
    return datetime.fromtimestamp(int(value), UTC).isoformat()
