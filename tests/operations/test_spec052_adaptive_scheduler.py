from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fragarach_ii.adaptive_scheduler import calculate_throughput, time_triggered_pacing
from fragarach_ii.acquisition_orchestrator import RateBudgetController
from fragarach_ii.scheduler_service import _fair_bounded_selection
from tests.operations.test_spec042_orchestrator import profile


NOW = datetime(2026, 7, 15, 0, 0, tzinfo=UTC)


def item(index: int, *, work_class: str = "QUEUE", age: float = 0, priority: str = "BEHIND_COMMISSIONED"):
    return {
        "id": f"lane-{index}", "symbol": f"LANE{index}", "timeframe": "D1",
        "work_class": work_class, "dispatch_priority": priority,
        "missed_boundaries": 1, "estimated_requests": 1,
        "enqueued_at": (NOW - timedelta(seconds=age)).isoformat(),
        "retry_due": work_class == "OPERATOR_RETRY",
        "expected_edge": NOW.isoformat(),
    }


def decision(
    work,
    *,
    policy="BALANCED",
    profiles=None,
    states=None,
    credentials=None,
    budgets=None,
    at=NOW,
    scheduled=None,
):
    selected_profiles = tuple(profiles or (profile("TWELVE_DATA", priority=1, credential=True),))
    selected_budgets = budgets or {
        value.provider: RateBudgetController(
            limit=value.request_limit, window_seconds=value.request_window_seconds,
            monotonic=lambda: 0.0, wall_clock=lambda: at,
        ) for value in selected_profiles
    }
    return calculate_throughput(
        policy=policy, work_items=list(work), queued_items=list(work),
        profiles=selected_profiles, provider_state=states or {}, budgets=selected_budgets,
        credentials=credentials if credentials is not None else {"TWELVE_DATA": "fixture"},
        scheduled_demand=scheduled or {}, now=at,
    )


def test_empty_small_large_and_ageing_queue_adapt_deterministically() -> None:
    empty = decision([])
    small = decision([item(1)])
    large_items = [item(index) for index in range(42)]
    large = decision(large_items)
    aged = decision([item(1, age=2 * 3600)])
    assert empty["target_requests_per_minute"] == 0
    assert empty["batch_size"] == 0
    assert small["target_requests_per_minute"] == large["target_requests_per_minute"] == 50
    assert aged["target_requests_per_minute"] == 50
    assert large == decision(large_items)


def test_time_triggered_speed_modes_bound_workers_and_catch_up_delay() -> None:
    slow = time_triggered_pacing("CONSERVATIVE", provider_worker_limit=4)
    balanced = time_triggered_pacing("BALANCED", provider_worker_limit=4)
    high = time_triggered_pacing("MAXIMUM_CATCH_UP", provider_worker_limit=4)

    assert slow == {"claim_limit": 1, "worker_limit": 1, "catch_up_delay_seconds": 30.0}
    assert balanced == {"claim_limit": 4, "worker_limit": 4, "catch_up_delay_seconds": 1.0}
    assert high == {"claim_limit": 16, "worker_limit": 4, "catch_up_delay_seconds": 0.0}


def test_operator_fetch_is_first_and_reserves_capacity_during_backlog() -> None:
    work = [item(index) for index in range(20)] + [
        item(100, work_class="OPERATOR_RETRY", priority="RETRY_QUEUE"),
        item(101, work_class="OPERATOR_FETCH", priority="OPERATOR_FETCH"),
        item(102, work_class="NORMAL", priority="CURRENT_BOUNDARY"),
    ]
    target = decision(work)

    class Journal:
        data = {"fairness_cursor": 0}

    selected = _fair_bounded_selection(work, 6, Journal())
    assert selected[0]["work_class"] == "OPERATOR_FETCH"
    assert selected[1]["work_class"] == "NORMAL"
    assert selected[-1]["work_class"] != "OPERATOR_RETRY"
    assert target["reserved_capacity"] == 0  # the 5-credit plan margin is the shared reserve


def test_provider_budget_exhaustion_never_exposes_capacity() -> None:
    provider = profile("TWELVE_DATA", priority=1, credential=True)
    budget = RateBudgetController(
        limit=55, window_seconds=60, monotonic=lambda: 0.0, wall_clock=lambda: NOW,
    )
    reservation = budget.reserve(55)
    budget.dispatch(reservation["reservation_id"], 55)
    target = decision(
        [item(index) for index in range(42)], profiles=(provider,),
        budgets={"TWELVE_DATA": budget},
    )
    assert target["available_capacity"] == 0
    assert budget.inspect()["calls_used"] <= 55


def test_cooldown_failure_and_credential_loss_back_off_then_recover() -> None:
    provider = profile("TWELVE_DATA", priority=1, credential=True)
    cooldown = {"TWELVE_DATA": {
        "health": "Cooling Down", "wait_reason": "RATE_LIMITED",
        "cooldown_until": (NOW + timedelta(minutes=5)).isoformat(),
    }}
    cooling = decision([item(1)], profiles=(provider,), states=cooldown)
    recovered = decision(
        [item(1)], profiles=(provider,), states=cooldown,
        at=NOW + timedelta(minutes=6),
    )
    degraded = decision(
        [item(1)], profiles=(provider,), states={"TWELVE_DATA": {"health": "Degraded"}},
    )
    missing = decision([item(1)], profiles=(provider,), credentials={})
    assert cooling["target_requests_per_minute"] == 50
    assert recovered["target_requests_per_minute"] > 0
    assert degraded["target_requests_per_minute"] == 50
    assert missing["target_requests_per_minute"] == 0


def test_mixed_provider_routing_capacity_uses_only_healthy_provider() -> None:
    twelve = profile("TWELVE_DATA", priority=1, credential=True)
    yahoo = profile("YAHOO_FINANCE", priority=2, limit=30)
    target = decision(
        [item(index) for index in range(20)], profiles=(twelve, yahoo),
        credentials={},
    )
    rows = {row["provider"]: row for row in target["providers"]}
    assert rows["TWELVE_DATA"]["available_capacity"] == 0
    assert rows["TWELVE_DATA"]["reserved_capacity"] == 0
    assert rows["TWELVE_DATA"]["backoff_reason"] == "CREDENTIAL_MISSING"
    assert rows["YAHOO_FINANCE"]["available_capacity"] > 0
    assert target["target_requests_per_minute"] == rows["YAHOO_FINANCE"]["target_requests_per_minute"]


def test_unused_dynamic_reservation_returns_automatically() -> None:
    operator = decision([item(1, work_class="OPERATOR_FETCH", priority="OPERATOR_FETCH")])
    backlog = decision([item(index) for index in range(10)])
    assert operator["reserved_capacity"] == 0
    assert backlog["reserved_capacity"] == 0
