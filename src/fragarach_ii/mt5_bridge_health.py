"""Authenticated operational health intake for the Windows MT5 bridge.

The report is an operational projection only.  It cannot modify provider
authority, canonical bars, credentials, or trading state.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .mt5_bridge_queue import (
    MT5BridgeQueueError, _atomic_json, bridge_namespaces, bridge_paths,
)


HEALTH_CONTRACT = "fragarach.mt5_bridge_health.v1"
HEALTH_ACK_CONTRACT = "fragarach.mt5_bridge_health_ack.v1"
FRESHNESS_BUDGET_SECONDS = 150
_BRIDGE_STATUSES = frozenset({"READY", "STARTING", "DEGRADED", "BLOCKED", "UNAVAILABLE"})
_WATCHDOG_STATUSES = frozenset({
    "HEALTHY", "WATCHING", "RECOVERY_DUE", "RELAUNCH_REQUESTED",
    "INTERVENTION_REQUIRED",
})
_NODE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise MT5BridgeQueueError(f"{field}_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise MT5BridgeQueueError(f"{field}_INVALID") from error
    if parsed.tzinfo is None:
        raise MT5BridgeQueueError(f"{field}_INVALID")
    return parsed.astimezone(UTC)


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > 500:
        raise MT5BridgeQueueError(f"{field}_INVALID")
    return value


def _optional_non_negative_number(value: object, field: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise MT5BridgeQueueError(f"{field}_INVALID")
    return float(value)


def health_paths(support: str | Path) -> dict[str, Path]:
    root = bridge_paths(support)["root"] / "health"
    return {
        "root": root,
        # `latest` is retained for a v1 bridge and older native clients. New
        # reports are additionally retained by node so a healthy standby is
        # not hidden by a stale or recovering primary node.
        "latest": root / "latest.json",
        "nodes": root / "nodes",
    }


def _node_identity(report: dict[str, Any], client_id: str) -> dict[str, str]:
    """Return a bounded node identity without making the v1 report invalid.

    Windows bridge deployments can add a ``node`` object as machines are
    provisioned. Existing single-node reports remain valid and are identified
    by their authenticated client id.
    """

    supplied = report.get("node")
    node = supplied if isinstance(supplied, dict) else {}
    node_id = str(node.get("node_id") or client_id)
    if not _NODE_ID_PATTERN.fullmatch(node_id):
        raise MT5BridgeQueueError("NODE_ID_INVALID")
    result = {"node_id": node_id}
    for key in ("broker_family", "terminal_identity", "role"):
        value = _optional_text(node.get(key), key.upper())
        if value is not None:
            result[key] = value
    return result


def _validate_report(report: dict[str, Any], now: datetime, *, client_id: str) -> dict[str, Any]:
    if report.get("contract") != HEALTH_CONTRACT:
        raise MT5BridgeQueueError("HEALTH_CONTRACT_MISMATCH")
    reported_at = _parse_utc(report.get("reported_at_utc"), "REPORTED_AT_UTC")
    if reported_at > now.replace(microsecond=0) and (reported_at - now).total_seconds() > 300:
        raise MT5BridgeQueueError("HEALTH_TIMESTAMP_IN_FUTURE")
    bridge = report.get("bridge")
    watchdog = report.get("watchdog")
    recovery = report.get("recovery")
    if not isinstance(bridge, dict) or not isinstance(watchdog, dict) or not isinstance(recovery, dict):
        raise MT5BridgeQueueError("HEALTH_COMPONENT_MISSING")
    bridge_status = str(bridge.get("status") or "")
    watchdog_status = str(watchdog.get("status") or "")
    if bridge_status not in _BRIDGE_STATUSES or watchdog_status not in _WATCHDOG_STATUSES:
        raise MT5BridgeQueueError("HEALTH_STATUS_INVALID")
    bridge_heartbeat = bridge.get("heartbeat_at_utc")
    if bridge_heartbeat is not None:
        _parse_utc(bridge_heartbeat, "BRIDGE_HEARTBEAT_AT_UTC")
    watchdog_checked = _parse_utc(watchdog.get("checked_at_utc"), "WATCHDOG_CHECKED_AT_UTC")
    if abs((reported_at - watchdog_checked).total_seconds()) > 5:
        raise MT5BridgeQueueError("HEALTH_REPORT_TIME_MISMATCH")
    for key in ("last_restart_at_utc",):
        if recovery.get(key) is not None:
            _parse_utc(recovery[key], key.upper())
    for key in ("restart_count_last_hour", "total_restart_count"):
        value = recovery.get(key, 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise MT5BridgeQueueError(f"{key.upper()}_INVALID")
    return {
        "contract": HEALTH_CONTRACT,
        "reported_at_utc": reported_at.isoformat().replace("+00:00", "Z"),
        "bridge": {
            "status": bridge_status,
            "heartbeat_at_utc": bridge_heartbeat,
            "process_started_at_utc": _optional_text(bridge.get("process_started_at_utc"), "PROCESS_STARTED_AT_UTC"),
            "last_result": _optional_text(bridge.get("last_result"), "LAST_RESULT"),
            "request_id": _optional_text(bridge.get("request_id"), "REQUEST_ID"),
            "source_route": _optional_text(bridge.get("source_route"), "SOURCE_ROUTE"),
            "error": _optional_text(bridge.get("error"), "BRIDGE_ERROR"),
        },
        "watchdog": {
            "status": watchdog_status,
            "checked_at_utc": watchdog["checked_at_utc"],
            "reason": _optional_text(watchdog.get("reason"), "WATCHDOG_REASON"),
            "action": _optional_text(watchdog.get("action"), "WATCHDOG_ACTION"),
            "heartbeat_age_seconds": _optional_non_negative_number(
                watchdog.get("heartbeat_age_seconds"), "HEARTBEAT_AGE_SECONDS"
            ),
            "unhealthy_for_seconds": _optional_non_negative_number(
                watchdog.get("unhealthy_for_seconds"), "UNHEALTHY_FOR_SECONDS"
            ),
            "error": _optional_text(watchdog.get("error"), "WATCHDOG_ERROR"),
        },
        "recovery": {
            "last_restart_at_utc": recovery.get("last_restart_at_utc"),
            "restart_count_last_hour": recovery.get("restart_count_last_hour", 0),
            "total_restart_count": recovery.get("total_restart_count", 0),
        },
        "node": _node_identity(report, client_id),
    }


def accept_health(
    support: str | Path, report: dict[str, Any], *, client_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    value = _validate_report(report, observed, client_id=client_id)
    value["received_at_utc"] = observed.isoformat().replace("+00:00", "Z")
    value["client_id"] = client_id
    paths = health_paths(support)
    latest_path = paths["latest"]
    node_path = paths["nodes"] / f"{value['node']['node_id']}.json"

    def retained_time(path: Path) -> datetime | None:
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            return _parse_utc(previous.get("reported_at_utc"), "REPORTED_AT_UTC")
        except (OSError, json.JSONDecodeError, MT5BridgeQueueError, AttributeError):
            return None

    report_time = _parse_utc(value["reported_at_utc"], "REPORTED_AT_UTC")
    node_previous_time = retained_time(node_path)
    accepted = node_previous_time is None or report_time >= node_previous_time
    if accepted:
        _atomic_json(node_path, value)

    # Keep the compatibility projection as the newest report across every
    # node. It must not decide whether a valid report is retained for its own
    # node: two independently scheduled bridges commonly report out of order.
    latest_previous_time = retained_time(latest_path)
    if latest_previous_time is None or report_time >= latest_previous_time:
        _atomic_json(latest_path, value)
    return {
        "contract": HEALTH_ACK_CONTRACT,
        "status": "ACCEPTED" if accepted else "OLDER_REPORT_IGNORED",
        "reported_at_utc": value["reported_at_utc"],
        "received_at_utc": value["received_at_utc"],
    }


def _effective_status(latest: dict[str, Any], *, observed: datetime) -> dict[str, Any]:
    """Project one retained node report into an operational health state."""

    received = _parse_utc(latest.get("received_at_utc"), "RECEIVED_AT_UTC")
    age = max(0.0, (observed - received).total_seconds())
    watchdog = latest.get("watchdog") or {}
    bridge = latest.get("bridge") or {}
    if age > FRESHNESS_BUDGET_SECONDS:
        effective = "STALE"
        freshness = "LATE"
    elif watchdog.get("status") == "INTERVENTION_REQUIRED":
        effective = "CRITICAL"
        freshness = "CURRENT"
    elif watchdog.get("status") in {"WATCHING", "RECOVERY_DUE", "RELAUNCH_REQUESTED"}:
        effective = "RECOVERING"
        freshness = "CURRENT"
    elif watchdog.get("status") == "HEALTHY" and bridge.get("status") == "READY":
        effective = "HEALTHY"
        freshness = "CURRENT"
    else:
        effective = "DEGRADED"
        freshness = "CURRENT"
    supplied_node = latest.get("node")
    node = dict(supplied_node) if isinstance(supplied_node, dict) else {}
    # A pre-node v1 receipt may have been copied into ``health/nodes`` by an
    # earlier release. Preserve its status while giving native clients the
    # stable identity they require; authenticated client identity is the v1
    # single-node identity.
    if not node.get("node_id"):
        node["node_id"] = str(latest.get("client_id") or "legacy-mt5-bridge")
    return {
        "node": node,
        "effective_status": effective,
        "freshness_state": freshness,
        "received_at_utc": latest.get("received_at_utc"),
        "reported_at_utc": latest.get("reported_at_utc"),
        "age_seconds": round(age, 3),
        "bridge": bridge,
        "watchdog": watchdog,
        "recovery": latest.get("recovery"),
    }


def _node_reports(support: Path) -> list[dict[str, Any]]:
    paths = health_paths(support)
    reports: list[dict[str, Any]] = []
    for path in sorted(paths["nodes"].glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            reports.append(value)
    if reports:
        return reports
    # Compatibility for a bridge health receipt written before node retention.
    try:
        value = json.loads(paths["latest"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [value] if isinstance(value, dict) else []


def bridge_health_status(
    database: str | Path, *, now: datetime | None = None,
) -> dict[str, Any]:
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    authority = Path(database).expanduser().resolve()
    support = Path(f"{authority}.read-only-clients")
    def queue_status(paths: dict[str, Path]) -> dict[str, int]:
        return {
            "pending": sum(1 for _ in paths["pending"].glob("*.json")),
            "completed": sum(1 for _ in paths["completed"].glob("*.json")),
            "responses": sum(1 for _ in paths["responses"].glob("*.json")),
            "expired": sum(1 for _ in paths["expired"].glob("*.json")),
        }

    namespace_paths = dict(bridge_namespaces(support))
    queue = {
        key: sum(item[key] for item in map(queue_status, namespace_paths.values()))
        for key in ("pending", "completed", "responses", "expired")
    }
    try:
        nodes = [_effective_status(item, observed=observed) for item in _node_reports(support)]
    except (MT5BridgeQueueError, AttributeError, TypeError):
        nodes = []
    from .mt5_catalogue import authorised_routes, current_catalogue
    from .mt5_route_manifest import bridge_node
    for item in nodes:
        node_id = str(item["node"].get("node_id") or "")
        config = bridge_node(node_id)
        namespace_node = None if config is None or config.get("queue_namespace") == "default" else node_id
        item["queue"] = queue_status(bridge_paths(support, namespace_node))
        catalogue = current_catalogue(support, namespace_node)
        item["catalogue"] = {
            "state": "AVAILABLE" if catalogue is not None else "MISSING",
            "generated_at_utc": catalogue.get("generated_at_utc") if catalogue else None,
            "symbol_count": int(catalogue.get("symbol_count") or 0) if catalogue else 0,
            "authorised_count": int(catalogue.get("bridge_authorized_count") or 0) if catalogue else 0,
        }
        try:
            routes = authorised_routes(support, database=authority)
            item["authorised_current_estate_routes"] = sum(
                route.get("node_id") == node_id for route in routes.values()
            )
        except (OSError, ValueError, RuntimeError):
            item["authorised_current_estate_routes"] = 0
    if not nodes:
        return {
            "contract": "fragarach_ii.mt5_bridge_monitor.v1",
            "effective_status": "UNAVAILABLE",
            "freshness_state": "MISSING",
            "received_at_utc": None,
            "age_seconds": None,
            "freshness_budget_seconds": FRESHNESS_BUDGET_SECONDS,
            "bridge": None, "watchdog": None, "recovery": None, "queue": queue,
            "nodes": [], "node_count": 0, "healthy_node_count": 0,
        }
    # A ready node remains operationally useful while another node is stale or
    # recovering.  Prefer that node for the compact legacy projection, while
    # returning every node for the native Operations view.
    rank = {"HEALTHY": 0, "RECOVERING": 1, "DEGRADED": 2, "STALE": 3, "CRITICAL": 4}
    nodes.sort(key=lambda item: (rank.get(str(item["effective_status"]), 99), str(item["node"].get("node_id", ""))))
    selected = nodes[0]
    healthy_count = sum(item["effective_status"] == "HEALTHY" for item in nodes)
    return {
        "contract": "fragarach_ii.mt5_bridge_monitor.v1",
        "effective_status": selected["effective_status"],
        "freshness_state": selected["freshness_state"],
        "received_at_utc": selected["received_at_utc"],
        "reported_at_utc": selected["reported_at_utc"],
        "age_seconds": selected["age_seconds"],
        "freshness_budget_seconds": FRESHNESS_BUDGET_SECONDS,
        "bridge": selected["bridge"],
        "watchdog": selected["watchdog"],
        "recovery": selected["recovery"],
        "queue": queue,
        "nodes": nodes,
        "node_count": len(nodes),
        "healthy_node_count": healthy_count,
    }


__all__ = [
    "FRESHNESS_BUDGET_SECONDS", "HEALTH_ACK_CONTRACT", "HEALTH_CONTRACT",
    "accept_health", "bridge_health_status", "health_paths",
]
