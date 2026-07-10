"""Calendar-independent structural validation for staged market bars."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping

from fragarach_ii.staging.contract import StagedBar, StagingRejection


DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RowValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def normalize_identity(value: str | None, name: str) -> str:
    normalized = (value or "").strip().upper()
    if not normalized:
        raise RowValidationError("MISSING_IDENTITY", f"{name} is required")
    return normalized


def stage_record(
    fields: Mapping[str, str],
    *,
    explicit_symbol: str | None,
    explicit_timeframe: str | None,
    provider: str,
    source: str,
    raw_block_id: str,
    source_row_number: int,
    received_at: str,
) -> StagedBar:
    csv_symbol = (fields.get("symbol") or "").strip() or None
    csv_timeframe = (fields.get("timeframe") or "").strip() or None
    symbol = _resolve_identity(explicit_symbol, csv_symbol, "symbol")
    timeframe = _resolve_identity(explicit_timeframe, csv_timeframe, "timeframe")
    if timeframe != "D1":
        raise RowValidationError(
            "UNSUPPORTED_TIMEFRAME", "SPEC-002 manual proof supports timeframe D1 only"
        )

    source_timestamp = (fields.get("timestamp") or "").strip()
    timestamp = parse_utc_timestamp(source_timestamp, timeframe)
    open_value = parse_decimal(fields.get("open"), "open")
    high_value = parse_decimal(fields.get("high"), "high")
    low_value = parse_decimal(fields.get("low"), "low")
    close_value = parse_decimal(fields.get("close"), "close")
    volume_text = (fields.get("volume") or "").strip()
    volume_value = parse_decimal(volume_text, "volume") if volume_text else None

    if high_value < low_value:
        raise RowValidationError("INVALID_OHLC", "high is below low")
    if high_value < open_value:
        raise RowValidationError("INVALID_OHLC", "high is below open")
    if high_value < close_value:
        raise RowValidationError("INVALID_OHLC", "high is below close")
    if low_value > open_value:
        raise RowValidationError("INVALID_OHLC", "low is above open")
    if low_value > close_value:
        raise RowValidationError("INVALID_OHLC", "low is above close")
    if volume_value is not None and volume_value < 0:
        raise RowValidationError("INVALID_VOLUME", "volume is negative")

    return StagedBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=canonical_decimal(open_value),
        high=canonical_decimal(high_value),
        low=canonical_decimal(low_value),
        close=canonical_decimal(close_value),
        volume=canonical_decimal(volume_value) if volume_value is not None else None,
        source=source,
        provider=normalize_identity(provider, "provider"),
        raw_block_id=raw_block_id,
        source_row_number=source_row_number,
        source_timestamp_text=source_timestamp,
        received_at=received_at,
    )


def deduplicate_bars(
    bars: list[StagedBar],
) -> tuple[tuple[StagedBar, ...], tuple[StagingRejection, ...], int, int]:
    by_key: dict[tuple[str, str, int], StagedBar] = {}
    rejections: list[StagingRejection] = []
    identical = 0
    conflicting = 0
    for bar in sorted(bars, key=lambda value: (value.canonical_key, value.source_row_number)):
        prior = by_key.get(bar.canonical_key)
        if prior is None:
            by_key[bar.canonical_key] = bar
        elif prior.values == bar.values:
            identical += 1
        else:
            conflicting += 1
            rejections.append(
                StagingRejection(
                    bar.source_row_number,
                    "CONFLICTING_DUPLICATE",
                    f"canonical key conflicts with source row {prior.source_row_number}",
                )
            )
    ordered = tuple(by_key[key] for key in sorted(by_key))
    return ordered, tuple(rejections), identical, conflicting


def parse_utc_timestamp(value: str, timeframe: str) -> int:
    if not value:
        raise RowValidationError("INVALID_TIMESTAMP", "timestamp is required")
    if DATE_ONLY.fullmatch(value):
        if timeframe != "D1":
            raise RowValidationError(
                "INVALID_TIMESTAMP", "date-only timestamps are accepted only for D1"
            )
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as error:
            raise RowValidationError("INVALID_TIMESTAMP", str(error)) from error
        parsed = datetime.combine(parsed_date, datetime.min.time(), UTC)
    else:
        if "/" in value:
            raise RowValidationError(
                "AMBIGUOUS_TIMESTAMP", "locale-style timestamp is not accepted"
            )
        candidate = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as error:
            raise RowValidationError("INVALID_TIMESTAMP", str(error)) from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise RowValidationError(
                "MISSING_TIMEZONE", "timestamp must declare UTC or be a D1 date"
            )
        if parsed.utcoffset().total_seconds() != 0:
            raise RowValidationError(
                "NON_UTC_TIMESTAMP", "timestamp offset must be UTC"
            )
        parsed = parsed.astimezone(UTC)
    return int(parsed.timestamp())


def parse_decimal(value: str | None, name: str) -> Decimal:
    text = (value or "").strip()
    if not text:
        raise RowValidationError("INVALID_NUMERIC", f"{name} is required")
    try:
        parsed = Decimal(text)
    except InvalidOperation as error:
        raise RowValidationError("INVALID_NUMERIC", f"{name} is not numeric") from error
    if not parsed.is_finite():
        raise RowValidationError("NON_FINITE_NUMERIC", f"{name} must be finite")
    return parsed


def canonical_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _resolve_identity(
    explicit: str | None, csv_value: str | None, name: str
) -> str:
    explicit_normalized = normalize_identity(explicit, name) if explicit else None
    csv_normalized = normalize_identity(csv_value, name) if csv_value else None
    if explicit_normalized and csv_normalized and explicit_normalized != csv_normalized:
        raise RowValidationError(
            "IDENTITY_MISMATCH",
            f"explicit {name} {explicit_normalized} disagrees with CSV {csv_normalized}",
        )
    result = explicit_normalized or csv_normalized
    if result is None:
        raise RowValidationError("MISSING_IDENTITY", f"{name} is required")
    return result
