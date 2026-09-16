from datetime import UTC, date, datetime, timedelta

from fragarach_ii.history_summary import history_summary
from tests.validation.test_d1_session_validation import _create_lane
from tests.operations.test_spec063_time_triggered_lane_scheduler import _m5_lane
from tests.operations.test_spec041_scheduler import _add_intraday_bar


def by_tf(result):
    return {row['timeframe']: row for row in result['lanes']}


def test_full_history_recent_windows_and_read_only(tmp_path):
    database = tmp_path / 'authority.sqlite3'
    _create_lane(database, 'AUDUSD', ['2024-01-02', '2025-08-31', '2026-07-30', '2026-07-31', '2026-08-28'])
    before = database.read_bytes()
    result = history_summary(database, 'AUDUSD', at=datetime(2026, 8, 31, tzinfo=UTC))
    rows = by_tf(result)
    daily = rows['D1']
    assert result['trading_days_held'] == 4  # the stored Sunday is not a calendar trading day
    assert daily['total_bars'] == 5
    assert daily['first_bar_utc'] == '2024-01-02T00:00:00+00:00'
    assert daily['last_bar_utc'] == '2026-08-28T00:00:00+00:00'
    assert daily['last_year_bars'] == 4
    assert daily['last_month_bars'] == 2
    assert all(rows[tf]['last_24_hours_bars'] is None for tf in ['MN1', 'W1', 'D1'])
    assert rows['H1']['total_bars'] is None
    assert rows['H1']['status'] == 'TIMEFRAME_NOT_ACTIVE'
    assert database.read_bytes() == before


def test_complete_month_and_week_derived_from_daily(tmp_path):
    database = tmp_path / 'authority.sqlite3'
    dates = []
    current = date(2026, 6, 1)
    while current <= date(2026, 7, 10):
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    _create_lane(database, 'AUDUSD', dates)
    rows = by_tf(history_summary(database, 'AUDUSD', at=datetime(2026, 7, 11, tzinfo=UTC)))
    assert rows['MN1']['total_bars'] == 1
    assert rows['MN1']['first_bar_utc'] == '2026-06-01T00:00:00+00:00'
    assert rows['W1']['total_bars'] == 6
    assert rows['W1']['last_month_bars'] == 4
    assert rows['MN1']['derived'] is True
    assert 'INCOMPLETE_DERIVED_PERIOD_EXCLUDED' in rows['MN1']['warnings']


def test_intraday_24_hours_closed_bars_and_stale_windows(tmp_path):
    database = _m5_lane(tmp_path)
    _add_intraday_bar(database, 'AUDUSD', 'M5', '2026-07-14T00:05:00+00:00', '2026-07-14T00:10:00+00:00')
    observed = datetime(2026, 7, 14, 0, 7, tzinfo=UTC)
    row = by_tf(history_summary(database, 'AUDUSD', at=observed))['M5']
    assert row['total_bars'] == 1  # the 00:05 bar has not closed yet
    assert row['last_24_hours_bars'] == 1
    assert 'shortened trading sessions may reduce' in row['notes'][0]
    assert 'not a confirmed cause' in row['notes'][0]
    boundary = by_tf(history_summary(database, 'AUDUSD', at=datetime(2026, 7, 15, tzinfo=UTC)))['M5']
    assert boundary['last_24_hours_bars'] == 2  # opening time exactly on lower bound included
    stale = by_tf(history_summary(database, 'AUDUSD', at=datetime(2026, 8, 15, tzinfo=UTC)))['M5']
    assert stale['total_bars'] == 2
    assert stale['last_month_bars'] == stale['last_24_hours_bars'] == 0


def test_calendar_windows_clamp_month_end_and_leap_day(tmp_path):
    database = tmp_path / 'authority.sqlite3'
    _create_lane(database, 'AUDUSD', ['2024-01-02'])
    leap = history_summary(database, 'AUDUSD', at=datetime(2024, 2, 29, 12, tzinfo=UTC))
    assert leap['last_year_start_utc'] == '2023-02-28T12:00:00+00:00'
    month_end = history_summary(database, 'AUDUSD', at=datetime(2024, 3, 31, 12, tzinfo=UTC))
    assert month_end['last_month_start_utc'] == '2024-02-29T12:00:00+00:00'


