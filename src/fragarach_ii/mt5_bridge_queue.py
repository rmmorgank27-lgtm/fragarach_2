"""Authenticated sidecar queue and canonical admission for the Windows MT5 bridge."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .index_cfd_mt5 import AUTHORITY_PATH, _authority, _ensure_authority
from .ingestion.pipeline import RawEvidence, ingest_staged_batch
from .mt5_broker_time import POLICY_ID, broker_server_to_utc
from .publication_service import enqueue_publication, resume_pending_publications
from .staging import StagedBar, StagingBatch
from .lane_update_register import LaneUpdateRegister


ACK_CONTRACT = "fragarach.mt5_evidence_ack.v0.4"
_MIRRORED = (
    "authority_reference", "operation", "canonical_symbol", "provider_symbol",
    "timeframe", "start_utc", "end_utc", "completed_bars_only",
    "timestamp_semantics", "source_route",
)
_REQUIRED_RESPONSE = frozenset({
    "contract", "request_id", "request_sha256", "response_sha256", "status",
    "captured_at_utc", *_MIRRORED, "terminal_route", "broker_family",
    "account_profile", "trading_permitted", "broker", "server",
    "fingerprint_sha256", "terminal_capabilities", "completion_evidence", "evidence",
})
# OHLC, timestamp and tick volume establish a usable broker bar.  Spread is
# useful execution metadata, but some valid MT5 history replies omit it.  It
# must therefore remain absent in retained evidence rather than being invented
# or turning an otherwise valid market observation into a scheduler failure.
_RAW_BAR_REQUIRED = frozenset({"time", "open", "high", "low", "close", "tick_volume"})
_RAW_BAR_OPTIONAL = frozenset({"spread", "real_volume"})
_DURATION = {"H1": 3600, "M30": 1800, "M5": 300}


class MT5BridgeQueueError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(canonical_json(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def queue_root(support: str | Path, node_id: str | None = None) -> Path:
    root = Path(support).expanduser().resolve() / "mt5-bridge"
    if node_id is None:
        return root
    from .mt5_route_manifest import bridge_node
    node = bridge_node(node_id)
    if node is None or node.get("queue_namespace") == "default":
        raise MT5BridgeQueueError("MT5_BRIDGE_NODE_UNKNOWN")
    return root / "nodes" / str(node["queue_namespace"])


def authorised_client_id(node_id: str | None = None) -> str:
    if node_id is None:
        return str(_authority()["bridge"]["transport_client_id"])
    from .mt5_route_manifest import bridge_node
    node = bridge_node(node_id)
    if node is None:
        raise MT5BridgeQueueError("MT5_BRIDGE_NODE_UNKNOWN")
    return str(node["transport_client_id"])


def _authority_reference(authority: dict[str, Any], route: dict[str, Any]) -> str:
    if route.get("authority_reference"):
        return str(route["authority_reference"])
    try:
        declared = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))["authority_checksum"]
    except (OSError, KeyError, json.JSONDecodeError) as error:
        raise MT5BridgeQueueError("AUTHORITY_REFERENCE_UNAVAILABLE") from error
    return f"{authority['authority_id']}:{declared}"


def bridge_paths(support: str | Path, node_id: str | None = None) -> dict[str, Path]:
    root = queue_root(support, node_id)
    return {
        "root": root,
        "pending": root / "pending",
        # An expired request is retained verbatim, but must no longer block a
        # fresh request for the same governed lane.
        "expired": root / "expired",
        "completed": root / "completed",
        # HTTP intake is deliberately sidecar-only. The publisher owns no
        # canonical-writer lease, so an authenticated receipt first lands here
        # and the Scheduler admits it in its next serialized cycle.
        "inbox": root / "inbox",
        "rejected": root / "rejected",
        "failed": root / "failed",
        "responses": root / "responses",
    }


def bridge_namespaces(support: str | Path) -> tuple[tuple[str | None, dict[str, Path]], ...]:
    """Return every active bridge queue while preserving the legacy default path."""

    from .mt5_route_manifest import active_bridge_nodes
    values: list[tuple[str | None, dict[str, Path]]] = []
    for node in active_bridge_nodes():
        node_id = None if node.get("queue_namespace") == "default" else str(node["node_id"])
        values.append((node_id, bridge_paths(support, node_id)))
    return tuple(values)


def enqueue_request(
    support: str | Path, *, symbol: str, timeframe: str, start_utc: str,
    end_utc: str, expires_in_seconds: int = 900, database: str | Path | None = None,
) -> dict[str, Any]:
    authority = _authority()
    bridge = authority["bridge"]
    canonical_symbol = symbol.strip().upper()
    native_timeframe = timeframe.strip().upper()
    try:
        start = datetime.fromisoformat(start_utc.replace("Z", "+00:00")).astimezone(UTC)
        end = datetime.fromisoformat(end_utc.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as error:
        raise MT5BridgeQueueError("INVALID_REQUEST_WINDOW_OR_MAPPING") from error
    if start >= end:
        raise MT5BridgeQueueError("INVALID_REQUEST_WINDOW")
    from .mt5_catalogue import authorised_routes
    published_route = authorised_routes(support, database=database).get(
        (canonical_symbol, native_timeframe)
    )
    if not published_route:
        static_timeframes = authority["bridge"].get("native_timeframes_by_symbol", {}).get(
            canonical_symbol, authority["timeframes"]
        )
        if canonical_symbol in authority["symbols"] and native_timeframe not in static_timeframes:
            raise MT5BridgeQueueError("OUTSIDE_APPROVED_NATIVE_SCOPE")
        raise MT5BridgeQueueError("CATALOGUE_ROUTE_NOT_AVAILABLE")
    provider_symbol = str(published_route["provider_symbol"])
    route = _route(authority, str(published_route["source_route"]))
    now = datetime.now(UTC).replace(microsecond=0)
    request = {
        "contract": bridge["request_contract"],
        "request_id": str(uuid.uuid4()),
        "issued_at_utc": now.isoformat().replace("+00:00", "Z"),
        "expires_at_utc": (now + timedelta(seconds=expires_in_seconds)).isoformat().replace("+00:00", "Z"),
        "authority_reference": _authority_reference(authority, route),
        "operation": "bars", "canonical_symbol": canonical_symbol,
        "provider_symbol": provider_symbol, "timeframe": native_timeframe,
        "start_utc": start.isoformat().replace("+00:00", "Z"),
        "end_utc": end.isoformat().replace("+00:00", "Z"),
        "completed_bars_only": True, "timestamp_semantics": POLICY_ID,
        "source_route": route["route_id"],
    }
    node_id = str(published_route["node_id"])
    paths = bridge_paths(support, None if published_route.get("queue_namespace") == "default" else node_id)
    _atomic_json(paths["pending"] / f"{request['request_id']}.json", request)
    return request


def poll_request(support: str | Path, node_id: str | None = None) -> dict[str, Any] | None:
    """Return the oldest valid pending request.

    Request identifiers are random UUIDs.  Filesystem-name ordering therefore
    made bridge dispatch effectively random: an older lane could be overtaken
    indefinitely by later work whose UUID happened to sort earlier.  Use the
    immutable issuance timestamp as the queue key, with the request id only as
    a stable tie-breaker.
    """
    paths = bridge_paths(support, node_id)
    # A receipt in the sidecar inbox is already durable transport evidence.
    # Canonical admission is deliberately asynchronous, so its request remains
    # in ``pending`` for a short period.  Returning it again in that window
    # makes a fast bridge re-deliver the same response and starves the next
    # lane.  Do not infer admission here; simply leave receipt-backed requests
    # for the Scheduler and offer another unreceived pending request.
    received_request_ids: set[str] = set()
    for path in paths["inbox"].glob("*.json"):
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        request_id = receipt.get("request_id") if isinstance(receipt, dict) else None
        if isinstance(request_id, str) and request_id:
            received_request_ids.add(request_id)
    queued: list[tuple[int, str, str, dict[str, Any]]] = []
    from .mt5_tick_activity import is_backfill_request
    for path in paths["pending"].glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        issued_at = value.get("issued_at_utc") if isinstance(value, dict) else None
        request_id = value.get("request_id") if isinstance(value, dict) else None
        if (
            isinstance(issued_at, str)
            and isinstance(request_id, str)
            and request_id
            and request_id not in received_request_ids
        ):
            # Normal completed-bar delivery is never allowed to sit behind a
            # historical activity chunk.
            queued.append((int(is_backfill_request(support, request_id)), issued_at, request_id, value))
    return min(queued, default=None, key=lambda item: (item[0], item[1], item[2]))[3] if queued else None


def receive_response(
    support: str | Path, response: dict[str, Any], *, node_id: str | None = None,
) -> dict[str, Any]:
    """Durably receive a broker response without touching canonical storage.

    The localhost publisher is a transport boundary, not an authority writer.
    Keeping inbound receipts in a sidecar inbox prevents a bridge retry storm
    from contending with the Scheduler's single-writer admission cycle.
    """

    if not isinstance(response, dict):
        raise MT5BridgeQueueError("RESPONSE_NOT_OBJECT")
    request_id = response.get("request_id")
    response_sha256 = response.get("response_sha256")
    if not isinstance(request_id, str) or not request_id:
        raise MT5BridgeQueueError("REQUEST_ID_MISSING")
    if not isinstance(response_sha256, str) or len(response_sha256) != 64:
        raise MT5BridgeQueueError("RESPONSE_CHECKSUM_MISSING")
    paths = bridge_paths(support, node_id)
    request = paths["pending"] / f"{request_id}.json"
    completed = paths["completed"] / f"{request_id}.json"
    if not request.is_file() and not completed.is_file():
        raise MT5BridgeQueueError("REQUEST_NOT_FOUND")
    destination = paths["inbox"] / f"{response_sha256}.json"
    payload = canonical_json(response)
    if destination.is_file():
        if destination.read_bytes().strip() != payload:
            raise MT5BridgeQueueError("RESPONSE_CHECKSUM_COLLISION")
        status = "ALREADY_RECEIVED"
    else:
        _atomic_json(destination, response)
        status = "RECEIVED"
    return {
        "contract": ACK_CONTRACT,
        "status": status,
        "request_id": request_id,
        "response_sha256": response_sha256,
    }


def drain_received_responses(
    database: str | Path, support: str | Path, *, limit: int = 32,
) -> dict[str, int]:
    """Admit a bounded inbox batch from the Scheduler's single-writer cycle."""

    if limit < 1:
        raise ValueError("limit must be positive")
    received = accepted = rejected = 0
    receipts = [
        (node_id, paths, path)
        for node_id, paths in bridge_namespaces(support)
        for path in paths["inbox"].glob("*.json")
    ]
    for node_id, paths, path in sorted(receipts, key=lambda item: item[2].name)[:limit]:
        received += 1
        try:
            response = json.loads(path.read_text(encoding="utf-8"))
            acknowledgement = accept_response(database, support, response, node_id=node_id)
        except MT5BridgeQueueError as error:
            # Keep malformed or now-unapproved evidence inspectable without
            # blocking healthy receipts behind it forever.
            _atomic_json(paths["rejected"] / path.name, {
                "response": _read_response_for_rejection(path),
                "rejected_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "reason": str(error),
            })
            path.unlink(missing_ok=True)
            request_id = ""
            try:
                request_id = str(response.get("request_id") or "")
            except (NameError, AttributeError):
                pass
            if request_id:
                from .mt5_tick_activity import fail_activity_request, is_activity_only_request
                activity_only = is_activity_only_request(support, request_id)
                fail_activity_request(support, request_id, str(error))
                pending_request = paths["pending"] / f"{request_id}.json"
                if pending_request.is_file():
                    request = json.loads(pending_request.read_text(encoding="utf-8"))
                    grant = None
                    if not activity_only:
                        from .mt5_bridge_requests import grant_mt5_fallback
                        grant = grant_mt5_fallback(
                            database,
                            support,
                            symbol=str(request.get("canonical_symbol") or ""),
                            timeframe=str(request.get("timeframe") or ""),
                            reason=f"MT5_BRIDGE_RESPONSE_REJECTED:{error}",
                            request_id=request_id,
                        )
                    failed_request = paths["failed"] / pending_request.name
                    failed_request.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    os.replace(pending_request, failed_request)
                    if grant is not None:
                        symbol, _, timeframe = str(grant["lane"]).partition(":")
                        try:
                            LaneUpdateRegister(database).release_provider_handoff(
                                asset=symbol,
                                timeframe=timeframe,
                                reason=str(grant["reason"]),
                            )
                        except (KeyError, OSError, sqlite3.Error):
                            pass
            rejected += 1
            continue
        if acknowledgement.get("status") != "ACCEPTED":
            raise MT5BridgeQueueError("RESPONSE_ADMISSION_NOT_ACCEPTED")
        path.unlink(missing_ok=True)
        accepted += 1
    return {"received": received, "accepted": accepted, "rejected": rejected}


