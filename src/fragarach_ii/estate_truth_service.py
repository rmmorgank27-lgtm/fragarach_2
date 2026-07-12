"""SPEC-009C read-only operational truth for the complete authority estate."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from .storage import open_read_only
from .truth_engine import truth_state_for_lane


ESTATE_TRUTH_CONTRACT = "fragarach_ii.estate_truth_state.v1"
AUTHORITY_VERSION = 1


def estate_truth_state(database_path: str | Path) -> dict[str, object]:
    """Build one deterministic estate snapshot from persisted authority."""

    connection = open_read_only(database_path)
    try:
        rows = connection.execute(
            """
            SELECT r.asset,l.timeframe,r.display_name,r.aliases_json,r.asset_class,
                   r.exchange_name,r.provider_id,r.provider_contract,r.provider_symbol,
                   s.validation_summary,
                   (SELECT max(p.recorded_at) FROM provenance p
                    WHERE p.symbol=l.asset AND p.timeframe=l.timeframe) AS provider_freshness
            FROM evidence_lanes l
            JOIN instrument_registrations r
              ON r.asset=l.asset AND r.timeframe=l.registration_timeframe
            LEFT JOIN lane_state s ON s.asset=l.asset AND s.timeframe=l.timeframe
            WHERE EXISTS (SELECT 1 FROM bars b WHERE b.asset=l.asset AND b.timeframe=l.timeframe)
              AND NOT EXISTS (SELECT 1 FROM authority_events e WHERE e.event_kind='LANE_SUPERSEDED' AND json_extract(e.canonical_payload,'$.body.asset')=l.asset AND json_extract(e.canonical_payload,'$.body.timeframe')=l.timeframe)
            ORDER BY r.asset,l.timeframe
            """
        ).fetchall()
        generated_at = connection.execute(
            """
            SELECT max(value) FROM (
              SELECT max(updated_at_utc) AS value FROM lane_state
              UNION ALL SELECT max(recorded_at_utc) FROM authority_events
              UNION ALL SELECT max(registered_at_utc) FROM instrument_registrations
            )
            """
        ).fetchone()[0]
    finally:
        connection.close()

    lanes = []
    for row in rows:
        truth = truth_state_for_lane(database_path, symbol=row[0], timeframe=row[1])
        validation = json.loads(row[9]) if row[9] else None
        gap_counts = _gap_counts(validation)
        lanes.append(
            {
                "symbol": row[0],
                "timeframe": row[1],
                "truth_state": truth,
                "search_metadata": {
                    "canonical_symbol": row[0],
                    "display_name": row[2],
                    "aliases": json.loads(row[3]),
                    "market": "NOT_RECORDED",
                    "asset_class": row[4],
                    "exchange": row[5],
                    "provider_family": row[6],
                },
                "provider_summary": {
                    "provider": row[6],
                    "provider_contract": row[7],
                    "provider_symbol": row[8],
                    "provider_freshness": row[10] or "NOT_MEASURED",
                    "provider_confidence": truth["provider_summary"]["confidence"],
                    "entitlement": "NOT_MEASURED",
                    "unknown_values": [
                        name
                        for name, value in (
                            ("provider_freshness", row[10]),
                            ("provider_confidence", truth["provider_score"]),
                            ("entitlement", None),
                        )
                        if value is None
                    ],
                },
                "gap_summary": {
                    **gap_counts,
                    "total_gap_count": validation.get("missing_expected_session_count") if validation else None,
                    "gap_classification": truth["gap_classification"],
                    "operational_impact": truth["gap_impact"],
                },
            }
        )
    return {
        "contract": ESTATE_TRUTH_CONTRACT,
        "estate_summary": _estate_summary(lanes, generated_at),
        "truth_matrix": lanes,
    }


class EstateTruthCache:
    """Explicit in-memory cache replaced only by load or manual refresh."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._value: dict[str, object] | None = None

    def load(self) -> dict[str, object]:
        if self._value is None:
            self._value = estate_truth_state(self.database_path)
        return copy.deepcopy(self._value)

    def refresh(self) -> dict[str, object]:
        self._value = estate_truth_state(self.database_path)
        return copy.deepcopy(self._value)


def _gap_counts(validation):
    if validation is None:
        return {"current_gap_count": None, "recent_gap_count": None, "historical_gap_count": None}
    missing = validation.get("missing_expected_session_count", 0)
    current = 0 if validation.get("latest_expected_session_present") else min(1, missing)
    material = validation.get("material_gap_count", 0)
    recent = min(max(0, missing - current), material)
    historical = max(0, missing - current - recent)
    return {"current_gap_count": current, "recent_gap_count": recent, "historical_gap_count": historical}


def _estate_summary(lanes, generated_at):
    scores = [lane["truth_state"]["truth_score"] for lane in lanes]
    overall = round(sum(scores) / len(scores)) if scores else None
    counts = {state: sum(lane["truth_state"]["authority_state"] == state for lane in lanes) for state in ("GREEN", "AMBER", "RED")}
    caodts = [lane["truth_state"]["caodt"] for lane in lanes]
    return {
        "overall_truth_score": overall,
        "overall_authority_state": "GREEN" if overall is not None and overall >= 80 else "AMBER" if overall is not None and overall >= 50 else "RED" if overall is not None else "NOT_MEASURED",
        "overall_caodt": min(caodts) if caodts else None,
        "total_symbols": len({lane["symbol"] for lane in lanes}),
        "total_lanes": len(lanes),
        "green_count": counts["GREEN"],
        "amber_count": counts["AMBER"],
        "red_count": counts["RED"],
        "authority_version": AUTHORITY_VERSION,
        "generated_at": generated_at,
        "aggregation": {
            "truth_score": "EQUAL_WEIGHT_MEAN_OF_LANE_TRUTH_SCORES",
            "authority_state": "STANDARD_GREEN_AMBER_RED_THRESHOLDS",
            "caodt": "EARLIEST_LANE_CAODT",
            "generated_at": "LATEST_PERSISTED_AUTHORITY_TIMESTAMP",
        },
    }
