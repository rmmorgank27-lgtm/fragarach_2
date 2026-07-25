from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import ProviderProfile
from fragarach_ii.lane_commissioning import commissioned_lane_keys
from fragarach_ii.scheduler_service import (
    required_set_acquisition_plan,
    run_required_set_fetch,
)
from fragarach_ii.storage import (
    initialize_database,
    open_read_only,
    register_instrument,
    registered_writer,
)
from tests.operations.test_spec025a_initial_fetch import _register_discovered
from tests.operations.test_spec047_unified_acquisition import (
    _fx_twelve_data_profile,
    _profile,
    _registered_gbpaud,
    _registered_sol,
)


OBSERVED = datetime(2026, 7, 14, 0, 2, tzinfo=UTC)


def _fx_profile(timeframes=("D1", "H1", "M30", "M5")) -> ProviderProfile:
    profile = _fx_twelve_data_profile(maximum_rows=10_000_000)
    mapping = dict(profile.mappings[0])
    mapping["timeframes"] = list(timeframes)
    return replace(
        profile,
        supported_timeframes=tuple(timeframes),
        mappings=(mapping,),
    )


def _stock_profile() -> ProviderProfile:
    return ProviderProfile(
        provider="TWELVE_DATA",
        enabled=True,
        supported_asset_classes=("US_EQUITIES",),
        supported_timeframes=("D1",),
        credential_environment=None,
        entitlement_state="AVAILABLE",
        request_limit=55,
        request_window_seconds=60,
        maximum_rows_per_request=10_000_000,
        history_limit_days=None,
        cost_class=0,
        priority=10,
        cooldown_seconds=30,
        mappings=(),
        rate_policy_verified=True,
    )


def _crypto_profile() -> ProviderProfile:
    return replace(
        _profile(
            "BINANCE",
            priority=20,
            mapping_class="EXACT_REPRESENTATION",
            symbol="SOLUSD",
            timeframes=("D1", "H1", "M30", "M5"),
        ),
        maximum_rows_per_request=10_000_000,
    )


