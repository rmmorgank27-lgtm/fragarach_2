"""Bounded, read-only bootstrap snapshot for Gator's 30 x 30 x 30 bowl."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from .calendars import CalendarRegistry
from .calendars.sessions import session_classification
from .crypto_intraday_quality import assess_crypto_intraday_rows
from .lane_commissioning import resolved_calendar_id
from .market_history_service import _iso_utc, _roll_up_d1_rows
from .scheduler_integrity import _lifecycle_projection
from .storage import open_read_only
from .validation.intraday_profiles import is_expected_open, profile_for


CONTRACT = "fragarach.gator_bootstrap.v1"
PROFILE = "30x30x30"
TIMEFRAMES = ("MN1", "W1", "D1", "H1", "M5")
DIRECT_TIMEFRAMES = ("D1", "H1", "M5")


class GatorBootstrapError(RuntimeError):
    """The bounded bootstrap request cannot be served safely."""


class GatorBootstrapService:
    """Build one deterministic tail snapshot from one SQLite read transaction."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    def build(self, *, bar_capacity: int = 270) -> dict[str, object]:
        if (
            isinstance(bar_capacity, bool)
            or not isinstance(bar_capacity, int)
            or bar_capacity < 1
            or bar_capacity > 2_000
        ):
            raise GatorBootstrapError("bar capacity must be between 1 and 2000")

        generated_at = datetime.now(UTC).replace(microsecond=0)
        observed_epoch = int(generated_at.timestamp())
        connection = open_read_only(self.database_path)
        try:
            connection.execute("BEGIN")
            registrations = connection.execute(
                """
                SELECT asset,asset_class,instrument_type,registration_status,
                       registered_at_utc,calendar_id,calendar_version,exchange_name,
                       representation_type
                FROM instrument_registrations
                WHERE timeframe='D1'
                ORDER BY asset
                """
            ).fetchall()
            evidence_lanes = connection.execute(
                """
                SELECT asset,timeframe
                FROM evidence_lanes
                WHERE timeframe IN ('D1','H1','M5')
                ORDER BY asset,timeframe
                """
            ).fetchall()
            events = connection.execute(
                """
                SELECT authority_event_id,supersedes_event_id,recorded_at_utc,
                       canonical_payload
                FROM authority_events
                ORDER BY recorded_at_utc,authority_event_id
                """
            ).fetchall()
            lifecycle = _lifecycle_projection(events)
            active = {
                str(row[0])
                for row in registrations
                if _is_active_registration(row, lifecycle)
            }
            registered_by_symbol = {str(row[0]): row for row in registrations}
            crypto_symbols = {
                str(row[0]) for row in registrations
                if str(row[8]) == "CRYPTO_SPOT_PAIR"
            }
            latest_routes = _latest_route_details(connection)

            lanes: list[dict[str, object]] = []
            direct_keys = [
                (str(asset), str(timeframe))
                for asset, timeframe in evidence_lanes
                if str(asset) in active
                and _is_active_lane(str(asset), str(timeframe), lifecycle)
            ]
            for symbol, timeframe in direct_keys:
                rows = _direct_tail(
                    connection,
                    symbol=symbol,
                    timeframe=timeframe,
                    bar_capacity=bar_capacity,
                    observed_epoch=observed_epoch,
                )
                if not rows:
                    lanes.append(_unavailable_lane(symbol, timeframe, "NO_MARKET_HISTORY"))
                    continue
                quality = None
                if symbol in crypto_symbols and timeframe in {"H1", "M5"}:
                    route = latest_routes.get((symbol, timeframe), {})
                    quality = assess_crypto_intraday_rows(
                        asset=symbol,
                        timeframe=timeframe,
                        rows=rows[-30:],
                        provider=str(route.get("provider") or ""),
                        provider_symbol=str(route.get("provider_symbol") or ""),
                        ingest_run_id=route.get("ingest_run_id"),
                        requested_window=30,
                    )
                if quality and quality["status"] in {"UNUSABLE", "INSUFFICIENT"}:
                    reason = ",".join(quality["reason_codes"]) or "INSUFFICIENT_PRICE_EVIDENCE"
                    lanes.append(_unavailable_lane(
                        symbol, timeframe, f"CRYPTO_INTRADAY_DATA_QUALITY:{reason}",
                    ))
                    continue
                warnings = []
                if quality and quality["status"] != "USABLE":
                    warnings.extend(
                        f"CRYPTO_INTRADAY_DATA_QUALITY:{reason}"
                        for reason in quality["reason_codes"]
                    )
                lanes.append(_available_lane(symbol, timeframe, rows, warnings=warnings))

            calendar_registry = CalendarRegistry(load_symbol_assignments=False)
            d1_symbols = {
                symbol for symbol, timeframe in direct_keys if timeframe == "D1"
            }
            for symbol in sorted(d1_symbols):
                registration = registered_by_symbol[symbol]
                d1_rows = connection.execute(
                    """
                    SELECT open_time_utc,open,high,low,close,volume
                    FROM bars
                    WHERE asset=? AND timeframe='D1' AND open_time_utc<=?
                    ORDER BY open_time_utc
                    """,
                    (symbol, observed_epoch),
                ).fetchall()
                for timeframe in ("W1", "MN1"):
                    lanes.append(
                        _derived_lane(
                            symbol=symbol,
                            timeframe=timeframe,
                            rows=d1_rows,
                            registration=registration,
                            calendar_registry=calendar_registry,
                            bar_capacity=bar_capacity,
                        )
                    )
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

        lanes.sort(key=lambda lane: (lane["symbol"], TIMEFRAMES.index(lane["timeframe"])))
        catalogue_revision = _catalogue_revision(registrations, active, evidence_lanes)
        symbols = _symbols(
            registrations, active, lanes,
            observed_at=generated_at, calendar_registry=calendar_registry,
        )
        revision_facts = {
            "catalogue_revision": catalogue_revision,
            "bar_capacity": bar_capacity,
            "lanes": [
                {
                    "symbol": lane["symbol"],
                    "timeframe": lane["timeframe"],
                    "status": lane["Status"],
                    "CAODT": lane["CAODT"],
                    "lane_fingerprint": lane["lane_fingerprint"],
                }
                for lane in lanes
            ],
        }
        bundle_revision = "sha256:" + hashlib.sha256(
            _canonical_json(revision_facts)
        ).hexdigest()
        unavailable = sum(1 for lane in lanes if lane["Status"] != "AVAILABLE")
        return {
            "contract": CONTRACT,
            "profile": PROFILE,
            "status": "AVAILABLE_WITH_WARNINGS" if unavailable else "AVAILABLE",
            "generated_at": generated_at.isoformat(),
            "catalogue_revision": catalogue_revision,
            "bundle_revision": bundle_revision,
            "bar_capacity": bar_capacity,
            "symbols": symbols,
            "lanes": lanes,
            "warnings": [f"{unavailable}_LANES_UNAVAILABLE"] if unavailable else [],
        }


