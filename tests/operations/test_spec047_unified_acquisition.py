from __future__ import annotations

import base64
import hashlib
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import (
    ProviderProfile,
    acquisition_capability_projection,
    acquisition_plan,
    approved_mapping,
    build_rate_budgets,
    estimate_requests,
)
from fragarach_ii.freshness import assess_lane_freshness
from fragarach_ii.history_depth import governed_d1_initial_start
from fragarach_ii.lane_commissioning import commissioned_lane_keys, ensure_commissioned_lane
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.providers.binance import acquire_binance
from fragarach_ii.providers.twelve_data import AcquisitionError
from fragarach_ii.scheduler_service import SchedulerJournal, run_operator_fetch, scheduler_snapshot
from fragarach_ii.storage import initialize_database, open_read_only, register_instrument, registered_writer
from fragarach_ii.truth_engine import truth_state_for_lane
from tests.validation.test_d1_session_validation import _create_lane


def _registered_sol(database: Path, *, d1_dates=("2026-07-11",)) -> None:
    initialize_database(database)
    market = discover_market(database, "SOLUSD")["markets"][0]
    representation = next(row for row in market["representations"] if row["symbol"] == "SOLUSD")
    encoded = representation["registration_plan"]["candidate"]
    candidate = json.loads(base64.urlsafe_b64decode(encoded))
    register_instrument(
        database,
        candidate_from_dict(candidate),
        registered_at_utc="2026-07-11T00:00:00+00:00",
    )
    _create_lane(database, "SOLUSD", list(d1_dates))


def _profile(
    provider: str,
    *,
    priority: int,
    mapping_class: str | None,
    symbol: str | None,
    timeframes=("D1",),
    asset_classes=("CRYPTO",),
    credential=False,
) -> ProviderProfile:
    mappings = ()
    if mapping_class and symbol:
        mappings = ({
            "asset": "SOLUSD",
            "symbol": symbol,
            "timeframes": list(timeframes),
            "mapping_class": mapping_class,
            "reviewed_status": "REVIEWED",
            "authority_source": "SPEC_047_TEST_AUTHORITY",
            "canonical_base_asset": "SOL",
            "canonical_quote_asset": "USD",
            "provider_base_asset": "SOL",
            "provider_quote_asset": "USDT" if symbol == "SOLUSDT" else "USD",
        },)
    return ProviderProfile(
        provider=provider,
        enabled=True,
        supported_asset_classes=tuple(asset_classes),
        supported_timeframes=tuple(timeframes),
        credential_environment=f"{provider}_KEY" if credential else None,
        entitlement_state="AVAILABLE",
        request_limit=50,
        request_window_seconds=60,
        maximum_rows_per_request=4000,
        history_limit_days=None,
        cost_class=0,
        priority=priority,
        cooldown_seconds=30,
        mappings=mappings,
        rate_policy_verified=True,
    )


def _four_provider_profiles() -> tuple[ProviderProfile, ...]:
    return (
        _profile("TWELVE_DATA", priority=10, mapping_class="EXACT_REPRESENTATION", symbol="SOL/USD", credential=True),
        _profile("YAHOO_FINANCE", priority=15, mapping_class=None, symbol=None, asset_classes=("FX",)),
        _profile("BINANCE", priority=20, mapping_class="EXACT_REPRESENTATION", symbol="SOLUSD"),
        _profile("COINGECKO", priority=30, mapping_class="APPROVED_PROVIDER_ALIAS", symbol="solana"),
    )


def _registered_gbpaud(database: Path) -> None:
    initialize_database(database)
    plan = discover_market(database, "GBPAUD")["markets"][0]["representations"][0]["registration_plan"]
    candidate = json.loads(base64.urlsafe_b64decode(plan["candidate"]))
    candidate.update(
        provider_id="TWELVE_DATA",
        provider_contract="TWELVE_DATA_TIME_SERIES_D1_V1",
        provider_symbol="GBP/AUD",
        provider_instrument_type="Physical Currency",
    )
    register_instrument(
        database,
        candidate_from_dict(candidate),
        registered_at_utc="2026-07-14T00:00:00+00:00",
    )


