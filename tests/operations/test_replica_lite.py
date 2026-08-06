from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

import pytest

from fragarach_ii.replica_lite import (
    FragarachLiteError,
    LitePaths,
    configure_lite,
    control_lane_request,
    lane_catalogue,
    lite_status,
    market_history,
    request_lane,
    selective_active_lanes,
    store_client_token,
    sync_lite,
    sync_selective,
)
from fragarach_ii.replica_publication import (
    ReplicaPaths,
    add_client,
    create_full_snapshot,
    set_publisher_enabled,
)
from fragarach_ii.replica_publisher_service import _handler
from fragarach_ii.replica_lite_daemon import LiteLifecyclePaths, launch_agent_definition
from fragarach_ii.replica_lite_service import _handler as _lite_handler
from fragarach_ii.selective_replication import artifact_payload, submit_request, update_request
from tests.validation.test_d1_session_validation import _create_lane


def _system(tmp_path: Path):
    database = tmp_path / "authority.sqlite3"
    _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
    publisher = ReplicaPaths.for_database(database, support=tmp_path / "publisher")
    client = add_client(publisher, client_id="macbook-pro", display_name="MacBook")
    manifest = create_full_snapshot(publisher)
    set_publisher_enabled(publisher, True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(publisher))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    lite = LitePaths.create(tmp_path / "lite")
    configure_lite(
        lite,
        endpoint=f"http://127.0.0.1:{server.server_address[1]}",
        client_id="macbook-pro",
    )
    store_client_token(lite, client["issued_token"])
    return database, publisher, manifest, server, thread, lite


def _stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_lite_rejects_unsigned_and_insecure_by_default(tmp_path: Path) -> None:
    _, _, _, server, thread, lite = _system(tmp_path)
    try:
        with pytest.raises(FragarachLiteError) as insecure:
            sync_lite(lite)
        assert insecure.value.code == "INSECURE_TRANSPORT_FORBIDDEN"
        with pytest.raises(FragarachLiteError) as unsigned:
            sync_lite(lite, allow_insecure_transport=True)
        assert unsigned.value.code == "UNSIGNED_PUBLICATION_FORBIDDEN"
        assert lite_status(lite)["state"] == "NO_REPLICA"
    finally:
        _stop(server, thread)


def test_lite_admits_exact_snapshot_atomically_and_serves_bounded_history(tmp_path: Path) -> None:
    database, _, manifest, server, thread, lite = _system(tmp_path)
    before = database.read_bytes()
    try:
        receipt = sync_lite(lite, allow_unsigned=True, allow_insecure_transport=True)
        assert receipt["sync_outcome"] == "ADMITTED"
        assert receipt["origin_authority_revision"] == manifest["authority_revision"]
        assert database.read_bytes() == before
        repeat = sync_lite(lite, allow_unsigned=True, allow_insecure_transport=True)
        assert repeat["sync_outcome"] == "ALREADY_CURRENT"

        result = market_history(
            lite,
            symbol="audusd",
            timeframe="d1",
            start_utc="2026-07-09T00:00:00Z",
            end_utc_exclusive="2026-07-11T00:00:00Z",
            as_of_utc="2026-07-11T00:00:00Z",
        )
        assert result["status"] == "AVAILABLE_WITH_WARNINGS"
        assert result["bar_count"] == 2
        assert result["symbol"] == "AUDUSD"
        assert result["source_receipt"]["origin_authority_revision"] == manifest["authority_revision"]
        assert result["warnings"] == ["REPLICA_SIGNATURE_NOT_COMMISSIONED"]
        catalogue = lane_catalogue(lite)
        assert catalogue["state"] == "READY"
        audusd = next(
            lane for lane in catalogue["lanes"]
            if lane["symbol"] == "AUDUSD" and lane["timeframe"] == "D1"
        )
        assert audusd["bar_count"] == 2
        assert audusd["caodt"]
        lite.control.write_text(
            json.dumps(
                {
                    "contract": "fragarach.replica_control.v1",
                    "sync_paused": False,
                    "refresh_generation": 0,
                    "paused_lanes": [{"symbol": "AUDUSD", "timeframe": "D1"}],
                }
            )
        )
        assert lane_catalogue(lite)["lanes"][0]["state"] in {"AVAILABLE", "PAUSED"}
        paused = market_history(
            lite,
            symbol="AUDUSD",
            timeframe="D1",
            start_utc="2026-07-09T00:00:00Z",
            end_utc_exclusive="2026-07-11T00:00:00Z",
            as_of_utc="2026-07-11T00:00:00Z",
        )
        assert paused["status"] == "LANE_PAUSED"
    finally:
        _stop(server, thread)


