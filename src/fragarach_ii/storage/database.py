"""SQLite connection, transaction, integrity, and backup primitives."""

from __future__ import annotations

import sqlite3
import time
from datetime import UTC, datetime
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from .migrations import apply_migrations, verify_migrations
from .schema import APPLICATION_TABLES
from .writer import WriterLock


BUSY_TIMEOUT_MS = 5_000


class _ClosingReadOnlyConnection(sqlite3.Connection):
    """Close read-only connections when their context manager exits.

    ``sqlite3.Connection.__exit__`` commits or rolls back but deliberately does
    not close.  Scheduler snapshots use short-lived ``with open_read_only``
    scopes, so retaining that default leaks database/WAL descriptors on every
    completed scope in a long-lived service.
    """

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


@dataclass(frozen=True)
class IntegrityReport:
    integrity_check: tuple[str, ...]
    foreign_key_violations: tuple[tuple[object, ...], ...]
    application_tables: frozenset[str]
    migrations_verified: bool

    @property
    def ok(self) -> bool:
        return (
            self.integrity_check == ("ok",)
            and not self.foreign_key_violations
            and self.application_tables == APPLICATION_TABLES
            and self.migrations_verified
        )


def initialize_database(database_path: str | Path) -> None:
    """Create or migrate a database while holding registered-writer ownership."""

    with registered_writer(database_path) as connection:
        apply_migrations(connection)


@contextmanager
def registered_writer(
    database_path: str | Path,
    measurement: dict[str, object] | None = None,
) -> Iterator[sqlite3.Connection]:
    """Yield the sole mutable connection, coupled to the process-held lock."""

    path = Path(database_path).expanduser().resolve()
    if not path.parent.is_dir():
        raise FileNotFoundError(f"database parent directory does not exist: {path.parent}")
    writer = WriterLock(path)
    lock_started = time.monotonic()
    with writer:
        if measurement is not None:
            measurement["lock_wait_ms"] = round((time.monotonic() - lock_started) * 1000, 3)
            measurement["writer_identity"] = writer.identity
        connection = sqlite3.connect(
            path,
            timeout=BUSY_TIMEOUT_MS / 1_000,
            isolation_level=None,
        )
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            journal_mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(journal_mode).lower() != "wal":
                raise RuntimeError(f"failed to enable WAL mode: {journal_mode}")
            connection.execute("PRAGMA synchronous = FULL")
            if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise RuntimeError("failed to enable foreign-key enforcement")
            yield connection
        finally:
            if connection.in_transaction:
                connection.rollback()
            connection.close()


def open_read_only(database_path: str | Path) -> sqlite3.Connection:
    """Open an existing authority according to the direct read-only contract."""

    path = Path(database_path).expanduser().resolve()
    uri_path = quote(str(path), safe="/")
    connection = sqlite3.connect(
        f"file:{uri_path}?mode=ro",
        uri=True,
        timeout=BUSY_TIMEOUT_MS / 1_000,
        isolation_level=None,
        factory=_ClosingReadOnlyConnection,
    )
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise RuntimeError("failed to enforce query-only consumer connection")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("failed to enable foreign-key enforcement")
        return connection
    except BaseException:
        connection.close()
        raise


@contextmanager
def transaction(
    connection: sqlite3.Connection,
    measurement: dict[str, object] | None = None,
) -> Iterator[sqlite3.Connection]:
    """Run one explicit immediate transaction with guaranteed rollback."""

    if connection.in_transaction:
        raise RuntimeError("nested transactions are not supported")
    started_at = datetime.now(UTC).isoformat()
    begin_started = time.monotonic()
    try:
        connection.execute("BEGIN IMMEDIATE")
    except sqlite3.Error as error:
        if measurement is not None:
            measurement.update(
                transaction_started_at=started_at,
                lock_wait_ms=round(
                    float(measurement.get("lock_wait_ms", 0) or 0)
                    + (time.monotonic() - begin_started) * 1000,
                    3,
                ),
                sqlite_result_code=getattr(error, "sqlite_errorname", type(error).__name__),
            )
        raise
    if measurement is not None:
        measurement["transaction_started_at"] = started_at
        measurement["lock_wait_ms"] = round(
            float(measurement.get("lock_wait_ms", 0) or 0)
            + (time.monotonic() - begin_started) * 1000,
            3,
        )
    write_started = time.monotonic()
    try:
        yield connection
    except BaseException as error:
        if measurement is not None:
            measurement["write_duration_ms"] = round((time.monotonic() - write_started) * 1000, 3)
            measurement["sqlite_result_code"] = getattr(error, "sqlite_errorname", type(error).__name__)
        connection.rollback()
        raise
    else:
        if measurement is not None:
            measurement["write_duration_ms"] = round((time.monotonic() - write_started) * 1000, 3)
        commit_started = time.monotonic()
        try:
            connection.commit()
        except sqlite3.Error as error:
            try:
                setattr(error, "fragarach_stage", "COMMIT")
            except (AttributeError, TypeError):
                pass
            if measurement is not None:
                measurement["commit_duration_ms"] = round((time.monotonic() - commit_started) * 1000, 3)
                measurement["sqlite_result_code"] = getattr(error, "sqlite_errorname", type(error).__name__)
                measurement["failure_stage"] = "COMMIT"
            raise
        if measurement is not None:
            measurement["commit_duration_ms"] = round((time.monotonic() - commit_started) * 1000, 3)
            measurement["sqlite_result_code"] = "SQLITE_OK"


def verify_integrity(database_path: str | Path) -> IntegrityReport:
    """Apply every structural verification required by SPEC-001."""

    connection = open_read_only(database_path)
    try:
        integrity = tuple(
            row[0] for row in connection.execute("PRAGMA integrity_check").fetchall()
        )
        foreign_keys = tuple(
            tuple(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        tables = frozenset(
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_schema
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
        )
        verify_migrations(connection)
        report = IntegrityReport(integrity, foreign_keys, tables, True)
        if not report.ok:
            raise RuntimeError(f"database integrity verification failed: {report!r}")
        return report
    finally:
        connection.close()


def backup_database(source_path: str | Path, destination_path: str | Path) -> None:
    """Create and verify a consistent SQLite online backup at a new path."""

    destination = Path(destination_path).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"backup destination already exists: {destination}")
    if not destination.parent.is_dir():
        raise FileNotFoundError(
            f"backup parent directory does not exist: {destination.parent}"
        )

    source = open_read_only(source_path)
    target = sqlite3.connect(destination, isolation_level=None)
    try:
        source.backup(target)
    except BaseException:
        target.close()
        source.close()
        destination.unlink(missing_ok=True)
        raise
    else:
        target.close()
        source.close()
    verify_integrity(destination)