def test_calendar_closures_excluded_without_fractional_daily_counts(tmp_path):
    database = tmp_path / 'authority.sqlite3'
    _create_lane(database, 'AUDUSD', ['2025-12-24', '2025-12-25', '2025-12-26'])
    result = history_summary(database, 'AUDUSD', at=datetime(2025, 12, 27, tzinfo=UTC))
    assert result['trading_days_held'] == 2
    daily = by_tf(result)['D1']
    assert daily['total_bars'] == 3  # inventory is never rewritten to match the calendar
    assert daily['notes'] == []
    assert isinstance(result['trading_days_held'], int)


def test_m15_reads_published_inventory_without_writes_and_flags_stale_source(tmp_path, monkeypatch):
    from fragarach_ii.synthetic_repository import SyntheticRepository
    from fragarach_ii.storage import registered_writer
    from tests.operations.test_spec045_synthetic_repository import add_intraday

    database = tmp_path / 'authority.sqlite3'
    repository_path = tmp_path / 'derived.sqlite3'
    monkeypatch.setenv('FRAGARACH_SYNTHETIC_REPOSITORY', str(repository_path))
    _create_lane(database, 'AUDUSD', ['2026-07-13'])
    start = int(datetime(2026, 7, 13, 21, tzinfo=UTC).timestamp())
    for tf, count, seconds in [('M5', 48, 300), ('M30', 8, 1800), ('H1', 4, 3600)]:
        add_intraday(database, tf, start, count, seconds)
    # Leave one incomplete group: the publisher must exclude it.
    with registered_writer(database) as connection:
        connection.execute("DELETE FROM bars WHERE asset='AUDUSD' AND timeframe='M5' AND open_time_utc=?", (start + 300,))
    repository = SyntheticRepository(database)
    repository.activate_registry(generate_on_activation=False)
    repository.generate('AUDUSD:M15', generated_at=datetime(2026, 7, 14, 2, tzinfo=UTC))
    before = (database.read_bytes(), repository_path.read_bytes())
    result = history_summary(database, 'AUDUSD', at=datetime(2026, 7, 14, 2, tzinfo=UTC))
    row = by_tf(result)['M15']
    assert [lane['timeframe'] for lane in result['lanes']][-3:] == ['M30', 'M15', 'M5']
    assert row['derived'] is True
    assert row['last_active_session_bars'] == 0
    assert row['current_session_bars'] == 15
    assert row['total_bars'] == row['last_year_bars'] == row['last_month_bars'] == row['last_24_hours_bars'] == 15
    assert row['first_bar_utc'] == '2026-07-13T21:15:00+00:00'
    assert row['last_bar_utc'] == '2026-07-14T00:45:00+00:00'
    assert 'M15_DERIVED_HISTORY_INCOMPLETE' in row['warnings']
    assert (database.read_bytes(), repository_path.read_bytes()) == before
    earlier = by_tf(history_summary(database, 'AUDUSD', at=datetime(2026, 7, 13, 21, 20, tzinfo=UTC)))['M15']
    assert earlier['total_bars'] == 0  # first published bar closes at 21:30
    with registered_writer(database) as connection:
        connection.execute("UPDATE lane_state SET state_version=state_version+1 WHERE asset='AUDUSD' AND timeframe='M5'")
    stale = by_tf(history_summary(database, 'AUDUSD', at=datetime(2026, 7, 14, 2, tzinfo=UTC)))['M15']
    assert stale['total_bars'] == 15
    assert 'M15_DERIVED_HISTORY_BEHIND_M5_SOURCE' in stale['warnings']


def test_missing_m15_repository_is_unavailable_and_is_not_created(tmp_path, monkeypatch):
    database = _m5_lane(tmp_path)
    repository_path = tmp_path / 'absent.sqlite3'
    monkeypatch.setenv('FRAGARACH_SYNTHETIC_REPOSITORY', str(repository_path))
    row = by_tf(history_summary(database, 'AUDUSD', at=datetime(2026, 7, 14, 2, tzinfo=UTC)))['M15']
    assert row['status'] == 'UNAVAILABLE'
    assert row['total_bars'] is None
    assert not repository_path.exists()
