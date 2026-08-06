from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from fragarach_ii.replica_publication import (
    ReplicaControlError,
    ReplicaPaths,
    add_client,
    authenticate_client,
    create_full_snapshot,
    registry_status,
    request_client_refresh,
    revoke_client,
    rotate_client_token,
    set_client_enabled,
    set_client_lane_paused,
    set_client_sync_paused,
    set_publisher_enabled,
)
from fragarach_ii.replica_publisher_service import _handler
from fragarach_ii.selective_replication import recover_registry, submit_request, update_request
from fragarach_ii.replica_publisher_daemon import PublisherLifecyclePaths, launch_agent_definition, publisher_service_status
from http.server import ThreadingHTTPServer
from tests.validation.test_d1_session_validation import _create_lane


def _fixture(tmp_path: Path) -> tuple[Path, ReplicaPaths]:
    database = tmp_path / "authority.sqlite3"
    _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
    return database, ReplicaPaths.for_database(database, support=tmp_path / "replica-support")


def test_controls_are_sidecar_only_and_tokens_are_one_time(tmp_path: Path) -> None:
    database, paths = _fixture(tmp_path)
    before = database.read_bytes()

    created = add_client(
        paths,
        client_id="macbook-pro",
        display_name="Ray's MacBook Pro",
        symbols=["AUDUSD"],
        timeframes=["D1"],
    )
    token = created["issued_token"]
    status = registry_status(paths)

    assert token.startswith("frg_ro_macbook-pro_")
    assert "issued_token" not in json.dumps(status)
    assert "token_sha256" not in json.dumps(status)
    assert authenticate_client(paths, token)["client_id"] == "macbook-pro"
    assert database.read_bytes() == before

    set_client_enabled(paths, "macbook-pro", False)
    assert authenticate_client(paths, token) is None
    set_client_enabled(paths, "macbook-pro", True)
    rotated = rotate_client_token(paths, "macbook-pro")["issued_token"]
    assert authenticate_client(paths, token) is None
    assert authenticate_client(paths, rotated) is not None
    revoke_client(paths, "macbook-pro")
    assert authenticate_client(paths, rotated) is None


def test_snapshot_is_compact_exact_and_does_not_mutate_authority(tmp_path: Path) -> None:
    database, paths = _fixture(tmp_path)
    before = database.read_bytes()

    manifest = create_full_snapshot(paths, symbols=["AUDUSD"], timeframes=["D1"])

    assert database.read_bytes() == before
    assert manifest["publication_kind"] == "FULL_SNAPSHOT"
    assert manifest["signature_state"] == "NOT_COMMISSIONED"
    assert [(row["symbol"], row["timeframe"], row["bar_count"]) for row in manifest["lanes"]] == [
        ("AUDUSD", "D1", 2)
    ]
    payload = paths.publications / manifest["publication_id"] / manifest["payload"]["path"]
    assert hashlib.sha256(payload.read_bytes()).hexdigest() == manifest["payload"]["sha256"]
    replica = tmp_path / "replica.sqlite3"
    with gzip.open(payload, "rb") as source, replica.open("wb") as target:
        target.write(source.read())
    connection = sqlite3.connect(replica)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute(
            "SELECT symbol,timeframe,open_time_utc,open,high,low,close,volume FROM bars ORDER BY open_time_utc"
        ).fetchall() == [
            ("AUDUSD", "D1", row[0], row[1], row[2], row[3], row[4], row[5])
            for row in sqlite3.connect(database).execute(
                "SELECT open_time_utc,open,high,low,close,volume FROM bars ORDER BY open_time_utc"
            ).fetchall()
        ]
    finally:
        connection.close()


def test_non_loopback_publisher_is_rejected(tmp_path: Path) -> None:
    from fragarach_ii.replica_publisher_service import serve

    _, paths = _fixture(tmp_path)
    with pytest.raises(ReplicaControlError, match="loopback"):
        serve(paths, host="0.0.0.0", port=0)