def _fx_twelve_data_profile(
    *,
    mapping_class: str | None = "EXACT_REPRESENTATION",
    symbol: str | None = "GBP/AUD",
    maximum_rows: int = 5000,
) -> ProviderProfile:
    mappings = ()
    if mapping_class and symbol:
        mappings = ({
            "asset": "GBPAUD",
            "symbol": symbol,
            "timeframes": ["D1", "H1", "M30", "M5"],
            "mapping_class": mapping_class,
            "reviewed_status": "REVIEWED",
            "authority_source": "SPEC_058_TEST_AUTHORITY",
            "canonical_base_asset": "GBP",
            "canonical_quote_asset": "AUD",
            "provider_base_asset": "GBP",
            "provider_quote_asset": "AUD" if symbol == "GBP/AUD" else "GBP",
        },)
    return ProviderProfile(
        provider="TWELVE_DATA",
        enabled=True,
        supported_asset_classes=("FX",),
        supported_timeframes=("D1", "H1", "M30", "M5"),
        credential_environment=None,
        entitlement_state="AVAILABLE",
        request_limit=55,
        request_window_seconds=60,
        maximum_rows_per_request=maximum_rows,
        history_limit_days=None,
        cost_class=0,
        priority=10,
        cooldown_seconds=30,
        mappings=mappings,
        rate_policy_verified=True,
    )


def _publish_gbpaud_h1_edge(database: Path, close_at: datetime, suffix: str) -> None:
    payload = f"spec-059-gbpaud-h1-{suffix}".encode()
    raw_id = f"raw-spec059-{suffix}"
    run_id = f"run-spec059-{suffix}"
    opened = int((close_at - timedelta(hours=1)).timestamp())
    closed = int(close_at.timestamp())
    with registered_writer(database) as connection:
        connection.execute(
            """INSERT OR IGNORE INTO raw_blocks
               (raw_block_id,sha256,source_name,source_locator,media_type,
                received_at_utc,byte_length,payload)
               VALUES(?,?, 'TWELVE_DATA','GBP/AUD','application/json',?,?,?)""",
            (
                raw_id, hashlib.sha256(payload).hexdigest(),
                close_at.isoformat(), len(payload), payload,
            ),
        )
        connection.execute(
            """INSERT OR IGNORE INTO ingest_runs
               (ingest_run_id,kind,status,started_at_utc,finished_at_utc,raw_block_id,detail)
               VALUES(?,'provider_twelve_data','committed',?,?,?,?)""",
            (
                run_id, close_at.isoformat(), close_at.isoformat(), raw_id,
                json.dumps({
                    "asset": "GBPAUD", "timeframe": "H1",
                    "provider": "TWELVE_DATA", "provider_symbol": "GBP/AUD",
                    "mapping_class": "EXACT_REPRESENTATION",
                }, separators=(",", ":")),
            ),
        )
        connection.execute(
            """INSERT OR IGNORE INTO bars
               (asset,timeframe,open_time_utc,close_time_utc,open,high,low,close,
                created_by_ingest_run_id,updated_by_ingest_run_id)
               VALUES('GBPAUD','H1',?,?,'1.90','1.91','1.89','1.905',?,?)""",
            (opened, closed, run_id, run_id),
        )


def test_shared_projection_exposes_all_providers_and_reviewed_solusd_representations() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_sol(database)
        for timeframe in ("H1", "M30", "M5"):
            ensure_commissioned_lane(database, "SOLUSD", timeframe, observed_at="2026-07-11T00:00:00+00:00")
        projection = acquisition_capability_projection(
            database,
            symbol="SOLUSD",
            now=datetime(2026, 7, 14, 12, tzinfo=UTC),
            credentials={},
        )
        rows = projection["rows"]
        assert len(rows) == 16
        d1 = {row["provider"]: row for row in rows if row["timeframe"] == "D1"}
        assert d1["BINANCE"]["provider_representation"] == "SOL/USD"
        assert d1["BINANCE"]["mapping_class"] == "EXACT_REPRESENTATION"
        assert d1["COINGECKO"]["mapping_class"] == "APPROVED_PROVIDER_ALIAS"
        assert d1["TWELVE_DATA"]["capability_state"] == "CREDENTIAL_REQUIRED"
        assert d1["YAHOO_FINANCE"]["eligibility"] == "INELIGIBLE"
        assert all(row["canonical_base_asset"] == "SOL" for row in rows)
        assert not any(row.get("provider_symbol") == "SOLUSDT" for row in rows)


