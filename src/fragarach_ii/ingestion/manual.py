"""Manual-file adapter into the one staged-bar ingestion pipeline."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fragarach_ii.staging import stage_csv_bytes
from fragarach_ii.calendars import CalendarRegistry, ConfigurationError
from fragarach_ii.lane_commissioning import resolved_calendar_id
from fragarach_ii.operational_schedule import latest_closed_session_date
from fragarach_ii.storage import open_read_only
from fragarach_ii.validation import validate_lane
from fragarach_ii.execution_trace import timing_record
from fragarach_ii.publication_service import enqueue_publication

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
    d1_date_format: str = "AUTO",
    clock: Clock | None = None,
    before_commit: Callable[[sqlite3.Connection], None] | None = None,
    progress: Callable[[str], None] | None = None,
) -> IngestionResult:
    if merge_mode not in {"preserve", "correct"}:
        raise ValueError("merge mode must be 'preserve' or 'correct'")
    selected = Path(file_path).expanduser().resolve()
    operation_id = f"manual-import-{hashlib.sha256(str(selected).encode()).hexdigest()[:12]}"
    timing_trace: list[dict[str, object]] = []
    read_started = datetime.now(UTC)
    if progress is not None:
        progress("reading")
    payload = selected.read_bytes()
    read_completed = datetime.now(UTC)
    timing_trace.append(timing_record(
        operation_id=operation_id, symbol=symbol, timeframe=timeframe,
        intent="MANUAL_CSV_IMPORT", step_name="file_read",
        started_at=read_started, ended_at=read_completed, provider=provider,
        rows_read=payload.count(b"\n") - (1 if b"\n" in payload else 0),
    ))
    checksum = hashlib.sha256(payload).hexdigest()
    raw_block_id = f"raw-{checksum}"
    received_at = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC).isoformat()
    normalized_timeframe = timeframe.strip().upper() if timeframe else None
    d1_closed_boundary, has_d1_calendar = _latest_closed_d1_boundary(
        database_path,
        symbol=symbol,
        observed_at=datetime.fromisoformat(received_at),
    ) if normalized_timeframe == "D1" else (None, False)
    asset_class = _registered_asset_class(database_path, symbol) if normalized_timeframe != "D1" else None
    if progress is not None:
        progress("validating")
    validation_started = datetime.now(UTC)
    batch = stage_csv_bytes(
        payload,
        symbol=symbol,
        timeframe=timeframe,
        provider=provider,
        raw_block_id=raw_block_id,
        received_at=received_at,
        asset_class=asset_class,
        source_timezone=source_timezone,
        d1_date_format=d1_date_format,
        d1_latest_closed_date=d1_closed_boundary,
    )
    validation_completed = datetime.now(UTC)
    timing_trace.append(timing_record(
        operation_id=operation_id, symbol=symbol, timeframe=normalized_timeframe,
        intent="MANUAL_CSV_IMPORT", step_name="parse_and_validate",
        started_at=validation_started, ended_at=validation_completed, provider=provider,
        rows_read=len(batch.bars) + len(batch.rejections),
        blocking_reason=(batch.rejections[0].code if batch.rejections else None),
    ))
    evidence = RawEvidence(
        raw_block_id=raw_block_id,
        checksum=checksum,
        payload=payload,
        source_name=selected.name,
        source_locator=str(selected),
        media_type="text/csv",
        received_at=received_at,
    )
    if progress is not None:
        progress("ingesting")
    admission_started = datetime.now(UTC)
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
            "d1_date_format": d1_date_format.strip().upper().replace("-", "_"),
            "source_timestamp_interpretations": ",".join(
                sorted({bar.source_timezone_interpretation for bar in batch.bars})
            ),
            "timestamp_provenance_contract": "RAW_BLOCK_EXACT_SOURCE_ROW_V1",
        },
        preserve_rejected_evidence=True,
        before_commit=before_commit,
    )
    admission_completed = datetime.now(UTC)
    timing_trace.append(timing_record(
        operation_id=operation_id, symbol=symbol, timeframe=normalized_timeframe,
        intent="MANUAL_CSV_IMPORT", step_name="canonical_admission",
        started_at=admission_started, ended_at=admission_completed, provider=provider,
        rows_read=result.accepted, rows_written=result.inserted + result.corrected,
        blocking_reason=(result.rejections[0].get("code") if result.rejections else None),
    ))
    if result.transaction_state in {"committed", "COMPLETED_WITH_WARNINGS"} and batch.bars:
        lane_validation_started = datetime.now(UTC)
        if (
            (batch.bars[0].timeframe != "D1" or (result.inserted or result.corrected))
            and (batch.bars[0].timeframe != "D1" or has_d1_calendar)
        ):
            latest_date = (
                d1_closed_boundary.isoformat()
                if batch.bars[0].timeframe == "D1" and d1_closed_boundary is not None
                else datetime.fromtimestamp(
                    max(bar.timestamp for bar in batch.bars), UTC
                ).date().isoformat()
            )
            validate_lane(
                database_path,
                symbol=batch.bars[0].symbol,
                timeframe=batch.bars[0].timeframe,
                through_date=latest_date,
                persist=True,
                clock=clock,
            )
            timing_trace.append(timing_record(
                operation_id=operation_id, symbol=batch.bars[0].symbol,
                timeframe=batch.bars[0].timeframe, intent="MANUAL_CSV_IMPORT",
                step_name=("d1_lane_validation" if batch.bars[0].timeframe == "D1" else "intraday_lane_validation"),
                started_at=lane_validation_started, ended_at=datetime.now(UTC), provider=provider,
            ))
    # Canonical admission is already durable at this point.  Publication is a
    # separate, asynchronous concern so an import never waits on an Estate or
    # consumer catalogue projection.  Even a conflict-preserving import can
    # change consumer-visible availability through a newly declared lane.
    if (
        result.transaction_state in {"committed", "COMPLETED_WITH_WARNINGS"}
        and batch.bars
        and (result.inserted or result.corrected or result.canonical_count)
    ):
        enqueue_publication(
            database_path,
            [(batch.bars[0].symbol, batch.bars[0].timeframe)],
            trigger="MANUAL_CSV_IMPORT",
        )
    return replace(result, timing_trace=tuple(timing_trace))


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


def _latest_closed_d1_boundary(
    database_path: str | Path,
    *,
    symbol: str | None,
    observed_at: datetime,
) -> tuple[date, bool]:
    """Return the calendar-approved closed D1 boundary for a manual import.

    A TradingView daily export normally includes today's still-forming candle.
    It remains preserved in the raw evidence, but must not become canonical.
    Older unregistered databases retain the safe UTC-yesterday fallback used by
    the original manual-file bootstrap flow.
    """
    observed = observed_at.astimezone(UTC)
    if symbol:
        try:
            connection = open_read_only(database_path)
            try:
                row = connection.execute(
                    """
                    SELECT asset_class, calendar_id, exchange_name
                    FROM instrument_registrations
                    WHERE asset = ? AND timeframe = 'D1'
                    """,
                    (symbol.strip().upper(),),
                ).fetchone()
            except sqlite3.OperationalError:
                row = None
            finally:
                connection.close()
        except sqlite3.OperationalError:
            row = None
        if row is not None:
            calendar_id = resolved_calendar_id(
                asset_class=row[0],
                calendar_id=row[1],
                exchange_name=row[2],
                canonical_symbol=symbol.strip().upper(),
            )
            if calendar_id:
                try:
                    definition = CalendarRegistry(
                        load_symbol_assignments=False
                    ).calendar_by_id(calendar_id)
                    boundary = latest_closed_session_date(definition, observed)
                    if boundary is not None:
                        return boundary, True
                except ConfigurationError:
                    pass
    return observed.date() - timedelta(days=1), False


__all__ = ["IngestionFailure", "IngestionResult", "ingest_manual_file"]
