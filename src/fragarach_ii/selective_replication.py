"""Authoritative selective lane artifacts and per-client request registry."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .replica_publication import (
    ReplicaControlError,
    ReplicaPaths,
    _client,
    _control,
    _normalized_scope,
    _write_registry,
    latest_manifest,
    load_registry,
    utc_now,
)
from .storage import open_read_only


REGISTRY_CONTRACT = "fragarach.selective_registry.v2"
ARTIFACT_CONTRACT = "fragarach.lane_artifact.v2"
DATABASE_CONTRACT = "fragarach.lane_database.v2"
REQUEST_STATES = frozenset(
    {"REQUESTED", "WAITING_FOR_STUDIO", "ACCEPTED", "TRANSFERRING", "VERIFYING", "ACTIVE",
     "PAUSED", "FAILED", "CANCELLED", "REMOVED"}
)
_REQUEST_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_ARTIFACT_ID = re.compile(r"^lane-[A-Z0-9._-]+-(?:D1|H1|M30|M15|M5)-[0-9a-f]{32}$")
_TRANSITIONS = {
    "WAITING_FOR_STUDIO": {"ACCEPTED", "CANCELLED", "REMOVED"},
    "ACCEPTED": {"TRANSFERRING", "PAUSED", "FAILED", "CANCELLED"},
    "TRANSFERRING": {"TRANSFERRING", "VERIFYING", "ACCEPTED", "PAUSED", "FAILED", "CANCELLED"},
    "VERIFYING": {"ACTIVE", "ACCEPTED", "FAILED", "CANCELLED"},
    "ACTIVE": {"ACTIVE", "ACCEPTED", "PAUSED", "FAILED", "REMOVED"},
    "PAUSED": {"PAUSED", "ACTIVE", "ACCEPTED", "REMOVED"},
    "FAILED": {"ACCEPTED", "CANCELLED", "REMOVED"},
    "CANCELLED": set(),
    "REMOVED": set(),
}


def artifact_root(paths: ReplicaPaths) -> Path:
    return paths.support / "lane-artifacts-v2"


def _canonical(symbol: str, timeframe: str, row: tuple[Any, ...]) -> bytes:
    return json.dumps([symbol, timeframe, *row], ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8") + b"\n"


def _registration(source: sqlite3.Connection, symbol: str) -> tuple[Any, ...]:
    row = source.execute(
        """SELECT asset,aliases_json,display_name,asset_class,calendar_id,
                  calendar_version,registration_status
           FROM instrument_registrations WHERE asset=? AND timeframe='D1'""",
        (symbol,),
    ).fetchone()
    if row is None:
        raise ReplicaControlError("LANE_NOT_AVAILABLE", symbol)
    return row


def create_lane_artifact(paths: ReplicaPaths, symbol: str, timeframe: str) -> dict[str, Any]:
    """Build or reuse one content-addressed immutable lane artifact."""

    symbol = _normalized_scope([symbol], timeframe=False)[0]
    timeframe = _normalized_scope([timeframe], timeframe=True)[0]
    source = open_read_only(paths.database)
    work_root = artifact_root(paths)
    work_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary_dir = Path(tempfile.mkdtemp(prefix=".building-", dir=work_root))
    database = temporary_dir / "lane.sqlite3"
    target = sqlite3.connect(database)
    created = utc_now()
    try:
        source.execute("BEGIN")
        exists = source.execute(
            "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",
            (symbol, timeframe),
        ).fetchone()
        if exists is None:
            raise ReplicaControlError("LANE_NOT_AVAILABLE", f"{symbol}:{timeframe}")
        registration = _registration(source, symbol)
        rows = source.execute(
            """SELECT open_time_utc,close_time_utc,open,high,low,close,volume
               FROM bars WHERE asset=? AND timeframe=? ORDER BY open_time_utc""",
            (symbol, timeframe),
        ).fetchall()
        digest = hashlib.sha256()
        for row in rows:
            digest.update(_canonical(symbol, timeframe, row))
        fingerprint = digest.hexdigest()
        artifact_id = f"lane-{symbol}-{timeframe}-{fingerprint[:32]}"
        final_dir = work_root / artifact_id
        existing = _read_manifest(final_dir / "manifest.json")
        if existing is not None:
            source.execute("ROLLBACK")
            return existing
        target.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE replica_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL) WITHOUT ROWID;
            CREATE TABLE registrations(
              symbol TEXT PRIMARY KEY,aliases_json TEXT NOT NULL,display_name TEXT NOT NULL,
              asset_class TEXT NOT NULL,calendar_id TEXT NOT NULL,calendar_version INTEGER NOT NULL,
              registration_status TEXT NOT NULL) WITHOUT ROWID;
            CREATE TABLE lanes(
              symbol TEXT NOT NULL,timeframe TEXT NOT NULL,first_bar_utc INTEGER,last_bar_utc INTEGER,
              bar_count INTEGER NOT NULL,data_fingerprint TEXT NOT NULL,
              PRIMARY KEY(symbol,timeframe)) WITHOUT ROWID;
            CREATE TABLE bars(
              symbol TEXT NOT NULL,timeframe TEXT NOT NULL,open_time_utc INTEGER NOT NULL,
              close_time_utc INTEGER,open TEXT NOT NULL,high TEXT NOT NULL,low TEXT NOT NULL,
              close TEXT NOT NULL,volume TEXT,PRIMARY KEY(symbol,timeframe,open_time_utc)) WITHOUT ROWID;
            """
        )
        first = int(rows[0][0]) if rows else None
        caodt = int(rows[-1][0]) if rows else None
        source_revision = f"sha256:{fingerprint}"
        target.execute("INSERT INTO registrations VALUES(?,?,?,?,?,?,?)", registration)
        target.execute("INSERT INTO lanes VALUES(?,?,?,?,?,?)",
                       (symbol, timeframe, first, caodt, len(rows), fingerprint))
        target.executemany("INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?)",
                           ((symbol, timeframe, *row) for row in rows))
        metadata = {
            "contract": DATABASE_CONTRACT, "artifact_id": artifact_id,
            "source_revision": source_revision, "symbol": symbol,
            "timeframe": timeframe, "caodt": caodt, "generated_at_utc": created,
        }
        target.executemany("INSERT INTO replica_metadata VALUES(?,?)",
                           ((key, json.dumps(value, separators=(",", ":")))
                            for key, value in metadata.items()))
        target.commit()
        if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ReplicaControlError("LANE_DATABASE_INTEGRITY_FAILED", artifact_id)
        target.close()
        expanded_sha = hashlib.sha256(database.read_bytes()).hexdigest()
        payload = temporary_dir / "lane.sqlite3.gz"
        with database.open("rb") as input_stream, payload.open("wb") as raw:
            with gzip.GzipFile(filename="lane.sqlite3", mode="wb", fileobj=raw, mtime=0) as output:
                while block := input_stream.read(1024 * 1024):
                    output.write(block)
        manifest = {
            "contract": ARTIFACT_CONTRACT, "artifact_id": artifact_id,
            "symbol": symbol, "timeframe": timeframe,
            "asset_class": registration[3],
            "source_revision": source_revision, "generated_at_utc": created,
            "first_bar_utc": datetime.fromtimestamp(first, UTC).isoformat() if first is not None else None,
            "caodt": datetime.fromtimestamp(caodt, UTC).isoformat() if caodt is not None else None,
            "bar_count": len(rows), "lane_fingerprint": source_revision,
            "payload": {"path": payload.name, "bytes": payload.stat().st_size,
                        "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                        "media_type": "application/vnd.sqlite3+gzip"},
            "database": {"bytes": database.stat().st_size, "sha256": expanded_sha},
            "signature": None, "signature_state": "NOT_COMMISSIONED",
        }
        from .replica_publication import _atomic_json
        _atomic_json(temporary_dir / "manifest.json", manifest)
        database.unlink()
        try:
            os.rename(temporary_dir, final_dir)
        except FileExistsError:
            return _read_manifest(final_dir / "manifest.json") or manifest
        source.execute("ROLLBACK")
        return manifest
    except BaseException:
        try:
            source.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        try:
            target.close()
        except sqlite3.Error:
            pass
        source.close()
        if temporary_dir.exists():
            for item in temporary_dir.iterdir():
                item.unlink(missing_ok=True)
            temporary_dir.rmdir()


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) and value.get("contract") == ARTIFACT_CONTRACT else None


