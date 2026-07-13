"""Twelve Data response bytes to the common immutable staged-bar contract."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date

from fragarach_ii.ingestion.validation import RowValidationError, deduplicate_bars, stage_record
from fragarach_ii.staging import StagingBatch, StagingRejection


_D1_DATETIME = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[ T]00:00:00)?(?:Z)?$")


class ProviderPayloadError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def stage_twelve_data_response(
    body: bytes,
    *,
    asset: str,
    provider_symbol: str,
    from_date: date,
    through_date: date,
    raw_block_id: str,
    received_at: str,
) -> StagingBatch:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderPayloadError("MALFORMED_PAYLOAD", "response is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise ProviderPayloadError("PROVIDER_DECLARED_ERROR", "provider response status is not ok")
    meta = payload.get("meta")
    values = payload.get("values")
    if not isinstance(meta, dict) or not isinstance(values, list) or not values:
        raise ProviderPayloadError("NO_USABLE_OBSERVATIONS", "response has no observation array")
    if meta.get("symbol") != provider_symbol:
        raise ProviderPayloadError("SYMBOL_MISMATCH", "provider response symbol mismatch")
    if meta.get("interval") != "1day":
        raise ProviderPayloadError("INTERVAL_MISMATCH", "provider response interval mismatch")
    bars = []
    row_rejections = []
    for index, observation in enumerate(values, start=1):
        if not isinstance(observation, dict):
            raise ProviderPayloadError("INVALID_OBSERVATION", f"observation {index} is not an object")
        timestamp_text = observation.get("datetime")
        match = _D1_DATETIME.fullmatch(timestamp_text) if isinstance(timestamp_text, str) else None
        if match is None:
            raise ProviderPayloadError("INVALID_TIMESTAMP", f"observation {index} has invalid D1 datetime")
        normalized_date = date.fromisoformat(match.group(1))
        if not from_date <= normalized_date <= through_date:
            raise ProviderPayloadError("OUT_OF_RANGE_OBSERVATION", f"observation {index} is outside request")
        fields = {
            "timestamp": normalized_date.isoformat(),
            "open": observation.get("open"),
            "high": observation.get("high"),
            "low": observation.get("low"),
            "close": observation.get("close"),
            "volume": observation.get("volume"),
        }
        if any(fields[name] is None for name in ("open", "high", "low", "close")):
            raise ProviderPayloadError("MISSING_OHLC", f"observation {index} lacks OHLC")
        try:
            bars.append(
                stage_record(
                    {key: str(value) if value is not None else "" for key, value in fields.items()},
                    explicit_symbol=asset,
                    explicit_timeframe="D1",
                    provider="TWELVE_DATA",
                    source="TWELVE_DATA_TIME_SERIES_D1_V1",
                    raw_block_id=raw_block_id,
                    source_row_number=index,
                    received_at=received_at,
                )
            )
        except RowValidationError as error:
            if error.code == "INVALID_OHLC":
                row_rejections.append(StagingRejection(index, error.code, str(error)))
                continue
            raise ProviderPayloadError(error.code, f"observation {index}: {error}") from error
    ordered, rejections, identical, conflicting = deduplicate_bars(bars)
    if rejections:
        raise ProviderPayloadError("CONFLICTING_DUPLICATE", rejections[0].message)
    return StagingBatch(
        bars=ordered,
        rejections=tuple(row_rejections),
        source_rows=len(values),
        duplicate_identical=identical,
        duplicate_conflicting=conflicting,
    )


def evidence_identity(body: bytes) -> tuple[str, str]:
    checksum = hashlib.sha256(body).hexdigest()
    return f"raw-{checksum}", checksum
