from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import (
    acquisition_plan,
    build_rate_budgets,
    credential_map,
    load_provider_profiles,
)
from fragarach_ii.estate_truth_service import estate_truth_state
from fragarach_ii.freshness import assess_lane_freshness
from fragarach_ii.operational_schedule import schedule_for_lane
from fragarach_ii.scheduler_service import SchedulerJournal, run_operator_fetch
from fragarach_ii.storage import open_read_only, registered_writer


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "data/runtime/spec002_real_evidence_acceptance.sqlite3"
NOW = datetime(2026, 7, 15, 2, 0, tzinfo=UTC)


def _runtime_fixture(root: Path) -> tuple[Path, Path]:
    database = root / "authority.sqlite3"
    shutil.copy2(RUNTIME, database)
    shutil.copy2(Path(f"{RUNTIME}.provider-facts.json"), Path(f"{database}.provider-facts.json"))
    # The native runtime is intentionally live and may already have converged.
    # Establish the observed regression boundary in this disposable copy so the
    # test remains deterministic after a successful production publication.
    cutoff = int(datetime(2026, 7, 14, tzinfo=UTC).timestamp())
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER IF EXISTS provenance_no_delete")
        connection.execute(
            "DELETE FROM provenance WHERE symbol IN ('DJI','SPY') AND timeframe='D1' AND timestamp>=?",
            (cutoff,),
        )
        connection.execute(
            "DELETE FROM bars WHERE asset IN ('DJI','SPY') AND timeframe='D1' AND open_time_utc>=?",
            (cutoff,),
        )
    return database, root / "scheduler.json"


def _plan(database: Path, journal_path: Path, symbol: str) -> dict[str, object]:
    journal = SchedulerJournal(database, journal_path)
    profiles = tuple(load_provider_profiles())
    credentials = credential_map("fixture")
    budgets = build_rate_budgets(
        profiles, journal.providers, wall_clock=lambda: NOW, credential="fixture"
    )
    with open_read_only(database) as connection:
        freshness = assess_lane_freshness(
            connection, symbol=symbol, timeframe="D1", as_of=NOW
        )
    return acquisition_plan(
        database, symbol=symbol, timeframe="D1",
        canonical_edge=str(freshness["latest_canonical_observation"]),
        expected_edge=str(freshness["expected_latest"]),
        missing_start="2026-07-14", missing_end="2026-07-14",
        scheduled_boundary=f"SPEC059:{symbol}", profiles=profiles,
        provider_state=journal.providers, budgets=budgets, credentials=credentials,
        now=NOW, work_class="OPERATOR_FETCH",
    )


