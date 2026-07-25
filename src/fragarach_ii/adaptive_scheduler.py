"""Deterministic adaptive throughput policy for Scheduler dispatch.

The controller observes operational state only.  Provider routing, authority,
acquisition, publication, and rolling-window accounting remain owned by their
existing components.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime


POLICIES = {
    "CONSERVATIVE": {
        "label": "Slow", "minimum": 0.20, "maximum": 0.70,
        "batch": 1, "worker_cap": 1, "catch_up_delay_seconds": 30.0,
    },
    "BALANCED": {
        "label": "Balanced", "minimum": 0.35, "maximum": 0.95,
        "batch": 4, "worker_cap": None, "catch_up_delay_seconds": 1.0,
    },
    "HIGH_THROUGHPUT": {
        # Kept for journals written by earlier releases. New controls expose
        # the clearer High mode below.
        "label": "High Throughput (Legacy)", "minimum": 0.50, "maximum": 1.00,
        "batch": 8, "worker_cap": None, "catch_up_delay_seconds": 0.0,
    },
    "MAXIMUM_CATCH_UP": {
        "label": "High", "minimum": 0.65, "maximum": 1.00,
        # Provider concurrency and rolling budgets remain the hard ceilings.
        "batch": 55, "worker_cap": None, "catch_up_delay_seconds": 0.0,
    },
}


def normalize_policy(value: object) -> str:
    key = str(value or "BALANCED").strip().upper().replace("-", "_").replace(" ", "_")
    # Earlier builds persisted this name for the eager catch-up policy. Keep
    # those journals valid while presenting one clear High control to users.
    if key == "HIGH_THROUGHPUT":
        key = "MAXIMUM_CATCH_UP"
    if key not in POLICIES:
        raise ValueError(f"unsupported scheduler policy: {value}")
    return key


def policy_label(value: object) -> str:
    return str(POLICIES[normalize_policy(value)]["label"])


def time_triggered_pacing(policy: object, *, provider_worker_limit: int) -> dict[str, int | float]:
    """Return bounded, operator-selected pace for register-backed work."""
    settings = POLICIES[normalize_policy(policy)]
    provider_limit = max(1, int(provider_worker_limit))
    configured_cap = settings.get("worker_cap")
    worker_limit = provider_limit if configured_cap is None else min(provider_limit, int(configured_cap))
    return {
        "claim_limit": max(1, int(settings["batch"])),
        "worker_limit": max(1, worker_limit),
        "catch_up_delay_seconds": float(settings["catch_up_delay_seconds"]),
    }


def calculate_throughput(
    *,
    policy: object,
    work_items: list[dict[str, object]],
    queued_items: list[dict[str, object]],
    profiles,
    provider_state: dict[str, object],
    budgets: dict[str, object],
    credentials: dict[str, str],
    scheduled_demand: dict[str, int],
    now: datetime,
    active_activity: dict[str, object] | None = None,
) -> dict[str, object]:
    """Return one deterministic acquisition target for the observed state."""

    observed = now.astimezone(UTC)
    selected_policy = normalize_policy(policy)
    settings = POLICIES[selected_policy]
    items = list(work_items)
    queue_depth = len(items)
    ages = [_age_seconds(item, observed) for item in queued_items]
    oldest_age = max((age for age in ages if age is not None), default=0.0)
    maximum_missed = max((int(item.get("missed_boundaries", 0) or 0) for item in items), default=0)

    depth_pressure = (
        0.0 if queue_depth == 0 else
        0.20 if queue_depth <= 3 else
        0.48 if queue_depth <= 10 else
        0.74 if queue_depth <= 25 else 1.0
    )
    age_pressure = (
        1.0 if oldest_age >= 8 * 3600 else
        0.82 if oldest_age >= 2 * 3600 else
        0.55 if oldest_age >= 30 * 60 else
        0.0
    )
    missed_pressure = min(1.0, maximum_missed / 12.0)
    pressure = max(depth_pressure, age_pressure, missed_pressure)
    fraction = 0.0 if queue_depth == 0 else float(settings["minimum"]) + pressure * (
        float(settings["maximum"]) - float(settings["minimum"])
    )

    operator_demand = sum(item.get("work_class") == "OPERATOR_FETCH" for item in items)
    retry_demand = sum(item.get("work_class") == "OPERATOR_RETRY" for item in items)
    current_demand = sum(item.get("work_class") == "NORMAL" for item in items)
    if active_activity and active_activity.get("work_class") == "OPERATOR_FETCH":
        operator_demand += 1
    publication_demand = int(bool(active_activity and str(active_activity.get("stage", "")).lower() == "publishing"))

    provider_rows: list[dict[str, object]] = []
    total_target_per_minute = 0
    total_current_per_minute = 0
    total_safe_capacity_per_minute = 0
    total_reserved = 0
    total_available = 0
    for profile in sorted(profiles, key=lambda item: item.provider):
        state = provider_state.get(profile.provider, {})
        state = state if isinstance(state, dict) else {}
        budget = budgets[profile.provider].inspect(work_class="NORMAL")
        used = int(budget["calls_used"])
        available = int(budget["calls_available"])
        health_factor, health_reason = _provider_health(
            profile, state, credentials, observed
        )
        provider_fraction = fraction * health_factor
        authority_limit = int(getattr(profile, "operational_limit", None) or profile.request_limit)
        if profile.provider == "TWELVE_DATA" and queue_depth and health_factor > 0:
            provider_fraction = 1.0
        target_window = min(authority_limit, math.floor(authority_limit * provider_fraction))
        dynamic_demand = (
            operator_demand + retry_demand + current_demand + publication_demand
            + int(scheduled_demand.get(profile.provider, 0) or 0)
        )
        # A reservation exists only while protected work is pending or forecast
        # inside the rolling window.  With no such demand it returns to zero.
        dynamic_reserve = min(
            available,
            dynamic_demand,
            max(1, math.ceil(profile.request_limit * 0.25)),
        ) if dynamic_demand and health_factor > 0 and profile.provider != "TWELVE_DATA" else 0
        adaptive_available = max(
            0,
            min(available - dynamic_reserve, target_window - used),
        )
        scale = 60.0 / float(profile.request_window_seconds)
        target_per_minute = math.floor(target_window * scale)
        current_per_minute = math.floor(used * scale)
        provider_rows.append({
            "provider": profile.provider,
            "target_utilization_percent": round(provider_fraction * 100),
            "target_requests_per_window": target_window,
            "target_requests_per_minute": target_per_minute,
            "current_requests_per_minute": current_per_minute,
            "reserved_capacity": dynamic_reserve,
            "available_capacity": adaptive_available,
            "health_factor": health_factor,
            "backoff_reason": health_reason,
        })
        if profile.budget_unit == "requests":
            total_target_per_minute += target_per_minute
            total_current_per_minute += current_per_minute
            total_safe_capacity_per_minute += math.floor(profile.request_limit * scale * health_factor)
        if profile.budget_unit == "requests":
            total_reserved += dynamic_reserve
            total_available += adaptive_available

    estimated_requests = sum(max(1, int(item.get("estimated_requests", 1) or 1)) for item in items)
    completion = None
    if estimated_requests and total_target_per_minute:
        completion = max(1, math.ceil(estimated_requests * 60 / total_target_per_minute))
    protected_count = operator_demand + current_demand + retry_demand
    batch_size = 0 if queue_depth == 0 else min(
        queue_depth,
        max(protected_count, min(int(settings["batch"]), max(1, total_available))),
    )
    reasons = []
    if operator_demand:
        reasons.append("Operator Fetch capacity reserved")
    if age_pressure >= depth_pressure and oldest_age >= 30 * 60:
        reasons.append("Queue age increased dispatch pressure")
    if maximum_missed > 1:
        reasons.append("Missed boundaries increased dispatch pressure")
    if any(row["health_factor"] < 1 for row in provider_rows):
        reasons.append("Provider health reduced safe capacity")
    if not reasons:
        reasons.append("Queue depth determines current adaptive target")

    return {
        "policy": selected_policy,
        "policy_label": settings["label"],
        "queue_depth": queue_depth,
        "pressure": round(pressure, 4),
        "oldest_queued_age_seconds": oldest_age or None,
        "target_utilization_percent": round(fraction * 100),
        "target_requests_per_minute": total_target_per_minute,
        "current_requests_per_minute": total_current_per_minute,
        "safe_capacity_per_minute": total_safe_capacity_per_minute,
        "reserved_capacity": total_reserved,
        "available_capacity": total_available,
        "batch_size": batch_size,
        "estimated_completion_seconds": completion,
        "reasons": reasons,
        "providers": provider_rows,
    }


def _age_seconds(item: dict[str, object], now: datetime) -> float | None:
    try:
        queued = datetime.fromisoformat(str(item.get("enqueued_at")))
        if queued.tzinfo is None:
            queued = queued.replace(tzinfo=UTC)
        return max(0.0, (now - queued.astimezone(UTC)).total_seconds())
    except (TypeError, ValueError):
        return None


def _provider_health(profile, state: dict[str, object], credentials: dict[str, str], now: datetime) -> tuple[float, str | None]:
    if not profile.enabled:
        return 0.0, "PROVIDER_DISABLED"
    if profile.credential_environment and not credentials.get(profile.provider):
        return 0.0, "CREDENTIAL_MISSING"
    if profile.entitlement_state != "AVAILABLE":
        return 0.0, "ENTITLEMENT_BLOCKED"
    cooldown = None if profile.provider == "TWELVE_DATA" else state.get("cooldown_until")
    if cooldown:
        try:
            if datetime.fromisoformat(str(cooldown)).astimezone(UTC) > now:
                return 0.0, str(state.get("wait_reason") or "PROVIDER_COOLDOWN")
        except ValueError:
            pass
    health = str(state.get("health", "Healthy"))
    if profile.provider == "TWELVE_DATA":
        if health in {"Credential Missing", "Authentication Blocked", "Authentication Failed", "Entitlement Blocked"}:
            return 0.0, str(state.get("wait_reason") or health.upper().replace(" ", "_"))
        return 1.0, None
    if cooldown and health == "Cooling Down":
        return 0.65, "COOLDOWN_RECOVERING"
    if health in {"Credential Missing", "Authentication Blocked", "Authentication Failed", "Entitlement Blocked", "Unavailable", "Cooling Down"}:
        return 0.0, str(state.get("wait_reason") or health.upper().replace(" ", "_"))
    if health == "Degraded":
        return 0.65, "PROVIDER_DEGRADED"
    return 1.0, None