def test_operator_fetch_uses_scheduler_failover_and_skips_ineligible_provider() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal = Path(directory) / "scheduler.json"
        _registered_sol(database)
        calls: list[str] = []

        def acquire(_database, **kwargs):
            calls.append(kwargs["provider"])
            if kwargs["provider"] == "TWELVE_DATA":
                raise AcquisitionError("PROVIDER_TIMEOUT", "forced timeout")
            edge=int(datetime(2026,7,12,tzinfo=UTC).timestamp())
            with registered_writer(database) as connection:
                run_id=connection.execute("SELECT created_by_ingest_run_id FROM bars WHERE asset='SOLUSD' LIMIT 1").fetchone()[0]
                connection.execute("INSERT OR IGNORE INTO bars(asset,timeframe,open_time_utc,open,high,low,close,created_by_ingest_run_id,updated_by_ingest_run_id) VALUES('SOLUSD','D1',?,'1','2','0','1',?,?)",(edge,run_id,run_id))
                connection.execute("UPDATE lane_state SET high_watermark_open_time_utc=?,state_version=state_version+1 WHERE asset='SOLUSD' AND timeframe='D1'",(edge,))
            return {"inserted": 1, "corrected": 0, "received": 1}

        result = run_operator_fetch(
            database,
            symbol="SOLUSD",
            timeframe="D1",
            credential="fixture",
            requested_mode="custom",
            requested_start="2026-07-12",
            requested_end="2026-07-12",
            reviewed_historical_range=True,
            journal_path=journal,
            at=datetime(2026, 7, 14, 12, tzinfo=UTC),
            acquirer=acquire,
            provider_profiles=_four_provider_profiles(),
        )
        assert result["work_class"] == "OPERATOR_FETCH"
        assert result["outcome"] == "SUCCESS"
        assert calls == ["TWELVE_DATA", "BINANCE"]
        assert result["providers_attempted"] == ["BINANCE", "TWELVE_DATA"]
        considered = {row["provider"]: row for row in result["providers_considered"]}
        assert considered["YAHOO_FINANCE"]["reason"] == "ASSET_CLASS_UNSUPPORTED"
        assert result["provider_results"][0]["result"] == "TRANSIENT_PROVIDER_FAILURE"
        assert result["provider_results"][-1]["mapping_class"] == "EXACT_REPRESENTATION"


def test_initial_fx_intraday_plan_does_not_require_canonical_edge() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_gbpaud(database)
        profiles = (_fx_twelve_data_profile(),)
        budgets = build_rate_budgets(
            profiles, {}, wall_clock=lambda: datetime(2026, 7, 14, 14, 2, tzinfo=UTC)
        )
        for timeframe, missing_start in (
            ("H1", "2023-07-14"),
            ("M30", "2024-07-14"),
            ("M5", "2025-07-14"),
        ):
            plan = acquisition_plan(
                database,
                symbol="GBPAUD",
                timeframe=timeframe,
                canonical_edge=None,
                expected_edge="2026-07-14T14:00:00+00:00",
                missing_start=missing_start,
                missing_end="2026-07-14",
                scheduled_boundary=f"OPERATOR_FETCH:{timeframe}",
                profiles=profiles,
                provider_state={},
                budgets=budgets,
                credentials={},
                now=datetime(2026, 7, 14, 14, 2, tzinfo=UTC),
                work_class="OPERATOR_FETCH",
            )
            assert plan["canonical_edge"] is None
            assert plan["expected_edge"] == "2026-07-14T14:00:00+00:00"
            assert plan["missing_range"] == {"start": missing_start, "end": "2026-07-14"}
            assert plan["selected_provider"] == "TWELVE_DATA"
            assert plan["selected_provider_symbol"] == "GBP/AUD"
            assert plan["selected_mapping_class"] == "EXACT_REPRESENTATION"
            assert plan["providers_considered"][0]["reason"] is None


