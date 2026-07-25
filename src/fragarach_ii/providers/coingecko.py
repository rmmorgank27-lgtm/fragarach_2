"""CoinGecko OHLC adapter constrained to exact daily evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from fragarach_ii.ingestion import RawEvidence, ingest_staged_batch
from fragarach_ii.ingestion.validation import deduplicate_bars, stage_record
from fragarach_ii.staging import StagingBatch

from .twelve_data import AcquisitionError


def acquire_coingecko(
    database_path: str | Path,
    *, asset: str, timeframe: str, provider_symbol: str,
    from_date: str, through_date: str, merge_mode: str = "preserve",
    mapping_class: str | None = None, fetch=None, progress=None,
) -> dict[str, object]:
    if timeframe != "D1":
        raise AcquisitionError("UNSUPPORTED_TIMEFRAME", timeframe)
    days = (datetime.fromisoformat(through_date).date() - datetime.fromisoformat(from_date).date()).days + 1
    if days > 30:
        raise AcquisitionError("RANGE_TOO_LARGE", "CoinGecko exact OHLC granularity is limited to 30 days")
    url = "https://api.coingecko.com/api/v3/coins/{}/ohlc?{}".format(
        quote(provider_symbol, safe=""), urlencode({"vs_currency": "usd", "days": max(1, days), "precision": "full"})
    )
    if progress:
        progress("requesting")
    body = (fetch or _fetch)(url)
    try:
        rows = json.loads(body)
    except (TypeError, json.JSONDecodeError) as error:
        raise AcquisitionError("INVALID_RESPONSE", "CoinGecko returned invalid JSON") from error
    if not isinstance(rows, list):
        raise AcquisitionError("INVALID_RESPONSE", str(rows))
    received_at = datetime.now(UTC).isoformat(); checksum = hashlib.sha256(body).hexdigest(); raw_id = f"raw-{checksum}"
    bars = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) != 5:
            raise AcquisitionError("INVALID_RESPONSE", "CoinGecko OHLC shape mismatch")
        opened = datetime.fromtimestamp(int(row[0]) / 1000, UTC)
        if opened.hour != 0 or opened.minute != 0:
            raise AcquisitionError("INVALID_CHRONOLOGY", "CoinGecko response is not exact D1 evidence")
        bars.append(stage_record(
            {"timestamp": opened.date().isoformat(), "open": str(row[1]), "high": str(row[2]), "low": str(row[3]), "close": str(row[4])},
            explicit_symbol=asset, explicit_timeframe="D1", provider="COINGECKO",
            source="COINGECKO_OHLC_V1", raw_block_id=raw_id,
            source_row_number=index, received_at=received_at,
        ))
    if progress:
        progress("validating")
    ordered, rejections, identical, conflicting = deduplicate_bars(bars)
    if not ordered:
        raise AcquisitionError("NO_DATA", "CoinGecko returned no exact daily observations")
    if rejections:
        raise AcquisitionError("INVALID_OHLC", "CoinGecko evidence failed staging validation")
    batch = StagingBatch(bars=ordered, rejections=(), source_rows=len(rows), duplicate_identical=identical, duplicate_conflicting=conflicting)
    if progress:
        progress("ingesting")
    ingestion = ingest_staged_batch(
        database_path, batch=batch,
        evidence=RawEvidence(raw_id, checksum, body, "COINGECKO_OHLC_V1", url, "application/json", received_at),
        run_kind="provider_acquisition", merge_mode=merge_mode,
        outcome_facts={"asset": asset, "timeframe": "D1", "provider": "COINGECKO", "provider_contract": "COINGECKO_OHLC_V1", "provider_symbol": provider_symbol, "mapping_state": "APPROVED_CONFIGURATION", "mapping_class": mapping_class or "APPROVED_PROVIDER_ALIAS", "from_date": from_date, "through_date": through_date, "merge_mode": merge_mode, "checksum": checksum},
        preserve_rejected_evidence=True,
    )
    return {**ingestion.as_dict(), "provider_id": "COINGECKO", "provider_contract": "COINGECKO_OHLC_V1", "provider_symbol": provider_symbol, "asset": asset, "timeframe": "D1", "from_date": from_date, "through_date": through_date, "received": len(rows), "warnings": []}


def _fetch(url: str) -> bytes:
    response = urlopen(Request(url, headers={
        "User-Agent": "Fragarach-II/2", "Accept": "application/json", "Connection": "close",
    }), timeout=30)
    try:
        if response.status == 429:
            raise AcquisitionError("RATE_LIMITED", "CoinGecko rate limit response")
        return response.read(20 * 1024 * 1024)
    finally:
        response.close()
