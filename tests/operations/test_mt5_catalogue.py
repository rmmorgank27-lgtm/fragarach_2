from __future__ import annotations

import json
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from fragarach_ii.mt5_bridge_queue import (
    FUSION_NON_INDEX_AUTHORITY_REFERENCE, MT5BridgeQueueError, _validate_response,
    bridge_paths, checksum, drain_received_responses, enqueue_request, poll_request,
)
from fragarach_ii.mt5_bridge_requests import (
    MINIMUM_SECONDS,
    active_fallback_grants,
    archive_expired_requests,
    enqueue_operator_request,
    grant_mt5_fallback,
    has_reviewed_twelve_data_fallback,
)
from fragarach_ii.mt5_catalogue import accept_catalogue, authorised_lanes, catalogue_paths
from fragarach_ii.mt5_route_manifest import (
    approved_route, is_mt5_primary_lane, provider_order, reviewed_primary_routes,
)
from fragarach_ii.mt5_bridge_requests import enqueue_due_requests
from fragarach_ii.provider_attempt_ledger import ProviderAttemptLedger
from fragarach_ii.lane_update_register import LaneUpdateRegister
from fragarach_ii.estate_truth_service import _mt5_bridge_capability_rows
from fragarach_ii.replica_publication import add_client, set_publisher_enabled
from fragarach_ii.replica_publisher_service import _handler
from tests.operations.test_read_only_clients import _fixture


def test_explicit_xom_intraday_overlay_is_a_reviewed_route() -> None:
    route = approved_route("XOM", "US_EQUITIES", "M5")
    assert route is not None
    assert route["provider_symbol"] == "ExxonMobil.r"
    assert route["authority_source"] == "XOM_FUSION_INTRADAY_OVERLAY_OPERATOR_APPROVED_2026-09-14"
    assert approved_route("XOM", "US_EQUITIES", "D1") is None


def _catalogue(*, xom_authorised: bool = True) -> dict:
    symbols = [
        {
            "provider_symbol": "ExxonMobil.r",
            "market_watch_selected": True,
            "bridge_authorized": xom_authorised,
            "canonical_symbol": "XOM" if xom_authorised else None,
            "bridge_native_timeframes": ["D1", "H1", "M30", "M5"] if xom_authorised else [],
            "description": "Exxon Mobil Corporation",
        },
        {
            "provider_symbol": "US30.r",
            "market_watch_selected": True,
            "bridge_authorized": True,
            "canonical_symbol": "US30",
            "bridge_native_timeframes": ["D1", "H1", "M30", "M5"],
        },
    ]
    body = {
        "contract": "fragarach.mt5_symbol_catalogue.v0.1",
        "generated_at_utc": "2026-09-09T00:00:00Z",
        "source_route": "registered_standard_data_primary",
        "terminal_route": "verified-live-terminal",
        "broker_family": "approved-index-data-broker-family-v1",
        "account_profile": "STANDARD_NON_TRADING_DATA",
        "broker": "FMGP Trading Group Pty Ltd",
        "server": "FusionMarketsAU-Live",
        "fingerprint_sha256": "a" * 64,
        "terminal_capabilities": {},
        "availability_semantics": {},
        "symbol_count": len(symbols),
        "bridge_authorized_count": sum(row["bridge_authorized"] for row in symbols),
        "symbols": symbols,
    }
    return {**body, "catalog_sha256": checksum(body)}


def _eightcap_catalogue() -> dict:
    estate = [
        "ADAUSD", "AVAXUSD", "BNBUSD", "BTCUSD", "DOGEUSD", "DOTUSD", "ETHUSD",
        "LINKUSD", "PEPEUSD", "SOLUSD", "SUIUSD", "XRPUSD",
    ]
    symbols = [{
        "provider_symbol": symbol,
        "market_watch_selected": True,
        "bridge_authorized": True,
        "canonical_symbol": symbol,
        "bridge_native_timeframes": ["D1", "H1", "M30", "M5"],
    } for symbol in estate]
    body = {
        "contract": "fragarach.mt5_symbol_catalogue.v0.1",
        "generated_at_utc": "2026-09-15T00:00:00Z",
        "source_route": "eightcap_standard_data_primary",
        "terminal_route": "verified-eightcap-live-terminal",
        "broker_family": "eightcap-live-crypto-v1",
        "account_profile": "STANDARD_NON_TRADING_DATA",
        "broker": "Eightcap Pty Ltd", "server": "Eightcap-Live",
        "fingerprint_sha256": "b" * 64,
        "terminal_capabilities": {}, "availability_semantics": {},
        "symbol_count": len(symbols), "bridge_authorized_count": len(symbols),
        "symbols": symbols,
    }
    return {**body, "catalog_sha256": checksum(body)}