def test_initial_fx_intraday_plan_blocks_without_exact_provider_representation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_gbpaud(database)
        profiles = (_fx_twelve_data_profile(mapping_class="CONVERSION_REQUIRED", symbol="AUD/GBP"),)
        budgets = build_rate_budgets(
            profiles, {}, wall_clock=lambda: datetime(2026, 7, 14, 14, 2, tzinfo=UTC)
        )
        plan = acquisition_plan(
            database,
            symbol="GBPAUD",
            timeframe="H1",
            canonical_edge=None,
            expected_edge="2026-07-14T14:00:00+00:00",
            missing_start="2023-07-14",
            missing_end="2026-07-14",
            scheduled_boundary="OPERATOR_FETCH:H1",
            profiles=profiles,
            provider_state={},
            budgets=budgets,
            credentials={},
            now=datetime(2026, 7, 14, 14, 2, tzinfo=UTC),
            work_class="OPERATOR_FETCH",
        )
        assert plan["selected_provider"] is None
        assert plan["providers_considered"][0]["mapping_class"] == "CONVERSION_REQUIRED"
        assert plan["providers_considered"][0]["reason"] == "NO_APPROVED_MAPPING"


def test_intraday_request_estimate_matches_whole_day_executor_chunks() -> None:
    assert estimate_requests("M5", "2025-07-17", "2026-07-17", 4000) == 29
    assert estimate_requests("M30", "2024-07-17", "2026-07-17", 4000) == 9
    assert estimate_requests("H1", "2023-07-17", "2026-07-17", 4000) == 7


def test_initial_fx_h1_fetch_consumes_the_complete_governed_history_range() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal_path = Path(directory) / "scheduler.json"
        _registered_gbpaud(database)
        calls: list[tuple[str, str]] = []
        published_edges = [
            datetime(2026, 7, 11, 12, tzinfo=UTC),
            datetime(2026, 7, 13, 12, tzinfo=UTC),
            datetime(2026, 7, 14, 14, tzinfo=UTC),
        ]

        def acquire(_database, **kwargs):
            calls.append((kwargs["from_date"], kwargs["through_date"]))
            _publish_gbpaud_h1_edge(
                database, published_edges[len(calls) - 1], f"continue-{len(calls)}"
            )
            return {"inserted": 1, "corrected": 0, "unchanged": 0, "received": 1}

        result = run_operator_fetch(
            database,
            symbol="GBPAUD",
            timeframe="H1",
            credential="fixture",
            requested_mode="initial",
            requested_start="2026-07-10",
            requested_end="2026-07-14",
            reviewed_historical_range=True,
            journal_path=journal_path,
            at=datetime(2026, 7, 14, 14, 2, tzinfo=UTC),
            acquirer=acquire,
            provider_profiles=(_fx_twelve_data_profile(maximum_rows=48),),
        )

        assert calls == [
            ("2026-07-10", "2026-07-11"),
            ("2026-07-12", "2026-07-13"),
            ("2026-07-14", "2026-07-14"),
        ]
        assert result["outcome"] == "SUCCESS"
        assert result["canonical_edge_after"] == "2026-07-14T14:00:00+00:00"
        assert result["freshness_result"]["state"] == "Current"
        with open_read_only(database) as connection:
            assert ("GBPAUD", "H1") not in commissioned_lane_keys(connection)


def test_initial_fx_h1_partial_failure_retries_from_partial_canonical_edge() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal_path = Path(directory) / "scheduler.json"
        _registered_gbpaud(database)
        profile = _fx_twelve_data_profile(maximum_rows=48)
        failing_calls: list[tuple[str, str]] = []

        def partial_then_fail(_database, **kwargs):
            failing_calls.append((kwargs["from_date"], kwargs["through_date"]))
            if len(failing_calls) == 1:
                _publish_gbpaud_h1_edge(
                    database, datetime(2026, 7, 12, 12, tzinfo=UTC), "partial"
                )
                return {"inserted": 1, "corrected": 0, "unchanged": 0, "received": 1}
            raise ValueError("SPEC059_CONTINUATION_INVARIANT")

        first = run_operator_fetch(
            database,
            symbol="GBPAUD",
            timeframe="H1",
            credential="fixture",
            requested_mode="initial",
            requested_start="2026-07-10",
            requested_end="2026-07-14",
            reviewed_historical_range=True,
            journal_path=journal_path,
            at=datetime(2026, 7, 14, 14, 2, tzinfo=UTC),
            acquirer=partial_then_fail,
            provider_profiles=(profile,),
        )

        assert failing_calls == [
            ("2026-07-10", "2026-07-11"),
            ("2026-07-12", "2026-07-13"),
        ]
        assert first["outcome"] == "WAITING"
        assert first["canonical_edge_after"] == "2026-07-12T12:00:00+00:00"
        failure = first["provider_results"][0]
        assert failure["reason"] == "LOCAL_PROGRAMMING_ERROR"
        assert "function=_execute_acquisition" in failure["detail"]
        assert "lane=GBPAUD:H1" in failure["detail"]
        assert "provider=TWELVE_DATA" in failure["detail"]
        assert "request_bounds=2026-07-12..2026-07-14" in failure["detail"]
        assert "SPEC059_CONTINUATION_INVARIANT" in failure["detail"]

        retry_calls: list[tuple[str, str]] = []

        def complete_from_partial(_database, **kwargs):
            retry_calls.append((kwargs["from_date"], kwargs["through_date"]))
            _publish_gbpaud_h1_edge(
                database, datetime(2026, 7, 14, 14, tzinfo=UTC), "retry-current"
            )
            return {"inserted": 1, "corrected": 0, "unchanged": 0, "received": 1}

        second = run_operator_fetch(
            database,
            symbol="GBPAUD",
            timeframe="H1",
            credential="fixture",
            requested_mode="initial",
            requested_start="2026-07-10",
            requested_end="2026-07-14",
            reviewed_historical_range=True,
            journal_path=journal_path,
            at=datetime(2026, 7, 14, 14, 3, tzinfo=UTC),
            acquirer=complete_from_partial,
            provider_profiles=(profile,),
        )

        assert retry_calls[0][0] == "2026-07-12"
        assert second["outcome"] == "SUCCESS"
        assert second["canonical_edge_after"] == "2026-07-14T14:00:00+00:00"


