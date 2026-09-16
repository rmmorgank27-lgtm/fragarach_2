from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from fragarach_ii.mt5_bridge_health import (
    HEALTH_CONTRACT, accept_health, bridge_health_status, health_paths,
)
from fragarach_ii.mt5_bridge_queue import MT5BridgeQueueError
from fragarach_ii.replica_publication import add_client, set_publisher_enabled
from fragarach_ii.replica_publisher_service import _handler
from tests.operations.test_read_only_clients import _fixture


NOW = datetime(2026, 9, 11, 1, 0, tzinfo=UTC)


def _report(*, reported_at: datetime = NOW, watchdog_status: str = "HEALTHY", node_id: str | None = None) -> dict:
    stamp = reported_at.isoformat().replace("+00:00", "Z")
    report = {
        "contract": HEALTH_CONTRACT,
        "reported_at_utc": stamp,
        "bridge": {
            "status": "READY", "heartbeat_at_utc": stamp,
            "process_started_at_utc": "2026-09-11T00:30:00Z",
            "last_result": "acknowledged", "request_id": "request-one",
            "source_route": "registered_standard_data_primary", "error": None,
        },
        "watchdog": {
            "status": watchdog_status, "checked_at_utc": stamp, "reason": "READY",
            "action": "NONE", "heartbeat_age_seconds": 2.0,
            "unhealthy_for_seconds": None, "error": None,
        },
        "recovery": {
            "last_restart_at_utc": "2026-09-11T00:45:00Z",
            "restart_count_last_hour": 1, "total_restart_count": 3,
        },
    }
    if node_id:
        report["node"] = {
            "node_id": node_id,
            "broker_family": "primary-broker",
            "terminal_identity": f"terminal-{node_id}",
            "role": "PRIMARY",
        }
    return report


def test_health_is_sidecar_only_and_projects_queue_and_recovery(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    database.write_bytes(b"immutable-authority")
    support = Path(f"{database.resolve()}.read-only-clients")
    pending = support / "mt5-bridge" / "pending"
    completed = support / "mt5-bridge" / "completed"
    pending.mkdir(parents=True)
    completed.mkdir(parents=True)
    (pending / "one.json").write_text("{}", encoding="utf-8")
    (completed / "two.json").write_text("{}", encoding="utf-8")
    before = database.read_bytes()

    acknowledgement = accept_health(
        support, _report(), client_id="tradewinds-mt5-bridge", now=NOW,
    )
    status = bridge_health_status(database, now=NOW + timedelta(seconds=5))

    assert acknowledgement["status"] == "ACCEPTED"
    assert status["effective_status"] == "HEALTHY"
    assert status["freshness_state"] == "CURRENT"
    assert status["queue"]["pending"] == 1
    assert status["queue"]["completed"] == 1
    assert status["recovery"]["last_restart_at_utc"] == "2026-09-11T00:45:00Z"
    assert database.read_bytes() == before


def test_stale_or_missing_reports_never_present_as_healthy(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    missing = bridge_health_status(database, now=NOW)
    assert missing["effective_status"] == "UNAVAILABLE"
    support = Path(f"{database.resolve()}.read-only-clients")
    accept_health(support, _report(), client_id="tradewinds-mt5-bridge", now=NOW)
    stale = bridge_health_status(database, now=NOW + timedelta(seconds=151))
    assert stale["effective_status"] == "STALE"
    assert stale["freshness_state"] == "LATE"


def test_healthy_standby_remains_visible_when_primary_is_stale(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    support = Path(f"{database.resolve()}.read-only-clients")
    accept_health(
        support, _report(reported_at=NOW - timedelta(seconds=151), node_id="mt5-primary"),
        client_id="mt5-primary", now=NOW - timedelta(seconds=151),
    )
    accept_health(
        support, _report(reported_at=NOW, node_id="mt5-standby"),
        client_id="mt5-standby", now=NOW,
    )

    status = bridge_health_status(database, now=NOW)

    assert status["effective_status"] == "HEALTHY"
    assert status["node_count"] == 2
    assert status["healthy_node_count"] == 1
    assert status["nodes"][0]["node"]["node_id"] == "mt5-standby"


def test_legacy_node_receipt_receives_authenticated_client_identity(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    support = Path(f"{database.resolve()}.read-only-clients")
    accept_health(support, _report(), client_id="tradewinds-mt5-bridge", now=NOW)
    path = health_paths(support)["nodes"] / "tradewinds-mt5-bridge.json"
    legacy = json.loads(path.read_text(encoding="utf-8"))
    legacy["node"] = {}
    path.write_text(json.dumps(legacy), encoding="utf-8")

    status = bridge_health_status(database, now=NOW)

    assert status["nodes"][0]["node"]["node_id"] == "tradewinds-mt5-bridge"


def test_older_health_report_cannot_replace_newer_observation(tmp_path: Path) -> None:
    support = tmp_path / "support"
    accept_health(support, _report(), client_id="tradewinds-mt5-bridge", now=NOW)
    old = _report(reported_at=NOW - timedelta(minutes=2))
    acknowledgement = accept_health(
        support, old, client_id="tradewinds-mt5-bridge", now=NOW,
    )
    latest = json.loads(health_paths(support)["latest"].read_text(encoding="utf-8"))
    assert acknowledgement["status"] == "OLDER_REPORT_IGNORED"
    assert latest["reported_at_utc"] == _report()["reported_at_utc"]


def test_each_node_retains_its_report_when_global_latest_is_newer(tmp_path: Path) -> None:
    support = tmp_path / "support"
    accept_health(
        support, _report(reported_at=NOW, node_id="fusion-node"),
        client_id="fusion-node", now=NOW,
    )
    acknowledgement = accept_health(
        support,
        _report(reported_at=NOW - timedelta(seconds=1), node_id="eightcap-node"),
        client_id="eightcap-node",
        now=NOW,
    )

    node = json.loads(
        (health_paths(support)["nodes"] / "eightcap-node.json").read_text(encoding="utf-8")
    )
    latest = json.loads(health_paths(support)["latest"].read_text(encoding="utf-8"))

    assert acknowledgement["status"] == "ACCEPTED"
    assert node["node"]["node_id"] == "eightcap-node"
    assert latest["node"]["node_id"] == "fusion-node"


def test_invalid_health_report_is_rejected(tmp_path: Path) -> None:
    invalid = _report()
    invalid["watchdog"]["status"] = "EVERYTHING_IS_FINE"
    with pytest.raises(MT5BridgeQueueError, match="HEALTH_STATUS_INVALID"):
        accept_health(tmp_path, invalid, client_id="tradewinds-mt5-bridge", now=NOW)


def test_health_http_endpoint_is_mt5_client_scoped(tmp_path: Path) -> None:
    _database, paths = _fixture(tmp_path)
    mt5 = add_client(paths, client_id="tradewinds-mt5-bridge", display_name="MT5 MCP")
    other = add_client(paths, client_id="other-client", display_name="Other")
    set_publisher_enabled(paths, True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(paths))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/v1/mt5/health"
    body = json.dumps(_report(reported_at=datetime.now(UTC))).encode()
    try:
        denied = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Bearer {other['issued_token']}", "Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(denied)
        assert error.value.code == 403
        request = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Bearer {mt5['issued_token']}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            acknowledgement = json.loads(response.read())
        assert acknowledgement["status"] == "ACCEPTED"
        assert health_paths(paths.support)["latest"].is_file()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
