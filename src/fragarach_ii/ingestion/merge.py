"""Deterministic canonical merge for the single SPEC-002 pipeline."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from typing import Callable, Iterable

from fragarach_ii.staging.contract import StagedBar


EventIdFactory = Callable[[], str]


@dataclass(frozen=True, slots=True)
class MergeCounts:
    inserted: int = 0
    corrected: int = 0
    unchanged: int = 0
    conflicts_preserved: int = 0

    @property
    def canonical_mutations(self) -> int:
        return self.inserted + self.corrected


def merge_staged_bars(
    connection: sqlite3.Connection,
    bars: Iterable[StagedBar],
    *,
    ingest_run_id: str,
    merge_mode: str,
    recorded_at: str,
    event_id_factory: EventIdFactory | None = None,
) -> MergeCounts:
    if merge_mode not in {"preserve", "correct"}:
        raise ValueError("merge mode must be 'preserve' or 'correct'")
    create_event_id = event_id_factory or (lambda: uuid.uuid4().hex)
    inserted = corrected = unchanged = conflicts = 0
    for bar in sorted(bars, key=lambda value: value.canonical_key):
        current = connection.execute(
            """
            SELECT open, high, low, close, volume, updated_by_ingest_run_id
            FROM bars
            WHERE asset = ? AND timeframe = ? AND open_time_utc = ?
            """,
            bar.canonical_key,
        ).fetchone()
        event_id = create_event_id()
        if current is None:
            connection.execute(
                """
                INSERT INTO bars (
                    asset, timeframe, open_time_utc, open, high, low, close, volume,
                    created_by_ingest_run_id, updated_by_ingest_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*bar.canonical_key, *bar.values, ingest_run_id, ingest_run_id),
            )
            _append_event(
                connection,
                event_id=event_id,
                run_id=ingest_run_id,
                bar=bar,
                action="INSERT",
                prior=None,
                supersedes=None,
                recorded_at=recorded_at,
            )
            inserted += 1
            continue

        prior = tuple(current[:5])
        if prior == bar.values:
            action = "UNCHANGED"
            unchanged += 1
            supersedes = None
        elif merge_mode == "preserve":
            action = "CONFLICT_PRESERVED"
            conflicts += 1
            supersedes = None
        else:
            action = "CORRECTED"
            supersedes_row = connection.execute(
                """
                SELECT provenance_event_id
                FROM provenance
                WHERE symbol = ? AND timeframe = ? AND timestamp = ?
                  AND ingest_run_id = ?
                  AND merge_action IN ('INSERT', 'CORRECTED')
                ORDER BY recorded_at DESC, provenance_event_id DESC
                LIMIT 1
                """,
                (*bar.canonical_key, current[5]),
            ).fetchone()
            if supersedes_row is None:
                raise RuntimeError(
                    f"canonical bar {bar.canonical_key!r} has no supporting provenance event"
                )
            supersedes = supersedes_row[0]
            connection.execute(
                """
                UPDATE bars
                SET open = ?, high = ?, low = ?, close = ?, volume = ?,
                    updated_by_ingest_run_id = ?
                WHERE asset = ? AND timeframe = ? AND open_time_utc = ?
                """,
                (*bar.values, ingest_run_id, *bar.canonical_key),
            )
            corrected += 1
        _append_event(
            connection,
            event_id=event_id,
            run_id=ingest_run_id,
            bar=bar,
            action=action,
            prior=prior,
            supersedes=supersedes,
            recorded_at=recorded_at,
        )
    return MergeCounts(inserted, corrected, unchanged, conflicts)


def _append_event(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    run_id: str,
    bar: StagedBar,
    action: str,
    prior: tuple[str, str, str, str, str | None] | None,
    supersedes: str | None,
    recorded_at: str,
) -> None:
    prior_values = prior or (None, None, None, None, None)
    connection.execute(
        """
        INSERT INTO provenance (
            provenance_event_id, ingest_run_id, raw_block_id, symbol, timeframe,
            timestamp, source_row_number, merge_action,
            candidate_open, candidate_high, candidate_low, candidate_close,
            candidate_volume, prior_open, prior_high, prior_low, prior_close,
            prior_volume, supersedes_event_id, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            run_id,
            bar.raw_block_id,
            *bar.canonical_key,
            bar.source_row_number,
            action,
            *bar.values,
            *prior_values,
            supersedes,
            recorded_at,
        ),
    )

