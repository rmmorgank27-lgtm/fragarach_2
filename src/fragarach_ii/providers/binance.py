"""Approved Binance klines adapter using the canonical ingestion pipeline."""

from __future__ import annotations

import hashlib
import http.client
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fragarach_ii.ingestion import RawEvidence, ingest_staged_batches
from fragarach_ii.ingestion.validation import deduplicate_bars, stage_record
from fragarach_ii.staging import StagingBatch

from .twelve_data import AcquisitionError


@dataclass(frozen=True, slots=True)
class PreparedBinanceChunk:
    """A validated Binance response awaiting one job-scoped admission."""

    batch: StagingBatch
    evidence: RawEvidence
    received: int
    incomplete_rows_excluded: int


def acquire_binance(
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
    prepared = prepare_binance_chunk(
        asset=asset,
        timeframe=timeframe,
        provider_symbol=provider_symbol,
        from_date=from_date,
        through_date=through_date,
        api_base_url=api_base_url,
        fetch=fetch,
        progress=progress,
        clock=clock,
    )
    return admit_binance_chunks(
        database_path,
        asset=asset,
        timeframe=timeframe,
        provider_symbol=provider_symbol,
        chunks=(prepared,),
        merge_mode=merge_mode,
        mapping_class=mapping_class,
        from_date=from_date,
        through_date=through_date,
    )


def prepare_binance_chunk(
    *,
    asset: str,
    timeframe: str,
    provider_symbol: str,
    from_date: str,
    through_date: str,
    api_base_url: str | None = None,
    fetch=None,
    progress=None,
    clock=None,
) -> PreparedBinanceChunk:
    """Download and validate one chunk without mutating canonical evidence."""
    interval = {"M5": "5m", "M30": "30m", "H1": "1h", "D1": "1d"}.get(timeframe)
    if not interval:
        raise AcquisitionError("UNSUPPORTED_TIMEFRAME", timeframe)
    start, _ = _parse_utc_bound(from_date)
    end, end_is_date = _parse_utc_bound(through_date)
    # Date-only callers retain the historical inclusive-date contract.  Unified
    # intraday plans supply precise UTC boundaries, which must not be expanded
    # to a whole extra day.
    if end_is_date:
        end += timedelta(days=1)
    params = urlencode({
        "symbol": provider_symbol,
        "interval": interval,
        "startTime": int(start.timestamp() * 1000),
        "endTime": int(end.timestamp() * 1000) - 1,
        "limit": 1000,
    })
    url = f"{_approved_api_base_url(api_base_url)}/api/v3/klines?{params}"
    if progress:
        progress("requesting")
    body = (fetch or _fetch)(url)
    try:
        rows = json.loads(body)
    except (TypeError, json.JSONDecodeError) as error:
        raise AcquisitionError("INVALID_RESPONSE", "Binance returned invalid JSON") from error
    if isinstance(rows, dict):
        code = "RATE_LIMITED" if rows.get("code") in {-1003, -1015} else "INVALID_RESPONSE"
        raise AcquisitionError(code, str(rows.get("msg") or "Binance request failed"))
    received = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC)
    received_at = received.isoformat()
    checksum = hashlib.sha256(body).hexdigest()
    raw_id = f"raw-{checksum}"
    bars = []
    incomplete_rows = 0
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) < 7:
            raise AcquisitionError("INVALID_RESPONSE", "Binance kline shape mismatch")
        opened = datetime.fromtimestamp(int(row[0]) / 1000, UTC)
        closed = datetime.fromtimestamp((int(row[6]) + 1) / 1000, UTC)
        if closed > received:
            incomplete_rows += 1
            continue
        bars.append(stage_record(
            {
                "timestamp": opened.isoformat(), "close_time": closed.isoformat(),
                "open": str(row[1]), "high": str(row[2]), "low": str(row[3]),
                "close": str(row[4]), "volume": str(row[5]),
            },
            explicit_symbol=asset, explicit_timeframe=timeframe,
            provider="BINANCE", source="BINANCE_KLINES_V1",
            raw_block_id=raw_id, source_row_number=index, received_at=received_at,
        ))
    if progress:
        progress("validating")
    ordered, rejections, identical, conflicting = deduplicate_bars(bars)
    if not ordered:
        raise AcquisitionError("NO_DATA", "Binance returned no observations")
    if rejections:
        raise AcquisitionError("INVALID_OHLC", "Binance evidence failed staging validation")
    batch = StagingBatch(
        bars=ordered, rejections=(), source_rows=len(rows),
        duplicate_identical=identical, duplicate_conflicting=conflicting,
    )
    if progress:
        progress("ingesting")
    return PreparedBinanceChunk(
        batch=batch,
        evidence=RawEvidence(
            raw_id, checksum, body, "BINANCE_KLINES_V1", url, "application/json", received_at
        ),
        received=len(rows),
        incomplete_rows_excluded=incomplete_rows,
    )


