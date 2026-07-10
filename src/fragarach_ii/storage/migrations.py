"""Schema migration execution and verification."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from .schema import (
    MIGRATION_1_NAME,
    MIGRATION_1_STATEMENTS,
    MIGRATION_2_NAME,
    MIGRATION_2_STATEMENTS,
    migration_1_checksum,
    migration_2_checksum,
)


class MigrationError(RuntimeError):
    """Raised when stored migration history differs from executable history."""


def apply_migrations(
    connection: sqlite3.Connection,
    *,
    target_version: int = 2,
    fault_after_statement: int | None = None,
) -> None:
    """Apply forward migrations atomically through ``target_version``.

    ``fault_after_statement`` exists solely for deterministic interruption proof.
    It applies to migration 2 and is never used by runtime initialization.
    """

    if target_version not in (1, 2):
        raise ValueError(f"unsupported target migration version: {target_version}")

    migrations = (
        (1, MIGRATION_1_NAME, migration_1_checksum(), MIGRATION_1_STATEMENTS),
        (2, MIGRATION_2_NAME, migration_2_checksum(), MIGRATION_2_STATEMENTS),
    )
    for version, name, checksum, statements in migrations[:target_version]:
        existing = _existing_migration(connection, version)
        if existing is not None:
            if existing != (name, checksum):
                raise MigrationError(
                    f"migration {version} history does not match implementation"
                )
            continue
        _apply_one(
            connection,
            version,
            name,
            checksum,
            statements,
            fault_after_statement=fault_after_statement if version == 2 else None,
        )


def verify_migrations(connection: sqlite3.Connection) -> None:
    expected = [
        (1, MIGRATION_1_NAME, migration_1_checksum()),
        (2, MIGRATION_2_NAME, migration_2_checksum()),
    ]
    rows = connection.execute(
        "SELECT version, name, checksum_sha256 FROM schema_migrations ORDER BY version"
    ).fetchall()
    if rows != expected:
        raise MigrationError(f"migration history mismatch: {rows!r}")


def _apply_one(
    connection: sqlite3.Connection,
    version: int,
    name: str,
    checksum: str,
    statements: tuple[str, ...],
    *,
    fault_after_statement: int | None,
) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        for index, statement in enumerate(statements, start=1):
            connection.execute(statement)
            if fault_after_statement == index:
                raise RuntimeError(f"injected migration interruption after statement {index}")
        connection.execute(
            """
            INSERT INTO schema_migrations
                (version, name, checksum_sha256, applied_at_utc)
            VALUES (?, ?, ?, ?)
            """,
            (version, name, checksum, datetime.now(UTC).isoformat()),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


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