def _is_active_registration(row, lifecycle: dict[tuple[str, str | None], dict]) -> bool:
    symbol = str(row[0])
    registration_status = str(row[3])
    leaf = lifecycle.get((symbol, "D1")) or lifecycle.get((symbol, None)) or {}
    state = str(leaf.get("lifecycle_state") or "ACTIVE")
    retired = state.startswith(("RETIRED", "QUARANTINED")) or state == "PERMANENTLY_REMOVED"
    return registration_status.startswith("REGISTERED_") and not retired


def _is_active_lane(
    symbol: str, timeframe: str,
    lifecycle: dict[tuple[str, str | None], dict],
) -> bool:
    leaf = lifecycle.get((symbol, timeframe)) or lifecycle.get((symbol, None)) or {}
    state = str(leaf.get("lifecycle_state") or "ACTIVE")
    return not (
        state.startswith(("RETIRED", "QUARANTINED"))
        or state == "PERMANENTLY_REMOVED"
    )


def _direct_tail(
    connection,
    *,
    symbol: str,
    timeframe: str,
    bar_capacity: int,
    observed_epoch: int,
):
    completion = (
        "open_time_utc<=?" if timeframe == "D1"
        else "close_time_utc IS NOT NULL AND close_time_utc<=?"
    )
    rows = connection.execute(
        f"""
        SELECT open_time_utc,open,high,low,close,volume,close_time_utc
        FROM bars
        WHERE asset=? AND timeframe=? AND {completion}
        ORDER BY open_time_utc DESC
        LIMIT ?
        """,
        (symbol, timeframe, observed_epoch, bar_capacity),
    ).fetchall()
    return list(reversed(rows))