def _publish_terminal_bar(database: Path, **kwargs) -> dict[str, object]:
    symbol = str(kwargs["asset"])
    timeframe = str(kwargs["timeframe"])
    provider = str(kwargs["provider"])
    provider_symbol = str(kwargs["provider_symbol"])
    through = date.fromisoformat(str(kwargs["through_date"]))
    if timeframe == "D1":
        open_at = datetime.combine(through, time.min, UTC)
        close_at = None
    else:
        seconds = {"H1": 3600, "M30": 1800, "M5": 300}[timeframe]
        close_at = datetime.combine(OBSERVED.date(), time.min, UTC)
        open_at = close_at - timedelta(seconds=seconds)
    payload = f"{symbol}:{timeframe}:{through.isoformat()}:{provider}".encode()
    digest = hashlib.sha256(payload).hexdigest()
    raw_id = f"raw-spec060-{symbol}-{timeframe}-{through.isoformat()}-{digest[:8]}"
    run_id = f"run-spec060-{symbol}-{timeframe}-{through.isoformat()}-{digest[:8]}"
    detail = json.dumps(
        {
            "asset": symbol,
            "timeframe": timeframe,
            "provider": provider,
            "provider_symbol": provider_symbol,
            "mapping_class": kwargs.get("mapping_class"),
        },
        separators=(",", ":"),
    )
    with registered_writer(database) as connection:
        connection.execute(
            """INSERT OR IGNORE INTO raw_blocks
               (raw_block_id,sha256,source_name,source_locator,media_type,
                received_at_utc,byte_length,payload)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                raw_id,
                digest,
                provider,
                provider_symbol,
                "application/json",
                OBSERVED.isoformat(),
                len(payload),
                payload,
            ),
        )
        connection.execute(
            """INSERT OR IGNORE INTO ingest_runs
               (ingest_run_id,kind,status,started_at_utc,finished_at_utc,detail)
               VALUES(?,'provider_test','committed',?,?,?)""",
            (run_id, OBSERVED.isoformat(), OBSERVED.isoformat(), detail),
        )
        connection.execute(
            """INSERT OR IGNORE INTO bars
               (asset,timeframe,open_time_utc,close_time_utc,open,high,low,close,
                created_by_ingest_run_id,updated_by_ingest_run_id)
               VALUES(?,?,?,?, '1','2','0','1',?,?)""",
            (
                symbol,
                timeframe,
                int(open_at.timestamp()),
                int(close_at.timestamp()) if close_at else None,
                run_id,
                run_id,
            ),
        )
        connection.execute(
            """INSERT INTO lane_state
               (asset,timeframe,high_watermark_open_time_utc,state_version,
                last_ingest_run_id,updated_at_utc)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(asset,timeframe) DO UPDATE SET
                 high_watermark_open_time_utc=excluded.high_watermark_open_time_utc,
                 state_version=lane_state.state_version+1,
                 last_ingest_run_id=excluded.last_ingest_run_id,
                 updated_at_utc=excluded.updated_at_utc""",
            (
                symbol,
                timeframe,
                int(open_at.timestamp()),
                1,
                run_id,
                OBSERVED.isoformat(),
            ),
        )
    return {"inserted": 1, "corrected": 0, "received": 1, "staged": 1}


def test_required_set_uses_market_doctrine_for_fx_crypto_and_stocks() -> None:
    with tempfile.TemporaryDirectory() as directory:
        fx = Path(directory) / "fx.sqlite3"
        crypto = Path(directory) / "crypto.sqlite3"
        stock = Path(directory) / "stock.sqlite3"
        _registered_gbpaud(fx)
        _registered_sol(crypto)
        initialize_database(stock)
        _register_discovered(stock, "AAPL")

        fx_plan = required_set_acquisition_plan(
            fx, symbol="GBPAUD", provider_profiles=(_fx_profile(),), at=OBSERVED
        )
        crypto_plan = required_set_acquisition_plan(
            crypto, symbol="SOLUSD", provider_profiles=(_crypto_profile(),), at=OBSERVED
        )
        stock_plan = required_set_acquisition_plan(
            stock, symbol="AAPL", provider_profiles=(_stock_profile(),), at=OBSERVED
        )

        assert fx_plan["required_timeframes"] == ["D1", "H1", "M30", "M5"]
        assert crypto_plan["required_timeframes"] == ["D1", "H1", "M30", "M5"]
        assert stock_plan["required_timeframes"] == ["D1"]


def test_grouped_plan_includes_per_lane_blocking_reasons() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_gbpaud(database)

        plan = required_set_acquisition_plan(
            database,
            symbol="GBPAUD",
            provider_profiles=(_fx_profile(timeframes=("D1",)),),
            at=OBSERVED,
        )
        lanes = {lane["timeframe"]: lane for lane in plan["lanes"]}

        assert lanes["D1"]["executable"] is True
        for timeframe in ("H1", "M30", "M5"):
            assert lanes[timeframe]["executable"] is False
            assert lanes[timeframe]["blocking_reason"] == "TIMEFRAME_UNSUPPORTED"


def test_executable_lanes_run_when_another_lane_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal = Path(directory) / "scheduler.json"
        _registered_gbpaud(database)
        calls: list[tuple[str, str]] = []

        def acquire(_database, **kwargs):
            calls.append((str(kwargs["asset"]), str(kwargs["timeframe"])))
            return _publish_terminal_bar(database, **kwargs)

        result = run_required_set_fetch(
            database,
            symbol="GBPAUD",
            credential=None,
            journal_path=journal,
            provider_profiles=(_fx_profile(timeframes=("D1",)),),
            acquirer=acquire,
            at=OBSERVED,
        )

        assert calls == [("GBPAUD", "D1")]
        assert result["outcome"] == "PARTIAL"
        assert {lane["timeframe"] for lane in result["blocked_lanes"]} == {"H1", "M30", "M5"}


def test_grouped_fetch_commissions_lane_only_after_canonical_evidence_exists() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal = Path(directory) / "scheduler.json"
        _registered_gbpaud(database)
        with open_read_only(database) as connection:
            assert ("GBPAUD", "H1") not in commissioned_lane_keys(connection)

        result = run_required_set_fetch(
            database,
            symbol="GBPAUD",
            credential=None,
            journal_path=journal,
            provider_profiles=(_fx_profile(),),
            acquirer=lambda _database, **kwargs: _publish_terminal_bar(database, **kwargs),
            at=OBSERVED,
        )

        assert result["outcome"] == "SUCCESS"
        with open_read_only(database) as connection:
            commissioned = commissioned_lane_keys(connection)
        for timeframe in ("H1", "M30", "M5"):
            assert ("GBPAUD", timeframe) in commissioned


def test_partial_grouped_job_can_be_resumed_without_refetching_completed_lanes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal = Path(directory) / "scheduler.json"
        _registered_gbpaud(database)
        first_calls: list[str] = []
        second_calls: list[str] = []

        def first_acquire(_database, **kwargs):
            first_calls.append(str(kwargs["timeframe"]))
            return _publish_terminal_bar(database, **kwargs)

        first = run_required_set_fetch(
            database,
            symbol="GBPAUD",
            credential=None,
            journal_path=journal,
            provider_profiles=(_fx_profile(timeframes=("D1", "H1")),),
            acquirer=first_acquire,
            at=OBSERVED,
        )

        def second_acquire(_database, **kwargs):
            second_calls.append(str(kwargs["timeframe"]))
            return _publish_terminal_bar(database, **kwargs)

        second = run_required_set_fetch(
            database,
            symbol="GBPAUD",
            credential=None,
            journal_path=journal,
            provider_profiles=(_fx_profile(),),
            acquirer=second_acquire,
            at=OBSERVED,
        )

        assert first["outcome"] == "PARTIAL"
        assert first_calls == ["D1", "H1"]
        assert second["outcome"] == "SUCCESS"
        assert second_calls == ["M30", "M5"]


def test_crypto_required_set_single_action_can_reach_current_lanes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal = Path(directory) / "scheduler.json"
        _registered_sol(database)

        result = run_required_set_fetch(
            database,
            symbol="SOLUSD",
            credential=None,
            journal_path=journal,
            provider_profiles=(_crypto_profile(),),
            acquirer=lambda _database, **kwargs: _publish_terminal_bar(database, **kwargs),
            at=OBSERVED,
        )

        assert result["outcome"] == "SUCCESS"
        lanes = {lane["timeframe"]: lane for lane in result["lanes"]}
        assert [lanes[timeframe]["eligibility"] for timeframe in ("D1", "H1", "M30", "M5")] == [
            "CURRENT",
            "CURRENT",
            "CURRENT",
            "CURRENT",
        ]