def test_http_transport_requires_enabled_registered_client(tmp_path: Path) -> None:
    _, paths = _fixture(tmp_path)
    created = add_client(paths, client_id="macbook-pro", display_name="MacBook")
    token = created["issued_token"]
    manifest = create_full_snapshot(paths)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(paths))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/health") as response:
            assert json.loads(response.read())["state"] == "DISABLED"
        request = urllib.request.Request(
            f"{base}/v1/replica/head", headers={"Authorization": f"Bearer {token}"}
        )
        with pytest.raises(urllib.error.HTTPError) as disabled:
            urllib.request.urlopen(request)
        assert disabled.value.code == 503

        set_publisher_enabled(paths, True)
        with pytest.raises(urllib.error.HTTPError) as unauthorised:
            urllib.request.urlopen(f"{base}/v1/replica/head")
        assert unauthorised.value.code == 401
        with urllib.request.urlopen(request) as response:
            assert json.loads(response.read())["publication_id"] == manifest["publication_id"]
        control_request = urllib.request.Request(
            f"{base}/v1/replica/control", headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(control_request) as response:
            assert json.loads(response.read())["sync_paused"] is False
        report_request = urllib.request.Request(
            f"{base}/v1/replica/report",
            data=json.dumps(
                {
                    "contract": "fragarach_lite.report.v1",
                    "reported_at_utc": "2026-08-06T00:00:00Z",
                    "state": "READY",
                    "service": {},
                    "replica": None,
                    "lanes": [],
                }
            ).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(report_request) as response:
            assert json.loads(response.read())["state"] == "RECORDED"
        assert registry_status(paths)["clients"][0]["report"]["state"] == "READY"
        payload_request = urllib.request.Request(
            f"{base}/v1/replica/publications/{manifest['publication_id']}/payload",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(payload_request) as response:
            body = response.read()
            assert response.headers["X-Content-SHA256"] == manifest["payload"]["sha256"]
            assert hashlib.sha256(body).hexdigest() == manifest["payload"]["sha256"]
        snapshot_request = urllib.request.Request(
            f"{base}/v1/replica/snapshots/{manifest['authority_revision']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(snapshot_request) as response:
            assert hashlib.sha256(response.read()).hexdigest() == manifest["payload"]["sha256"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_replica_operational_controls_are_visible_without_authority_writes(tmp_path: Path) -> None:
    database, paths = _fixture(tmp_path)
    before = database.read_bytes()
    add_client(paths, client_id="macbook-pro", display_name="MacBook")
    set_client_sync_paused(paths, "macbook-pro", True)
    request_client_refresh(paths, "macbook-pro")
    set_client_lane_paused(paths, "macbook-pro", "audusd", "d1", True)
    client = registry_status(paths)["clients"][0]
    assert client["control"] == {
        "sync_paused": True,
        "refresh_generation": 1,
        "paused_lanes": [{"symbol": "AUDUSD", "timeframe": "D1"}],
    }
    assert database.read_bytes() == before


def test_launch_agent_is_independent_loopback_only_and_does_not_mutate_authority(tmp_path: Path) -> None:
    database, replica_paths = _fixture(tmp_path)
    before = database.read_bytes()
    lifecycle = PublisherLifecyclePaths.create(replica_paths, home=tmp_path / "home")
    definition = launch_agent_definition(
        lifecycle,
        python="/usr/bin/python3",
        repository=tmp_path / "Fragarach_2",
    )

    assert definition["Label"] == "com.raymorgan.fragarach-ii.replica-publisher"
    assert definition["ProgramArguments"][-4:] == ["--host", "127.0.0.1", "--port", "9462"]
    assert "scheduler" not in " ".join(definition["ProgramArguments"])
    assert publisher_service_status(lifecycle)["state"] == "NOT_INSTALLED"
    assert database.read_bytes() == before


def test_selective_registry_recovers_interruption_and_supports_retry_pause_resume(tmp_path: Path) -> None:
    _, paths = _fixture(tmp_path)
    add_client(paths, client_id="macbook-pro", display_name="MacBook")
    request = submit_request(
        paths, "macbook-pro",
        {"request_id": "12345678-1234-4123-8123-123456789abc",
         "symbol": "AUDUSD", "timeframe": "D1"},
    )
    expected = request["expected_bytes"]
    request = update_request(paths, "macbook-pro", request["request_id"],
                             {"state": "TRANSFERRING", "transferred_bytes": expected // 2})
    assert request["state"] == "TRANSFERRING"
    assert request["transferred_bytes"] == expected // 2

    recover_registry(paths)
    recovered = registry_status(paths)["clients"][0]["control"]
    assert recovered is not None
    request = next(item for item in json.loads(paths.registry.read_text())["clients"][0]["requests"]
                   if item["request_id"] == request["request_id"])
    assert request["state"] == "ACCEPTED"
    assert request["transferred_bytes"] == 0

    request = update_request(paths, "macbook-pro", request["request_id"],
                             {"state": "FAILED", "transferred_bytes": 0,
                              "error": {"code": "NETWORK_INTERRUPTED"}})
    request = update_request(paths, "macbook-pro", request["request_id"],
                             {"state": "ACCEPTED", "transferred_bytes": 0})
    assert request["attempt"] == 2
    request = update_request(paths, "macbook-pro", request["request_id"],
                             {"state": "PAUSED", "transferred_bytes": 0})
    assert request["state"] == "PAUSED"
    request = update_request(paths, "macbook-pro", request["request_id"],
                             {"state": "ACCEPTED", "transferred_bytes": 0})
    assert request["state"] == "ACCEPTED"
