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
    IntradayLaneValidationSummary,
)
from .registrations import (Alias, RegistrationCandidate, RegistrationError, RegistrationResult,
    canonical_registration, register_instrument, registration_for_lane)
from .writer import WriterLock, WriterLockError
from .authority_ledger import (AuthorityEventManifest, AuthorityEventResult, AuthorityLedgerError,
    append_authority_event, bootstrap_legacy_authority, canonical_json, inspect_authority,
    prepare_authority_event, reconstruct_authority)

__all__ = [
    "IntegrityReport",
    "LaneValidationSummary",
    "IntradayLaneValidationSummary",
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
    "Alias", "RegistrationCandidate", "RegistrationError", "RegistrationResult",
    "canonical_registration", "register_instrument", "registration_for_lane",
    "AuthorityEventManifest", "AuthorityEventResult", "AuthorityLedgerError",
    "append_authority_event", "bootstrap_legacy_authority", "canonical_json",
    "inspect_authority", "prepare_authority_event", "reconstruct_authority",
]
