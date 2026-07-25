"""Twelve Data response bytes to the common immutable staged-bar contract."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC,date,datetime
from zoneinfo import ZoneInfo

from fragarach_ii.ingestion.validation import RowValidationError, deduplicate_bars, stage_record
from fragarach_ii.staging import StagingBatch, StagingRejection
from fragarach_ii.validation.intraday_profiles import canonical_open,profile_for,iso,is_expected_open


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
    timeframe: str="D1",
    asset_class: str="FX",
    observed_at: datetime|None=None,
    allow_empty: bool=False,
) -> StagingBatch:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderPayloadError("MALFORMED_PAYLOAD", "response is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        code = payload.get("code") if isinstance(payload, dict) else None
        message = str(payload.get("message", "provider response status is not ok")) if isinstance(payload, dict) else "provider response status is not ok"
        normalized = message.lower()
        if code in {401, 403} or "api key" in normalized or "authentication" in normalized:
            raise ProviderPayloadError("AUTHENTICATION_FAILED", f"Twelve Data {code or 'authentication'}: {message}")
        if code == 429 or "rate limit" in normalized:
            raise ProviderPayloadError("RATE_LIMITED", f"Twelve Data {code or 'rate limit'}: {message}")
        if "quota" in normalized or "credits" in normalized:
            raise ProviderPayloadError("QUOTA_EXCEEDED", f"Twelve Data quota: {message}")
        raise ProviderPayloadError("PROVIDER_DECLARED_ERROR", f"Twelve Data {code or 'error'}: {message}")
    meta = payload.get("meta")
    values = payload.get("values")
    if not isinstance(meta, dict) or not isinstance(values, list) or (not values and not allow_empty):
        raise ProviderPayloadError("NO_USABLE_OBSERVATIONS", "response has no observation array")
    if meta.get("symbol") != provider_symbol:
        raise ProviderPayloadError("SYMBOL_MISMATCH", "provider response symbol mismatch")
    expected_interval={"D1":"1day","H1":"1h","M30":"30min","M5":"5min"}[timeframe]
    if meta.get("interval") != expected_interval:
        raise ProviderPayloadError("INTERVAL_MISMATCH", "provider response interval mismatch")
    bars = []
    row_rejections = []
    for index, observation in enumerate(values, start=1):
        if not isinstance(observation, dict):
            raise ProviderPayloadError("INVALID_OBSERVATION", f"observation {index} is not an object")
        timestamp_text = observation.get("datetime")
        try:
            if timeframe=="D1":
                match=_D1_DATETIME.fullmatch(timestamp_text) if isinstance(timestamp_text,str) else None
                if match is None:raise ValueError("INVALID_D1_TIMESTAMP")
                normalized_date=date.fromisoformat(match.group(1));canonical=normalized_date.isoformat()
            else:
                profile=profile_for(asset_class,timeframe);epoch=canonical_open(str(timestamp_text),profile)
                if not is_expected_open(epoch,profile):raise ValueError("OUTSIDE_EXPECTED_SESSION")
                # Intraday request bounds are provider-local calendar dates.
                # Comparing the canonical UTC date rejects the final hours of
                # every New York day once they cross 00:00 UTC.
                normalized_date=datetime.fromtimestamp(epoch,UTC).astimezone(
                    ZoneInfo(profile.timezone)
                ).date();canonical=iso(epoch)
                now=(observed_at or datetime.now(UTC)).astimezone(UTC)
                if epoch+profile.seconds>int(now.timestamp()):raise ValueError("INCOMPLETE_CURRENT_INTERVAL")
            if not from_date<=normalized_date<=through_date:raise ValueError("OUT_OF_RANGE_OBSERVATION")
        except (ValueError,TypeError) as error:
            row_rejections.append(StagingRejection(index,str(error),f"observation {index}: {error}"));continue
        fields = {
            "timestamp": canonical,
            "open": observation.get("open"),
            "high": observation.get("high"),
            "low": observation.get("low"),
            "close": observation.get("close"),
            "volume": observation.get("volume"),
        }
        if any(fields[name] is None for name in ("open", "high", "low", "close")):
            row_rejections.append(StagingRejection(index,"MISSING_OHLC",f"observation {index} lacks OHLC"));continue
        try:
            bars.append(
                stage_record(
                    {key: str(value) if value is not None else "" for key, value in fields.items()},
                    explicit_symbol=asset,
                    explicit_timeframe=timeframe,
                    provider="TWELVE_DATA",
                    source=f"TWELVE_DATA_TIME_SERIES_{timeframe}_V1",
                    raw_block_id=raw_block_id,
                    source_row_number=index,
                    received_at=received_at,
                )
            )
        except RowValidationError as error:
            row_rejections.append(StagingRejection(index,error.code,str(error)));continue
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
