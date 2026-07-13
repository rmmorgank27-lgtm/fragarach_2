"""UTF-8 CSV boundary adapter into the common staging contract."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from fragarach_ii.ingestion.validation import (
    RowValidationError,
    deduplicate_bars,
    stage_record,
)

from .contract import StagingBatch, StagingRejection
from fragarach_ii.validation.intraday_profiles import (
    is_aligned_open,
    is_expected_open,
    profile_for,
)


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
    asset_class: str | None = None,
    source_timezone: str | None = None,
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
                bar = stage_record(
                        fields,
                        explicit_symbol=symbol,
                        explicit_timeframe=timeframe,
                        provider=provider,
                        source="MANUAL_FILE",
                        raw_block_id=raw_block_id,
                        source_row_number=source_row_number,
                        received_at=received_at,
                        source_timezone=source_timezone,
                    )
                if bar.timeframe != "D1":
                    if asset_class is None:
                        raise RowValidationError(
                            "INTRADAY_PROFILE_NOT_REVIEWED",
                            "intraday CSV staging requires the registered asset class",
                        )
                    profile = profile_for(asset_class, bar.timeframe)
                    if not is_aligned_open(bar.timestamp, profile):
                        raise RowValidationError(
                            "MISALIGNED_INTERVAL_OPEN",
                            "canonical UTC instant is not aligned to the authorised interval",
                        )
                    if not is_expected_open(bar.timestamp, profile):
                        raise RowValidationError(
                            "OUTSIDE_EXPECTED_SESSION",
                            "canonical UTC instant is outside the authorised session",
                        )
                    observed = datetime.fromisoformat(received_at).astimezone(UTC)
                    if bar.close_timestamp is None or bar.close_timestamp > int(observed.timestamp()):
                        raise RowValidationError(
                            "INCOMPLETE_CURRENT_INTERVAL",
                            "interval was not closed when the source was admitted",
                        )
                bars.append(bar)
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
