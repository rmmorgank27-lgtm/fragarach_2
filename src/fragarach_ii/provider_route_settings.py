"""Operator-owned reviewed provider-route and proxy-calendar settings.

Routes here are explicit operator decisions.  They never infer that two market
representations are identical: an alias or equivalent representation must be
named, given a D1 calendar, and marked reviewed before the scheduler sees it.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path


CONTRACT = "fragarach_ii.provider_route_settings.v1"
DEFAULT_PATH = Path("~/Library/Application Support/Fragarach II/provider-route-settings.json").expanduser()
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "providers" / "acquisition_orchestrator.v1.json"
DIRECT_MAPPING_CLASSES = {
    "EXACT_REPRESENTATION", "APPROVED_PROVIDER_ALIAS", "APPROVED_EQUIVALENT_REPRESENTATION",
}


def settings_path(path: str | Path | None = None) -> Path:
    return Path(path).expanduser() if path else DEFAULT_PATH


def load_route_overrides(path: str | Path | None = None) -> list[dict[str, object]]:
    try:
        payload = json.loads(settings_path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    routes = payload.get("routes") if payload.get("contract") == CONTRACT else None
    return [dict(route) for route in routes] if isinstance(routes, list) and all(isinstance(route, dict) for route in routes) else []


def _route_key(route: dict[str, object]) -> tuple[str, str, tuple[str, ...]]:
    return (
        str(route.get("provider") or "").upper(),
        str(route.get("asset") or route.get("canonical_symbol") or "").upper(),
        tuple(sorted(str(item).upper() for item in route.get("timeframes", []) if item)),
    )


def merged_provider_mappings(provider: str, base: list[object]) -> list[dict[str, object]]:
    """Overlay user routes on shipped reviewed routes without changing others."""

    overrides = [route for route in load_route_overrides() if str(route.get("provider") or "").upper() == provider.upper()]
    override_keys = {_route_key(route) for route in overrides}
    result = [dict(route) for route in base if isinstance(route, dict) and _route_key(route) not in override_keys]
    return [*result, *overrides]


def _configured_routes() -> list[dict[str, object]]:
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    routes: list[dict[str, object]] = []
    for profile in payload.get("providers", []):
        if isinstance(profile, dict):
            provider = str(profile.get("provider") or "").upper()
            routes.extend(merged_provider_mappings(provider, list(profile.get("mappings") or [])))
    return routes


def configured_calendar_for_symbol(symbol: str) -> str | None:
    canonical = symbol.strip().upper()
    candidates = [
        route for route in _configured_routes()
        if str(route.get("asset") or route.get("canonical_symbol") or "").upper() == canonical
        and "D1" in {str(value).upper() for value in route.get("timeframes", [])}
        and str(route.get("mapping_class") or "").upper() in DIRECT_MAPPING_CLASSES
    ]
    if not candidates:
        return None
    calendar = candidates[-1].get("calendar_id")
    return str(calendar) if calendar else None


def update_provider_route(
    *, provider: str, asset: str, provider_symbol: str, timeframe: str,
    mapping_class: str, calendar_id: str, path: str | Path | None = None,
) -> dict[str, object]:
    selected_provider, canonical = provider.strip().upper(), asset.strip().upper()
    selected_symbol, lane = provider_symbol.strip(), timeframe.strip().upper()
    selected_class, selected_calendar = mapping_class.strip().upper(), calendar_id.strip().upper()
    if not selected_provider or not canonical or not selected_symbol:
        raise ValueError("provider, asset, and provider symbol are required")
    if lane != "D1":
        raise ValueError("operator-configurable proxy routes are D1-only")
    if selected_class not in DIRECT_MAPPING_CLASSES:
        raise ValueError("mapping class must be exact, approved alias, or approved equivalent")
    if not selected_calendar:
        raise ValueError("an approved D1 calendar is required")
    # Validate the calendar name against the same reviewed registry used by D1 validation.
    from .calendars import CalendarRegistry, ConfigurationError
    try:
        CalendarRegistry(load_symbol_assignments=False).calendar_by_id(selected_calendar)
    except ConfigurationError as error:
        raise ValueError(f"unknown approved D1 calendar: {selected_calendar}") from error
    route = {
        "provider": selected_provider, "asset": canonical, "symbol": selected_symbol,
        "timeframes": [lane], "mapping_class": selected_class,
        "conversion_policy": "NO_CONVERSION", "calendar_id": selected_calendar,
        "reviewed_status": "REVIEWED", "authority_source": "OPERATOR_CONFIGURED_PROVIDER_ROUTE",
    }
    target = settings_path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = target.with_suffix(f"{target.suffix}.lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            routes = load_route_overrides(target)
            key = _route_key(route)
            routes = [item for item in routes if _route_key(item) != key]
            routes.append(route)
            payload = {"contract": CONTRACT, "routes": routes}
            descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(payload, stream, sort_keys=True, separators=(",", ":")); stream.write("\n")
                    stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return {"contract": CONTRACT, **route}
