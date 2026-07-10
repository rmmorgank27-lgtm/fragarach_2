"""Schema migration execution and verification."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from .schema import MIGRATION_1_NAME, MIGRATION_1_STATEMENTS, migration_1_checksum


class MigrationError(RuntimeError):
    """Raised when stored migration history differs from executable history."""


def apply_migrations(connection: sqlite3.Connection) -> None:
    existing = _existing_migration(connection, 1)
    checksum = migration_1_checksum()
    if existing is not None:
        if existing != (MIGRATION_1_NAME, checksum):
            raise MigrationError("migration 1 history does not match implementation")
        return

    connection.execute("BEGIN IMMEDIATE")
    try:
        for statement in MIGRATION_1_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO schema_migrations
                (version, name, checksum_sha256, applied_at_utc)
            VALUES (?, ?, ?, ?)
            """,
            (1, MIGRATION_1_NAME, checksum, datetime.now(UTC).isoformat()),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def verify_migrations(connection: sqlite3.Connection) -> None:
    expected = (1, MIGRATION_1_NAME, migration_1_checksum())
    rows = connection.execute(
        "SELECT version, name, checksum_sha256 FROM schema_migrations ORDER BY version"
    ).fetchall()
    if rows != [expected]:
        raise MigrationError(f"migration history mismatch: {rows!r}")


def _existing_migration(
    connection: sqlite3.Connection, version: int
) -> tuple[str, str] | None:
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if table_exists is None:
        return None
    row = connection.execute(
        "SELECT name, checksum_sha256 FROM schema_migrations WHERE version = ?", (version,)
    ).fetchone()
    return tuple(row) if row is not None else None