def admit_binance_chunks(
    database_path: str | Path,
    *,
    asset: str,
    timeframe: str,
    provider_symbol: str,
    chunks: tuple[PreparedBinanceChunk, ...],
    merge_mode: str = "preserve",
    mapping_class: str | None = None,
    from_date: str,
    through_date: str,
) -> dict[str, object]:
    """Commit prepared chunks once, retaining a raw block for every response."""
    if not chunks:
        raise ValueError("at least one prepared Binance chunk is required")
    checksum = chunks[0].evidence.checksum
    ingestion = ingest_staged_batches(
        database_path,
        batches=tuple(chunk.batch for chunk in chunks),
        evidences=tuple(chunk.evidence for chunk in chunks),
        run_kind="provider_acquisition", merge_mode=merge_mode,
        outcome_facts={
            "asset": asset, "timeframe": timeframe, "provider": "BINANCE",
            "provider_contract": "BINANCE_KLINES_V1", "provider_symbol": provider_symbol,
            "mapping_state": "APPROVED_CONFIGURATION", "from_date": from_date,
            "mapping_class": mapping_class or "EXACT_REPRESENTATION",
            "through_date": through_date, "merge_mode": merge_mode, "checksum": checksum,
            "provider_rows_received": sum(chunk.received for chunk in chunks),
            "incomplete_rows_excluded": sum(chunk.incomplete_rows_excluded for chunk in chunks),
            "provider_chunk_count": len(chunks),
        },
        preserve_rejected_evidence=True,
    )
    return {
        **ingestion.as_dict(), "provider_id": "BINANCE",
        "provider_contract": "BINANCE_KLINES_V1", "provider_symbol": provider_symbol,
        "asset": asset, "timeframe": timeframe, "from_date": from_date,
        "through_date": through_date,
        "received": sum(chunk.received for chunk in chunks),
        "completed_observations_received": sum(len(chunk.batch.bars) for chunk in chunks),
        "incomplete_rows_excluded": sum(chunk.incomplete_rows_excluded for chunk in chunks),
        "chunk_count": len(chunks),
        "warnings": (
            [f"Excluded {sum(chunk.incomplete_rows_excluded for chunk in chunks)} still-open provider candle(s)"]
            if any(chunk.incomplete_rows_excluded for chunk in chunks) else []
        ),
    }


def _fetch(url: str) -> bytes:
    """Read one Binance response and deterministically close its TCP socket."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Binance request must use HTTPS")
    target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=30)
    try:
        connection.request("GET", target, headers={
            "User-Agent": "Fragarach-II/2", "Connection": "close",
        })
        response = connection.getresponse()
        if response.status == 429:
            raise AcquisitionError("RATE_LIMITED", "Binance rate limit response")
        return response.read(20 * 1024 * 1024)
    finally:
        # ``HTTPResponse.close`` alone has left sockets in CLOSE_WAIT under
        # sustained catch-up on macOS.  Closing the owning connection releases
        # the descriptor even when parsing or validation raises.
        connection.close()


def _approved_api_base_url(value: str | None) -> str:
    """Use only a reviewed Binance venue; existing USD routes stay on Binance.US."""
    base_url = (value or "https://api.binance.us").rstrip("/")
    if base_url not in {"https://api.binance.us", "https://api.binance.com"}:
        raise ValueError("unapproved Binance API base URL")
    return base_url


def _parse_utc_bound(value: str) -> tuple[datetime, bool]:
    """Parse a date or explicit UTC request boundary without touching evidence."""
    raw = str(value).strip()
    if len(raw) == 10:
        return datetime.combine(date.fromisoformat(raw), time.min, UTC), True
    normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Binance request bounds must declare UTC offset")
    return parsed.astimezone(UTC), False
