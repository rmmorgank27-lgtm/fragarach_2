"""SPEC-026 consumer-neutral Market History Service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from .calendars import CalendarRegistry
from .calendars.models import CalendarDefinition
from .calendars.sessions import expected_session_dates, session_classification
from .external_consumer_service import canonical_database_path
from .lane_commissioning import market_policy
from .storage import open_read_only
from .truth_engine import TruthEngineError, truth_state_for_lane
from .validation.intraday_profiles import (
    IntradayProfile,
    expected_opens,
    profile_for,
)


DIRECT_TIMEFRAMES = frozenset({"D1", "H1", "M30", "M5"})
PENDING_DERIVED_TIMEFRAMES = frozenset({"H4", "M15"})
MARKET_HISTORY_RESPONSE_KEYS = frozenset({"OHLC", "CAODT", "Status", "Warnings"})
WindowKind = Literal["LAST_TRADING_DAYS", "BETWEEN"]


class MarketHistoryServiceError(RuntimeError):
    """A malformed Market History request."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class MarketHistoryWindow:
    """An authority-owned time window with no bar-count mechanics."""

    kind: WindowKind
    trading_days: int | None = None
    start: date | None = None
    end: date | None = None

    @classmethod
    def last_trading_days(cls, count: int) -> "MarketHistoryWindow":
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise MarketHistoryServiceError(
                "INVALID_TIME_WINDOW", "trading-day count must be a positive integer"
            )
        return cls("LAST_TRADING_DAYS", trading_days=count)

    @classmethod
    def between(cls, start: str | date, end: str | date) -> "MarketHistoryWindow":
        first = _canonical_date(start, "start")
        last = _canonical_date(end, "end")
        if last < first:
            raise MarketHistoryServiceError(
                "INVALID_TIME_WINDOW", "between-window end precedes start"
            )
        return cls("BETWEEN", start=first, end=last)


@dataclass(frozen=True, slots=True)
class DerivedContributor:
    """One canonical contributor already selected by construction authority."""

    timestamp: int
    open: str
    high: str
    low: str
    close: str


@dataclass(frozen=True, slots=True)
class DerivedTargetInterval:
    """One bounded target interval whose boundaries come from approved authority."""

    timestamp: int
    expected_contributor_timestamps: tuple[int, ...]
    contributors: tuple[DerivedContributor, ...]


def construct_bounded_derived_view(
    intervals: tuple[DerivedTargetInterval, ...],
) -> list[dict[str, object]]:
    """Construct deterministic OHLC without selecting or inventing boundaries.

    The inactive engine accepts only a complete authority-supplied interval plan.
    It performs no provider, session, alignment, or source-timeframe decision and
    writes nothing. H4 and M15 cannot call it until their construction authorities
    are separately commissioned.
    """

    output: list[dict[str, object]] = []
    previous_target: int | None = None
    for interval in intervals:
        if previous_target is not None and interval.timestamp <= previous_target:
            raise MarketHistoryServiceError(
                "INELIGIBLE_DERIVED_INTERVAL", "target intervals are not strictly ordered"
            )
        actual = tuple(item.timestamp for item in interval.contributors)
        if not actual or actual != interval.expected_contributor_timestamps:
            raise MarketHistoryServiceError(
                "INELIGIBLE_DERIVED_INTERVAL",
                "contributors do not exactly match the authority-supplied interval plan",
            )
        values = [_decimal_ohlc(item) for item in interval.contributors]
        output.append(
            {
                "timestamp": _iso_utc(interval.timestamp),
                "open": interval.contributors[0].open,
                "high": str(max(value[1] for value in values)),
                "low": str(min(value[2] for value in values)),
                "close": interval.contributors[-1].close,
            }
        )
        previous_target = interval.timestamp
    return output


def get_market_history(
    symbol: str,
    timeframe: str,
    window: MarketHistoryWindow,
) -> dict[str, object]:
    """Return Market History from Fragarach's configured authority."""

    return MarketHistoryService(canonical_database_path()).get_market_history(
        symbol, timeframe, window
    )


