"""Boundary-only network provider adapters."""

from .twelve_data import AcquisitionError, AcquisitionResult, acquire_twelve_data

__all__ = ["AcquisitionError", "AcquisitionResult", "acquire_twelve_data"]