def _latest_route_details(connection) -> dict[tuple[str, str], dict[str, object]]:
    rows = connection.execute(
        """SELECT s.asset,s.timeframe,s.last_ingest_run_id,i.detail
             FROM lane_state s
             LEFT JOIN ingest_runs i ON i.ingest_run_id=s.last_ingest_run_id
            WHERE s.timeframe IN ('H1','M5')"""
    ).fetchall()
    details: dict[tuple[str, str], dict[str, object]] = {}
    for asset, timeframe, ingest_run_id, detail_text in rows:
        try:
            detail = json.loads(detail_text) if detail_text else {}
        except (TypeError, json.JSONDecodeError):
            detail = {}
        details[(str(asset), str(timeframe))] = {
            "provider": detail.get("provider"),
            "provider_symbol": detail.get("provider_symbol"),
            "ingest_run_id": ingest_run_id,
        }
    return details


def _derived_lane(
    *, symbol: str, timeframe: str, rows, registration,
    calendar_registry: CalendarRegistry, bar_capacity: int,
) -> dict[str, object]:
    if not rows:
        return _unavailable_lane(symbol, timeframe, "NO_D1_MARKET_HISTORY")
    try:
        calendar_id = resolved_calendar_id(
            asset_class=str(registration[1]),
            calendar_id=str(registration[5]),
            exchange_name=str(registration[7]) if registration[7] else None,
            canonical_symbol=symbol,
        )
        if calendar_id is None:
            raise GatorBootstrapError("CALENDAR_AUTHORITY_UNAVAILABLE")
        calendar = calendar_registry.calendar_by_id(calendar_id)
        if calendar.calendar_version != int(registration[6]):
            raise GatorBootstrapError("CALENDAR_AUTHORITY_VERSION_MISMATCH")
        first_owner = datetime.fromtimestamp(int(rows[0][0]), UTC).date()
        caodt_owner = datetime.fromtimestamp(int(rows[-1][0]), UTC).date()
        constructed, incomplete = _roll_up_d1_rows(
            rows,
            timeframe=timeframe,
            calendar=calendar,
            caodt_owner=caodt_owner,
            first_owner=first_owner,
            last_owner=caodt_owner,
        )
        tail = [(*row, None, None) for row in constructed[-bar_capacity:]]
        warnings = ["INCOMPLETE_DERIVED_PERIOD_EXCLUDED"] if incomplete else []
        return _available_lane(symbol, timeframe, tail, warnings=warnings)
    except Exception as error:
        return _unavailable_lane(symbol, timeframe, str(error))


def _available_lane(
    symbol: str, timeframe: str, rows, *, warnings: list[str] | None = None,
) -> dict[str, object]:
    bars = [
        {
            "timestamp": _iso_utc(int(row[0])),
            "open": str(row[1]),
            "high": str(row[2]),
            "low": str(row[3]),
            "close": str(row[4]),
            "volume": None if row[5] is None else str(row[5]),
        }
        for row in rows
    ]
    if timeframe == "D1" or rows[-1][6] is None:
        caodt = bars[-1]["timestamp"]
    else:
        caodt = _iso_utc(int(rows[-1][6]))
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "Status": "AVAILABLE",
        "Warnings": warnings or [],
        "CAODT": caodt,
        "bar_count": len(bars),
        "lane_fingerprint": _lane_fingerprint(bars),
        "OHLC": bars,
    }


def _unavailable_lane(symbol: str, timeframe: str, reason: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "Status": "UNAVAILABLE",
        "Warnings": [reason],
        "CAODT": None,
        "bar_count": 0,
        "lane_fingerprint": None,
        "OHLC": [],
    }


def _lane_fingerprint(bars: list[dict[str, object]]) -> str:
    canonical = "\n".join(
        "|".join(
            str(bar.get(key) if bar.get(key) is not None else "")
            for key in ("timestamp", "open", "high", "low", "close", "volume")
        )
        for bar in bars
    )
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _catalogue_revision(registrations, active: set[str], evidence_lanes) -> str:
    facts = {
        "registrations": [
            [str(value) if value is not None else None for value in row]
            for row in registrations
        ],
        "active": sorted(active),
        "evidence_lanes": [list(map(str, row)) for row in evidence_lanes],
    }
    return "sha256:" + hashlib.sha256(_canonical_json(facts)).hexdigest()


