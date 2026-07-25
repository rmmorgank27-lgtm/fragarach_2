"""Provider capability, deterministic routing, rate budgets, and escalation.

This module owns operational decisions only.  Provider adapters remain
responsible for passing evidence through the immutable ingestion pipeline.
"""

from __future__ import annotations

import json
import hashlib
import math
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Callable

from .providers.twelve_data import AcquisitionError
from .credentials import CredentialAuthority
from .provider_facts import active_representation_symbols, load_provider_facts, representation_mapping
from .lane_commissioning import commissioned_lane_keys
from .storage import open_read_only
from .twelve_data_credit import TwelveDataCreditAuthority
from .authority_cache import AUTHORITY_PREFLIGHT_CACHE, redacted_revision, revision_key


CAPABILITY_CONTRACT = "fragarach_ii.provider_capabilities.v1"
CAPABILITY_PROJECTION_CONTRACT = "fragarach_ii.acquisition_capability_projection.v1"
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config/providers/acquisition_orchestrator.v1.json"
TEMPORARY_INELIGIBILITY = {
    "RATE_BUDGET_EXHAUSTED", "ADAPTIVE_CAPACITY_RESERVED", "PROVIDER_COOLDOWN",
    "CREDENTIAL_MISSING", "AUTHENTICATION_BLOCKED", "AUTHENTICATION_FAILED",
}
RETRYABLE_FAILURES = {
    "TWELVEDATA_RATE_LIMIT_429", "TWELVEDATA_UPSTREAM_5XX",
    "TWELVEDATA_TRANSPORT_FAILURE",
}
EVIDENCE_FAILURES = {
    "INVALID_RESPONSE", "INVALID_CHRONOLOGY", "INVALID_OHLC",
    "ORIENTATION_MISMATCH", "NO_NEW_DATA",
}
WORK_CLASSES = {"NORMAL", "QUEUE", "OPERATOR_RETRY", "OPERATOR_FETCH"}
DIRECT_REAL_MAPPING_CLASSES = {
    "EXACT_REPRESENTATION",
    "APPROVED_PROVIDER_ALIAS",
    "APPROVED_EQUIVALENT_REPRESENTATION",
}
CONTROLLED_CAPABILITY_STATES = {
    "SUPPORTED", "SUPPORTED_WITH_APPROVED_MAPPING", "MAPPING_REQUIRED",
    "TIMEFRAME_UNSUPPORTED", "RANGE_UNAVAILABLE", "CREDENTIAL_REQUIRED",
    "ENTITLEMENT_REQUIRED", "RATE_POLICY_UNVERIFIED", "PROVIDER_DISABLED",
    "CAPABILITY_UNKNOWN",
}
CRYPTO_INTRADAY_TIMEFRAMES = {"H1", "M30", "M5"}


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    provider: str
    enabled: bool
    supported_asset_classes: tuple[str, ...]
    supported_timeframes: tuple[str, ...]
    credential_environment: str | None
    entitlement_state: str
    request_limit: int
    request_window_seconds: int
    maximum_rows_per_request: int
    history_limit_days: int | None
    cost_class: int
    priority: int
    cooldown_seconds: int
    mappings: tuple[dict[str, object], ...]
    budget_unit: str = "requests"
    rate_policy_verified: bool = False
    safety_reserve: int = 0
    concurrency_limit: int = 1
    operational_limit: int | None = None
    dispatch_interval_seconds: float = 0.0

    @property
    def budget_policy(self) -> str:
        if not self.rate_policy_verified:
            return "Rate Policy Unverified"
        if self.budget_unit == "requests":
            return f"{self.request_limit} requests per rolling {self.request_window_seconds} seconds"
        return f"{self.request_limit} {self.budget_unit} per rolling {self.request_window_seconds} seconds"

    @property
    def credential_requirement(self) -> str:
        return "REQUIRED" if self.credential_environment else "NONE"


