"""Deterministic, read-only SPEC-009B operational Truth Engine."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .storage import open_read_only
from .retirement import is_retired


TRUTH_STATE_CONTRACT = "fragarach_ii.truth_state.v1"
TRUTH_ENGINE_VERSION = 1


class TruthEngineError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def truth_state_for_lane(
    database_path: str | Path, *, symbol: str, timeframe: str
) -> dict[str, object]:
    """Calculate TruthState from persisted authority for one canonical lane."""

    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()
    if is_retired(database_path,symbol,timeframe):raise TruthEngineError("RETIRED_LANE",f"{symbol}:{timeframe}")
    connection = open_read_only(database_path)
    try:
        registration = connection.execute(
            """
            SELECT provider_id,provider_contract,provider_symbol,registration_status
            FROM instrument_registrations WHERE asset=? AND timeframe=?
            """,
            (symbol, timeframe),
        ).fetchone()
        if registration is None:
            raise TruthEngineError("UNREGISTERED_LANE", f"{symbol}:{timeframe}")
        if connection.execute(
            "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?", (symbol, timeframe)
        ).fetchone() is None:
            raise TruthEngineError("UNDECLARED_LANE", f"{symbol}:{timeframe}")
        range_row = connection.execute(
            "SELECT count(*),min(open_time_utc),max(open_time_utc) FROM bars WHERE asset=? AND timeframe=?",
            (symbol, timeframe),
        ).fetchone()
        if not range_row or range_row[0] == 0:
            raise TruthEngineError("NO_AUTHORITY", f"{symbol}:{timeframe}")
        state_row = connection.execute(
            "SELECT validation_summary FROM lane_state WHERE asset=? AND timeframe=?",
            (symbol, timeframe),
        ).fetchone()
        validation = json.loads(state_row[0]) if state_row and state_row[0] else None
        ledger = connection.execute(
            """
            SELECT canonical_payload FROM authority_events
            WHERE entity_kind='EVIDENCE_LANE'
              AND json_extract(canonical_payload,'$.body.legacy_key.asset')=?
              AND json_extract(canonical_payload,'$.body.legacy_key.timeframe')=?
            ORDER BY effective_from_utc DESC,recorded_at_utc DESC,authority_event_id DESC LIMIT 1
            """,
            (symbol, timeframe),
        ).fetchone()
        return _calculate(symbol, timeframe, registration, range_row, validation, ledger)
    finally:
        connection.close()


def truth_states(database_path: str | Path) -> list[dict[str, object]]:
    """Produce one TruthState for every declared lane that contains authority."""

    connection = open_read_only(database_path)
    try:
        lanes = connection.execute(
            """
            SELECT l.asset,l.timeframe FROM evidence_lanes l
            WHERE EXISTS (SELECT 1 FROM bars b WHERE b.asset=l.asset AND b.timeframe=l.timeframe)
              AND NOT EXISTS (SELECT 1 FROM authority_events e WHERE e.event_kind='LANE_SUPERSEDED' AND json_extract(e.canonical_payload,'$.body.asset')=l.asset AND json_extract(e.canonical_payload,'$.body.timeframe')=l.timeframe)
            ORDER BY l.asset,l.timeframe
            """
        ).fetchall()
    finally:
        connection.close()
    return [truth_state_for_lane(database_path, symbol=row[0], timeframe=row[1]) for row in lanes]


def _calculate(symbol, timeframe, registration, range_row, validation, ledger):
    row_count, earliest, latest = range_row
    caodt = _iso_utc(latest)
    authority_score = 100 if registration[3] == "REGISTERED_WITH_EVIDENCE" and ledger else 90 if registration[3] == "REGISTERED_WITH_EVIDENCE" else 75
    authority_basis = f"{registration[3]};" + ("LEDGER_BOUND" if ledger else "LEDGER_BINDING_NOT_PRESENT")
    validation_state, validation_score = _validation(validation)
    expected = validation.get("expected_session_count") if validation else None
    present = validation.get("present_expected_session_count") if validation else None
    missing = validation.get("missing_expected_session_count") if validation else None
    coverage_score = round(100 * present / expected) if expected else None
    continuity_score = round(100 * (expected - missing) / expected) if expected is not None and expected > 0 else None
    freshness_score = 100 if validation and validation.get("latest_expected_session_present") else (50 if validation else None)
    gap_classification, gap_impact = _gaps(validation)
    provider_summary = {
        "provider": registration[0],
        "provider_contract": registration[1],
        "provider_symbol": registration[2],
        "confidence": "NOT_MEASURED",
        "score": None,
        "basis": "NO_PERSISTED_PROVIDER_CONFIDENCE_FACT",
    }
    components: dict[str, dict[str, object]] = {
        "authority": {"score": authority_score, "basis": authority_basis},
        "freshness": {"score": freshness_score, "basis": "LATEST_EXPECTED_SESSION_PRESENT" if freshness_score == 100 else "LATEST_EXPECTED_SESSION_NOT_CONFIRMED" if validation else "NOT_MEASURED"},
        "coverage": {"score": coverage_score, "basis": f"{present}/{expected} expected sessions" if expected else "NOT_MEASURED"},
        "continuity": {"score": continuity_score, "basis": f"{missing} missing of {expected} expected sessions" if expected else "NOT_MEASURED"},
        "validation": {"score": validation_score, "basis": validation_state},
        "provider": {"score": None, "basis": provider_summary["basis"]},
    }
    measured = [item["score"] for item in components.values() if item["score"] is not None]
    truth_score = round(sum(measured) / len(measured))
    state = "GREEN" if truth_score >= 80 else "AMBER" if truth_score >= 50 else "RED"
    limitations = [name.upper() + "_NOT_MEASURED" for name, item in components.items() if item["score"] is None]
    return {
        "contract": TRUTH_STATE_CONTRACT,
        "engine_version": TRUTH_ENGINE_VERSION,
        "symbol": symbol,
        "timeframe": timeframe,
        "truth_score": truth_score,
        "authority_score": authority_score,
        "freshness_score": freshness_score,
        "coverage_score": coverage_score,
        "continuity_score": continuity_score,
        "validation_score": validation_score,
        "provider_score": None,
        "authority_state": state,
        "validation_state": validation_state,
        "caodt": caodt,
        "gap_classification": gap_classification,
        "gap_impact": gap_impact,
        "coverage": {
            "earliest_bar": _iso_utc(earliest),
            "latest_bar": caodt,
            "row_count": row_count,
            "expected_range": {"start": _iso_utc(earliest), "end": validation.get("latest_expected_session") if validation else None},
            "available_range": {"start": _iso_utc(earliest), "end": caodt},
            "expected_session_count": expected,
            "available_expected_session_count": present,
        },
        "gap_summary": {
            "classification": gap_classification,
            "operational_impact": gap_impact,
            "total_known_gaps": missing,
        },
        "provider_summary": provider_summary,
        "epoch": "UNKNOWN",
        "explanation": {
            "method": "EQUAL_WEIGHT_MEAN_OF_MEASURED_COMPONENTS",
            "components": components,
            "limitations": limitations,
        },
    }


def _validation(validation: dict[str, Any] | None) -> tuple[str, int | None]:
    if validation is None:
        return "LIMITED", None
    if validation.get("material_gap_count", 0) or validation.get("outside_expected_session_count", 0):
        return "WARNING", 60
    if validation.get("missing_expected_session_count", 0):
        return "WARNING", 80
    return "PASS", 100


def _gaps(validation: dict[str, Any] | None) -> tuple[str, str]:
    if validation is None:
        return "NOT_MEASURED", "HIGH"
    missing = validation.get("missing_expected_session_count", 0)
    outside = validation.get("outside_expected_session_count", 0)
    if not missing and not outside:
        return "NONE", "NONE"
    if not validation.get("latest_expected_session_present"):
        return "CURRENT", "HIGH"
    if validation.get("material_gap_count", 0):
        return "RECENT", "MEDIUM"
    return "HISTORICAL", "LOW"


def _iso_utc(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, UTC).isoformat()