def _symbols(
    registrations, active: set[str], lanes, *, observed_at: datetime,
    calendar_registry: CalendarRegistry,
) -> list[dict[str, object]]:
    by_symbol: dict[str, list[dict[str, object]]] = {}
    for lane in lanes:
        if lane["Status"] != "AVAILABLE":
            continue
        bars = lane["OHLC"]
        by_symbol.setdefault(str(lane["symbol"]), []).append(
            {
                "timeframe": lane["timeframe"],
                "governed": True,
                "bar_count": lane["bar_count"],
                "first_bar": bars[0]["timestamp"],
                "last_bar": bars[-1]["timestamp"],
            }
        )
    output = []
    for row in registrations:
        symbol = str(row[0])
        histories = sorted(
            by_symbol.get(symbol, []), key=lambda item: TIMEFRAMES.index(item["timeframe"])
        )
        output.append(
            {
                "symbol": symbol,
                "market": _market(str(row[1])),
                "asset_class": str(row[1]),
                "availability": "AVAILABLE" if symbol in active and histories else "UNAVAILABLE",
                "market_session": _market_session(
                    row, observed_at=observed_at,
                    calendar_registry=calendar_registry,
                ),
                "histories": histories,
            }
        )
    return output


_CASH_SESSION_OPENS = {
    "US_EQUITIES": time(9, 30),
    "AUSTRALIAN_EQUITIES": time(10, 0),
    "UK_EQUITIES": time(8, 0),
    "GERMAN_EQUITIES": time(9, 0),
}


def _market_session(
    registration, *, observed_at: datetime,
    calendar_registry: CalendarRegistry,
) -> dict[str, object]:
    """Publish Fragarach's current session decision with each symbol.

    Gator consumes this decision verbatim. Unknown calendars fail closed and
    therefore cannot be presented as open-market evidence.
    """

    symbol = str(registration[0])
    asset_class = str(registration[1]).upper()
    observed = observed_at.astimezone(UTC)
    base = {"as_of": observed.isoformat()}
    if asset_class in {"CRYPTO", "FX", "METALS", "ENERGY"}:
        try:
            profile = profile_for(asset_class, "M5")
            epoch = int(observed.timestamp())
            interval_open = epoch - (epoch % profile.seconds)
            market_open = is_expected_open(interval_open, profile)
            return {
                **base,
                "state": "OPEN" if market_open else "CLOSED",
                "is_open": market_open,
                "calendar_id": profile.calendar_id,
                "timezone": profile.timezone,
                "reason": "CONTINUOUS_SESSION" if profile.continuous else "APPROVED_24X5_SESSION",
            }
        except ValueError as error:
            return {**base, "state": "UNKNOWN", "is_open": None, "reason": str(error)}

    calendar_id = resolved_calendar_id(
        asset_class=asset_class,
        calendar_id=str(registration[5] or ""),
        exchange_name=str(registration[7]) if registration[7] else None,
        canonical_symbol=symbol,
    )
    if calendar_id is None and asset_class == "INDICES" and symbol in {"DJI", "QQQ", "SPY"}:
        calendar_id = "US_EQUITIES_D1_V1"
    session_open = _CASH_SESSION_OPENS.get(asset_class)
    if asset_class == "INDICES" and calendar_id == "US_EQUITIES_D1_V1":
        session_open = _CASH_SESSION_OPENS["US_EQUITIES"]
    if calendar_id is None or session_open is None:
        return {
            **base, "state": "UNKNOWN", "is_open": None,
            "reason": "MARKET_SESSION_AUTHORITY_UNAVAILABLE",
        }
    try:
        definition = calendar_registry.calendar_by_id(calendar_id)
        local = observed.astimezone(ZoneInfo(definition.session_timezone))
        expected, _ = session_classification(local.date(), definition)
        market_open = (
            expected and session_open <= local.time().replace(tzinfo=None)
            < definition.session_close_local
        )
        return {
            **base,
            "state": "OPEN" if market_open else "CLOSED",
            "is_open": market_open,
            "calendar_id": calendar_id,
            "timezone": definition.session_timezone,
            "reason": "APPROVED_REGULAR_SESSION",
        }
    except Exception as error:
        return {**base, "state": "UNKNOWN", "is_open": None, "reason": str(error)}


def _market(asset_class: str) -> str:
    return {
        "CRYPTO": "Crypto",
        "FX": "Forex",
        "US_EQUITIES": "Equities",
        "AUSTRALIAN_EQUITIES": "Equities",
        "UK_EQUITIES": "Equities",
        "GERMAN_EQUITIES": "Equities",
        "METALS": "Metals",
        "ENERGY": "Energy",
        "INDICES": "Indices",
    }.get(asset_class, asset_class)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