class MarketHistoryService:
    """Read-only, consumer-neutral historical authority boundary."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    def get_market_history(
        self,
        symbol: str,
        timeframe: str,
        window: MarketHistoryWindow,
    ) -> dict[str, object]:
        requested_symbol = symbol.strip().upper()
        requested_timeframe = timeframe.strip().upper()
        if not requested_symbol or not requested_timeframe:
            raise MarketHistoryServiceError(
                "INVALID_REQUEST", "symbol and timeframe are required"
            )
        if not isinstance(window, MarketHistoryWindow):
            raise MarketHistoryServiceError(
                "INVALID_TIME_WINDOW", "a MarketHistoryWindow is required"
            )

        connection = open_read_only(self.database_path)
        try:
            registration = _registration(connection, requested_symbol)
            if registration is None:
                return _response("NOT_REGISTERED", ["SYMBOL_NOT_REGISTERED"])
            canonical_symbol, asset_class, calendar_id, calendar_version = registration

            if requested_timeframe in PENDING_DERIVED_TIMEFRAMES:
                return _response(
                    "TIMEFRAME_NOT_ACTIVE",
                    ["CONSTRUCTION_AUTHORITY_NOT_COMMISSIONED"],
                )
            if requested_timeframe not in DIRECT_TIMEFRAMES:
                return _response(
                    "TIMEFRAME_NOT_AUTHORISED", ["TIMEFRAME_NOT_AUTHORISED"]
                )

            policy = market_policy(asset_class, requested_timeframe)
            if policy == "INTENTIONALLY_DEFERRED":
                return _response(
                    "TIMEFRAME_NOT_ACTIVE", ["TIMEFRAME_INTENTIONALLY_DEFERRED"]
                )
            lane = connection.execute(
                "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",
                (canonical_symbol, requested_timeframe),
            ).fetchone()
            if lane is None:
                return _response("TIMEFRAME_NOT_ACTIVE", ["TIMEFRAME_NOT_ACTIVE"])
            has_history = connection.execute(
                "SELECT 1 FROM bars WHERE asset=? AND timeframe=? LIMIT 1",
                (canonical_symbol, requested_timeframe),
            ).fetchone()
            if has_history is None:
                return _response("NO_HISTORY", ["NO_MARKET_HISTORY"])
        finally:
            connection.close()

        try:
            truth = truth_state_for_lane(
                self.database_path,
                symbol=canonical_symbol,
                timeframe=requested_timeframe,
            )
        except TruthEngineError as error:
            return _response("NO_HISTORY", [error.code])

        caodt = str(truth["caodt"])
        caodt_value = _canonical_datetime(caodt)
        try:
            calendar = CalendarRegistry(
                load_symbol_assignments=False
            ).calendar_by_id(calendar_id)
        except Exception as error:
            raise MarketHistoryServiceError(
                "HISTORY_AUTHORITY_UNAVAILABLE", str(error)
            ) from error
        if calendar.calendar_version != calendar_version:
            raise MarketHistoryServiceError(
                "HISTORY_AUTHORITY_UNAVAILABLE", "calendar authority version mismatch"
            )

        profile = (
            None
            if requested_timeframe == "D1"
            else profile_for(asset_class, requested_timeframe)
        )
        caodt_owner = _caodt_owner_date(caodt_value, requested_timeframe, profile)
        first_owner, last_owner, expected_days, warnings = _resolve_window(
            window, caodt_owner, calendar
        )
        warnings.extend(_truth_warnings(truth))
        if first_owner is None or last_owner is None:
            return _response("NO_HISTORY", _stable_warnings(warnings), caodt=caodt)

        lower, upper = _epoch_bounds(
            first_owner, last_owner, requested_timeframe, profile
        )
        connection = open_read_only(self.database_path)
        try:
            if requested_timeframe == "D1":
                rows = connection.execute(
                    """
                    SELECT open_time_utc,open,high,low,close
                    FROM bars
                    WHERE asset=? AND timeframe=?
                      AND open_time_utc>=? AND open_time_utc<?
                    ORDER BY open_time_utc
                    """,
                    (canonical_symbol, requested_timeframe, lower, upper),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT open_time_utc,open,high,low,close
                    FROM bars
                    WHERE asset=? AND timeframe=?
                      AND open_time_utc>=? AND open_time_utc<?
                      AND close_time_utc<=?
                    ORDER BY open_time_utc
                    """,
                    (
                        canonical_symbol,
                        requested_timeframe,
                        lower,
                        upper,
                        int(caodt_value.timestamp()),
                    ),
                ).fetchall()
        finally:
            connection.close()

        if not rows:
            warnings.append("NO_HISTORY_IN_REQUESTED_WINDOW")
            return _response("NO_HISTORY", _stable_warnings(warnings), caodt=caodt)

        if _has_missing_history(
            rows,
            requested_timeframe,
            profile,
            expected_days,
            lower,
            min(upper, int(caodt_value.timestamp())),
        ):
            warnings.append("REQUESTED_WINDOW_HAS_MISSING_HISTORY")

        warnings = _stable_warnings(warnings)
        status = "AVAILABLE_WITH_WARNINGS" if warnings else "AVAILABLE"
        return _response(
            status,
            warnings,
            caodt=caodt,
            ohlc=[
                {
                    "timestamp": _iso_utc(row[0]),
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                }
                for row in rows
            ],
        )


