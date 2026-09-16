"""Reviewed MT5 route authority, deliberately separate from terminal capability.

An MT5 terminal catalogue proves a symbol is available at a broker.  It does
not prove that its broker representation is the governed Fragarach instrument.
This manifest is the small, inspectable gate between those two facts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT = "fragarach_ii.mt5_route_manifest.v1"
MANIFEST_PATH = Path(__file__).resolve().parents[2] / "config" / "providers" / "mt5_route_manifest.v1.json"
PRIMARY_TIMEFRAMES = frozenset({"H1", "M30", "M5"})
DAILY_TIMEFRAMES = frozenset({"D1"})
REVIEWABLE_TIMEFRAMES = PRIMARY_TIMEFRAMES | DAILY_TIMEFRAMES
_FX_RAW_SUFFIX = ".r"


class MT5RouteManifestError(ValueError):
    """A shipped routing manifest is malformed and cannot be used."""


def load_manifest(path: str | Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_UNREADABLE") from error
    if not isinstance(value, dict) or value.get("contract") != CONTRACT:
        raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_CONTRACT_MISMATCH")
    reviewed = value.get("reviewed_mt5_primary_lanes")
    if not isinstance(reviewed, list):
        raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_ROUTES_INVALID")
    seen: set[tuple[str, str]] = set()
    for route in reviewed:
        if not isinstance(route, dict):
            raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_ROUTE_INVALID")
        symbol = str(route.get("canonical_symbol") or "").upper()
        provider_symbol = str(route.get("provider_symbol") or "")
        timeframes = route.get("timeframes")
        if not symbol or not provider_symbol or not isinstance(timeframes, list):
            raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_ROUTE_INVALID")
        for raw_timeframe in timeframes:
            timeframe = str(raw_timeframe).upper()
            if timeframe not in REVIEWABLE_TIMEFRAMES or (symbol, timeframe) in seen:
                raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_ROUTE_INVALID")
            seen.add((symbol, timeframe))
    aliases = value.get("approved_aliases", {})
    if not isinstance(aliases, dict) or any(
        not isinstance(symbol, str) or not isinstance(provider, str)
        for symbol, provider in aliases.items()
    ):
        raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_ALIASES_INVALID")
    policies = value.get("class_policy")
    if not isinstance(policies, list):
        raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_CLASS_POLICY_INVALID")
    policy_keys: set[tuple[str, str]] = set()
    for policy in policies:
        if not isinstance(policy, dict):
            raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_CLASS_POLICY_INVALID")
        classes = policy.get("asset_classes")
        timeframes = policy.get("timeframes")
        order = policy.get("provider_order")
        if (
            not isinstance(classes, list)
            or not isinstance(timeframes, list)
            or not isinstance(order, list)
            or not order
            or len(order) != len(set(order))
        ):
            raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_CLASS_POLICY_INVALID")
        for asset_class in classes:
            for timeframe in timeframes:
                key = (str(asset_class).upper(), str(timeframe).upper())
                if key in policy_keys:
                    raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_CLASS_POLICY_OVERLAP")
                policy_keys.add(key)
    nodes = value.get("nodes")
    if not isinstance(nodes, list):
        raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_NODES_INVALID")
    active_ids: set[str] = set()
    active_clients: set[str] = set()
    active_classes: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("node_id"), str):
            raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_NODE_INVALID")
        if node.get("activation") != "ACTIVE":
            continue
        node_id = str(node["node_id"])
        client_id = str(node.get("transport_client_id") or "")
        source_route = str(node.get("source_route") or "")
        namespace = str(node.get("queue_namespace") or "")
        classes = node.get("asset_classes")
        if (
            not client_id or not source_route or not namespace
            or not isinstance(classes, list) or not classes
            or node_id in active_ids or client_id in active_clients
        ):
            raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_NODE_INVALID")
        normalized_classes = {str(item).upper() for item in classes}
        if active_classes.intersection(normalized_classes):
            raise MT5RouteManifestError("MT5_ROUTE_MANIFEST_NODE_CLASS_OVERLAP")
        active_ids.add(node_id)
        active_clients.add(client_id)
        active_classes.update(normalized_classes)
    return value


def active_bridge_nodes(path: str | Path = MANIFEST_PATH) -> tuple[dict[str, Any], ...]:
    """Return the separately authenticated, active MT5 acquisition nodes."""

    return tuple(
        dict(node) for node in load_manifest(path).get("nodes", [])
        if isinstance(node, dict) and node.get("activation") == "ACTIVE"
    )


def bridge_node(node_id: str, path: str | Path = MANIFEST_PATH) -> dict[str, Any] | None:
    wanted = node_id.strip()
    return next((node for node in active_bridge_nodes(path) if node.get("node_id") == wanted), None)


def bridge_node_for_client(client_id: str) -> dict[str, Any] | None:
    wanted = client_id.strip()
    return next(
        (node for node in active_bridge_nodes() if node.get("transport_client_id") == wanted),
        None,
    )


def bridge_node_for_asset_class(asset_class: str) -> dict[str, Any] | None:
    market = asset_class.strip().upper()
    return next(
        (
            node for node in active_bridge_nodes()
            if market in {str(item).upper() for item in node.get("asset_classes", [])}
        ),
        None,
    )


def provider_order(asset_class: str, timeframe: str) -> tuple[str, ...]:
    """Return the one reviewed provider order for a market lane."""

    market = asset_class.strip().upper()
    lane = timeframe.strip().upper()
    for policy in load_manifest().get("class_policy", []):
        classes = {str(value).upper() for value in policy.get("asset_classes", [])}
        timeframes = {str(value).upper() for value in policy.get("timeframes", [])}
        if market in classes and lane in timeframes:
            return tuple(str(value).upper() for value in policy["provider_order"])
    return ()


def reviewed_primary_routes(path: str | Path = MANIFEST_PATH) -> dict[tuple[str, str], str]:
    """Map only approved canonical MT5-primary lanes to their broker symbols."""

    routes: dict[tuple[str, str], str] = {}
    for route in load_manifest(path)["reviewed_mt5_primary_lanes"]:
        symbol = str(route["canonical_symbol"]).upper()
        provider_symbol = str(route["provider_symbol"])
        for timeframe in route["timeframes"]:
            routes[(symbol, str(timeframe).upper())] = provider_symbol
    return routes


def approved_provider_symbol(symbol: str, asset_class: str) -> str | None:
    """Return the operator-approved broker representation, never a guess.

    The operator approved the raw-spread convention for the ordinary FX book.
    That still becomes usable only when the current terminal catalogue confirms
    the exact resulting name.  Metals, energy and broker index aliases remain
    an explicit small table because their terminal names do not derive safely
    from the Fragarach canonical symbols.
    """

    canonical = symbol.strip().upper()
    market = asset_class.strip().upper()
    manifest = load_manifest()
    aliases = {
        str(key).upper(): str(value)
        for key, value in manifest.get("approved_aliases", {}).items()
    }
    if canonical in aliases:
        return aliases[canonical]
    # Eightcap advertises its USD crypto CFDs using the same exact uppercase
    # symbol as Fragarach's registered crypto estate.  Exact equality is the
    # authority boundary: no USD/USDT or short-symbol aliases are inferred.
    if market == "CRYPTO" and canonical.endswith("USD"):
        return canonical
    if market == "FX" and len(canonical) == 6 and canonical.isalpha():
        return f"{canonical}{_FX_RAW_SUFFIX}"
    return None


def approved_route(
    symbol: str, asset_class: str, timeframe: str,
) -> dict[str, str] | None:
    """Describe a manifest-approved MT5 lane before terminal admission."""

    canonical = symbol.strip().upper()
    market = asset_class.strip().upper()
    lane = timeframe.strip().upper()
    provider_symbol = approved_provider_symbol(canonical, market)
    if provider_symbol is None or lane not in REVIEWABLE_TIMEFRAMES:
        return None
    node = bridge_node_for_asset_class(market)
    if node is None:
        return None
    return {
        "canonical_symbol": canonical,
        "provider_symbol": provider_symbol,
        "asset_class": market,
        "timeframe": lane,
        "mapping_class": "APPROVED_PROVIDER_ALIAS",
        "authority_source": "MT5_ROUTE_MANIFEST_V6_OPERATOR_APPROVED",
        "node_id": str(node["node_id"]),
        "source_route": str(node["source_route"]),
        "transport_client_id": str(node["transport_client_id"]),
    }


def is_mt5_primary_lane(
    symbol: str,
    timeframe: str,
    *,
    provider_symbol: str | None = None,
    asset_class: str | None = None,
) -> bool:
    """Return whether a lane is actually approved to be emitted to MT5 now."""

    canonical, lane = symbol.strip().upper(), timeframe.strip().upper()
    expected = reviewed_primary_routes().get((canonical, lane))
    if expected is not None:
        return provider_symbol is None or provider_symbol == expected
    if asset_class is not None:
        expected_symbol = approved_provider_symbol(canonical, asset_class)
        order = provider_order(asset_class, lane)
        return bool(
            expected_symbol
            and order
            and order[0] == "MT5_BRIDGE"
            and (provider_symbol is None or provider_symbol == expected_symbol)
        )
    if lane not in PRIMARY_TIMEFRAMES:
        return False
    # This deliberately recognises only the explicit raw-FX convention and
    # aliases in the manifest.  Terminal capability remains the final gate.
    raw_fx = len(canonical) == 6 and canonical.isalpha() and provider_symbol == f"{canonical}{_FX_RAW_SUFFIX}"
    aliases = {
        str(key).upper(): str(value)
        for key, value in load_manifest().get("approved_aliases", {}).items()
    }
    return raw_fx or aliases.get(canonical) == provider_symbol


__all__ = [
    "CONTRACT", "MANIFEST_PATH", "MT5RouteManifestError", "active_bridge_nodes",
    "approved_provider_symbol", "approved_route", "bridge_node", "bridge_node_for_asset_class",
    "bridge_node_for_client", "is_mt5_primary_lane", "load_manifest", "provider_order",
    "reviewed_primary_routes",
]