def test_initial_d1_operator_fetch_expands_depth_and_accepts_backfill_without_edge_advance() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal = Path(directory) / "scheduler.json"
        _registered_sol(database, d1_dates=("2026-07-11",))
        calls: list[dict[str, object]] = []

        def acquire(_database, **kwargs):
            calls.append(dict(kwargs))
            opened = int(datetime.fromisoformat(kwargs["from_date"]).replace(tzinfo=UTC).timestamp())
            with registered_writer(database) as connection:
                run_id = connection.execute(
                    "SELECT created_by_ingest_run_id FROM bars WHERE asset='SOLUSD' LIMIT 1"
                ).fetchone()[0]
                connection.execute(
                    """INSERT OR IGNORE INTO bars(
                           asset,timeframe,open_time_utc,open,high,low,close,
                           created_by_ingest_run_id,updated_by_ingest_run_id
                       ) VALUES('SOLUSD','D1',?,'1','2','0','1',?,?)""",
                    (opened, run_id, run_id),
                )
            return {"inserted": 1, "corrected": 0, "received": 1, "staged": 1}

        result = run_operator_fetch(
            database,
            symbol="SOLUSD",
            timeframe="D1",
            credential=None,
            requested_mode="initial",
            requested_start="2026-07-11",
            requested_end="2026-07-11",
            reviewed_historical_range=True,
            journal_path=journal,
            at=datetime(2026, 7, 14, 12, tzinfo=UTC),
            acquirer=acquire,
            provider_profiles=(_profile("BINANCE", priority=1, mapping_class="EXACT_REPRESENTATION", symbol="SOLUSD"),),
        )

        expected_start = governed_d1_initial_start(datetime(2026, 7, 11, tzinfo=UTC).date()).isoformat()
        assert calls[0]["from_date"] == expected_start
        assert calls[0]["through_date"] == "2026-07-11"
        assert result["outcome"] == "SUCCESS"
        assert result["requested_range"] == {"start": expected_start, "end": "2026-07-11"}
        assert result["canonical_edge_before"] == result["canonical_edge_after"]
        assert result["provider_results"][-1]["inserted"] == 1


def test_provider_exhaustion_creates_one_transparent_manual_request() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal_path = Path(directory) / "scheduler.json"
        _registered_sol(database)

        def fail(_database, **kwargs):
            raise AcquisitionError("INVALID_RESPONSE", f"invalid {kwargs['provider']}")

        result = run_operator_fetch(
            database,
            symbol="SOLUSD",
            timeframe="D1",
            credential="fixture",
            requested_mode="custom",
            requested_start="2026-07-12",
            requested_end="2026-07-12",
            reviewed_historical_range=True,
            journal_path=journal_path,
            at=datetime(2026, 7, 14, 12, tzinfo=UTC),
            acquirer=fail,
            provider_profiles=_four_provider_profiles(),
        )
        assert result["outcome"] == "WAITING"
        assert result["manual_request_created"] is None
        queue = SchedulerJournal(database, journal_path).data["acquisition_queue"]
        item = next(row for row in queue if row["lane"] == "SOLUSD:D1")
        assert item["trace_id"]
        assert item["next_attempt"]


