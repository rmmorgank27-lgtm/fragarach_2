"""SQLite storage foundation defined by SPEC-001."""

from .database import (
    IntegrityReport,
    backup_database,
    initialize_database,
    open_read_only,
    registered_writer,
    transaction,
    verify_integrity,
)
from .writer import WriterLock, WriterLockError

__all__ = [
    "IntegrityReport",
    "WriterLock",
    "WriterLockError",
    "backup_database",
    "initialize_database",
    "open_read_only",
    "registered_writer",
    "transaction",
    "verify_integrity",
]

