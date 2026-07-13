"""Manual-file adapter into the one staged-bar ingestion pipeline."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.staging import stage_csv_bytes
from fragarach_ii.storage import open_read_only
from fragarach_ii.validation import validate_lane

from .pipeline import (
    IngestionFailure,
    IngestionResult,
    RawEvidence,
    ingest_staged_batch,
)


Clock = Callable[[], datetime]


def ingest_manual_file(
    database_path: str | Path,
    file_path: str | Path,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    provider: str = "MANUAL",
    merge_mode: str = "preserve",
    source_timezone: str | None = None,
    clock: Clock | None = None,
    before_commit: Callable[[sqlite3.Connection], None] | None = None,
) -> IngestionResult:
    if merge_mode not in {"preserve", "correct"}:
        raise ValueError("merge mode must be 'preserve' or 'correct'")
    selected = Path(file_path).expanduser().resolve()
    payload = selected.read_bytes()
    checksum = hashlib.sha256(payload).hexdigest()
    raw_block_id = f"raw-{checksum}"
    received_at = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC).isoformat()
    normalized_timeframe = timeframe.strip().upper() if timeframe else None
    asset_class = _registered_asset_class(database_path, symbol) if normalized_timeframe != "D1" else None
    batch = stage_csv_bytes(
        payload,
        symbol=symbol,
        timeframe=timeframe,
        provider=provider,
        raw_block_id=raw_block_id,
        received_at=received_at,
        asset_class=asset_class,
        source_timezone=source_timezone,
    )
    evidence = RawEvidence(
        raw_block_id=raw_block_id,
        checksum=checksum,
        payload=payload,
        source_name=selected.name,
        source_locator=str(selected),
        media_type="text/csv",
        received_at=received_at,
    )
    result = ingest_staged_batch(
        database_path,
        batch=batch,
        evidence=evidence,
        run_kind="manual_file",
        merge_mode=merge_mode,
        outcome_facts={
            "checksum": checksum,
            "merge_mode": merge_mode,
            "provider": provider.strip().upper(),
            "source_filename": selected.name,
            "asset": (symbol or "").strip().upper(),
            "timeframe": normalized_timeframe or "",
            "source_timezone": source_timezone or "EXPLICIT_OFFSETS_IN_SOURCE",
            "source_timestamp_interpretations": ",".join(
                sorted({bar.source_timezone_interpretation for bar in batch.bars})
            ),
            "timestamp_provenance_contract": "RAW_BLOCK_EXACT_SOURCE_ROW_V1",
        },
        preserve_rejected_evidence=True,
        before_commit=before_commit,
    )
    if (
        result.transaction_state in {"committed", "COMPLETED_WITH_WARNINGS"}
        and batch.bars
        and batch.bars[0].timeframe != "D1"
    ):
        latest_date = datetime.fromtimestamp(
            max(bar.timestamp for bar in batch.bars), UTC
        ).date().isoformat()
        validate_lane(
            database_path,
            symbol=batch.bars[0].symbol,
            timeframe=batch.bars[0].timeframe,
            through_date=latest_date,
            persist=True,
            clock=clock,
        )
    return result


def _registered_asset_class(database_path: str | Path, symbol: str | None) -> str | None:
    if not symbol:
        return None
    connection = open_read_only(database_path)
    try:
        row = connection.execute(
            "SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
            (symbol.strip().upper(),),
        ).fetchone()
        return row[0] if row else None
    finally:
        connection.close()


__all__ = ["IngestionFailure", "IngestionResult", "ingest_manual_file"]
