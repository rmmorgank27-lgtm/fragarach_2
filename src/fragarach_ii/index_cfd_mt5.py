"""Admit immutable native MT5 broker-family index-CFD packages into Fragarach."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import signal
import sys
import tempfile
import time
from typing import Any
import zipfile

from .external_consumer_service import canonical_database_path
from .ingestion.pipeline import RawEvidence, ingest_staged_batch
from .lane_commissioning import ensure_commissioned_lane
from .publication_service import enqueue_publication, lane_publication_state, resume_pending_publications
from .staging import StagedBar, StagingBatch
from .storage import (
    RegistrationCandidate,
    WriterLockError,
    open_read_only,
    register_instrument,
)
from .validation import validate_lane


CONTRACT = "fragarach_ii.mt5_broker_index_cfd_admission.v2"
TRANSPORT_CONTRACT = "datagather.tailscale_transport.v1"
LANE = "divergence.market_data"
TIMESTAMP_POLICY = "MT5_PYTHON_COPY_RATES_UNIX_UTC_V1"
SYMBOLS = ("US30", "US500", "NAS100")
TIMEFRAMES = ("D1", "H1", "M30", "M5")
SUPERSEDED_TIMEFRAME_SCOPES = frozenset({
    frozenset(("D1", "H1", "M15", "M5")),
    frozenset(("D1", "H1", "M30", "M15", "M5")),
})
DURATIONS = {"H1": 3600, "M30": 1800, "M5": 300}
UNDERLYINGS = {
    "US30": "INDEX_REFERENCE:DJIA:MT5_BROKER_FAMILY_CFD",
    "US500": "INDEX_REFERENCE:SP500:MT5_BROKER_FAMILY_CFD",
    "NAS100": "INDEX_REFERENCE:NASDAQ100:MT5_BROKER_FAMILY_CFD",
}
DISPLAY_NAMES = {
    "US30": "MT5 Broker Family US30 Index CFD",
    "US500": "MT5 Broker Family US500 Index CFD",
    "NAS100": "MT5 Broker Family NAS100 Index CFD",
}
AUTHORITY_PATH = (
    Path(__file__).resolve().parents[2]
    / "constitution/authorities/index_cfds/MT5_BROKER_FAMILY_INDEX_CFD_AUTHORITY_V1.json"
)


class IndexCFDAdmissionError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _authority() -> dict[str, Any]:
    """Load the governed route catalogue; providers never live in code."""

    try:
        value = _json_object(AUTHORITY_PATH.read_bytes(), AUTHORITY_PATH.name)
        declared_checksum = str(value.pop("authority_checksum"))
    except (OSError, KeyError) as error:
        raise IndexCFDAdmissionError("BROKER_FAMILY_AUTHORITY_UNAVAILABLE") from error
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if declared_checksum != _sha256(canonical):
        raise IndexCFDAdmissionError("BROKER_FAMILY_AUTHORITY_CHECKSUM_MISMATCH")
    registration = value.get("canonical_registration")
    routes = value.get("routes")
    if (
        not isinstance(registration, dict)
        or not isinstance(routes, list)
        or not routes
        or any(not isinstance(route, dict) for route in routes)
    ):
        raise IndexCFDAdmissionError("BROKER_FAMILY_AUTHORITY_INVALID")
    return value


def _route_for(manifest: dict[str, Any], authority: dict[str, Any]) -> dict[str, Any]:
    """Resolve a route exclusively from Fragarach's approved authority."""

    for route in authority["routes"]:
        identity = route.get("manifest_identity")
        contracts = route.get("manifest_contracts")
        if (
            isinstance(identity, dict)
            and isinstance(contracts, list)
            and manifest.get("contract") in contracts
            and all(manifest.get(key) == expected for key, expected in identity.items())
        ):
            return route
    raise IndexCFDAdmissionError("UNAPPROVED_BROKER_FAMILY_ROUTE")


@dataclass(frozen=True, slots=True)
class SeriesEvidence:
    symbol: str
    timeframe: str
    payload: bytes
    rows: tuple[dict[str, Any], ...]
    checksum: str


