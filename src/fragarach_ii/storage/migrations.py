"""Schema migration execution and verification."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from .schema import (
    MIGRATION_1_NAME,
    MIGRATION_1_STATEMENTS,
    MIGRATION_2_NAME,
    MIGRATION_2_STATEMENTS,
    MIGRATION_3_NAME,
    MIGRATION_3_STATEMENTS,
    MIGRATION_4_NAME,
    MIGRATION_4_STATEMENTS,
    MIGRATION_5_NAME,
    MIGRATION_5_STATEMENTS,
    MIGRATION_6_NAME,
    MIGRATION_6_STATEMENTS,
    migration_1_checksum,
    migration_2_checksum,
    migration_3_checksum,
    migration_4_checksum,
    migration_5_checksum,
    migration_6_checksum,
    MIGRATION_7_NAME,
    MIGRATION_7_STATEMENTS,
    migration_7_checksum,
    MIGRATION_8_NAME, MIGRATION_8_STATEMENTS, migration_8_checksum,
    MIGRATION_9_NAME, MIGRATION_9_STATEMENTS, migration_9_checksum,
    MIGRATION_10_NAME, MIGRATION_10_STATEMENTS, migration_10_checksum,
)


class MigrationError(RuntimeError):
    """Raised when stored migration history differs from executable history."""


def apply_migrations(
    connection: sqlite3.Connection,
    *,
    target_version: int = 10,
    fault_after_statement: int | None = None,
    fault_migration_version: int = 2,
) -> None:
    """Apply forward migrations atomically through ``target_version``.

    ``fault_after_statement`` exists solely for deterministic interruption proof.
    ``fault_migration_version`` selects the migration interrupted by that test hook.
    Neither argument is used by runtime initialization.
    """

    if target_version not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        raise ValueError(f"unsupported target migration version: {target_version}")

    migrations = (
        (1, MIGRATION_1_NAME, migration_1_checksum(), MIGRATION_1_STATEMENTS),
        (2, MIGRATION_2_NAME, migration_2_checksum(), MIGRATION_2_STATEMENTS),
        (3, MIGRATION_3_NAME, migration_3_checksum(), MIGRATION_3_STATEMENTS),
        (4, MIGRATION_4_NAME, migration_4_checksum(), MIGRATION_4_STATEMENTS),
        (5, MIGRATION_5_NAME, migration_5_checksum(), MIGRATION_5_STATEMENTS),
        (6, MIGRATION_6_NAME, migration_6_checksum(), MIGRATION_6_STATEMENTS),
        (7, MIGRATION_7_NAME, migration_7_checksum(), MIGRATION_7_STATEMENTS),
        (8, MIGRATION_8_NAME, migration_8_checksum(), MIGRATION_8_STATEMENTS),
        (9, MIGRATION_9_NAME, migration_9_checksum(), MIGRATION_9_STATEMENTS),
        (10, MIGRATION_10_NAME, migration_10_checksum(), MIGRATION_10_STATEMENTS),
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
            fault_after_statement=(
                fault_after_statement if version == fault_migration_version else None
            ),
        )


def verify_migrations(connection: sqlite3.Connection) -> None:
    expected = [
        (1, MIGRATION_1_NAME, migration_1_checksum()),
        (2, MIGRATION_2_NAME, migration_2_checksum()),
        (3, MIGRATION_3_NAME, migration_3_checksum()),
        (4, MIGRATION_4_NAME, migration_4_checksum()),
        (5, MIGRATION_5_NAME, migration_5_checksum()),
        (6, MIGRATION_6_NAME, migration_6_checksum()),
        (7, MIGRATION_7_NAME, migration_7_checksum()),
        (8, MIGRATION_8_NAME, migration_8_checksum()),
        (9, MIGRATION_9_NAME, migration_9_checksum()),
        (10, MIGRATION_10_NAME, migration_10_checksum()),
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
