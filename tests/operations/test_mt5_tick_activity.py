from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.ingestion.pipeline import RawEvidence, ingest_staged_batch
from fragarach_ii.external_consumer_service import HistoryService
from fragarach_ii.mt5_bridge_queue import _atomic_json, bridge_paths, checksum, poll_request
from fragarach_ii.mt5_catalogue import accept_catalogue
from fragarach_ii.mt5_bridge_requests import enqueue_due_requests
from fragarach_ii.mt5_tick_activity import (
    ACTIVITY_SOURCE_LABEL,
    activity_coverage,
    activity_paths,
    admit_bridge_activity,
    queue_activity_backfill_requests,
    queue_continuous_activity_requests,
    start_activity_backfill,
)
from fragarach_ii.staging import StagedBar, StagingBatch
from fragarach_ii.storage import (
    RegistrationCandidate,
    initialize_database,
    open_read_only,
    register_instrument,
)


OPENED = int(datetime(2026, 9, 11, tzinfo=UTC).timestamp())


def _database(tmp_path: Path) -> Path:
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    register_instrument(
        database,
        RegistrationCandidate(
            asset="AUDUSD", timeframe="D1", instrument_family="AUDUSD", local_symbol="AUDUSD",
            display_name="Australian Dollar / US Dollar", instrument_type="FX_SPOT_PAIR",
            asset_class="FX", representation_type="FX_SPOT_PAIR", trading_currency="USD",
            exchange_name="OTC", provider_id="TWELVE_DATA",
            provider_contract="TWELVE_DATA_TIME_SERIES_D1_V1", provider_symbol="AUD/USD",
            provider_instrument_type="Physical Currency", calendar_id="FX_D1_V1",
            calendar_version=1, gap_doctrine_id="FRAGARACH_II_D1_GAP_DOCTRINE_V1",
            gap_doctrine_version=1,
        ),
        registered_at_utc="2026-09-11T01:00:00+00:00",
    )
    payload = b"twelve-data-price"
    raw_id = "raw-" + checksum({"payload": payload.decode()})
    ingest_staged_batch(
        database,
        batch=StagingBatch((StagedBar(
            symbol="AUDUSD", timeframe="D1", timestamp=OPENED,
            open="1.1", high="1.2", low="1.0", close="1.15", volume="999",
            source="TWELVE_DATA", provider="TWELVE_DATA", raw_block_id=raw_id,
            source_row_number=1, source_timestamp_text="2026-09-11",
            source_timezone_interpretation="UTC_DATE", received_at="2026-09-12T00:00:00+00:00",
        ),), (), 1, 0, 0),
        evidence=RawEvidence(
            raw_block_id=raw_id, checksum=__import__("hashlib").sha256(payload).hexdigest(),
            payload=payload, source_name="price.json", source_locator="fixture://price",
            media_type="application/json", received_at="2026-09-12T00:00:00+00:00",
        ),
        run_kind="test_price", merge_mode="preserve", outcome_facts={},
        preserve_rejected_evidence=True,
    )
    return database


def _catalogue() -> dict:
    symbols = [{
        "provider_symbol": "AUDUSD.r", "market_watch_selected": True,
        "bridge_authorized": True, "canonical_symbol": "AUDUSD",
        "bridge_native_timeframes": ["D1", "H1", "M30", "M5"],
    }]
    body = {
        "contract": "fragarach.mt5_symbol_catalogue.v0.1",
        "generated_at_utc": "2026-09-14T00:00:00Z",
        "source_route": "registered_standard_data_primary",
        "terminal_route": "verified-live-terminal",
        "broker_family": "approved-index-data-broker-family-v1",
        "account_profile": "STANDARD_NON_TRADING_DATA", "broker": "Fusion Markets",
        "server": "FusionMarketsAU-Live", "fingerprint_sha256": "a" * 64,
        "terminal_capabilities": {}, "availability_semantics": {},
        "symbol_count": 1, "bridge_authorized_count": 1, "symbols": symbols,
    }
    return {**body, "catalog_sha256": checksum(body)}


def _activity_receipt(tick_volume: int, suffix: str) -> tuple[dict, dict, dict, list[dict]]:
    request = {
        "canonical_symbol": "AUDUSD", "provider_symbol": "AUDUSD.r", "timeframe": "D1",
    }
    body = {
        "request_id": f"request-{suffix}", "captured_at_utc": "2026-09-12T00:05:00Z",
        "broker_family": "approved-index-data-broker-family-v1",
        "terminal_route": "verified-live-terminal", "source_route": "registered_standard_data_primary",
    }
    body["response_sha256"] = checksum({"receipt": suffix})
    route = {"record_provider": "FUSION_MARKETS_MT5"}
    bars = [{
        "time": "2026.09.11 00:00:00", "open": 1.1, "high": 1.2,
        "low": 1.0, "close": 1.15, "tick_volume": tick_volume,
        "real_volume": 0, "spread": 5,
    }]
    return request, body, route, bars