def test_failed_tampered_download_preserves_active_replica(tmp_path: Path) -> None:
    _, publisher, first, server, thread, lite = _system(tmp_path)
    try:
        admitted = sync_lite(lite, allow_unsigned=True, allow_insecure_transport=True)
        create_full_snapshot(publisher, symbols=["AUDUSD"], timeframes=["D1"])
        head = json.loads(publisher.head.read_text())
        publication = publisher.publications / head["publication_id"]
        manifest_path = publication / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        fake_revision = "sha256:" + "1" * 64
        head["authority_revision"] = fake_revision
        manifest["authority_revision"] = fake_revision
        publisher.head.write_text(json.dumps(head))
        manifest_path.write_text(json.dumps(manifest))
        payload = publication / head["payload"]["path"]
        with payload.open("ab") as stream:
            stream.write(b"tamper")
        with pytest.raises(FragarachLiteError) as failure:
            sync_lite(lite, allow_unsigned=True, allow_insecure_transport=True)
        assert failure.value.code == "PAYLOAD_FINGERPRINT_MISMATCH"
        status = lite_status(lite)
        assert status["active_replica"]["origin_authority_revision"] == admitted["origin_authority_revision"]
        assert status["active_replica"]["publication_id"] == first["publication_id"]
    finally:
        _stop(server, thread)


def test_offline_status_retains_last_verified_replica(tmp_path: Path) -> None:
    _, _, _, server, thread, lite = _system(tmp_path)
    sync_lite(lite, allow_unsigned=True, allow_insecure_transport=True)
    _stop(server, thread)

    status = lite_status(lite)
    assert status["state"] == "READY"
    result = market_history(
        lite,
        symbol="AUDUSD",
        timeframe="D1",
        start_utc="2026-07-09T00:00:00Z",
        end_utc_exclusive="2026-07-11T00:00:00Z",
        as_of_utc="2026-07-11T00:00:00Z",
    )
    assert result["bar_count"] == 2


def test_local_service_exposes_bounded_history_and_rejects_bad_requests(tmp_path: Path) -> None:
    _, _, _, publisher_server, publisher_thread, lite = _system(tmp_path)
    sync_lite(lite, allow_unsigned=True, allow_insecure_transport=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _lite_handler(lite))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/health") as response:
            assert json.loads(response.read())["state"] == "READY"
        with urllib.request.urlopen(f"{base}/v1/catalogue") as response:
            assert json.loads(response.read())["lanes"][0]["symbol"] == "AUDUSD"
        query = urlencode(
            {
                "symbol": "AUDUSD",
                "timeframe": "D1",
                "start_utc": "2026-07-09T00:00:00Z",
                "end_utc_exclusive": "2026-07-11T00:00:00Z",
                "as_of_utc": "2026-07-11T00:00:00Z",
            }
        )
        with urllib.request.urlopen(f"{base}/v1/market-history?{query}") as response:
            result = json.loads(response.read())
        assert result["bar_count"] == 2
        assert result["source_receipt"]["origin_authority_revision"]
        with pytest.raises(urllib.error.HTTPError) as bad_request:
            urllib.request.urlopen(f"{base}/v1/market-history?symbol=AUDUSD")
        assert bad_request.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        _stop(publisher_server, publisher_thread)


def test_lite_launch_agent_is_loopback_and_independent(tmp_path: Path) -> None:
    paths = LitePaths.create(tmp_path / "lite")
    lifecycle = LiteLifecyclePaths.create(paths, home=tmp_path / "home")
    definition = launch_agent_definition(
        lifecycle,
        python="/usr/bin/python3",
        repository=tmp_path / "Fragarach_2",
        sync_interval=600,
    )
    arguments = definition["ProgramArguments"]
    assert definition["Label"] == "com.raymorgan.fragarach-lite"
    assert ["--host", "127.0.0.1"] == arguments[arguments.index("--host") : arguments.index("--host") + 2]
    assert "scheduler" not in " ".join(arguments).lower()
    assert "--allow-unsigned" not in arguments


