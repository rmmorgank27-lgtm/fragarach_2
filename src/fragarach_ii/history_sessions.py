"""Read-only session windows for the History inventory, not scheduler policy."""
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .calendars import CalendarRegistry, ConfigurationError
from .calendars.sessions import session_classification
from .lane_commissioning import resolved_calendar_id

# Ordinary grids already specified by the equities H1 authorities and used in
# gator_bootstrap_service. Early-close overrides are not yet modelled here.
_CASH_OPENS = {
    "US_EQUITIES_D1_V1": time(9, 30),
    "AUSTRALIAN_EQUITIES_D1_V1": time(10),
    "UK_EQUITIES_D1_V1": time(8),
}


def history_sessions(registration, observed: datetime) -> dict:
    symbol, asset_class, calendar_id, version, exchange = registration
    unavailable = {"state": "UNAVAILABLE", "timezone": None, "calendar_id": calendar_id,
                   "last_active": None, "current": None,
                   "note": "Session calendar or opening-time authority unavailable."}
    try:
        resolved = resolved_calendar_id(asset_class=asset_class, calendar_id=calendar_id,
                                        exchange_name=exchange, canonical_symbol=symbol)
        if resolved is None:
            return unavailable
        definition = CalendarRegistry(load_symbol_assignments=False).calendar_by_id(resolved)
        if definition.calendar_version != version:
            return unavailable
        if asset_class not in {"FX", "METALS", "ENERGY", "CRYPTO"} and resolved not in _CASH_OPENS:
            return unavailable
        observed = observed.astimezone(UTC)
        local_day = observed.astimezone(ZoneInfo(definition.session_timezone)).date()
        if local_day < definition.effective_from or (definition.effective_to and local_day > definition.effective_to):
            return unavailable
        previous = current = None
        # The next owner date can already be active after today's rollover.
        for offset in range(1, -371, -1):
            owner = local_day + timedelta(days=offset)
            if not session_classification(owner, definition)[0]:
                continue
            opened, closed = _bounds(owner, definition, asset_class)
            session = {"date": owner.isoformat(), "open_utc": opened.isoformat(), "close_utc": closed.isoformat()}
            if opened <= observed < closed:
                current = session
            if closed <= observed:
                previous = session
                break
        return {"state": "OPEN" if current else "CLOSED", "timezone": definition.session_timezone,
                "calendar_id": resolved, "last_active": previous, "current": current,
                "note": "Regular session calendar; holiday closures are excluded. Shortened-session exceptions are not yet modelled."
                        if asset_class != "CRYPTO" else "Continuous crypto sessions use UTC calendar days."}
    except (ConfigurationError, ValueError):
        return unavailable


def _bounds(owner: date, definition, asset_class: str):
    zone = ZoneInfo(definition.session_timezone)
    close_day = owner + timedelta(days=definition.session_close_owner_day_offset)
    closed = datetime.combine(close_day, definition.session_close_local, zone)
    if asset_class == "CRYPTO":
        opened = datetime.combine(owner, time.min, zone)
    elif asset_class in {"FX", "METALS", "ENERGY"}:
        opened = datetime.combine(close_day - timedelta(days=1), definition.session_close_local, zone)
    else:
        opened = datetime.combine(owner, _CASH_OPENS[definition.calendar_id], zone)
    # Scheduling publication delays are not part of market opening hours.
    return opened.astimezone(UTC), closed.astimezone(UTC)


def session_bar_counts(connection, *, symbol: str, timeframe: str, sessions: dict,
                       observed_epoch: int, authority_cutoff: int | None = None,
                       synthetic_id: str | None = None) -> dict:
    counts = {"last_active_session_bars": None, "current_session_bars": None}
    if timeframe in {"MN1", "W1"} or sessions["state"] == "UNAVAILABLE":
        return counts
    upper = min(observed_epoch, authority_cutoff) if authority_cutoff is not None else observed_epoch
    for name, field in [("last_active", "last_active_session_bars"), ("current", "current_session_bars")]:
        session = sessions[name]
        if session is None:
            continue
        opened = datetime.fromisoformat(session["open_utc"]).timestamp()
        closed = datetime.fromisoformat(session["close_utc"]).timestamp()
        if timeframe == "D1":
            # D1 timestamps identify the owner date, not the session opening
            # instant. A current, unclosed daily bar is never counted.
            if closed > observed_epoch:
                counts[field] = 0
                continue
            owner_epoch = int(datetime.combine(date.fromisoformat(session["date"]), time.min, UTC).timestamp())
            counts[field] = connection.execute(
                "SELECT count(*) FROM bars WHERE asset=? AND timeframe='D1' AND open_time_utc=? AND open_time_utc<=?",
                (symbol, owner_epoch, upper),
            ).fetchone()[0]
        else:
            table = "synthetic_observations" if synthetic_id else "bars"
            identity = "registration_id=?" if synthetic_id else "asset=? AND timeframe=?"
            parameters = [synthetic_id] if synthetic_id else [symbol, timeframe]
            counts[field] = connection.execute(
                f"SELECT count(*) FROM {table} WHERE {identity} "
                "AND open_time_utc>=? AND open_time_utc<? AND close_time_utc<=?",
                [*parameters, opened, closed, min(upper, closed)],
            ).fetchone()[0]
    return counts
