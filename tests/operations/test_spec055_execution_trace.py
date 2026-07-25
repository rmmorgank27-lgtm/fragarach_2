from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fragarach_ii.execution_trace import (
    CYCLE_LIMIT,
    REQUIRED_EVENTS,
    TIMING_RECORD_LIMIT,
    TRACE_EVENT_LIMIT,
    record_event,
    record_timing,
    trace_for_lane,
)
from fragarach_ii.providers.config import load_provider_config
from fragarach_ii.providers.twelve_data import _request
from fragarach_ii.providers.twelve_data_adapter import stage_twelve_data_response
from fragarach_ii.scheduler_service import SchedulerJournal, run_due_acquisitions
from fragarach_ii.storage import registered_writer
from tests.operations.test_spec041_scheduler import _epoch
from tests.validation.test_d1_session_validation import _create_lane


AT = datetime(2026, 7, 14, 21, 0, tzinfo=UTC)


def _advance_d1(database: Path) -> None:
    edge = _epoch("2026-07-14T00:00:00+00:00")
    with registered_writer(database) as connection:
        run_id = connection.execute(
            "SELECT created_by_ingest_run_id FROM bars WHERE asset='AUDUSD' LIMIT 1"
        ).fetchone()[0]
        connection.execute(
            """INSERT OR IGNORE INTO bars
               (asset,timeframe,open_time_utc,open,high,low,close,
                created_by_ingest_run_id,updated_by_ingest_run_id)
               VALUES ('AUDUSD','D1',?,'1','2','0','1',?,?)""",
            (edge, run_id, run_id),
        )
        connection.execute(
            """UPDATE lane_state SET high_watermark_open_time_utc=?,
               state_version=state_version+1,updated_at_utc=?
               WHERE asset='AUDUSD' AND timeframe='D1'""",
            (edge, AT.isoformat()),
        )


def test_intraday_provider_bound_covers_the_requested_day() -> None:
    config = load_provider_config(timeframe="M5")
    request = _request(
        config, "AUD/USD", datetime(2026, 7, 14).date(),
        datetime(2026, 7, 14).date(), 288,
    )
    assert "start_date=2026-07-14T00%3A00%3A00" in request.target
    assert "end_date=2026-07-14T23%3A59%3A59" in request.target
    assert "apikey" not in request.target.lower()


def test_intraday_admission_uses_the_provider_local_request_date() -> None:
    body = json.dumps({
        "meta": {"symbol": "AUD/USD", "interval": "5min"},
        "values": [{
            "datetime": "2026-07-14 21:45:00", "open": "1",
            "high": "2", "low": "0", "close": "1",
        }],
        "status": "ok",
    }).encode()
    batch = stage_twelve_data_response(
        body, asset="AUDUSD", provider_symbol="AUD/USD",
        from_date=datetime(2026, 7, 14).date(),
        through_date=datetime(2026, 7, 14).date(), raw_block_id="raw-fixture",
        received_at="2026-07-15T01:51:00+00:00", timeframe="M5",
        asset_class="FX", observed_at=datetime(2026, 7, 15, 1, 51, tzinfo=UTC),
    )
    assert not batch.rejections
    assert batch.bars[0].timestamp == int(datetime(2026, 7, 15, 1, 45, tzinfo=UTC).timestamp())


def test_stable_trace_retry_then_complete_and_remove(tmp_path: Path) -> None:
    database, journal_path = tmp_path / "authority.sqlite3", tmp_path / "scheduler.json"
    _create_lane(database, "AUDUSD", ["2026-07-13"])

    def unchanged(_database, **_kwargs):
        return {"received": 1, "staged": 1, "inserted": 0, "corrected": 0, "unchanged": 1}

    first = run_due_acquisitions(
        database, at=AT, credential="fixture", journal_path=journal_path,
        acquirer=unchanged,
    )
    first_item = next(item for item in first["acquisition_queue"] if item["lane"] == "AUDUSD:D1")
    trace_id = first_item["trace_id"]
    assert first_item["stop_reason"] == "CANONICAL_UNCHANGED"
    deferred_trace = trace_for_lane(SchedulerJournal(database, journal_path).data, "AUDUSD", "D1")
    assert deferred_trace["final_lane_state"] == "BEHIND"

    def advancing(_database, **_kwargs):
        _advance_d1(database)
        return {"received": 1, "staged": 1, "inserted": 1, "corrected": 0, "unchanged": 0}

    second = run_due_acquisitions(
        database, at=AT + timedelta(seconds=61), credential="fixture",
        journal_path=journal_path, acquirer=advancing, catch_up=True,
    )
    assert not any(item["lane"] == "AUDUSD:D1" for item in second["acquisition_queue"])
    journal = SchedulerJournal(database, journal_path)
    trace = trace_for_lane(journal.data, "AUDUSD", "D1")
    assert trace["trace_id"] == trace_id
    assert trace["attempt_count"] == 2
    assert trace["queue_disposition"] == "REMOVED"
    assert trace["final_lane_state"] == "CURRENT"
    assert trace["stop_reason"] is None
    assert trace["events"][-2]["event"] == "QUEUE_COMPLETED"
    assert trace["events"][-1]["event"] == "LANE_CURRENT"


