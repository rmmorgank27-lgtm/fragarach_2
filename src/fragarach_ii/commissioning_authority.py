"""Canonical SPEC-053 commissioning and operational-priority authority."""

from __future__ import annotations

from collections.abc import Iterable,Mapping


ALL_TIMEFRAMES = ("D1", "H1", "M30", "M5")

# This is the only definition of the operational estate Fragarach requires.
# Callers provide persisted registration/lane facts; this authority never
# commissions a lane or fabricates evidence.
REQUIRED_TIMEFRAMES = {
    "FOREX": ALL_TIMEFRAMES,
    "METALS": ALL_TIMEFRAMES,
    "ENERGY": ALL_TIMEFRAMES,
    "INDICES": ALL_TIMEFRAMES,
    "CRYPTO": ALL_TIMEFRAMES,
    "STOCKS": ("D1",),
}

OPERATIONAL_STATES = (
    "Current",
    "Behind",
    "Queued",
    "Downloading",
    "Unavailable",
    "Missing",
    "Not Commissioned",
)

OPERATIONAL_MARKET_ORDER = (
    "FOREX",
    "METALS",
    "INDICES",
    "ENERGY",
    "CRYPTO",
    "STOCKS",
)


def canonical_market(asset_class: str) -> str:
    """Normalize registration asset classes into the commissioning markets."""

    value = asset_class.strip().upper()
    if value == "FX" or "FOREX" in value:
        return "FOREX"
    if "METAL" in value:
        return "METALS"
    if "ENERGY" in value:
        return "ENERGY"
    if "INDIC" in value:
        return "INDICES"
    if "CRYPTO" in value or "DIGITAL_ASSET" in value:
        return "CRYPTO"
    if "EQUIT" in value or value in {"STOCK", "STOCKS"}:
        return "STOCKS"
    return value


def required_timeframes(asset_class: str) -> tuple[str, ...]:
    """Return the complete ordered set of required lanes for an asset class."""

    return REQUIRED_TIMEFRAMES.get(canonical_market(asset_class), ("D1",))


def commissioning_policy(asset_class: str, timeframe: str) -> str:
    timeframe = timeframe.strip().upper()
    if timeframe in required_timeframes(asset_class):
        return "REQUIRED"
    if canonical_market(asset_class) == "STOCKS" and timeframe in ALL_TIMEFRAMES:
        return "INTENTIONALLY_DEFERRED"
    return "NOT_AUTHORISED"


def operational_market_rank(asset_class: str | None) -> int:
    """Return the deterministic dispatch rank; unknown future markets sort last."""

    market = canonical_market(asset_class or "")
    try:
        return OPERATIONAL_MARKET_ORDER.index(market)
    except ValueError:
        return len(OPERATIONAL_MARKET_ORDER)


def project_required_lanes(
    registrations: Iterable[tuple[str, str]],
    commissioned_lanes: set[tuple[str, str]],
    *,
    evidence_counts: Mapping[tuple[str, str], int] | None = None,
    operational_states: Mapping[tuple[str, str], str] | None = None,
    operational_lanes: set[tuple[str, str]] | None = None,
    enabled_lanes: set[tuple[str, str]] | None = None,
) -> list[dict[str, object]]:
    """Build the enabled Required → Commissioned → Operational projection.

    A registered D1 identity is always required.  Lower timeframes are visible
    for every symbol, but do not become a required commission merely because a
    market class *could* support them.  They become required only after their
    explicit lane commissioning enables them.
    """

    counts=evidence_counts or {}
    states=operational_states or {}
    operational=operational_lanes or set()
    enabled=enabled_lanes
    result=[]
    for symbol,asset_class in registrations:
        for timeframe in ALL_TIMEFRAMES:
            key=(symbol,timeframe)
            lane_enabled=(
                timeframe in required_timeframes(asset_class)
                if enabled is None else timeframe == "D1" or key in enabled
            )
            required=lane_enabled
            commissioned=key in commissioned_lanes
            evidence_count=int(counts.get(key) or 0)
            if not lane_enabled:
                state="Not Enabled"
            elif not commissioned:
                state="Not Commissioned"
            elif evidence_count == 0:
                state=states.get(key,"Behind")
                if state not in {"Behind","Unavailable"}:
                    state="Behind"
            else:
                state=states.get(key,"Unavailable")
                if state not in {"Current","Behind","Queued","Downloading","Unavailable"}:
                    state="Unavailable"
            result.append({
                "id":f"{symbol}:{timeframe}",
                "symbol":symbol,
                "asset_class":asset_class,
                "timeframe":timeframe,
                "required":required,
                "enabled":lane_enabled,
                "non_blocking":not lane_enabled,
                "commissioned":commissioned,
                "operational":key in operational,
                "missing_commission":required and not commissioned,
                "commissioning_state":(
                    "NOT_ENABLED" if not lane_enabled else
                    "COMMISSIONED" if commissioned else "MISSING_COMMISSION"
                ),
                "operational_state":state,
                "evidence_count":evidence_count,
            })
    return result
