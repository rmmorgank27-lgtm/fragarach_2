"""One writer-controlled manual-file ingestion path for SPEC-002."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.staging import StagingBatch, stage_csv_bytes
from fragarach_ii.storage import (
    Rejection,
    canonical_ingest_outcome,
    registered_writer,
    transaction,
)
from fragarach_ii.storage.migrations import apply_migrations

from .merge import MergeCounts, merge_staged_bars


Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class IngestionResult:
    ingest_run_id: str
    raw_block_id: str
    checksum: str
    source_rows: int
    staged: int
    accepted: int
    inserted: int
    corrected: int
    unchanged: int
    conflicts_preserved: int
    rejected: int
    duplicate_identical: int
    duplicate_conflicting: int
    earliest: str | None
    latest: str | None
    canonical_count: int
    transaction_state: str
    raw_block_reused: bool
    rejections: tuple[dict[str, object], ...] = ()

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))


class IngestionFailure(RuntimeError):
    def __init__(
        self, ingest_run_id: str, raw_block_id: str, checksum: str, cause: BaseException
    ) -> None:
        self.ingest_run_id = ingest_run_id
        self.raw_block_id = raw_block_id
        self.checksum = checksum
        self.cause = cause
        super().__init__(f"manual ingestion failed: {cause}")


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
    """Preserve and process one selected UTF-8 CSV through the sole pipeline."""

    if merge_mode not in {"preserve", "correct"}:
        raise ValueError("merge mode must be 'preserve' or 'correct'")
    selected = Path(file_path).expanduser().resolve()
    payload = selected.read_bytes()
    checksum = hashlib.sha256(payload).hexdigest()
    raw_block_id = f"raw-{checksum}"
    now = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC).isoformat()
    ingest_run_id = uuid.uuid4().hex
    batch = stage_csv_bytes(
        payload,
        symbol=symbol,
        timeframe=timeframe,
        provider=provider,
        raw_block_id=raw_block_id,
        received_at=now,
    )

    with registered_writer(database_path) as connection:
        apply_migrations(connection)
        if batch.rejections:
            with transaction(connection):
                reused = _ensure_raw_block(
                    connection, selected, payload, checksum, raw_block_id, now
                )
                _record_active_run(connection, ingest_run_id, raw_block_id, now)
                detail = _outcome_json(
                    batch,
                    MergeCounts(),
                    accepted=0,
                    selected=selected,
                    merge_mode=merge_mode,
                    provider=provider,
                    checksum=checksum,
                    reused=reused,
                )
                _finish_run(connection, ingest_run_id, "failed", now, detail)
            return _result(
                connection,
                batch,
                MergeCounts(),
                ingest_run_id,
                raw_block_id,
                checksum,
                "failed",
                reused,
                accepted=0,
                symbol=symbol,
                timeframe=timeframe,
            )

        try:
            with transaction(connection):
                reused = _ensure_raw_block(
                    connection, selected, payload, checksum, raw_block_id, now
                )
                _record_active_run(connection, ingest_run_id, raw_block_id, now)
                counts = merge_staged_bars(
                    connection,
                    batch.bars,
                    ingest_run_id=ingest_run_id,
                    merge_mode=merge_mode,
                    recorded_at=now,
                )
                if counts.canonical_mutations:
                    _refresh_lane_state(connection, batch, ingest_run_id, now)
                if before_commit is not None:
                    before_commit(connection)
                detail = _outcome_json(
                    batch,
                    counts,
                    accepted=len(batch.bars),
                    selected=selected,
                    merge_mode=merge_mode,
                    provider=batch.bars[0].provider,
                    checksum=checksum,
                    reused=reused,
                )
                _finish_run(connection, ingest_run_id, "committed", now, detail)
        except BaseException as error:
            failure = Rejection(0, "UNEXPECTED_FAILURE", str(error))
            with transaction(connection):
                failure_reused = _ensure_raw_block(
                    connection, selected, payload, checksum, raw_block_id, now
                )
                _record_active_run(connection, ingest_run_id, raw_block_id, now)
                detail = canonical_ingest_outcome(
                    rejected=1,
                    rejections=(failure,),
                    facts={
                        "accepted": 0,
                        "checksum": checksum,
                        "duplicate_conflicting": batch.duplicate_conflicting,
                        "duplicate_identical": batch.duplicate_identical,
                        "merge_mode": merge_mode,
                        "provider": provider.strip().upper(),
                        "raw_block_reused": failure_reused,
                        "source_filename": selected.name,
                    },
                )
                _finish_run(connection, ingest_run_id, "failed", now, detail)
            raise IngestionFailure(ingest_run_id, raw_block_id, checksum, error) from error

        return _result(
            connection,
            batch,
            counts,
            ingest_run_id,
            raw_block_id,
            checksum,
            "committed",
            reused,
            accepted=len(batch.bars),
            symbol=batch.bars[0].symbol,
            timeframe=batch.bars[0].timeframe,
        )


def _ensure_raw_block(
    connection: sqlite3.Connection,
    selected: Path,
    payload: bytes,
    checksum: str,
    raw_block_id: str,
    received_at: str,
) -> bool:
    existing = connection.execute(
        "SELECT raw_block_id, byte_length, payload FROM raw_blocks WHERE sha256 = ?",
        (checksum,),
    ).fetchone()
    if existing is not None:
        if existing != (raw_block_id, len(payload), payload):
            raise RuntimeError("checksum-identified raw evidence does not match stored bytes")
        return True
    connection.execute(
        """
        INSERT INTO raw_blocks (
            raw_block_id, sha256, source_name, source_locator, media_type,
            received_at_utc, byte_length, payload
        ) VALUES (?, ?, ?, ?, 'text/csv', ?, ?, ?)
        """,
        (
            raw_block_id,
            checksum,
            selected.name,
            str(selected),
            received_at,
            len(payload),
            payload,
        ),
    )
    return False


def _record_active_run(
    connection: sqlite3.Connection, run_id: str, raw_block_id: str, started_at: str
) -> None:
    connection.execute(
        """
        INSERT INTO ingest_runs (
            ingest_run_id, kind, status, started_at_utc, raw_block_id
        ) VALUES (?, 'manual_file', 'active', ?, ?)
        """,
        (run_id, started_at, raw_block_id),
    )


def _finish_run(
    connection: sqlite3.Connection,
    run_id: str,
    status: str,
    finished_at: str,
    detail: str,
) -> None:
    connection.execute(
        """
        UPDATE ingest_runs
        SET status = ?, finished_at_utc = ?, detail = ?
        WHERE ingest_run_id = ?
        """,
        (status, finished_at, detail, run_id),
    )


def _refresh_lane_state(
    connection: sqlite3.Connection,
    batch: StagingBatch,
    run_id: str,
    updated_at: str,
) -> None:
    symbol, timeframe = batch.bars[0].symbol, batch.bars[0].timeframe
    latest = connection.execute(
        "SELECT max(open_time_utc) FROM bars WHERE asset = ? AND timeframe = ?",
        (symbol, timeframe),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO lane_state (
            asset, timeframe, high_watermark_open_time_utc, state_version,
            last_ingest_run_id, updated_at_utc
        ) VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT (asset, timeframe) DO UPDATE SET
            high_watermark_open_time_utc = excluded.high_watermark_open_time_utc,
            state_version = lane_state.state_version + 1,
            last_ingest_run_id = excluded.last_ingest_run_id,
            updated_at_utc = excluded.updated_at_utc
        """,
        (symbol, timeframe, latest, run_id, updated_at),
    )


