"""Read-only chartability audit for commissioned crypto H1 and M5 lanes."""

from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.storage import open_read_only


CONTRACT = "fragarach_ii.crypto_intraday_quality.v1"


def audit_crypto_intraday_quality(
    database_path: str | Path, *, window: int = 270,
) -> dict[str, object]:
    if window < 30:
        raise ValueError("crypto intraday quality window must contain at least 30 bars")
    connection = open_read_only(database_path)
    try:
        lanes = connection.execute(
            """SELECT l.asset,l.timeframe,s.last_ingest_run_id,i.detail
                 FROM evidence_lanes l
                 JOIN instrument_registrations r
                   ON r.asset=l.asset AND r.timeframe=l.registration_timeframe
                 LEFT JOIN lane_state s USING(asset,timeframe)
                 LEFT JOIN ingest_runs i ON i.ingest_run_id=s.last_ingest_run_id
                WHERE r.representation_type='CRYPTO_SPOT_PAIR'
                  AND l.timeframe IN ('H1','M5')
                ORDER BY l.asset,l.timeframe"""
        ).fetchall()
        results = []
        for asset, timeframe, ingest_run_id, detail_text in lanes:
            rows = connection.execute(
                """SELECT open_time_utc,CAST(open AS REAL),CAST(high AS REAL),
                          CAST(low AS REAL),CAST(close AS REAL),CAST(volume AS REAL)
                     FROM bars WHERE asset=? AND timeframe=?
                    ORDER BY open_time_utc DESC LIMIT ?""",
                (asset, timeframe, window),
            ).fetchall()[::-1]
            try:
                detail = json.loads(detail_text) if detail_text else {}
            except (TypeError, json.JSONDecodeError):
                detail = {}
            results.append(assess_crypto_intraday_rows(
                asset=asset,
                timeframe=timeframe,
                rows=rows,
                provider=str(detail.get("provider") or ""),
                provider_symbol=str(detail.get("provider_symbol") or ""),
                ingest_run_id=ingest_run_id,
                requested_window=window,
            ))
    finally:
        connection.close()
    counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "contract": CONTRACT,
        "window": window,
        "lane_count": len(results),
        "status_counts": counts,
        "lanes": results,
    }


