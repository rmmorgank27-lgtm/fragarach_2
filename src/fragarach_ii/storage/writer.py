"""Cross-process registered-writer exclusion for SPEC-001."""

from __future__ import annotations

import fcntl
import json
import os
import socket
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any


_PROCESS_STARTED_AT_UTC = datetime.now(UTC).isoformat()


class WriterLockError(RuntimeError):
    """Raised when registered-writer ownership cannot be obtained."""

    def __init__(self, lock_path: Path, owner: dict[str, Any] | None = None) -> None:
        self.lock_path = lock_path
        self.owner = owner
        detail = f"registered writer already owns {lock_path}"
        if owner:
            detail += f" (pid={owner.get('pid')}, host={owner.get('hostname')})"
        super().__init__(detail)


class WriterLock:
    """A process-held exclusive flock with non-authoritative diagnostic metadata."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.lock_path = Path(f"{self.database_path}.writer.lock")
        self._file: IO[bytes] | None = None
        self._token: str | None = None

    @property
    def held(self) -> bool:
        return self._file is not None

    def acquire(self) -> "WriterLock":
        if self.held:
            raise RuntimeError("writer lock instance is already held")
        descriptor = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        lock_file = os.fdopen(descriptor, "r+b", buffering=0)
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            owner = self._read_metadata(lock_file)
            lock_file.close()
            raise WriterLockError(self.lock_path, owner) from error

        self._file = lock_file
        self._token = uuid.uuid4().hex
        try:
            self._write_metadata(
                {
                    "format_version": 1,
                    "state": "held",
                    "database_path": str(self.database_path),
                    "pid": os.getpid(),
                    "hostname": socket.gethostname(),
                    "process_started_at_utc": _PROCESS_STARTED_AT_UTC,
                    "python_executable": sys.executable,
                    "acquired_at_utc": datetime.now(UTC).isoformat(),
                    "ownership_token": self._token,
                }
            )
        except BaseException:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            self._file = None
            self._token = None
            raise
        return self

    def release(self) -> None:
        if self._file is None:
            return
        lock_file = self._file
        try:
            self._write_metadata(
                {
                    "format_version": 1,
                    "state": "released",
                    "database_path": str(self.database_path),
                    "pid": os.getpid(),
                    "hostname": socket.gethostname(),
                    "released_at_utc": datetime.now(UTC).isoformat(),
                    "ownership_token": self._token,
                }
            )
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()
            self._file = None
            self._token = None

    def __enter__(self) -> "WriterLock":
        return self.acquire()

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.release()

    def _write_metadata(self, metadata: dict[str, Any]) -> None:
        if self._file is None:
            raise RuntimeError("cannot write metadata without lock ownership")
        payload = (json.dumps(metadata, sort_keys=True) + "\n").encode("utf-8")
        self._file.seek(0)
        self._file.truncate()
        self._file.write(payload)
        os.fsync(self._file.fileno())

    @staticmethod
    def _read_metadata(lock_file: IO[bytes]) -> dict[str, Any] | None:
        try:
            lock_file.seek(0)
            content = lock_file.read().decode("utf-8")
            value = json.loads(content)
            return value if isinstance(value, dict) else None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