class RateBudgetController:
    """Sliding-window accounting that separates reservations from dispatches."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: float,
        persisted_events: list[object] | None = None,
        persisted_reservations: list[object] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] | None = None,
    ) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("rate limit and window must be positive")
        self.limit = limit
        self.window_seconds = float(window_seconds)
        self._monotonic = monotonic
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        now_mono = monotonic()
        now_wall = self._utc(self._wall_clock())
        self._events: list[tuple[float, datetime, str, int]] = []
        self._reservations: list[tuple[str, float, datetime, str, int]] = []
        for raw in persisted_events or []:
            try:
                if isinstance(raw, dict):
                    wall = self._utc(datetime.fromisoformat(str(raw["at"])))
                    work_class = str(raw.get("work_class", "NORMAL")).upper()
                    cost = max(1, int(raw.get("cost", 1)))
                else:
                    wall = self._utc(datetime.fromisoformat(str(raw)))
                    work_class, cost = "NORMAL", 1
                if work_class not in WORK_CLASSES:
                    work_class = "NORMAL"
            except (KeyError, TypeError, ValueError):
                continue
            age = max(0.0, (now_wall - wall).total_seconds())
            if age < self.window_seconds:
                self._events.append((now_mono - age, wall, work_class, cost))
        self._events.sort()
        for raw in persisted_reservations or []:
            try:
                identifier = str(raw["id"])
                wall = self._utc(datetime.fromisoformat(str(raw["at"])))
                work_class = str(raw.get("work_class", "NORMAL")).upper()
                cost = max(1, int(raw.get("cost", 1)))
            except (KeyError, TypeError, ValueError):
                continue
            if work_class not in WORK_CLASSES:
                work_class = "NORMAL"
            age = max(0.0, (now_wall - wall).total_seconds())
            self._reservations.append((identifier, now_mono - age, wall, work_class, cost))

    def inspect(
        self,
        request_count: int = 0,
        *,
        work_class: str = "NORMAL",
        queue_percentage: int = 80,
        protected_normal_demand: int = 0,
        safety_reserve: int = 0,
    ) -> dict[str, object]:
        with self._lock:
            return self._inspect_locked(
                request_count,
                work_class=work_class,
                queue_percentage=queue_percentage,
                protected_normal_demand=protected_normal_demand,
                safety_reserve=safety_reserve,
            )

    def reserve(
        self,
        request_count: int,
        *,
        work_class: str = "NORMAL",
        queue_percentage: int = 80,
        protected_normal_demand: int = 0,
        safety_reserve: int = 0,
    ) -> dict[str, object]:
        if request_count <= 0:
            raise ValueError("request count must be positive")
        work_class = work_class.upper()
        if work_class not in WORK_CLASSES:
            raise ValueError(f"unsupported work class: {work_class}")
        if not 0 <= queue_percentage <= 100:
            raise ValueError("adaptive utilization must be between 0 and 100")
        if request_count > self.limit:
            return {
                "eligible": False,
                "calls_used": sum(item[3] for item in self._events),
                "calls_available": max(0, self.limit - sum(item[3] for item in self._events)),
                "next_available": None,
                "reason": "REQUEST_EXCEEDS_RATE_WINDOW",
            }
        with self._lock:
            result = self._inspect_locked(
                request_count,
                work_class=work_class,
                queue_percentage=queue_percentage,
                protected_normal_demand=protected_normal_demand,
                safety_reserve=safety_reserve,
            )
            if not result["eligible"]:
                return result
            mono = self._monotonic()
            wall = self._utc(self._wall_clock())
            reservation_id = f"reservation-{uuid.uuid4().hex}"
            self._reservations.append((reservation_id, mono, wall, work_class, request_count))
            return self._inspect_locked(
                0,
                work_class=work_class,
                queue_percentage=queue_percentage,
                protected_normal_demand=protected_normal_demand,
                safety_reserve=safety_reserve,
            ) | {
                "eligible": True,
                "reserved": request_count,
                "reservation_id": reservation_id,
                "reason": None,
            }

    def dispatch(self, reservation_id: str, request_count: int = 1) -> dict[str, object]:
        """Convert reserved units into actual provider calls atomically."""
        if request_count <= 0:
            raise ValueError("request count must be positive")
        with self._lock:
            for index, (identifier, _, _, work_class, cost) in enumerate(self._reservations):
                if identifier != reservation_id:
                    continue
                if request_count > cost:
                    raise ValueError("dispatch exceeds reserved capacity")
                if request_count == cost:
                    self._reservations.pop(index)
                else:
                    current = self._reservations[index]
                    self._reservations[index] = (*current[:4], cost - request_count)
                mono = self._monotonic()
                wall = self._utc(self._wall_clock())
                self._events.append((mono, wall, work_class, request_count))
                return {"dispatched": request_count, "reservation_id": reservation_id}
        raise ValueError(f"unknown reservation: {reservation_id}")

    def release(self, reservation_id: str, request_count: int | None = None) -> int:
        """Release unused capacity without recording a provider call."""
        with self._lock:
            for index, (identifier, _, _, _, cost) in enumerate(self._reservations):
                if identifier != reservation_id:
                    continue
                released = cost if request_count is None else min(cost, max(0, request_count))
                if released == cost:
                    self._reservations.pop(index)
                else:
                    current = self._reservations[index]
                    self._reservations[index] = (*current[:4], cost - released)
                return released
        return 0

    def persisted_events(self) -> list[dict[str, object]]:
        with self._lock:
            self._prune_locked()
            return [
                {"at": wall.isoformat(), "work_class": work_class, "cost": cost}
                for _, wall, work_class, cost in self._events
            ]

    def persisted_reservations(self) -> list[dict[str, object]]:
        with self._lock:
            return [
                {"id": identifier, "at": wall.isoformat(), "work_class": work_class, "cost": cost}
                for identifier, _, wall, work_class, cost in self._reservations
            ]

    def _inspect_locked(
        self,
        request_count: int,
        *,
        work_class: str,
        queue_percentage: int,
        protected_normal_demand: int,
        safety_reserve: int,
    ) -> dict[str, object]:
        self._prune_locked()
        work_class = work_class.upper()
        used = sum(item[3] for item in self._events)
        reserved = sum(item[4] for item in self._reservations)
        queue_used = sum(item[3] for item in self._events if item[2] == "QUEUE")
        queue_reserved = sum(item[4] for item in self._reservations if item[3] == "QUEUE")
        committed = used + reserved
        available = max(0, self.limit - committed)
        queue_ceiling = math.floor(self.limit * queue_percentage / 100)
        protected_capacity = self.limit - queue_ceiling
        protected = max(protected_capacity, protected_normal_demand, safety_reserve)
        if work_class != "QUEUE":
            dispatch_available = available
        else:
            dispatch_available = min(
                max(0, queue_ceiling - queue_used - queue_reserved),
                max(0, available - protected),
            )
        eligible = request_count <= dispatch_available
        next_available = self._next_release_locked(
            request_count,
            work_class=work_class,
            queue_ceiling=queue_ceiling,
            protected=protected,
        ) if not eligible else None
        return {
            "eligible": eligible,
            "calls_used": used,
            "calls_available": available,
            "active_reservations": len(self._reservations),
            "reserved_calls": reserved,
            "queue_calls_used": queue_used,
            "queue_calls_reserved": queue_reserved,
            "queue_ceiling": queue_ceiling,
            "queue_available": max(0, min(queue_ceiling - queue_used - queue_reserved, available - protected)),
            "protected_capacity": protected_capacity,
            "protected_normal_demand": protected_normal_demand,
            "safety_reserve": safety_reserve,
            "next_available": next_available,
            "reason": None if eligible else (
                "ADAPTIVE_CAPACITY_RESERVED" if work_class == "QUEUE" and available >= request_count
                else "RATE_BUDGET_EXHAUSTED"
            ),
        }

    def _next_release_locked(
        self, request_count: int, *, work_class: str, queue_ceiling: int, protected: int
    ) -> str | None:
        if not self._events:
            return None
        used = sum(item[3] for item in self._events)
        reserved = sum(item[4] for item in self._reservations)
        queue_used = sum(item[3] for item in self._events if item[2] == "QUEUE")
        queue_reserved = sum(item[4] for item in self._reservations if item[3] == "QUEUE")
        grouped: dict[datetime, list[tuple[str, int]]] = {}
        for _, wall, event_class, cost in self._events:
            grouped.setdefault(wall + timedelta(seconds=self.window_seconds), []).append((event_class, cost))
        for release in sorted(grouped):
            for event_class, cost in grouped[release]:
                used -= cost
                if event_class == "QUEUE":
                    queue_used -= cost
            available = max(0, self.limit - used - reserved)
            dispatch_available = available if work_class != "QUEUE" else min(
                max(0, queue_ceiling - queue_used - queue_reserved), max(0, available - protected)
            )
            if request_count <= dispatch_available:
                return release.isoformat()
        return None

    def _prune_locked(self) -> None:
        cutoff = self._monotonic() - self.window_seconds
        self._events = [item for item in self._events if item[0] > cutoff]

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def load_provider_profiles(
    path: str | Path | None = None, *, apply_runtime_overrides: bool = True,
) -> tuple[ProviderProfile, ...]:
    payload = json.loads(Path(path or CONFIG_PATH).read_text(encoding="utf-8"))
    if payload.get("contract") != CAPABILITY_CONTRACT:
        raise ValueError("unsupported provider capability contract")
    profiles = []
    seen = set()
    overrides = {}
    if apply_runtime_overrides:
        from .provider_settings import load_provider_overrides
        overrides = load_provider_overrides()
    for source in payload.get("providers", []):
        raw = dict(source)
        provider = str(raw["provider"]).upper()
        override = overrides.get(provider, {})
        if isinstance(override, dict):
            raw["enabled"] = bool(override.get("enabled", raw["enabled"]))
            raw["operational_limit"] = min(
                int(raw["request_limit"]),
                max(1, int(override.get("operational_limit", raw.get("operational_limit") or raw["request_limit"]))),
            )
            raw["concurrency_limit"] = min(
                max(1, int(source.get("concurrency_limit", 1))),
                max(1, int(override.get("concurrency_limit", source.get("concurrency_limit", 1)))),
            )
        if provider in seen:
            raise ValueError(f"duplicate provider capability: {provider}")
        seen.add(provider)
        limit = int(raw["request_limit"])
        if provider == "TWELVE_DATA" and limit > 55:
            raise ValueError("Twelve Data configured limit exceeds approved 55 calls/minute")
        for mapping in raw.get("mappings", []):
            mapping_class = str(mapping.get("mapping_class") or "")
            if mapping_class not in {
                "EXACT_REPRESENTATION", "APPROVED_PROVIDER_ALIAS",
                "APPROVED_EQUIVALENT_REPRESENTATION", "CONVERSION_REQUIRED", "NOT_EQUIVALENT",
            }:
                raise ValueError(f"uncontrolled provider mapping class: {provider}:{mapping_class or 'MISSING'}")
            if str(mapping.get("reviewed_status")) != "REVIEWED":
                raise ValueError(f"provider mapping is not reviewed: {provider}:{mapping.get('asset')}")
            if mapping.get("quote_equivalence") is not None:
                if (
                    mapping.get("quote_equivalence") != "USD_USDT_CRYPTO"
                    or mapping.get("asset_class") != "CRYPTO"
                    or mapping_class != "APPROVED_EQUIVALENT_REPRESENTATION"
                    or mapping.get("canonical_base_asset") != mapping.get("provider_base_asset")
                    or mapping.get("canonical_quote_asset") != "USD"
                    or mapping.get("provider_quote_asset") != "USDT"
                ):
                    raise ValueError(
                        f"invalid crypto quote-equivalence mapping: {provider}:{mapping.get('asset')}"
                    )
        profiles.append(
            ProviderProfile(
                provider=provider,
                enabled=bool(raw["enabled"]),
                supported_asset_classes=tuple(raw["supported_asset_classes"]),
                supported_timeframes=tuple(raw["supported_timeframes"]),
                credential_environment=raw.get("credential_environment"),
                entitlement_state=str(raw["entitlement_state"]),
                request_limit=limit,
                request_window_seconds=int(raw["request_window_seconds"]),
                maximum_rows_per_request=int(raw["maximum_rows_per_request"]),
                history_limit_days=(int(raw["history_limit_days"]) if raw.get("history_limit_days") is not None else None),
                cost_class=int(raw["cost_class"]),
                priority=int(raw["priority"]),
                cooldown_seconds=int(raw["cooldown_seconds"]),
                mappings=tuple(raw.get("mappings", [])),
                budget_unit=str(raw.get("budget_unit", "requests")),
                rate_policy_verified=bool(raw.get("rate_policy_verified", False)),
                safety_reserve=max(0, int(raw.get("safety_reserve", 0))),
                concurrency_limit=max(1, int(raw.get("concurrency_limit", 1))),
                operational_limit=(
                    int(raw["operational_limit"])
                    if raw.get("operational_limit") is not None else limit
                ),
                dispatch_interval_seconds=max(0.0, float(raw.get("dispatch_interval_seconds", 0))),
            )
        )
    return tuple(profiles)


_AUTHORITY_CREDENTIAL = object()


def credential_map(twelve_data_credential: str | None | object = _AUTHORITY_CREDENTIAL) -> dict[str, str]:
    """Project authority-owned secrets into the router's provider map."""
    credential = twelve_data_credential
    if credential is _AUTHORITY_CREDENTIAL:
        credential = CredentialAuthority().credential_for("TWELVE_DATA")
    return {"TWELVE_DATA": str(credential)} if credential else {}


def build_rate_budgets(
    profiles: tuple[ProviderProfile, ...],
    provider_state: dict[str, object],
    *,
    monotonic: Callable[[], float] = time.monotonic,
    wall_clock: Callable[[], datetime] | None = None,
    credential: str | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, RateBudgetController | TwelveDataCreditAuthority]:
    budgets = {}
    for profile in profiles:
        state = provider_state.get(profile.provider, {})
        events = state.get("rate_events", []) if isinstance(state, dict) else []
        reservations = state.get("active_reservations", []) if isinstance(state, dict) else []
        if profile.provider == "TWELVE_DATA" and credential:
            budgets[profile.provider] = TwelveDataCreditAuthority(
                credential=credential,
                plan_limit=profile.request_limit,
                operational_limit=int(profile.operational_limit or profile.request_limit),
                window_seconds=profile.request_window_seconds,
                dispatch_interval_seconds=profile.dispatch_interval_seconds,
                clock=wall_clock,
                sleeper=sleeper,
            )
        else:
            budgets[profile.provider] = RateBudgetController(
                limit=profile.request_limit,
                window_seconds=profile.request_window_seconds,
                persisted_events=list(events) if isinstance(events, list) else [],
                persisted_reservations=list(reservations) if isinstance(reservations, list) else [],
                monotonic=monotonic,
                wall_clock=wall_clock,
            )
    return budgets


