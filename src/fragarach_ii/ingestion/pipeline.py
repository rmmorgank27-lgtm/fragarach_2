"""The one writer-controlled staged-bar ingestion pipeline."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.staging import StagingBatch
from fragarach_ii.storage import Rejection, canonical_ingest_outcome, registered_writer, transaction
from fragarach_ii.storage.migrations import apply_migrations

from .merge import MergeCounts, merge_staged_bars


@dataclass(frozen=True, slots=True)
class RawEvidence:
    raw_block_id: str
    checksum: str
    payload: bytes
    source_name: str
    source_locator: str
    media_type: str
    received_at: str


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
        super().__init__(f"staged ingestion failed: {cause}")


def ingest_staged_batch(
    database_path: str | Path,
    *,
    batch: StagingBatch,
    evidence: RawEvidence,
    run_kind: str,
    merge_mode: str,
    outcome_facts: Mapping[str, str | int | bool],
    preserve_rejected_evidence: bool,
    before_commit: Callable[[sqlite3.Connection], None] | None = None,
) -> IngestionResult:
    if merge_mode not in {"preserve", "correct"}:
        raise ValueError("merge mode must be 'preserve' or 'correct'")
    ingest_run_id = uuid.uuid4().hex
    with registered_writer(database_path) as connection:
        apply_migrations(connection)
        if batch.bars:
            _require_registration(connection, batch.bars[0].symbol, batch.bars[0].timeframe)
        if batch.rejections:
            if not preserve_rejected_evidence:
                raise ValueError("rejected staged provider evidence is not persistable")
            with transaction(connection):
                reused = _ensure_raw_block(connection, evidence)
                _record_active_run(
                    connection, ingest_run_id, evidence.raw_block_id, evidence.received_at, run_kind
                )
                detail = _outcome_json(batch, MergeCounts(), 0, outcome_facts, reused)
                _finish_run(connection, ingest_run_id, "failed", evidence.received_at, detail)
            return _result(
                connection, batch, MergeCounts(), ingest_run_id, evidence,
                "failed", reused, accepted=0
            )

        try:
            with transaction(connection):
                reused = _ensure_raw_block(connection, evidence)
                _record_active_run(
                    connection, ingest_run_id, evidence.raw_block_id, evidence.received_at, run_kind
                )
                counts = merge_staged_bars(
                    connection,
                    batch.bars,
                    ingest_run_id=ingest_run_id,
                    merge_mode=merge_mode,
                    recorded_at=evidence.received_at,
                )
                if counts.canonical_mutations:
                    _refresh_lane_state(connection, batch, ingest_run_id, evidence.received_at)
                _confirm_registration_evidence(connection, batch.bars[0].symbol, batch.bars[0].timeframe, evidence.received_at)
                if before_commit is not None:
                    before_commit(connection)
                detail = _outcome_json(
                    batch, counts, len(batch.bars), outcome_facts, reused
                )
                _finish_run(
                    connection, ingest_run_id, "committed", evidence.received_at, detail
                )
        except BaseException as error:
            with transaction(connection):
                failure_reused = _ensure_raw_block(connection, evidence)
                _record_active_run(
                    connection, ingest_run_id, evidence.raw_block_id, evidence.received_at, run_kind
                )
                detail = canonical_ingest_outcome(
                    rejected=1,
                    rejections=(Rejection(0, "UNEXPECTED_FAILURE", str(error)),),
                    facts={**outcome_facts, "accepted": 0, "raw_block_reused": failure_reused},
                )
                _finish_run(connection, ingest_run_id, "failed", evidence.received_at, detail)
            raise IngestionFailure(
                ingest_run_id, evidence.raw_block_id, evidence.checksum, error
            ) from error
        return _result(
            connection, batch, counts, ingest_run_id, evidence,
            "committed", reused, accepted=len(batch.bars)
        )


def _ensure_raw_block(connection: sqlite3.Connection, evidence: RawEvidence) -> bool:
    existing = connection.execute(
        "SELECT raw_block_id, byte_length, payload FROM raw_blocks WHERE sha256 = ?",
        (evidence.checksum,),
    ).fetchone()
    if existing is not None:
        if existing != (evidence.raw_block_id, len(evidence.payload), evidence.payload):
            raise RuntimeError("checksum-identified raw evidence does not match stored bytes")
        return True
    connection.execute(
        """
        INSERT INTO raw_blocks (
            raw_block_id, sha256, source_name, source_locator, media_type,
            received_at_utc, byte_length, payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence.raw_block_id, evidence.checksum, evidence.source_name,
            evidence.source_locator, evidence.media_type, evidence.received_at,
            len(evidence.payload), evidence.payload,
        ),
    )
    return False


