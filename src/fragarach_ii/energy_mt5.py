"""Admit reviewed Global Prime oil M5 and deterministic oil rollups."""

from __future__ import annotations

import csv
import hashlib
import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .ingestion.pipeline import IngestionResult, RawEvidence, ingest_staged_batch
from .lane_commissioning import ensure_commissioned_lane
from .lane_update_register import LaneUpdateRegister
from .provider_facts import approve_reviewed_provider_mapping
from .publication_service import enqueue_publication
from .staging import StagedBar, StagingBatch, stage_csv_bytes
from .synthetic_repository import SyntheticRepository
from .validation import validate_lane


PROVIDER = "GLOBAL_PRIME_MT5"
REQUIRED_HEADERS = {
    "time_utc", "open", "high", "low", "close",
    "tick_volume", "spread", "real_volume",
}
PACKAGE_HEADERS = {
    "mt5_time", "mt5_documented_utc_rendering", "open", "high", "low", "close",
    "tick_volume", "spread", "real_volume",
}


@dataclass(frozen=True, slots=True)
class EnergyInstrument:
    canonical_symbol: str
    mt5_symbol: str
    twelve_data_symbol: str
    session_first_utc: str
    session_last_utc: str
    expected_m5_count: int


INSTRUMENTS = {
    "USOIL": EnergyInstrument("USOIL", "XTIUSD", "WTI/USD", "01:00", "23:55", 276),
    "UKOIL": EnergyInstrument("UKOIL", "XBRUSD", "XBR/USD", "03:00", "23:55", 252),
}


@dataclass(frozen=True, slots=True)
class M5Bar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source_row_number: int