def acquisition_plan(
    database_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    canonical_edge: str | None,
    expected_edge: str,
    missing_start: str,
    missing_end: str,
    scheduled_boundary: str,
    profiles: tuple[ProviderProfile, ...],
    provider_state: dict[str, object],
    budgets: dict[str, RateBudgetController],
    credentials: dict[str, str],
    now: datetime,
    attempted_providers: set[str] | None = None,
    work_class: str = "NORMAL",
    queue_percentage: int = 80,
    protected_demand: dict[str, int] | None = None,
) -> dict[str, object]:
    asset_class, primary_provider, primary_symbol = _registration(database_path, symbol)
    attempted = attempted_providers or set()
    considered: list[dict[str, object]] = []
    eligible: list[tuple[ProviderProfile, dict[str, object], int, int, int, str]] = []
    for profile in profiles:
        resolved_mapping = representation_mapping(database_path, profile.provider, symbol)
        mapping = mapping_authority(
            profile, symbol=symbol, timeframe=timeframe,
            primary_provider=primary_provider, primary_symbol=primary_symbol,
            resolved_mapping=resolved_mapping,
        )
        estimated = estimate_requests(timeframe, missing_start, missing_end, profile.maximum_rows_per_request)
        reason = eligibility_reason(
            profile,
            asset_class=asset_class,
            timeframe=timeframe,
            mapping=str(mapping["provider_symbol"]) if mapping.get("direct_real_eligible") else None,
            credentials=credentials,
            state=provider_state.get(profile.provider, {}),
            budget=budgets[profile.provider],
            estimated_requests=estimated,
            missing_start=missing_start,
            missing_end=missing_end,
            now=now,
            work_class=work_class,
            queue_percentage=queue_percentage,
            protected_normal_demand=int((protected_demand or {}).get(profile.provider, 0)),
        )
        if mapping.get("timeframe_supported") is False:
            reason = "TIMEFRAME_UNSUPPORTED"
        quote_equivalence_rejection = _quote_equivalence_rejection(asset_class, mapping)
        if quote_equivalence_rejection:
            reason = quote_equivalence_rejection
        route_rank, routing_policy, routing_rejection = _routing_policy(
            asset_class=asset_class, timeframe=timeframe, profile=profile, mapping=mapping,
        )
        if routing_rejection and mapping.get("direct_real_eligible"):
            reason = routing_rejection
        if profile.provider in attempted:
            reason = "PROVIDER_ALREADY_ATTEMPTED"
        considered.append({
            "market": asset_class,
            "timeframe": timeframe,
            "provider": profile.provider,
            "eligible": reason is None,
            "reason": reason,
            "rejection_reason": reason or mapping.get("rejection_reason"),
            "provider_symbol": mapping.get("provider_symbol"),
            "provider_representation": mapping.get("provider_representation"),
            "representation_type": mapping.get("mapping_class"),
            "mapping_status": mapping.get("mapping_status"),
            "mapping_class": mapping.get("mapping_class"),
            "mapping_authority_source": mapping.get("authority_source"),
            "capability": mapping.get("timeframe_capability"),
            "quote_equivalence": mapping.get("quote_equivalence"),
            "quote_equivalence_reason": mapping.get("quote_equivalence_reason"),
            "api_base_url": mapping.get("api_base_url"),
            "routing_policy": routing_policy,
            "fallback_rank": None,
            "estimated_request_count": estimated,
        })
        if reason is None and mapping.get("direct_real_eligible"):
            health_score = int(_state_dict(provider_state, profile.provider).get("health_score", 100))
            eligible.append((profile, mapping, estimated, health_score, route_rank, routing_policy))
    eligible.sort(key=lambda value: (
        value[4], value[0].priority, value[0].cost_class, -value[3], value[2], value[0].provider
    ))
    fallback_ranks = {value[0].provider: index for index, value in enumerate(eligible, start=1)}
    for item in considered:
        item["fallback_rank"] = fallback_ranks.get(item["provider"])
    selected = eligible[0] if eligible else None
    selection_reason = None
    if selected:
        profile, _, requests, score, route_rank, routing_policy = selected
        selection_reason = (
            f"routing_policy={routing_policy}; routing_rank={route_rank}; "
            f"fallback_rank={fallback_ranks[profile.provider]}; "
            f"priority={profile.priority}; cost_class={profile.cost_class}; "
            f"health={score}; estimated_requests={requests}; provider={profile.provider}"
        )
    temporary = [item for item in considered if item["reason"] in TEMPORARY_INELIGIBILITY]
    return {
        "id": f"{symbol}:{timeframe}:{scheduled_boundary}",
        "lane": f"{symbol}:{timeframe}",
        "symbol": symbol,
        "timeframe": timeframe,
        "scheduled_boundary": scheduled_boundary,
        "canonical_edge": canonical_edge,
        "expected_edge": expected_edge,
        "missing_range": {"start": missing_start, "end": missing_end},
        "providers_considered": considered,
        "eligible_providers": [value[0].provider for value in eligible],
        "selected_provider": selected[0].provider if selected else None,
        "selected_provider_symbol": selected[1]["provider_symbol"] if selected else None,
        "selected_mapping_class": selected[1]["mapping_class"] if selected else None,
        "selected_mapping_authority_source": selected[1]["authority_source"] if selected else None,
        "selected_provider_api_base_url": selected[1].get("api_base_url") if selected else None,
        "selected_fallback_rank": fallback_ranks.get(selected[0].provider) if selected else None,
        "routing_policy": selected[5] if selected else _routing_policy_name(asset_class, timeframe),
        "selection_reason": selection_reason,
        "estimated_request_count": selected[2] if selected else 0,
        "rate_budget_eligibility": bool(selected),
        "fallback_sequence": [value[0].provider for value in eligible],
        "temporary_ineligibility": temporary,
        "created_at": now.astimezone(UTC).isoformat(),
        "work_class": work_class,
    }


def _routing_policy(
    *, asset_class: str, timeframe: str, profile: ProviderProfile, mapping: dict[str, object],
) -> tuple[int, str, str | None]:
    """Return deterministic market/timeframe routing rank and a policy rejection.

    A D1 registration is evidence for its D1 lane only.  Crypto intraday lanes
    require their own approved routing authority and cannot inherit a generic
    Twelve Data representation fact.
    """
    policy = _routing_policy_name(asset_class, timeframe)
    if policy != "CRYPTO_INTRADAY_V1":
        return 100, policy, None
    if profile.provider == "BINANCE":
        return (1 if mapping.get("quote_equivalence") == "USD_USDT_CRYPTO" else 0), policy, None
    if profile.provider == "TWELVE_DATA":
        explicit_approval = bool(mapping.get("crypto_intraday_approved"))
        proven_capability = bool((mapping.get("timeframe_capability") or {}).get("supported"))
        if not (explicit_approval and proven_capability):
            return 90, policy, "CRYPTO_INTRADAY_NOT_APPROVED"
        return 3, policy, None
    if "CRYPTO" in profile.supported_asset_classes:
        return (1 if mapping.get("quote_equivalence") == "USD_USDT_CRYPTO" else 2), policy, None
    return 100, policy, None


def _routing_policy_name(asset_class: str, timeframe: str) -> str:
    if asset_class == "CRYPTO" and timeframe in CRYPTO_INTRADAY_TIMEFRAMES:
        return "CRYPTO_INTRADAY_V1"
    return "DEFAULT_PROVIDER_PRIORITY_V1"


def _quote_equivalence_rejection(asset_class: str, mapping: dict[str, object]) -> str | None:
    """Keep the USD/USDT rule scoped to crypto even if a bad fact is stored."""
    if mapping.get("quote_equivalence") == "USD_USDT_CRYPTO" and asset_class != "CRYPTO":
        return "CRYPTO_QUOTE_EQUIVALENCE_NOT_APPLICABLE"
    return None


def approved_mapping(
    profile: ProviderProfile,
    *,
    symbol: str,
    timeframe: str,
    primary_provider: str | None,
    primary_symbol: str | None,
) -> str | None:
    mapping = mapping_authority(
        profile, symbol=symbol, timeframe=timeframe,
        primary_provider=primary_provider, primary_symbol=primary_symbol,
    )
    return str(mapping["provider_symbol"]) if mapping.get("direct_real_eligible") else None


