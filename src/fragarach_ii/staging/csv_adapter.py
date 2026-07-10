"""UTF-8 CSV boundary adapter into the common staging contract."""

from __future__ import annotations

import csv
import io

from fragarach_ii.ingestion.validation import (
    RowValidationError,
    deduplicate_bars,
    stage_record,
)

from .contract import StagingBatch, StagingRejection


REQUIRED_FIELDS = frozenset({"timestamp", "open", "high", "low", "close"})
OPTIONAL_FIELDS = frozenset({"volume", "symbol", "timeframe"})
HEADER_ALIASES = {"time": "timestamp"}


def stage_csv_bytes(
    payload: bytes,
    *,
    symbol: str | None,
    timeframe: str | None,
    provider: str,
    raw_block_id: str,
    received_at: str,
) -> StagingBatch:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        return _file_rejection("INVALID_UTF8", str(error))

    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if reader.fieldnames is None:
            return _file_rejection("MISSING_HEADER", "CSV header row is required")
        physical_headers = [header.strip().lower() for header in reader.fieldnames]
        normalized_headers = [HEADER_ALIASES.get(header, header) for header in physical_headers]
        if any(not header for header in normalized_headers):
            return _file_rejection("INVALID_HEADER", "CSV contains an empty header")
        if len(set(normalized_headers)) != len(normalized_headers):
            return _file_rejection("DUPLICATE_HEADER", "CSV logical headers must be unique")
        missing = sorted(REQUIRED_FIELDS - set(normalized_headers))
        if missing:
            return _file_rejection(
                "MISSING_COLUMNS", f"required columns missing: {', '.join(missing)}"
            )
        unsupported = sorted(set(normalized_headers) - REQUIRED_FIELDS - OPTIONAL_FIELDS)
        if unsupported:
            return _file_rejection(
                "UNSUPPORTED_COLUMNS", f"unsupported columns: {', '.join(unsupported)}"
            )
        reader.fieldnames = normalized_headers

        bars = []
        rejections: list[StagingRejection] = []
        source_rows = 0
        for source_row_number, fields in enumerate(reader, start=2):
            source_rows += 1
            if None in fields:
                rejections.append(
                    StagingRejection(
                        source_row_number,
                        "EXTRA_FIELDS",
                        "row contains more fields than the header",
                    )
                )
                continue
            try:
                bars.append(
                    stage_record(
                        fields,
                        explicit_symbol=symbol,
                        explicit_timeframe=timeframe,
                        provider=provider,
                        raw_block_id=raw_block_id,
                        source_row_number=source_row_number,
                        received_at=received_at,
                    )
                )
            except RowValidationError as error:
                rejections.append(
                    StagingRejection(source_row_number, error.code, str(error))
                )
    except csv.Error as error:
        return _file_rejection("INVALID_CSV", str(error))

    if source_rows == 0:
        rejections.append(StagingRejection(1, "NO_DATA_ROWS", "CSV has no data rows"))
    deduplicated, duplicate_rejections, identical, conflicting = deduplicate_bars(bars)
    rejections.extend(duplicate_rejections)
    lanes = {(bar.symbol, bar.timeframe) for bar in deduplicated}
    if len(lanes) > 1:
        rejections.append(
            StagingRejection(
                1,
                "MULTIPLE_LANES",
                "one SPEC-002 manual file must resolve to one symbol/timeframe lane",
            )
        )
    return StagingBatch(
        bars=deduplicated,
        rejections=tuple(sorted(rejections, key=lambda item: (item.source_row_number, item.code))),
        source_rows=source_rows,
        duplicate_identical=identical,
        duplicate_conflicting=conflicting,
    )


def _file_rejection(code: str, message: str) -> StagingBatch:
    return StagingBatch((), (StagingRejection(1, code, message),), 0, 0, 0)
