"""Continuously admit accepted Global Prime energy packages from Datagather."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import signal
import tempfile
import time
from typing import Any
import zipfile

from .energy_mt5 import admit_energy_mt5
from .external_consumer_service import canonical_database_path
from .storage import WriterLockError


CONTRACT = "fragarach_ii.global_prime_energy_importer.v1"
TRANSPORT_LANE = "fragarach.market_data"
MANIFEST_CONTRACT = "global_prime.mt5.market_data_package.v1"
LANE_ID = "fragarach.energy.m5.v1"
SYMBOL_FILES = {"USOIL": "XTIUSD_M5.csv", "UKOIL": "XBRUSD_M5.csv"}


class EnergyPackageError(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_name(name: str) -> bool:
    if not name or "\\" in name or name.startswith("/"):
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _json(payload: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EnergyPackageError(f"INVALID_JSON:{name}") from error
    if not isinstance(value, dict):
        raise EnergyPackageError(f"INVALID_JSON_OBJECT:{name}")
    return value


def _checksums(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise EnergyPackageError("INVALID_CHECKSUM_INVENTORY") from error
    for line in lines:
        digest, separator, name = line.partition("  ")
        if separator != "  " or len(digest) != 64 or not _safe_name(name) or name in result:
            raise EnergyPackageError("INVALID_CHECKSUM_INVENTORY")
        result[name] = digest
    return result


def load_package(path: str | Path, receipt: dict[str, Any]) -> dict[str, Any]:
    selected = Path(path).expanduser().resolve()
    body = selected.read_bytes()
    if receipt.get("lane") != TRANSPORT_LANE or receipt.get("status") not in {"ACCEPTED", "DUPLICATE"}:
        raise EnergyPackageError("RECEIPT_NOT_ACCEPTED")
    if receipt.get("package_sha256") != _sha256(body):
        raise EnergyPackageError("RECEIPT_PACKAGE_HASH_MISMATCH")
    try:
        archive = zipfile.ZipFile(selected, "r")
    except (OSError, zipfile.BadZipFile) as error:
        raise EnergyPackageError("INVALID_ZIP") from error
    with archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(not _safe_name(name) for name in names):
            raise EnergyPackageError("UNSAFE_ZIP_NAMES")
        files = {name: archive.read(name) for name in names if not name.endswith("/")}
    required = {"SHA256SUMS.txt", "transport-envelope.json", "manifest.json"}
    if not required.issubset(files):
        raise EnergyPackageError("PACKAGE_FILES_MISSING")
    inventory = _checksums(files["SHA256SUMS.txt"])
    if set(inventory) != set(files) - {"SHA256SUMS.txt"}:
        raise EnergyPackageError("CHECKSUM_COVERAGE_MISMATCH")
    if any(_sha256(files[name]) != digest for name, digest in inventory.items()):
        raise EnergyPackageError("EMBEDDED_CHECKSUM_MISMATCH")
    manifest = _json(files["manifest.json"], "manifest.json")
    if manifest.get("contract") != MANIFEST_CONTRACT or manifest.get("lane_id") != LANE_ID:
        raise EnergyPackageError("MANIFEST_CONTRACT_MISMATCH")
    required = {"coverage-report.json", "payload/raw/XTIUSD_M5.csv", "payload/raw/XBRUSD_M5.csv"}
    if not required.issubset(files):
        raise EnergyPackageError("ENERGY_PACKAGE_FILES_MISSING")
    envelope = _json(files["transport-envelope.json"], "transport-envelope.json")
    coverage = _json(files["coverage-report.json"], "coverage-report.json")
    if manifest.get("provider") != "GLOBAL_PRIME" or manifest.get("platform") != "MT5":
        raise EnergyPackageError("PROVIDER_IDENTITY_MISMATCH")
    if set(manifest.get("native_timeframes") or ()) != {"M5"}:
        raise EnergyPackageError("NATIVE_TIMEFRAME_MISMATCH")
    exact = manifest.get("exact_terminal_symbols") or {}
    labels = manifest.get("canonical_labels") or {}
    if set(exact) != {"XTIUSD", "XBRUSD"} or any(exact[symbol].get("name") != symbol for symbol in exact):
        raise EnergyPackageError("EXACT_SYMBOLS_MISMATCH")
    if labels != {"XTIUSD": "USOIL", "XBRUSD": "UKOIL"}:
        raise EnergyPackageError("CANONICAL_LABELS_MISMATCH")
    for key in ("message_id", "request_id", "export_run_id"):
        if envelope.get(key) != receipt.get(key):
            raise EnergyPackageError(f"RECEIPT_IDENTITY_MISMATCH:{key}")
    series = coverage.get("series") or {}
    for provider_symbol, canonical in labels.items():
        detail = series.get(f"{provider_symbol}_M5") or {}
        raw_name = f"payload/raw/{provider_symbol}_M5.csv"
        if (
            detail.get("canonical_label") != canonical
            or detail.get("exact_provider_symbol") != provider_symbol
            or detail.get("native_timeframe") != "M5"
            or detail.get("strict_ordering") is not True
            or detail.get("unique") is not True
            or detail.get("per_file_sha256", {}).get(raw_name) != _sha256(files[raw_name])
        ):
            raise EnergyPackageError(f"SERIES_PROOF_MISMATCH:{provider_symbol}")
    return {
        "path": selected,
        "package_sha256": _sha256(body),
        "receipt": receipt,
        "manifest": manifest,
        "payloads": {canonical: files[f"payload/raw/{provider_symbol}_M5.csv"] for provider_symbol, canonical in labels.items()},
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


def _state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    if value.get("contract") != CONTRACT:
        value = {"contract": CONTRACT, "processed_package_sha256": []}
    return value


def _receipts(receiver: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in (receiver / "receipts").glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("lane") == TRANSPORT_LANE and value.get("status") in {"ACCEPTED", "DUPLICATE"}:
            result.append(value)
    result.sort(key=lambda item: (str(item.get("received_utc") or ""), str(item.get("message_id") or "")))
    return result


def process_receiver(database_path: str | Path, receiver_root: str | Path, state_path: str | Path) -> dict[str, Any]:
    receiver = Path(receiver_root).expanduser().resolve()
    state_file = Path(state_path).expanduser().resolve()
    state = _state(state_file)
    processed = set(map(str, state.get("processed_package_sha256") or []))
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for receipt in _receipts(receiver):
        checksum = str(receipt.get("package_sha256") or "")
        if not checksum or checksum in processed:
            continue
        package_path = receiver / str(receipt.get("accepted_object") or "")
        try:
            package = load_package(package_path, receipt)
        except EnergyPackageError as error:
            processed.add(checksum)
            skipped.append({"package_sha256": checksum, "reason": str(error)})
            continue
        candidates.append(package)
    superseded: list[str] = []
    if not state.get("last_success_utc") and len(candidates) > 1:
        for package in candidates[:-1]:
            checksum = str(package["package_sha256"])
            processed.add(checksum)
            superseded.append(checksum)
        candidates = candidates[-1:]
    admitted: list[dict[str, Any]] = []
    for package in candidates:
        with tempfile.TemporaryDirectory(prefix="fragarach-energy-package-") as temporary:
            files: dict[str, Path] = {}
            for canonical, name in SYMBOL_FILES.items():
                path = Path(temporary) / name
                path.write_bytes(package["payloads"][canonical])
                files[canonical] = path
            result = admit_energy_mt5(
                database_path, usoil_file=files["USOIL"], ukoil_file=files["UKOIL"],
            )
        processed.add(str(package["package_sha256"]))
        admitted.append({
            "package_sha256": package["package_sha256"],
            "message_id": package["receipt"]["message_id"],
            "received_utc": package["receipt"]["received_utc"],
            "results": result["results"],
        })
        state.update({
            "last_success_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "last_message_id": package["receipt"]["message_id"],
            "last_package_sha256": package["package_sha256"],
        })
    state.update({
        "contract": CONTRACT, "status": "HEALTHY",
        "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "processed_package_sha256": sorted(processed)[-2000:],
        "newly_admitted_count": len(admitted),
        "superseded_bootstrap_count": len(superseded),
        "skipped_non_energy_count": len(skipped),
    })
    state.pop("error", None)
    _atomic_json(state_file, state)
    return {"status": "HEALTHY", "admitted": admitted, "superseded": superseded, "skipped": skipped, "state": state}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=canonical_database_path())
    parser.add_argument("--receiver-root", type=Path, default=Path.home() / "Library/Application Support/Datagather/MT5Receiver")
    parser.add_argument("--state", type=Path, default=Path(__file__).resolve().parents[2] / "data/runtime/global-prime-energy-importer.json")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=20.0)
    args = parser.parse_args(argv)
    stop = False

    def request_stop(*_unused: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    while not stop:
        try:
            result = process_receiver(args.database, args.receiver_root, args.state)
        except WriterLockError as error:
            result = _state(args.state)
            result.update({"status": "RETRYING_WRITER_BUSY", "last_retry_reason": str(error)})
            _atomic_json(args.state, result)
        except Exception as error:
            result = _state(args.state)
            result.update({"status": "FAILED", "error": str(error)})
            _atomic_json(args.state, result)
            if not args.watch:
                print(json.dumps(result, sort_keys=True, separators=(",", ":")))
                return 1
        if not args.watch:
            print(json.dumps(result, sort_keys=True, separators=(",", ":")))
            return 0
        deadline = time.monotonic() + max(5.0, args.poll_seconds)
        while not stop and time.monotonic() < deadline:
            time.sleep(min(1.0, deadline - time.monotonic()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
