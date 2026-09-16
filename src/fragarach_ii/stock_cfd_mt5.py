"""Promote reviewed Global Prime stock-CFD evidence without changing D1 identity."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from .ingestion.pipeline import RawEvidence, ingest_staged_batch
from .publication_service import enqueue_publication, resume_pending_publications
from .staging import StagedBar, StagingBatch
from .storage import (
    AuthorityEventManifest,
    append_authority_event,
    open_read_only,
    registered_writer,
    transaction,
)
from .storage.migrations import apply_migrations
from .validation import validate_lane


CONTRACT = "fragarach_ii.global_prime_stock_cfd_overlay.v1"
AUTHORITY_ID = "GLOBAL_PRIME_STOCK_CFD_INTRADAY_OVERLAY_V1"
PROVIDER = "GLOBAL_PRIME_MT5"
TERMINAL_SYMBOL = "ExxonMobil"
CANONICAL_SYMBOL = "XOM"
NATIVE_TIMEFRAMES = ("M5", "M15")
OUTPUT_TIMEFRAMES = ("M5", "M15", "M30", "H1")
DURATIONS = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600}
SOURCE_TIMESTAMP_STATUS = "TIMESTAMP_AUTHORITY_UNRESOLVED"
CANONICAL_TIMESTAMP_POLICY = "NYSE_REGULAR_SESSION_ORDINAL_ALIGNMENT_V1"
REQUIRED_HEADERS = {
    "mt5_time", "mt5_documented_utc_rendering", "open", "high", "low", "close",
    "tick_volume", "spread", "real_volume",
}


class StockCFDAdmissionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StockCFDBar:
    timestamp: datetime
    raw_timestamp: int
    raw_rendering: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source_row_number: int


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _normal(value: Decimal) -> str:
    return format(value, "f")


def _canonical_open(raw_timestamp: int) -> datetime | None:
    raw = datetime.fromtimestamp(raw_timestamp, UTC)
    raw_clock = raw.timetz().replace(tzinfo=None)
    if raw.weekday() >= 5 or not (time(16, 30) <= raw_clock < time(23, 0)):
        return None
    session_open = datetime.combine(raw.date(), time(9, 30), ZoneInfo("America/New_York"))
    return session_open.astimezone(UTC) + (raw - datetime.combine(raw.date(), time(16, 30), UTC))


def read_native_csv(path: str | Path, timeframe: str) -> tuple[bytes, tuple[StockCFDBar, ...]]:
    timeframe = timeframe.strip().upper()
    if timeframe not in NATIVE_TIMEFRAMES:
        raise StockCFDAdmissionError(f"NATIVE_TIMEFRAME_REQUIRED:{timeframe}")
    selected = Path(path).expanduser().resolve()
    if selected.name != f"{TERMINAL_SYMBOL}_{timeframe}.csv":
        raise StockCFDAdmissionError(f"EXACT_TERMINAL_FILE_REQUIRED:{TERMINAL_SYMBOL}_{timeframe}.csv")
    payload = selected.read_bytes()
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True)
    headers = {str(value).strip() for value in (reader.fieldnames or ())}
    if headers != REQUIRED_HEADERS:
        raise StockCFDAdmissionError(f"SCHEMA_MISMATCH:{sorted(headers)}")
    bars: list[StockCFDBar] = []
    previous_raw: int | None = None
    previous_canonical: datetime | None = None
    for source_row_number, row in enumerate(reader, start=2):
        try:
            raw_timestamp = int(row["mt5_time"])
            values = tuple(Decimal(str(row[key]).strip()) for key in ("open", "high", "low", "close"))
            volume = Decimal(str(row["tick_volume"]).strip())
            spread = Decimal(str(row["spread"]).strip())
            real_volume = Decimal(str(row["real_volume"]).strip())
        except (KeyError, TypeError, ValueError, InvalidOperation) as error:
            raise StockCFDAdmissionError(f"INVALID_ROW:{timeframe}:{source_row_number}") from error
        if previous_raw is not None and raw_timestamp <= previous_raw:
            raise StockCFDAdmissionError(f"RAW_TIMESTAMP_ORDER:{timeframe}:{source_row_number}")
        previous_raw = raw_timestamp
        rendered = datetime.fromtimestamp(raw_timestamp, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        if row["mt5_documented_utc_rendering"] != rendered:
            raise StockCFDAdmissionError(f"RAW_RENDERING_MISMATCH:{timeframe}:{source_row_number}")
        canonical = _canonical_open(raw_timestamp)
        if canonical is None:
            continue
        seconds = DURATIONS[timeframe]
        if int(canonical.timestamp()) % seconds:
            raise StockCFDAdmissionError(f"CANONICAL_GRID_MISMATCH:{timeframe}:{source_row_number}")
        opened, high, low, closed = values
        if min(values) <= 0 or high < max(opened, low, closed) or low > min(opened, high, closed):
            raise StockCFDAdmissionError(f"OHLC_INVALID:{timeframe}:{source_row_number}")
        if min(volume, spread, real_volume) < 0:
            raise StockCFDAdmissionError(f"VOLUME_OR_SPREAD_INVALID:{timeframe}:{source_row_number}")
        if previous_canonical is not None and canonical <= previous_canonical:
            raise StockCFDAdmissionError(f"CANONICAL_TIMESTAMP_ORDER:{timeframe}:{source_row_number}")
        bars.append(StockCFDBar(
            canonical, raw_timestamp, rendered, opened, high, low, closed, volume, source_row_number,
        ))
        previous_canonical = canonical
    if not bars:
        raise StockCFDAdmissionError(f"NO_REGULAR_SESSION_ROWS:{timeframe}")
    return payload, tuple(bars)


def rollup(bars: tuple[StockCFDBar, ...], timeframe: str) -> tuple[StockCFDBar, ...]:
    timeframe = timeframe.strip().upper()
    seconds = DURATIONS.get(timeframe)
    if timeframe not in {"M15", "M30", "H1"} or seconds is None:
        raise StockCFDAdmissionError(f"UNSUPPORTED_ROLLUP:{timeframe}")
    source_seconds = 300 if timeframe == "M15" else 900
    expected_count = seconds // source_seconds
    grouped: dict[int, list[StockCFDBar]] = defaultdict(list)
    for bar in bars:
        opened = int(bar.timestamp.timestamp())
        grouped[opened - opened % seconds].append(bar)
    output: list[StockCFDBar] = []
    for opened, components in sorted(grouped.items()):
        components.sort(key=lambda item: item.timestamp)
        if [int(item.timestamp.timestamp()) for item in components] != [
            opened + index * source_seconds for index in range(expected_count)
        ]:
            continue
        output.append(StockCFDBar(
            datetime.fromtimestamp(opened, UTC), components[0].raw_timestamp,
            components[0].raw_rendering, components[0].open,
            max(item.high for item in components), min(item.low for item in components),
            components[-1].close, sum((item.volume for item in components), Decimal(0)),
            components[0].source_row_number,
        ))
    return tuple(output)


def _verify_native_equivalence(m5: tuple[StockCFDBar, ...], m15: tuple[StockCFDBar, ...]) -> None:
    aggregate = {bar.timestamp: bar for bar in rollup(m5, "M15")}
    comparable = 0
    for native in m15:
        derived = aggregate.get(native.timestamp)
        if derived is None:
            continue
        comparable += 1
        if (native.open, native.high, native.low, native.close) != (
            derived.open, derived.high, derived.low, derived.close
        ):
            raise StockCFDAdmissionError(f"NATIVE_M15_MISMATCH:{native.timestamp.isoformat()}")
    if not comparable:
        raise StockCFDAdmissionError("NO_COMPARABLE_NATIVE_M15")


def _active_overlay_event(connection, symbol: str, timeframe: str):
    return connection.execute(
        """SELECT e.authority_event_id FROM authority_events e
             WHERE e.entity_kind='EVIDENCE_LANE'
               AND json_extract(e.canonical_payload,'$.body.asset')=?
               AND json_extract(e.canonical_payload,'$.body.timeframe')=?
               AND json_extract(e.canonical_payload,'$.body.authority_id')=?
               AND json_extract(e.canonical_payload,'$.body.commissioning_state')='COMMISSIONED'
               AND NOT EXISTS (
                   SELECT 1 FROM authority_events successor
                    WHERE successor.supersedes_event_id=e.authority_event_id
               )
             ORDER BY e.recorded_at_utc DESC,e.authority_event_id DESC LIMIT 1""",
        (symbol, timeframe, AUTHORITY_ID),
    ).fetchone()


def broker_stock_cfd_intraday_enabled(database_path: str | Path, symbol: str, timeframe: str) -> bool:
    with open_read_only(database_path) as connection:
        return _active_overlay_event(
            connection, symbol.strip().upper(), timeframe.strip().upper()
        ) is not None


def _ensure_overlay_lane(database_path: str | Path, timeframe: str, observed_at: str) -> None:
    with open_read_only(database_path) as connection:
        registration = connection.execute(
            """SELECT asset_class,representation_type,exchange_name
                 FROM instrument_registrations WHERE asset='XOM' AND timeframe='D1'"""
        ).fetchone()
        lane_exists = connection.execute(
            "SELECT 1 FROM evidence_lanes WHERE asset='XOM' AND timeframe=?", (timeframe,)
        ).fetchone()
        overlay_exists = _active_overlay_event(connection, CANONICAL_SYMBOL, timeframe)
    if registration is None or tuple(registration) != ("US_EQUITIES", "COMMON_STOCK", "NYSE"):
        raise StockCFDAdmissionError(f"XOM_D1_IDENTITY_MISMATCH:{registration}")
    if overlay_exists:
        return
    append_authority_event(
        database_path,
        AuthorityEventManifest(
            "EVIDENCE_LANE", f"lane:{CANONICAL_SYMBOL}:{timeframe}",
            "LANE_REVISED" if lane_exists else "LANE_DECLARED", observed_at,
            "OPERATOR_APPROVED_GLOBAL_PRIME_STOCK_CFD_OVERLAY", (), "COMPATIBLE", (), {
                "asset": CANONICAL_SYMBOL,
                "timeframe": timeframe,
                "authority_id": AUTHORITY_ID,
                "policy_state": "EXPLICIT_BROKER_STOCK_CFD_INTRADAY_OVERLAY",
                "activation_state": "ACTIVE_NO_EVIDENCE",
                "commissioning_state": "COMMISSIONED",
                "automation_enabled": False,
                "registration_entity_id": f"registration:{CANONICAL_SYMBOL}:D1",
                "underlying_d1_representation": "NYSE_COMMON_STOCK",
                "intraday_representation": "GLOBAL_PRIME_STOCK_CFD",
                "provider": PROVIDER,
                "provider_symbol": TERMINAL_SYMBOL,
                "source_timestamp_status": SOURCE_TIMESTAMP_STATUS,
                "canonical_timestamp_policy": CANONICAL_TIMESTAMP_POLICY,
            },
        ),
        recorded_at_utc=observed_at,
    )
    if not lane_exists:
        with registered_writer(database_path) as connection:
            apply_migrations(connection)
            with transaction(connection):
                connection.execute(
                    "INSERT OR IGNORE INTO evidence_lanes VALUES(?,?, 'D1','EVIDENCE_LANE_V1',1,?)",
                    (CANONICAL_SYMBOL, timeframe, observed_at),
                )


def _csv_payload(bars: tuple[StockCFDBar, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
    for bar in bars:
        writer.writerow((
            bar.timestamp.isoformat(), _normal(bar.open), _normal(bar.high),
            _normal(bar.low), _normal(bar.close), _normal(bar.volume),
        ))
    return stream.getvalue().encode("utf-8")


def _batch(timeframe: str, bars: tuple[StockCFDBar, ...], raw_block_id: str, observed_at: str) -> StagingBatch:
    seconds = DURATIONS[timeframe]
    return StagingBatch(tuple(
        StagedBar(
            symbol=CANONICAL_SYMBOL, timeframe=timeframe,
            timestamp=int(bar.timestamp.timestamp()), open=_normal(bar.open),
            high=_normal(bar.high), low=_normal(bar.low), close=_normal(bar.close),
            volume=_normal(bar.volume), source="DATAGATHER_IMMUTABLE_PACKAGE",
            provider=PROVIDER, raw_block_id=raw_block_id,
            source_row_number=bar.source_row_number,
            source_timestamp_text=bar.raw_rendering,
            source_timezone_interpretation=CANONICAL_TIMESTAMP_POLICY,
            received_at=observed_at,
            close_timestamp=int(bar.timestamp.timestamp()) + seconds,
        ) for bar in bars
    ), (), len(bars), 0, 0)


def _ingest_series(
    database_path: str | Path, *, timeframe: str, bars: tuple[StockCFDBar, ...],
    evidence_payload: bytes, source_path: Path, bundle_checksum: str,
    observed_at: str, native: bool,
) -> dict[str, object]:
    checksum = _sha256(evidence_payload)
    raw_block_id = f"raw-{checksum}"
    result = ingest_staged_batch(
        database_path,
        batch=_batch(timeframe, bars, raw_block_id, observed_at),
        evidence=RawEvidence(
            raw_block_id=raw_block_id, checksum=checksum, payload=evidence_payload,
            source_name=source_path.name if native else f"ExxonMobil_{timeframe}_derived.csv",
            source_locator=f"{source_path.resolve()}#{timeframe}", media_type="text/csv",
            received_at=observed_at,
        ),
        run_kind="global_prime_stock_cfd_overlay",
        merge_mode="preserve",
        outcome_facts={
            "provider": PROVIDER,
            "provider_contract": (
                f"GLOBAL_PRIME_MT5_STOCK_CFD_NATIVE_{timeframe}_V1" if native
                else f"GLOBAL_PRIME_MT5_STOCK_CFD_M15_ROLLUP_{timeframe}_V1"
            ),
            "provider_symbol": TERMINAL_SYMBOL,
            "mapping_class": "APPROVED_PROVIDER_ALIAS",
            "representation": "STOCK_CFD",
            "underlying_reference": "NYSE:XOM",
            "asset": CANONICAL_SYMBOL,
            "timeframe": timeframe,
            "native_timeframe": native,
            "rollup_from": "NONE" if native else "M15",
            "source_timestamp_status": SOURCE_TIMESTAMP_STATUS,
            "canonical_timestamp_policy": CANONICAL_TIMESTAMP_POLICY,
            "bundle_manifest_sha256": bundle_checksum,
        },
        preserve_rejected_evidence=True,
        writer_lock_timeout_seconds=30.0,
    )
    return result.as_dict()


def admit_xom_stock_cfd_overlay(
    database_path: str | Path, bundle_root: str | Path,
    *, observed_at: datetime | None = None,
) -> dict[str, object]:
    root = Path(bundle_root).expanduser().resolve()
    manifest_path = root / "manifest.json"
    manifest_payload = manifest_path.read_bytes()
    manifest = json.loads(manifest_payload)
    if manifest.get("contract") != "global_prime.mt5.echo_short.phase2.v1":
        raise StockCFDAdmissionError("BUNDLE_CONTRACT_MISMATCH")
    instrument = (manifest.get("instruments") or {}).get(CANONICAL_SYMBOL) or {}
    if instrument.get("exact_terminal_symbol") != TERMINAL_SYMBOL:
        raise StockCFDAdmissionError("EXACT_TERMINAL_SYMBOL_MISMATCH")
    if (manifest.get("source_semantics") or {}).get("representation") != "STOCK_CFD":
        raise StockCFDAdmissionError("STOCK_CFD_REPRESENTATION_REQUIRED")
    artifacts = {item.get("file"): item.get("sha256") for item in manifest.get("artifacts") or []}
    native: dict[str, tuple[bytes, tuple[StockCFDBar, ...], Path]] = {}
    for timeframe in NATIVE_TIMEFRAMES:
        path = root / "data" / "history_730d" / f"{TERMINAL_SYMBOL}_{timeframe}.csv"
        payload, bars = read_native_csv(path, timeframe)
        if artifacts.get(str(path.relative_to(root))) != _sha256(payload):
            raise StockCFDAdmissionError(f"ARTIFACT_CHECKSUM_MISMATCH:{timeframe}")
        native[timeframe] = payload, bars, path
    _verify_native_equivalence(native["M5"][1], native["M15"][1])
    series = {
        "M5": native["M5"][1],
        "M15": native["M15"][1],
        "M30": rollup(native["M15"][1], "M30"),
        "H1": rollup(native["M15"][1], "H1"),
    }
    observed = (observed_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
    for timeframe in OUTPUT_TIMEFRAMES:
        _ensure_overlay_lane(database_path, timeframe, observed)
    bundle_checksum = _sha256(manifest_payload)
    results: dict[str, object] = {}
    for timeframe in OUTPUT_TIMEFRAMES:
        is_native = timeframe in NATIVE_TIMEFRAMES
        source_path = native[timeframe][2] if is_native else native["M15"][2]
        payload = native[timeframe][0] if is_native else _csv_payload(series[timeframe])
        results[timeframe] = _ingest_series(
            database_path, timeframe=timeframe, bars=series[timeframe],
            evidence_payload=payload, source_path=source_path,
            bundle_checksum=bundle_checksum, observed_at=observed, native=is_native,
        )
        validate_lane(
            database_path, symbol=CANONICAL_SYMBOL, timeframe=timeframe,
            through_date=series[timeframe][-1].timestamp.date().isoformat(),
            persist=True, clock=lambda: datetime.fromisoformat(observed),
        )
    enqueue_publication(
        database_path, [(CANONICAL_SYMBOL, timeframe) for timeframe in OUTPUT_TIMEFRAMES],
        trigger="GLOBAL_PRIME_STOCK_CFD_OVERLAY",
    )
    resume_pending_publications(database_path)
    return {
        "contract": CONTRACT,
        "status": "ADMITTED",
        "symbol": CANONICAL_SYMBOL,
        "provider_symbol": TERMINAL_SYMBOL,
        "provider": PROVIDER,
        "source_timestamp_status": SOURCE_TIMESTAMP_STATUS,
        "canonical_timestamp_policy": CANONICAL_TIMESTAMP_POLICY,
        "bundle_manifest_sha256": bundle_checksum,
        "rows": {timeframe: len(series[timeframe]) for timeframe in OUTPUT_TIMEFRAMES},
        "results": results,
    }


__all__ = [
    "AUTHORITY_ID", "CANONICAL_TIMESTAMP_POLICY", "SOURCE_TIMESTAMP_STATUS",
    "StockCFDAdmissionError", "admit_xom_stock_cfd_overlay",
    "broker_stock_cfd_intraday_enabled", "read_native_csv", "rollup",
]
