"""Read-only replica publication and client-control sidecar.

This module never mutates the Fragarach authority database.  Client controls,
replica snapshots, and service status live under a separate operational support
root derived from the configured authority path.
"""

from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .storage import open_read_only


REGISTRY_CONTRACT = "fragarach_ii.read_only_client_registry.v1"
STATUS_CONTRACT = "fragarach_ii.read_only_client_status.v1"
PUBLICATION_CONTRACT = "fragarach.replica_publication.v1"
REPLICA_DATABASE_CONTRACT = "fragarach.replica_database.v1"
DEFAULT_PUBLISHER_PORT = 9462
_CLIENT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
_TIMEFRAMES = frozenset({"D1", "H1", "M30", "M15", "M5"})


class ReplicaControlError(RuntimeError):
    """Stable operational failure for replica controls."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ReplicaPaths:
    database: Path
    support: Path
    registry: Path
    publications: Path
    head: Path
    service_status: Path
    client_reports: Path

    @classmethod
    def for_database(
        cls, database: str | Path, *, support: str | Path | None = None
    ) -> "ReplicaPaths":
        authority = Path(database).expanduser().resolve()
        root = (
            Path(support).expanduser().resolve()
            if support is not None
            else Path(f"{authority}.read-only-clients")
        )
        return cls(
            database=authority,
            support=root,
            registry=root / "clients.json",
            publications=root / "publications",
            head=root / "head.json",
            service_status=root / "service-status.json",
            client_reports=root / "client-reports",
        )

    def prepare(self) -> None:
        self.support.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.publications.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.client_reports.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.support, 0o700)
        os.chmod(self.publications, 0o700)
        os.chmod(self.client_reports, 0o700)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _atomic_json(path: Path, value: Any, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
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


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _default_registry() -> dict[str, Any]:
    return {
        "contract": REGISTRY_CONTRACT,
        "revision": 0,
        "publisher_enabled": False,
        "updated_at_utc": None,
        "clients": [],
    }


def load_registry(paths: ReplicaPaths) -> dict[str, Any]:
    registry = _read_json(paths.registry, _default_registry())
    if not isinstance(registry, dict) or registry.get("contract") != REGISTRY_CONTRACT:
        raise ReplicaControlError("INVALID_CLIENT_REGISTRY", str(paths.registry))
    if not isinstance(registry.get("clients"), list):
        raise ReplicaControlError("INVALID_CLIENT_REGISTRY", "clients must be a list")
    return registry


def _write_registry(paths: ReplicaPaths, registry: dict[str, Any]) -> None:
    paths.prepare()
    registry["revision"] = int(registry.get("revision") or 0) + 1
    registry["updated_at_utc"] = utc_now()
    _atomic_json(paths.registry, registry)


def set_publisher_enabled(paths: ReplicaPaths, enabled: bool) -> dict[str, Any]:
    registry = load_registry(paths)
    registry["publisher_enabled"] = bool(enabled)
    _write_registry(paths, registry)
    return registry_status(paths)


def _normalized_client_id(value: str) -> str:
    candidate = value.strip().lower()
    if not _CLIENT_ID.fullmatch(candidate):
        raise ReplicaControlError(
            "INVALID_CLIENT_ID",
            "client ID must contain 2-64 lowercase letters, digits, dot, underscore, or hyphen",
        )
    return candidate


def _normalized_scope(values: Iterable[str] | None, *, timeframe: bool) -> list[str]:
    cleaned = sorted({str(value).strip().upper() for value in (values or ["*"])})
    if not cleaned or "*" in cleaned:
        return ["*"]
    if timeframe and any(value not in _TIMEFRAMES for value in cleaned):
        raise ReplicaControlError("INVALID_TIMEFRAME_SCOPE", ",".join(cleaned))
    if not timeframe and any(not value or not re.fullmatch(r"[A-Z0-9._-]+", value) for value in cleaned):
        raise ReplicaControlError("INVALID_SYMBOL_SCOPE", ",".join(cleaned))
    return cleaned


def _token_record(client_id: str) -> tuple[str, str]:
    token = f"frg_ro_{client_id}_{secrets.token_urlsafe(32)}"
    return token, hashlib.sha256(token.encode("utf-8")).hexdigest()


def add_client(
    paths: ReplicaPaths,
    *,
    client_id: str,
    display_name: str,
    symbols: Iterable[str] | None = None,
    timeframes: Iterable[str] | None = None,
) -> dict[str, Any]:
    identifier = _normalized_client_id(client_id)
    name = display_name.strip()
    if not name:
        raise ReplicaControlError("INVALID_DISPLAY_NAME", "display name is required")
    registry = load_registry(paths)
    if any(row.get("client_id") == identifier for row in registry["clients"]):
        raise ReplicaControlError("CLIENT_ALREADY_EXISTS", identifier)
    token, digest = _token_record(identifier)
    now = utc_now()
    registry["clients"].append(
        {
            "client_id": identifier,
            "display_name": name,
            "enabled": True,
            "revoked": False,
            "symbols": _normalized_scope(symbols, timeframe=False),
            "timeframes": _normalized_scope(timeframes, timeframe=True),
            "control": {
                "sync_paused": False,
                "refresh_generation": 0,
                "paused_lanes": [],
            },
            "token_sha256": digest,
            "token_issued_at_utc": now,
            "created_at_utc": now,
            "updated_at_utc": now,
        }
    )
    registry["clients"].sort(key=lambda row: str(row["client_id"]))
    _write_registry(paths, registry)
    return {"client": _public_client(_client(registry, identifier)), "issued_token": token}


def _client(registry: dict[str, Any], client_id: str) -> dict[str, Any]:
    identifier = _normalized_client_id(client_id)
    for row in registry["clients"]:
        if row.get("client_id") == identifier:
            return row
    raise ReplicaControlError("CLIENT_NOT_FOUND", identifier)


def set_client_enabled(
    paths: ReplicaPaths, client_id: str, enabled: bool
) -> dict[str, Any]:
    registry = load_registry(paths)
    row = _client(registry, client_id)
    if row.get("revoked") and enabled:
        raise ReplicaControlError("CLIENT_REVOKED", str(row["client_id"]))
    row["enabled"] = bool(enabled)
    row["updated_at_utc"] = utc_now()
    _write_registry(paths, registry)
    return registry_status(paths)


def revoke_client(paths: ReplicaPaths, client_id: str) -> dict[str, Any]:
    registry = load_registry(paths)
    row = _client(registry, client_id)
    row["enabled"] = False
    row["revoked"] = True
    row["token_sha256"] = None
    row["updated_at_utc"] = utc_now()
    _write_registry(paths, registry)
    return registry_status(paths)


def rotate_client_token(paths: ReplicaPaths, client_id: str) -> dict[str, Any]:
    registry = load_registry(paths)
    row = _client(registry, client_id)
    if row.get("revoked"):
        raise ReplicaControlError("CLIENT_REVOKED", str(row["client_id"]))
    token, digest = _token_record(str(row["client_id"]))
    row["token_sha256"] = digest
    row["token_issued_at_utc"] = utc_now()
    row["updated_at_utc"] = row["token_issued_at_utc"]
    _write_registry(paths, registry)
    return {"client": _public_client(row), "issued_token": token}


def _control(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("control")
    if not isinstance(value, dict):
        value = {}
        row["control"] = value
    value.setdefault("sync_paused", False)
    value.setdefault("refresh_generation", 0)
    value.setdefault("paused_lanes", [])
    return value


def set_client_sync_paused(paths: ReplicaPaths, client_id: str, paused: bool) -> dict[str, Any]:
    registry = load_registry(paths)
    row = _client(registry, client_id)
    _control(row)["sync_paused"] = bool(paused)
    row["updated_at_utc"] = utc_now()
    _write_registry(paths, registry)
    return registry_status(paths)


def request_client_refresh(paths: ReplicaPaths, client_id: str) -> dict[str, Any]:
    registry = load_registry(paths)
    row = _client(registry, client_id)
    control = _control(row)
    control["refresh_generation"] = int(control.get("refresh_generation") or 0) + 1
    row["updated_at_utc"] = utc_now()
    _write_registry(paths, registry)
    return registry_status(paths)


def set_client_lane_paused(
    paths: ReplicaPaths, client_id: str, symbol: str, timeframe: str, paused: bool
) -> dict[str, Any]:
    registry = load_registry(paths)
    row = _client(registry, client_id)
    lane = {
        "symbol": _normalized_scope([symbol], timeframe=False)[0],
        "timeframe": _normalized_scope([timeframe], timeframe=True)[0],
    }
    control = _control(row)
    lanes = [item for item in control.get("paused_lanes") or [] if item != lane]
    if paused:
        lanes.append(lane)
    control["paused_lanes"] = sorted(lanes, key=lambda item: (item["symbol"], item["timeframe"]))
    now = utc_now()
    for request in row.get("requests") or []:
        if request.get("symbol") != lane["symbol"] or request.get("timeframe") != lane["timeframe"]:
            continue
        current = request.get("state")
        if paused and current in {"ACCEPTED", "TRANSFERRING", "ACTIVE"}:
            request["state"] = "PAUSED"
        elif not paused and current == "PAUSED":
            expected = int(request.get("expected_bytes") or 0)
            request["state"] = "ACTIVE" if expected and int(request.get("verified_bytes") or 0) == expected else "ACCEPTED"
        else:
            continue
        request["updated_at_utc"] = now
        request.setdefault("events", []).append({"state": request["state"], "at_utc": now})
    row["updated_at_utc"] = now
    _write_registry(paths, registry)
    return registry_status(paths)


def client_control(paths: ReplicaPaths, client: dict[str, Any]) -> dict[str, Any]:
    manifest = latest_manifest(paths) or {}
    source = open_read_only(paths.database)
    try:
        asset_classes = dict(
            source.execute(
                "SELECT asset,asset_class FROM instrument_registrations WHERE timeframe='D1'"
            ).fetchall()
        )
    finally:
        source.close()
    available_lanes = [
        {
            **lane,
            "first_bar_utc": datetime.fromtimestamp(lane["first_bar_utc"], UTC).isoformat()
            if lane.get("first_bar_utc") is not None else None,
            "caodt": datetime.fromtimestamp(lane["caodt"], UTC).isoformat()
            if lane.get("caodt") is not None else None,
            "asset_class": asset_classes.get(lane.get("symbol"), "UNKNOWN"),
            "state": "AVAILABLE",
        }
        for lane in manifest.get("lanes") or []
    ]
    return {
        "contract": "fragarach.replica_control.v1",
        "sync_paused": bool((client.get("control") or {}).get("sync_paused")),
        "refresh_generation": int((client.get("control") or {}).get("refresh_generation") or 0),
        "paused_lanes": list((client.get("control") or {}).get("paused_lanes") or []),
        "available_lanes": available_lanes,
    }


def record_client_report(paths: ReplicaPaths, client: dict[str, Any], report: dict[str, Any]) -> None:
    if not isinstance(report, dict) or report.get("contract") != "fragarach_lite.report.v1":
        raise ReplicaControlError("INVALID_CLIENT_REPORT", "unsupported Lite report")
    previous = client_report(paths, str(client["client_id"])) or {}
    previous_requests = {
        (item.get("symbol"), item.get("timeframe"))
        for item in previous.get("requests") or []
        if isinstance(item, dict)
    }
    current_requests = {
        (item.get("symbol"), item.get("timeframe"))
        for item in report.get("requests") or []
        if isinstance(item, dict) and item.get("symbol") and item.get("timeframe")
    }
    if current_requests - previous_requests:
        registry = load_registry(paths)
        row = _client(registry, str(client["client_id"]))
        control = _control(row)
        control["paused_lanes"] = [
            item
            for item in control.get("paused_lanes") or []
            if (item.get("symbol"), item.get("timeframe")) not in current_requests
        ]
        control["refresh_generation"] = int(control.get("refresh_generation") or 0) + 1
        row["updated_at_utc"] = utc_now()
        _write_registry(paths, registry)
    payload = {**report, "client_id": client["client_id"], "received_at_utc": utc_now()}
    paths.prepare()
    _atomic_json(paths.client_reports / f"{client['client_id']}.json", payload)


def client_report(paths: ReplicaPaths, client_id: str) -> dict[str, Any] | None:
    value = _read_json(paths.client_reports / f"{_normalized_client_id(client_id)}.json", None)
    return value if isinstance(value, dict) else None


def authenticate_client(paths: ReplicaPaths, token: str) -> dict[str, Any] | None:
    if not token:
        return None
    supplied = hashlib.sha256(token.encode("utf-8")).hexdigest()
    for row in load_registry(paths)["clients"]:
        expected = row.get("token_sha256")
        if (
            row.get("enabled")
            and not row.get("revoked")
            and isinstance(expected, str)
            and hmac.compare_digest(supplied, expected)
        ):
            return _public_client(row)
    return None


def _public_client(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "client_id",
            "display_name",
            "enabled",
            "revoked",
            "symbols",
            "timeframes",
            "control",
            "requests",
            "token_issued_at_utc",
            "created_at_utc",
            "updated_at_utc",
        )
    }


def latest_manifest(paths: ReplicaPaths) -> dict[str, Any] | None:
    head = _read_json(paths.head, None)
    return head if isinstance(head, dict) and head.get("contract") == PUBLICATION_CONTRACT else None


def registry_status(paths: ReplicaPaths) -> dict[str, Any]:
    registry = load_registry(paths)
    service = _read_json(paths.service_status, {})
    if not isinstance(service, dict):
        service = {}
    return {
        "contract": STATUS_CONTRACT,
        "registry_revision": int(registry.get("revision") or 0),
        "publisher_enabled": bool(registry.get("publisher_enabled")),
        "support_root": str(paths.support),
        "service": service,
        "clients": [
            {**_public_client(row), "report": client_report(paths, str(row["client_id"]))}
            for row in registry["clients"]
        ],
        "latest_publication": latest_manifest(paths),
    }


def _scope_clause(values: list[str], column: str) -> tuple[str, list[str]]:
    if values == ["*"]:
        return "", []
    placeholders = ",".join("?" for _ in values)
    return f" AND {column} IN ({placeholders})", values


def create_full_snapshot(
    paths: ReplicaPaths,
    *,
    symbols: Iterable[str] | None = None,
    timeframes: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Create one immutable read-only replica without changing authority bytes."""

    symbol_scope = _normalized_scope(symbols, timeframe=False)
    timeframe_scope = _normalized_scope(timeframes, timeframe=True)
    paths.prepare()
    publication_id = f"publication-{uuid.uuid4().hex}"
    publication_dir = paths.publications / publication_id
    publication_dir.mkdir(mode=0o700)
    replica_path = publication_dir / "replica.sqlite3"
    payload_path = publication_dir / "replica.sqlite3.gz"
    manifest_path = publication_dir / "manifest.json"
    created = utc_now()
    data_hash = hashlib.sha256()
    lanes: list[dict[str, Any]] = []

    source = open_read_only(paths.database)
    target = sqlite3.connect(replica_path)
    try:
        source.execute("BEGIN")
        target.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE replica_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL) WITHOUT ROWID;
            CREATE TABLE registrations(
              symbol TEXT PRIMARY KEY,aliases_json TEXT NOT NULL,display_name TEXT NOT NULL,
              asset_class TEXT NOT NULL,calendar_id TEXT NOT NULL,calendar_version INTEGER NOT NULL,
              registration_status TEXT NOT NULL
            ) WITHOUT ROWID;
            CREATE TABLE lanes(
              symbol TEXT NOT NULL,timeframe TEXT NOT NULL,first_bar_utc INTEGER,
              last_bar_utc INTEGER,bar_count INTEGER NOT NULL,data_fingerprint TEXT NOT NULL,
              PRIMARY KEY(symbol,timeframe)
            ) WITHOUT ROWID;
            CREATE TABLE bars(
              symbol TEXT NOT NULL,timeframe TEXT NOT NULL,open_time_utc INTEGER NOT NULL,
              close_time_utc INTEGER,open TEXT NOT NULL,high TEXT NOT NULL,low TEXT NOT NULL,
              close TEXT NOT NULL,volume TEXT,
              PRIMARY KEY(symbol,timeframe,open_time_utc)
            ) WITHOUT ROWID;
            """
        )
        symbol_clause, symbol_parameters = _scope_clause(symbol_scope, "asset")
        registrations = source.execute(
            """SELECT asset,aliases_json,display_name,asset_class,calendar_id,
                      calendar_version,registration_status
               FROM instrument_registrations WHERE timeframe='D1'"""
            + symbol_clause
            + " ORDER BY asset",
            symbol_parameters,
        ).fetchall()
        target.executemany(
            "INSERT INTO registrations VALUES(?,?,?,?,?,?,?)", registrations
        )
        timeframe_clause, timeframe_parameters = _scope_clause(timeframe_scope, "timeframe")
        lane_rows = source.execute(
            "SELECT asset,timeframe FROM evidence_lanes WHERE 1=1"
            + symbol_clause
            + timeframe_clause
            + " ORDER BY asset,timeframe",
            symbol_parameters + timeframe_parameters,
        ).fetchall()
        for symbol, timeframe in lane_rows:
            lane_hash = hashlib.sha256()
            count = 0
            first: int | None = None
            last: int | None = None
            cursor = source.execute(
                """SELECT open_time_utc,close_time_utc,open,high,low,close,volume
                   FROM bars WHERE asset=? AND timeframe=? ORDER BY open_time_utc""",
                (symbol, timeframe),
            )
            while True:
                batch = cursor.fetchmany(2000)
                if not batch:
                    break
                target.executemany(
                    "INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?)",
                    ((symbol, timeframe, *row) for row in batch),
                )
                for row in batch:
                    canonical = json.dumps(
                        [symbol, timeframe, *row],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8") + b"\n"
                    lane_hash.update(canonical)
                    data_hash.update(canonical)
                    count += 1
                    first = int(row[0]) if first is None else first
                    last = int(row[0])
            fingerprint = lane_hash.hexdigest()
            target.execute(
                "INSERT INTO lanes VALUES(?,?,?,?,?,?)",
                (symbol, timeframe, first, last, count, fingerprint),
            )
            lanes.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "first_bar_utc": first,
                    "caodt": last,
                    "bar_count": count,
                    "data_fingerprint": f"sha256:{fingerprint}",
                }
            )
        authority_revision = f"sha256:{data_hash.hexdigest()}"
        metadata = {
            "contract": REPLICA_DATABASE_CONTRACT,
            "origin_authority": "MAC_STUDIO_FRAGARACH_2",
            "publication_id": publication_id,
            "authority_revision": authority_revision,
            "generated_at_utc": created,
        }
        target.executemany(
            "INSERT INTO replica_metadata VALUES(?,?)",
            ((key, json.dumps(value, separators=(",", ":"))) for key, value in metadata.items()),
        )
        target.commit()
        source.execute("ROLLBACK")
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ReplicaControlError("REPLICA_INTEGRITY_FAILED", publication_id)
    except BaseException:
        publication_dir.chmod(0o700)
        for path in publication_dir.iterdir():
            path.unlink(missing_ok=True)
        publication_dir.rmdir()
        raise
    finally:
        target.close()
        source.close()

    with replica_path.open("rb") as source_stream, payload_path.open("wb") as raw_output:
        with gzip.GzipFile(filename="replica.sqlite3", mode="wb", fileobj=raw_output, mtime=0) as compressed:
            while block := source_stream.read(1024 * 1024):
                compressed.write(block)
    replica_path.unlink()
    payload_sha256 = hashlib.sha256(payload_path.read_bytes()).hexdigest()
    previous = latest_manifest(paths)
    manifest = {
        "contract": PUBLICATION_CONTRACT,
        "publication_kind": "FULL_SNAPSHOT",
        "origin_authority": "MAC_STUDIO_FRAGARACH_2",
        "publication_id": publication_id,
        "authority_revision": authority_revision,
        "previous_authority_revision": previous.get("authority_revision") if previous else None,
        "generated_at_utc": created,
        "symbol_scope": symbol_scope,
        "timeframe_scope": timeframe_scope,
        "lanes": lanes,
        "payload": {
            "media_type": "application/vnd.sqlite3+gzip",
            "path": payload_path.name,
            "bytes": payload_path.stat().st_size,
            "sha256": payload_sha256,
        },
        "signature": None,
        "signature_state": "NOT_COMMISSIONED",
    }
    _atomic_json(manifest_path, manifest)
    _atomic_json(paths.head, manifest)
    return manifest


def publication_manifest(paths: ReplicaPaths, publication_id: str) -> dict[str, Any] | None:
    if not re.fullmatch(r"publication-[0-9a-f]{32}", publication_id):
        return None
    value = _read_json(paths.publications / publication_id / "manifest.json", None)
    return value if isinstance(value, dict) and value.get("contract") == PUBLICATION_CONTRACT else None


def publication_payload(paths: ReplicaPaths, publication_id: str) -> Path | None:
    manifest = publication_manifest(paths, publication_id)
    if manifest is None:
        return None
    candidate = paths.publications / publication_id / str(manifest["payload"]["path"])
    return candidate if candidate.is_file() else None


def list_publications(paths: ReplicaPaths, *, after: str | None = None) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    if not paths.publications.is_dir():
        return manifests
    for path in sorted(paths.publications.glob("publication-*/manifest.json")):
        value = _read_json(path, None)
        if isinstance(value, dict) and value.get("contract") == PUBLICATION_CONTRACT:
            manifests.append(value)
    if after is None:
        return manifests
    for index, manifest in enumerate(manifests):
        if manifest.get("authority_revision") == after:
            return manifests[index + 1 :]
    raise ReplicaControlError("REVISION_NOT_FOUND", after)


def client_allows_manifest(client: dict[str, Any], manifest: dict[str, Any]) -> bool:
    symbols = set(client.get("symbols") or [])
    timeframes = set(client.get("timeframes") or [])
    for lane in manifest.get("lanes") or []:
        if "*" not in symbols and lane.get("symbol") not in symbols:
            return False
        if "*" not in timeframes and lane.get("timeframe") not in timeframes:
            return False
    return True