def test_catalogue_is_immutable_and_drives_only_explicitly_authorised_aliases(tmp_path: Path) -> None:
    value = _catalogue()
    acknowledgement = accept_catalogue(tmp_path, value)

    assert acknowledgement == {"status": "ACCEPTED", "catalog_sha256": value["catalog_sha256"]}
    assert ("XOM", "D1") not in authorised_lanes(tmp_path)
    assert authorised_lanes(tmp_path)[("XOM", "H1")] == "ExxonMobil.r"
    assert authorised_lanes(tmp_path)[("XOM", "M30")] == "ExxonMobil.r"
    assert authorised_lanes(tmp_path)[("XOM", "M5")] == "ExxonMobil.r"
    assert authorised_lanes(tmp_path)[("US30", "M5")] == "US30.r"
    assert catalogue_paths(tmp_path)["history"].joinpath(f"{value['catalog_sha256']}.json").is_file()

    changed = json.loads(json.dumps(value))
    changed["symbols"][0]["provider_symbol"] = "invented"
    with pytest.raises(MT5BridgeQueueError, match="CATALOGUE_CHECKSUM_MISMATCH"):
        accept_catalogue(tmp_path, changed)

    request = enqueue_request(
        tmp_path, symbol="XOM", timeframe="H1",
        start_utc="2026-09-01T00:00:00Z", end_utc="2026-09-08T00:00:00Z",
    )
    assert request["canonical_symbol"] == "XOM"
    assert request["provider_symbol"] == "ExxonMobil.r"

    with pytest.raises(MT5BridgeQueueError, match="OUTSIDE_APPROVED_NATIVE_SCOPE"):
        enqueue_request(
            tmp_path, symbol="XOM", timeframe="D1",
            start_utc="2026-09-01T00:00:00Z", end_utc="2026-09-08T00:00:00Z",
        )


def test_unapproved_catalogue_listing_cannot_be_requested(tmp_path: Path) -> None:
    accept_catalogue(tmp_path, _catalogue(xom_authorised=False))
    with pytest.raises(MT5BridgeQueueError, match="CATALOGUE_ROUTE_NOT_AVAILABLE"):
        enqueue_request(
            tmp_path, symbol="XOM", timeframe="H1",
            start_utc="2026-09-01T00:00:00Z", end_utc="2026-09-08T00:00:00Z",
        )


def test_mt5_primary_manifest_makes_reviewed_index_daily_routes_broker_primary() -> None:
    routes = reviewed_primary_routes()
    assert routes[("US30", "M5")] == "US30.r"
    assert routes[("US30", "D1")] == "US30.r"
    assert is_mt5_primary_lane("US30", "D1", provider_symbol="US30.r")
    assert not is_mt5_primary_lane("US30", "D1", provider_symbol="US30")
    assert is_mt5_primary_lane("XOM", "H1", provider_symbol="ExxonMobil.r")
    assert is_mt5_primary_lane("XOM", "M30", provider_symbol="ExxonMobil.r")
    assert is_mt5_primary_lane("XOM", "M5", provider_symbol="ExxonMobil.r")
    assert not is_mt5_primary_lane("XOM", "D1", provider_symbol="ExxonMobil.r")
    assert not is_mt5_primary_lane("US30", "M5", provider_symbol="US30")
    assert approved_route("AUDUSD", "FX", "M5")["provider_symbol"] == "AUDUSD.r"
    assert approved_route("USOIL", "ENERGY", "H1")["provider_symbol"] == "XTIUSD.r"
    assert approved_route("USO", "ENERGY", "H1") is None
    assert is_mt5_primary_lane(
        "AUDUSD", "D1", provider_symbol="AUDUSD.r", asset_class="FX",
    )
    assert is_mt5_primary_lane(
        "XAUUSD", "D1", provider_symbol="XAUUSD.r", asset_class="METALS",
    )
    assert is_mt5_primary_lane(
        "USOIL", "D1", provider_symbol="XTIUSD.r", asset_class="ENERGY",
    )
    assert provider_order("FX", "D1") == ("MT5_BRIDGE", "YAHOO_FINANCE", "TWELVE_DATA")
    assert provider_order("US_EQUITIES", "D1") == ("MT5_BRIDGE", "YAHOO_FINANCE", "TWELVE_DATA")


