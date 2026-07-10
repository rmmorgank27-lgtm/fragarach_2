"""Stable structured operations-console boundary for identity, verification, and backup."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.storage import backup_database, verify_integrity


CLI_ID = "fragarach_ii.operations_cli.v1"
CLI_VERSION = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    identity = subparsers.add_parser("identity")
    identity.add_argument("--json", action="store_true", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--database", required=True)
    verify.add_argument("--json", action="store_true", required=True)
    backup = subparsers.add_parser("backup")
    backup.add_argument("--database", required=True)
    backup.add_argument("--destination", required=True)
    backup.add_argument("--json", action="store_true", required=True)
    return parser


def _verification(path: Path) -> dict[str, object]:
    report = verify_integrity(path)
    return {
        "database_path": str(path),
        "exact_seven_tables": len(report.application_tables) == 7,
        "foreign_keys_ok": not report.foreign_key_violations,
        "integrity_ok": report.integrity_check == ("ok",),
        "migration_checksums_ok": report.migrations_verified,
        "read_only_contract": True,
        "tables": sorted(report.application_tables),
        "verified_at_utc": datetime.now(UTC).isoformat(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.operation == "identity":
            payload = {"cli_id": CLI_ID, "cli_version": CLI_VERSION}
        elif arguments.operation == "verify":
            payload = {"cli_id": CLI_ID, **_verification(Path(arguments.database).expanduser().resolve())}
        else:
            source = Path(arguments.database).expanduser().resolve()
            destination = Path(arguments.destination).expanduser().resolve()
            backup_database(source, destination)
            payload = {
                "cli_id": CLI_ID,
                "source_database_path": str(source),
                "backup_path": str(destination),
                "backup_bytes": destination.stat().st_size,
                "backup_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "created_at_utc": datetime.now(UTC).isoformat(),
                "verification": _verification(destination),
            }
    except (FileNotFoundError, FileExistsError, RuntimeError, OSError, sqlite3.Error) as error:
        print(json.dumps({"cli_id": CLI_ID, "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
