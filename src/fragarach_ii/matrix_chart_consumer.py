"""Bounded, read-only price projection exclusively for Echo Matrix charts.

The existing full-history and range consumers deliberately remain unchanged.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from .external_consumer_service import (
    ExternalConsumerServiceError, _registered_symbol, canonical_database_path,
)
from .freshness import authority_revision_for_lane
from .publication_service import lane_publication_state
from .storage import open_read_only
from .truth_engine import truth_state_for_lane

CONTRACT = "fragarach_ii.echo_matrix_chart.v1"
CONSUMER = "com.raymorgan.echomatrix"
BAR_LIMITS = {"M5": 60_000, "M30": 10_000}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _stamp(value: int) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")


def get_matrix_chart_context(
    symbol: str, timeframe: str, *, consumer: str, days: int = 35,
    descriptor_only: bool = False, database_path: str | Path | None = None,
) -> dict:
    """Return governed prices without the unrelated market-activity window join.

    Authority is calculated by the existing owner engine. Its revision brackets
    the transactional price read, so a concurrent correction cannot mix evidence.
    A caller may retry REVISION_CHANGED within its overall foreground budget.
    """
    if consumer != CONSUMER:
        raise ExternalConsumerServiceError("CONSUMER_NOT_PERMITTED", consumer)
    symbol, timeframe = symbol.strip().upper(), timeframe.strip().upper()
    if timeframe not in BAR_LIMITS or not symbol:
        raise ExternalConsumerServiceError("INVALID_MATRIX_CHART_REQUEST", f"{symbol}:{timeframe}")
    days = min(204, max(35, int(days)))
    database = Path(database_path) if database_path is not None else canonical_database_path()
    checked_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    started = time.monotonic()

    def unavailable(reason: str, descriptor: dict | None = None) -> dict:
        return {"contract": CONTRACT, "available": False, "reason": reason,
                "symbol": symbol, "timeframe": timeframe, "descriptor": descriptor, "bars": []}

    connection = open_read_only(database)
    try:
        canonical = _registered_symbol(connection, symbol, timeframe)
    finally:
        connection.close()
    if canonical is None:
        return unavailable("NOT_REGISTERED")
    symbol = canonical
    if lane_publication_state(database, symbol, timeframe) != "PUBLISHED":
        return unavailable("PUBLICATION_PENDING")
    truth = truth_state_for_lane(database, symbol=symbol, timeframe=timeframe)
    if truth["authority_state"] == "RED":
        return unavailable("AUTHORITY_WITHDRAWN")
    revision = str(truth["authority_revision"])
    connection = open_read_only(database)
    try:
        connection.execute("BEGIN")
        connection.set_progress_handler(lambda: int(time.monotonic() - started > 3.5), 10_000)
        if authority_revision_for_lane(connection, symbol=symbol, timeframe=timeframe) != revision:
            return unavailable("REVISION_CHANGED")
        registration = connection.execute(
            "SELECT asset_class,calendar_id,calendar_version,provider_id,provider_contract,provider_symbol "
            "FROM instrument_registrations WHERE asset=? AND timeframe='D1'", (symbol,),
        ).fetchone()
        latest = connection.execute(
            "SELECT open_time_utc FROM bars WHERE asset=? AND timeframe=? ORDER BY open_time_utc DESC LIMIT 1",
            (symbol, timeframe),
        ).fetchone()
        first = connection.execute(
            "SELECT open_time_utc FROM bars WHERE asset=? AND timeframe=? ORDER BY open_time_utc LIMIT 1",
            (symbol, timeframe),
        ).fetchone()
        if not latest or not first:
            return unavailable("NO_HISTORY")
        descriptor = {
            "contract": CONTRACT, "symbol": symbol, "timeframe": timeframe,
            "publication_revision": revision, "publication_state": "PUBLISHED",
            "authority_state": truth["authority_state"], "truth_score": truth["truth_score"],
            "CAODT": truth["caodt"], "asset_class": registration[0],
            "calendar_id": registration[1], "calendar_version": registration[2],
            "provider": registration[3], "provider_contract": registration[4],
            "provider_symbol": registration[5], "latest_governed_closed_observation": _stamp(latest[0]),
            "earliest_available_observation": _stamp(first[0]), "validated_at": checked_at,
        }
        # Freshness can change without a price publication (for example a lane
        # becomes Red). Its owner-calculated band is part of cache admission.
        descriptor["cache_revision"] = _digest({k: v for k, v in descriptor.items() if k != "validated_at"})
        rows = [] if descriptor_only else connection.execute(
            "SELECT open_time_utc,open,high,low,close,volume FROM bars "
            "WHERE asset=? AND timeframe=? AND open_time_utc>=? "
            "ORDER BY open_time_utc DESC LIMIT ?",
            (symbol, timeframe, latest[0] - days * 86_400, BAR_LIMITS[timeframe]),
        ).fetchall()
    finally:
        connection.close()
    if lane_publication_state(database, symbol, timeframe) != "PUBLISHED":
        return unavailable("PUBLICATION_PENDING", descriptor)
    connection = open_read_only(database)
    try:
        if authority_revision_for_lane(connection, symbol=symbol, timeframe=timeframe) != revision:
            return unavailable("REVISION_CHANGED", descriptor)
    finally:
        connection.close()
    bars = [{"observation_time": _stamp(row[0]), "open": row[1], "high": row[2],
             "low": row[3], "close": row[4], "volume": row[5]} for row in reversed(rows)]
    return {"contract": CONTRACT, "available": True, "reason": "", "symbol": symbol,
            "timeframe": timeframe, "descriptor": descriptor, "bars": bars,
            "content_digest": _digest(bars) if not descriptor_only else None,
            "coverage_days": days, "query_seconds": time.monotonic() - started}
