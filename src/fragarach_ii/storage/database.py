"""SQLite connection, transaction, integrity, and backup primitives."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from .migrations import apply_migrations, verify_migrations
from .schema import APPLICATION_TABLES
from .writer import WriterLock


BUSY_TIMEOUT_MS = 5_000


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
def registered_writer(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Yield the sole mutable connection, coupled to the process-held lock."""

    path = Path(database_path).expanduser().resolve()
    if not path.parent.is_dir():
        raise FileNotFoundError(f"database parent directory does not exist: {path.parent}")
    with WriterLock(path):
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
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run one explicit immediate transaction with guaranteed rollback."""

    if connection.in_transaction:
        raise RuntimeError("nested transactions are not supported")
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


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