def test_lite_lane_requests_are_timestamped_lifecycle_state(tmp_path: Path) -> None:
    paths = LitePaths.create(tmp_path / "lite")
    requests = request_lane(paths, symbol="eurusd", timeframe="h1")
    assert len(requests) == 1
    assert requests[0]["symbol"] == "EURUSD"
    assert requests[0]["timeframe"] == "H1"
    assert requests[0]["state"] == "REQUESTED"
    assert requests[0]["request_id"]
    assert requests[0]["expected_bytes"] == 0
    assert requests[0]["transferred_bytes"] == 0
    assert requests[0]["verified_bytes"] == 0
    assert requests[0]["requested_at_utc"]
    assert json.loads(paths.requests.read_text()) == requests


def test_selective_transfer_admits_two_requested_lanes_and_never_fetches_third(tmp_path: Path) -> None:
    _, publisher, _, server, thread, lite = _system(tmp_path)
    try:
        request_lane(lite, symbol="AUDUSD", timeframe="D1")
        request_lane(lite, symbol="XAUUSD", timeframe="D1")
        result = sync_selective(
            lite, allow_unsigned=True, allow_insecure_transport=True
        )

        assert result["admitted"] == 2
        active = selective_active_lanes(lite)
        assert {(item["symbol"], item["timeframe"]) for item in active} == {
            ("AUDUSD", "D1"), ("XAUUSD", "D1")
        }
        assert all(item["expected_bytes"] == item["transferred_bytes"] == item["verified_bytes"]
                   and item["expected_bytes"] > 0 for item in active)
        registry = result["registry"]
        assert len(registry["available_lanes"]) >= 3
        assert {item["state"] for item in registry["requests"]} == {"ACTIVE"}
        assert not any(item["symbol"] == "BTCUSD" for item in registry["requests"])
        assert len(list(lite.lane_artifacts.glob("*.sqlite3"))) == 2
        assert not any("BTCUSD" in path.name for path in publisher.support.rglob("*"))
        missing = market_history(
            lite, symbol="BTCUSD", timeframe="D1",
            start_utc="2026-07-09T00:00:00Z",
            end_utc_exclusive="2026-07-11T00:00:00Z",
            as_of_utc="2026-07-11T00:00:00Z",
        )
        assert missing["status"] == "NO_REPLICA"
    finally:
        _stop(server, thread)


def test_v2_registry_stops_presenting_legacy_full_snapshot_as_selective_local_lanes(tmp_path: Path) -> None:
    _, _, _, server, thread, lite = _system(tmp_path)
    try:
        sync_lite(lite, allow_unsigned=True, allow_insecure_transport=True)
        assert len(lane_catalogue(lite)["lanes"]) >= 3

        sync_selective(lite, allow_unsigned=True, allow_insecure_transport=True)
        catalogue = lane_catalogue(lite)
        assert catalogue["replication_mode"] == "SELECTIVE_V2"
        assert catalogue["lanes"] == []
        assert len(catalogue["available_lanes"]) >= 3
        assert catalogue["requests"] == []
        assert catalogue["incoming_data"] == []
        status = lite_status(lite)
        assert status["replication_mode"] == "SELECTIVE_V2"
        assert status["state"] == "NO_REPLICA"
        assert status["active_replica"] is None
        history = market_history(
            lite, symbol="AUDUSD", timeframe="D1",
            start_utc="2026-07-09T00:00:00Z",
            end_utc_exclusive="2026-07-11T00:00:00Z",
            as_of_utc="2026-07-11T00:00:00Z",
        )
        assert history["status"] == "NO_REPLICA"
    finally:
        _stop(server, thread)


def test_pending_request_is_visible_before_studio_acceptance(tmp_path: Path) -> None:
    _, _, _, server, thread, lite = _system(tmp_path)
    try:
        sync_selective(lite, allow_unsigned=True, allow_insecure_transport=True)
        pending = request_lane(lite, symbol="AUDUSD", timeframe="D1")[0]

        catalogue = lane_catalogue(lite)

        assert catalogue["requests"] == [pending]
        assert catalogue["incoming_data"] == [pending]
        assert catalogue["requests"][0]["state"] == "REQUESTED"
    finally:
        _stop(server, thread)


