"""Manual-file adapter into the one staged-bar ingestion pipeline."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.staging import stage_csv_bytes

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
    batch = stage_csv_bytes(
        payload,
        symbol=symbol,
        timeframe=timeframe,
        provider=provider,
        raw_block_id=raw_block_id,
        received_at=received_at,
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
    return ingest_staged_batch(
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
        },
        preserve_rejected_evidence=True,
        before_commit=before_commit,
    )


__all__ = ["IngestionFailure", "IngestionResult", "ingest_manual_file"]
