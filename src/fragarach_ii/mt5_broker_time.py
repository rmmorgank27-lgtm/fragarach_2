"""Authoritative MT5 broker-server clock conversion for Fragarach evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


POLICY_ID = "MT5_BROKER_SERVER_US_DST_UTC_PLUS_2_3_V1"
_US_EASTERN = ZoneInfo("America/New_York")
_FORMATS = ("%Y.%m.%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


class MT5BrokerTimeError(ValueError):
    """The supplied broker timestamp cannot be mapped under the approved rule."""


def _parse_server_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise MT5BrokerTimeError("BROKER_TIME_NOT_TEXT")
    for format_string in _FORMATS:
        try:
            return datetime.strptime(value, format_string)
        except ValueError:
            continue
    raise MT5BrokerTimeError("BROKER_TIME_FORMAT_INVALID")


def broker_server_utc_candidates(value: str) -> tuple[datetime, ...]:
    """Return UTC candidates consistent with the broker's UTC+2/+3 clock.

    The broker follows the US daylight-saving state: UTC+2 while New York is
    on standard time and UTC+3 while New York is on daylight time.  Testing
    both offsets against the IANA transition authority avoids a fixed offset.
    """

    local = _parse_server_time(value)
    candidates: list[datetime] = []
    for offset_hours in (2, 3):
        candidate = (local - timedelta(hours=offset_hours)).replace(tzinfo=UTC)
        eastern = candidate.astimezone(_US_EASTERN)
        expected = 3 if eastern.dst() and eastern.dst() != timedelta(0) else 2
        if expected == offset_hours:
            candidates.append(candidate)
    return tuple(sorted(candidates))


def broker_server_to_utc(value: str, *, after: datetime | None = None) -> datetime:
    """Convert one MT5 broker-server timestamp under the approved DST rule.

    `after` disambiguates the repeated clock interval at the autumn transition
    while preserving the source order. Index-CFD markets are normally closed
    during that transition, but the rule remains explicit and deterministic.
    """

    candidates = broker_server_utc_candidates(value)
    if after is not None:
        prior = after.astimezone(UTC)
        candidates = tuple(candidate for candidate in candidates if candidate > prior)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise MT5BrokerTimeError("BROKER_TIME_HAS_NO_VALID_UTC_MAPPING")
    raise MT5BrokerTimeError("BROKER_TIME_AMBIGUOUS_REQUIRES_SEQUENCE")


__all__ = [
    "POLICY_ID",
    "MT5BrokerTimeError",
    "broker_server_to_utc",
    "broker_server_utc_candidates",
]
