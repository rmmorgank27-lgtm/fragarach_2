from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.commands.get_market_history import main
from fragarach_ii.market_history_service import (
    DerivedContributor,
    DerivedTargetInterval,
    MARKET_HISTORY_RESPONSE_KEYS,
    MarketHistoryService,
    MarketHistoryServiceError,
    MarketHistoryWindow,
    construct_bounded_derived_view,
)
from tests.validation.test_d1_session_validation import _create_lane


class MarketHistoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "authority.sqlite3"
        _create_lane(
            self.database,
            "AUDUSD",
            ["2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10"],
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_same_request_has_one_consumer_neutral_answer(self) -> None:
        service = MarketHistoryService(self.database)
        request = MarketHistoryWindow.last_trading_days(2)

        signalbar = service.get_market_history("AUDUSD", "D1", request)
        sea_eagle = service.get_market_history("AUDUSD", "D1", request)
        harp = service.get_market_history("AUDUSD", "D1", request)

        self.assertEqual(signalbar, sea_eagle)
        self.assertEqual(signalbar, harp)
        self.assertEqual(frozenset(signalbar), MARKET_HISTORY_RESPONSE_KEYS)
        self.assertEqual(signalbar["Status"], "AVAILABLE_WITH_WARNINGS")
        self.assertEqual(
            [bar["timestamp"] for bar in signalbar["OHLC"]],
            ["2026-07-09T00:00:00+00:00", "2026-07-10T00:00:00+00:00"],
        )
        forbidden = {
            "provider",
            "evidence",
            "provenance",
            "derivation",
            "source_timeframe",
            "alignment",
            "calendar",
            "session",
            "validation",
            "bar_count",
        }
        self.assertFalse(forbidden & set(signalbar))

    def test_between_window_is_inclusive_and_authority_owned(self) -> None:
        response = MarketHistoryService(self.database).get_market_history(
            "AUDUSD",
            "D1",
            MarketHistoryWindow.between("2026-07-07", "2026-07-09"),
        )
        self.assertEqual(response["Status"], "AVAILABLE_WITH_WARNINGS")
        self.assertEqual(len(response["OHLC"]), 3)
        self.assertEqual(response["CAODT"], "2026-07-10T00:00:00+00:00")

    def test_pending_derived_timeframes_are_stable_unavailable_capabilities(self) -> None:
        service = MarketHistoryService(self.database)
        for timeframe in ("H4", "M15"):
            with self.subTest(timeframe=timeframe):
                response = service.get_market_history(
                    "AUDUSD", timeframe, MarketHistoryWindow.last_trading_days(5)
                )
                self.assertEqual(response["Status"], "TIMEFRAME_NOT_ACTIVE")
                self.assertEqual(response["OHLC"], [])
                self.assertEqual(
                    response["Warnings"],
                    ["CONSTRUCTION_AUTHORITY_NOT_COMMISSIONED"],
                )

    def test_cli_exposes_only_market_history_contract(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(
                [
                    "--database",
                    str(self.database),
                    "--symbol",
                    "AUDUSD",
                    "--timeframe",
                    "D1",
                    "--last-trading-days",
                    "2",
                    "--json",
                ]
            )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(frozenset(payload), MARKET_HISTORY_RESPONSE_KEYS)
        self.assertEqual(len(payload["OHLC"]), 2)

    def test_inactive_derived_engine_is_bounded_deterministic_and_read_only(self) -> None:
        before = self.database.read_bytes()
        contributors = (
            DerivedContributor(100, "1.0", "1.4", "0.9", "1.2"),
            DerivedContributor(200, "1.2", "1.5", "1.1", "1.3"),
        )
        plan = (
            DerivedTargetInterval(100, (100, 200), contributors),
        )

        first = construct_bounded_derived_view(plan)
        second = construct_bounded_derived_view(plan)

        self.assertEqual(first, second)
        self.assertEqual(first[0]["open"], "1.0")
        self.assertEqual(first[0]["high"], "1.5")
        self.assertEqual(first[0]["low"], "0.9")
        self.assertEqual(first[0]["close"], "1.3")
        self.assertEqual(self.database.read_bytes(), before)

    def test_inactive_derived_engine_rejects_incomplete_authority_plan(self) -> None:
        plan = (
            DerivedTargetInterval(
                100,
                (100, 200),
                (DerivedContributor(100, "1.0", "1.4", "0.9", "1.2"),),
            ),
        )
        with self.assertRaisesRegex(
            MarketHistoryServiceError, "authority-supplied interval plan"
        ):
            construct_bounded_derived_view(plan)


if __name__ == "__main__":
    unittest.main()