def _compact_provider_symbol(value: object) -> str:
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def mapping_authority(
    profile: ProviderProfile,
    *,
    symbol: str,
    timeframe: str,
    primary_provider: str | None,
    primary_symbol: str | None,
    resolved_mapping: dict[str, object] | None = None,
) -> dict[str, object]:
    """Resolve reviewed representation authority without inferring equivalence."""

    canonical = symbol.strip().upper()
    timeframe = timeframe.strip().upper()
    if resolved_mapping:
        configured = next((
            item for item in profile.mappings
            if str(item.get("asset", item.get("canonical_symbol", ""))).upper() == canonical
            and str(item.get("reviewed_status", "")).upper() == "REVIEWED"
            and _compact_provider_symbol(item.get("symbol", item.get("provider_symbol")))
            == _compact_provider_symbol(resolved_mapping.get("provider_symbol"))
        ), None)
        # Provider facts prove that the operator approved the selected symbol.
        # A reviewed profile mapping remains the authority for cross-timeframe
        # capability and a governed crypto USD/USDT equivalence; the D1
        # registration fact must not erase those fields.
        if configured is not None:
            provider_symbol = str(configured.get("symbol", configured.get("provider_symbol", ""))) or None
            mapping_class = str(configured.get("mapping_class") or "").upper() or None
            capability_supported = timeframe in {
                str(value).upper() for value in configured.get("timeframes", ())
            }
            capability = {
                "timeframe": timeframe,
                "supported": capability_supported,
                "history_availability": "AVAILABLE_BY_PROVIDER_CONTRACT",
                "verification_method": configured.get("authority_source") or "PROVIDER_CAPABILITY_CONFIGURATION",
            }
            direct = mapping_class in DIRECT_REAL_MAPPING_CLASSES
            return {
                "canonical_symbol": canonical,
                "canonical_base_asset": configured.get("canonical_base_asset"),
                "canonical_quote_asset": configured.get("canonical_quote_asset"),
                "provider": profile.provider,
                "provider_symbol": provider_symbol,
                "provider_base_asset": configured.get("provider_base_asset"),
                "provider_quote_asset": configured.get("provider_quote_asset"),
                "provider_representation": configured.get("provider_representation") or provider_symbol,
                "mapping_class": mapping_class,
                "mapping_status": mapping_class if direct else "MAPPING_REQUIRED",
                "conversion_policy": configured.get("conversion_policy") or "NO_CONVERSION",
                "effective_date": configured.get("effective_date"),
                "reviewed_status": "REVIEWED",
                "authority_source": configured.get("authority_source"),
                "direct_real_eligible": direct,
                "rejection_reason": None if direct else mapping_class or "MAPPING_NOT_REVIEWED",
                "resolution_method": resolved_mapping.get("resolution_method"),
                "resolution_evidence": resolved_mapping.get("resolution_evidence"),
                "timeframe_supported": capability_supported,
                "timeframe_capability": capability,
                "crypto_intraday_approved": bool(configured.get("crypto_intraday_approved")),
                "quote_equivalence": configured.get("quote_equivalence"),
                "quote_equivalence_reason": (
                    "CRYPTO_USD_USDT_QUOTE_EQUIVALENCE"
                    if configured.get("quote_equivalence") == "USD_USDT_CRYPTO" else None
                ),
                "api_base_url": configured.get("api_base_url"),
            }
        mapping_class = str(resolved_mapping.get("mapping_class") or "").upper() or None
        reviewed = resolved_mapping.get("status") in {"RESOLVED_AUTOMATICALLY", "OPERATOR_RESOLVED"}
        direct = bool(reviewed and mapping_class in DIRECT_REAL_MAPPING_CLASSES)
        capability = resolved_mapping.get("timeframe_capabilities", {}).get(timeframe, {}) if isinstance(resolved_mapping.get("timeframe_capabilities"), dict) else {}
        # A reviewed Twelve Data physical-currency representation is a
        # provider-level FX authority.  Older operator reviews persisted only
        # the D1 capability, despite Twelve Data's reviewed FX contract
        # covering M5/M30/H1/D1.  Treating those missing legacy rows as a
        # provider rejection stranded already-proven FX lanes.
        is_twelve_fx = (
            profile.provider == "TWELVE_DATA"
            and str(resolved_mapping.get("provider_asset_class") or resolved_mapping.get("market_category") or "").upper()
                in {"FX", "FOREX", "PHYSICAL CURRENCY"}
            and str(resolved_mapping.get("provider_instrument_type") or "").upper() == "PHYSICAL CURRENCY"
        )
        if direct and is_twelve_fx and not capability:
            capability = {
                "timeframe": timeframe,
                "supported": timeframe in profile.supported_timeframes,
                "history_availability": "AVAILABLE_BY_REVIEWED_FX_CONTRACT",
                "verification_method": "TWELVE_DATA_REVIEWED_FX_CONTRACT",
            }
        return {
            "canonical_symbol": canonical,
            "canonical_base_asset": resolved_mapping.get("canonical_base_asset"),
            "canonical_quote_asset": resolved_mapping.get("canonical_quote_asset"),
            "provider": profile.provider,
            "provider_symbol": resolved_mapping.get("provider_symbol"),
            "provider_base_asset": resolved_mapping.get("provider_base_asset"),
            "provider_quote_asset": resolved_mapping.get("provider_quote_asset"),
            "provider_representation": resolved_mapping.get("provider_symbol"),
            "mapping_class": mapping_class,
            "mapping_status": mapping_class if reviewed else "MAPPING_REQUIRED",
            "conversion_policy": "NO_CONVERSION",
            "effective_date": resolved_mapping.get("effective_time"),
            "reviewed_status": "REVIEWED" if reviewed else "UNREVIEWED",
            "authority_source": "TWELVE_DATA_PROVIDER_FACT_RESOLVER_V1",
            "direct_real_eligible": direct,
            "rejection_reason": None if direct else mapping_class or str(resolved_mapping.get("status") or "MAPPING_NOT_REVIEWED"),
            "resolution_method": resolved_mapping.get("resolution_method"),
            "resolution_evidence": resolved_mapping.get("resolution_evidence"),
            "timeframe_supported": capability.get("supported") if capability else None,
            "timeframe_capability": capability or None,
            "crypto_intraday_approved": bool(resolved_mapping.get("crypto_intraday_approved")),
            "quote_equivalence": resolved_mapping.get("quote_equivalence"),
            "quote_equivalence_reason": resolved_mapping.get("quote_equivalence_reason"),
            "api_base_url": resolved_mapping.get("api_base_url"),
        }
    candidates = [
        item for item in profile.mappings
        if str(item.get("asset", item.get("canonical_symbol", ""))).upper() == canonical
    ]
    # Prefer a reviewed direct mapping over a recorded negative or conversion-only fact.
    candidates.sort(key=lambda item: (
        str(item.get("mapping_class", "")) not in DIRECT_REAL_MAPPING_CLASSES,
        item.get("quote_equivalence") == "USD_USDT_CRYPTO",
        str(item.get("symbol", item.get("provider_symbol", ""))),
    ))
    if candidates:
        raw = candidates[0]
        provider_symbol = str(raw.get("symbol", raw.get("provider_symbol", ""))) or None
        normalized_provider = "".join(character for character in (provider_symbol or "").upper() if character.isalnum())
        legacy_exact = not raw.get("mapping_class") and normalized_provider == canonical
        legacy_alias = not raw.get("mapping_class") and normalized_provider.removesuffix("X") == canonical
        mapping_class = str(raw.get("mapping_class") or ("EXACT_REPRESENTATION" if legacy_exact else "APPROVED_PROVIDER_ALIAS" if legacy_alias else "CAPABILITY_UNKNOWN")).upper()
        reviewed = legacy_exact or legacy_alias or str(raw.get("reviewed_status") or "UNREVIEWED").upper() == "REVIEWED"
        direct = reviewed and mapping_class in DIRECT_REAL_MAPPING_CLASSES
        timeframe_supported = timeframe in {str(value).upper() for value in raw.get("timeframes", ())}
        timeframe_capability = {
            "timeframe": timeframe,
            "supported": timeframe_supported,
            "history_availability": "AVAILABLE_BY_PROVIDER_CONTRACT",
            "verification_method": raw.get("authority_source") or "PROVIDER_CAPABILITY_CONFIGURATION",
        }
        return {
            "canonical_symbol": canonical,
            "canonical_base_asset": raw.get("canonical_base_asset") or (canonical[:-3] if len(canonical) > 3 else None),
            "canonical_quote_asset": raw.get("canonical_quote_asset") or (canonical[-3:] if len(canonical) >= 6 else None),
            "provider": profile.provider,
            "provider_symbol": provider_symbol,
            "provider_base_asset": raw.get("provider_base_asset"),
            "provider_quote_asset": raw.get("provider_quote_asset"),
            "provider_representation": raw.get("provider_representation") or provider_symbol,
            "mapping_class": mapping_class,
            "mapping_status": mapping_class if reviewed else "MAPPING_REQUIRED",
            "conversion_policy": raw.get("conversion_policy") or "NO_CONVERSION",
            "effective_date": raw.get("effective_date"),
            "reviewed_status": "REVIEWED" if reviewed else "UNREVIEWED",
            "authority_source": raw.get("authority_source") or ("LEGACY_REVIEWED_SYMBOL_CONFIGURATION" if legacy_exact or legacy_alias else "PROVIDER_CAPABILITY_CONFIGURATION"),
            "direct_real_eligible": direct,
            "rejection_reason": None if direct else mapping_class if reviewed else "MAPPING_NOT_REVIEWED",
            "timeframe_supported": timeframe_supported,
            "timeframe_capability": timeframe_capability,
            "crypto_intraday_approved": bool(raw.get("crypto_intraday_approved")),
            "quote_equivalence": raw.get("quote_equivalence"),
            "quote_equivalence_reason": (
                "CRYPTO_USD_USDT_QUOTE_EQUIVALENCE"
                if raw.get("quote_equivalence") == "USD_USDT_CRYPTO" else None
            ),
            "api_base_url": raw.get("api_base_url"),
        }
    if primary_provider == profile.provider and primary_symbol:
        normalized_provider = "".join(character for character in primary_symbol.upper() if character.isalnum())
        same_representation = normalized_provider == canonical
        approved_alias = normalized_provider.removesuffix("X") == canonical
        direct = same_representation or approved_alias
        return {
            "canonical_symbol": canonical,
            "canonical_base_asset": canonical[:-3] if len(canonical) >= 6 else None,
            "canonical_quote_asset": canonical[-3:] if len(canonical) >= 6 else None,
            "provider": profile.provider,
            "provider_symbol": primary_symbol,
            "provider_base_asset": canonical[:-3] if same_representation and len(canonical) >= 6 else None,
            "provider_quote_asset": canonical[-3:] if same_representation and len(canonical) >= 6 else None,
            "provider_representation": primary_symbol,
            "mapping_class": "EXACT_REPRESENTATION" if same_representation else "APPROVED_PROVIDER_ALIAS" if approved_alias else "CAPABILITY_UNKNOWN",
            "mapping_status": "EXACT_REPRESENTATION" if same_representation else "APPROVED_PROVIDER_ALIAS" if approved_alias else "MAPPING_REQUIRED",
            "conversion_policy": "NO_CONVERSION",
            "effective_date": None,
            "reviewed_status": "REVIEWED" if direct else "UNREVIEWED",
            "authority_source": "CANONICAL_INSTRUMENT_REGISTRATION",
            "direct_real_eligible": direct,
            "rejection_reason": None if direct else "MAPPING_NOT_REVIEWED",
            "timeframe_supported": None,
            "timeframe_capability": None,
            "crypto_intraday_approved": False,
            "quote_equivalence": None,
            "quote_equivalence_reason": None,
            "api_base_url": None,
        }
    return {
        "canonical_symbol": canonical, "provider": profile.provider,
        "provider_symbol": None, "provider_representation": None,
        "mapping_class": None, "mapping_status": "MAPPING_REQUIRED",
        "reviewed_status": "UNREVIEWED", "authority_source": "NO_APPROVED_MAPPING_AUTHORITY",
        "direct_real_eligible": False, "rejection_reason": "NO_APPROVED_MAPPING",
        "timeframe_supported": None, "timeframe_capability": None,
        "crypto_intraday_approved": False,
        "quote_equivalence": None,
        "quote_equivalence_reason": None,
        "api_base_url": None,
    }


