"""Deterministic Gregorian calendar calculations."""

from __future__ import annotations

from datetime import date, timedelta


def easter_sunday(year: int) -> date:
    """Return Gregorian Easter Sunday using the Meeus/Jones/Butcher rule."""

    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = (h + ell - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def good_friday(year: int) -> date:
    return easter_sunday(year) - timedelta(days=2)


def us_equities_holidays(year: int) -> frozenset[date]:
    """Official full-day US equity-market closures for the supported era."""
    values={
        _observed(date(year,1,1)),
        _nth_weekday(year,2,0,3),
        good_friday(year),
        _last_weekday(year,5,0),
        _observed(date(year,7,4)),
        _nth_weekday(year,9,0,1),
        _nth_weekday(year,11,3,4),
        _observed(date(year,12,25)),
    }
    next_new_year=_observed(date(year+1,1,1))
    if next_new_year.year==year:values.add(next_new_year)
    if year>=1998:values.add(_nth_weekday(year,1,0,3))
    if year>=2022:values.add(_observed(date(year,6,19)))
    return frozenset(value for value in values if value.year==year)


def australian_equities_holidays(year: int) -> frozenset[date]:
    """Reviewed full-day ASX cash-market closures for D1 scheduling."""
    values={
        _observed_next_weekday(date(year,1,1)),
        _observed_next_weekday(date(year,1,26)),
        good_friday(year),
        easter_sunday(year)+timedelta(days=1),
        _nth_weekday(year,6,0,2),
    }
    anzac=date(year,4,25)
    if anzac.weekday()<5:values.add(anzac)
    values.update(_christmas_boxing_observed(year))
    return frozenset(value for value in values if value.year==year)


def uk_equities_holidays(year: int) -> frozenset[date]:
    """Reviewed full-day LSE cash-market closures for D1 scheduling."""
    values={
        _observed_next_weekday(date(year,1,1)),
        good_friday(year),
        easter_sunday(year)+timedelta(days=1),
        _nth_weekday(year,5,0,1),
        _last_weekday(year,5,0),
        _last_weekday(year,8,0),
    }
    values.update(_christmas_boxing_observed(year))
    return frozenset(value for value in values if value.year==year)


def _observed(value:date)->date:
    if value.weekday()==5:return value-timedelta(days=1)
    if value.weekday()==6:return value+timedelta(days=1)
    return value


def _observed_next_weekday(value:date)->date:
    if value.weekday()==5:return value+timedelta(days=2)
    if value.weekday()==6:return value+timedelta(days=1)
    return value


def _christmas_boxing_observed(year:int)->set[date]:
    christmas=date(year,12,25)
    boxing=date(year,12,26)
    if christmas.weekday()==5:
        return {date(year,12,27),date(year,12,28)}
    if christmas.weekday()==6:
        return {date(year,12,26),date(year,12,27)}
    if boxing.weekday()==5:
        return {christmas,date(year,12,28)}
    if boxing.weekday()==6:
        return {christmas,date(year,12,27)}
    return {christmas,boxing}


def _nth_weekday(year:int,month:int,weekday:int,n:int)->date:
    value=date(year,month,1)
    return value+timedelta(days=(weekday-value.weekday())%7+7*(n-1))


def _last_weekday(year:int,month:int,weekday:int)->date:
    value=date(year+1,1,1)-timedelta(days=1) if month==12 else date(year,month+1,1)-timedelta(days=1)
    return value-timedelta(days=(value.weekday()-weekday)%7)
