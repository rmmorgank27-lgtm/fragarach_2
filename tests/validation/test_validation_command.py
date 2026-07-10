from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.commands.validate_lane import main
from fragarach_ii.storage import open_read_only
from tests.validation.test_d1_session_validation import _create_lane


class ValidationCommandTests(unittest.TestCase):
    def test_json_defaults_to_no_persist_and_explicit_persist_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
            arguments = [
                "--database",
                str(database),
                "--symbol",
                "AUDUSD",
                "--timeframe",
                "D1",
                "--through-date",
                "2026-07-10",
                "--json",
            ]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(arguments), 0)
            initial = json.loads(output.getvalue())
            self.assertFalse(initial["persisted"])
            connection = open_read_only(database)
            try:
                self.assertIsNone(connection.execute("SELECT validation_summary FROM lane_state").fetchone()[0])
            finally:
                connection.close()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([*arguments[:-1], "--persist", "--json"]), 0)
            persisted = json.loads(output.getvalue())
            self.assertTrue(persisted["persisted"])
            self.assertEqual(initial["result_checksum"], persisted["result_checksum"])

    def test_unknown_symbol_returns_factual_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main(
                    [
                        "--database",
                        str(database),
                        "--symbol",
                        "EURUSD",
                        "--timeframe",
                        "D1",
                        "--through-date",
                        "2026-07-10",
                        "--persist",
                        "--json",
                    ]
                )
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(output.getvalue())["code"], "CALENDAR_NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