def test_eightcap_crypto_uses_its_own_queue_and_exact_symbols_on_every_lane(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE instrument_registrations "
            "(asset TEXT, timeframe TEXT, asset_class TEXT)"
        )
        for symbol in ("BTCUSD", "SOLUSD", "HYPEUSD"):
            connection.execute(
                "INSERT INTO instrument_registrations VALUES(?,?,?)",
                (symbol, "D1", "CRYPTO"),
            )
    support = tmp_path / "support"
    accept_catalogue(support, _catalogue())
    accept_catalogue(support, _eightcap_catalogue(), node_id="eightcap-mt5-bridge")

    routes = authorised_lanes(support, database=database)
    assert all(("BTCUSD", lane) in routes for lane in ("D1", "H1", "M30", "M5"))
    assert not any(symbol == "HYPEUSD" for symbol, _ in routes)
    assert routes[("BTCUSD", "M5")] == "BTCUSD"
    assert approved_route("BTCUSD", "CRYPTO", "M5")["node_id"] == "eightcap-mt5-bridge"
    assert provider_order("CRYPTO", "M5") == (
        "MT5_BRIDGE", "BINANCE", "COINGECKO_DEX", "COINGECKO",
        "YAHOO_FINANCE", "TWELVE_DATA",
    )
    assert provider_order("CRYPTO", "D1")[-1] == "TWELVE_DATA"

    request = enqueue_request(
        support, database=database, symbol="BTCUSD", timeframe="M5",
        start_utc="2026-09-15T00:00:00Z", end_utc="2026-09-15T01:00:00Z",
    )
    eightcap_path = bridge_paths(support, "eightcap-mt5-bridge")["pending"] / f"{request['request_id']}.json"
    assert eightcap_path.is_file()
    assert request["source_route"] == "eightcap_standard_data_primary"
    assert request["provider_symbol"] == "BTCUSD"
    assert not bridge_paths(support)["pending"].joinpath(f"{request['request_id']}.json").exists()