def acquisition_capability_projection(
    database_path: str | Path,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    profiles: tuple[ProviderProfile, ...] | None = None,
    provider_state: dict[str, object] | None = None,
    budgets: dict[str, RateBudgetController] | None = None,
    credentials: dict[str, str] | None = None,
    now: datetime | None = None,
    requested_start: str | None = None,
    requested_end: str | None = None,
) -> dict[str, object]:
    """Return the single provider capability truth consumed by every workflow."""

    observed = (now or datetime.now(UTC)).astimezone(UTC)
    selected_profiles = tuple(profiles or load_provider_profiles())
    states = provider_state if provider_state is not None else {}
    selected_budgets = budgets or build_rate_budgets(
        selected_profiles, states, wall_clock=lambda: observed,
        credential=(credentials or {}).get("TWELVE_DATA") if credentials is not None else credential_map().get("TWELVE_DATA"),
    )
    available_credentials = credentials if credentials is not None else credential_map()
    requested_symbol = symbol.strip().upper() if symbol else None
    requested_timeframe = timeframe.strip().upper() if timeframe else None
    with open_read_only(database_path) as connection:
        registrations = connection.execute(
            """SELECT asset,asset_class,representation_type,provider_id,provider_symbol,
                      registration_status,identity_json
               FROM instrument_registrations
               WHERE timeframe='D1' AND (? IS NULL OR asset=?) ORDER BY asset""",
            (requested_symbol, requested_symbol),
        ).fetchall()
        commissioned = {
            key for key in commissioned_lane_keys(connection)
            if requested_symbol is None or key[0] == requested_symbol
        }
        last_success = {
            (str(row[0]), str(row[1])): {
                "provider": row[2], "provider_symbol": row[3],
                "mapping_class": row[4], "finished_at": row[5],
            }
            for row in connection.execute(
                """WITH ranked AS (
                       SELECT json_extract(detail,'$.asset') asset,
                              json_extract(detail,'$.timeframe') timeframe,
                              json_extract(detail,'$.provider') provider,
                              json_extract(detail,'$.provider_symbol') provider_symbol,
                              json_extract(detail,'$.mapping_class') mapping_class,
                              finished_at_utc,
                              row_number() OVER (
                                  PARTITION BY json_extract(detail,'$.asset'),
                                               json_extract(detail,'$.timeframe')
                                  ORDER BY finished_at_utc DESC, ingest_run_id DESC
                              ) ordinal
                       FROM ingest_runs WHERE status='committed'
                         AND (? IS NULL OR json_extract(detail,'$.asset')=?)
                   )
                   SELECT asset,timeframe,provider,provider_symbol,mapping_class,finished_at_utc
                   FROM ranked WHERE ordinal=1""",
                (requested_symbol, requested_symbol),
            ).fetchall()
            if row[0] and row[1]
        }
    active_symbols = active_representation_symbols(database_path)
    operational_facts = load_provider_facts(database_path).get("mappings", {})
    rows: list[dict[str, object]] = []
    for registration in registrations:
        canonical, asset_class, representation, primary_provider, primary_symbol, registration_status, identity_text = registration
        if str(canonical) not in active_symbols:
            continue
        identity = json.loads(identity_text) if identity_text else {}
        canonical_quote = identity.get("trading_currency")
        canonical_base = (
            str(canonical)[:-len(str(canonical_quote))]
            if canonical_quote and str(canonical).endswith(str(canonical_quote))
            else identity.get("instrument_family")
        )
        timeframes = [requested_timeframe] if requested_timeframe else ["D1", "H1", "M30", "M5"]
        for lane_timeframe in timeframes:
            if lane_timeframe is None:
                continue
            for profile in selected_profiles:
                prior = last_success.get((str(canonical), lane_timeframe))
                effective_primary_provider = (
                    prior.get("provider") if prior and prior.get("provider") == profile.provider
                    else primary_provider
                )
                effective_primary_symbol = (
                    prior.get("provider_symbol") if prior and prior.get("provider") == profile.provider
                    else primary_symbol
                )
                mapping = mapping_authority(
                    profile, symbol=str(canonical), timeframe=lane_timeframe,
                    primary_provider=effective_primary_provider, primary_symbol=effective_primary_symbol,
                    resolved_mapping=(operational_facts.get(f"{profile.provider}:{canonical}") if isinstance(operational_facts, dict) else None),
                )
                start = requested_start or observed.date().isoformat()
                end = requested_end or start
                estimated = estimate_requests(lane_timeframe, start, end, profile.maximum_rows_per_request)
                reason = eligibility_reason(
                    profile, asset_class=str(asset_class), timeframe=lane_timeframe,
                    mapping=(str(mapping["provider_symbol"]) if mapping.get("direct_real_eligible") else None),
                    credentials=available_credentials, state=states.get(profile.provider, {}),
                    budget=selected_budgets[profile.provider], estimated_requests=estimated,
                    missing_start=start, missing_end=end, now=observed,
                    work_class="OPERATOR_FETCH",
                )
                if mapping.get("timeframe_supported") is False:
                    reason = "TIMEFRAME_UNSUPPORTED"
                quote_equivalence_rejection = _quote_equivalence_rejection(str(asset_class), mapping)
                if quote_equivalence_rejection:
                    reason = quote_equivalence_rejection
                route_rank, routing_policy, routing_rejection = _routing_policy(
                    asset_class=str(asset_class), timeframe=lane_timeframe,
                    profile=profile, mapping=mapping,
                )
                if routing_rejection and mapping.get("direct_real_eligible"):
                    reason = routing_rejection
                capability_state = _controlled_capability_state(profile, mapping, reason)
                rows.append({
                    "canonical_symbol": canonical,
                    "canonical_representation": representation,
                    "canonical_base_asset": canonical_base or mapping.get("canonical_base_asset"),
                    "canonical_quote_asset": canonical_quote or mapping.get("canonical_quote_asset"),
                    "timeframe": lane_timeframe,
                    "provider": profile.provider,
                    "provider_symbol": mapping.get("provider_symbol"),
                    "provider_representation": mapping.get("provider_representation"),
                    "provider_base_asset": mapping.get("provider_base_asset"),
                    "provider_quote_asset": mapping.get("provider_quote_asset"),
                    "mapping_status": mapping.get("mapping_status"),
                    "mapping_class": mapping.get("mapping_class"),
                    "conversion_policy": mapping.get("conversion_policy"),
                    "reviewed_status": mapping.get("reviewed_status"),
                    "capability_state": capability_state,
                    "eligibility": "ELIGIBLE" if reason is None else "INELIGIBLE",
                    "credential_status": "AVAILABLE" if not profile.credential_environment or available_credentials.get(profile.provider) else "CREDENTIAL_REQUIRED",
                    "entitlement_status": profile.entitlement_state,
                    "rate_policy_status": "VERIFIED" if profile.rate_policy_verified else "RATE_POLICY_UNVERIFIED",
                    "history_range_support": "UNBOUNDED_BY_CONTRACT" if profile.history_limit_days is None else f"{profile.history_limit_days}_CALENDAR_DAYS",
                    "priority": profile.priority,
                    "routing_policy": routing_policy,
                    "routing_rank": route_rank,
                    "quote_equivalence": mapping.get("quote_equivalence"),
                    "quote_equivalence_reason": mapping.get("quote_equivalence_reason"),
                    "rejection_reason": reason or mapping.get("rejection_reason"),
                    "authority_source": mapping.get("authority_source"),
                    "resolution_method": mapping.get("resolution_method"),
                    "resolution_evidence": mapping.get("resolution_evidence"),
                    "timeframe_capability": mapping.get("timeframe_capability"),
                    "registration_status": registration_status,
                    "existing_commissioned_lane": (str(canonical), lane_timeframe) in commissioned,
                    "last_successful_provider": prior,
                })
    return {
        "contract": CAPABILITY_PROJECTION_CONTRACT,
        "generated_at": observed.isoformat(),
        "rows": rows,
    }


def cached_acquisition_capability_projection(
    database_path: str | Path,
    **kwargs,
) -> dict[str, object]:
    """Reuse an unchanged capability matrix without caching credential values.

    The cache key includes the canonical database revision, provider-facts
    revision, a redacted credential revision, profile configuration, provider
    status, and the requested planning scope. Any one of those changes creates
    a new authority answer.
    """
    profiles = tuple(kwargs.get("profiles") or load_provider_profiles())
    credentials = kwargs.get("credentials") or credential_map()
    provider_state = kwargs.get("provider_state") or {}
    budgets = kwargs.get("budgets") or {}
    facts = load_provider_facts(database_path)
    budget_state = {
        provider: budget.inspect() if hasattr(budget, "inspect") else repr(budget)
        for provider, budget in budgets.items()
    }
    key = revision_key(
        database_path,
        provider_facts_revision=facts.get("revision", 0),
        credential_revision=redacted_revision(credentials),
        profile_revision=redacted_revision([repr(profile) for profile in profiles]),
        provider_state_revision=redacted_revision({"state": provider_state, "budget": budget_state}),
        request={
            "symbol": kwargs.get("symbol"), "timeframe": kwargs.get("timeframe"),
            "requested_start": kwargs.get("requested_start"),
            "requested_end": kwargs.get("requested_end"),
        },
    )
    call_kwargs = dict(kwargs)
    call_kwargs["profiles"] = profiles
    call_kwargs["credentials"] = credentials
    return AUTHORITY_PREFLIGHT_CACHE.get_or_compute(
        key, lambda: acquisition_capability_projection(database_path, **call_kwargs)
    )


