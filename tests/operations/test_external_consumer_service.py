from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fragarach_ii.commands.get_history import main
from fragarach_ii.external_consumer_service import CATALOG_CONTRACT, CONTRACT, HistoryService
from fragarach_ii.history_depth import D1_MORPHIX_MIN_OBSERVATIONS
from fragarach_ii.storage import open_read_only, registered_writer
from fragarach_ii.synthetic_repository import SyntheticRepository
from tests.operations.test_spec045_synthetic_repository import add_intraday
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
            self.assertIn(response["lane_status"], {"GOLD", "GREEN", "AMBER", "RED"})
            self.assertEqual(
                response["lane_status_contract"]["contract"],
                "fragarach_ii.lane_status.v1",
            )
            self.assertEqual(
                response["lane_status_contract"]["consumer_guidance"]["safety_days_eligible"],
                ["GOLD", "GREEN", "AMBER"],
            )
            self.assertEqual(
                response["authority"],
                "GREEN" if response["lane_status"] == "GOLD" else response["lane_status"],
            )

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

    def test_extreme_fx_outlier_is_never_served_as_green(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            dates = [f"2026-07-{day:02d}" for day in range(1, 13)]
            _create_lane(database, "AUDUSD", dates)
            with registered_writer(database) as connection:
                connection.execute(
                    "UPDATE bars SET open='0.59',high='0.596',low='0.584',close='0.591'"
                )
                connection.execute(
                    "UPDATE bars SET high='1.71632' WHERE open_time_utc=strftime('%s','2026-07-07')"
                )

            response = HistoryService(database).get_history("AUDUSD", "D1")

        self.assertEqual(response["status"], "AVAILABLE")
        self.assertEqual(response["authority"], "RED")
        self.assertIn("EXTREME_PRICE_OUTLIER", response["reason"])

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

    def test_echo_can_read_authorised_derived_m15_but_real_only_cannot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            _create_lane(database, "AUDUSD", ["2026-07-13"])
            start = int(datetime(2026, 7, 13, 21, tzinfo=UTC).timestamp())
            add_intraday(database, "M5", start, 6, 300)
            add_intraday(database, "M30", start, 2, 1800)
            add_intraday(database, "H1", start, 1, 3600)
            repository = SyntheticRepository(database)
            repository.activate_registry(generate_on_activation=False)
            repository.generate(
                "AUDUSD:M15",
                generated_at=datetime(2026, 7, 13, 22, tzinfo=UTC),
            )
            service = HistoryService(database)

            denied = service.get_history("AUDUSD", "M15")
            allowed = service.get_history(
                "AUDUSD", "M15", consumer="com.raymorgan.echo",
                evidence_requirement="SYNTHETIC_PERMITTED",
            )
            catalogue = service.list_histories(
                consumer="com.raymorgan.echo",
                evidence_requirement="SYNTHETIC_PERMITTED",
            )

            self.assertEqual(denied["status"], "SYNTHETIC_NOT_PERMITTED")
            self.assertEqual(
                (
                    allowed["status"], allowed["authority"],
                    allowed["evidence_class"], allowed["bar_count"],
                ),
                ("AVAILABLE", "AMBER", "SYNTHETIC", 2),
            )
            self.assertEqual(
                [
                    row["timeframe"] for row in catalogue["histories"]
                    if row["symbol"] == "AUDUSD" and row["timeframe"] == "M15"
                ],
                ["M15"],
            )

    def test_estate_catalogue_requires_d1_depth_before_morphix_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            shallow = Path(directory) / "shallow.sqlite3"
            _create_lane(shallow, "AUDUSD", ["2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09"])

            payload = HistoryService(shallow).get_catalogue()

            history = next(row for row in payload["symbols"] if row["symbol"] == "AUDUSD")["histories"][0]
            self.assertEqual(history["bar_count"], 4)
            self.assertFalse(history["eligible_for_morphix"])
            self.assertEqual(history["minimum_required_bar_count"], D1_MORPHIX_MIN_OBSERVATIONS)
            self.assertIn(history["morphix_eligibility_reason"], {"PROVIDER_HISTORY_LIMIT", "SHORT_HISTORY_FETCH_USED"})

        with tempfile.TemporaryDirectory() as directory:
            deep = Path(directory) / "deep.sqlite3"
            start = date(2025, 1, 1)
            dates = [
                (start + timedelta(days=offset)).isoformat()
                for offset in range(D1_MORPHIX_MIN_OBSERVATIONS)
            ]
            _create_lane(deep, "BTCUSD", dates)

            payload = HistoryService(deep).get_catalogue()

            history = next(row for row in payload["symbols"] if row["symbol"] == "BTCUSD")["histories"][0]
            self.assertEqual(history["bar_count"], D1_MORPHIX_MIN_OBSERVATIONS)
            self.assertTrue(history["eligible_for_morphix"])
            self.assertIsNone(history["morphix_eligibility_reason"])


if __name__ == "__main__":
    unittest.main()
