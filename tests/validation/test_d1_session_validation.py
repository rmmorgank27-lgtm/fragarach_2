from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from fragarach_ii.storage import open_read_only, registered_writer
from fragarach_ii.storage.migrations import apply_migrations
from fragarach_ii.validation import ValidationError, validate_lane


OBSERVED = datetime(2026, 7, 11, 0, 0, tzinfo=UTC)


def _epoch(value: str) -> int:
    return int(datetime.combine(date.fromisoformat(value), datetime.min.time(), UTC).timestamp())


def _create_lane(path: Path, symbol: str, dates: list[str], *, reverse: bool = False) -> None:
    payload = (symbol + " evidence").encode()
    ordered = list(reversed(dates)) if reverse else dates
    with registered_writer(path) as connection:
        apply_migrations(connection)
        connection.execute(
            """INSERT INTO raw_blocks
               (raw_block_id,sha256,source_name,source_locator,media_type,
                received_at_utc,byte_length,payload)
               VALUES ('raw-1',?,'proof','proof','text/plain',?,?,?)""",
            (hashlib.sha256(payload).hexdigest(), OBSERVED.isoformat(), len(payload), payload),
        )
        connection.execute(
            """INSERT INTO ingest_runs
               (ingest_run_id,kind,status,started_at_utc,raw_block_id)
               VALUES ('run-1','proof','registered',?,'raw-1')""",
            (OBSERVED.isoformat(),),
        )
        for index, text in enumerate(ordered, start=1):
            timestamp = _epoch(text)
            connection.execute(
                """INSERT INTO bars
                   (asset,timeframe,open_time_utc,open,high,low,close,
                    created_by_ingest_run_id,updated_by_ingest_run_id)
                   VALUES (?,'D1',?,'1','2','0','1','run-1','run-1')""",
                (symbol, timestamp),
            )
            connection.execute(
                """INSERT INTO provenance
                   (provenance_event_id,ingest_run_id,raw_block_id,symbol,timeframe,
                    timestamp,source_row_number,merge_action,candidate_open,
                    candidate_high,candidate_low,candidate_close,recorded_at)
                   VALUES (?,'run-1','raw-1',?,'D1',?,?, 'INSERT','1','2','0','1',?)""",
                (f"event-{index}", symbol, timestamp, index + 1, OBSERVED.isoformat()),
            )
        connection.execute(
            """INSERT INTO lane_state
               (asset,timeframe,high_watermark_open_time_utc,state_version,
                last_ingest_run_id,updated_at_utc)
               VALUES (?,'D1',?,1,'run-1',?)""",
            (symbol, max(_epoch(value) for value in dates), OBSERVED.isoformat()),
        )


