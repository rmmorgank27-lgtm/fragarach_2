"""Provider-neutral validation required after canonical evidence admission."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
import json
from pathlib import Path

from fragarach_ii.storage import open_read_only, registered_writer, transaction
from fragarach_ii.validation import validate_lane
from fragarach_ii.validation.intraday import validate_intraday_lane_incremental


@dataclass(frozen=True, slots=True)
class PersistedValidationView:
    """Small common view over a new or safely reused validation summary."""

    value: dict[str, object]
    reused: bool = False

    def as_dict(self) -> dict[str, object]:
        return dict(self.value)


def persist_committed_lane_validation(
    database_path: str | Path,
    *,
    asset: str,
    timeframe: str,
    through_date: str,
    clock: Callable[[], datetime] | None = None,
    canonical_inserts: int | None = None,
    canonical_corrections: int = 0,
    validator: Callable[..., object] = validate_lane,
):
    """Persist validation, avoiding full-lane work when authority did not change.

    Provider responses are immutable evidence, but a repeated response often
    produces zero canonical inserts or corrections.  Revalidating a 100,000
    bar M5 lane in that case cannot discover a new canonical fact: reuse the
    already-persisted summary.  Explicit validation commands and any canonical
    change still run the complete governed validator.
    """

    if canonical_inserts == 0 and canonical_corrections == 0:
        existing = _persisted_summary(database_path, asset=asset, timeframe=timeframe)
        if existing is not None:
            return PersistedValidationView(existing, reused=True)

    try:
        if (
            timeframe.strip().upper() != "D1"
            and canonical_inserts is not None
            and validator is validate_lane
        ):
            result = validate_intraday_lane_incremental(
                database_path, symbol=asset, timeframe=timeframe,
                through_date=_validation_date(through_date),
                canonical_inserts=canonical_inserts,
                canonical_corrections=canonical_corrections,
                persist=True, clock=clock,
            )
        else:
            result = validator(
                database_path,
                symbol=asset,
                timeframe=timeframe,
                through_date=_validation_date(through_date),
                persist=True,
                clock=clock,
            )
        return result
    except BaseException as error:
        try:
            with registered_writer(database_path) as connection:
                with transaction(connection):
                    connection.execute(
                        "UPDATE lane_state SET validation_summary=NULL WHERE asset=? AND timeframe=?",
                        (asset.strip().upper(), timeframe.strip().upper()),
                    )
        except BaseException as clear_error:
            from .twelve_data import AcquisitionError

            raise AcquisitionError(
                "POST_INGEST_VALIDATION_FAILED",
                "evidence committed, validation failed, and stale validation could not be cleared",
                evidence_committed=True,
            ) from clear_error

        from .twelve_data import AcquisitionError

        raise AcquisitionError(
            "POST_INGEST_VALIDATION_FAILED",
            f"evidence committed but validation failed: {type(error).__name__}",
            evidence_committed=True,
        ) from error


def _persisted_summary(
    database_path: str | Path, *, asset: str, timeframe: str
) -> dict[str, object] | None:
    connection = open_read_only(database_path)
    try:
        row = connection.execute(
            "SELECT validation_summary FROM lane_state WHERE asset=? AND timeframe=?",
            (asset.strip().upper(), timeframe.strip().upper()),
        ).fetchone()
    finally:
        connection.close()
    if row is None or row[0] is None:
        return None
    try:
        value = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _validation_date(value: str) -> str:
    """Convert a provider UTC boundary to the validator's calendar-date contract."""

    raw = str(value).strip()
    if len(raw) == 10:
        return date.fromisoformat(raw).isoformat()
    normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("provider validation boundary must declare a UTC offset")
    return parsed.astimezone(UTC).date().isoformat()