def _require_registration(connection: sqlite3.Connection, symbol: str, timeframe: str) -> None:
    if connection.execute("SELECT 1 FROM authority_events WHERE event_kind IN ('REGISTRATION_SUPERSEDED','LANE_SUPERSEDED') AND json_extract(canonical_payload,'$.body.asset')=? AND (json_extract(canonical_payload,'$.body.scope')='WHOLE_INSTRUMENT' OR json_extract(canonical_payload,'$.body.timeframe')=?)",(symbol,timeframe)).fetchone() is not None:
        raise ValueError(f"INSTRUMENT_RETIRED: {symbol}:{timeframe}")
    if connection.execute("""SELECT 1 FROM evidence_lanes l JOIN instrument_registrations r
      ON r.asset=l.asset AND r.timeframe=l.registration_timeframe
      WHERE l.asset=? AND l.timeframe=?""",(symbol,timeframe)).fetchone() is None:
        raise ValueError(f"UNREGISTERED_LANE: {symbol}:{timeframe}")


def _confirm_registration_evidence(connection: sqlite3.Connection, symbol: str, timeframe: str, observed_at: str) -> None:
    row=connection.execute("SELECT registration_status FROM instrument_registrations WHERE asset=? AND timeframe=?",(symbol,timeframe)).fetchone()
    if row == ("REGISTERED_NO_EVIDENCE",):
        connection.execute("UPDATE instrument_registrations SET registration_status='REGISTERED_WITH_EVIDENCE',evidence_confirmed_at_utc=? WHERE asset=? AND timeframe=?",(observed_at,symbol,timeframe))
    mismatch=connection.execute("""SELECT 1 FROM instrument_registrations r WHERE r.asset=? AND r.timeframe=? AND
      ((r.registration_status='REGISTERED_WITH_EVIDENCE') <> EXISTS(SELECT 1 FROM bars b WHERE b.asset=r.asset AND b.timeframe=r.timeframe))""",(symbol,timeframe)).fetchone()
    if mismatch: raise RuntimeError("registration evidence status invariant failed")


def _record_active_run(
    connection: sqlite3.Connection,
    run_id: str,
    raw_block_id: str,
    started_at: str,
    run_kind: str,
) -> None:
    connection.execute(
        """
        INSERT INTO ingest_runs (
            ingest_run_id, kind, status, started_at_utc, raw_block_id
        ) VALUES (?, ?, 'active', ?, ?)
        """,
        (run_id, run_kind, started_at, raw_block_id),
    )


def _finish_run(
    connection: sqlite3.Connection,
    run_id: str,
    status: str,
    finished_at: str,
    detail: str,
) -> None:
    connection.execute(
        """UPDATE ingest_runs SET status=?, finished_at_utc=?, detail=?
           WHERE ingest_run_id=?""",
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
        "SELECT max(open_time_utc) FROM bars WHERE asset=? AND timeframe=?",
        (symbol, timeframe),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO lane_state (
            asset,timeframe,high_watermark_open_time_utc,state_version,
            last_ingest_run_id,updated_at_utc
        ) VALUES (?,?,?,1,?,?)
        ON CONFLICT (asset,timeframe) DO UPDATE SET
            high_watermark_open_time_utc=excluded.high_watermark_open_time_utc,
            state_version=lane_state.state_version+1,
            last_ingest_run_id=excluded.last_ingest_run_id,
            updated_at_utc=excluded.updated_at_utc
        """,
        (symbol, timeframe, latest, run_id, updated_at),
    )


def _outcome_json(
    batch: StagingBatch,
    counts: MergeCounts,
    accepted: int,
    facts: Mapping[str, str | int | bool],
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
            **facts,
            "accepted": accepted,
            "duplicate_conflicting": batch.duplicate_conflicting,
            "duplicate_identical": batch.duplicate_identical,
            "raw_block_reused": reused,
        },
    )


def _result(
    connection: sqlite3.Connection,
    batch: StagingBatch,
    counts: MergeCounts,
    run_id: str,
    evidence: RawEvidence,
    state: str,
    reused: bool,
    *,
    accepted: int,
) -> IngestionResult:
    symbol = batch.bars[0].symbol if batch.bars else ""
    timeframe = batch.bars[0].timeframe if batch.bars else ""
    earliest = latest = None
    canonical_count = 0
    if symbol and timeframe:
        earliest_epoch, latest_epoch, canonical_count = connection.execute(
            """SELECT min(open_time_utc),max(open_time_utc),count(*) FROM bars
               WHERE asset=? AND timeframe=?""",
            (symbol, timeframe),
        ).fetchone()
        earliest = _epoch_iso(earliest_epoch)
        latest = _epoch_iso(latest_epoch)
    return IngestionResult(
        ingest_run_id=run_id, raw_block_id=evidence.raw_block_id,
        checksum=evidence.checksum, source_rows=batch.source_rows,
        staged=len(batch.bars), accepted=accepted, inserted=counts.inserted,
        corrected=counts.corrected, unchanged=counts.unchanged,
        conflicts_preserved=counts.conflicts_preserved,
        rejected=len(batch.rejections), duplicate_identical=batch.duplicate_identical,
        duplicate_conflicting=batch.duplicate_conflicting, earliest=earliest,
        latest=latest, canonical_count=canonical_count, transaction_state=state,
        raw_block_reused=reused,
        rejections=tuple(
            {"source_row_number": item.source_row_number, "code": item.code, "message": item.message}
            for item in batch.rejections
        ),
    )


def _epoch_iso(value: int | None) -> str | None:
    return datetime.fromtimestamp(value, UTC).isoformat() if value is not None else None
