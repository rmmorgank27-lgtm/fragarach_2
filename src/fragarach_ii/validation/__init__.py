"""Deterministic factual validation; consumers interpret the result."""

from .d1_sessions import ValidationError, validate_lane
from .result import ValidationResult

__all__ = ["ValidationError", "ValidationResult", "validate_lane"]