def assess_crypto_intraday_rows(
    *,
    asset: str,
    timeframe: str,
    rows: list[tuple[object, ...]],
    provider: str,
    provider_symbol: str,
    ingest_run_id: str | None = None,
    requested_window: int | None = None,
) -> dict[str, object]:
    """Classify price chartability separately from optional volume coverage."""

    count = len(rows)
    if not rows:
        return _result(
            asset, timeframe, provider, provider_symbol, ingest_run_id,
            requested_window, count, "INSUFFICIENT", ("NO_BARS",), {},
        )
    opens = [float(row[1]) for row in rows]
    highs = [float(row[2]) for row in rows]
    lows = [float(row[3]) for row in rows]
    closes = [float(row[4]) for row in rows]
    volumes = [float(row[5] or 0) for row in rows]
    timestamps = [_timestamp_seconds(row[0]) for row in rows]
    expected_step = {"H1": 3600, "M5": 300}.get(timeframe)
    interval_deltas = [right - left for left, right in zip(timestamps, timestamps[1:])]
    unexpected_spacing = (
        sum(delta != expected_step for delta in interval_deltas)
        if expected_step is not None else 0
    )
    missing_intervals = (
        sum(max(0, delta // expected_step - 1) for delta in interval_deltas if delta > 0)
        if expected_step is not None else 0
    )
    ranges = [high - low for high, low in zip(highs, lows, strict=True)]
    invalid = sum(
        not (low <= min(opened, closed) <= max(opened, closed) <= high)
        for opened, high, low, closed in zip(opens, highs, lows, closes, strict=True)
    )
    positive_ranges = [value for value in ranges if value > 0]
    median_range = statistics.median(positive_ranges) if positive_ranges else 0.0
    boundary_gaps = [
        abs(opens[index] - closes[index - 1]) for index in range(1, count)
    ]
    gap_ratios = sorted(
        value / median_range for value in boundary_gaps
    ) if median_range else [0.0 if value == 0 else float("inf") for value in boundary_gaps]
    p95_gap_ratio = (
        gap_ratios[int(0.95 * (len(gap_ratios) - 1))] if gap_ratios else 0.0
    )
    metrics = {
        "bar_count": count,
        "invalid_ohlc_count": invalid,
        "zero_range_ratio": sum(value == 0 for value in ranges) / count,
        "zero_volume_ratio": sum(value == 0 for value in volumes) / count,
        "distinct_close_ratio": len(set(closes)) / count,
        "boundary_mismatch_ratio": (
            sum(opens[index] != closes[index - 1] for index in range(1, count))
            / max(1, count - 1)
        ),
        "p95_boundary_gap_to_median_range": p95_gap_ratio,
        "unexpected_interval_spacing_count": unexpected_spacing,
        "missing_interval_count": missing_intervals,
    }
    reasons: list[str] = []
    if count < 30:
        reasons.append("FEWER_THAN_30_BARS")
    if invalid:
        reasons.append("INVALID_OHLC_GEOMETRY")
    if unexpected_spacing:
        reasons.append("MISSING_OR_MISALIGNED_INTRADAY_INTERVALS")
    if metrics["zero_range_ratio"] >= 0.5:
        reasons.append("MOST_CANDLES_HAVE_NO_PRICE_RANGE")
    distinct_floor = 0.25 if timeframe == "H1" else 0.10
    if count >= 30 and metrics["distinct_close_ratio"] < distinct_floor:
        reasons.append("PRICE_GRID_TOO_COARSE_FOR_CHART")
    thin_binance_usd = (
        provider.upper() == "BINANCE"
        and provider_symbol.upper().endswith("USD")
        and not provider_symbol.upper().endswith(("USDT", "USDC"))
        and metrics["boundary_mismatch_ratio"] >= 0.85
    )
    discontinuous_h1 = (
        timeframe == "H1"
        and metrics["boundary_mismatch_ratio"] >= 0.85
        and p95_gap_ratio >= 0.5
    )
    if discontinuous_h1:
        reasons.append("DISCONTINUOUS_H1_CANDLE_SERIES")
    hard_failure = any(reason in reasons for reason in (
        "INVALID_OHLC_GEOMETRY",
        "MISSING_OR_MISALIGNED_INTRADAY_INTERVALS",
        "MOST_CANDLES_HAVE_NO_PRICE_RANGE",
        "PRICE_GRID_TOO_COARSE_FOR_CHART",
        "DISCONTINUOUS_H1_CANDLE_SERIES",
    ))
    if count < 30:
        status = "INSUFFICIENT"
    elif hard_failure:
        status = "UNUSABLE"
    elif metrics["zero_volume_ratio"] == 1:
        status = "USABLE_PRICE_ONLY"
        reasons.append("VOLUME_UNAVAILABLE")
    elif thin_binance_usd:
        status = "DEGRADED"
        reasons.append("THIN_EXACT_USD_MARKET")
    else:
        status = "USABLE"
    return _result(
        asset, timeframe, provider, provider_symbol, ingest_run_id,
        requested_window, count, status, tuple(reasons), metrics,
    )


def _timestamp_seconds(value: object) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    raw = str(value).strip()
    try:
        return int(raw)
    except ValueError:
        normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("intraday quality timestamps must declare UTC")
        return int(parsed.astimezone(UTC).timestamp())


def _result(
    asset: str,
    timeframe: str,
    provider: str,
    provider_symbol: str,
    ingest_run_id: str | None,
    requested_window: int | None,
    bar_count: int,
    status: str,
    reasons: tuple[str, ...],
    metrics: dict[str, object],
) -> dict[str, object]:
    return {
        "lane": f"{asset}:{timeframe}",
        "asset": asset,
        "timeframe": timeframe,
        "provider": provider or None,
        "provider_symbol": provider_symbol or None,
        "last_ingest_run_id": ingest_run_id,
        "requested_window": requested_window,
        "bar_count": bar_count,
        "status": status,
        "reason_codes": list(reasons),
        "metrics": metrics,
    }