def test_unhealthy_fusion_does_not_prevent_eightcap_queueing(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE bars (asset TEXT, timeframe TEXT, open_time_utc INTEGER)")
        connection.execute(
            "CREATE TABLE instrument_registrations "
            "(asset TEXT, timeframe TEXT, asset_class TEXT)"
        )
        connection.execute("INSERT INTO instrument_registrations VALUES('BTCUSD','D1','CRYPTO')")
    support = tmp_path / "support"
    accept_catalogue(support, _catalogue())
    accept_catalogue(support, _eightcap_catalogue(), node_id="eightcap-mt5-bridge")

    report = enqueue_due_requests(
        database, support, tmp_path / "state.json",
        at=datetime(2026, 9, 16, 12, tzinfo=UTC),
        eligible_node_ids={"eightcap-mt5-bridge"},
    )

    assert report["queued"]
    assert all(item["lane"].startswith("BTCUSD:") for item in report["queued"])
    assert not list(bridge_paths(support)["pending"].glob("*.json"))
    assert list(bridge_paths(support, "eightcap-mt5-bridge")["pending"].glob("*.json"))


def test_catalogue_confirmed_bridge_route_is_visible_to_estate_capability_truth(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    sqlite3.connect(database).close()
    support = Path(f"{database}.read-only-clients")
    accept_catalogue(support, _catalogue())

    rows = _mt5_bridge_capability_rows(database)
    us30 = next(row for row in rows if row["canonical_symbol"] == "US30" and row["timeframe"] == "M5")

    assert us30["provider"] == "MT5_BRIDGE"
    assert us30["provider_symbol"] == "US30.r"
    assert us30["capability_state"] == "SUPPORTED_WITH_APPROVED_MAPPING"
    assert us30["eligibility"] == "BRIDGE_SCHEDULED"


def test_mt5_scheduler_emits_only_reviewed_primary_lanes(tmp_path: Path) -> None:
    support = tmp_path / "support"
    accept_catalogue(support, _catalogue())
    database = tmp_path / "authority.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE bars (asset TEXT, timeframe TEXT, open_time_utc INTEGER)")
        connection.execute(
            "INSERT INTO bars VALUES('XOM','M5',1700000000)"
        )
        connection.commit()
    finally:
        connection.close()
    report = enqueue_due_requests(database, support, tmp_path / "state.json")
    assert {item["lane"] for item in report["queued"]} == {
        "US30:D1", "US30:H1", "US30:M30", "US30:M5",
        "XOM:H1", "XOM:M30", "XOM:M5",
    }
    xom_m5 = next(item for item in report["queued"] if item["lane"] == "XOM:M5")
    request = json.loads(
        bridge_paths(support)["pending"].joinpath(f"{xom_m5['request_id']}.json").read_text()
    )
    assert request["start_utc"] == datetime.fromtimestamp(1700000300, UTC).isoformat().replace("+00:00", "Z")


def test_mt5_d1_request_includes_next_broker_midnight(tmp_path: Path) -> None:
    support = tmp_path / "support"
    accept_catalogue(support, _catalogue())
    database = tmp_path / "authority.sqlite3"
    latest = datetime(2026, 9, 14, tzinfo=UTC)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE bars (asset TEXT, timeframe TEXT, open_time_utc INTEGER)")
        connection.execute(
            "INSERT INTO bars VALUES(?,?,?)", ("US30", "D1", int(latest.timestamp())),
        )
    report = enqueue_due_requests(
        database, support, tmp_path / "state.json",
        at=datetime(2026, 9, 16, 12, tzinfo=UTC),
    )
    item = next(row for row in report["queued"] if row["lane"] == "US30:D1")
    request = json.loads(
        (bridge_paths(support)["pending"] / f"{item['request_id']}.json").read_text()
    )
    assert request["start_utc"] == "2026-09-14T20:00:00Z"


def test_fusion_authority_cutover_preserves_index_and_legacy_receipts(tmp_path: Path) -> None:
    support = tmp_path / "support"
    accept_catalogue(support, _catalogue())
    database = tmp_path / "authority.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE bars (asset TEXT, timeframe TEXT, open_time_utc INTEGER)")
    bounds = {
        "start_utc": "2026-09-15T00:00:00Z",
        "end_utc": "2026-09-15T01:00:00Z",
    }
    non_index = enqueue_request(
        support, database=database, symbol="XOM", timeframe="M5", **bounds,
    )
    index = enqueue_request(
        support, database=database, symbol="US30", timeframe="M5", **bounds,
    )
    old_index_reference = (
        "MT5_BROKER_FAMILY_INDEX_CFD_AUTHORITY_V1:"
        "2c5dc7e112b1a3ca761efb2bcb467a862e477fe74a3d9b69601c588b72b0da09"
    )
    assert non_index["authority_reference"] == FUSION_NON_INDEX_AUTHORITY_REFERENCE
    assert index["authority_reference"] == old_index_reference

    def response_for(request: dict) -> dict:
        response = {
            "contract": "fragarach.mt5_evidence_response.v0.4",
            "request_id": request["request_id"], "request_sha256": checksum(request),
            "status": "FULFILLED", "captured_at_utc": "2026-09-15T01:00:01Z",
            **{key: request[key] for key in (
                "authority_reference", "operation", "canonical_symbol", "provider_symbol",
                "timeframe", "start_utc", "end_utc", "completed_bars_only",
                "timestamp_semantics", "source_route",
            )},
            "terminal_route": "verified-live-terminal",
            "broker_family": "approved-index-data-broker-family-v1",
            "account_profile": "STANDARD_NON_TRADING_DATA", "trading_permitted": False,
            "broker": "FMGP Trading Group Pty Ltd", "server": "FusionMarketsAU-Live",
            "fingerprint_sha256": "a" * 64, "terminal_capabilities": {},
            "completion_evidence": {"timestamp_semantics": request["timestamp_semantics"], "bars": []},
            "evidence": [],
        }
        response["response_sha256"] = checksum(response)
        return response

    assert _validate_response(response_for(non_index), non_index)[1] == []
    assert _validate_response(response_for(index), index)[1] == []
    legacy = {**non_index, "authority_reference": old_index_reference}
    assert _validate_response(response_for(legacy), legacy)[1] == []
    with pytest.raises(MT5BridgeQueueError, match="REQUEST_AUTHORITY_SCOPE_MISMATCH"):
        crossed = {**index, "authority_reference": FUSION_NON_INDEX_AUTHORITY_REFERENCE}
        _validate_response(response_for(crossed), crossed)
    with pytest.raises(MT5BridgeQueueError, match="REQUEST_AUTHORITY_SCOPE_MISMATCH"):
        arbitrary = {**non_index, "authority_reference": "UNREVIEWED:arbitrary"}
        _validate_response(response_for(arbitrary), arbitrary)


