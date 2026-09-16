from __future__ import annotations

import threading
import time
from pathlib import Path

from fragarach_ii.commands.acquire import _await_service_fetch_result
from fragarach_ii.scheduler_daemon import ServicePaths
from fragarach_ii.scheduler_state_store import SchedulerStateStore
from fragarach_ii.storage import initialize_database


def test_service_fetch_submission_resolves_to_durable_lane_result(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "scheduler.json"
    initialize_database(database)
    paths = ServicePaths.create(
        database,
        journal=journal,
        support=tmp_path / "support",
        home=tmp_path,
    )
    store = SchedulerStateStore(database, journal)
    store.save({
        "lanes": {
            "GBPCHF:D1": {
                "operator_fetch_pending": {"id": "operator-fetch-1"},
            }
        }
    })

    def publish_result() -> None:
        time.sleep(0.05)
        SchedulerStateStore(database, journal).save({
            "lanes": {
                "GBPCHF:D1": {
                    "last_operator_fetch_result": {
                        "operation_id": "operator-fetch-1",
                        "work_class": "OPERATOR_FETCH",
                        "outcome": "SUCCESS",
                        "published_observations": 4,
                    }
                }
            }
        })

    publisher = threading.Thread(target=publish_result)
    publisher.start()
    result = _await_service_fetch_result(
        paths,
        {
            "operation_id": "operator-fetch-1",
            "work_class": "OPERATOR_FETCH",
            "outcome": "QUEUED",
            "symbol": "GBPCHF",
            "timeframe": "D1",
        },
        timeout_seconds=2,
        poll_seconds=0.01,
    )
    publisher.join(timeout=2)

    assert result["outcome"] == "SUCCESS"
    assert result["published_observations"] == 4
    assert result["symbol"] == "GBPCHF"
    assert result["timeframe"] == "D1"


def test_service_fetch_timeout_is_not_reported_as_complete(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    journal = tmp_path / "scheduler.json"
    initialize_database(database)
    paths = ServicePaths.create(
        database,
        journal=journal,
        support=tmp_path / "support",
        home=tmp_path,
    )
    SchedulerStateStore(database, journal).save({"lanes": {}})

    result = _await_service_fetch_result(
        paths,
        {
            "operation_id": "operator-fetch-2",
            "work_class": "OPERATOR_FETCH",
            "outcome": "QUEUED",
            "symbol": "GBPCHF",
            "timeframe": "D1",
        },
        timeout_seconds=0.02,
        poll_seconds=0.01,
    )

    assert result["outcome"] == "WAITING"
    assert "pending" in str(result["reason"]).lower()
