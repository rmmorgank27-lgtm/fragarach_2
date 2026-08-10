"""Shared bounded market-history contract used by Fragarach II and Lite.

The ordered-range fingerprint is SHA-256 over one UTF-8 JSON line per
observation.  Each line is the compact array
``[symbol,timeframe,open_epoch,completed_epoch,open,high,low,close,volume]``.
Rows are hashed in the order supplied, so identity, ordering, completion time,
or any OHLCV content change produces a different fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping


HISTORY_RANGE_CONTRACT_VERSION = "fragarach.market_history_range.v1"
LEGACY_CONSUMER_IDENTITY = "UNSPECIFIED_LEGACY_CONSUMER"


class HistoryRangeContractError(RuntimeError):
    """A malformed bounded-range request."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def parse_utc(value: object, name: str) -> datetime:
    """Parse one timezone-aware ISO-8601 value and canonicalise it to UTC."""

    candidate = str(value)
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except (TypeError, ValueError) as error:
        raise HistoryRangeContractError(
            "INVALID_TIMESTAMP", f"{name} must be an ISO-8601 timestamp"
        ) from error
    if parsed.tzinfo is None:
        raise HistoryRangeContractError(
            "INVALID_TIMESTAMP", f"{name} requires an explicit timezone"
        )
    return parsed.astimezone(UTC)


def canonical_utc(value: datetime | int | float) -> str:
    parsed = (
        datetime.fromtimestamp(value, UTC)
        if isinstance(value, int | float)
        else value.astimezone(UTC)
    )
    return parsed.isoformat(timespec="seconds")


def validate_range(
    start_utc: object,
    end_utc_exclusive: object,
    as_of_utc: object,
) -> tuple[datetime, datetime, datetime]:
    start = parse_utc(start_utc, "start_utc")
    end = parse_utc(end_utc_exclusive, "end_utc_exclusive")
    as_of = parse_utc(as_of_utc, "as_of_utc")
    if end <= start:
        raise HistoryRangeContractError(
            "INVALID_TIME_WINDOW", "end_utc_exclusive must follow start_utc"
        )
    return start, end, as_of


def request_identity(
    *,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    as_of: datetime,
    consumer: str,
) -> str:
    payload = [
        HISTORY_RANGE_CONTRACT_VERSION,
        consumer,
        symbol,
        timeframe,
        canonical_utc(start),
        canonical_utc(end),
        canonical_utc(as_of),
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def ordered_range_fingerprint(
    symbol: str,
    timeframe: str,
    observations: Iterable[Mapping[str, Any]],
) -> str:
    """Fingerprint observation identity, supplied order, completion and OHLCV."""

    digest = hashlib.sha256()
    for observation in observations:
        timestamp = int(parse_utc(observation["timestamp"], "timestamp").timestamp())
        completed = int(
            parse_utc(
                observation["close_timestamp"], "close_timestamp"
            ).timestamp()
        )
        canonical = [
            symbol,
            timeframe,
            timestamp,
            completed,
            observation.get("open"),
            observation.get("high"),
            observation.get("low"),
            observation.get("close"),
            observation.get("volume"),
        ]
        digest.update(
            json.dumps(
                canonical, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            + b"\n"
        )
    return "sha256:" + digest.hexdigest()