def test_solusdt_is_not_an_approved_solusd_real_representation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_sol(database)
        conversion = _profile(
            "UNSAFE_EXCHANGE",
            priority=1,
            mapping_class="CONVERSION_REQUIRED",
            symbol="SOLUSDT",
        )
        assert approved_mapping(
            conversion,
            symbol="SOLUSD",
            timeframe="D1",
            primary_provider=None,
            primary_symbol=None,
        ) is None
        profiles = (conversion,)
        budgets = build_rate_budgets(profiles, {}, wall_clock=lambda: datetime(2026, 7, 14, tzinfo=UTC))
        plan = acquisition_plan(
            database,
            symbol="SOLUSD",
            timeframe="D1",
            canonical_edge="2026-07-11T00:00:00+00:00",
            expected_edge="2026-07-13T00:00:00+00:00",
            missing_start="2026-07-12",
            missing_end="2026-07-13",
            scheduled_boundary="2026-07-14T00:00:00+00:00",
            profiles=profiles,
            provider_state={},
            budgets=budgets,
            credentials={},
            now=datetime(2026, 7, 14, tzinfo=UTC),
        )
        assert plan["selected_provider"] is None
        assert plan["providers_considered"][0]["mapping_class"] == "CONVERSION_REQUIRED"
        assert plan["providers_considered"][0]["reason"] == "NO_APPROVED_MAPPING"
        not_equivalent = _profile(
            "REJECTED_EXCHANGE",
            priority=1,
            mapping_class="NOT_EQUIVALENT",
            symbol="SOLUSDT",
        )
        assert approved_mapping(
            not_equivalent,
            symbol="SOLUSD",
            timeframe="D1",
            primary_provider=None,
            primary_symbol=None,
        ) is None


def test_crypto_freshness_is_24_7_and_critical_staleness_cannot_remain_green() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_sol(database, d1_dates=("2026-07-11",))
        for timeframe, seconds in (("H1", 3600), ("M30", 1800), ("M5", 300)):
            ensure_commissioned_lane(database, "SOLUSD", timeframe, observed_at="2026-07-11T00:00:00+00:00")
            opened = int(datetime(2026, 7, 14, 0, 0, tzinfo=UTC).timestamp())
            with registered_writer(database) as connection:
                connection.execute(
                    """INSERT INTO bars(asset,timeframe,open_time_utc,close_time_utc,open,high,low,close,
                                         created_by_ingest_run_id,updated_by_ingest_run_id)
                       VALUES('SOLUSD',?,?,?,'1','2','0','1','run-1','run-1')""",
                    (timeframe, opened, opened + seconds),
                )
        as_of = datetime(2026, 7, 14, 12, 15, tzinfo=UTC)
        with open_read_only(database) as connection:
            states = {
                timeframe: assess_lane_freshness(
                    connection, symbol="SOLUSD", timeframe=timeframe, as_of=as_of
                )
                for timeframe in ("D1", "H1", "M30", "M5")
            }
        assert all(row["state"] == "Behind" for row in states.values())
        assert all(row["severity"] == "CRITICAL" for row in states.values())
        assert states["M5"]["lag"]["count"] > states["M30"]["lag"]["count"] > states["H1"]["lag"]["count"]
        truth = truth_state_for_lane(database, symbol="SOLUSD", timeframe="D1", as_of=as_of)
        assert truth["freshness"]["severity"] == "CRITICAL"
        assert truth["authority_state"] == "RED"
        assert truth["overall_operational_state"] == "Critical"


