"""CoinGecko GeckoTerminal pool OHLCV adapter for reviewed crypto lanes."""

from __future__ import annotations

import hashlib
import http.client
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

from fragarach_ii.ingestion import RawEvidence, ingest_staged_batch
from fragarach_ii.ingestion.validation import deduplicate_bars, stage_record
from fragarach_ii.staging import StagingBatch

from .post_ingest_validation import persist_committed_lane_validation
from .twelve_data import AcquisitionError


PROVIDER_ID = "COINGECKO_DEX"
PROVIDER_CONTRACT = "COINGECKO_GECKOTERMINAL_POOL_OHLCV_V1"
DEFAULT_API_BASE_URL = "https://api.geckoterminal.com/api/v2"
_ADDRESS = re.compile(r"0x[0-9a-f]{40,64}", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class PoolMapping:
    network: str
    pool_address: str
    token_side: str
    token_address: str


def acquire_coingecko_dex(
    database_path: str | Path,
    *,
    asset: str,
    timeframe: str,
    provider_symbol: str,
    from_date: str,
    through_date: str,
    merge_mode: str = "preserve",
    mapping_class: str | None = None,
    api_base_url: str | None = None,
    fetch=None,
    progress=None,
    clock=None,
) -> dict[str, object]:
    interval = {"H1": ("hour", 1, 3600), "M5": ("minute", 5, 300)}.get(timeframe)
    if interval is None:
        raise AcquisitionError("UNSUPPORTED_TIMEFRAME", timeframe)
    mapping = _parse_provider_symbol(provider_symbol)
    path_timeframe, aggregate, interval_seconds = interval
    start, _ = _parse_utc_bound(from_date)
    end, end_is_date = _parse_utc_bound(through_date)
    if end_is_date:
        end += timedelta(days=1)
    expected_rows = max(1, int((end - start).total_seconds() // interval_seconds))
    if expected_rows > 1000:
        raise AcquisitionError("RANGE_TOO_LARGE", "GeckoTerminal requests are limited to 1,000 candles")
    params = urlencode({
        "token": mapping.token_side,
        "aggregate": aggregate,
        "before_timestamp": int(end.timestamp()),
        "limit": min(1000, expected_rows + 2),
        "currency": "usd",
        "include_empty_intervals": "true",
    })
    base_url = _approved_api_base_url(api_base_url)
    url = (
        f"{base_url}/networks/{quote(mapping.network, safe='')}/pools/"
        f"{quote(mapping.pool_address, safe='')}/ohlcv/{path_timeframe}?{params}"
    )
    if progress:
        progress("requesting")
    body = (fetch or _fetch)(url)
    try:
        payload = json.loads(body)
    except (TypeError, json.JSONDecodeError) as error:
        raise AcquisitionError("INVALID_RESPONSE", "CoinGecko returned invalid JSON") from error
    rows = (((payload or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list")
    if not isinstance(rows, list):
        detail = (payload or {}).get("errors") if isinstance(payload, dict) else payload
        raise AcquisitionError("INVALID_RESPONSE", str(detail or "CoinGecko OHLCV shape mismatch"))
    _verify_token_identity(payload, mapping)

    received = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC)
    received_at = received.isoformat()
    checksum = hashlib.sha256(body).hexdigest()
    raw_id = f"raw-{checksum}"
    bars = []
    incomplete_rows = 0
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) != 6:
            raise AcquisitionError("INVALID_RESPONSE", "CoinGecko OHLCV row shape mismatch")
        opened = datetime.fromtimestamp(int(row[0]), UTC)
        closed = opened + timedelta(seconds=interval_seconds)
        if int(opened.timestamp()) % interval_seconds:
            raise AcquisitionError("INVALID_CHRONOLOGY", "CoinGecko candle is not UTC boundary aligned")
        if opened < start or opened >= end:
            continue
        if closed > received:
            incomplete_rows += 1
            continue
        bars.append(stage_record(
            {
                "timestamp": opened.isoformat(),
                "close_time": closed.isoformat(),
                "open": str(row[1]), "high": str(row[2]), "low": str(row[3]),
                "close": str(row[4]), "volume": str(row[5]),
            },
            explicit_symbol=asset, explicit_timeframe=timeframe,
            provider=PROVIDER_ID, source=PROVIDER_CONTRACT,
            raw_block_id=raw_id, source_row_number=index, received_at=received_at,
        ))
    if progress:
        progress("validating")
    ordered, rejections, identical, conflicting = deduplicate_bars(bars)
    if not ordered:
        raise AcquisitionError("NO_DATA", "CoinGecko returned no completed observations in range")
    if rejections:
        raise AcquisitionError("INVALID_OHLC", "CoinGecko evidence failed staging validation")
    _require_continuous_intervals(ordered, interval_seconds)
    batch = StagingBatch(
        bars=ordered, rejections=(), source_rows=len(rows),
        duplicate_identical=identical, duplicate_conflicting=conflicting,
    )
    if progress:
        progress("ingesting")
    ingestion = ingest_staged_batch(
        database_path,
        batch=batch,
        evidence=RawEvidence(
            raw_id, checksum, body, PROVIDER_CONTRACT, url,
            "application/json", received_at,
        ),
        run_kind="provider_acquisition",
        merge_mode=merge_mode,
        outcome_facts={
            "asset": asset, "timeframe": timeframe, "provider": PROVIDER_ID,
            "provider_contract": PROVIDER_CONTRACT, "provider_symbol": provider_symbol,
            "mapping_state": "APPROVED_CONFIGURATION",
            "mapping_class": mapping_class or "APPROVED_PROVIDER_ALIAS",
            "from_date": from_date, "through_date": through_date,
            "merge_mode": merge_mode, "checksum": checksum,
            "provider_rows_received": len(rows),
            "completed_observations_received": len(ordered),
            "incomplete_rows_excluded": incomplete_rows,
            "empty_intervals_included": True,
        },
        preserve_rejected_evidence=True,
    )
    validation = persist_committed_lane_validation(
        database_path,
        asset=asset,
        timeframe=timeframe,
        through_date=through_date,
        clock=clock,
        canonical_inserts=ingestion.inserted,
        canonical_corrections=ingestion.corrected,
    )
    return {
        **ingestion.as_dict(),
        "provider_id": PROVIDER_ID,
        "provider_contract": PROVIDER_CONTRACT,
        "provider_symbol": provider_symbol,
        "asset": asset,
        "timeframe": timeframe,
        "from_date": from_date,
        "through_date": through_date,
        "received": len(rows),
        "completed_observations_received": len(ordered),
        "incomplete_rows_excluded": incomplete_rows,
        "validation_calendar_id": validation.as_dict().get("calendar_id"),
        "warnings": (
            [f"Excluded {incomplete_rows} still-open provider candle(s)"]
            if incomplete_rows else []
        ),
    }


def _parse_provider_symbol(value: str) -> PoolMapping:
    parts = str(value).split(":")
    if len(parts) != 4:
        raise AcquisitionError("INVALID_PROVIDER_MAPPING", "CoinGecko pool mapping must contain network, pool, token side, and token address")
    network, pool_address, token_side, token_address = parts
    if network != "eth" or token_side not in {"base", "quote"}:
        raise AcquisitionError("INVALID_PROVIDER_MAPPING", "CoinGecko pool mapping is not approved")
    if not _ADDRESS.fullmatch(pool_address) or not _ADDRESS.fullmatch(token_address):
        raise AcquisitionError("INVALID_PROVIDER_MAPPING", "CoinGecko pool mapping contains an invalid address")
    return PoolMapping(network, pool_address.lower(), token_side, token_address.lower())


def _verify_token_identity(payload: dict[str, object], mapping: PoolMapping) -> None:
    meta = payload.get("meta") if isinstance(payload, dict) else None
    token = meta.get(mapping.token_side) if isinstance(meta, dict) else None
    observed = str(token.get("address") or "").lower() if isinstance(token, dict) else ""
    if observed != mapping.token_address:
        raise AcquisitionError("ORIENTATION_MISMATCH", "CoinGecko pool token identity does not match the reviewed mapping")


def _require_continuous_intervals(bars, interval_seconds: int) -> None:
    opened = [int(bar.timestamp) for bar in bars]
    if any(right - left != interval_seconds for left, right in zip(opened, opened[1:])):
        raise AcquisitionError("INVALID_CHRONOLOGY", "CoinGecko response omitted an expected candle interval")


def _fetch(url: str) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "api.geckoterminal.com":
        raise ValueError("CoinGecko DEX request must use the approved HTTPS host")
    target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=30)
    try:
        connection.request("GET", target, headers={
            "User-Agent": "Fragarach-II/2", "Accept": "application/json", "Connection": "close",
        })
        response = connection.getresponse()
        body = response.read(20 * 1024 * 1024)
        if response.status == 429:
            raise AcquisitionError("RATE_LIMITED", "CoinGecko rate limit response")
        if response.status >= 400:
            raise AcquisitionError("INVALID_RESPONSE", f"CoinGecko returned HTTP {response.status}")
        return body
    finally:
        connection.close()


def _approved_api_base_url(value: str | None) -> str:
    base_url = (value or DEFAULT_API_BASE_URL).rstrip("/")
    if base_url != DEFAULT_API_BASE_URL:
        raise ValueError("unapproved CoinGecko DEX API base URL")
    return base_url


def _parse_utc_bound(value: str) -> tuple[datetime, bool]:
    raw = str(value).strip()
    if len(raw) == 10:
        return datetime.combine(date.fromisoformat(raw), time.min, UTC), True
    normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("CoinGecko request bounds must declare UTC offset")
    return parsed.astimezone(UTC), False
