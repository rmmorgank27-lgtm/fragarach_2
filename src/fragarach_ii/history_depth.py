"""Shared D1 history-depth policy for initial acquisition and consumers."""

from __future__ import annotations

from datetime import date, timedelta


D1_INITIAL_HISTORY_DAYS = 3652
D1_MORPHIX_MIN_OBSERVATIONS = 200


def governed_d1_initial_start(through_date: date) -> date:
    """Return the approved minimum historical start for a D1 initial fetch."""

    return through_date - timedelta(days=D1_INITIAL_HISTORY_DAYS)


def has_morphix_d1_depth(bar_count: int) -> bool:
    return bar_count >= D1_MORPHIX_MIN_OBSERVATIONS