def test_current_crypto_m5_edge_is_current_under_continuous_calendar() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_sol(database)
        ensure_commissioned_lane(database, "SOLUSD", "M5", observed_at="2026-07-11T00:00:00+00:00")
        opened = int(datetime(2026, 7, 14, 12, 5, tzinfo=UTC).timestamp())
        with registered_writer(database) as connection:
            connection.execute(
                """INSERT INTO bars(asset,timeframe,open_time_utc,close_time_utc,open,high,low,close,
                                     created_by_ingest_run_id,updated_by_ingest_run_id)
                   VALUES('SOLUSD','M5',?,?,'1','2','0','1','run-1','run-1')""",
                (opened, opened + 300),
            )
        with open_read_only(database) as connection:
            freshness = assess_lane_freshness(
                connection,
                symbol="SOLUSD",
                timeframe="M5",
                as_of=datetime(2026, 7, 14, 12, 11, tzinfo=UTC),
            )
        assert freshness["state"] == "Current"
        assert freshness["severity"] == "HEALTHY"


def test_operator_fetch_deduplicates_existing_active_work() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal_path = Path(directory) / "scheduler.json"
        _registered_sol(database)
        journal = SchedulerJournal(database, journal_path)
        journal.lane("SOLUSD", "D1")["operator_fetch_pending"] = {
            "id": "operator-fetch-existing",
            "requested_start": "2026-07-12",
            "requested_end": "2026-07-13",
        }
        journal.save()
        result = run_operator_fetch(
            database,
            symbol="SOLUSD",
            timeframe="D1",
            credential=None,
            requested_mode="custom",
            requested_start="2026-07-12",
            requested_end="2026-07-13",
            reviewed_historical_range=True,
            journal_path=journal_path,
            at=datetime(2026, 7, 14, 12, tzinfo=UTC),
        )
        assert result["outcome"] == "DEDUPLICATED_ACTIVE_WORK"
        assert result["operation_id"] == "operator-fetch-existing"


def test_successful_publication_advances_every_read_model_without_restart() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal_path = Path(directory) / "scheduler.json"
        _registered_sol(database)
        as_of = datetime(2026, 7, 14, 12, tzinfo=UTC)
        with open_read_only(database) as connection:
            before_revision = __import__(
                "fragarach_ii.freshness", fromlist=["authority_revision_for_lane"]
            ).authority_revision_for_lane(connection, symbol="SOLUSD", timeframe="D1")

        def publish(_database, **kwargs):
            payload = b"spec-047 immutable binance evidence"
            detail = json.dumps({
                "asset": "SOLUSD",
                "timeframe": "D1",
                "provider": "BINANCE",
                "provider_symbol": kwargs["provider_symbol"],
                "mapping_class": kwargs["mapping_class"],
                "inserted": 1,
            }, separators=(",", ":"))
            edge = int(datetime(2026, 7, 13, tzinfo=UTC).timestamp())
            with registered_writer(database) as connection:
                connection.execute(
                    """INSERT INTO raw_blocks(raw_block_id,sha256,source_name,source_locator,media_type,
                                               received_at_utc,byte_length,payload)
                       VALUES('raw-spec047',?,'BINANCE','SOLUSD','application/json',?,?,?)""",
                    (hashlib.sha256(payload).hexdigest(), as_of.isoformat(), len(payload), payload),
                )
                connection.execute(
                    """INSERT INTO ingest_runs(ingest_run_id,kind,status,started_at_utc,finished_at_utc,raw_block_id,detail)
                       VALUES('run-spec047','provider_binance','committed',?,?, 'raw-spec047',?)""",
                    (as_of.isoformat(), as_of.isoformat(), detail),
                )
                connection.execute(
                    """INSERT INTO bars(asset,timeframe,open_time_utc,open,high,low,close,
                                         created_by_ingest_run_id,updated_by_ingest_run_id)
                       VALUES('SOLUSD','D1',?,'150','151','149','150.5','run-spec047','run-spec047')""",
                    (edge,),
                )
                connection.execute(
                    """INSERT INTO provenance(provenance_event_id,ingest_run_id,raw_block_id,symbol,timeframe,
                                               timestamp,source_row_number,merge_action,candidate_open,candidate_high,
                                               candidate_low,candidate_close,recorded_at)
                       VALUES('event-spec047','run-spec047','raw-spec047','SOLUSD','D1',?,1,'INSERT',
                              '150','151','149','150.5',?)""",
                    (edge, as_of.isoformat()),
                )
                connection.execute(
                    """UPDATE lane_state SET high_watermark_open_time_utc=?,state_version=state_version+1,
                                               last_ingest_run_id='run-spec047',updated_at_utc=?
                       WHERE asset='SOLUSD' AND timeframe='D1'""",
                    (edge, as_of.isoformat()),
                )
            return {"inserted": 1, "corrected": 0, "received": 1}

        profiles = (_profile("BINANCE", priority=1, mapping_class="EXACT_REPRESENTATION", symbol="SOLUSD"),)
        result = run_operator_fetch(
            database,
            symbol="SOLUSD",
            timeframe="D1",
            credential=None,
            requested_mode="update",
            journal_path=journal_path,
            at=as_of,
            acquirer=publish,
            provider_profiles=profiles,
        )
        assert result["canonical_edge_after"] == "2026-07-13T00:00:00+00:00", result
        assert result["authority_revision"] != before_revision
        assert result["freshness_result"]["state"] == "Current"
        monitor = scheduler_snapshot(database, journal_path=journal_path, clock=lambda: as_of)
        lane = next(row for row in monitor["lanes"] if row["id"] == "SOLUSD:D1")
        assert lane["latest_canonical_observation"] == "2026-07-13T00:00:00+00:00"
        assert lane["publication_result"]["provider"] == "BINANCE"
        truth = truth_state_for_lane(database, symbol="SOLUSD", timeframe="D1", as_of=as_of)
        assert truth["freshness"]["state"] == "Current"
        last = acquisition_capability_projection(database, symbol="SOLUSD", now=as_of)["rows"]
        assert any(
            row["last_successful_provider"]
            and row["last_successful_provider"]["provider"] == "BINANCE"
            and row["last_successful_provider"]["provider_symbol"] == "SOLUSD"
            and row["last_successful_provider"]["mapping_class"] == "EXACT_REPRESENTATION"
            for row in last if row["timeframe"] == "D1"
        )
        with open_read_only(database) as connection:
            published = json.loads(connection.execute(
                "SELECT detail FROM ingest_runs WHERE ingest_run_id='run-spec047'"
            ).fetchone()[0])
        assert (published["provider_symbol"], published["mapping_class"]) == (
            "SOLUSD", "EXACT_REPRESENTATION"
        )


