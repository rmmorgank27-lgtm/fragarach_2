from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from fragarach_ii.authority_service import AUTHORITY_CONTRACT, AuthorityServiceError, serve_historical_authority
from fragarach_ii.commands.serve_authority import main
from fragarach_ii.storage import open_read_only
from tests.validation.test_d1_session_validation import _create_lane


class AuthorityServiceTests(unittest.TestCase):
    def test_standard_contract_is_complete_explainable_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
            before = database.stat().st_mtime_ns
            response = serve_historical_authority(database, symbol="audusd", timeframe="d1")
            self.assertEqual(response["contract"], AUTHORITY_CONTRACT)
            self.assertEqual(response["operational_metadata"]["row_count"], 2)
            self.assertEqual(response["operational_metadata"]["symbol"], "AUDUSD")
            self.assertEqual(response["validation_state"], "LIMITED")
            self.assertEqual(response["gap_summary"]["operational_impact"], "HIGH")
            self.assertEqual(set(response["truth_score"]["components"]), {"authority", "integrity", "freshness", "historical_depth", "continuity"})
            self.assertEqual(response["provider_summary"]["provider_entitlement"], "NOT_RECORDED")
            self.assertEqual(before, database.stat().st_mtime_ns)

    def test_date_range_filters_bars_without_changing_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
            all_rows = serve_historical_authority(database, symbol="AUDUSD", timeframe="D1")
            latest = all_rows["historical_bars"][-1]["open_time_utc"]
            ranged = serve_historical_authority(database, symbol="AUDUSD", timeframe="D1", start_time_utc=latest)
            self.assertEqual(len(ranged["historical_bars"]), 1)
            self.assertEqual(ranged["caodt"], all_rows["caodt"])

    def test_degraded_lane_does_not_block_unrelated_lane(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "authority.sqlite3"
            _create_lane(first, "AUDUSD", ["2026-07-10"])
            response = serve_historical_authority(first, symbol="AUDUSD", timeframe="D1")
            self.assertEqual(response["validation_state"], "LIMITED")
            with self.assertRaises(AuthorityServiceError) as caught:
                serve_historical_authority(first, symbol="NOPE", timeframe="D1")
            self.assertEqual(caught.exception.code, "UNREGISTERED_LANE")
            self.assertEqual(response["operational_metadata"]["row_count"], 1)

    def test_cli_returns_identical_json_contract_and_factual_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-10"])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--database", str(database), "--symbol", "AUDUSD", "--timeframe", "D1", "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["contract"], AUTHORITY_CONTRACT)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--database", str(database), "--symbol", "EURUSD", "--timeframe", "D1", "--json"])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["code"], "UNREGISTERED_LANE")


if __name__ == "__main__":
    unittest.main()