def _publish(database: Path, **kwargs) -> dict[str, object]:
    symbol = str(kwargs["asset"])
    provider = str(kwargs["provider"])
    provider_symbol = str(kwargs["provider_symbol"])
    identifier = uuid.uuid4().hex
    raw_id, run_id = f"raw-spec059-{identifier}", f"run-spec059-{identifier}"
    payload = f"spec-059:{symbol}:2026-07-14".encode()
    opened = int(datetime(2026, 7, 14, tzinfo=UTC).timestamp())
    with registered_writer(database) as connection:
        connection.execute(
            """INSERT INTO raw_blocks
               (raw_block_id,sha256,source_name,source_locator,media_type,
                received_at_utc,byte_length,payload)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                raw_id, hashlib.sha256(payload).hexdigest(), provider,
                f"{provider_symbol}:{identifier}", "application/json",
                NOW.isoformat(), len(payload), payload,
            ),
        )
        connection.execute(
            """INSERT INTO ingest_runs
               (ingest_run_id,kind,status,started_at_utc,finished_at_utc,raw_block_id,detail)
               VALUES(?,'provider_yahoo_finance','committed',?,?,?,?)""",
            (
                run_id, NOW.isoformat(), NOW.isoformat(), raw_id,
                json.dumps({
                    "asset": symbol, "timeframe": "D1", "provider": provider,
                    "provider_symbol": provider_symbol,
                    "mapping_class": kwargs.get("mapping_class"),
                }, separators=(",", ":")),
            ),
        )
        connection.execute(
            """INSERT OR IGNORE INTO bars
               (asset,timeframe,open_time_utc,open,high,low,close,
                created_by_ingest_run_id,updated_by_ingest_run_id)
               VALUES(?,'D1',?,'1','2','0','1',?,?)""",
            (symbol, opened, run_id, run_id),
        )
    return {"inserted": 1, "corrected": 0, "unchanged": 0, "received": 1}


def test_dji_and_spy_resolve_us_calendar_and_yahoo_fallback() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database, journal_path = _runtime_fixture(Path(directory))
        with open_read_only(database) as connection:
            for symbol in ("DJI", "SPY"):
                freshness = assess_lane_freshness(
                    connection, symbol=symbol, timeframe="D1", as_of=NOW
                )
                schedule = schedule_for_lane(
                    connection, symbol=symbol, timeframe="D1", after=NOW
                )
                assert freshness["calendar_id"] == "US_EQUITIES_D1_V1"
                assert freshness["expected_latest"] == "2026-07-14T00:00:00+00:00"
                assert freshness["expected_edge_state"] == "EXPECTED_EDGE_AVAILABLE"
                assert freshness["state"] == "Behind"
                assert schedule["calendar_id"] == "US_EQUITIES_D1_V1"
                assert schedule["timezone"] == "America/New_York"

        for symbol, approved_symbol, mapping_class in (
            ("DJI", "^DJI", "APPROVED_PROVIDER_ALIAS"),
            ("SPY", "SPY", "EXACT_REPRESENTATION"),
        ):
            plan = _plan(database, journal_path, symbol)
            considered = {row["provider"]: row for row in plan["providers_considered"]}
            assert considered["TWELVE_DATA"]["reason"] == "NO_APPROVED_MAPPING"
            assert considered["TWELVE_DATA"]["provider_symbol"] is None
            assert considered["YAHOO_FINANCE"]["eligible"] is True
            assert considered["YAHOO_FINANCE"]["provider_symbol"] == approved_symbol
            assert considered["YAHOO_FINANCE"]["mapping_class"] == mapping_class
            assert plan["selected_provider"] == "YAHOO_FINANCE"
            assert plan["selected_provider_symbol"] == approved_symbol


def test_manual_updates_advance_canonical_edges_and_estate_truth() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database, journal_path = _runtime_fixture(Path(directory))
        for symbol in ("DJI", "SPY"):
            result = run_operator_fetch(
                database, symbol=symbol, timeframe="D1", credential="fixture",
                requested_mode="update", requested_start="2026-07-14",
                requested_end="2026-07-14", reviewed_historical_range=True,
                journal_path=journal_path, at=NOW, acquirer=_publish,
            )
            assert result["outcome"] == "SUCCESS"
            assert result["canonical_edge_before"] == "2026-07-13T00:00:00+00:00"
            assert result["canonical_edge_after"] == "2026-07-14T00:00:00+00:00"
            assert result["providers_attempted"] == ["YAHOO_FINANCE"]

        estate = estate_truth_state(database, clock=lambda: NOW)
        states = {
            (row["symbol"], row["timeframe"]): row["operational_state"]
            for row in estate["commissioning_matrix"]
        }
        assert states[("DJI", "D1")] == "Current"
        assert states[("SPY", "D1")] == "Current"


def test_forex_and_metals_d1_calendar_planning_is_unchanged() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database, _ = _runtime_fixture(Path(directory))
        with open_read_only(database) as connection:
            forex = assess_lane_freshness(
                connection, symbol="AUDUSD", timeframe="D1", as_of=NOW
            )
            metals = assess_lane_freshness(
                connection, symbol="XAUUSD", timeframe="D1", as_of=NOW
            )
        assert (forex["calendar_id"], forex["expected_edge_state"]) == (
            "FX_D1_V1", "NO_NEW_COMPLETED_SESSION"
        )
        assert (metals["calendar_id"], metals["expected_edge_state"]) == (
            "METALS_D1_V1", "NO_NEW_COMPLETED_SESSION"
        )