def capability_reconciliation_report(
    projection: dict[str, object],
) -> dict[str, object]:
    """Audit legacy display claims against the unified runtime projection."""

    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for raw in projection.get("rows", []):
        if not isinstance(raw, dict):
            continue
        key = (str(raw.get("canonical_symbol")), str(raw.get("timeframe")))
        grouped.setdefault(key, []).append(raw)
    rows: list[dict[str, object]] = []
    for (symbol, timeframe), capabilities in sorted(grouped.items()):
        previous = "SUPPORTED" if timeframe == "D1" else "CAPABILITY_UNKNOWN"
        actual = [
            {
                "provider": row.get("provider"),
                "capability_state": row.get("capability_state"),
                "eligibility": row.get("eligibility"),
                "rejection_reason": row.get("rejection_reason"),
            }
            for row in capabilities
        ]
        mapping = [
            {
                "provider": row.get("provider"),
                "provider_symbol": row.get("provider_symbol"),
                "mapping_status": row.get("mapping_status"),
                "mapping_class": row.get("mapping_class"),
                "authority_source": row.get("authority_source"),
            }
            for row in capabilities
        ]
        supported = any(
            row.get("capability_state")
            in {"SUPPORTED", "SUPPORTED_WITH_APPROVED_MAPPING", "CREDENTIAL_REQUIRED"}
            for row in capabilities
        )
        ambiguous = any(
            row.get("mapping_class") in {"CONVERSION_REQUIRED", "NOT_EQUIVALENT"}
            for row in capabilities
        )
        decision = (
            "REVIEW_REPRESENTATION_EQUIVALENCE"
            if ambiguous
            else "REVIEW_PROVIDER_MAPPING"
            if not supported and any(row.get("mapping_status") == "MAPPING_REQUIRED" for row in capabilities)
            else "NONE"
        )
        rows.append({
            "lane": f"{symbol}:{timeframe}",
            "previous_displayed_capability": previous,
            "actual_provider_capability": actual,
            "mapping_status": mapping,
            "required_operator_decision": decision,
            "display_contradiction": previous == "CAPABILITY_UNKNOWN" and supported,
        })
    return {
        "contract": "fragarach_ii.capability_reconciliation.v1",
        "generated_at": projection.get("generated_at"),
        "canonical_observations_action": "RETAINED_UNCHANGED",
        "provider_mapping_archive_action": "NONE",
        "rows": rows,
        "contradiction_count": sum(bool(row["display_contradiction"]) for row in rows),
        "operator_review_count": sum(row["required_operator_decision"] != "NONE" for row in rows),
    }


def _controlled_capability_state(
    profile: ProviderProfile, mapping: dict[str, object], reason: str | None
) -> str:
    if not profile.enabled or reason == "PROVIDER_DISABLED":
        return "PROVIDER_DISABLED"
    if reason in {"ASSET_CLASS_UNSUPPORTED", "TIMEFRAME_UNSUPPORTED"}:
        return "TIMEFRAME_UNSUPPORTED"
    if reason == "CRYPTO_INTRADAY_NOT_APPROVED":
        return "CAPABILITY_UNKNOWN"
    if reason == "CRYPTO_QUOTE_EQUIVALENCE_NOT_APPLICABLE":
        return "MAPPING_REQUIRED"
    if mapping.get("mapping_class") in {"CONVERSION_REQUIRED", "NOT_EQUIVALENT"}:
        return "MAPPING_REQUIRED"
    if not mapping.get("direct_real_eligible"):
        return "MAPPING_REQUIRED" if mapping.get("authority_source") != "NO_APPROVED_MAPPING_AUTHORITY" else "CAPABILITY_UNKNOWN"
    if reason in {"CREDENTIAL_MISSING", "AUTHENTICATION_BLOCKED", "AUTHENTICATION_FAILED"}:
        return "CREDENTIAL_REQUIRED"
    if reason == "ENTITLEMENT_BLOCKED":
        return "ENTITLEMENT_REQUIRED"
    if reason == "RANGE_UNAVAILABLE":
        return "RANGE_UNAVAILABLE"
    if not profile.rate_policy_verified:
        return "RATE_POLICY_UNVERIFIED"
    return "SUPPORTED" if mapping.get("mapping_class") == "EXACT_REPRESENTATION" else "SUPPORTED_WITH_APPROVED_MAPPING"


