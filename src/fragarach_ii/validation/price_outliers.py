"""Conservative price-plausibility checks for canonical FX daily bars."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Iterable


MIN_REFERENCE_BARS = 8
REFERENCE_RADIUS = 20
MIN_LEVEL_DEVIATION = math.log(1.25)
MIN_ROBUST_Z = 12.0
MIN_LOG_SCALE = 0.0025
GROSS_INTRABAR_RATIO = Decimal("1.5")


@dataclass(frozen=True, slots=True)
class ExtremePriceOutlier:
    timestamp: int
    field: str
    observed: str
    local_median: str | None
    level_ratio: float
    robust_z: float | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def find_extreme_price_outliers(
    rows: Iterable[tuple[int, str, str, str, str]],
    *,
    candidate_timestamps: set[int] | None = None,
) -> tuple[ExtremePriceOutlier, ...]:
    """Find gross FX price errors using local level and dispersion.

    The absolute 25% gate deliberately keeps this detector conservative; the
    robust-z requirement then establishes that the level is also exceptional
    relative to nearby closes.  A 50% one-sided wick is quarantined even when
    a short response does not contain enough neighbours to estimate dispersion.
    """

    parsed: list[tuple[int, tuple[Decimal, Decimal, Decimal, Decimal]]] = []
    for timestamp, open_value, high, low, close in rows:
        try:
            values = tuple(Decimal(value) for value in (open_value, high, low, close))
        except (InvalidOperation, TypeError):
            continue
        if any(not value.is_finite() or value <= 0 for value in values):
            continue
        parsed.append((int(timestamp), values))  # type: ignore[arg-type]
    parsed.sort(key=lambda item: item[0])
    candidates = candidate_timestamps or {item[0] for item in parsed}
    findings: list[ExtremePriceOutlier] = []

    for index, (timestamp, values) in enumerate(parsed):
        if timestamp not in candidates:
            continue
        open_value, high, low, close = values
        gross = _gross_intrabar_field(open_value, high, low, close)
        start = max(0, index - REFERENCE_RADIUS)
        end = min(len(parsed), index + REFERENCE_RADIUS + 1)
        neighbour_closes = [
            float(item[1][3]) for offset, item in enumerate(parsed[start:end], start)
            if offset != index
        ]
        if len(neighbour_closes) < MIN_REFERENCE_BARS:
            if gross is not None:
                field, observed, ratio = gross
                findings.append(
                    ExtremePriceOutlier(timestamp, field, str(observed), None, ratio, None)
                )
            continue

        log_closes = [math.log(value) for value in neighbour_closes]
        centre = median(log_closes)
        mad = median(abs(value - centre) for value in log_closes)
        scale = max(1.4826 * mad, MIN_LOG_SCALE)
        component_findings = []
        for field, observed in zip(("open", "high", "low", "close"), values):
            deviation = abs(math.log(float(observed)) - centre)
            robust_z = deviation / scale
            if deviation >= MIN_LEVEL_DEVIATION and robust_z >= MIN_ROBUST_Z:
                component_findings.append((deviation, field, observed, robust_z))
        if component_findings:
            _, field, observed, robust_z = max(component_findings)
            local_level = math.exp(centre)
            findings.append(
                ExtremePriceOutlier(
                    timestamp=timestamp,
                    field=field,
                    observed=str(observed),
                    local_median=format(local_level, ".10g"),
                    level_ratio=float(observed) / local_level,
                    robust_z=robust_z,
                )
            )
        elif gross is not None:
            field, observed, ratio = gross
            findings.append(
                ExtremePriceOutlier(
                    timestamp, field, str(observed), format(math.exp(centre), ".10g"), ratio,
                    abs(math.log(float(observed)) - centre) / scale,
                )
            )
    return tuple(findings)


def assess_lane_price_quality(
    connection: sqlite3.Connection,
    *,
    symbol: str,
    timeframe: str,
    asset_class: str,
) -> dict[str, object]:
    """Return a read-only truth fact for the commissioned FX D1 detector."""

    if asset_class != "FX" or timeframe != "D1":
        return {"state": "NOT_APPLICABLE", "outlier_count": 0, "findings": []}
    rows = connection.execute(
        """SELECT open_time_utc,open,high,low,close FROM bars
           WHERE asset=? AND timeframe=? ORDER BY open_time_utc""",
        (symbol, timeframe),
    ).fetchall()
    findings = find_extreme_price_outliers(rows)
    return {
        "state": "FAILED" if findings else "PASS",
        "outlier_count": len(findings),
        "findings": [finding.as_dict() for finding in findings],
        "method": "FX_D1_LOCAL_MEDIAN_MAD_V1",
    }


def _gross_intrabar_field(
    open_value: Decimal, high: Decimal, low: Decimal, close: Decimal
) -> tuple[str, Decimal, float] | None:
    upper_body = max(open_value, close)
    lower_body = min(open_value, close)
    high_ratio = high / upper_body
    low_ratio = lower_body / low
    if high_ratio >= GROSS_INTRABAR_RATIO and high_ratio >= low_ratio:
        return "high", high, float(high_ratio)
    if low_ratio >= GROSS_INTRABAR_RATIO:
        return "low", low, float(low / lower_body)
    return None
