from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from fragarach_ii.external_consumer_service import HistoryService
from fragarach_ii.index_cfd_mt5 import (
    IndexCFDAdmissionError,
    SYMBOLS,
    TIMEFRAMES,
    load_package,
    process_receiver,
)
from fragarach_ii.storage import initialize_database, open_read_only


OPEN_TIMES = {
    "D1": datetime(2026, 9, 3, tzinfo=UTC),
    "H1": datetime(2026, 9, 4, 8, tzinfo=UTC),
    "M30": datetime(2026, 9, 4, 9, 30, tzinfo=UTC),
    "M15": datetime(2026, 9, 4, 9, 30, tzinfo=UTC),
    "M5": datetime(2026, 9, 4, 9, 50, tzinfo=UTC),
}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _package(
    receiver: Path, *, timestamp_status: str = "UTC_AUTHORITY_RESOLVED",
    timeframes: tuple[str, ...] = TIMEFRAMES, name: str = "test",
    provider: str = "FUSION_MARKETS", contract: str = "fragarach.mt5.market_data_package.v1",
    provider_route_id: str | None = "fusion_mt5_data_reader",
    account_profile: str | None = "STANDARD_NON_TRADING_DATA",
) -> dict[str, object]:
    message_id = "message-test-index-cfd"
    request_id = "request-test-index-cfd"
    export_run_id = "export-test-index-cfd"
    files: dict[str, bytes] = {}
    files["transport-envelope.json"] = _json_bytes({
        "contract": "datagather.tailscale_transport.v1",
        "lane": "divergence.market_data",
        "message_id": message_id,
        "request_id": request_id,
        "export_run_id": export_run_id,
    })
    manifest = {
        "contract": contract,
        "lane_id": "divergence.indices.native.v1",
        "provider": provider,
        "platform": "MT5",
        "request_id": request_id,
        "export_run_id": export_run_id,
        "native_timeframes": list(timeframes),
        "timestamp_status": timestamp_status,
        "timestamp_policy": "MT5_PYTHON_COPY_RATES_UNIX_UTC_V1",
        "source_method": "MetaTrader5.copy_rates_range",
        "exact_terminal_symbols": {
            symbol: {"name": symbol, "path": f"CFD-IndicesMini\\{symbol}"}
            for symbol in SYMBOLS
        },
    }
    if provider_route_id is not None:
        manifest["provider_route_id"] = provider_route_id
    if account_profile is not None:
        manifest["account_profile"] = account_profile
    files["manifest.json"] = _json_bytes(manifest)
    coverage: dict[str, object] = {"series": {}}
    for symbol_index, symbol in enumerate(SYMBOLS):
        for timeframe in timeframes:
            opened = int(OPEN_TIMES[timeframe].timestamp())
            value = 1000 + symbol_index * 100
            row = {
                "mt5_time": opened,
                "mt5_documented_utc_rendering": OPEN_TIMES[timeframe].isoformat(timespec="seconds").replace("+00:00", "Z"),
                "open": value,
                "high": value + 5,
                "low": value - 5,
                "close": value + 1,
                "tick_volume": 12,
                "spread": 2,
                "real_volume": 0,
            }
            name = f"payload/json/{symbol}_{timeframe}.jsonl"
            payload = _json_bytes(row)
            files[name] = payload
            coverage["series"][f"{symbol}_{timeframe}"] = {
                "row_count": 1,
                "first_raw_timestamp": opened,
                "last_raw_timestamp": opened,
                "native_timeframe": timeframe,
                "exact_provider_symbol": symbol,
                "canonical_label": symbol,
                "forming_bar_excluded": True,
                "strict_ordering": True,
                "unique": True,
                "per_file_sha256": {name: hashlib.sha256(payload).hexdigest()},
            }
    files["coverage-report.json"] = _json_bytes(coverage)
    files["SHA256SUMS.txt"] = "".join(
        f"{hashlib.sha256(payload).hexdigest()}  {name}\n"
        for name, payload in sorted(files.items())
    ).encode()

    accepted = receiver / "accepted" / "divergence-market_data" / f"{name}.zip"
    accepted.parent.mkdir(parents=True)
    with zipfile.ZipFile(accepted, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    package_sha = hashlib.sha256(accepted.read_bytes()).hexdigest()
    receipt = {
        "receipt_id": "receipt-test-index-cfd",
        "message_id": message_id,
        "request_id": request_id,
        "export_run_id": export_run_id,
        "lane": "divergence.market_data",
        "status": "ACCEPTED",
        "received_utc": "2026-09-04T10:00:36Z",
        "package_sha256": package_sha,
        "accepted_object": str(accepted.relative_to(receiver)),
    }
    receipts = receiver / "receipts"
    receipts.mkdir(parents=True)
    (receipts / f"receipt-{name}-index-cfd.json").write_text(json.dumps(receipt), encoding="utf-8")
    return receipt


def test_unresolved_timestamp_package_is_rejected(tmp_path: Path) -> None:
    receiver = tmp_path / "receiver"
    receipt = _package(receiver, timestamp_status="TIMESTAMP_AUTHORITY_UNRESOLVED")
    with pytest.raises(IndexCFDAdmissionError, match="TIMESTAMP_AUTHORITY_NOT_RESOLVED"):
        load_package(receiver / str(receipt["accepted_object"]), receipt)


def test_unapproved_provider_route_is_rejected(tmp_path: Path) -> None:
    receiver = tmp_path / "receiver"
    receipt = _package(receiver, provider="UNAPPROVED", contract="unapproved.mt5.v1")

    with pytest.raises(IndexCFDAdmissionError, match="UNAPPROVED_BROKER_FAMILY_ROUTE"):
        load_package(receiver / str(receipt["accepted_object"]), receipt)


def test_fusion_demo_route_is_rejected_for_data_collection(tmp_path: Path) -> None:
    receiver = tmp_path / "receiver"
    receipt = _package(
        receiver, provider="FUSION_MARKETS", contract="fragarach.mt5.market_data_package.v1",
        provider_route_id="fusion_mt5_demo1", account_profile="DEMO",
    )

    with pytest.raises(IndexCFDAdmissionError, match="UNAPPROVED_BROKER_FAMILY_ROUTE"):
        load_package(receiver / str(receipt["accepted_object"]), receipt)


def test_pre_m30_package_is_preserved_as_superseded_during_scope_transition(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    receiver = tmp_path / "receiver"
    state = tmp_path / "state.json"
    initialize_database(database)
    _package(receiver, timeframes=("D1", "H1", "M15", "M5"), name="legacy")

    result = process_receiver(database, receiver, state)

    assert result["status"] == "HEALTHY"
    assert result["admitted"] == []
    assert result["superseded"][0]["reason"] == "SUPERSEDED_BY_FOUR_NATIVE_TIMEFRAME_SCOPE"


def test_prior_native_m15_package_is_preserved_as_superseded(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    receiver = tmp_path / "receiver"
    state = tmp_path / "state.json"
    initialize_database(database)
    _package(receiver, timeframes=("D1", "H1", "M30", "M15", "M5"), name="native-m15")

    result = process_receiver(database, receiver, state)

    assert result["status"] == "HEALTHY"
    assert result["admitted"] == []
    assert result["superseded"][0]["reason"] == "SUPERSEDED_BY_FOUR_NATIVE_TIMEFRAME_SCOPE"


def test_exact_native_index_cfd_lanes_are_commissioned_published_and_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    receiver = tmp_path / "receiver"
    state = tmp_path / "state.json"
    initialize_database(database)
    _package(receiver)

    first = process_receiver(database, receiver, state)
    second = process_receiver(database, receiver, state)

    assert first["status"] == "HEALTHY"
    assert len(first["admitted"]) == 1
    assert first["admitted"][0]["changed_lane_count"] == 12
    assert set(first["admitted"][0]["publication"].values()) == {"PUBLISHED"}
    assert second["admitted"] == []
    assert "error" not in second["state"]
    assert "last_retry_reason" not in second["state"]
    with open_read_only(database) as connection:
        registrations = connection.execute(
            """SELECT asset,asset_class,representation_type,provider_id,
                      provider_contract,provider_symbol,
                      json_extract(identity_json,'$.selected_representation')
                 FROM instrument_registrations
                WHERE asset IN ('US30','US500','NAS100')
                ORDER BY asset"""
        ).fetchall()
        assert [tuple(row) for row in registrations] == [
            ("NAS100", "BROKER_INDEX_CFDS", "CFD", "MT5_BROKER_FAMILY", "MT5_BROKER_FAMILY_INDEX_CFD_DATA_V1", "NAS100", "NAS100"),
            ("US30", "BROKER_INDEX_CFDS", "CFD", "MT5_BROKER_FAMILY", "MT5_BROKER_FAMILY_INDEX_CFD_DATA_V1", "US30", "US30"),
            ("US500", "BROKER_INDEX_CFDS", "CFD", "MT5_BROKER_FAMILY", "MT5_BROKER_FAMILY_INDEX_CFD_DATA_V1", "US500", "US500"),
        ]
        lane_rows = connection.execute(
            """SELECT asset,timeframe,COUNT(*) FROM bars
                 WHERE asset IN ('US30','US500','NAS100')
                 GROUP BY asset,timeframe"""
        ).fetchall()
        assert {(row[0], row[1], row[2]) for row in lane_rows} == {
            (symbol, timeframe, 1) for symbol in SYMBOLS for timeframe in TIMEFRAMES
        }

    with open_read_only(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM bars WHERE asset='US30' AND timeframe='M15'"
        ).fetchone()[0] == 0
    m15 = HistoryService(database).get_history("US30", "M15")
    assert m15["status"] == "SYNTHETIC_NOT_PERMITTED"


def test_standard_fusion_data_reader_is_admitted_under_the_same_broker_family(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    receiver = tmp_path / "receiver"
    state = tmp_path / "state.json"
    initialize_database(database)
    _package(
        receiver, name="fusion", provider="FUSION_MARKETS",
        contract="fragarach.mt5.market_data_package.v1",
        provider_route_id="fusion_mt5_data_reader",
        account_profile="STANDARD_NON_TRADING_DATA",
    )

    result = process_receiver(database, receiver, state)

    admitted = result["admitted"][0]
    assert admitted["provider_family"] == "MT5_BROKER_FAMILY_INDEX_CFD_AUTHORITY_V1"
    assert admitted["provider_route"] == "fusion_mt5_data_reader"
