"""Read-only history inventory; rolling periods count bar opening timestamps."""
from __future__ import annotations

import calendar as civil_calendar
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .market_history_service import (
    CalendarRegistry, MarketHistoryServiceError, _canonical_datetime, _iso_utc,
    _registration, _roll_up_d1_rows, _truth_warnings, market_policy,
    resolved_calendar_id,
)
from .calendars.sessions import session_classification
from .freshness import authority_revision_for_lane
from .synthetic_repository import default_repository_path
from .history_sessions import history_sessions, session_bar_counts
from .storage import open_read_only
from .truth_engine import TruthEngineError, truth_state_for_lane

TIMEFRAMES = ("MN1", "W1", "D1", "H1", "M30", "M15", "M5")


def _months_before(value: datetime, months: int) -> datetime:
    year, month0 = divmod(value.year * 12 + value.month - 1 - months, 12)
    month = month0 + 1
    return value.replace(year=year, month=month,
                         day=min(value.day, civil_calendar.monthrange(year, month)[1]))


def history_summary(database_path: str | Path, symbol: str, *,
                    at: datetime | None = None) -> dict[str, object]:
    """Count canonical history without exporting intraday OHLC or acquiring data.

    W1/MN1 use the existing calendar-complete D1 construction authority. Empty
    active lanes have zero bars; uncommissioned/unreadable lanes have null counts.
    Recent windows end at observation time, never at a stale lane's latest bar.
    """
    observed = at or datetime.now(UTC)
    if observed.tzinfo is None:
        raise ValueError("history observation time must include a timezone")
    observed = observed.astimezone(UTC)
    starts = [_months_before(observed, 12), _months_before(observed, 1),
              observed - timedelta(hours=24)]
    cutoffs = [value.timestamp() for value in starts]
    now_epoch = int(observed.timestamp())
    connection = open_read_only(database_path)
    try:
        registration = _registration(connection, symbol.strip().upper())
        if registration is None:
            raise MarketHistoryServiceError("NOT_REGISTERED", "Symbol is not registered")
        asset, asset_class, calendar_id, calendar_version, exchange = registration
        calendar = None
        d1_history_start_epoch = None
        try:
            resolved = resolved_calendar_id(
                asset_class=asset_class,
                calendar_id=calendar_id,
                exchange_name=exchange,
                canonical_symbol=asset,
            )
            if resolved is not None:
                calendar = CalendarRegistry(load_symbol_assignments=False).calendar_by_id(resolved)
                if calendar.calendar_version != calendar_version:
                    calendar = None
                else:
                    d1_history_start_epoch = int(
                        datetime.combine(calendar.effective_from, datetime.min.time(), UTC).timestamp()
                    )
        except (MarketHistoryServiceError, KeyError, ValueError):
            calendar = None
        sessions = history_sessions(registration, observed)
        lanes = {str(row[0]) for row in connection.execute(
            "SELECT timeframe FROM evidence_lanes WHERE asset=?", (asset,))}
        results: dict[str, dict] = {}
        d1_rows = []
        d1_caodt = None
        for timeframe in ("D1", "H1", "M30", "M5"):
            row = _empty(timeframe, "TIMEFRAME_NOT_ACTIVE")
            if timeframe not in lanes or market_policy(asset_class, timeframe) == "INTENTIONALLY_DEFERRED":
                results[timeframe] = row
                continue
            existence_sql = "SELECT 1 FROM bars WHERE asset=? AND timeframe=?"
            existence_parameters: list[object] = [asset, timeframe]
            if timeframe == "D1" and d1_history_start_epoch is not None:
                existence_sql += " AND open_time_utc>=?"
                existence_parameters.append(d1_history_start_epoch)
            if not connection.execute(existence_sql + " LIMIT 1", existence_parameters).fetchone():
                results[timeframe] = _empty(timeframe, "NO_HISTORY", count=0)
                results[timeframe].update(session_bar_counts(connection, symbol=asset, timeframe=timeframe,
                    sessions=sessions, observed_epoch=now_epoch))
                continue
            try:
                truth = truth_state_for_lane(database_path, symbol=asset, timeframe=timeframe, as_of=observed)
                caodt = _canonical_datetime(str(truth["caodt"]))
                upper = min(int(caodt.timestamp()), now_epoch)
                # D1 authority uses the owner-date open; intraday CAODT uses close.
                close_clause = "" if timeframe == "D1" else " AND close_time_utc<=?"
                parameters = [*cutoffs, asset, timeframe, upper]
                start_clause = ""
                if timeframe == "D1" and d1_history_start_epoch is not None:
                    start_clause = " AND open_time_utc>=?"
                    parameters.append(d1_history_start_epoch)
                if timeframe != "D1":
                    parameters.append(upper)
                stats = connection.execute(
                    "SELECT count(*),min(open_time_utc),max(open_time_utc),"
                    "coalesce(sum(open_time_utc>=?),0),coalesce(sum(open_time_utc>=?),0),"
                    "coalesce(sum(open_time_utc>=?),0) FROM bars "
                    "WHERE asset=? AND timeframe=? AND open_time_utc<=?" + start_clause + close_clause,
                    parameters,
                ).fetchone()
                warnings = _truth_warnings(truth)
                row = _counts(timeframe, stats, warnings)
                row.update(session_bar_counts(connection, symbol=asset, timeframe=timeframe,
                    sessions=sessions, observed_epoch=now_epoch, authority_cutoff=upper))
                if timeframe == "D1":
                    d1_caodt = datetime.fromtimestamp(upper, UTC).date()
                    d1_rows = connection.execute(
                        "SELECT open_time_utc,open,high,low,close FROM bars "
                        "WHERE asset=? AND timeframe='D1' AND open_time_utc<=?"
                        + (" AND open_time_utc>=?" if d1_history_start_epoch is not None else "")
                        + " ORDER BY open_time_utc",
                        (asset, upper)
                        if d1_history_start_epoch is None
                        else (asset, upper, d1_history_start_epoch),
                    ).fetchall()
            except (TruthEngineError, MarketHistoryServiceError) as error:
                row = _empty(timeframe, "UNAVAILABLE", warnings=[error.code])
            results[timeframe] = row

        for timeframe in ("W1", "MN1"):
            source = results["D1"]
            if not d1_rows or d1_caodt is None:
                results[timeframe] = _empty(timeframe, source["status"],
                    count=0 if source["total_bars"] == 0 else None, warnings=source["warnings"])
                continue
            try:
                if calendar is None:
                    resolved = resolved_calendar_id(asset_class=asset_class, calendar_id=calendar_id,
                                                   exchange_name=exchange, canonical_symbol=asset)
                    if resolved is None:
                        raise MarketHistoryServiceError("HISTORY_AUTHORITY_UNAVAILABLE", "Calendar unavailable")
                    calendar = CalendarRegistry(load_symbol_assignments=False).calendar_by_id(resolved)
                    if calendar.calendar_version != calendar_version:
                        raise MarketHistoryServiceError("HISTORY_AUTHORITY_UNAVAILABLE", "Calendar version mismatch")
                rolled, incomplete = _roll_up_d1_rows(
                    d1_rows, timeframe=timeframe, calendar=calendar, caodt_owner=d1_caodt,
                    first_owner=datetime.fromtimestamp(d1_rows[0][0], UTC).date(), last_owner=d1_caodt,
                )
                timestamps = [int(value[0]) for value in rolled]
                stats = [len(timestamps), min(timestamps) if timestamps else None,
                         max(timestamps) if timestamps else None,
                         *[sum(value >= cutoff for value in timestamps) for cutoff in cutoffs]]
                warnings = list(source["warnings"])
                if incomplete:
                    warnings.append("INCOMPLETE_DERIVED_PERIOD_EXCLUDED")
                results[timeframe] = _counts(timeframe, stats, warnings)
            except (MarketHistoryServiceError, KeyError, ValueError) as error:
                results[timeframe] = _empty(timeframe, "UNAVAILABLE", warnings=[str(error)])
        results["M15"] = _m15_summary(database_path, connection, asset, results["M5"], cutoffs, now_epoch, sessions)
        trading_days_held = 0 if results["D1"]["total_bars"] == 0 else None
        if calendar is not None and calendar.calendar_version == calendar_version and d1_rows:
            represented_dates = {datetime.fromtimestamp(row[0], UTC).date() for row in d1_rows}
            trading_days_held = sum(session_classification(day, calendar)[0] for day in represented_dates)
        for timeframe in ("H1", "M30", "M15", "M5"):
            # Informational only: do not classify a potential early close as a
            # detected gap or reduce any recorded bar/session count.
            if asset_class != "CRYPTO" and results[timeframe]["total_bars"] is not None:
                results[timeframe]["notes"] += [
                    "Holidays and shortened trading sessions may reduce intraday bar counts. "
                    "Early-close dates are not identified here; this is a possibility, not a confirmed cause of gaps. "
                    "A shortened session still counts as one trading day and one D1 bar when present."
                ]
        return {
            "sessions": sessions,
            "trading_days_held": trading_days_held,
            "contract": "fragarach_ii.history_summary.v1", "symbol": asset,
            "observed_at_utc": observed.isoformat(),
            "last_year_start_utc": starts[0].isoformat(),
            "last_month_start_utc": starts[1].isoformat(),
            "last_24_hours_start_utc": starts[2].isoformat(),
            "lanes": [results[timeframe] for timeframe in TIMEFRAMES],
        }
    finally:
        connection.close()


