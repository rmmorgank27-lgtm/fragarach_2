"""Immutable models loaded from versioned calendar assets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True, slots=True)
class CalendarOverride:
    date: date
    classification: str
    reason: str


@dataclass(frozen=True, slots=True)
class RecurringClosure:
    month: int
    day: int
    reason: str


@dataclass(frozen=True, slots=True)
class CalendarDefinition:
    calendar_id: str
    calendar_version: int
    asset_class: str
    timeframe: str
    timezone_basis: str
    effective_from: date
    effective_to: date | None
    definition_checksum: str
    weekdays_expected: tuple[int, ...]
    recurring_full_day_closures: tuple[RecurringClosure, ...]
    calculated_closures: tuple[str, ...]
    overrides: tuple[CalendarOverride, ...]
    session_close_local: time = time(0, 0)
    session_timezone: str = "UTC"
    session_close_owner_day_offset: int = 0
    acquisition_delay_seconds: int = 0


@dataclass(frozen=True, slots=True)
class GapDoctrine:
    gap_doctrine_id: str
    gap_doctrine_version: int
    doctrine_checksum: str
    material_classes: tuple[str, ...]
    non_material_classes: tuple[str, ...]
    material_wording: str
    non_material_wording: str
