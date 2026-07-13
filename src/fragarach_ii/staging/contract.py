"""Immutable provider-independent staging values for SPEC-002."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StagedBar:
    symbol: str
    timeframe: str
    timestamp: int
    open: str
    high: str
    low: str
    close: str
    volume: str | None
    source: str
    provider: str
    raw_block_id: str
    source_row_number: int
    source_timestamp_text: str
    source_timezone_interpretation: str
    received_at: str
    close_timestamp: int | None = None

    @property
    def canonical_key(self) -> tuple[str, str, int]:
        return (self.symbol, self.timeframe, self.timestamp)

    @property
    def values(self) -> tuple[str, str, str, str, str | None]:
        return (self.open, self.high, self.low, self.close, self.volume)


@dataclass(frozen=True, slots=True)
class StagingRejection:
    source_row_number: int
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class StagingBatch:
    bars: tuple[StagedBar, ...]
    rejections: tuple[StagingRejection, ...]
    source_rows: int
    duplicate_identical: int
    duplicate_conflicting: int