def _registration(connection, symbol: str) -> tuple[str, str, str, int] | None:
    direct = connection.execute(
        """
        SELECT asset,asset_class,calendar_id,calendar_version
        FROM instrument_registrations
        WHERE asset=? AND timeframe='D1'
        """,
        (symbol,),
    ).fetchone()
    if direct is not None:
        return str(direct[0]), str(direct[1]), str(direct[2]), int(direct[3])
    aliases = connection.execute(
        """
        SELECT DISTINCT r.asset,r.asset_class,r.calendar_id,r.calendar_version
        FROM instrument_registrations AS r,json_each(r.aliases_json) AS alias
        WHERE r.timeframe='D1'
          AND json_extract(alias.value,'$.normalized_alias')=?
        ORDER BY r.asset
        """,
        (symbol,),
    ).fetchall()
    if len(aliases) > 1:
        raise MarketHistoryServiceError("AMBIGUOUS_SYMBOL", symbol)
    if not aliases:
        return None
    row = aliases[0]
    return str(row[0]), str(row[1]), str(row[2]), int(row[3])


def _resolve_window(
    window: MarketHistoryWindow,
    caodt_owner: date,
    calendar: CalendarDefinition,
) -> tuple[date | None, date | None, tuple[date, ...], list[str]]:
    warnings: list[str] = []
    if window.kind == "LAST_TRADING_DAYS":
        assert window.trading_days is not None
        expected = _last_expected_days(caodt_owner, window.trading_days, calendar)
        if len(expected) < window.trading_days:
            warnings.append("REQUESTED_WINDOW_TRUNCATED_AT_AUTHORITY_START")
        return (
            expected[0] if expected else None,
            expected[-1] if expected else None,
            expected,
            warnings,
        )

    assert window.start is not None and window.end is not None
    first = window.start
    last = window.end
    if last > caodt_owner:
        warnings.append("REQUESTED_WINDOW_EXTENDS_BEYOND_CAODT")
        last = caodt_owner
    if first < calendar.effective_from:
        warnings.append("REQUESTED_WINDOW_TRUNCATED_AT_AUTHORITY_START")
        first = calendar.effective_from
    if calendar.effective_to is not None and last > calendar.effective_to:
        warnings.append("REQUESTED_WINDOW_TRUNCATED_AT_AUTHORITY_END")
        last = calendar.effective_to
    if last < first:
        warnings.append("NO_HISTORY_IN_REQUESTED_WINDOW")
        return None, None, (), warnings
    expected, _ = expected_session_dates(first, last, calendar)
    return first, last, expected, warnings


def _last_expected_days(
    end: date, count: int, calendar: CalendarDefinition
) -> tuple[date, ...]:
    values: list[date] = []
    current = min(end, calendar.effective_to) if calendar.effective_to else end
    while current >= calendar.effective_from and len(values) < count:
        if session_classification(current, calendar)[0]:
            values.append(current)
        current -= timedelta(days=1)
    return tuple(reversed(values))


