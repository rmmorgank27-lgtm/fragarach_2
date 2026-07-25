#!/usr/bin/env python3
"""Create a portable, read-only report of governed-estate continuity gaps."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


CADENCE_SECONDS = {"M5": 300, "M30": 1_800, "H1": 3_600, "D1": 86_400}


def iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d %H:%M UTC")


def duration(seconds: int) -> str:
    minutes = seconds // 60
    days, minutes = divmod(minutes, 1_440)
    hours, minutes = divmod(minutes, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def expected_fx_weekend(previous: int, following: int, seconds: int) -> bool:
    if not 44 * 3_600 <= seconds <= 76 * 3_600:
        return False
    # Python weekday: Friday=4, Sunday=6, Monday=0.
    return datetime.fromtimestamp(previous, UTC).weekday() == 4 and datetime.fromtimestamp(
        following, UTC
    ).weekday() in {6, 0}


def query_report(database: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        lane_rows = connection.execute(
            """
            SELECT l.asset,l.timeframe,r.asset_class,count(b.open_time_utc) AS bar_count,
                   min(b.open_time_utc) AS earliest,max(b.open_time_utc) AS latest,
                   ls.validation_summary
            FROM evidence_lanes l
            LEFT JOIN instrument_registrations r
              ON r.asset=l.asset AND r.timeframe='D1'
            LEFT JOIN bars b ON b.asset=l.asset AND b.timeframe=l.timeframe
            LEFT JOIN lane_state ls ON ls.asset=l.asset AND ls.timeframe=l.timeframe
            GROUP BY l.asset,l.timeframe,r.asset_class,ls.validation_summary
            ORDER BY l.asset,l.timeframe
            """
        ).fetchall()
        interval_rows = connection.execute(
            """
            WITH intervals AS (
                SELECT asset,timeframe,open_time_utc AS next_timestamp,
                       lag(open_time_utc) OVER (
                           PARTITION BY asset,timeframe ORDER BY open_time_utc
                       ) AS previous_timestamp
                FROM bars
            )
            SELECT asset,timeframe,previous_timestamp,next_timestamp,
                   next_timestamp-previous_timestamp AS gap_seconds
            FROM intervals
            WHERE previous_timestamp IS NOT NULL
            ORDER BY asset,timeframe,next_timestamp
            """
        ).fetchall()
    finally:
        connection.close()

    lane_metadata: dict[tuple[str, str], dict[str, object]] = {}
    for row in lane_rows:
        validation = json.loads(row["validation_summary"]) if row["validation_summary"] else {}
        missing = validation.get(
            "missing_expected_interval_count",
            validation.get("missing_expected_session_count"),
        )
        lane_metadata[(row["asset"], row["timeframe"])] = {
            "asset_class": row["asset_class"] or "Unknown",
            "bar_count": int(row["bar_count"]),
            "range_start": iso(row["earliest"]) if row["earliest"] is not None else "No data",
            "range_end": iso(row["latest"]) if row["latest"] is not None else "No data",
            "validation_missing": missing if missing is not None else "Not measured",
            "material_gaps": validation.get("material_gap_count", "Not measured"),
            "non_material_gaps": validation.get("non_material_gap_count", "Not measured"),
        }

    details: list[dict[str, object]] = []
    by_lane: defaultdict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    expected_weekends = 0
    for row in interval_rows:
        lane = (row["asset"], row["timeframe"])
        cadence = CADENCE_SECONDS.get(row["timeframe"], 86_400)
        threshold = cadence * (3 if cadence >= 86_400 else 2)
        gap_seconds = int(row["gap_seconds"])
        if gap_seconds <= threshold:
            continue
        if lane_metadata.get(lane, {}).get("asset_class") == "FX" and expected_fx_weekend(
            int(row["previous_timestamp"]), int(row["next_timestamp"]), gap_seconds
        ):
            expected_weekends += 1
            continue
        detail = {
            "symbol": row["asset"],
            "timeframe": row["timeframe"],
            "previous_bar": iso(int(row["previous_timestamp"])),
            "next_bar": iso(int(row["next_timestamp"])),
            "gap": duration(gap_seconds),
            "gap_minutes": gap_seconds // 60,
        }
        details.append(detail)
        by_lane[lane].append(detail)

    lanes: list[dict[str, object]] = []
    for lane, gaps in by_lane.items():
        metadata = lane_metadata[lane]
        largest = max(gaps, key=lambda gap: int(gap["gap_minutes"]))
        most_recent = max(gaps, key=lambda gap: str(gap["next_bar"]))
        lanes.append(
            {
                "symbol": lane[0],
                "timeframe": lane[1],
                "observed_gap_count": len(gaps),
                "largest_gap": largest["gap"],
                "largest_gap_minutes": largest["gap_minutes"],
                "most_recent_gap_end": most_recent["next_bar"],
                "validation_missing": metadata["validation_missing"],
                "material_gaps": metadata["material_gaps"],
                "bars": metadata["bar_count"],
                "available_range": f"{metadata['range_start']} — {metadata['range_end']}",
            }
        )
    lanes.sort(key=lambda lane: (-int(lane["largest_gap_minutes"]), str(lane["symbol"]), str(lane["timeframe"])))
    # Keep the portable report readable while preserving the complete count per
    # lane.  The detail table carries the three largest breaks for each lane;
    # the summary table retains the full observed-gap total.
    detail_samples: list[dict[str, object]] = []
    for lane in sorted(by_lane):
        detail_samples.extend(
            sorted(
                by_lane[lane], key=lambda gap: (-int(gap["gap_minutes"]), str(gap["next_bar"]))
            )[:3]
        )
    detail_samples.sort(key=lambda gap: (str(gap["symbol"]), str(gap["timeframe"]), -int(gap["gap_minutes"])))
    stats = {
        "total_lanes": len(lane_metadata),
        "lanes_with_observed_gaps": len(lanes),
        "observed_gaps": len(details),
        "expected_fx_weekends_excluded": expected_weekends,
    }
    return lanes, detail_samples, stats


def make_artifact(lanes: list[dict[str, object]], details: list[dict[str, object]], stats: dict[str, int]) -> dict[str, object]:
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    source = {
        "id": "estate_gap_query",
        "label": "Fragarach II governed-estate SQLite snapshot",
        "query": {
            "engine": "sqlite",
            "description": "Consecutive governed-bar continuity scan, joined to current lane validation summaries.",
            "sql": "WITH intervals AS (SELECT asset,timeframe,open_time_utc AS next_timestamp,lag(open_time_utc) OVER (PARTITION BY asset,timeframe ORDER BY open_time_utc) AS previous_timestamp FROM bars) SELECT * FROM intervals;",
            "tables_used": ["bars", "evidence_lanes", "instrument_registrations", "lane_state"],
            "filters": ["All current evidence lanes", "Expected FX Friday-to-Sunday/Monday weekend closures excluded"],
            "executed_at": generated_at,
            "language": "sql",
        },
    }
    summary = [{**stats}]
    gap_rank = [
        {
            "lane": f"{lane['symbol']} {lane['timeframe']}",
            "largest_gap_minutes": lane["largest_gap_minutes"],
            "largest_gap": lane["largest_gap"],
        }
        for lane in lanes[:12]
    ]
    return {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": "Estate Gap Report",
            "description": "Current continuity gaps by symbol and timeframe.",
            "generatedAt": generated_at,
            "cards": [
                {
                    "id": "affected_lanes",
                    "description": "Lanes with one or more observed continuity gaps.",
                    "dataset": "summary",
                    "sourceId": "estate_gap_query",
                    "metrics": [{"label": "Affected lanes", "field": "lanes_with_observed_gaps", "format": "number"}],
                },
                {
                    "id": "observed_gaps",
                    "description": "Observed discontinuities after excluding expected FX weekends.",
                    "dataset": "summary",
                    "sourceId": "estate_gap_query",
                    "metrics": [{"label": "Observed gaps", "field": "observed_gaps", "format": "number"}],
                },
                {
                    "id": "scanned_lanes",
                    "description": "Current governed evidence lanes scanned.",
                    "dataset": "summary",
                    "sourceId": "estate_gap_query",
                    "metrics": [{"label": "Lanes scanned", "field": "total_lanes", "format": "number"}],
                },
            ],
            "charts": [
                {
                    "id": "largest_gap_ranking",
                    "title": "Largest observed gap by affected lane",
                    "subtitle": "Top 12 lanes, minutes; expected FX weekend closures excluded.",
                    "type": "bar",
                    "dataset": "gap_rank",
                    "sourceId": "estate_gap_query",
                    "encodings": {
                        "x": {"field": "lane", "type": "ordinal", "label": "Lane"},
                        "y": {"field": "largest_gap_minutes", "type": "quantitative", "label": "Largest gap (minutes)", "format": "number"},
                    },
                    "valueFormat": "number",
                    "layout": "full",
                },
            ],
            "tables": [
                {
                    "id": "lane_gaps",
                    "title": "Affected symbol/timeframe lanes",
                    "dataset": "lane_gaps",
                    "sourceId": "estate_gap_query",
                    "defaultSort": {"field": "largest_gap_minutes", "direction": "desc"},
                    "columns": [
                        {"field": "symbol", "label": "Symbol", "type": "text"},
                        {"field": "timeframe", "label": "TF", "type": "text"},
                        {"field": "observed_gap_count", "label": "Observed gaps", "format": "number"},
                        {"field": "largest_gap", "label": "Largest gap", "type": "text"},
                        {"field": "largest_gap_minutes", "label": "Largest gap (min)", "format": "number"},
                        {"field": "most_recent_gap_end", "label": "Most recent gap ends", "type": "text"},
                        {"field": "validation_missing", "label": "Validation missing", "type": "text"},
                        {"field": "material_gaps", "label": "Material gaps", "type": "text"},
                        {"field": "available_range", "label": "Available range", "type": "text"},
                    ],
                },
                {
                    "id": "gap_details",
                    "title": "Largest observed gaps by lane",
                    "dataset": "gap_details",
                    "sourceId": "estate_gap_query",
                    "defaultSort": {"field": "gap_minutes", "direction": "desc"},
                    "columns": [
                        {"field": "symbol", "label": "Symbol", "type": "text"},
                        {"field": "timeframe", "label": "TF", "type": "text"},
                        {"field": "previous_bar", "label": "Previous governed bar", "type": "text"},
                        {"field": "next_bar", "label": "Next governed bar", "type": "text"},
                        {"field": "gap", "label": "Gap", "type": "text"},
                        {"field": "gap_minutes", "label": "Gap (min)", "format": "number"},
                    ],
                },
            ],
            "sources": [source],
            "blocks": [
                {"id": "title", "type": "markdown", "body": "# Estate Gap Report"},
                {
                    "id": "technical_summary",
                    "type": "markdown",
                    "sourceId": "estate_gap_query",
                    "body": (
                        "## Technical summary\n\n"
                        f"The scan found **{stats['observed_gaps']} observed discontinuities** across "
                        f"**{stats['lanes_with_observed_gaps']} of {stats['total_lanes']} governed lanes**. "
                        f"It excludes **{stats['expected_fx_weekends_excluded']} normal FX weekend closures**. "
                        "Use the lane table to prioritise symbols; use the detailed table to inspect each missing interval."
                    ),
                },
                {"id": "metrics", "type": "metric-strip", "cardIds": ["affected_lanes", "observed_gaps", "scanned_lanes"]},
                {
                    "id": "definitions",
                    "type": "markdown",
                    "sourceId": "estate_gap_query",
                    "body": "## What counts as a gap\n\nAn observed gap is a break between consecutive governed bars longer than two expected intraday intervals, or longer than three D1 intervals. FX Friday-to-Sunday/Monday closures are excluded. `Validation missing` is the independent, calendar-aware count stored by the lane validator, so it may differ from the visual discontinuity count.",
                },
                {
                    "id": "lane_table_intro",
                    "type": "markdown",
                    "body": "## Prioritise lanes by the largest break\n\nThe chart ranks the 12 most consequential continuity breaks. The table that follows has one row per affected symbol/timeframe and is sorted by the same measure for exact lookup.",
                },
                {"id": "largest_gap_chart", "type": "chart", "chartId": "largest_gap_ranking", "layout": "full"},
                {"id": "lane_table", "type": "table", "tableId": "lane_gaps", "layout": "full"},
                {
                    "id": "detail_intro",
                    "type": "markdown",
                        "body": "## Inspect the largest breaks\n\nThis exact lookup table lists up to the three largest observed breaks in each affected lane. The first table retains the complete observed-gap count. Neither table infers or interpolates price data.",
                },
                {"id": "detail_table", "type": "table", "tableId": "gap_details", "layout": "full"},
                {
                    "id": "limitations",
                    "type": "markdown",
                    "body": "## Limits of this report\n\nThe report is a point-in-time snapshot of the current estate. It reports continuity, not price correctness. A lane can be continuous while still requiring provenance or price-quality review; conversely, expected market closures are intentionally not counted as missing history.",
                },
                {
                    "id": "next_steps",
                    "type": "markdown",
                    "body": "## Next steps\n\nPrioritise rows with material validator gaps or the largest observed intervals. Re-run this report after scheduler catch-up or a controlled historical import to confirm that the specific interval has closed.",
                },
            ],
        },
        "snapshot": {"version": 1, "generatedAt": generated_at, "status": "ready", "datasets": {"summary": summary, "gap_rank": gap_rank, "lane_gaps": lanes, "gap_details": details}},
        "sources": [source],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    lanes, details, stats = query_report(arguments.database)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(make_artifact(lanes, details, stats), indent=2) + "\n")
    print(json.dumps({"output": str(arguments.output), **stats}, sort_keys=True))


if __name__ == "__main__":
    main()
