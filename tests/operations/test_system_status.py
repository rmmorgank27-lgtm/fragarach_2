from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3

from fragarach_ii.system_status import (
    SCHEMA,
    build_truth_authority_status,
    publish_truth_authority_status,
)


NOW = datetime(2026, 8, 29, 4, 0, tzinfo=UTC)


def monitor(*, heartbeat: datetime = NOW, state: str = "RUNNING", blocked: int = 0) -> dict:
    return {
        "service_state": state,
        "service_build": "fixture",
        "heartbeat_time": heartbeat.isoformat(),
        "next_run": (NOW + timedelta(minutes=1)).isoformat(),
        "operational_health": {
            "overall_operational_health": "IDLE",
            "blocked_queue_depth": blocked,
        },
    }


def facts(*, refreshed: datetime = NOW, missing_routes: int = 0, providers: bool = True) -> dict:
    return {
        "registration_count": 2,
        "registered_count": 2,
        "symbol_count": 1,
        "missing_routes": missing_routes,
        "latest_truth_refresh": refreshed.isoformat(),
        "providers": {
            "YAHOO_FINANCE": {
                "lanes": 2,
                "contracts": ["YAHOO_FINANCE_CHART_D1_V1"],
                "last_refresh": refreshed.isoformat(),
            }
        } if providers else {},
    }


def test_normal_truth_authority_record_is_operational() -> None:
    payload = build_truth_authority_status(Path("fixture.sqlite3"), monitor(), now=NOW, facts=facts(missing_routes=1))
    assert payload["schema"] == SCHEMA
    assert payload["displayName"] == "Fragarach_2 — Truth Authority"
    assert payload["state"] == "OPERATIONAL"
    yahoo = next(item for item in payload["capabilities"] if item["id"] == "provider-route-yahoo-finance")
    assert "fallback/process availability alone is never authoritative" in yahoo["reason"]
    assert "current bar provenance is reported separately" in yahoo["reason"]
    catalogue = next(item for item in payload["capabilities"] if item["id"] == "catalogue-symbol-truth")
    assert catalogue["state"] == "OPERATIONAL"
    assert "not missing registered lanes" in catalogue["reason"]
    unresolved = next(item for item in payload["capabilities"] if item["id"] == "provider-route-unresolved-lookups")
    assert unresolved["state"] == "OPERATIONAL"
    assert unresolved["affectedConsumers"] == []


def test_stale_truth_and_failed_service_cannot_be_green() -> None:
    stale = NOW - timedelta(hours=80)
    assert build_truth_authority_status(Path("fixture.sqlite3"), monitor(), now=NOW, facts=facts(refreshed=stale))["state"] == "FAILURE"
    assert build_truth_authority_status(Path("fixture.sqlite3"), monitor(state="STOPPED"), now=NOW, facts=facts())["state"] == "FAILURE"


def test_missing_provider_and_blocked_lanes_name_affected_consumers() -> None:
    payload = build_truth_authority_status(Path("fixture.sqlite3"), monitor(blocked=2), now=NOW, facts=facts(missing_routes=1, providers=False))
    assert payload["state"] == "FAILURE"
    affected = [item for item in payload["capabilities"] if item["affectedConsumers"]]
    assert affected
    assert "Morphix" in affected[0]["affectedConsumers"]
    assert "truth_score" not in json.dumps(payload).lower()


def test_empty_startup_register_is_attention_not_catalogue_failure(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    database.touch()
    startup = {**facts(), "registration_count": 0, "registered_count": 0}
    payload = build_truth_authority_status(database, monitor(), now=NOW, facts=startup)
    catalogue = next(item for item in payload["capabilities"] if item["id"] == "catalogue-symbol-truth")
    assert catalogue["state"] == "ATTENTION"
    assert "recovering after service start" in catalogue["reason"]


def test_atomic_publication_is_valid_after_restart(tmp_path: Path) -> None:
    output = tmp_path / "fragarach-system-status.json"
    publish_truth_authority_status(tmp_path / "fixture.sqlite3", monitor(), now=NOW, destination=output, facts=facts())
    first = json.loads(output.read_text())
    publish_truth_authority_status(tmp_path / "fixture.sqlite3", monitor(state="STOPPED"), now=NOW + timedelta(seconds=1), destination=output, facts=facts())
    second = json.loads(output.read_text())
    assert first["state"] == "OPERATIONAL"
    assert second["state"] == "FAILURE"
    assert second["lastGoodAt"] == first["lastGoodAt"]
    assert not list(tmp_path.glob(f".{output.name}.*"))