def _read_response_for_rejection(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"unreadable_inbox_path": path.name}


def _route(authority: dict[str, Any], route_id: str) -> dict[str, Any]:
    match = next((item for item in authority["bridge"]["routes"] if item.get("route_id") == route_id), None)
    if not isinstance(match, dict):
        raise MT5BridgeQueueError("UNAPPROVED_SOURCE_ROUTE")
    return match


def _validate_response(response: dict[str, Any], request: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    authority = _authority()
    if set(response) != _REQUIRED_RESPONSE:
        raise MT5BridgeQueueError("RESPONSE_FIELD_SET_MISMATCH")
    if response["contract"] != authority["bridge"]["response_contract"] or response["status"] != "FULFILLED":
        raise MT5BridgeQueueError("RESPONSE_CONTRACT_MISMATCH")
    body = dict(response)
    response_sha = body.pop("response_sha256")
    if response_sha != checksum(body):
        raise MT5BridgeQueueError("RESPONSE_CHECKSUM_MISMATCH")
    if response["request_id"] != request["request_id"] or response["request_sha256"] != checksum(request):
        raise MT5BridgeQueueError("REQUEST_IDENTITY_MISMATCH")
    if any(response[key] != request[key] for key in _MIRRORED):
        raise MT5BridgeQueueError("REQUEST_RESPONSE_SCOPE_MISMATCH")
    if response["trading_permitted"] is not False or response["account_profile"] != "STANDARD_NON_TRADING_DATA":
        raise MT5BridgeQueueError("INELIGIBLE_TERMINAL_PROFILE")
    route = _route(authority, str(response["source_route"]))
    if response["broker_family"] != route["broker_family"]:
        raise MT5BridgeQueueError("BROKER_FAMILY_MISMATCH")
    bars = response["evidence"]
    if not isinstance(bars, list):
        raise MT5BridgeQueueError("BAR_EVIDENCE_NOT_LIST")
    for bar in bars:
        if not isinstance(bar, dict) or not _RAW_BAR_REQUIRED.issubset(bar) or set(bar).difference(_RAW_BAR_REQUIRED | _RAW_BAR_OPTIONAL):
            raise MT5BridgeQueueError("RAW_BAR_FIELD_SET_MISMATCH")
    completion = response["completion_evidence"]
    if not isinstance(completion, dict) or completion.get("timestamp_semantics") != POLICY_ID:
        raise MT5BridgeQueueError("COMPLETION_EVIDENCE_MISSING")
    proved = {item.get("bar_time") for item in completion.get("bars", []) if isinstance(item, dict)}
    if any(bar["time"] not in proved for bar in bars):
        raise MT5BridgeQueueError("BAR_COMPLETION_NOT_PROVED")
    return route, bars


def accept_response(
    database: str | Path, support: str | Path, response: dict[str, Any], *,
    node_id: str | None = None,
) -> dict[str, Any]:
    paths = bridge_paths(support, node_id)
    request_id = str(response.get("request_id") or "")
    pending = paths["pending"] / f"{request_id}.json"
    completed = paths["completed"] / f"{request_id}.json"
    request_path = pending if pending.is_file() else completed
    if not request_path.is_file():
        raise MT5BridgeQueueError("REQUEST_NOT_FOUND")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    authority = _authority()
    symbol = str(request.get("canonical_symbol") or "").upper()
    timeframe = str(request.get("timeframe") or "").upper()
    # The catalogue uses queue primitives while it verifies catalogue receipts;
    # resolve it at this boundary to avoid a module-import cycle.
    from .mt5_catalogue import authorised_routes
    approved_route = authorised_routes(support, database=database).get((symbol, timeframe))
    expected_node = "tradewinds-mt5-bridge" if node_id is None else node_id
    if (
        not approved_route
        or approved_route.get("provider_symbol") != request.get("provider_symbol")
        or approved_route.get("node_id") != expected_node
    ):
        raise MT5BridgeQueueError("OUTSIDE_APPROVED_NATIVE_SCOPE")
    route, bars = _validate_response(response, request)
    stored = paths["responses"] / f"{response['response_sha256']}.json"
    if stored.is_file() and stored.read_bytes().strip() != canonical_json(response):
        raise MT5BridgeQueueError("RESPONSE_CHECKSUM_COLLISION")
    _atomic_json(stored, response)
    raw_payload = canonical_json(response)
    raw_payload_sha256 = hashlib.sha256(raw_payload).hexdigest()
    raw_block_id = f"raw-{raw_payload_sha256}"
    received = datetime.now(UTC).replace(microsecond=0)
    _ensure_authority(Path(database), received.isoformat(), authority)
    from .mt5_route_manifest import is_mt5_primary_lane
    from .mt5_tick_activity import is_activity_only_request
    try:
        with sqlite3.connect(
            f"file:{Path(database).expanduser().resolve()}?mode=ro", uri=True,
        ) as route_connection:
            asset_class_row = route_connection.execute(
                "SELECT asset_class FROM instrument_registrations "
                "WHERE asset=? AND timeframe='D1'",
                (symbol,),
            ).fetchone()
    except sqlite3.Error:
        asset_class_row = None
    price_primary = not is_activity_only_request(support, request_id) and is_mt5_primary_lane(
        symbol, timeframe, provider_symbol=str(request.get("provider_symbol") or ""),
        asset_class=(str(asset_class_row[0]) if asset_class_row is not None else None),
    )
    staged: list[StagedBar] = []
    for index, bar in enumerate(bars, start=1):
        try:
            raw_time = str(bar["time"])
            server = datetime.strptime(raw_time, "%Y.%m.%d %H:%M:%S")
            opened = (
                int(datetime(server.year, server.month, server.day, tzinfo=UTC).timestamp())
                if request["timeframe"] == "D1"
                else int(broker_server_to_utc(raw_time).timestamp())
            )
            values = [format(Decimal(str(bar[key])), "f") for key in ("open", "high", "low", "close")]
        except (ValueError, InvalidOperation, KeyError) as error:
            raise MT5BridgeQueueError("INVALID_BAR_VALUE") from error
        opened_value, high, low, closed = map(Decimal, values)
        if min(opened_value, high, low, closed) <= 0 or high < max(opened_value, closed) or low > min(opened_value, closed):
            raise MT5BridgeQueueError("INVALID_BAR_OHLC")
        if price_primary:
            staged.append(StagedBar(
                symbol=request["canonical_symbol"], timeframe=request["timeframe"], timestamp=opened,
                open=values[0], high=values[1], low=values[2], close=values[3], volume=None,
                source="FRAGARACH_MT5_BRIDGE", provider=str(route["record_provider"]),
                raw_block_id=raw_block_id, source_row_number=index,
                source_timestamp_text=raw_time, source_timezone_interpretation=POLICY_ID,
                received_at=received.isoformat(),
                close_timestamp=None if request["timeframe"] == "D1" else opened + _DURATION[request["timeframe"]],
            ))
    outcome_facts: dict[str, str | int | bool] = {
        "provider": str(route["record_provider"]),
        "provider_contract": str(route["record_provider_contract"]),
        "provider_route": str(route["route_id"]), "provider_symbol": request["provider_symbol"],
        "asset": request["canonical_symbol"], "timeframe": request["timeframe"],
        "timestamp_policy": POLICY_ID, "native_timeframe": True,
        "request_id": request_id, "response_sha256": response["response_sha256"],
        "price_primary": price_primary,
        "volume_semantics": "attributed_tick_activity_companion",
    }
    activity_result: dict[str, Any] = {}
    def attach_activity(connection: sqlite3.Connection) -> None:
        from .mt5_tick_activity import admit_bridge_activity
        activity_result.update(admit_bridge_activity(
            connection, response=response, request=request, route=route, bars=bars,
            raw_block_id=raw_block_id, admitted_at_utc=received.isoformat(),
        ))
        outcome_facts.update(activity_result)

    ingest_staged_batch(
        database, batch=StagingBatch(tuple(staged), (), len(bars), 0, 0),
        evidence=RawEvidence(
            raw_block_id=raw_block_id, checksum=raw_payload_sha256,
            payload=raw_payload, source_name=f"{request_id}.json",
            source_locator=f"mt5-bridge://{request_id}", media_type="application/json",
            received_at=received.isoformat(),
        ),
        run_kind="mt5_broker_bridge", merge_mode="correct",
        outcome_facts=outcome_facts, preserve_rejected_evidence=True,
        before_commit=attach_activity, writer_lock_timeout_seconds=30.0,
    )
    fallback_grant = None
    if staged:
        lane = [(request["canonical_symbol"], request["timeframe"])]
        enqueue_publication(database, lane, trigger="MT5_BRIDGE_RESPONSE")
        resume_pending_publications(database)
        try:
            LaneUpdateRegister(database).record_checked(
                asset=request["canonical_symbol"], timeframe=request["timeframe"],
                checked_boundary=request["end_utc"], at=received,
                outcome="MT5_BRIDGE_CANONICAL_ADVANCED",
            )
        except (KeyError, OSError, sqlite3.Error):
            # Canonical evidence and its acknowledgement remain authoritative;
            # the scheduler's next reconciliation repairs this derived register.
            pass
        if price_primary:
            try:
                from .freshness import assess_lane_freshness
                from .storage import open_read_only
                with open_read_only(database) as freshness_connection:
                    freshness = assess_lane_freshness(
                        freshness_connection,
                        symbol=symbol,
                        timeframe=timeframe,
                        as_of=received,
                    )
                if freshness.get("state") == "Behind":
                    from .mt5_bridge_requests import grant_mt5_fallback
                    fallback_grant = grant_mt5_fallback(
                        database,
                        support,
                        symbol=symbol,
                        timeframe=timeframe,
                        reason="MT5_BRIDGE_INCOMPLETE_RESPONSE",
                        request_id=request_id,
                        at=received,
                    )
            except (KeyError, OSError, ValueError, sqlite3.Error):
                fallback_grant = None
    elif price_primary:
        from .mt5_bridge_requests import grant_mt5_fallback
        fallback_grant = grant_mt5_fallback(
            database,
            support,
            symbol=symbol,
            timeframe=timeframe,
            reason="MT5_BRIDGE_EMPTY_RESPONSE",
            request_id=request_id,
            at=received,
        )
    if fallback_grant is not None:
        try:
            LaneUpdateRegister(database).release_provider_handoff(
                asset=symbol,
                timeframe=timeframe,
                reason=str(fallback_grant["reason"]),
                at=received,
            )
        except (KeyError, OSError, sqlite3.Error):
            pass
    if pending.is_file():
        completed.parent.mkdir(parents=True, exist_ok=True)
        os.replace(pending, completed)
    from .mt5_tick_activity import complete_activity_request
    complete_activity_request(support, request_id, activity_result)
    return {
        "contract": ACK_CONTRACT, "status": "ACCEPTED", "request_id": request_id,
        "response_sha256": response["response_sha256"], "accepted_bar_count": len(staged),
        "fallback_granted": fallback_grant is not None,
        **activity_result,
    }


__all__ = [
    "ACK_CONTRACT", "MT5BridgeQueueError", "accept_response", "authorised_client_id",
    "bridge_namespaces", "bridge_paths", "drain_received_responses", "enqueue_request",
    "poll_request", "queue_root", "receive_response",
]