def artifact_manifest(paths: ReplicaPaths, artifact_id: str) -> dict[str, Any] | None:
    if not _ARTIFACT_ID.fullmatch(artifact_id):
        return None
    return _read_manifest(artifact_root(paths) / artifact_id / "manifest.json")


def artifact_payload(paths: ReplicaPaths, artifact_id: str) -> Path | None:
    manifest = artifact_manifest(paths, artifact_id)
    if manifest is None:
        return None
    payload = artifact_root(paths) / artifact_id / str(manifest["payload"]["path"])
    return payload if payload.is_file() else None


def _requests(row: dict[str, Any]) -> list[dict[str, Any]]:
    value = row.get("requests")
    if not isinstance(value, list):
        value = []
        row["requests"] = value
    return value


def _lane_state(source: sqlite3.Connection, symbol: str, timeframe: str) -> dict[str, Any]:
    row = source.execute(
        """SELECT state_version,updated_at_utc
           FROM lane_state WHERE asset=? AND timeframe=?""",
        (symbol, timeframe),
    ).fetchone()
    return {
        "authority_state_version": int(row[0]) if row is not None else None,
        "authority_lane_updated_at_utc": row[1] if row is not None else None,
    }


def _apply_artifact(request: dict[str, Any], artifact: dict[str, Any],
                    lane_state: dict[str, Any]) -> None:
    request.update(
        artifact_id=artifact["artifact_id"],
        source_revision=artifact["source_revision"],
        first_bar_utc=artifact.get("first_bar_utc"),
        caodt=artifact.get("caodt"),
        bar_count=int(artifact.get("bar_count") or 0),
        lane_fingerprint=artifact.get("lane_fingerprint"),
        artifact_generated_at_utc=artifact.get("generated_at_utc"),
        database_bytes=int((artifact.get("database") or {}).get("bytes") or 0),
        expected_bytes=int((artifact.get("payload") or {}).get("bytes") or 0),
        **lane_state,
    )