def test_selective_active_lane_keeps_studio_asset_class(tmp_path: Path) -> None:
    _, _, _, server, thread, lite = _system(tmp_path)
    try:
        request_lane(lite, symbol="AUDUSD", timeframe="D1")
        sync_selective(lite, allow_unsigned=True, allow_insecure_transport=True)

        catalogue = lane_catalogue(lite)

        lane = next(item for item in catalogue["lanes"] if item["symbol"] == "AUDUSD")
        available = next(item for item in catalogue["available_lanes"] if item["symbol"] == "AUDUSD")
        assert lane["asset_class"] == available["asset_class"]
        assert lane["asset_class"] != "UNKNOWN"
    finally:
        _stop(server, thread)


def test_selective_verification_failure_preserves_previous_active_lane(tmp_path: Path) -> None:
    _, publisher, _, server, thread, lite = _system(tmp_path)
    try:
        request_lane(lite, symbol="AUDUSD", timeframe="D1")
        sync_selective(lite, allow_unsigned=True, allow_insecure_transport=True)
        before = selective_active_lanes(lite)

        pending = request_lane(lite, symbol="XAUUSD", timeframe="D1")[-1]
        accepted = submit_request(publisher, "macbook-pro", pending)
        payload = artifact_payload(publisher, accepted["artifact_id"])
        assert payload is not None
        with payload.open("ab") as stream:
            stream.write(b"tampered")

        with pytest.raises(FragarachLiteError) as failure:
            sync_selective(lite, allow_unsigned=True, allow_insecure_transport=True)
        assert failure.value.code in {"PAYLOAD_BYTE_COUNT_MISMATCH", "PAYLOAD_FINGERPRINT_MISMATCH"}
        after = selective_active_lanes(lite)
        assert after == before
        assert {(item["symbol"], item["timeframe"]) for item in after} == {("AUDUSD", "D1")}
        requests = json.loads(lite.requests.read_text())
        failed = next(item for item in requests if item["symbol"] == "XAUUSD")
        assert failed["state"] == "FAILED"
        assert failed["verified_bytes"] == 0
    finally:
        _stop(server, thread)


def test_selective_pause_retains_lane_resume_and_remove_are_explicit(tmp_path: Path) -> None:
    _, _, _, server, thread, lite = _system(tmp_path)
    try:
        request_lane(lite, symbol="AUDUSD", timeframe="D1")
        sync_selective(lite, allow_unsigned=True, allow_insecure_transport=True)
        database = Path(selective_active_lanes(lite)[0]["database"])

        paused = control_lane_request(lite, symbol="AUDUSD", timeframe="D1", action="PAUSE")
        assert paused["state"] == "PAUSED"
        assert database.is_file()
        resumed = control_lane_request(lite, symbol="AUDUSD", timeframe="D1", action="RESUME")
        assert resumed["state"] == "ACTIVE"
        removed = control_lane_request(lite, symbol="AUDUSD", timeframe="D1", action="REMOVE")
        assert removed["state"] == "REMOVED"
        assert selective_active_lanes(lite) == []
        assert not database.exists()
    finally:
        _stop(server, thread)


def test_lite_restart_recovers_in_progress_request_from_zero(tmp_path: Path) -> None:
    _, publisher, _, server, thread, lite = _system(tmp_path)
    try:
        pending = request_lane(lite, symbol="AUDUSD", timeframe="D1")[0]
        accepted = submit_request(publisher, "macbook-pro", pending)
        update_request(
            publisher, "macbook-pro", accepted["request_id"],
            {"state": "TRANSFERRING", "transferred_bytes": accepted["expected_bytes"] // 2},
        )

        result = sync_selective(lite, allow_unsigned=True, allow_insecure_transport=True)
        assert result["admitted"] == 1
        active = selective_active_lanes(lite)[0]
        assert active["expected_bytes"] == active["transferred_bytes"] == active["verified_bytes"]
        assert result["registry"]["requests"][0]["state"] == "ACTIVE"
    finally:
        _stop(server, thread)