def test_ordered_success_events_cycle_accounting_and_edges(tmp_path: Path) -> None:
    database, journal_path = tmp_path / "authority.sqlite3", tmp_path / "scheduler.json"
    _create_lane(database, "AUDUSD", ["2026-07-13"])

    def advancing(_database, **_kwargs):
        _advance_d1(database)
        return {"received": 2, "staged": 1, "inserted": 1, "corrected": 0, "unchanged": 0}

    snapshot = run_due_acquisitions(
        database, at=AT, credential="fixture", journal_path=journal_path,
        acquirer=advancing,
    )
    journal = SchedulerJournal(database, journal_path)
    trace = trace_for_lane(journal.data, "AUDUSD", "D1")
    names = [event["event"] for event in trace["events"]]
    assert names == list(REQUIRED_EVENTS)
    edge = next(event for event in trace["events"] if event["event"] == "CANONICAL_EDGE_ADVANCED")
    assert edge["canonical_edge_before"] == "2026-07-13T00:00:00+00:00"
    assert edge["canonical_edge_after"] == "2026-07-14T00:00:00+00:00"
    cycle = snapshot["execution"]
    assert cycle["eligible_count"] == cycle["selected_count"] >= 1
    assert cycle["worker_allocated_count"] >= 1
    assert cycle["request_started_count"] == cycle["request_completed_count"] >= 1
    assert cycle["canonical_advanced_count"] == cycle["queue_completed_count"] >= 1
    assert isinstance(cycle["cycle_overrun"], bool)
    timings = journal.data["operation_timing_records"]
    assert {item["step_name"] for item in timings} >= {
        "planning_and_reservation", "provider_execution_and_admission",
        "lane_total", "cycle_total",
    }
    assert all("duration_ms" in item for item in timings)


def test_cycle_overrun_uses_elapsed_monotonic_time(tmp_path: Path) -> None:
    database, journal_path = tmp_path / "authority.sqlite3", tmp_path / "scheduler.json"
    _create_lane(database, "AUDUSD", ["2026-07-13"])
    tick = [0.0]

    def monotonic() -> float:
        tick[0] += 1.0
        return tick[0]

    def advancing(_database, **_kwargs):
        _advance_d1(database)
        return {"received": 1, "staged": 1, "inserted": 1, "corrected": 0, "unchanged": 0}

    snapshot = run_due_acquisitions(
        database, at=AT, credential="fixture", journal_path=journal_path,
        acquirer=advancing, monotonic=monotonic,
    )
    cycle = snapshot["execution"]
    assert cycle["duration_ms"] > 5_000
    assert cycle["cycle_overrun"] is True
    assert cycle["cycle_overrun_ms"] == cycle["duration_ms"] - 5_000


def test_trace_persistence_allow_list_redacts_secrets() -> None:
    journal: dict[str, object] = {}
    item = {
        "trace_id": "trace", "lane": "AUDUSD:M5", "symbol": "AUDUSD",
        "timeframe": "M5", "attempt_number": 1,
    }
    record_event(
        journal, item, "REQUEST_STARTED", cycle_id="cycle", provider="TWELVE_DATA",
        credential="forbidden-secret", api_key="also-forbidden",
    )
    serialized = json.dumps(journal)
    assert "forbidden-secret" not in serialized
    assert "also-forbidden" not in serialized
    event = journal["execution_trace_events"][0]
    required = {
        "trace_id", "lane_id", "symbol", "timeframe", "attempt_number", "event",
        "timestamp", "result", "reason_code", "duration_ms", "scheduler_cycle_id",
    }
    assert required.issubset(event)


def test_timing_trace_is_operator_readable_and_redacted() -> None:
    journal: dict[str, object] = {}
    record = record_timing(
        journal, operation_id="operation", symbol="AUDUSD", timeframe="H1",
        intent="OPERATOR_FETCH", provider="TWELVE_DATA", step_name="provider_execution",
        started_at=AT, ended_at=AT + timedelta(milliseconds=125),
        rows_read=10, rows_written=8, provider_calls=1, credential="forbidden-secret",
    )
    assert record["duration_ms"] == 125.0
    assert record["operation_id"] == "operation"
    assert record["rows_written"] == 8
    assert journal["operation_timing_records"] == [record]
    assert "forbidden-secret" not in json.dumps(journal)


def test_legacy_oversized_operational_history_is_compacted(tmp_path: Path) -> None:
    journal: dict[str, object] = {
        "contract": "fragarach_ii.scheduler_journal.v4",
        "execution_trace_events": [{"event": index} for index in range(TRACE_EVENT_LIMIT + 3)],
        "operation_timing_records": [{"step_name": index} for index in range(TIMING_RECORD_LIMIT + 3)],
        "scheduler_cycles": [{"cycle_id": index} for index in range(CYCLE_LIMIT + 3)],
    }
    journal_path = tmp_path / "scheduler.json"
    journal_path.write_text(json.dumps(journal), encoding="utf-8")

    loaded = SchedulerJournal(tmp_path / "authority.sqlite3", journal_path)

    assert loaded.migration_pending is True
    assert len(loaded.data["execution_trace_events"]) == TRACE_EVENT_LIMIT
    assert len(loaded.data["operation_timing_records"]) == TIMING_RECORD_LIMIT
    assert len(loaded.data["scheduler_cycles"]) == CYCLE_LIMIT
    assert loaded.data["execution_trace_events"][0]["event"] == 3
