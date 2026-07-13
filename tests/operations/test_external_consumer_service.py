from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fragarach_ii.commands.get_history import main
from fragarach_ii.external_consumer_service import CATALOG_CONTRACT, CONTRACT, HistoryService
from fragarach_ii.storage import open_read_only
from tests.validation.test_d1_session_validation import _create_lane


class ExternalConsumerServiceTests(unittest.TestCase):
    def test_complete_history_matches_canonical_rows_and_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
            before = database.read_bytes()

            response = HistoryService(database).get_history("audusd", "d1")

            self.assertEqual(response["contract"], CONTRACT)
            self.assertEqual(response["status"], "AVAILABLE")
            self.assertEqual(response["symbol"], "AUDUSD")
            self.assertEqual(response["timeframe"], "D1")
            self.assertEqual(response["bar_count"], 2)
            self.assertEqual(response["first_bar"], "2026-07-09T00:00:00+00:00")
            self.assertEqual(response["last_bar"], "2026-07-10T00:00:00+00:00")
            self.assertEqual(response["CAODT"], response["last_bar"])
            self.assertIsInstance(response["truth_score"], int)
            self.assertIn(response["authority"], {"GREEN", "AMBER", "RED"})

            with open_read_only(database) as connection:
                canonical = connection.execute(
                    "SELECT open_time_utc,open,high,low,close,volume FROM bars ORDER BY open_time_utc"
                ).fetchall()
            self.assertEqual(
                response["bars"],
                [
                    {
                        "timestamp": row[0],
                        "open": row[1],
                        "high": row[2],
                        "low": row[3],
                        "close": row[4],
                        "volume": row[5],
                    }
                    for row in canonical
                ],
            )
            self.assertEqual(database.read_bytes(), before)

    def test_unavailable_data_is_explicit_and_never_fabricated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            response = HistoryService(database).get_history("AAPL", "D1")
            self.assertEqual(response["status"], "NOT_REGISTERED")
            self.assertEqual(response["bar_count"], 0)
            self.assertEqual(response["bars"], [])

    def test_cli_request_contains_only_symbol_and_timeframe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "BTCUSD", ["2026-07-10"])
            output = io.StringIO()
            with patch.dict(
                os.environ, {"FRAGARACH_AUTHORITY_DATABASE": str(database)}
            ), contextlib.redirect_stdout(output):
                code = main(
                    ["--symbol", "BTCUSD", "--timeframe", "D1", "--json"]
                )
            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "AVAILABLE")
            self.assertEqual(payload["bar_count"], 1)

    def test_catalog_lists_servable_authority_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
            before = database.read_bytes()

            payload = HistoryService(database).list_histories()

            self.assertEqual(payload["contract"], CATALOG_CONTRACT)
            self.assertEqual(payload["status"], "AVAILABLE")
            history = next(row for row in payload["histories"] if row["symbol"] == "AUDUSD")
            self.assertEqual((history["timeframe"], history["bar_count"]), ("D1", 2))
            self.assertEqual(database.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
