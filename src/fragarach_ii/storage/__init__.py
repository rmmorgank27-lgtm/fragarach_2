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
from .outcome import OUTCOME_FORMAT, Rejection, canonical_ingest_outcome
from .validation_summary import (
    VALIDATION_SUMMARY_FORMAT,
    LaneValidationSummary,
)
from .writer import WriterLock, WriterLockError

__all__ = [
    "IntegrityReport",
    "LaneValidationSummary",
    "OUTCOME_FORMAT",
    "Rejection",
    "VALIDATION_SUMMARY_FORMAT",
    "WriterLock",
    "WriterLockError",
    "backup_database",
    "canonical_ingest_outcome",
    "initialize_database",
    "open_read_only",
    "registered_writer",
    "transaction",
    "verify_integrity",
]