def _empty(timeframe: str, status: str, *, count: int | None = None,
           warnings: list[str] | None = None) -> dict:
    return {"timeframe": timeframe, "status": status, "total_bars": count,
            "last_active_session_bars": None, "current_session_bars": None,
            "first_bar_utc": None, "last_bar_utc": None,
            "last_year_bars": count, "last_month_bars": count,
            "last_24_hours_bars": None if timeframe in {"MN1", "W1", "D1"} else count,
            "warnings": warnings or [], "notes": [], "derived": timeframe in {"MN1", "W1", "M15"}}


def _counts(timeframe: str, stats, warnings: list[str]) -> dict:
    row = _empty(timeframe, "NO_HISTORY" if not stats[0] else
                 "AVAILABLE_WITH_WARNINGS" if warnings else "AVAILABLE", warnings=warnings)
    row.update(total_bars=int(stats[0]), first_bar_utc=_iso_utc(stats[1]) if stats[1] is not None else None,
               last_bar_utc=_iso_utc(stats[2]) if stats[2] is not None else None,
               last_year_bars=int(stats[3]), last_month_bars=int(stats[4]),
               last_24_hours_bars=None if timeframe in {"MN1", "W1", "D1"} else int(stats[5]))
    return row


def _m15_summary(database_path, authority, asset, source, cutoffs, now_epoch, sessions):
    """Read published M15 inventory only; never initialise or regenerate it."""
    if source["total_bars"] is None:
        return _empty("M15", source["status"], warnings=list(source["warnings"]))
    path = default_repository_path(database_path)
    if not path.is_file():
        return _empty("M15", "UNAVAILABLE", warnings=["M15_DERIVED_REPOSITORY_UNAVAILABLE"])
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN")
            registration = connection.execute(
                "SELECT * FROM synthetic_registrations WHERE symbol=? AND target_timeframe='M15'",
                (asset,),
            ).fetchone()
            if registration is None or registration["registration_status"] != "ACTIVE":
                return _empty("M15", "TIMEFRAME_NOT_ACTIVE")
            if (registration["immediate_source_symbol"], registration["immediate_source_timeframe"],
                registration["immediate_source_evidence_class"]) != (asset, "M5", "REAL"):
                return _empty("M15", "UNAVAILABLE", warnings=["M15_SOURCE_LINEAGE_UNAVAILABLE"])
            stats = connection.execute(
                "SELECT count(*),min(open_time_utc),max(open_time_utc),"
                "coalesce(sum(open_time_utc>=?),0),coalesce(sum(open_time_utc>=?),0),"
                "coalesce(sum(open_time_utc>=?),0) FROM synthetic_observations "
                "WHERE registration_id=? AND close_time_utc<=?",
                [*cutoffs, registration["registration_id"], now_epoch],
            ).fetchone()
            warnings = list(source["warnings"])
            if registration["generation_status"] != "Available":
                warnings.append("M15_DERIVED_HISTORY_" + registration["generation_status"].upper())
            current_revision = authority_revision_for_lane(authority, symbol=asset, timeframe="M5")
            if registration["source_revision"] != current_revision:
                warnings.append("M15_DERIVED_HISTORY_BEHIND_M5_SOURCE")
            row = _counts("M15", stats, warnings)
            row.update(session_bar_counts(connection, symbol=asset, timeframe="M15", sessions=sessions,
                observed_epoch=now_epoch, synthetic_id=registration["registration_id"]))
            if registration["generation_status"] == "Unavailable":
                row["status"] = "UNAVAILABLE"
            row["notes"] = [
                "Published M15 history derived from complete groups of three M5 bars. "
                "Incomplete groups and open intervals are excluded."
            ]
            return row
        finally:
            connection.close()
    except sqlite3.Error:
        return _empty("M15", "UNAVAILABLE", warnings=["M15_DERIVED_REPOSITORY_UNREADABLE"])
