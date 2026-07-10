"""Immutable models loaded from versioned calendar assets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


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


@dataclass(frozen=True, slots=True)
class GapDoctrine:
    gap_doctrine_id: str
    gap_doctrine_version: int
    doctrine_checksum: str
    material_classes: tuple[str, ...]
    non_material_classes: tuple[str, ...]
    material_wording: str
    non_material_wording: str
