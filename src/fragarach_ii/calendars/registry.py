"""Load and checksum explicit calendar, symbol, and doctrine registries."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, time
from pathlib import Path
from typing import Any

from .models import (
    CalendarDefinition,
    CalendarOverride,
    GapDoctrine,
    RecurringClosure,
)


_CHECKSUM = re.compile(r"^[0-9a-f]{64}$")


class ConfigurationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class CalendarRegistry:
    def __init__(self, config_root: str | Path | None = None, *, load_symbol_assignments: bool = True) -> None:
        self.config_root = (
            Path(config_root).resolve()
            if config_root is not None
            else Path(__file__).resolve().parents[3] / "config"
        )
        calendar_root = self.config_root / "calendars"
        registry = _load_verified_json(
            calendar_root / "calendar_registry.v1.json",
            "registry_checksum",
            "fragarach_ii.calendar_registry.v1",
        )
        self.calendar_registry_checksum = registry["registry_checksum"]
        self._calendars: dict[str, CalendarDefinition] = {}
        for calendar_id, filename in sorted(registry["calendars"].items()):
            raw = _load_verified_json(
                calendar_root / filename,
                "definition_checksum",
                "fragarach_ii.calendar_definition.v1",
            )
            if raw.get("calendar_id") != calendar_id:
                raise ConfigurationError(
                    "CALENDAR_ID_MISMATCH",
                    f"registry key {calendar_id} disagrees with definition",
                )
            self._calendars[calendar_id] = _parse_calendar(raw)

        if load_symbol_assignments:
            symbol_registry = _load_verified_json(self.config_root / "symbol_calendars.v1.json", "registry_checksum", "fragarach_ii.symbol_calendars.v1")
            self.symbol_registry_checksum = symbol_registry["registry_checksum"]
            self._symbols = dict(symbol_registry["symbols"])
        else:
            self.symbol_registry_checksum = "4c14a8a08af532790be70ddd100e499075980cd89a4d624718c3da36deb68c2f"
            self._symbols = {}
        unknown = sorted(set(self._symbols.values()) - set(self._calendars))
        if unknown:
            raise ConfigurationError(
                "UNKNOWN_CALENDAR_ID", f"symbol registry references {unknown}"
            )
        doctrine_raw = _load_verified_json(
            self.config_root / "gap_doctrine.v1.json",
            "doctrine_checksum",
            "fragarach_ii.gap_doctrine.v1",
        )
        self.gap_doctrine = _parse_gap_doctrine(doctrine_raw)

    def calendar_for_symbol(self, symbol: str) -> CalendarDefinition:
        normalized = symbol.strip().upper()
        calendar_id = self._symbols.get(normalized)
        if calendar_id is None:
            raise ConfigurationError(
                "CALENDAR_NOT_CONFIGURED",
                f"no calendar is explicitly configured for {normalized or symbol!r}",
            )
        return self.calendar_by_id(calendar_id)

    def calendar_by_id(self, calendar_id: str) -> CalendarDefinition:
        try:
            return self._calendars[calendar_id]
        except KeyError as error:
            raise ConfigurationError(
                "UNKNOWN_CALENDAR_ID", f"unknown calendar ID: {calendar_id}"
            ) from error


def canonical_definition_checksum(raw: dict[str, Any], checksum_key: str) -> str:
    payload = {key: value for key, value in raw.items() if key != checksum_key}
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _load_verified_json(
    path: Path, checksum_key: str, expected_format: str
) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError("INVALID_CONFIGURATION", f"cannot load {path}: {error}") from error
    if not isinstance(raw, dict) or raw.get("format") != expected_format:
        raise ConfigurationError("INVALID_CONFIGURATION_FORMAT", f"invalid format in {path}")
    stored = raw.get(checksum_key)
    if not isinstance(stored, str) or not _CHECKSUM.fullmatch(stored):
        raise ConfigurationError("INVALID_CONFIGURATION_CHECKSUM", f"invalid checksum in {path}")
    actual = canonical_definition_checksum(raw, checksum_key)
    if actual != stored:
        raise ConfigurationError(
            "CONFIGURATION_CHECKSUM_DRIFT",
            f"checksum drift in {path}: stored={stored}, actual={actual}",
        )
    return raw


def _parse_calendar(raw: dict[str, Any]) -> CalendarDefinition:
    if raw.get("calendar_version") != 1 or raw.get("timeframe") != "D1":
        raise ConfigurationError("UNSUPPORTED_CALENDAR_VERSION", str(raw.get("calendar_id")))
    overrides = []
    for value in raw.get("overrides", []):
        classification = value.get("classification")
        if classification not in {"EXPECTED_OVERRIDE", "CLOSED_OVERRIDE"}:
            raise ConfigurationError("INVALID_CALENDAR_OVERRIDE", str(value))
        reason = value.get("reason")
        if not isinstance(reason, str) or not reason:
            raise ConfigurationError("INVALID_CALENDAR_OVERRIDE", str(value))
        overrides.append(
            CalendarOverride(date.fromisoformat(value["date"]), classification, reason)
        )
    recurring = tuple(
        RecurringClosure(value["month"], value["day"], value["reason"])
        for value in raw.get("recurring_full_day_closures", [])
    )
    calculated = tuple(raw.get("calculated_closures", []))
    if any(value not in {"GOOD_FRIDAY","US_EQUITIES_HOLIDAYS","AUSTRALIAN_EQUITIES_HOLIDAYS","UK_EQUITIES_HOLIDAYS"} for value in calculated):
        raise ConfigurationError("UNKNOWN_CALCULATED_CLOSURE", str(calculated))
    try:
        session_close = time.fromisoformat(raw["session_close_local"])
        session_timezone = str(raw.get("session_timezone", raw["timezone_basis"]))
        owner_offset = int(raw.get("session_close_owner_day_offset", 0))
        acquisition_delay = int(raw.get("acquisition_delay_seconds", 0))
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigurationError(
            "INVALID_SESSION_SCHEDULE", str(raw.get("calendar_id"))
        ) from error
    if owner_offset not in {0, 1} or acquisition_delay < 0:
        raise ConfigurationError(
            "INVALID_SESSION_SCHEDULE", str(raw.get("calendar_id"))
        )
    return CalendarDefinition(
        calendar_id=raw["calendar_id"],
        calendar_version=raw["calendar_version"],
        asset_class=raw["asset_class"],
        timeframe=raw["timeframe"],
        timezone_basis=raw["timezone_basis"],
        effective_from=date.fromisoformat(raw["effective_from"]),
        effective_to=(date.fromisoformat(raw["effective_to"]) if raw["effective_to"] else None),
        definition_checksum=raw["definition_checksum"],
        weekdays_expected=tuple(raw["weekdays_expected"]),
        recurring_full_day_closures=recurring,
        calculated_closures=calculated,
        overrides=tuple(sorted(overrides, key=lambda item: item.date)),
        session_close_local=session_close,
        session_timezone=session_timezone,
        session_close_owner_day_offset=owner_offset,
        acquisition_delay_seconds=acquisition_delay,
    )


def _parse_gap_doctrine(raw: dict[str, Any]) -> GapDoctrine:
    if raw.get("gap_doctrine_version") != 1:
        raise ConfigurationError("UNSUPPORTED_GAP_DOCTRINE_VERSION", str(raw))
    return GapDoctrine(
        gap_doctrine_id=raw["gap_doctrine_id"],
        gap_doctrine_version=raw["gap_doctrine_version"],
        doctrine_checksum=raw["doctrine_checksum"],
        material_classes=tuple(raw["material_classes"]),
        non_material_classes=tuple(raw["non_material_classes"]),
        material_wording=raw["material_wording"],
        non_material_wording=raw["non_material_wording"],
    )
