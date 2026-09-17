from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import ProviderProfile
from fragarach_ii.freshness import assess_lane_freshness
from fragarach_ii.lane_update_register import LaneUpdateRegister
from fragarach_ii.provider_attempt_ledger import ProviderAttemptLedger
from fragarach_ii.routing_service import current_revision, routing_snapshot
from fragarach_ii.scheduler_service import SchedulerJournal, run_due_acquisitions, scheduler_snapshot
from fragarach_ii.storage import open_read_only
from tests.operations.test_spec063_time_triggered_lane_scheduler import _m5_lane


NOW = datetime(2026, 7, 14, 0, 10, tzinfo=UTC)


def _fx_profile() -> ProviderProfile:
    return ProviderProfile(
        provider="TWELVE_DATA", enabled=True,
        supported_asset_classes=("FX",), supported_timeframes=("M5",),
        credential_environment=None, entitlement_state="AVAILABLE",
        request_limit=55, request_window_seconds=60, maximum_rows_per_request=4_000,
        history_limit_days=None, cost_class=0, priority=1, cooldown_seconds=0,
        mappings=({
            "asset": "AUDUSD", "symbol": "AUD/USD", "timeframes": ["M5"],
            "mapping_class": "EXACT_REPRESENTATION", "reviewed_status": "REVIEWED",
            "authority_source": "TEST",
        },),
        rate_policy_verified=True,
    )


def test_ledger_is_idempotent_bounded_and_releases_only_undispatched(tmp_path: Path) -> None:
    ledger = ProviderAttemptLedger(tmp_path / "authority.sqlite3")
    key = dict(lane="AUDUSD:M5", expected_boundary="2026-07-14T00:05:00+00:00",
               routing_revision="revision-1", provider="MT5_BRIDGE", at=NOW)
    first = ledger.reserve(request_id="mt5-1", **key)
    assert first is not None and first["ordinal"] == 1
    assert ledger.reserve(request_id="mt5-1", **key)["ordinal"] == 1
    ledger.release_undispatched("mt5-1", reason="QUEUE_REJECTED")
    assert ledger.attempts(**{key_name: key[key_name] for key_name in (
        "lane", "expected_boundary", "routing_revision"
    )}) == []
    for index in range(2, 5):
        attempt = ledger.reserve(request_id=f"mt5-{index}", **key)
        assert attempt is not None and attempt["ordinal"] == index
        ledger.mark_dispatched(f"mt5-{index}", at=NOW)
        ledger.release_undispatched(f"mt5-{index}", reason="MUST_NOT_RELEASE")
    assert ledger.reserve(request_id="http-four", provider="TWELVE_DATA", **{
        key_name: key[key_name] for key_name in (
            "lane", "expected_boundary", "routing_revision", "at"
        )
    }) is None
    assert ledger.reserve(request_id="new-boundary", provider="TWELVE_DATA",
                          lane=key["lane"], expected_boundary="2026-07-14T00:10:00+00:00",
                          routing_revision=key["routing_revision"], at=NOW) is not None


def test_three_mt5_attempts_prevent_http_attempt_four(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    register = LaneUpdateRegister(database)
    register.audit_estate(at=NOW, reason="TEST")
    with open_read_only(database) as connection:
        boundary = str(assess_lane_freshness(
            connection, symbol="AUDUSD", timeframe="M5", as_of=NOW,
        )["expected_latest"])
    revision = str(current_revision(database)["routing_revision"])
    ledger = ProviderAttemptLedger(database)
    for index in range(3):
        request_id = f"mt5-{index}"
        assert ledger.reserve(
            request_id=request_id, lane="AUDUSD:M5",
            expected_boundary=boundary, routing_revision=revision,
            provider="MT5_BRIDGE", at=NOW,
        ) is not None
        ledger.mark_dispatched(request_id, at=NOW)
    calls: list[str] = []
    run_due_acquisitions(
        database, at=NOW, credential=None, journal_path=tmp_path / "scheduler.json",
        acquirer=lambda *_args, **_kwargs: calls.append("HTTP") or {},
        provider_profiles=(_fx_profile(),), time_triggered=True,
    )
    assert calls == []
    lane = SchedulerJournal(database, tmp_path / "scheduler.json").lane("AUDUSD", "M5")
    assert lane["reason"] == "PROVIDER_ATTEMPT_LIMIT_REACHED"
    assert len(ledger.attempts(
        lane="AUDUSD:M5", expected_boundary=boundary,
        routing_revision=revision,
    )) == 3
    route = next(item for item in routing_snapshot(database)["lanes"] if item["id"] == "AUDUSD:M5")
    assert route["attempt_state"]["count"] == 3
    assert route["attempt_state"]["providers"] == ["MT5_BRIDGE"] * 3
    monitor = scheduler_snapshot(database, clock=lambda: NOW, journal_path=tmp_path / "scheduler.json")
    monitored = next(item for item in monitor["lanes"] if item["id"] == "AUDUSD:M5")
    assert monitored["attempt_count"] == 3


def test_http_fallback_records_second_attempt_after_mt5(tmp_path: Path) -> None:
    database = _m5_lane(tmp_path)
    LaneUpdateRegister(database).audit_estate(at=NOW, reason="TEST")
    with open_read_only(database) as connection:
        boundary = str(assess_lane_freshness(
            connection, symbol="AUDUSD", timeframe="M5", as_of=NOW,
        )["expected_latest"])
    revision = str(current_revision(database)["routing_revision"])
    ledger = ProviderAttemptLedger(database)
    ledger.reserve(
        request_id="mt5-primary", lane="AUDUSD:M5", expected_boundary=boundary,
        routing_revision=revision, provider="MT5_BRIDGE", at=NOW,
    )
    ledger.mark_dispatched("mt5-primary", at=NOW)
    calls: list[str] = []
    run_due_acquisitions(
        database, at=NOW, credential=None, journal_path=tmp_path / "scheduler.json",
        acquirer=lambda *_args, **kwargs: calls.append(str(kwargs["provider"])) or {
            "received": 0, "staged": 0, "inserted": 0, "corrected": 0,
        },
        provider_profiles=(_fx_profile(),), time_triggered=True,
    )
    assert calls == ["TWELVE_DATA"]
    attempts = ledger.attempts(
        lane="AUDUSD:M5", expected_boundary=boundary,
        routing_revision=revision,
    )
    assert [item["provider"] for item in attempts] == ["MT5_BRIDGE", "TWELVE_DATA"]
    assert [item["ordinal"] for item in attempts] == [1, 2]
