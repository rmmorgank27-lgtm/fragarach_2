from __future__ import annotations

import base64
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.commissioning_authority import project_required_lanes
from fragarach_ii.estate_truth_service import estate_truth_state
from fragarach_ii.lane_commissioning import commissioned_lane_keys, ensure_commissioned_lane
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.scheduler_integrity import active_universe
from fragarach_ii.scheduler_service import SchedulerJournal, run_due_acquisitions, run_operator_fetch
from fragarach_ii.storage import initialize_database, open_read_only, register_instrument, registered_writer


NOW = datetime(2026, 7, 14, 14, 2, tzinfo=UTC)


def _register_gbpaud(database: Path) -> None:
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
        database, candidate_from_dict(candidate), registered_at_utc=NOW.isoformat()
    )


def _publish_h1(database: Path, **kwargs) -> dict[str, object]:
    payload = b"spec-058-gbpaud-h1"
    opened = int(datetime(2026, 7, 14, 13, 0, tzinfo=UTC).timestamp())
    with registered_writer(database) as connection:
        connection.execute(
            """INSERT OR IGNORE INTO raw_blocks
               (raw_block_id,sha256,source_name,source_locator,media_type,
                received_at_utc,byte_length,payload)
               VALUES('raw-spec058',?,'TWELVE_DATA','GBP/AUD','application/json',?,?,?)""",
            (hashlib.sha256(payload).hexdigest(), NOW.isoformat(), len(payload), payload),
        )
        connection.execute(
            """INSERT OR IGNORE INTO ingest_runs
               (ingest_run_id,kind,status,started_at_utc,finished_at_utc,raw_block_id,detail)
               VALUES('run-spec058','provider_twelve_data','committed',?,?,
                      'raw-spec058',?)""",
            (
                NOW.isoformat(), NOW.isoformat(),
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
               VALUES('GBPAUD','H1',?,?,'1.90','1.91','1.89','1.905',
                      'run-spec058','run-spec058')""",
            (opened, opened + 3600),
        )
    return {"inserted": 1, "corrected": 0, "unchanged": 0, "received": 1}


def test_uncommissioned_manual_fetch_publishes_without_scheduler_ownership() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database, journal_path = root / "authority.sqlite3", root / "scheduler.json"
        _register_gbpaud(database)

        result = run_operator_fetch(
            database, symbol="GBPAUD", timeframe="H1", credential="fixture",
            requested_mode="initial", requested_start="2026-07-14",
            requested_end="2026-07-14", reviewed_historical_range=True,
            journal_path=journal_path, at=NOW, acquirer=_publish_h1,
        )

        assert result["outcome"] == "SUCCESS"
        assert result["canonical_edge_after"] == "2026-07-14T14:00:00+00:00"
        with open_read_only(database) as connection:
            assert connection.execute(
                "SELECT count(*) FROM bars WHERE asset='GBPAUD' AND timeframe='H1'"
            ).fetchone()[0] == 1
            assert ("GBPAUD", "H1") not in commissioned_lane_keys(connection)
        assert "GBPAUD:H1" not in active_universe(database)["active_lanes"]
        journal = SchedulerJournal(database, journal_path)
        assert "GBPAUD:H1" not in journal.data["lanes"]
        assert not any(item.get("lane") == "GBPAUD:H1" for item in journal.data["acquisition_queue"])

        automatic_calls: list[str] = []
        run_due_acquisitions(
            database, at=NOW, credential="fixture", journal_path=journal_path,
            catch_up=True,
            acquirer=lambda _database, **kwargs: automatic_calls.append(kwargs["timeframe"]) or {},
        )
        assert automatic_calls == []

        estate = estate_truth_state(database, clock=lambda: NOW)
        state = next(row for row in estate["commissioning_matrix"] if row["id"] == "GBPAUD:H1")
        assert state["operational_state"] == "Not Commissioned"
        assert state["commissioned"] is False
        assert next(
            row for row in estate["truth_matrix"]
            if row["symbol"] == "GBPAUD" and row["timeframe"] == "H1"
        )["latest_canonical_observation"] == "2026-07-14T14:00:00+00:00"


def test_commissioning_existing_manual_lane_only_enables_scheduler_ownership() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database, journal_path = root / "authority.sqlite3", root / "scheduler.json"
        _register_gbpaud(database)
        run_operator_fetch(
            database, symbol="GBPAUD", timeframe="H1", credential="fixture",
            requested_mode="initial", requested_start="2026-07-14",
            requested_end="2026-07-14", reviewed_historical_range=True,
            journal_path=journal_path, at=NOW, acquirer=_publish_h1,
        )
        with open_read_only(database) as connection:
            before = (
                connection.execute("SELECT count(*) FROM bars WHERE asset='GBPAUD' AND timeframe='H1'").fetchone()[0],
                connection.execute("SELECT count(*) FROM ingest_runs").fetchone()[0],
            )

        ensure_commissioned_lane(database, "GBPAUD", "H1", observed_at="2026-07-14T14:03:00+00:00")

        with open_read_only(database) as connection:
            after = (
                connection.execute("SELECT count(*) FROM bars WHERE asset='GBPAUD' AND timeframe='H1'").fetchone()[0],
                connection.execute("SELECT count(*) FROM ingest_runs").fetchone()[0],
            )
            assert ("GBPAUD", "H1") in commissioned_lane_keys(connection)
        assert after == before
        assert "GBPAUD:H1" in active_universe(database)["active_lanes"]


def test_truth_presentation_has_only_four_operational_meanings() -> None:
    rows = project_required_lanes(
        [("GBPAUD", "FX")], {("GBPAUD", "D1"), ("GBPAUD", "H1"), ("GBPAUD", "M30")},
        evidence_counts={("GBPAUD", "D1"): 1, ("GBPAUD", "H1"): 0, ("GBPAUD", "M30"): 0},
        operational_states={("GBPAUD", "D1"): "Current", ("GBPAUD", "H1"): "Behind", ("GBPAUD", "M30"): "Unavailable"},
    )
    states = {row["timeframe"]: row["operational_state"] for row in rows}
    assert states == {"D1": "Current", "H1": "Behind", "M30": "Unavailable", "M5": "Not Commissioned"}