@dataclass(frozen=True, slots=True)
class PackageEvidence:
    path: Path
    package_sha256: str
    receipt: dict[str, Any]
    envelope: dict[str, Any]
    manifest: dict[str, Any]
    route: dict[str, Any]
    series: tuple[SeriesEvidence, ...]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_name(name: str) -> bool:
    if not name or "\\" in name or name.startswith("/"):
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _json_object(payload: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IndexCFDAdmissionError(f"INVALID_JSON:{name}") from error
    if not isinstance(value, dict):
        raise IndexCFDAdmissionError(f"INVALID_JSON_OBJECT:{name}")
    return value


def _inventory(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise IndexCFDAdmissionError("INVALID_CHECKSUM_INVENTORY") from error
    for line in lines:
        digest, separator, name = line.partition("  ")
        if separator != "  " or len(digest) != 64 or not _safe_name(name):
            raise IndexCFDAdmissionError("INVALID_CHECKSUM_INVENTORY")
        if name in result:
            raise IndexCFDAdmissionError("DUPLICATE_CHECKSUM_ENTRY")
        result[name] = digest
    return result


def _validate_rows(
    payload: bytes, *, symbol: str, timeframe: str, coverage: dict[str, Any]
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    previous: int | None = None
    duration = DURATIONS.get(timeframe, 86_400)
    for line_number, line in enumerate(payload.splitlines(), start=1):
        row = _json_object(line, f"{symbol}_{timeframe}.jsonl:{line_number}")
        try:
            opened = int(row["mt5_time"])
            values = tuple(Decimal(str(row[key])) for key in ("open", "high", "low", "close"))
            tick_volume = Decimal(str(row["tick_volume"]))
            spread = Decimal(str(row["spread"]))
            real_volume = Decimal(str(row["real_volume"]))
        except (KeyError, TypeError, ValueError, InvalidOperation) as error:
            raise IndexCFDAdmissionError(f"INVALID_ROW:{symbol}:{timeframe}:{line_number}") from error
        opened_value, high, low, closed = values
        if previous is not None and opened <= previous:
            raise IndexCFDAdmissionError(f"TIMESTAMP_ORDER:{symbol}:{timeframe}")
        if opened % duration:
            raise IndexCFDAdmissionError(f"TIMESTAMP_GRID:{symbol}:{timeframe}:{opened}")
        rendered = datetime.fromtimestamp(opened, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        if row.get("mt5_documented_utc_rendering") != rendered:
            raise IndexCFDAdmissionError(f"UTC_RENDERING_MISMATCH:{symbol}:{timeframe}:{opened}")
        if min(values) <= 0 or high < max(opened_value, low, closed) or low > min(opened_value, high, closed):
            raise IndexCFDAdmissionError(f"OHLC_INVALID:{symbol}:{timeframe}:{opened}")
        if min(tick_volume, spread, real_volume) < 0:
            raise IndexCFDAdmissionError(f"VOLUME_OR_SPREAD_INVALID:{symbol}:{timeframe}:{opened}")
        rows.append(row)
        previous = opened
    if not rows:
        raise IndexCFDAdmissionError(f"EMPTY_SERIES:{symbol}:{timeframe}")
    if int(coverage.get("row_count", -1)) != len(rows):
        raise IndexCFDAdmissionError(f"ROW_COUNT_MISMATCH:{symbol}:{timeframe}")
    if coverage.get("first_raw_timestamp") != rows[0]["mt5_time"] or coverage.get("last_raw_timestamp") != rows[-1]["mt5_time"]:
        raise IndexCFDAdmissionError(f"RANGE_MISMATCH:{symbol}:{timeframe}")
    if coverage.get("native_timeframe") != timeframe or coverage.get("exact_provider_symbol") != symbol:
        raise IndexCFDAdmissionError(f"NATIVE_IDENTITY_MISMATCH:{symbol}:{timeframe}")
    if coverage.get("canonical_label") != symbol or coverage.get("forming_bar_excluded") is not True:
        raise IndexCFDAdmissionError(f"COMPLETION_IDENTITY_MISMATCH:{symbol}:{timeframe}")
    if coverage.get("strict_ordering") is not True or coverage.get("unique") is not True:
        raise IndexCFDAdmissionError(f"ORDERING_PROOF_MISSING:{symbol}:{timeframe}")
    return tuple(rows)


def load_package(path: str | Path, receipt: dict[str, Any]) -> PackageEvidence:
    authority = _authority()
    selected = Path(path).expanduser().resolve()
    body = selected.read_bytes()
    package_sha = _sha256(body)
    if receipt.get("lane") != LANE or receipt.get("status") not in {"ACCEPTED", "DUPLICATE"}:
        raise IndexCFDAdmissionError("RECEIPT_NOT_ACCEPTED_FOR_DIVERGENCE")
    if receipt.get("package_sha256") != package_sha:
        raise IndexCFDAdmissionError("RECEIPT_PACKAGE_HASH_MISMATCH")
    try:
        archive = zipfile.ZipFile(selected, "r")
    except (OSError, zipfile.BadZipFile) as error:
        raise IndexCFDAdmissionError("INVALID_ZIP") from error
    with archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(not _safe_name(name) for name in names):
            raise IndexCFDAdmissionError("UNSAFE_ZIP_NAMES")
        files = {name: archive.read(name) for name in names if not name.endswith("/")}
    required = {"SHA256SUMS.txt", "transport-envelope.json", "manifest.json", "coverage-report.json"}
    expected_series = {f"payload/json/{symbol}_{timeframe}.jsonl" for symbol in SYMBOLS for timeframe in TIMEFRAMES}
    if not required.issubset(files) or not expected_series.issubset(files):
        raise IndexCFDAdmissionError("PACKAGE_FILES_MISSING")
    checksums = _inventory(files["SHA256SUMS.txt"])
    if set(checksums) != set(files) - {"SHA256SUMS.txt"}:
        raise IndexCFDAdmissionError("CHECKSUM_COVERAGE_MISMATCH")
    if any(_sha256(files[name]) != digest for name, digest in checksums.items()):
        raise IndexCFDAdmissionError("EMBEDDED_CHECKSUM_MISMATCH")
    envelope = _json_object(files["transport-envelope.json"], "transport-envelope.json")
    manifest = _json_object(files["manifest.json"], "manifest.json")
    coverage = _json_object(files["coverage-report.json"], "coverage-report.json")
    if envelope.get("contract") != TRANSPORT_CONTRACT or envelope.get("lane") != LANE:
        raise IndexCFDAdmissionError("TRANSPORT_CONTRACT_MISMATCH")
    if manifest.get("lane_id") != "divergence.indices.native.v1":
        raise IndexCFDAdmissionError("MANIFEST_CONTRACT_MISMATCH")
    route = _route_for(manifest, authority)
    for key in ("message_id", "request_id", "export_run_id"):
        if envelope.get(key) != receipt.get(key):
            raise IndexCFDAdmissionError(f"RECEIPT_IDENTITY_MISMATCH:{key}")
    if manifest.get("request_id") != envelope.get("request_id") or manifest.get("export_run_id") != envelope.get("export_run_id"):
        raise IndexCFDAdmissionError("MANIFEST_IDENTITY_MISMATCH")
    if manifest.get("timestamp_status") != "UTC_AUTHORITY_RESOLVED" or manifest.get("timestamp_policy") != TIMESTAMP_POLICY:
        raise IndexCFDAdmissionError("TIMESTAMP_AUTHORITY_NOT_RESOLVED")
    if manifest.get("source_method") not in {"MetaTrader5.copy_rates_range", "MetaTrader5.copy_rates_from"}:
        raise IndexCFDAdmissionError("SOURCE_METHOD_NOT_APPROVED")
    if set(manifest.get("native_timeframes") or ()) != set(TIMEFRAMES):
        raise IndexCFDAdmissionError("NATIVE_TIMEFRAMES_MISMATCH")
    terminal_symbols = manifest.get("exact_terminal_symbols") or {}
    if set(terminal_symbols) != set(SYMBOLS) or any(terminal_symbols[symbol].get("name") != symbol for symbol in SYMBOLS):
        raise IndexCFDAdmissionError("EXACT_SYMBOLS_MISMATCH")
    coverage_rows = coverage.get("series") or {}
    if set(coverage_rows) != {f"{symbol}_{timeframe}" for symbol in SYMBOLS for timeframe in TIMEFRAMES}:
        raise IndexCFDAdmissionError("SERIES_SET_MISMATCH")
    series: list[SeriesEvidence] = []
    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            name = f"payload/json/{symbol}_{timeframe}.jsonl"
            payload = files[name]
            item = coverage_rows[f"{symbol}_{timeframe}"]
            if item.get("per_file_sha256", {}).get(name) != _sha256(payload):
                raise IndexCFDAdmissionError(f"SERIES_CHECKSUM_MISMATCH:{symbol}:{timeframe}")
            rows = _validate_rows(payload, symbol=symbol, timeframe=timeframe, coverage=item)
            series.append(SeriesEvidence(symbol, timeframe, payload, rows, _sha256(payload)))
    return PackageEvidence(selected, package_sha, receipt, envelope, manifest, route, tuple(series))


def _is_superseded_native_scope_package(path: Path) -> bool:
    """Recognize immutable prior native scopes without admitting them again."""

    try:
        with zipfile.ZipFile(path, "r") as archive:
            manifest = _json_object(archive.read("manifest.json"), "manifest.json")
    except (OSError, KeyError, zipfile.BadZipFile, IndexCFDAdmissionError):
        return False
    try:
        _route_for(manifest, _authority())
    except IndexCFDAdmissionError:
        return False
    return (
        manifest.get("lane_id") == "divergence.indices.native.v1"
        and frozenset(manifest.get("native_timeframes") or ()) in SUPERSEDED_TIMEFRAME_SCOPES
    )


def _candidate(symbol: str, authority: dict[str, Any]) -> RegistrationCandidate:
    registration = authority["canonical_registration"]
    return RegistrationCandidate(
        asset=symbol, timeframe="D1", instrument_family=symbol, local_symbol=symbol,
        display_name=DISPLAY_NAMES[symbol], instrument_type="INDEX_CFD",
        asset_class="BROKER_INDEX_CFDS", representation_type="CFD",
        trading_currency="USD", exchange_name=str(registration["exchange_name"]),
        provider_id=str(registration["provider_id"]),
        provider_contract=str(registration["provider_contract"]),
        provider_symbol=symbol, provider_instrument_type="INDEX_CFD",
        calendar_id=str(registration["calendar_id"]), calendar_version=int(registration["calendar_version"]),
        gap_doctrine_id="FRAGARACH_II_D1_GAP_DOCTRINE_V1", gap_doctrine_version=1,
        selected_representation=symbol, underlying_reference=UNDERLYINGS[symbol],
        contract_or_series=str(registration["contract_or_series"]),
    )


def _existing(database_path: Path, series: SeriesEvidence) -> dict[int, tuple[str, str, str, str, str | None]]:
    first = int(series.rows[0]["mt5_time"])
    last = int(series.rows[-1]["mt5_time"])
    with open_read_only(database_path) as connection:
        rows = connection.execute(
            """SELECT open_time_utc,open,high,low,close,volume FROM bars
               WHERE asset=? AND timeframe=? AND open_time_utc BETWEEN ? AND ?""",
            (series.symbol, series.timeframe, first, last),
        ).fetchall()
    return {int(row[0]): tuple(row[1:]) for row in rows}


def _ensure_authority(database: Path, received_at: str, authority: dict[str, Any]) -> None:
    with open_read_only(database) as connection:
        registrations = {
            str(row[0]): tuple(row[1:])
            for row in connection.execute(
                """SELECT asset,asset_class,representation_type,provider_id,
                          provider_contract,provider_symbol
                     FROM instrument_registrations
                    WHERE asset IN ('US30','US500','NAS100') AND timeframe='D1'"""
            ).fetchall()
        }
        lanes = {
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                """SELECT asset,timeframe FROM evidence_lanes
                    WHERE asset IN ('US30','US500','NAS100')"""
            ).fetchall()
        }
    registration = authority["canonical_registration"]
    for symbol in SYMBOLS:
        existing = registrations.get(symbol)
        if existing is None:
            register_instrument(database, _candidate(symbol, authority), registered_at_utc=received_at)
        elif (
            existing[:2] != ("BROKER_INDEX_CFDS", "CFD")
            or existing[4] != symbol
        ):
            raise IndexCFDAdmissionError(f"CANONICAL_INDEX_CFD_IDENTITY_COLLISION:{symbol}")
        # A D1 registration is immutable historical identity, not an active
        # provider route. Current receipts are admitted only through the
        # authority's bridge route and retain their per-receipt provider.
        for timeframe in TIMEFRAMES:
            if (symbol, timeframe) not in lanes:
                ensure_commissioned_lane(database, symbol, timeframe, observed_at=received_at)


def _normal(value: Any) -> str:
    return format(Decimal(str(value)), "f")


def _delta(
    database_path: Path, series: SeriesEvidence, received_at: str, *, provider: str,
) -> tuple[StagingBatch, bytes]:
    existing = _existing(database_path, series)
    staged: list[StagedBar] = []
    lines: list[bytes] = []
    raw_lines = series.payload.splitlines(keepends=True)
    for index, row in enumerate(series.rows, start=1):
        opened = int(row["mt5_time"])
        values = tuple(_normal(row[key]) for key in ("open", "high", "low", "close"))
        volume = _normal(row["tick_volume"])
        if existing.get(opened) == (*values, volume):
            continue
        lines.append(raw_lines[index - 1])
        staged.append(StagedBar(
            symbol=series.symbol, timeframe=series.timeframe, timestamp=opened,
            open=values[0], high=values[1], low=values[2], close=values[3], volume=volume,
            source="DATAGATHER_IMMUTABLE_PACKAGE", provider=provider,
            raw_block_id="pending", source_row_number=index,
            source_timestamp_text=str(row["mt5_documented_utc_rendering"]),
            source_timezone_interpretation=TIMESTAMP_POLICY, received_at=received_at,
            close_timestamp=None if series.timeframe == "D1" else opened + DURATIONS[series.timeframe],
        ))
    delta_payload = b"".join(lines)
    raw_id = f"raw-{_sha256(delta_payload)}" if delta_payload else ""
    bars = tuple(
        StagedBar(
            symbol=item.symbol, timeframe=item.timeframe, timestamp=item.timestamp,
            open=item.open, high=item.high, low=item.low, close=item.close, volume=item.volume,
            source=item.source, provider=item.provider, raw_block_id=raw_id,
            source_row_number=item.source_row_number, source_timestamp_text=item.source_timestamp_text,
            source_timezone_interpretation=item.source_timezone_interpretation,
            received_at=item.received_at, close_timestamp=item.close_timestamp,
        ) for item in staged
    )
    return StagingBatch(bars, (), len(bars), 0, 0), delta_payload


def admit_package(database_path: str | Path, package: PackageEvidence) -> dict[str, Any]:
    database = Path(database_path).expanduser().resolve()
    authority = _authority()
    observed = datetime.fromisoformat(
        str(package.receipt["received_utc"]).replace("Z", "+00:00")
    ).astimezone(UTC)
    received_at = observed.isoformat(timespec="seconds")
    _ensure_authority(database, received_at, authority)
    results: dict[str, Any] = {}
    changed_lanes: list[tuple[str, str]] = []
    for series in package.series:
        batch, delta_payload = _delta(
            database, series, received_at, provider=str(package.route["record_provider"]),
        )
        key = f"{series.symbol}:{series.timeframe}"
        if not batch.bars:
            results[key] = {"source_rows": len(series.rows), "delta_rows": 0, "outcome": "UNCHANGED"}
            continue
        delta_checksum = _sha256(delta_payload)
        ingestion = ingest_staged_batch(
            database,
            batch=batch,
            evidence=RawEvidence(
                raw_block_id=f"raw-{delta_checksum}", checksum=delta_checksum,
                payload=delta_payload, source_name=f"{series.symbol}_{series.timeframe}.delta.jsonl",
                source_locator=(
                    f"datagather://{LANE}/{package.receipt['message_id']}/"
                    f"payload/json/{series.symbol}_{series.timeframe}.jsonl"
                ),
                media_type="application/x-ndjson", received_at=received_at,
            ),
            run_kind="mt5_broker_family_index_cfd",
            merge_mode="correct",
            outcome_facts={
                "provider": str(package.route["record_provider"]),
                "provider_contract": str(package.route["record_provider_contract"]),
                "provider_family": str(authority["authority_id"]),
                "provider_route": str(package.route["route_id"]),
                "provider_symbol": series.symbol, "mapping_class": "EXACT_REPRESENTATION",
                "asset": series.symbol, "timeframe": series.timeframe,
                "timestamp_policy": TIMESTAMP_POLICY, "native_timeframe": True,
                "transport_lane": LANE, "message_id": str(package.receipt["message_id"]),
                "export_run_id": str(package.receipt["export_run_id"]),
                "receipt_id": str(package.receipt["receipt_id"]),
                "package_sha256": package.package_sha256,
                "source_series_sha256": series.checksum,
                "package_source_rows": len(series.rows), "delta_rows": len(batch.bars),
            },
            preserve_rejected_evidence=True,
            writer_lock_timeout_seconds=30.0,
        )
        results[key] = {"source_rows": len(series.rows), "delta_rows": len(batch.bars), **ingestion.as_dict()}
        changed_lanes.append((series.symbol, series.timeframe))
    for series in package.series:
        validate_lane(
            database, symbol=series.symbol, timeframe=series.timeframe,
            through_date=datetime.fromtimestamp(int(series.rows[-1]["mt5_time"]), UTC).date().isoformat(),
            persist=True, clock=lambda: observed,
        )
    all_lanes = [(symbol, timeframe) for symbol in SYMBOLS for timeframe in TIMEFRAMES]
    enqueue_publication(database, all_lanes, trigger="MT5_BROKER_FAMILY_INDEX_CFD")
    resume_pending_publications(database)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and any(
        lane_publication_state(database, symbol, timeframe) == "PUBLISHING"
        for symbol, timeframe in all_lanes
    ):
        time.sleep(0.1)
    publication = {
        f"{symbol}:{timeframe}": lane_publication_state(database, symbol, timeframe)
        for symbol, timeframe in all_lanes
    }
    if any(value != "PUBLISHED" for value in publication.values()):
        raise IndexCFDAdmissionError(f"PUBLICATION_NOT_READY:{publication}")
    return {
        "contract": CONTRACT, "status": "ADMITTED",
        "provider_family": authority["authority_id"],
        "provider_route": package.route["route_id"],
        "timestamp_policy": TIMESTAMP_POLICY,
        "message_id": package.receipt["message_id"],
        "receipt_id": package.receipt["receipt_id"],
        "export_run_id": package.receipt["export_run_id"],
        "package_sha256": package.package_sha256,
        "changed_lane_count": len(changed_lanes), "publication": publication,
        "results": results,
    }


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    if value.get("contract") != CONTRACT:
        value = {"contract": CONTRACT, "processed_package_sha256": []}
    return value


def process_receiver(database_path: str | Path, receiver_root: str | Path, state_path: str | Path) -> dict[str, Any]:
    receiver = Path(receiver_root).expanduser().resolve()
    state_file = Path(state_path).expanduser().resolve()
    state = _load_state(state_file)
    processed = set(map(str, state.get("processed_package_sha256") or []))
    receipts: list[dict[str, Any]] = []
    for path in (receiver / "receipts").glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("lane") == LANE and value.get("status") in {"ACCEPTED", "DUPLICATE"}:
            receipts.append(value)
    receipts.sort(key=lambda item: (str(item.get("received_utc") or ""), str(item.get("message_id") or "")))
    admitted: list[dict[str, Any]] = []
    waiting: list[dict[str, str]] = []
    superseded: list[dict[str, str]] = []
    for receipt in receipts:
        package_sha = str(receipt.get("package_sha256") or "")
        if not package_sha or package_sha in processed:
            continue
        package_path = receiver / str(receipt.get("accepted_object") or "")
        try:
            package = load_package(package_path, receipt)
            result = admit_package(database_path, package)
        except IndexCFDAdmissionError as error:
            if str(error) in {"PACKAGE_FILES_MISSING", "NATIVE_TIMEFRAMES_MISMATCH"} and _is_superseded_native_scope_package(package_path):
                processed.add(package_sha)
                superseded.append({
                    "package_sha256": package_sha,
                    "reason": "SUPERSEDED_BY_FOUR_NATIVE_TIMEFRAME_SCOPE",
                })
                continue
            if str(error) == "TIMESTAMP_AUTHORITY_NOT_RESOLVED":
                waiting.append({"package_sha256": package_sha, "reason": str(error)})
                continue
            raise
        processed.add(package_sha)
        admitted.append(result)
        state.update({
            "last_success_utc": datetime.now(UTC).isoformat(),
            "last_message_id": result["message_id"],
            "last_receipt_id": result["receipt_id"],
            "last_export_run_id": result["export_run_id"],
            "last_package_sha256": result["package_sha256"],
        })
    state.update({
        "contract": CONTRACT, "status": "HEALTHY",
        "updated_utc": datetime.now(UTC).isoformat(),
        "processed_package_sha256": sorted(processed)[-1000:],
        "waiting_unresolved_count": len(waiting),
        "superseded_legacy_count": len(superseded),
        "newly_admitted_count": len(admitted),
    })
    state.pop("error", None)
    state.pop("last_retry_reason", None)
    _atomic_json(state_file, state)
    return {
        "status": state["status"], "admitted": admitted, "waiting": waiting,
        "superseded": superseded, "state": state,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=canonical_database_path())
    parser.add_argument(
        "--receiver-root", type=Path,
        default=Path.home() / "Library/Application Support/Datagather/MT5Receiver",
    )
    parser.add_argument(
        "--state", type=Path,
        default=Path(__file__).resolve().parents[2] / "data/runtime/global-prime-index-cfd-importer.json",
    )
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=20.0)
    args = parser.parse_args(argv)
    stop = False

    def request_stop(*_unused: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        while True:
            try:
                result = process_receiver(args.database, args.receiver_root, args.state)
            except WriterLockError as error:
                prior = _load_state(args.state)
                prior.update({
                    "contract": CONTRACT, "status": "RETRYING_WRITER_BUSY",
                    "last_retry_utc": datetime.now(UTC).isoformat(),
                    "last_retry_reason": str(error),
                })
                _atomic_json(args.state, prior)
                if not args.watch:
                    print(json.dumps(prior, sort_keys=True, separators=(",", ":")))
                    return 2
                result = {"status": prior["status"], "state": prior}
            if not args.watch or stop:
                print(json.dumps(result, sort_keys=True, separators=(",", ":")))
                return 0
            deadline = time.monotonic() + max(5.0, args.poll_seconds)
            while not stop and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))
            if stop:
                return 0
    except Exception as error:
        failure = _load_state(args.state)
        failure.update({
            "contract": CONTRACT, "status": "FAILED", "error": str(error),
            "updated_utc": datetime.now(UTC).isoformat(),
        })
        _atomic_json(args.state, failure)
        print(json.dumps(failure, sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "CONTRACT", "SYMBOLS", "TIMEFRAMES", "TIMESTAMP_POLICY",
    "IndexCFDAdmissionError", "PackageEvidence", "SeriesEvidence",
    "admit_package", "load_package", "process_receiver",
]
