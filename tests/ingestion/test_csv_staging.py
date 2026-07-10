from __future__ import annotations

import unittest

from fragarach_ii.staging import stage_csv_bytes


NOW = "2026-07-10T00:00:00+00:00"


class CsvStagingTests(unittest.TestCase):
    def stage(self, text: str, **overrides: object):
        arguments = {
            "symbol": " audusd ",
            "timeframe": " d1 ",
            "provider": " manual ",
            "raw_block_id": "raw-proof",
            "received_at": NOW,
        }
        arguments.update(overrides)
        return stage_csv_bytes(text.encode(), **arguments)

    def test_column_order_identity_timestamp_and_missing_volume(self) -> None:
        batch = self.stage(
            "close,timestamp,low,open,high\n"
            "1.0500,2026-07-09,0.900,1.000,1.100\n"
            "1.1,2026-07-10T00:00:00Z,1,1.05,1.2\n"
        )
        self.assertEqual(batch.rejections, ())
        self.assertEqual(len(batch.bars), 2)
        first = batch.bars[0]
        self.assertEqual((first.symbol, first.timeframe), ("AUDUSD", "D1"))
        self.assertEqual(first.values, ("1", "1.1", "0.9", "1.05", None))
        self.assertEqual(first.source_row_number, 2)
        self.assertEqual(first.source_timestamp_text, "2026-07-09")
        self.assertEqual(first.source, "MANUAL_FILE")
        self.assertEqual(first.provider, "MANUAL")

    def test_time_header_maps_to_logical_timestamp_without_changing_source_text(self) -> None:
        batch = self.stage("time,open,high,low,close\n2026-07-09,1,2,0,1\n")
        self.assertEqual(batch.rejections, ())
        self.assertEqual(batch.bars[0].source_timestamp_text, "2026-07-09")

    def test_csv_identity_must_agree_with_explicit_identity(self) -> None:
        batch = self.stage(
            "symbol,timeframe,timestamp,open,high,low,close\n"
            "XAUUSD,D1,2026-07-09,1,2,0,1\n"
        )
        self.assertEqual(batch.rejections[0].code, "IDENTITY_MISMATCH")
        self.assertEqual(batch.rejections[0].source_row_number, 2)

    def test_structural_rejections_are_factual_and_row_specific(self) -> None:
        batch = self.stage(
            "timestamp,open,high,low,close,volume\n"
            "07/09/26,1,2,0,1,1\n"
            "2026-07-10,1,NaN,0,1,1\n"
            "2026-07-11,1,0,2,1,1\n"
            "2026-07-12,1,2,0,1,-1\n"
        )
        self.assertEqual(
            [(item.source_row_number, item.code) for item in batch.rejections],
            [
                (2, "AMBIGUOUS_TIMESTAMP"),
                (3, "NON_FINITE_NUMERIC"),
                (4, "INVALID_OHLC"),
                (5, "INVALID_VOLUME"),
            ],
        )

    def test_exact_duplicates_collapse_and_conflicting_duplicates_reject(self) -> None:
        batch = self.stage(
            "timestamp,open,high,low,close\n"
            "2026-07-09,1.0,2,0,1\n"
            "2026-07-09,1,2.0,0.0,1.0\n"
            "2026-07-10,1,2,0,1\n"
            "2026-07-10,1,2,0,1.5\n"
        )
        self.assertEqual(batch.duplicate_identical, 1)
        self.assertEqual(batch.duplicate_conflicting, 1)
        self.assertEqual(len(batch.bars), 2)
        self.assertEqual(batch.rejections[0].code, "CONFLICTING_DUPLICATE")
        self.assertEqual(batch.rejections[0].source_row_number, 5)

    def test_required_headers_utf8_and_timezone_are_enforced(self) -> None:
        missing = self.stage("timestamp,open,high,low\n2026-07-09,1,2,0\n")
        self.assertEqual(missing.rejections[0].code, "MISSING_COLUMNS")
        invalid_utf8 = stage_csv_bytes(
            b"\xff",
            symbol="AUDUSD",
            timeframe="D1",
            provider="MANUAL",
            raw_block_id="raw-proof",
            received_at=NOW,
        )
        self.assertEqual(invalid_utf8.rejections[0].code, "INVALID_UTF8")
        missing_zone = self.stage(
            "timestamp,open,high,low,close\n2026-07-09T12:00:00,1,2,0,1\n"
        )
        self.assertEqual(missing_zone.rejections[0].code, "MISSING_TIMEZONE")
        duplicate_logical = self.stage(
            "time,timestamp,open,high,low,close\n"
            "2026-07-09,2026-07-09,1,2,0,1\n"
        )
        self.assertEqual(duplicate_logical.rejections[0].code, "DUPLICATE_HEADER")


if __name__ == "__main__":
    unittest.main()
