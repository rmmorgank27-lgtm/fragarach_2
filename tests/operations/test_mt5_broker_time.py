from __future__ import annotations

from datetime import UTC, datetime

from fragarach_ii.mt5_broker_time import broker_server_to_utc


def test_standard_time_broker_clock_is_utc_plus_two() -> None:
    assert broker_server_to_utc("2026.02.23 16:30:00") == datetime(
        2026, 2, 23, 14, 30, tzinfo=UTC
    )


def test_daylight_time_broker_clock_is_utc_plus_three() -> None:
    assert broker_server_to_utc("2026.09.08 03:33:08") == datetime(
        2026, 9, 8, 0, 33, 8, tzinfo=UTC
    )


def test_us_dst_transition_controls_the_broker_offset() -> None:
    assert broker_server_to_utc("2026.03.09 16:30:00") == datetime(
        2026, 3, 9, 13, 30, tzinfo=UTC
    )
    assert broker_server_to_utc("2026.11.02 16:30:00") == datetime(
        2026, 11, 2, 14, 30, tzinfo=UTC
    )