class D1SessionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def validate(self, path: Path, symbol: str, through: str, **values: object):
        return validate_lane(
            path,
            symbol=symbol,
            timeframe="D1",
            through_date=through,
            clock=lambda: OBSERVED,
            **values,
        )

    def test_complete_fx_range_and_weekend_absence(self) -> None:
        path = self.root / "complete.sqlite3"
        _create_lane(path, "AUDUSD", ["2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10"])
        result = self.validate(path, "AUDUSD", "2026-07-12").as_dict()
        self.assertEqual(result["expected_session_count"], 5)
        self.assertEqual(result["missing_expected_session_count"], 0)
        self.assertEqual(result["outside_expected_session_count"], 0)

    def test_missing_weekday_is_non_material_when_week_and_month_represented(self) -> None:
        path = self.root / "missing.sqlite3"
        _create_lane(path, "AUDUSD", ["2026-07-06", "2026-07-08", "2026-07-09", "2026-07-10"])
        result = self.validate(path, "AUDUSD", "2026-07-10").as_dict()
        self.assertEqual(result["missing_session_dates"], ["2026-07-07"])
        self.assertEqual(result["material_gap_count"], 0)
        self.assertEqual(result["non_material_gap_count"], 1)
        self.assertEqual(result["gap_classifications"][0]["classification"], "NON_MATERIAL_BY_GAP_DOCTRINE_V1")

    def test_crypto_reports_weekend_missing_but_fx_does_not(self) -> None:
        crypto = self.root / "crypto.sqlite3"
        _create_lane(crypto, "BTCUSD", ["2026-07-10", "2026-07-13"])
        crypto_result = self.validate(crypto, "BTCUSD", "2026-07-13").as_dict()
        self.assertEqual(crypto_result["missing_session_dates"], ["2026-07-11", "2026-07-12"])
        fx = self.root / "fx.sqlite3"
        _create_lane(fx, "AUDUSD", ["2026-07-10", "2026-07-13"])
        self.assertEqual(self.validate(fx, "AUDUSD", "2026-07-13").as_dict()["missing_session_dates"], [])

    def test_weekend_bar_is_outside_and_future_bar_is_beyond_boundary(self) -> None:
        path = self.root / "outside.sqlite3"
        _create_lane(path, "AUDUSD", ["2026-07-10", "2026-07-11", "2026-07-13"])
        result = self.validate(path, "AUDUSD", "2026-07-11").as_dict()
        self.assertEqual(result["outside_expected_session_dates"], ["2026-07-11"])
        self.assertEqual(result["beyond_declared_boundary_dates"], ["2026-07-13"])

    def test_validation_starts_at_earliest_present_and_asserts_nothing_before(self) -> None:
        path = self.root / "start.sqlite3"
        _create_lane(path, "AUDUSD", ["2026-07-08", "2026-07-09", "2026-07-10"])
        result = self.validate(path, "AUDUSD", "2026-07-10").as_dict()
        self.assertEqual(result["validation_start_date"], "2026-07-08")
        self.assertEqual(result["first_expected_session"], "2026-07-08")
        self.assertEqual(result["expected_session_count"], 3)

    def test_current_edge_and_empty_week_are_material(self) -> None:
        path = self.root / "edge.sqlite3"
        _create_lane(path, "AUDUSD", ["2026-07-03"])
        result = self.validate(path, "AUDUSD", "2026-07-17").as_dict()
        self.assertFalse(result["latest_expected_session_present"])
        self.assertIn("2026-W28", result["empty_week_ids"])
        by_date = {item["date"]: item for item in result["gap_classifications"]}
        self.assertIn("CURRENT_EDGE_MISSING", by_date["2026-07-17"]["reasons"])
        self.assertIn("EMPTY_EXPECTED_WEEK", by_date["2026-07-08"]["reasons"])
        self.assertGreater(result["material_gap_count"], 0)

    def test_empty_month_and_multiple_material_reasons_count_each_date_once(self) -> None:
        path = self.root / "month.sqlite3"
        _create_lane(path, "BTCUSD", ["2026-01-31"])
        result = self.validate(path, "BTCUSD", "2026-02-28").as_dict()
        self.assertEqual(result["empty_month_ids"], ["2026-02"])
        self.assertEqual(result["material_gap_count"], 28)
        last = result["gap_classifications"][-1]
        self.assertEqual(
            last["reasons"],
            ["CURRENT_EDGE_MISSING", "EMPTY_EXPECTED_WEEK", "EMPTY_EXPECTED_MONTH"],
        )

    def test_weekly_and_monthly_summaries_reconcile(self) -> None:
        path = self.root / "reconcile.sqlite3"
        _create_lane(path, "AUDUSD", ["2026-06-29", "2026-07-01", "2026-07-03"])
        result = self.validate(path, "AUDUSD", "2026-07-03").as_dict()
        for key in ("weekly_summaries", "monthly_summaries"):
            self.assertEqual(sum(item["expected_session_count"] for item in result[key]), result["expected_session_count"])
            self.assertEqual(sum(item["present_expected_session_count"] for item in result[key]), result["present_expected_session_count"])
            self.assertEqual(sum(item["missing_expected_session_count"] for item in result[key]), result["missing_expected_session_count"])

    def test_insertion_order_and_wall_clock_do_not_change_checksum(self) -> None:
        dates = ["2026-07-06", "2026-07-08", "2026-07-10"]
        first = self.root / "first.sqlite3"
        second = self.root / "second.sqlite3"
        _create_lane(first, "AUDUSD", dates)
        _create_lane(second, "AUDUSD", dates, reverse=True)
        one = self.validate(first, "AUDUSD", "2026-07-10")
        two = validate_lane(second, symbol="AUDUSD", timeframe="D1", through_date="2026-07-10", clock=lambda: datetime(2030, 1, 1, tzinfo=UTC))
        self.assertEqual(one.result_checksum, two.result_checksum)
        self.assertNotEqual(one.validation_observed_at, two.validation_observed_at)

    def test_no_persist_is_read_only_and_persist_changes_only_summary(self) -> None:
        path = self.root / "persist.sqlite3"
        _create_lane(path, "AUDUSD", ["2026-07-09", "2026-07-10"])
        connection = open_read_only(path)
        try:
            before = connection.execute("SELECT * FROM lane_state").fetchone()
            bars_before = connection.execute("SELECT * FROM bars ORDER BY open_time_utc").fetchall()
        finally:
            connection.close()
        self.validate(path, "AUDUSD", "2026-07-10")
        connection = open_read_only(path)
        try:
            self.assertEqual(connection.execute("SELECT * FROM lane_state").fetchone(), before)
        finally:
            connection.close()
        result = self.validate(path, "AUDUSD", "2026-07-10", persist=True)
        connection = open_read_only(path)
        try:
            after = connection.execute("SELECT * FROM lane_state").fetchone()
            self.assertEqual(after[:-1], before[:-1])
            self.assertEqual(json.loads(after[-1])["result_checksum"], result.result_checksum)
            self.assertEqual(connection.execute("SELECT * FROM bars ORDER BY open_time_utc").fetchall(), bars_before)
        finally:
            connection.close()

    def test_unknown_symbol_timeframe_and_boundary_do_not_mutate(self) -> None:
        path = self.root / "error.sqlite3"
        _create_lane(path, "AUDUSD", ["2026-07-10"])
        connection = open_read_only(path)
        try:
            before = connection.execute("SELECT * FROM lane_state").fetchone()
        finally:
            connection.close()
        cases = (
            ({"symbol": "EURUSD", "timeframe": "D1", "through_date": "2026-07-10", "persist": True}, "UNREGISTERED_LANE"),
            ({"symbol": "AUDUSD", "timeframe": "H1", "through_date": "2026-07-10", "persist": True}, "UNSUPPORTED_TIMEFRAME"),
            ({"symbol": "AUDUSD", "timeframe": "D1", "through_date": "07/10/2026", "persist": True}, "INVALID_THROUGH_DATE"),
        )
        for arguments, code in cases:
            with self.assertRaises(ValidationError) as raised:
                validate_lane(path, **arguments)
            self.assertEqual(raised.exception.code, code)
        connection = open_read_only(path)
        try:
            self.assertEqual(connection.execute("SELECT * FROM lane_state").fetchone(), before)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