def submit_request(paths: ReplicaPaths, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    request_id = str(payload.get("request_id") or "").lower()
    if not _REQUEST_ID.fullmatch(request_id):
        raise ReplicaControlError("INVALID_REQUEST_ID", request_id)
    symbol = _normalized_scope([str(payload.get("symbol") or "")], timeframe=False)[0]
    timeframe = _normalized_scope([str(payload.get("timeframe") or "")], timeframe=True)[0]
    registry = load_registry(paths)
    row = _client(registry, client_id)
    for request in _requests(row):
        if request.get("request_id") == request_id:
            return request
    symbols, timeframes = set(row.get("symbols") or []), set(row.get("timeframes") or [])
    if "*" not in symbols and symbol not in symbols:
        raise ReplicaControlError("CLIENT_SCOPE_DENIED", symbol)
    if "*" not in timeframes and timeframe not in timeframes:
        raise ReplicaControlError("CLIENT_SCOPE_DENIED", timeframe)
    live = next((item for item in _requests(row)
                 if item.get("symbol") == symbol and item.get("timeframe") == timeframe
                 and item.get("state") not in {"CANCELLED", "REMOVED", "FAILED"}), None)
    if live is not None:
        return live
    now = utc_now()
    try:
        artifact = create_lane_artifact(paths, symbol, timeframe)
    except ReplicaControlError as error:
        if error.code != "LANE_NOT_AVAILABLE":
            raise
        artifact = None
    request = {
        "request_id": request_id, "client_id": client_id, "symbol": symbol,
        "timeframe": timeframe,
        "state": "ACCEPTED" if artifact is not None else "WAITING_FOR_STUDIO", "attempt": 1,
        "requested_at_utc": str(payload.get("requested_at_utc") or now),
        "updated_at_utc": now,
        "transferred_bytes": 0, "verified_bytes": 0, "last_error": None,
        "last_update_check_at_utc": now,
        "last_update_outcome": "UPDATE_AVAILABLE" if artifact is not None else "WAITING_FOR_STUDIO",
        "retention": str(payload.get("retention") or "RETAIN"),
        "events": [{"state": "REQUESTED", "at_utc": str(payload.get("requested_at_utc") or now)}],
    }
    if artifact is None:
        request.update(expected_bytes=0, database_bytes=0, bar_count=0,
                       first_bar_utc=None, caodt=None)
        request["events"].append({"state": "WAITING_FOR_STUDIO", "at_utc": now})
    else:
        source = open_read_only(paths.database)
        try:
            lane_state = _lane_state(source, symbol, timeframe)
        finally:
            source.close()
        request["accepted_at_utc"] = now
        request["events"].append({"state": "ACCEPTED", "at_utc": now})
        _apply_artifact(request, artifact, lane_state)
    _requests(row).append(request)
    row["updated_at_utc"] = now
    _write_registry(paths, registry)
    return request


def update_request(paths: ReplicaPaths, client_id: str, request_id: str,
                   event: dict[str, Any]) -> dict[str, Any]:
    registry = load_registry(paths)
    row = _client(registry, client_id)
    request = next((item for item in _requests(row) if item.get("request_id") == request_id), None)
    if request is None:
        raise ReplicaControlError("REQUEST_NOT_FOUND", request_id)
    state = str(event.get("state") or "").upper()
    current = str(request.get("state") or "")
    if state not in REQUEST_STATES or state not in _TRANSITIONS.get(current, set()):
        raise ReplicaControlError("INVALID_REQUEST_TRANSITION", f"{current}->{state}")
    expected = int(request.get("expected_bytes") or 0)
    transferred = int(event.get("transferred_bytes", request.get("transferred_bytes") or 0))
    verified = int(event.get("verified_bytes", request.get("verified_bytes") or 0))
    if not (0 <= verified <= transferred <= expected):
        raise ReplicaControlError("INVALID_BYTE_COUNTS", f"{verified}/{transferred}/{expected}")
    if state == current and transferred < int(request.get("transferred_bytes") or 0):
        raise ReplicaControlError("NON_MONOTONIC_TRANSFER", str(transferred))
    if state == "VERIFYING" and transferred != expected:
        raise ReplicaControlError("TRANSFER_INCOMPLETE", str(transferred))
    if state == "ACTIVE" and (transferred != expected or verified != expected):
        raise ReplicaControlError("VERIFICATION_INCOMPLETE", str(verified))
    now = utc_now()
    request.update(state=state, transferred_bytes=transferred, verified_bytes=verified,
                   updated_at_utc=now)
    if state == "ACTIVE":
        request["active_at_utc"] = now
    if state == "PAUSED":
        request["paused_at_utc"] = now
    if state == "FAILED":
        request["last_error"] = event.get("error") or {"code": "TRANSFER_FAILED"}
    if current == "FAILED" and state == "ACCEPTED":
        request.update(attempt=int(request.get("attempt") or 0) + 1,
                       transferred_bytes=0, verified_bytes=0, last_error=None)
    request.setdefault("events", []).append({"state": state, "at_utc": now,
                                               "transferred_bytes": request["transferred_bytes"],
                                               "verified_bytes": request["verified_bytes"]})
    row["updated_at_utc"] = now
    _write_registry(paths, registry)
    return request


def registry_projection(paths: ReplicaPaths, client_id: str) -> dict[str, Any]:
    registry = load_registry(paths)
    row = _client(registry, client_id)
    manifest = latest_manifest(paths) or {}
    source = open_read_only(paths.database)
    try:
        asset_classes = dict(source.execute(
            "SELECT asset,asset_class FROM instrument_registrations WHERE timeframe='D1'"
        ).fetchall())
        now = utc_now()
        changed = False
        for request in _requests(row):
            if request.get("state") == "WAITING_FOR_STUDIO":
                request["last_update_check_at_utc"] = now
                exists = source.execute(
                    "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",
                    (request.get("symbol"), request.get("timeframe")),
                ).fetchone()
                if exists is None:
                    request["last_update_outcome"] = "WAITING_FOR_STUDIO"
                    changed = True
                    continue
                artifact = create_lane_artifact(
                    paths, str(request.get("symbol")), str(request.get("timeframe"))
                )
                lane_state = _lane_state(
                    source, str(request.get("symbol")), str(request.get("timeframe"))
                )
                _apply_artifact(request, artifact, lane_state)
                request.update(
                    state="ACCEPTED", accepted_at_utc=now, updated_at_utc=now,
                    transferred_bytes=0, verified_bytes=0,
                    last_update_outcome="UPDATE_AVAILABLE", last_error=None,
                )
                request.setdefault("events", []).append({
                    "state": "ACCEPTED", "at_utc": now, "reason": "STUDIO_LANE_AVAILABLE"
                })
                changed = True
                continue
            if request.get("state") != "ACTIVE":
                continue
            symbol, timeframe = str(request.get("symbol")), str(request.get("timeframe"))
            lane_state = _lane_state(source, symbol, timeframe)
            request["last_update_check_at_utc"] = now
            current_version = lane_state.get("authority_state_version")
            metadata_complete = all(
                key in request for key in ("first_bar_utc", "bar_count", "database_bytes")
            )
            if request.get("authority_state_version") == current_version and metadata_complete:
                request["last_update_outcome"] = "NO_CHANGE"
                changed = True
                continue
            artifact = create_lane_artifact(paths, symbol, timeframe)
            same_artifact = request.get("artifact_id") == artifact.get("artifact_id")
            _apply_artifact(request, artifact, lane_state)
            if same_artifact:
                request["last_update_outcome"] = "NO_CHANGE"
            else:
                request.update(
                    state="ACCEPTED", transferred_bytes=0, verified_bytes=0,
                    updated_at_utc=now, update_available_at_utc=now,
                    last_update_outcome="UPDATE_AVAILABLE", last_error=None,
                )
                request.setdefault("events", []).append({
                    "state": "ACCEPTED", "at_utc": now, "reason": "LANE_UPDATED"
                })
            changed = True
    finally:
        source.close()
    if changed:
        row["updated_at_utc"] = now
        _write_registry(paths, registry)
    available = [{**lane,
                  "first_bar_utc": datetime.fromtimestamp(lane["first_bar_utc"], UTC).isoformat()
                  if lane.get("first_bar_utc") is not None else None,
                  "caodt": datetime.fromtimestamp(lane["caodt"], UTC).isoformat()
                  if lane.get("caodt") is not None else None,
                  "asset_class": asset_classes.get(lane.get("symbol"), "UNKNOWN"),
                  "state": "STUDIO_AVAILABLE"} for lane in manifest.get("lanes") or []]
    return {"contract": REGISTRY_CONTRACT, "registry_revision": int(registry.get("revision") or 0),
            "client_id": client_id, "sync_paused": bool(_control(row).get("sync_paused")),
            "available_lanes": available, "requests": list(_requests(row)),
            "generated_at_utc": utc_now()}


def recover_registry(paths: ReplicaPaths) -> None:
    registry = load_registry(paths)
    changed = False
    now = utc_now()
    for row in registry.get("clients") or []:
        for request in _requests(row):
            if request.get("state") in {"TRANSFERRING", "VERIFYING"}:
                request.update(state="ACCEPTED", transferred_bytes=0, verified_bytes=0,
                               updated_at_utc=now,
                               last_error={"code": "RECOVERED_AFTER_PUBLISHER_RESTART"})
                request.setdefault("events", []).append({"state": "ACCEPTED", "at_utc": now,
                                                           "recovery": True})
                changed = True
    if changed:
        _write_registry(paths, registry)
