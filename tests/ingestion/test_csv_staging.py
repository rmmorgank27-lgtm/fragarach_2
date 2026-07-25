from __future__ import annotations

import unittest
from datetime import UTC, datetime

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

    def test_timestamp_utc_header_maps_to_logical_timestamp(self) -> None:
        batch = self.stage(
            "timestamp_utc,open,high,low,close\n"
            "2026-07-10T12:00:00Z,1,2,0,1\n",
            timeframe="M5",
            asset_class="FX",
            received_at="2026-07-10T12:30:00+00:00",
        )
        self.assertEqual(batch.rejections, ())
        self.assertEqual(batch.bars[0].source_timestamp_text, "2026-07-10T12:00:00Z")

    def test_canonical_export_provenance_columns_are_accepted(self) -> None:
        batch = self.stage(
            "timestamp_utc,open,high,low,close,volume,source_event_id,ingest_run_id,raw_symbol,source_exchange_prefix,raw_timeframe\n"
            "2026-07-10T12:00:00Z,1,2,0,1,10,event,run,AUDUSD,,M5\n",
            timeframe="M5",
            asset_class="FX",
            received_at="2026-07-10T12:30:00+00:00",
        )
        self.assertEqual(batch.rejections, ())
        self.assertEqual(len(batch.bars), 1)

    def test_daily_tradingview_slash_dates_are_auto_detected_without_timezone(self) -> None:
        batch = self.stage(
            "timestamp,open,high,low,close\n"
            "13/07/2026,1,2,0,1\n"
            "14/07/2026,1,2,0,1\n"
        )
        self.assertEqual(batch.rejections, ())
        self.assertEqual(
            batch.bars[0].source_timezone_interpretation,
            "D1_DATE_DAY_FIRST_AT_UTC_MIDNIGHT",
        )
        self.assertEqual(batch.bars[0].timestamp, int(datetime(2026, 7, 13, tzinfo=UTC).timestamp()))

    def test_daily_slash_dates_can_use_an_explicit_operator_date_order(self) -> None:
        batch = self.stage(
            "timestamp,open,high,low,close\n"
            "03/04/2026,1,2,0,1\n",
            d1_date_format="DAY_FIRST",
        )
        self.assertEqual(batch.rejections, ())
        self.assertEqual(batch.bars[0].timestamp, int(datetime(2026, 4, 3, tzinfo=UTC).timestamp()))

    def test_unambiguous_year_first_daily_slash_date_needs_no_timezone(self) -> None:
        batch = self.stage("timestamp,open,high,low,close\n2026/07/13,1,2,0,1\n")
        self.assertEqual(batch.rejections, ())
        self.assertEqual(batch.bars[0].source_timezone_interpretation, "D1_DATE_YEAR_FIRST_AT_UTC_MIDNIGHT")

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

    def test_intraday_explicit_offset_is_preserved_and_canonicalised_before_alignment(self) -> None:
        batch=self.stage(
            "timestamp,open,high,low,close\n2026-07-10T12:00:00+03:00,1,2,0,1\n",
            timeframe="H1",asset_class="FX",received_at="2026-07-10T16:30:00+00:00",
        )
        self.assertEqual(batch.rejections,())
        bar=batch.bars[0]
        self.assertEqual(bar.source_timestamp_text,"2026-07-10T12:00:00+03:00")
        self.assertEqual(bar.source_timezone_interpretation,"EXPLICIT_OFFSET:+03:00")
        self.assertEqual(bar.timestamp,int(datetime(2026,7,10,9,tzinfo=UTC).timestamp()))
        self.assertEqual(bar.close_timestamp,bar.timestamp+3600)

    def test_intraday_naive_timestamp_requires_reviewed_timezone_and_never_guesses(self) -> None:
        text="timestamp,open,high,low,close\n2026-07-10T12:00:00,1,2,0,1\n"
        missing=self.stage(text,timeframe="H1",asset_class="FX",received_at="2026-07-10T16:30:00+00:00")
        self.assertEqual(missing.rejections[0].code,"MISSING_TIMEZONE")
        reviewed=self.stage(text,timeframe="H1",asset_class="FX",source_timezone="Etc/GMT-3",received_at="2026-07-10T16:30:00+00:00")
        self.assertEqual(reviewed.rejections,())
        self.assertEqual(reviewed.bars[0].timestamp,int(datetime(2026,7,10,9,tzinfo=UTC).timestamp()))
        self.assertEqual(reviewed.bars[0].source_timezone_interpretation,"REVIEWED_SOURCE_TIMEZONE:Etc/GMT-3:OFFSET=+03:00")

    def test_intraday_quarantine_runs_after_utc_conversion(self) -> None:
        batch=self.stage(
            "timestamp,open,high,low,close\n"
            "2026-07-10T12:30:00+03:00,1,2,0,1\n"
            "2026-07-11T12:00:00+03:00,1,2,0,1\n"
            "2026-07-10T19:00:00+03:00,1,2,0,1\n",
            timeframe="H1",asset_class="FX",received_at="2026-07-10T16:30:00+00:00",
        )
        self.assertEqual([row.code for row in batch.rejections],["MISALIGNED_INTERVAL_OPEN","OUTSIDE_EXPECTED_SESSION","INCOMPLETE_CURRENT_INTERVAL"])

    def test_d1_nonzero_offset_semantics_are_unchanged(self) -> None:
        batch=self.stage("timestamp,open,high,low,close\n2026-07-10T00:00:00+03:00,1,2,0,1\n")
        self.assertEqual(batch.rejections[0].code,"NON_UTC_TIMESTAMP")


if __name__ == "__main__":
    unittest.main()
