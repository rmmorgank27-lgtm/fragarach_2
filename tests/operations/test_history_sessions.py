from datetime import UTC, datetime

import pytest

from fragarach_ii.history_sessions import history_sessions
from fragarach_ii.history_summary import history_summary
from tests.operations.test_spec063_time_triggered_lane_scheduler import _m5_lane
from tests.operations.test_spec041_scheduler import _add_intraday_bar

FX = ('AUDUSD', 'FX', 'FX_D1_V1', 1, 'FX')
CRYPTO = ('BTCUSD', 'CRYPTO', 'CRYPTO_D1_V1', 1, 'BINANCE')
STOCK = ('TSLA', 'US_EQUITIES', 'US_EQUITIES_D1_V1', 1, 'NASDAQ')


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


@pytest.mark.parametrize('observed,state,current', [
    ('2026-08-29T12:00:00', 'CLOSED', None),
    ('2026-08-30T20:59:59', 'CLOSED', None),
    ('2026-08-30T21:00:00', 'OPEN', '2026-08-31'),
])
def test_weekend_and_exact_sunday_rollover(observed, state, current):
    result = history_sessions(FX, at(observed))
    assert result['state'] == state
    assert result['last_active']['date'] == '2026-08-28'
    assert (result['current']['date'] if result['current'] else None) == current


@pytest.mark.parametrize('observed,previous_close,current_open', [
    ('2026-03-08T21:00:00', '2026-03-06T22:00:00+00:00', '2026-03-08T21:00:00+00:00'),
    ('2026-11-01T22:00:00', '2026-10-30T21:00:00+00:00', '2026-11-01T22:00:00+00:00'),
])
def test_dst_uses_local_session_boundaries(observed, previous_close, current_open):
    result = history_sessions(FX, at(observed))
    assert result['last_active']['close_utc'] == previous_close
    assert result['current']['open_utc'] == current_open


def test_crypto_midnight_starts_next_session_on_weekends():
    result = history_sessions(CRYPTO, at('2026-08-30T00:00:00'))
    assert result['state'] == 'OPEN'
    assert result['last_active']['date'] == '2026-08-29'
    assert result['current']['date'] == '2026-08-30'


def test_holidays_skipped_and_stock_regular_hours():
    holiday = history_sessions(STOCK, at('2026-07-03T15:00:00'))
    assert holiday['state'] == 'CLOSED'
    assert holiday['last_active']['date'] == '2026-07-02'
    before = history_sessions(STOCK, at('2026-07-06T13:29:59'))
    assert before['state'] == 'CLOSED'
    opened = history_sessions(STOCK, at('2026-07-06T13:30:00'))
    assert opened['current']['date'] == '2026-07-06'
    closed = history_sessions(STOCK, at('2026-07-06T20:00:00'))
    assert closed['state'] == 'CLOSED'
    assert closed['last_active']['date'] == '2026-07-06'
    assert history_sessions(FX, at('2026-12-25T12:00:00'))['state'] == 'CLOSED'


def test_unknown_session_is_unavailable_not_closed():
    result = history_sessions(('UNKNOWN', 'UNKNOWN', 'UNKNOWN', 1, None), at('2026-08-31T14:00:00'))
    assert result['state'] == 'UNAVAILABLE'
    assert result['current'] is None


def test_counts_closed_bars_by_session_without_changing_inventory(tmp_path):
    database = _m5_lane(tmp_path)
    _add_intraday_bar(database, 'AUDUSD', 'M5', '2026-07-13T20:55:00+00:00', '2026-07-13T21:00:00+00:00')
    _add_intraday_bar(database, 'AUDUSD', 'M5', '2026-07-13T21:00:00+00:00', '2026-07-13T21:05:00+00:00')
    _add_intraday_bar(database, 'AUDUSD', 'M5', '2026-07-14T00:05:00+00:00', '2026-07-14T00:10:00+00:00')
    before = database.read_bytes()
    result = history_summary(database, 'AUDUSD', at=at('2026-07-14T00:07:00'))
    rows = {r['timeframe']: r for r in result['lanes']}
    assert result['sessions']['last_active']['date'] == '2026-07-13'
    assert result['sessions']['current']['date'] == '2026-07-14'
    assert rows['M5']['last_active_session_bars'] == 1
    assert rows['M5']['current_session_bars'] == 2
    assert rows['D1']['last_active_session_bars'] == 1
    assert rows['D1']['current_session_bars'] == 0
    assert rows['W1']['last_active_session_bars'] is None
    assert rows['MN1']['current_session_bars'] is None
    weekend = history_summary(database, 'AUDUSD', at=at('2026-07-18T12:00:00'))
    m5 = next(r for r in weekend['lanes'] if r['timeframe'] == 'M5')
    assert m5['current_session_bars'] is None
    assert m5['last_active_session_bars'] == 0  # no data is held for that Friday
    assert database.read_bytes() == before