def read_mt5_m5(path: str | Path, *, instrument: EnergyInstrument) -> tuple[bytes, tuple[M5Bar, ...]]:
    selected = Path(path).expanduser().resolve()
    if not selected.name.upper().startswith(f"{instrument.mt5_symbol}_M5"):
        raise ValueError(f"MT5_SYMBOL_FILE_MISMATCH: expected {instrument.mt5_symbol}_M5*")
    payload = selected.read_bytes()
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True)
    headers = {str(value).strip().lower() for value in (reader.fieldnames or ())}
    if headers not in (REQUIRED_HEADERS, PACKAGE_HEADERS):
        raise ValueError(f"MT5_SCHEMA_MISMATCH: {sorted(headers)}")
    bars: list[M5Bar] = []
    seen: set[datetime] = set()
    prior: datetime | None = None
    for source_row_number, row in enumerate(reader, start=2):
        if headers == PACKAGE_HEADERS:
            raw_timestamp = int(str(row["mt5_time"]).strip())
            timestamp = datetime.fromtimestamp(raw_timestamp, UTC)
            rendered = timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")
            if str(row["mt5_documented_utc_rendering"]).strip() != rendered:
                raise ValueError(f"MT5_TIMESTAMP_RENDERING_MISMATCH: row {source_row_number}")
        else:
            timestamp = datetime.fromisoformat(str(row["time_utc"]).replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
            raise ValueError(f"MT5_TIMESTAMP_NOT_UTC: row {source_row_number}")
        timestamp = timestamp.astimezone(UTC)
        if timestamp.minute % 5 or timestamp.second or timestamp.microsecond:
            raise ValueError(f"MT5_M5_GRID_MISMATCH: row {source_row_number}")
        if timestamp in seen or (prior is not None and timestamp <= prior):
            raise ValueError(f"MT5_TIMESTAMP_ORDER_OR_DUPLICATE: row {source_row_number}")
        try:
            values = [Decimal(str(row[key]).strip()) for key in ("open", "high", "low", "close")]
            volume = Decimal(str(row["tick_volume"]).strip())
            spread = Decimal(str(row["spread"]).strip())
            real_volume = Decimal(str(row["real_volume"]).strip())
        except InvalidOperation as error:
            raise ValueError(f"MT5_NUMERIC_VALUE_INVALID: row {source_row_number}") from error
        opened, high, low, closed = values
        if min(opened, high, low, closed) <= 0 or high < max(opened, low, closed) or low > min(opened, high, closed):
            raise ValueError(f"MT5_OHLC_INVALID: row {source_row_number}")
        if min(volume, spread, real_volume) < 0:
            raise ValueError(f"MT5_VOLUME_OR_SPREAD_INVALID: row {source_row_number}")
        bars.append(M5Bar(timestamp, opened, high, low, closed, volume, source_row_number))
        seen.add(timestamp)
        prior = timestamp
    if not bars:
        raise ValueError("MT5_EMPTY_FILE")
    return payload, tuple(bars)


def fixed_rollup(bars: tuple[M5Bar, ...], timeframe: str) -> tuple[M5Bar, ...]:
    seconds = {"M15": 900, "M30": 1800, "H1": 3600}.get(timeframe.upper())
    if seconds is None:
        raise ValueError(f"UNSUPPORTED_FIXED_ROLLUP: {timeframe}")
    expected_count = seconds // 300
    grouped: dict[int, list[M5Bar]] = defaultdict(list)
    for bar in bars:
        epoch = int(bar.timestamp.timestamp())
        grouped[epoch - epoch % seconds].append(bar)
    output: list[M5Bar] = []
    for opened, components in sorted(grouped.items()):
        components.sort(key=lambda item: item.timestamp)
        expected = [opened + index * 300 for index in range(expected_count)]
        if [int(item.timestamp.timestamp()) for item in components] != expected:
            continue
        output.append(_aggregate(datetime.fromtimestamp(opened, UTC), components))
    return tuple(output)


def daily_rollup(bars: tuple[M5Bar, ...], *, instrument: EnergyInstrument) -> tuple[M5Bar, ...]:
    grouped: dict[date, list[M5Bar]] = defaultdict(list)
    for bar in bars:
        grouped[bar.timestamp.date()].append(bar)
    output: list[M5Bar] = []
    for owner_day, components in sorted(grouped.items()):
        components.sort(key=lambda item: item.timestamp)
        first = datetime.fromisoformat(f"{owner_day}T{instrument.session_first_utc}:00+00:00")
        last = datetime.fromisoformat(f"{owner_day}T{instrument.session_last_utc}:00+00:00")
        expected = [first + timedelta(minutes=5 * index) for index in range(instrument.expected_m5_count)]
        if expected[-1] != last or [item.timestamp for item in components] != expected:
            continue
        output.append(_aggregate(datetime.combine(owner_day, datetime.min.time(), UTC), components))
    return tuple(output)


def configure_twelve_data_fallbacks(database_path: str | Path, *, observed_at: datetime | None = None) -> None:
    decided = (observed_at or datetime.now(UTC)).astimezone(UTC)
    for instrument in INSTRUMENTS.values():
        for timeframe in ("D1", "H1", "M30", "M5"):
            approve_reviewed_provider_mapping(
                database_path,
                canonical_symbol=instrument.canonical_symbol,
                provider="TWELVE_DATA",
                provider_symbol=instrument.twelve_data_symbol,
                timeframe=timeframe,
                asset_class="ENERGY",
                representation_type="CFD",
                provider_instrument_type="Energy Resource",
                decided_at=decided,
            )


def admit_energy_mt5(
    database_path: str | Path,
    *, usoil_file: str | Path, ukoil_file: str | Path,
    observed_at: datetime | None = None,
    symbols: tuple[str, ...] = ("USOIL", "UKOIL"),
) -> dict[str, object]:
    observed = (observed_at or datetime.now(UTC)).astimezone(UTC)
    configure_twelve_data_fallbacks(database_path, observed_at=observed)
    update_register = LaneUpdateRegister(database_path)
    result: dict[str, object] = {}
    files = {"USOIL": usoil_file, "UKOIL": ukoil_file}
    selected = tuple(symbol.strip().upper() for symbol in symbols)
    unknown = set(selected) - set(files)
    if unknown:
        raise ValueError(f"UNKNOWN_ENERGY_SYMBOLS: {sorted(unknown)}")
    for canonical in selected:
        file_path = files[canonical]
        instrument = INSTRUMENTS[canonical]
        raw_payload, bars = read_mt5_m5(file_path, instrument=instrument)
        for timeframe in ("M5", "M30", "H1", "D1"):
            ensure_commissioned_lane(database_path, canonical, timeframe, observed_at=observed.isoformat())
            update_register.ensure_commissioned_lane(
                asset=canonical, timeframe=timeframe, at=observed,
            )
        rollups = {
            "M5": bars,
            "M30": fixed_rollup(bars, "M30"),
            "H1": fixed_rollup(bars, "H1"),
            "D1": daily_rollup(bars, instrument=instrument),
        }
        lane_results: dict[str, object] = {}
        source_checksum = hashlib.sha256(raw_payload).hexdigest()
        for timeframe, observations in rollups.items():
            evidence_payload = raw_payload if timeframe == "M5" else _csv_payload(observations, timeframe)
            ingestion = _ingest(
                database_path, canonical=canonical, timeframe=timeframe,
                observations=observations, evidence_payload=evidence_payload,
                source_path=Path(file_path), source_checksum=source_checksum,
                instrument=instrument, observed=observed,
            )
            lane_results[timeframe] = ingestion.as_dict()
            validate_lane(
                database_path, symbol=canonical, timeframe=timeframe,
                through_date=observations[-1].timestamp.date().isoformat(),
                persist=True, clock=lambda: observed,
            )
            enqueue_publication(database_path, [(canonical, timeframe)], trigger="GLOBAL_PRIME_MT5_ROLLUP")
        repository = SyntheticRepository(database_path)
        repository.activate_registry(generate_on_activation=False)
        m15 = repository.generate(f"{canonical}:M15", generated_at=observed)
        result[canonical] = {
            "mt5_symbol": instrument.mt5_symbol,
            "source_checksum": source_checksum,
            "source_rows": len(bars),
            "complete_m15": len(fixed_rollup(bars, "M15")),
            "complete_m30": len(rollups["M30"]),
            "complete_h1": len(rollups["H1"]),
            "complete_d1": len(rollups["D1"]),
            "lanes": lane_results,
            "m15": m15,
            "fallback": {"provider": "TWELVE_DATA", "symbol": instrument.twelve_data_symbol},
        }
    return {
        "contract": "fragarach_ii.energy_mt5_rollup.v1",
        "primary_provider": PROVIDER,
        "fallback_provider": "TWELVE_DATA",
        "timestamp_policy": "MT5_DOCUMENTED_UTC_RENDERING_ACCEPTED_FOR_OIL_ROLLUP_V1",
        "results": result,
    }


def _aggregate(timestamp: datetime, components: list[M5Bar]) -> M5Bar:
    return M5Bar(
        timestamp, components[0].open, max(item.high for item in components),
        min(item.low for item in components), components[-1].close,
        sum((item.volume for item in components), Decimal(0)),
        components[0].source_row_number,
    )


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _csv_payload(observations: tuple[M5Bar, ...], timeframe: str) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
    for item in observations:
        stamp = item.timestamp.date().isoformat() if timeframe == "D1" else item.timestamp.isoformat()
        writer.writerow((stamp, _decimal(item.open), _decimal(item.high), _decimal(item.low), _decimal(item.close), _decimal(item.volume)))
    return stream.getvalue().encode("utf-8")


def _ingest(
    database_path: str | Path,
    *, canonical: str, timeframe: str, observations: tuple[M5Bar, ...],
    evidence_payload: bytes, source_path: Path, source_checksum: str,
    instrument: EnergyInstrument, observed: datetime,
) -> IngestionResult:
    if not observations:
        raise ValueError(f"NO_COMPLETE_{timeframe}_OBSERVATIONS: {canonical}")
    checksum = hashlib.sha256(evidence_payload).hexdigest()
    raw_block_id = f"raw-{checksum}"
    batch = (
        stage_csv_bytes(
            _csv_payload(observations, timeframe), symbol=canonical,
            timeframe=timeframe, provider=PROVIDER, raw_block_id=raw_block_id,
            received_at=observed.isoformat(),
            d1_latest_closed_date=observations[-1].timestamp.date(),
        )
        if timeframe == "D1"
        else _intraday_batch(
            canonical, timeframe, observations, raw_block_id, observed
        )
    )
    evidence = RawEvidence(
        raw_block_id=raw_block_id, checksum=checksum, payload=evidence_payload,
        source_name=source_path.name if timeframe == "M5" else f"{source_path.stem}_{timeframe}_rollup.csv",
        source_locator=f"{source_path.resolve()}#{timeframe}", media_type="text/csv",
        received_at=observed.isoformat(),
    )
    return ingest_staged_batch(
        database_path, batch=batch, evidence=evidence,
        run_kind="global_prime_mt5_rollup", merge_mode="correct",
        outcome_facts={
            "provider": PROVIDER,
            "provider_contract": f"GLOBAL_PRIME_MT5_{timeframe}_ROLLUP_V1" if timeframe != "M5" else "GLOBAL_PRIME_MT5_M5_V1",
            "provider_symbol": instrument.mt5_symbol,
            "mapping_class": "APPROVED_PROVIDER_ALIAS",
            "asset": canonical, "timeframe": timeframe,
            "source_checksum": source_checksum,
            "rollup_observation_count": len(observations),
            "rollup_from": "M5" if timeframe != "M5" else "NONE",
            "fallback_provider": "TWELVE_DATA",
            "fallback_symbol": instrument.twelve_data_symbol,
            "timestamp_policy": "MT5_DOCUMENTED_UTC_RENDERING_ACCEPTED_FOR_OIL_ROLLUP_V1",
        },
        preserve_rejected_evidence=True, writer_lock_timeout_seconds=30.0,
    )


def _intraday_batch(
    canonical: str, timeframe: str, observations: tuple[M5Bar, ...],
    raw_block_id: str, observed: datetime,
) -> StagingBatch:
    seconds = {"M5": 300, "M30": 1800, "H1": 3600}[timeframe]
    bars = tuple(
        StagedBar(
            symbol=canonical, timeframe=timeframe,
            timestamp=int(item.timestamp.timestamp()),
            open=_decimal(item.open), high=_decimal(item.high),
            low=_decimal(item.low), close=_decimal(item.close),
            volume=_decimal(item.volume), source="MANUAL_FILE",
            provider=PROVIDER, raw_block_id=raw_block_id,
            source_row_number=item.source_row_number,
            source_timestamp_text=item.timestamp.isoformat(),
            source_timezone_interpretation="EXPLICIT_UTC_OFFSET",
            received_at=observed.isoformat(),
            close_timestamp=int(item.timestamp.timestamp()) + seconds,
        )
        for item in observations
    )
    return StagingBatch(bars, (), len(bars), 0, 0)


__all__ = [
    "INSTRUMENTS", "EnergyInstrument", "M5Bar", "admit_energy_mt5",
    "configure_twelve_data_fallbacks", "daily_rollup", "fixed_rollup", "read_mt5_m5",
]
