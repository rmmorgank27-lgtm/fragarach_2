"""Immutable capability catalogues published by the Windows MT5 MCP process."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mt5_bridge_queue import MT5BridgeQueueError, _atomic_json, checksum, queue_root
from .storage import open_read_only


CATALOGUE_CONTRACT = "fragarach.mt5_symbol_catalogue.v0.1"


def catalogue_paths(support: str | Path, node_id: str | None = None) -> dict[str, Path]:
    root = queue_root(support, node_id) / "catalogue"
    return {"root": root, "current": root / "current.json", "history": root / "history"}


def _validate_catalogue(value: dict[str, Any]) -> None:
    if value.get("contract") != CATALOGUE_CONTRACT:
        raise MT5BridgeQueueError("CATALOGUE_CONTRACT_MISMATCH")
    body = dict(value)
    declared = body.pop("catalog_sha256", None)
    if not isinstance(declared, str) or declared != checksum(body):
        raise MT5BridgeQueueError("CATALOGUE_CHECKSUM_MISMATCH")
    if value.get("account_profile") != "STANDARD_NON_TRADING_DATA":
        raise MT5BridgeQueueError("INELIGIBLE_TERMINAL_PROFILE")
    symbols = value.get("symbols")
    if not isinstance(symbols, list) or value.get("symbol_count") != len(symbols):
        raise MT5BridgeQueueError("CATALOGUE_SYMBOL_COUNT_MISMATCH")
    provider_symbols: set[str] = set()
    authorised = 0
    for entry in symbols:
        if not isinstance(entry, dict) or not isinstance(entry.get("provider_symbol"), str):
            raise MT5BridgeQueueError("CATALOGUE_SYMBOL_INVALID")
        provider_symbol = entry["provider_symbol"]
        if not provider_symbol or provider_symbol in provider_symbols:
            raise MT5BridgeQueueError("CATALOGUE_SYMBOL_DUPLICATE")
        provider_symbols.add(provider_symbol)
        if entry.get("bridge_authorized") is True:
            authorised += 1
            if not isinstance(entry.get("canonical_symbol"), str):
                raise MT5BridgeQueueError("CATALOGUE_AUTHORISED_MAPPING_INVALID")
            if not isinstance(entry.get("bridge_native_timeframes"), list):
                raise MT5BridgeQueueError("CATALOGUE_TIMEFRAMES_INVALID")
    if value.get("bridge_authorized_count") != authorised:
        raise MT5BridgeQueueError("CATALOGUE_AUTHORISED_COUNT_MISMATCH")


def accept_catalogue(
    support: str | Path, value: dict[str, Any], *, node_id: str | None = None,
) -> dict[str, str]:
    """Validate and retain both the immutable receipt and current projection."""

    if not isinstance(value, dict):
        raise MT5BridgeQueueError("CATALOGUE_NOT_OBJECT")
    _validate_catalogue(value)
    paths = catalogue_paths(support, node_id)
    digest = str(value["catalog_sha256"])
    historical = paths["history"] / f"{digest}.json"
    if historical.is_file():
        try:
            existing = json.loads(historical.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MT5BridgeQueueError("CATALOGUE_HISTORY_UNREADABLE") from error
        if existing != value:
            raise MT5BridgeQueueError("CATALOGUE_CHECKSUM_COLLISION")
    else:
        _atomic_json(historical, value)
    _atomic_json(paths["current"], value)
    return {"status": "ACCEPTED", "catalog_sha256": digest}


def current_catalogue(
    support: str | Path, node_id: str | None = None,
) -> dict[str, Any] | None:
    path = catalogue_paths(support, node_id)["current"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _registered_markets(database: str | Path | None) -> dict[str, str]:
    if database is None:
        return {}
    try:
        with open_read_only(database) as connection:
            rows = connection.execute(
                "SELECT asset,asset_class FROM instrument_registrations WHERE timeframe='D1'"
            ).fetchall()
    except Exception:
        # No database authority means that only the catalogue's existing,
        # self-described admissions can be used.  It is not safe to infer a
        # market class from a terminal symbol.
        return {}
    return {str(row[0]).upper(): str(row[1]).upper() for row in rows}


def authorised_routes(
    support: str | Path, *, database: str | Path | None = None,
) -> dict[tuple[str, str], dict[str, str]]:
    """Intersect each live terminal catalogue with the governed estate routes."""

    from .index_cfd_mt5 import _authority
    from .mt5_route_manifest import active_bridge_nodes, approved_route
    authority = _authority()
    symbol_timeframes = authority["bridge"].get("native_timeframes_by_symbol", {})
    lanes: dict[tuple[str, str], dict[str, str]] = {}
    catalogues: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for node in active_bridge_nodes():
        namespace_node = None if node.get("queue_namespace") == "default" else str(node["node_id"])
        catalogue = current_catalogue(support, namespace_node)
        if catalogue is not None and catalogue.get("source_route") == node.get("source_route"):
            catalogues.append((node, catalogue))
    for node, catalogue in catalogues:
        for entry in catalogue.get("symbols", []):
            if not isinstance(entry, dict) or entry.get("bridge_authorized") is not True:
                continue
            canonical = str(entry.get("canonical_symbol") or "").upper()
            provider = str(entry.get("provider_symbol") or "")
            for timeframe in entry.get("bridge_native_timeframes") or []:
                native_timeframe = str(timeframe).upper()
                approved = symbol_timeframes.get(canonical, authority["timeframes"])
                if canonical in authority["symbols"] and native_timeframe in approved:
                    lanes[(canonical, native_timeframe)] = {
                        "provider_symbol": provider,
                        "node_id": str(node["node_id"]),
                        "queue_namespace": str(node["queue_namespace"]),
                        "source_route": str(node["source_route"]),
                    }
    # The Windows catalogue is capability evidence, not an authority file.
    # The manifest gives the operator-approved canonical aliases and provider
    # order, while the live registration supplies the market class. All three
    # must agree before the Scheduler may treat the route as primary.
    registered = _registered_markets(database)
    for node, catalogue in catalogues:
        available = {
            str(entry.get("provider_symbol") or "")
            for entry in catalogue.get("symbols", []) if isinstance(entry, dict)
        }
        for canonical, market in registered.items():
            for timeframe in ("D1", "H1", "M30", "M5"):
                route = approved_route(canonical, market, timeframe)
                if (
                    route is not None
                    and route["node_id"] == node["node_id"]
                    and route["source_route"] == catalogue.get("source_route")
                    and route["provider_symbol"] in available
                ):
                    lanes[(canonical, timeframe)] = {
                        **route,
                        "queue_namespace": str(node["queue_namespace"]),
                    }
    return lanes


def authorised_lanes(
    support: str | Path, *, database: str | Path | None = None,
) -> dict[tuple[str, str], str]:
    return {
        lane: str(route["provider_symbol"])
        for lane, route in authorised_routes(support, database=database).items()
    }


__all__ = [
    "CATALOGUE_CONTRACT", "accept_catalogue", "authorised_lanes", "authorised_routes",
    "catalogue_paths", "current_catalogue",
]
