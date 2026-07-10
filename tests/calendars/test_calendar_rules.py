from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from fragarach_ii.calendars import CalendarRegistry, ConfigurationError
from fragarach_ii.calendars.models import CalendarDefinition, CalendarOverride
from fragarach_ii.calendars.rules import good_friday
from fragarach_ii.calendars.sessions import expected_session_dates, session_classification


class CalendarRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CalendarRegistry()

    def test_crypto_expects_every_day_of_ordinary_week(self) -> None:
        calendar = self.registry.calendar_by_id("CRYPTO_D1_V1")
        sessions, _ = expected_session_dates(date(2026, 7, 6), date(2026, 7, 12), calendar)
        self.assertEqual(len(sessions), 7)

    def test_fx_weekends_and_published_recurring_closures(self) -> None:
        calendar = self.registry.calendar_by_id("FX_D1_V1")
        self.assertFalse(session_classification(date(2026, 7, 11), calendar)[0])
        self.assertFalse(session_classification(date(2026, 1, 1), calendar)[0])
        self.assertFalse(session_classification(date(2025, 12, 25), calendar)[0])
        self.assertTrue(session_classification(date(2026, 7, 3), calendar)[0])
        # No observed weekday closure is invented when Christmas falls on Sunday.
        self.assertTrue(session_classification(date(2022, 12, 26), calendar)[0])

    def test_metals_good_friday_and_early_close_weekdays(self) -> None:
        calendar = self.registry.calendar_by_id("METALS_D1_V1")
        expected = {
            2024: date(2024, 3, 29),
            2025: date(2025, 4, 18),
            2026: date(2026, 4, 3),
        }
        for year, value in expected.items():
            self.assertEqual(good_friday(year), value)
            self.assertFalse(session_classification(value, calendar)[0])
        self.assertTrue(session_classification(date(2026, 12, 24), calendar)[0])
        self.assertFalse(session_classification(date(2026, 7, 11), calendar)[0])

    def test_explicit_overrides_take_precedence_and_are_reported(self) -> None:
        base = self.registry.calendar_by_id("FX_D1_V1")
        calendar = CalendarDefinition(
            calendar_id=base.calendar_id,
            calendar_version=base.calendar_version,
            asset_class=base.asset_class,
            timeframe=base.timeframe,
            timezone_basis=base.timezone_basis,
            effective_from=base.effective_from,
            effective_to=base.effective_to,
            definition_checksum=base.definition_checksum,
            weekdays_expected=base.weekdays_expected,
            recurring_full_day_closures=base.recurring_full_day_closures,
            calculated_closures=base.calculated_closures,
            overrides=(
                CalendarOverride(date(2026, 7, 11), "EXPECTED_OVERRIDE", "Published session"),
                CalendarOverride(date(2026, 7, 10), "CLOSED_OVERRIDE", "Published closure"),
            ),
        )
        self.assertTrue(session_classification(date(2026, 7, 11), calendar)[0])
        self.assertFalse(session_classification(date(2026, 7, 10), calendar)[0])
        _, overrides = expected_session_dates(date(2026, 7, 10), date(2026, 7, 11), calendar)
        self.assertEqual([item["classification"] for item in overrides], ["CLOSED_OVERRIDE", "EXPECTED_OVERRIDE"])

    def test_unknown_calendar_and_symbol_fail_explicitly(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "unknown calendar") as calendar:
            self.registry.calendar_by_id("NOT_A_CALENDAR")
        self.assertEqual(calendar.exception.code, "UNKNOWN_CALENDAR_ID")
        with self.assertRaises(ConfigurationError) as symbol:
            self.registry.calendar_for_symbol("EURUSD")
        self.assertEqual(symbol.exception.code, "CALENDAR_NOT_CONFIGURED")

    def test_calendar_checksum_drift_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(Path("config/calendars"), root / "calendars")
            shutil.copy2("config/symbol_calendars.v1.json", root)
            shutil.copy2("config/gap_doctrine.v1.json", root)
            path = root / "calendars/fx_d1.v1.json"
            data = json.loads(path.read_text())
            data["weekdays_expected"] = [1, 2, 3, 4]
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ConfigurationError) as raised:
                CalendarRegistry(root)
            self.assertEqual(raised.exception.code, "CONFIGURATION_CHECKSUM_DRIFT")


if __name__ == "__main__":
    unittest.main()
