"""Canonical run-outcome JSON contract introduced by SPEC-001A."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Mapping


OUTCOME_FORMAT = "fragarach_ii.ingest_outcome.v1"


@dataclass(frozen=True, slots=True)
class Rejection:
    source_row_number: int
    code: str
    message: str

    def __post_init__(self) -> None:
        if self.source_row_number < 0:
            raise ValueError("source row number must be non-negative")
        if not self.code:
            raise ValueError("rejection code must not be empty")
        if not self.message:
            raise ValueError("rejection message must not be empty")


def canonical_ingest_outcome(
    *,
    source_rows: int = 0,
    staged: int = 0,
    inserted: int = 0,
    corrected: int = 0,
    unchanged: int = 0,
    conflicts_preserved: int = 0,
    rejected: int = 0,
    rejections: Iterable[Rejection] = (),
    facts: Mapping[str, str | int | bool] | None = None,
) -> str:
    """Serialize an outcome deterministically for equivalent factual input."""

    counts = {
        "source_rows": source_rows,
        "staged": staged,
        "inserted": inserted,
        "corrected": corrected,
        "unchanged": unchanged,
        "conflicts_preserved": conflicts_preserved,
        "rejected": rejected,
    }
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts.values()):
        raise ValueError("outcome counts must be non-negative integers")
    rejection_values = sorted(
        (
            {
                "source_row_number": rejection.source_row_number,
                "code": rejection.code,
                "message": rejection.message,
            }
            for rejection in rejections
        ),
        key=lambda value: (
            value["source_row_number"],
            value["code"],
            value["message"],
        ),
    )
    payload = {
        "format": OUTCOME_FORMAT,
        **counts,
        "rejections": rejection_values,
    }
    reserved = set(payload)
    for key, value in sorted((facts or {}).items()):
        if key in reserved:
            raise ValueError(f"factual outcome key is reserved: {key}")
        if not key or not isinstance(value, (str, int, bool)):
            raise ValueError("additional outcome facts must be named JSON scalars")
        payload[key] = value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