def test_first_scheduler_launch_persists_reconciliation_without_touching_bars() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        journal_path = Path(directory) / "scheduler.json"
        _registered_sol(database)
        before = database.read_bytes()
        first = scheduler_snapshot(
            database,
            journal_path=journal_path,
            clock=lambda: datetime(2026, 7, 14, 12, tzinfo=UTC),
        )["capability_reconciliation"]
        second = scheduler_snapshot(
            database,
            journal_path=journal_path,
            clock=lambda: datetime(2026, 7, 14, 13, tzinfo=UTC),
        )["capability_reconciliation"]
        assert first == second
        assert first["canonical_observations_action"] == "RETAINED_UNCHANGED"
        assert first["provider_mapping_archive_action"] == "NONE"
        assert {"lane", "previous_displayed_capability", "actual_provider_capability", "mapping_status", "required_operator_decision"}.issubset(first["rows"][0])
        assert database.read_bytes() == before


def test_binance_adapter_excludes_still_open_candle_before_immutable_ingest() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _registered_sol(database)
        ensure_commissioned_lane(database, "SOLUSD", "M5", observed_at="2026-07-11T00:00:00+00:00")
        now = datetime(2026, 7, 14, 12, 7, tzinfo=UTC)
        completed_open = int(datetime(2026, 7, 14, 11, 55, tzinfo=UTC).timestamp() * 1000)
        active_open = int(datetime(2026, 7, 14, 12, 5, tzinfo=UTC).timestamp() * 1000)
        payload = json.dumps([
            [completed_open, "1", "2", "0", "1", "10", completed_open + 300_000 - 1],
            [active_open, "1", "2", "0", "1", "10", active_open + 300_000 - 1],
        ]).encode()
        result = acquire_binance(
            database,
            asset="SOLUSD",
            timeframe="M5",
            provider_symbol="SOLUSD",
            from_date="2026-07-14",
            through_date="2026-07-14",
            mapping_class="EXACT_REPRESENTATION",
            fetch=lambda _: payload,
            clock=lambda: now,
        )
        assert result["inserted"] == 1
        assert result["incomplete_rows_excluded"] == 1
        with open_read_only(database) as connection:
            edges = connection.execute(
                "SELECT open_time_utc,close_time_utc FROM bars WHERE asset='SOLUSD' AND timeframe='M5'"
            ).fetchall()
        assert edges == [(completed_open // 1000, completed_open // 1000 + 300)]
