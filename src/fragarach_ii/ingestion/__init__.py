"""The single canonical ingestion pipeline."""

from .pipeline import RawEvidence, ingest_staged_batch

__all__ = ["RawEvidence", "ingest_staged_batch"]