def _outcome_json(
    batch: StagingBatch,
    counts: MergeCounts,
    *,
    accepted: int,
    selected: Path,
    merge_mode: str,
    provider: str,
    checksum: str,
    reused: bool,
) -> str:
    return canonical_ingest_outcome(
        source_rows=batch.source_rows,
        staged=len(batch.bars),
        inserted=counts.inserted,
        corrected=counts.corrected,
        unchanged=counts.unchanged,
        conflicts_preserved=counts.conflicts_preserved,
        rejected=len(batch.rejections),
        rejections=tuple(
            Rejection(item.source_row_number, item.code, item.message)
            for item in batch.rejections
        ),
        facts={
            "accepted": accepted,
            "checksum": checksum,
            "duplicate_conflicting": batch.duplicate_conflicting,
            "duplicate_identical": batch.duplicate_identical,
            "merge_mode": merge_mode,
            "provider": provider.strip().upper(),
            "raw_block_reused": reused,
            "source_filename": selected.name,
        },
    )


def _result(
    connection: sqlite3.Connection,
    batch: StagingBatch,
    counts: MergeCounts,
    run_id: str,
    raw_block_id: str,
    checksum: str,
    state: str,
    reused: bool,
    *,
    accepted: int,
    symbol: str | None,
    timeframe: str | None,
) -> IngestionResult:
    lane_symbol = batch.bars[0].symbol if batch.bars else (symbol or "").strip().upper()
    lane_timeframe = (
        batch.bars[0].timeframe if batch.bars else (timeframe or "").strip().upper()
    )
    earliest = latest = None
    canonical_count = 0
    if lane_symbol and lane_timeframe:
        earliest_epoch, latest_epoch, canonical_count = connection.execute(
            """
            SELECT min(open_time_utc), max(open_time_utc), count(*)
            FROM bars WHERE asset = ? AND timeframe = ?
            """,
            (lane_symbol, lane_timeframe),
        ).fetchone()
        earliest = _epoch_iso(earliest_epoch)
        latest = _epoch_iso(latest_epoch)
    return IngestionResult(
        ingest_run_id=run_id,
        raw_block_id=raw_block_id,
        checksum=checksum,
        source_rows=batch.source_rows,
        staged=len(batch.bars),
        accepted=accepted,
        inserted=counts.inserted,
        corrected=counts.corrected,
        unchanged=counts.unchanged,
        conflicts_preserved=counts.conflicts_preserved,
        rejected=len(batch.rejections),
        duplicate_identical=batch.duplicate_identical,
        duplicate_conflicting=batch.duplicate_conflicting,
        earliest=earliest,
        latest=latest,
        canonical_count=canonical_count,
        transaction_state=state,
        raw_block_reused=reused,
        rejections=tuple(
            {
                "source_row_number": item.source_row_number,
                "code": item.code,
                "message": item.message,
            }
            for item in batch.rejections
        ),
    )


def _epoch_iso(value: int | None) -> str | None:
    return datetime.fromtimestamp(value, UTC).isoformat() if value is not None else None