def test_mt5_request_cadence_matches_closed_bar_cadence() -> None:
    assert MINIMUM_SECONDS == {"D1": 3600, "H1": 3600, "M30": 1800, "M5": 300}


def test_operator_force_request_uses_catalogue_route_and_deduplicates_lane(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    sqlite3.connect(database).close()
    support = Path(f"{database}.read-only-clients")
    accept_catalogue(support, _catalogue())

    first = enqueue_operator_request(
        database,
        support,
        symbol="XOM",
        timeframe="H1",
        start_utc="2026-09-01T00:00:00Z",
        end_utc="2026-09-08T00:00:00Z",
    )
    second = enqueue_operator_request(
        database,
        support,
        symbol="XOM",
        timeframe="H1",
        start_utc="2026-09-02T00:00:00Z",
        end_utc="2026-09-09T00:00:00Z",
    )

    assert first is not None and first["outcome"] == "MT5_BRIDGE_QUEUED"
    assert first["provider"] == "MT5_BRIDGE"
    assert first["provider_symbol"] == "ExxonMobil.r"
    assert second is not None and second["outcome"] == "MT5_BRIDGE_REQUEST_ALREADY_PENDING"
    assert second["request_id"] == first["request_id"]
    assert len(list(bridge_paths(support)["pending"].glob("*.json"))) == 1


def test_operator_same_day_range_becomes_one_complete_bridge_day(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    sqlite3.connect(database).close()
    support = Path(f"{database}.read-only-clients")
    accept_catalogue(support, _catalogue())

    result = enqueue_operator_request(
        database,
        support,
        symbol="XOM",
        timeframe="M5",
        start_utc="2026-09-08",
        end_utc="2026-09-08",
    )

    assert result is not None and result["outcome"] == "MT5_BRIDGE_QUEUED"
    assert result["requested_range"] == {
        "start": "2026-09-08T00:00:00Z",
        "end": "2026-09-09T00:00:00Z",
    }


def test_operator_force_request_rejects_non_primary_stock_d1_bridge_route(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    sqlite3.connect(database).close()
    support = Path(f"{database}.read-only-clients")
    accept_catalogue(support, _catalogue())

    assert enqueue_operator_request(
        database,
        support,
        symbol="XOM",
        timeframe="D1",
        start_utc="2026-09-01T00:00:00Z",
        end_utc="2026-09-08T00:00:00Z",
    ) is None


def test_expired_request_is_archived_and_does_not_block_lane_retry(tmp_path: Path) -> None:
    accept_catalogue(tmp_path, _catalogue())
    request = enqueue_request(
        tmp_path, symbol="US30", timeframe="M5",
        start_utc="2026-09-01T00:00:00Z", end_utc="2026-09-08T00:00:00Z",
        expires_in_seconds=1,
    )
    archived = archive_expired_requests(
        tmp_path, at=datetime.now(UTC) + timedelta(seconds=2),
    )

    assert archived == [{"request_id": request["request_id"], "lane": "US30:M5"}]
    assert not bridge_paths(tmp_path)["pending"].joinpath(f"{request['request_id']}.json").exists()
    receipt = bridge_paths(tmp_path)["expired"].joinpath(f"{request['request_id']}.json")
    assert json.loads(receipt.read_text(encoding="utf-8")) == request


def test_pending_primary_is_not_requeued_and_index_without_equivalent_fails_closed(tmp_path: Path) -> None:
    support = tmp_path / "support"
    accept_catalogue(support, _catalogue())
    database = tmp_path / "authority.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE bars (asset TEXT, timeframe TEXT, open_time_utc INTEGER)")
        connection.commit()
    finally:
        connection.close()
    state = tmp_path / "state.json"

    observed = datetime.now(UTC).replace(microsecond=0)
    first = enqueue_due_requests(database, support, state, at=observed)
    us30 = next(item for item in first["queued"] if item["lane"] == "US30:M5")
    second = enqueue_due_requests(database, support, state, at=observed)
    assert us30["request_id"] in {item["request_id"] for item in second["pending"]}
    assert "US30:M5" not in {item["lane"] for item in second["queued"]}

    pending = bridge_paths(support)["pending"] / f"{us30['request_id']}.json"
    request = json.loads(pending.read_text())
    request["expires_at_utc"] = "2000-01-01T00:00:00Z"
    pending.write_text(json.dumps(request))
    expired = enqueue_due_requests(
        database, support, state, at=observed + timedelta(seconds=301),
    )

    assert "US30:M5" in {item["lane"] for item in expired["expired"]}
    assert "US30:M5" not in {item["lane"] for item in expired["fallback_grants"]}
    assert "US30:M5" in {item["lane"] for item in expired["queued"]}


def test_mt5_only_lane_stops_before_automatic_request_four(tmp_path: Path) -> None:
    support = tmp_path / "support"
    accept_catalogue(support, _catalogue())
    database = tmp_path / "authority.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE bars (asset TEXT, timeframe TEXT, open_time_utc INTEGER)")
    state = tmp_path / "state.json"
    observed = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    for index in range(3):
        report = enqueue_due_requests(
            database, support, state, at=observed + timedelta(seconds=301 * index),
        )
        request = next(item for item in report["queued"] if item["lane"] == "US30:M5")
        pending = bridge_paths(support)["pending"] / f"{request['request_id']}.json"
        payload = json.loads(pending.read_text(encoding="utf-8"))
        payload["expires_at_utc"] = "2000-01-01T00:00:00Z"
        pending.write_text(json.dumps(payload), encoding="utf-8")
    fourth = enqueue_due_requests(
        database, support, state, at=observed + timedelta(seconds=903),
    )
    assert "US30:M5" not in {item["lane"] for item in fourth["queued"]}
    assert any(
        item["lane"] == "US30:M5" and item["reason"] == "PROVIDER_ATTEMPT_LIMIT_REACHED"
        for item in fourth["attention"]
    )
    sample = request
    assert len(ProviderAttemptLedger(database).attempts(
        lane="US30:M5", expected_boundary=str(sample["expected_boundary"]),
        routing_revision=str(sample["routing_revision"]),
    )) == 3


def test_fallback_grant_requires_reviewed_exact_twelve_data_lane(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "CREATE TABLE bars (asset TEXT, timeframe TEXT, open_time_utc INTEGER, "
            "updated_by_ingest_run_id TEXT)"
        )
        connection.execute(
            "CREATE TABLE instrument_registrations "
            "(asset TEXT, timeframe TEXT, asset_class TEXT)"
        )
        connection.execute(
            "INSERT INTO instrument_registrations VALUES('AUDUSD','D1','FX')"
        )
        connection.commit()
    finally:
        connection.close()
    support = tmp_path / "support"
    catalogue = _catalogue()
    catalogue.pop("catalog_sha256")
    catalogue["symbols"].append({
        "provider_symbol": "AUDUSD.r",
        "market_watch_selected": True,
        "bridge_authorized": True,
        "canonical_symbol": "AUDUSD",
        "bridge_native_timeframes": ["D1", "H1", "M30", "M5"],
    })
    catalogue["symbol_count"] += 1
    catalogue["bridge_authorized_count"] += 1
    catalogue["catalog_sha256"] = checksum(catalogue)
    accept_catalogue(support, catalogue)
    database.with_suffix(".sqlite3.provider-facts.json").write_text(json.dumps({
        "contract": "fragarach_ii.provider_facts.v1",
        "resolver_version": 1,
        "revision": 1,
        "mappings": {
            "TWELVE_DATA:AUDUSD": {
                "status": "RESOLVED_AUTOMATICALLY",
                "mapping_class": "EXACT_REPRESENTATION",
                "provider_symbol": "AUD/USD",
                "provider_asset_class": "FOREX",
                "provider_instrument_type": "Physical Currency",
                "timeframe_capabilities": {"M5": {"supported": True}},
            },
            "TWELVE_DATA:US30": {
                "status": "REPRESENTATION_AMBIGUOUS",
                "mapping_class": None,
                "provider_symbol": None,
                "timeframe_capabilities": {},
            },
        },
    }))

    assert has_reviewed_twelve_data_fallback(
        database, symbol="AUDUSD", timeframe="M5",
    )
    assert not has_reviewed_twelve_data_fallback(
        database, symbol="US30", timeframe="M5",
    )
    assert grant_mt5_fallback(
        database,
        support,
        symbol="AUDUSD",
        timeframe="M5",
        reason="MT5_BRIDGE_REQUEST_EXPIRED",
    ) is not None
    assert grant_mt5_fallback(
        database,
        support,
        symbol="US30",
        timeframe="M5",
        reason="MT5_BRIDGE_REQUEST_EXPIRED",
    ) is None

    assert "AUDUSD:M5" in active_fallback_grants(database, support)
    register = LaneUpdateRegister(database)
    attempted = datetime.now(UTC) + timedelta(seconds=2)
    with sqlite3.connect(register.path) as connection:
        connection.execute(
            "INSERT INTO lane_update_register "
            "(asset,timeframe,state,last_attempted_at_utc,last_outcome,updated_at_utc) "
            "VALUES(?,?,?,?,?,?)",
            (
                "AUDUSD", "M5", "RETRY", attempted.isoformat(),
                "AUTO_PROVIDER_CYCLE:ALL_PROVIDERS_EXHAUSTED", attempted.isoformat(),
            ),
        )
    assert "AUDUSD:M5" not in active_fallback_grants(database, support)


def test_bridge_dispatch_is_fifo_by_issuance_not_random_request_uuid(tmp_path: Path) -> None:
    """An older lane must not be starved by lexically earlier random UUIDs."""
    paths = bridge_paths(tmp_path)
    newer = {
        "request_id": "00000000-0000-0000-0000-000000000000",
        "issued_at_utc": "2026-09-14T05:00:00Z",
    }
    older = {
        "request_id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "issued_at_utc": "2026-09-14T04:00:00Z",
    }
    paths["pending"].mkdir(parents=True)
    paths["pending"].joinpath(f"{newer['request_id']}.json").write_text(json.dumps(newer))
    paths["pending"].joinpath(f"{older['request_id']}.json").write_text(json.dumps(older))

    assert poll_request(tmp_path) == older


def test_bridge_dispatch_skips_durably_received_pending_request(tmp_path: Path) -> None:
    """Transport receipt is not admission, but must not be delivered twice."""
    paths = bridge_paths(tmp_path)
    received = {
        "request_id": "00000000-0000-0000-0000-000000000000",
        "issued_at_utc": "2026-09-14T04:00:00Z",
    }
    next_request = {
        "request_id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "issued_at_utc": "2026-09-14T04:01:00Z",
    }
    paths["pending"].mkdir(parents=True)
    paths["inbox"].mkdir(parents=True)
    paths["pending"].joinpath(f"{received['request_id']}.json").write_text(json.dumps(received))
    paths["pending"].joinpath(f"{next_request['request_id']}.json").write_text(json.dumps(next_request))
    paths["inbox"].joinpath("receipt.json").write_text(json.dumps({"request_id": received["request_id"]}))

    assert poll_request(tmp_path) == next_request


def test_catalogue_http_endpoint_is_separate_and_mt5_client_scoped(tmp_path: Path) -> None:
    database, paths = _fixture(tmp_path)
    mt5 = add_client(paths, client_id="tradewinds-mt5-bridge", display_name="MT5 MCP")
    other = add_client(paths, client_id="other-client", display_name="Other")
    set_publisher_enabled(paths, True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(paths))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/v1/mt5/catalogue"
    payload = json.dumps(_catalogue()).encode()
    try:
        denied = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": f"Bearer {other['issued_token']}", "Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(denied)
        assert error.value.code == 403

        request = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": f"Bearer {mt5['issued_token']}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            acknowledgement = json.loads(response.read())
        assert acknowledgement["catalog_sha256"] == _catalogue()["catalog_sha256"]
        assert database.is_file()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_eightcap_node_endpoints_are_separately_authenticated(tmp_path: Path) -> None:
    _database, paths = _fixture(tmp_path)
    eightcap = add_client(paths, client_id="eightcap-mt5-bridge", display_name="Eightcap MT5")
    fusion = add_client(paths, client_id="tradewinds-mt5-bridge", display_name="Fusion MT5")
    set_publisher_enabled(paths, True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(paths))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}/v1/mt5/nodes/eightcap-mt5-bridge"
    try:
        denied = urllib.request.Request(
            f"{base}/catalogue", data=json.dumps(_eightcap_catalogue()).encode(),
            headers={"Authorization": f"Bearer {fusion['issued_token']}"},
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(denied)
        assert error.value.code == 403

        accepted = urllib.request.Request(
            f"{base}/catalogue", data=json.dumps(_eightcap_catalogue()).encode(),
            headers={"Authorization": f"Bearer {eightcap['issued_token']}"},
        )
        with urllib.request.urlopen(accepted) as response:
            assert json.loads(response.read())["status"] == "ACCEPTED"

        poll = urllib.request.Request(
            f"{base}/evidence/requests/next",
            headers={"Authorization": f"Bearer {eightcap['issued_token']}"},
        )
        with urllib.request.urlopen(poll) as response:
            assert response.status == 204
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_mt5_response_endpoint_accepts_a_catalogue_authorised_empty_completion(tmp_path: Path) -> None:
    """The receiver must return an acknowledgement, never a server error, for a valid MT5 receipt."""
    database, paths = _fixture(tmp_path)
    mt5 = add_client(paths, client_id="tradewinds-mt5-bridge", display_name="MT5 MCP")
    set_publisher_enabled(paths, True)
    accept_catalogue(paths.support, _catalogue())
    queued = enqueue_request(
        paths.support, database=database, symbol="US30", timeframe="M5",
        start_utc="2026-09-01T00:00:00Z", end_utc="2026-09-08T00:00:00Z",
    )
    attempts = ProviderAttemptLedger(database)
    attempts.reserve(
        request_id=queued["request_id"], lane="US30:M5",
        expected_boundary="2026-09-08T00:00:00Z", routing_revision="test-revision",
        provider="MT5_BRIDGE",
    )
    attempts.mark_dispatched(queued["request_id"])
    body = {
        "contract": "fragarach.mt5_evidence_response.v0.4",
        "request_id": queued["request_id"], "request_sha256": checksum(queued),
        "status": "FULFILLED", "captured_at_utc": "2026-09-08T00:00:01Z",
        **{key: queued[key] for key in (
            "authority_reference", "operation", "canonical_symbol", "provider_symbol", "timeframe",
            "start_utc", "end_utc", "completed_bars_only", "timestamp_semantics", "source_route",
        )},
        "terminal_route": "verified-live-terminal",
        "broker_family": "approved-index-data-broker-family-v1",
        "account_profile": "STANDARD_NON_TRADING_DATA", "trading_permitted": False,
        "broker": "FMGP Trading Group Pty Ltd", "server": "FusionMarketsAU-Live",
        "fingerprint_sha256": "a" * 64, "terminal_capabilities": {},
        "completion_evidence": {"timestamp_semantics": queued["timestamp_semantics"], "bars": []},
        "evidence": [],
    }
    body["response_sha256"] = checksum(body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(paths))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/v1/mt5/evidence/responses",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {mt5['issued_token']}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            acknowledgement = json.loads(response.read())
        assert acknowledgement["status"] == "RECEIVED"
        assert acknowledgement["request_id"] == queued["request_id"]
        paths = bridge_paths(paths.support)
        assert paths["inbox"].joinpath(f"{body['response_sha256']}.json").is_file()
        drained = drain_received_responses(database, paths["root"].parent)
        assert drained == {"received": 1, "accepted": 1, "rejected": 0}
        assert paths["completed"].joinpath(f"{queued['request_id']}.json").is_file()
        assert attempts.attempts(
            lane="US30:M5", expected_boundary="2026-09-08T00:00:00Z",
            routing_revision="test-revision",
        )[0]["outcome"] == "MT5_BRIDGE_EMPTY_RESPONSE"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