def _admit(database: Path, tick_volume: int, suffix: str) -> dict:
    request, response, route, bars = _activity_receipt(tick_volume, suffix)
    payload = json.dumps(response, sort_keys=True).encode()
    raw_id = "raw-" + __import__("hashlib").sha256(payload).hexdigest()
    facts: dict[str, str | int | bool] = {}
    result: dict = {}

    def callback(connection) -> None:
        result.update(admit_bridge_activity(
            connection, response=response, request=request, route=route, bars=bars,
            raw_block_id=raw_id, admitted_at_utc="2026-09-12T00:06:00+00:00",
        ))
        facts.update(result)

    ingest_staged_batch(
        database, batch=StagingBatch((), (), 1, 0, 0),
        evidence=RawEvidence(
            raw_block_id=raw_id, checksum=__import__("hashlib").sha256(payload).hexdigest(),
            payload=payload, source_name=f"{suffix}.json", source_locator=f"fixture://{suffix}",
            media_type="application/json", received_at="2026-09-12T00:06:00+00:00",
        ),
        run_kind="mt5_broker_bridge", merge_mode="correct", outcome_facts=facts,
        preserve_rejected_evidence=True, before_commit=callback,
    )
    return result


def test_activity_is_attributed_and_does_not_rewrite_non_mt5_price(tmp_path: Path) -> None:
    database = _database(tmp_path)
    result = _admit(database, 123, "first")

    assert result["activity_inserted"] == 1
    with open_read_only(database) as connection:
        price = connection.execute(
            "SELECT open,high,low,close,volume FROM bars WHERE asset='AUDUSD' AND timeframe='D1'"
        ).fetchone()
        activity = connection.execute(
            """SELECT tick_volume,real_volume,spread,activity_source_label,provider_symbol
               FROM market_activity_observations"""
        ).fetchone()
    assert tuple(price) == ("1.1", "1.2", "1.0", "1.15", "999")
    assert tuple(activity) == (123, None, 5, ACTIVITY_SOURCE_LABEL, "AUDUSD.r")
    assert activity_coverage(database)["lanes"][0]["activity_state"] == "CURRENT"
    consumer_bar = HistoryService(database).get_history("AUDUSD", "D1")["bars"][0]
    assert consumer_bar["tick_activity"] == 123
    assert consumer_bar["tick_activity_source"] == ACTIVITY_SOURCE_LABEL
    assert consumer_bar["broker_reported_volume"] is None


def test_activity_corrections_are_append_only_and_exact_receipt_replay_is_idempotent(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _admit(database, 123, "first")
    repeated = _admit(database, 123, "first")
    corrected = _admit(database, 124, "correction")

    assert repeated["activity_already_known"] == 1
    assert corrected["activity_inserted"] == 1
    with open_read_only(database) as connection:
        values = connection.execute(
            "SELECT tick_volume FROM market_activity_observations ORDER BY admitted_at_utc,activity_observation_id"
        ).fetchall()
    assert sorted(row[0] for row in values) == [123, 124]
    assert HistoryService(database).get_history("AUDUSD", "D1")["bars"][0]["tick_activity"] == 124


def test_backfill_is_resumable_and_live_request_has_dispatch_priority(tmp_path: Path) -> None:
    database = _database(tmp_path)
    support = Path(f"{database}.read-only-clients")
    accept_catalogue(support, _catalogue())
    state = start_activity_backfill(database, support)

    assert state["lanes"]["AUDUSD:D1"]["state"] == "ACTIVE"
    queued = queue_activity_backfill_requests(database, support)
    request_id = queued["queued"][0]["request_id"]
    assert activity_paths(support)["pending"].joinpath(f"{request_id}.json").is_file()

    live = {
        "request_id": "live-request", "issued_at_utc": "2026-09-14T01:00:00Z",
    }
    _atomic_json(bridge_paths(support)["pending"] / "live-request.json", live)
    assert poll_request(support) == live


def test_primary_daily_activity_is_not_queued_through_activity_only_route(tmp_path: Path) -> None:
    database = _database(tmp_path)
    support = Path(f"{database}.read-only-clients")
    accept_catalogue(support, _catalogue())

    report = queue_continuous_activity_requests(database, support)

    assert report["queued"] == []


def test_current_closed_daily_lane_does_not_create_empty_primary_request(tmp_path: Path) -> None:
    database = _database(tmp_path)
    support = Path(f"{database}.read-only-clients")
    accept_catalogue(support, _catalogue())

    report = enqueue_due_requests(
        database,
        support,
        tmp_path / "scheduler-state.json",
        at=datetime(2026, 9, 12, 12, tzinfo=UTC),
    )

    assert "AUDUSD:D1" not in {item["lane"] for item in report["queued"]}