def estimate_requests(timeframe: str, start: str, end: str, maximum_rows: int) -> int:
    first, last = _bound_date(start), _bound_date(end)
    days = max(1, (last - first).days + 1)
    rows_per_day = {"D1": 1, "H1": 24, "M30": 48, "M5": 288}.get(timeframe, 1)
    days_per_request = max(1, maximum_rows // rows_per_day)
    return max(1, math.ceil(days / days_per_request))


def _bound_date(value: str) -> date:
    """Reduce an approved date or UTC instant to its calendar day for planning."""
    raw = str(value).strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        return datetime.fromisoformat(normalized).date()


def eligibility_reason(
    profile: ProviderProfile,
    *,
    asset_class: str,
    timeframe: str,
    mapping: str | None,
    credentials: dict[str, str],
    state: object,
    budget: RateBudgetController,
    estimated_requests: int,
    missing_start: str,
    missing_end: str,
    now: datetime,
    work_class: str = "NORMAL",
    queue_percentage: int = 80,
    protected_normal_demand: int = 0,
) -> str | None:
    if not profile.enabled:
        return "PROVIDER_DISABLED"
    if asset_class not in profile.supported_asset_classes:
        return "ASSET_CLASS_UNSUPPORTED"
    if timeframe not in profile.supported_timeframes:
        return "TIMEFRAME_UNSUPPORTED"
    if mapping is None:
        return "NO_APPROVED_MAPPING"
    if profile.credential_environment and not credentials.get(profile.provider):
        return "CREDENTIAL_MISSING"
    current = state if isinstance(state, dict) else {}
    if current.get("health") == "Credential Missing":
        return "CREDENTIAL_MISSING"
    if current.get("health") == "Authentication Failed":
        return "AUTHENTICATION_FAILED"
    if profile.entitlement_state != "AVAILABLE" or current.get("health") == "Entitlement Blocked":
        return "ENTITLEMENT_BLOCKED"
    cooldown = current.get("cooldown_until")
    if cooldown and profile.provider != "TWELVE_DATA":
        try:
            if datetime.fromisoformat(str(cooldown)) > now.astimezone(UTC):
                return "PROVIDER_COOLDOWN"
        except ValueError:
            pass
    if profile.history_limit_days is not None:
        span = (_bound_date(missing_end) - _bound_date(missing_start)).days + 1
        if span > profile.history_limit_days:
            return "RANGE_UNAVAILABLE"
    if estimated_requests > profile.request_limit:
        return "RANGE_UNAVAILABLE"
    budget_state = budget.inspect(
        estimated_requests,
        work_class=work_class,
        queue_percentage=queue_percentage,
        protected_normal_demand=protected_normal_demand,
        safety_reserve=profile.safety_reserve,
    )
    if not budget_state["eligible"]:
        return str(budget_state["reason"])
    return None


def classify_failure(error: BaseException) -> tuple[str, str]:
    code = getattr(error, "code", None)
    normalized = str(code or "").upper()
    mapping = {
        "MISSING_CREDENTIAL": "CREDENTIAL_MISSING",
        "INVALID_API_KEY": "AUTHENTICATION_FAILED",
        "AUTHENTICATION_FAILED": "AUTHENTICATION_FAILED",
        "QUOTA_EXCEEDED": "QUOTA_EXCEEDED",
        "ENTITLEMENT_BLOCKED": "ENTITLEMENT_BLOCKED",
        "UNSUPPORTED_TIMEFRAME": "TIMEFRAME_UNSUPPORTED",
        "RANGE_TOO_LARGE": "RANGE_UNAVAILABLE",
        "PROVIDER_ORIENTATION_MISMATCH": "ORIENTATION_MISMATCH",
        "INVALID_OHLC": "INVALID_OHLC",
        "NO_DATA": "NO_NEW_DATA",
        "RATE_LIMITED": "TWELVEDATA_RATE_LIMIT_429",
        "RATE_LIMIT": "TWELVEDATA_RATE_LIMIT_429",
        "HTTP_429": "TWELVEDATA_RATE_LIMIT_429",
        "TWELVEDATA_RATE_LIMIT_429": "TWELVEDATA_RATE_LIMIT_429",
        "TWELVEDATA_UPSTREAM_5XX": "TWELVEDATA_UPSTREAM_5XX",
        "TWELVEDATA_TRANSPORT_FAILURE": "TWELVEDATA_TRANSPORT_FAILURE",
        "TWELVEDATA_INVALID_RESPONSE": "TWELVEDATA_INVALID_RESPONSE",
        "PROVIDER_TIMEOUT": "TWELVEDATA_TRANSPORT_FAILURE",
        "INVALID_RESPONSE": "TWELVEDATA_INVALID_RESPONSE",
        "MALFORMED_PAYLOAD": "TWELVEDATA_INVALID_RESPONSE",
        "PROVIDER_DECLARED_ERROR": "TWELVEDATA_INVALID_RESPONSE",
        "NO_USABLE_OBSERVATIONS": "TWELVEDATA_INVALID_RESPONSE",
        "SYMBOL_MISMATCH": "TWELVEDATA_INVALID_RESPONSE",
        "INTERVAL_MISMATCH": "TWELVEDATA_INVALID_RESPONSE",
        "INVALID_OBSERVATION": "TWELVEDATA_INVALID_RESPONSE",
        "CONFLICTING_DUPLICATE": "TWELVEDATA_INVALID_RESPONSE",
        "POST_INGEST_VALIDATION_FAILED": "PUBLICATION_ERROR",
        "QUEUE_COMPLETION_ERROR": "QUEUE_COMPLETION_ERROR",
    }
    if normalized in mapping:
        return mapping[normalized], str(error)
    text = str(error).lower()
    if isinstance(error, (TimeoutError, ConnectionError)) or "timed out" in text:
        return "TWELVEDATA_TRANSPORT_FAILURE", str(error)
    if "429" in text:
        return "TWELVEDATA_RATE_LIMIT_429", str(error)
    if "401" in text or "api key" in text or "authentication" in text:
        return "AUTHENTICATION_FAILED", str(error)
    if "entitlement" in text or "subscription" in text:
        return "ENTITLEMENT_BLOCKED", str(error)
    if isinstance(error, json.JSONDecodeError):
        return "LOCAL_PARSE_ERROR", str(error)
    if isinstance(error, ValueError):
        return "LOCAL_PROGRAMMING_ERROR", str(error)
    try:
        import sqlite3
        if isinstance(error, sqlite3.Error):
            if getattr(error, "fragarach_stage", None) == "COMMIT":
                return "SQLITE_COMMIT_ERROR", str(error)
            name = str(getattr(error, "sqlite_errorname", "") or "").upper()
            message = str(error).lower()
            if "BUSY" in name or "busy" in message:
                return "SQLITE_BUSY", str(error)
            if "LOCKED" in name or "locked" in message:
                return "SQLITE_LOCKED", str(error)
            return "SQLITE_WRITE_ERROR", str(error)
    except ImportError:  # pragma: no cover - sqlite3 is part of Python
        pass
    cause = getattr(error, "cause", None)
    if isinstance(cause, BaseException) and cause is not error:
        return classify_failure(cause)
    if type(error).__name__ == "WriterLockError":
        return "SQLITE_LOCKED", str(error)
    return "LOCAL_PROGRAMMING_ERROR", f"{type(error).__name__}: {error}"


def update_provider_health(
    state: dict[str, object], profile: ProviderProfile, result: str, now: datetime,
    *, lane: str | None = None, request_id: str | None = None,
    response_class: str | None = None,
) -> None:
    stamp = now.astimezone(UTC).isoformat()
    score = int(state.get("health_score", 100))
    if result == "SUCCESS":
        state["responses_received"] = int(state.get("responses_received", 0)) + 1
        state.update(
            health="Healthy", health_score=min(100, score + 20),
            consecutive_failures=0, cooldown_until=None, cooldown=None, last_success=stamp,
            wait_reason=None, wait_scope=None,
        )
        return
    local_domains = {
        "LOCAL_PARSE_ERROR", "LOCAL_ADMISSION_ERROR", "LOCAL_CANONICAL_ERROR",
        "LOCAL_PROGRAMMING_ERROR", "SQLITE_BUSY", "SQLITE_LOCKED",
        "SQLITE_WRITE_ERROR", "SQLITE_COMMIT_ERROR", "PUBLICATION_ERROR",
        "QUEUE_COMPLETION_ERROR",
    }
    if result in local_domains:
        state["last_local_failure"] = {"at": stamp, "reason": result}
        return
    state["last_failure"] = stamp
    state["last_failure_reason"] = result
    if result == "TWELVEDATA_RATE_LIMIT_429":
        state["rate_limit_responses"] = int(state.get("rate_limit_responses", 0)) + 1
    if result in RETRYABLE_FAILURES and result != "TWELVEDATA_RATE_LIMIT_429":
        state["transient_failures"] = int(state.get("transient_failures", 0)) + 1
    if result == "CREDENTIAL_MISSING":
        state.update(health="Credential Missing", health_score=0, wait_reason="CREDENTIAL_MISSING", wait_scope="PROVIDER")
        return
    if result == "AUTHENTICATION_FAILED":
        state.update(health="Authentication Failed", health_score=0, wait_reason="AUTHENTICATION_FAILED", wait_scope="PROVIDER")
        return
    if result == "QUOTA_EXCEEDED":
        state.update(health="Quota Exceeded", health_score=0, wait_reason="QUOTA_EXCEEDED", wait_scope="PROVIDER")
        return
    if result == "ENTITLEMENT_BLOCKED":
        state.update(health="Entitlement Blocked", health_score=0, wait_reason="ENTITLEMENT_BLOCKED", wait_scope="PROVIDER")
        return
    if result == "TWELVEDATA_RATE_LIMIT_429":
        state.update(
            health="Healthy", cooldown_until=None, cooldown=None,
            wait_reason="CREDIT_WINDOW_EXHAUSTED", wait_scope="CREDIT_WINDOW",
        )
        return
    failures = int(state.get("consecutive_failures", 0)) + 1
    state["consecutive_failures"] = failures
    state["health_score"] = max(0, score - (20 if result in RETRYABLE_FAILURES else 8))
    if result in RETRYABLE_FAILURES:
        state["health"] = "Degraded"
        state["cooldown_until"] = None
        state["cooldown"] = None
        state["wait_reason"] = None
        state["wait_scope"] = None
    elif result in EVIDENCE_FAILURES:
        state["health"] = "Degraded" if state["health_score"] < 70 else "Healthy"
        state["lane_specific_failure"] = {
            "reason": "LANE_SPECIFIC_FAILURE", "scope": "LANE", "triggering_lane": lane,
            "triggering_request": request_id, "triggering_response_class": response_class or result,
            "failure_count": failures, "started_time": stamp, "expiry_time": None,
        }
    else:
        state["health"] = "Unavailable"


def provider_monitor_rows(
    profiles: tuple[ProviderProfile, ...],
    provider_state: dict[str, object],
    budgets: dict[str, RateBudgetController],
    credentials: dict[str, str],
    now: datetime,
    *,
    queue_percentage: int = 80,
    protected_demand: dict[str, int] | None = None,
    active_requests: dict[str, int] | None = None,
    throughput: dict[str, object] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    providers, rate_budgets = [], []
    throughput_by_provider = {
        str(item.get("provider")): item
        for item in (throughput or {}).get("providers", [])
        if isinstance(item, dict)
    }
    for profile in profiles:
        state = _state_dict(provider_state, profile.provider)
        authority_resolution = CredentialAuthority().resolve(profile.provider)
        authority_matches_projection = (
            not profile.credential_environment
            or authority_resolution.credential == credentials.get(profile.provider)
        )
        cooldown = None if profile.provider == "TWELVE_DATA" else state.get("cooldown_until")
        health = str(state.get("health", "Healthy"))
        wait_reason = state.get("wait_reason")
        wait_scope = state.get("wait_scope")
        if profile.credential_environment and not credentials.get(profile.provider):
            health = "Credential Missing"
            wait_reason, wait_scope = "CREDENTIAL_MISSING", "PROVIDER"
        if profile.entitlement_state != "AVAILABLE":
            health = "Entitlement Blocked"
            wait_reason, wait_scope = "ENTITLEMENT_BLOCKED", "PROVIDER"
        if cooldown and not state.get("wait_reason"):
            # Legacy journals did not preserve cause.  SPEC-046 forbids
            # reconstructing a provider-imposed cooldown from that ambiguity.
            cooldown = None
            state["cooldown_until"] = None
            state["cooldown"] = None
            health = "Degraded" if health == "Cooling Down" else health
            state["health"] = health
        if cooldown:
            try:
                if datetime.fromisoformat(str(cooldown)) <= now.astimezone(UTC):
                    health = "Degraded"
                    state["health"] = health
                    state["cooldown_until"] = None
                    state["cooldown"] = None
                    state["wait_reason"] = None
                    state["wait_scope"] = None
                    cooldown = None
            except ValueError:
                cooldown = None
        budget = budgets[profile.provider].inspect(
            1,
            work_class="QUEUE", queue_percentage=queue_percentage,
            protected_normal_demand=int((protected_demand or {}).get(profile.provider, 0)),
            safety_reserve=profile.safety_reserve,
        )
        if profile.provider == "TWELVE_DATA":
            cooldown = None
            if budget.get("rate_limit_until"):
                health = "Healthy"
                wait_reason, wait_scope = "CREDIT_WINDOW_EXHAUSTED", "CREDIT_WINDOW"
            elif wait_reason == "CREDIT_WINDOW_EXHAUSTED":
                wait_reason = wait_scope = None
                state["wait_reason"] = None
                state["wait_scope"] = None
        adaptive = throughput_by_provider.get(profile.provider, {})
        providers.append({
            "provider": profile.provider,
            "enabled": profile.enabled,
            "supported_asset_classes": list(profile.supported_asset_classes),
            "supported_timeframes": list(profile.supported_timeframes),
            "approved_symbol_mappings": len(profile.mappings),
            "credential_requirement": profile.credential_requirement,
            "credentials": "Present" if (not profile.credential_environment or credentials.get(profile.provider)) else "Missing",
            "credential_state": authority_resolution.state.value if authority_matches_projection else ("Available" if credentials.get(profile.provider) else "Missing"),
            "credential_authority_revision": authority_resolution.authority_revision if authority_matches_projection else _credential_projection_revision(profile.provider, credentials.get(profile.provider)),
            "credential_last_validation": authority_resolution.last_validation if authority_matches_projection else None,
            "credential_validation_source": authority_resolution.validation_source if authority_matches_projection else "Injected test authority",
            "entitlement": profile.entitlement_state,
            "request_limit": profile.request_limit,
            "plan_limit": budget.get("plan_limit", profile.request_limit),
            "operational_credit_limit": budget.get("operational_limit", profile.operational_limit or profile.request_limit),
            "request_window_seconds": profile.request_window_seconds,
            "budget_unit": profile.budget_unit,
            "budget_policy": profile.budget_policy,
            "rate_policy_verified": profile.rate_policy_verified,
            "queue_ceiling": budget["queue_ceiling"],
            "protected_capacity": budget["protected_capacity"],
            "adaptive_target": adaptive.get("target_requests_per_window", budget["queue_ceiling"]),
            "target_utilization_percent": adaptive.get("target_utilization_percent", queue_percentage),
            "dynamic_reserved_capacity": adaptive.get("reserved_capacity", 0),
            "dispatch_available": adaptive.get("available_capacity", budget["queue_available"]),
            "budget_used": budget["calls_used"],
            "budget_available": budget["calls_available"],
            "window_started_at": budget.get("window_started_at"),
            "window_ends_at": budget.get("window_ends_at"),
            "credits_consumed": budget.get("credits_consumed", budget["calls_used"]),
            "credits_remaining": budget.get("credits_remaining", budget["calls_available"]),
            "next_dispatch_at": budget.get("next_dispatch_at"),
            "last_429_at": budget.get("last_429_at"),
            "requests_last_minute": budget.get("requests_last_minute", budget["calls_used"]),
            "current_dispatch_rate": budget.get("dispatch_rate_per_minute", 0),
            "actual_dispatched_calls": budget["calls_used"],
            "active_reservations": budget["active_reservations"],
            "capacity_reserved": budget["reserved_calls"],
            "responses_received": int(state.get("responses_received", 0)),
            "rate_limit_responses": int(state.get("rate_limit_responses", 0)),
            "transient_failures": int(state.get("transient_failures", 0)),
            "active_requests": int((active_requests or {}).get(profile.provider, 0)),
            "concurrency_limit": profile.concurrency_limit,
            "effective_throughput": state.get("effective_throughput", 0),
            "next_budget_release": budget["next_available"],
            "next_scheduled_demand": state.get("next_scheduled_demand"),
            "maximum_rows_per_request": profile.maximum_rows_per_request,
            "history_limitations": profile.history_limit_days,
            "cost_class": profile.cost_class,
            "priority": profile.priority,
            "health": health,
            "cooldown_until": cooldown,
            "provider_wait_reason": wait_reason,
            "provider_wait_scope": wait_scope,
            "cooldown_record": state.get("cooldown"),
            "last_success": state.get("last_success"),
            "last_failure": state.get("last_failure"),
        })
        rate_budgets.append({
            "provider": profile.provider,
            "limit": profile.request_limit,
            "plan_limit": budget.get("plan_limit", profile.request_limit),
            "operational_limit": budget.get("operational_limit", profile.operational_limit or profile.request_limit),
            "window_seconds": profile.request_window_seconds,
            "calls_used": budget["calls_used"],
            "calls_available": budget["calls_available"],
            "actual_dispatched_calls": budget["calls_used"],
            "active_reservations": budget["active_reservations"],
            "capacity_reserved": budget["reserved_calls"],
            "next_available": budget["next_available"],
            "window_started_at": budget.get("window_started_at"),
            "window_ends_at": budget.get("window_ends_at"),
            "credits_consumed": budget.get("credits_consumed", budget["calls_used"]),
            "credits_remaining": budget.get("credits_remaining", budget["calls_available"]),
            "next_dispatch_at": budget.get("next_dispatch_at"),
            "last_429_at": budget.get("last_429_at"),
            "requests_last_minute": budget.get("requests_last_minute", budget["calls_used"]),
            "current_dispatch_rate": budget.get("dispatch_rate_per_minute", 0),
            "queue_calls_used": budget["queue_calls_used"],
            "queue_ceiling": budget["queue_ceiling"],
            "protected_capacity": budget["protected_capacity"],
            "queue_available": budget["queue_available"],
        })
    return providers, rate_budgets


def _credential_projection_revision(provider: str, credential: str | None) -> str:
    fingerprint = hashlib.sha256(credential.encode("utf-8")).hexdigest() if credential else "none"
    state = "Available" if credential else "Missing"
    return hashlib.sha256(
        f"fragarach_ii.credential_authority.v1|{provider}|{state}|{fingerprint}".encode("utf-8")
    ).hexdigest()


def create_manual_request(
    requests: list[dict[str, object]],
    *,
    symbol: str,
    timeframe: str,
    missing_start: str,
    missing_end: str,
    expected_edge: str,
    reason: str,
    providers_attempted: list[str],
    failures: list[dict[str, object]],
    now: datetime,
    providers_considered: list[dict[str, object]] | None = None,
    recommended_operator_action: str = "IMPORT_REVIEWED_MANUAL_EVIDENCE",
    provider_fact_revision: int | None = None,
    capability_projection_revision: str | None = None,
) -> dict[str, object]:
    for request in requests:
        if (
            request.get("symbol") == symbol
            and request.get("timeframe") == timeframe
            and request.get("missing_start") == missing_start
            and request.get("missing_end") == missing_end
            and request.get("status") in {"Required", "Acknowledged"}
        ):
            request.setdefault("providers_considered_at_creation", list(request.get("providers_considered", [])))
            request.setdefault("providers_attempted_at_creation", list(request.get("providers_attempted", [])))
            request.setdefault("original_rejection_reasons", list(request.get("providers_rejected", [])))
            request.setdefault("original_provider_facts", list(request.get("providers_considered", [])))
            request.setdefault("original_missing_range", {
                "start": request.get("missing_start"), "end": request.get("missing_end"),
            })
            request["providers_considered"] = list(providers_considered or [])
            request["providers_rejected"] = [
                item for item in providers_considered or [] if not item.get("eligible")
            ]
            request["provider_failure_summaries"] = failures
            request["mapping_limitations"] = [
                item for item in providers_considered or []
                if item.get("reason") in {"NO_APPROVED_MAPPING", "MAPPING_REQUIRED"}
            ]
            return request
    request = {
        "id": f"manual-{uuid.uuid4().hex}",
        "symbol": symbol,
        "timeframe": timeframe,
        "missing_start": missing_start,
        "missing_end": missing_end,
        "expected_canonical_edge": expected_edge,
        "priority": "High",
        "reason": reason,
        "providers_attempted": providers_attempted,
        "providers_considered": list(providers_considered or []),
        "providers_rejected": [
            item for item in providers_considered or [] if not item.get("eligible")
        ],
        "provider_failure_summaries": failures,
        "mapping_limitations": [
            item for item in providers_considered or []
            if item.get("reason") in {"NO_APPROVED_MAPPING", "MAPPING_REQUIRED"}
        ],
        "recommended_operator_action": recommended_operator_action,
        "accepted_import_format": "CSV via Manage Data preview, validation, quarantine, and immutable ingest",
        "created_at": now.astimezone(UTC).isoformat(),
        "status": "Required",
        "created_provider_fact_revision": provider_fact_revision,
        "last_evaluated_provider_fact_revision": provider_fact_revision,
        "created_capability_projection_revision": capability_projection_revision,
        "last_evaluated_capability_projection_revision": capability_projection_revision,
        "last_evaluated_at": now.astimezone(UTC).isoformat(),
        "reconciliation_status": "STILL_NO_ELIGIBLE_PROVIDER",
        "reconciliation_reason": reason,
        "providers_considered_at_creation": list(providers_considered or []),
        "providers_attempted_at_creation": list(providers_attempted),
        "original_rejection_reasons": [
            item for item in providers_considered or [] if not item.get("eligible")
        ],
        "original_provider_facts": list(providers_considered or []),
        "original_missing_range": {"start": missing_start, "end": missing_end},
    }
    requests.append(request)
    return request


def resolve_satisfied_manual_requests(
    database_path: str | Path, requests: list[dict[str, object]], now: datetime
) -> bool:
    changed = False
    with open_read_only(database_path) as connection:
        for request in requests:
            if request.get("status") not in {"Required", "Acknowledged"}:
                continue
            row = connection.execute(
                "SELECT max(open_time_utc) FROM bars WHERE asset=? AND timeframe=?",
                (request["symbol"], request["timeframe"]),
            ).fetchone()
            if row and row[0] is not None:
                latest = datetime.fromtimestamp(row[0], UTC)
                required = datetime.fromisoformat(str(request["expected_canonical_edge"]))
                required = required.replace(tzinfo=UTC) if required.tzinfo is None else required.astimezone(UTC)
                if latest >= required:
                    request["status"] = "Resolved"
                    request["resolved_at"] = now.astimezone(UTC).isoformat()
                    changed = True
    return changed


def dismiss_manual_request(requests: list[dict[str, object]], request_id: str, now: datetime) -> dict[str, object]:
    for request in requests:
        if request.get("id") == request_id:
            if request.get("status") == "Resolved":
                raise ValueError("resolved manual request cannot be dismissed")
            request["status"] = "Dismissed"
            request["dismissed_at"] = now.astimezone(UTC).isoformat()
            return request
    raise ValueError(f"unknown manual acquisition request: {request_id}")


def _registration(database_path: str | Path, symbol: str) -> tuple[str, str | None, str | None]:
    with open_read_only(database_path) as connection:
        row = connection.execute(
            "SELECT asset_class,provider_id,provider_symbol FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
            (symbol,),
        ).fetchone()
    if not row:
        raise ValueError(f"unregistered instrument: {symbol}")
    return str(row[0]), row[1], row[2]


def _state_dict(provider_state: dict[str, object], provider: str) -> dict[str, object]:
    state = provider_state.setdefault(provider, {})
    if not isinstance(state, dict):
        state = {}
        provider_state[provider] = state
    return state
