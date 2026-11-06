from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from fragarach_ii.commands.get_gator_bootstrap import main
from fragarach_ii.gator_bootstrap_service import (
    CONTRACT,
    GatorBootstrapService,
    _market_session,
)
from fragarach_ii.calendars import CalendarRegistry
from tests.validation.test_d1_session_validation import _create_lane
from fragarach_ii.storage import registered_writer


class GatorBootstrapServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "authority.sqlite3"
        _create_lane(
            self.database,
            "AUDUSD",
            [
                "2026-07-06", "2026-07-07", "2026-07-08",
                "2026-07-09", "2026-07-10",
            ],
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_bundle_caps_lanes_and_includes_governed_derived_history(self) -> None:
        before = self.database.read_bytes()
        payload = GatorBootstrapService(self.database).build(bar_capacity=3)

        self.assertEqual(payload["contract"], CONTRACT)
        self.assertIn(payload["status"], {"AVAILABLE", "AVAILABLE_WITH_WARNINGS"})
        lanes = {
            (lane["symbol"], lane["timeframe"]): lane
            for lane in payload["lanes"]
        }
        self.assertEqual(len(lanes[("AUDUSD", "D1")]["OHLC"]), 3)
        self.assertEqual(
            lanes[("AUDUSD", "D1")]["OHLC"][0]["timestamp"],
            "2026-07-08T00:00:00+00:00",
        )
        self.assertEqual(len(lanes[("AUDUSD", "W1")]["OHLC"]), 1)
        self.assertEqual(lanes[("AUDUSD", "W1")]["Status"], "AVAILABLE")
        self.assertTrue(payload["bundle_revision"].startswith("sha256:"))
        self.assertTrue(lanes[("AUDUSD", "D1")]["lane_fingerprint"].startswith("sha256:"))
        self.assertEqual(self.database.read_bytes(), before)

    def test_cli_returns_the_complete_contract_in_one_response(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main([
                "--database", str(self.database),
                "--bar-capacity", "3",
                "--json",
            ])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["contract"], CONTRACT)
        self.assertEqual(payload["bar_capacity"], 3)
        self.assertIn("AUDUSD", {item["symbol"] for item in payload["symbols"]})
        audusd = next(item for item in payload["symbols"] if item["symbol"] == "AUDUSD")
        self.assertIn(audusd["market_session"]["state"], {"OPEN", "CLOSED"})
        self.assertEqual(audusd["market_session"]["calendar_id"], "FX_24X5_NEW_YORK_ROLLOVER_V1")
        self.assertGreaterEqual(len(payload["lanes"]), 3)

    def test_M30_uses_native_completed_bars_and_public_admission_policy(self) -> None:
        with registered_writer(self.database) as connection:
            connection.execute("""INSERT INTO evidence_lanes
                (asset,timeframe,registration_timeframe,lane_contract,lane_contract_version,created_at_utc)
                VALUES ('AUDUSD','M30','D1','EVIDENCE_LANE_V1',1,'2026-07-06T00:00:00+00:00')""")
            for index in range(5):
                start = 1783296000 + index * 1800
                connection.execute(
                    """INSERT INTO bars (asset,timeframe,open_time_utc,close_time_utc,
                       open,high,low,close,created_by_ingest_run_id,updated_by_ingest_run_id)
                       VALUES ('AUDUSD','M30',?,?, '1','2','0','1','run-1','run-1')""",
                    (start, start + 1800),
                )
            # A stored future/forming candle must not enter the completed tail.
            connection.execute(
                """INSERT INTO bars (asset,timeframe,open_time_utc,close_time_utc,
                   open,high,low,close,created_by_ingest_run_id,updated_by_ingest_run_id)
                   VALUES ('AUDUSD','M30',4102444800,4102446600,'1','2','0','1','run-1','run-1')""",
            )
        before = self.database.read_bytes()
        payload = GatorBootstrapService(self.database).build(bar_capacity=3)
        lane = next(lane for lane in payload['lanes'] if lane['timeframe'] == 'M30')
        self.assertEqual(lane['Status'], 'AVAILABLE')
        self.assertEqual(lane['bar_count'], 3)
        self.assertEqual(lane['OHLC'][-1]['timestamp'], '2026-07-06T02:00:00+00:00')
        symbol = next(symbol for symbol in payload['symbols'] if symbol['symbol'] == 'AUDUSD')
        self.assertIn('M30', [history['timeframe'] for history in symbol['histories']])
        with patch('fragarach_ii.gator_bootstrap_service.market_policy', return_value='INTENTIONALLY_DEFERRED'):
            deferred = GatorBootstrapService(self.database).build(bar_capacity=3)
        rejected = next(lane for lane in deferred['lanes'] if lane['timeframe'] == 'M30')
        self.assertEqual(rejected['Status'], 'UNAVAILABLE')
        self.assertEqual(rejected['Warnings'], ['TIMEFRAME_INTENTIONALLY_DEFERRED'])
        self.assertTrue(next(lane for lane in deferred['lanes'] if lane['timeframe'] == 'D1')['OHLC'])
        self.assertEqual(self.database.read_bytes(), before)

    def test_market_sessions_are_calendar_backed_and_fail_closed(self) -> None:
        registry = CalendarRegistry(load_symbol_assignments=False)
        sunday = datetime(2026, 8, 16, 5, 0, tzinfo=UTC)
        monday_us_cash = datetime(2026, 8, 17, 15, 0, tzinfo=UTC)
        crypto = ("AVAXUSD", "CRYPTO", None, None, None, "CRYPTO_D1_V1", 1, None, "CRYPTO_SPOT_PAIR")
        us_equity = ("AMD", "US_EQUITIES", None, None, None, "US_EQUITIES_D1_V1", 1, "NASDAQ", "COMMON_STOCK")

        self.assertTrue(_market_session(
            crypto, observed_at=sunday, calendar_registry=registry
        )["is_open"])
        self.assertFalse(_market_session(
            us_equity, observed_at=sunday, calendar_registry=registry
        )["is_open"])
        self.assertTrue(_market_session(
            us_equity, observed_at=monday_us_cash, calendar_registry=registry
        )["is_open"])


if __name__ == "__main__":
    unittest.main()