def _epoch_bounds(
    first: date,
    last: date,
    timeframe: str,
    profile: IntradayProfile | None,
) -> tuple[int, int]:
    if timeframe == "D1" or profile is None or profile.continuous:
        lower = datetime.combine(first, time.min, UTC)
        upper = datetime.combine(last + timedelta(days=1), time.min, UTC)
        return int(lower.timestamp()), int(upper.timestamp())
    zone = ZoneInfo(profile.timezone)
    lower = datetime.combine(first - timedelta(days=1), time(17), zone)
    upper = datetime.combine(last, time(17), zone)
    return int(lower.timestamp()), int(upper.timestamp())


def _caodt_owner_date(
    caodt: datetime,
    timeframe: str,
    profile: IntradayProfile | None,
) -> date:
    if timeframe == "D1" or profile is None or profile.continuous:
        return caodt.astimezone(UTC).date()
    return _intraday_owner_date(
        int(caodt.timestamp()) - 1,
        profile,
    )


def _intraday_owner_date(epoch: int, profile: IntradayProfile) -> date:
    value = datetime.fromtimestamp(epoch, UTC)
    if profile.continuous:
        return value.date()
    local = value.astimezone(ZoneInfo(profile.timezone))
    return local.date() + timedelta(days=1) if local.hour >= 17 else local.date()


def _has_missing_history(
    rows,
    timeframe: str,
    profile: IntradayProfile | None,
    expected_days: tuple[date, ...],
    lower: int,
    upper: int,
) -> bool:
    expected_day_set = set(expected_days)
    if timeframe == "D1" or profile is None:
        present = {datetime.fromtimestamp(row[0], UTC).date() for row in rows}
        return bool(expected_day_set - present)
    expected = {
        value
        for value in expected_opens(lower, upper, profile)
        if _intraday_owner_date(value, profile) in expected_day_set
    }
    present = {int(row[0]) for row in rows}
    return bool(expected - present)


def _truth_warnings(truth: dict[str, object]) -> list[str]:
    state = str(truth.get("authority_state") or "").upper()
    warnings: list[str] = []
    if state and state != "GREEN":
        warnings.append(f"HISTORICAL_AUTHORITY_{state}")
    gap_summary = truth.get("gap_summary")
    if isinstance(gap_summary, dict) and int(gap_summary.get("total_known_gaps") or 0):
        warnings.append("HISTORICAL_GAPS_PRESENT")
    return warnings


def _response(
    status: str,
    warnings: list[str],
    *,
    caodt: str | None = None,
    ohlc: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    response: dict[str, object] = {
        "OHLC": ohlc or [],
        "CAODT": caodt,
        "Status": status,
        "Warnings": warnings,
    }
    assert frozenset(response) == MARKET_HISTORY_RESPONSE_KEYS
    return response


def _stable_warnings(warnings: list[str]) -> list[str]:
    return list(dict.fromkeys(warnings))


def _decimal_ohlc(
    contributor: DerivedContributor,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    try:
        values = tuple(
            Decimal(value)
            for value in (
                contributor.open,
                contributor.high,
                contributor.low,
                contributor.close,
            )
        )
    except (InvalidOperation, TypeError) as error:
        raise MarketHistoryServiceError(
            "INELIGIBLE_DERIVED_INTERVAL", "contributor contains invalid OHLC"
        ) from error
    open_value, high, low, close = values
    if low > min(open_value, close) or high < max(open_value, close) or low > high:
        raise MarketHistoryServiceError(
            "INELIGIBLE_DERIVED_INTERVAL", "contributor contains invalid OHLC geometry"
        )
    return open_value, high, low, close


def _canonical_date(value: str | date, name: str) -> date:
    if isinstance(value, date):
        return value
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise MarketHistoryServiceError(
            "INVALID_TIME_WINDOW", f"{name} must be an ISO calendar date"
        ) from error
    if parsed.isoformat() != value:
        raise MarketHistoryServiceError(
            "INVALID_TIME_WINDOW", f"{name} must be canonical ISO date text"
        )
    return parsed


def _canonical_datetime(value: str) -> datetime:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        raise MarketHistoryServiceError(
            "HISTORY_AUTHORITY_UNAVAILABLE", "CAODT is missing timezone authority"
        )
    return parsed.astimezone(UTC)


def _iso_utc(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).isoformat()
