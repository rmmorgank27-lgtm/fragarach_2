"""Read-only SPEC-009A operational historical-authority service."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .storage import open_read_only


AUTHORITY_CONTRACT = "fragarach_ii.operational_authority.v1"
AUTHORITY_VERSION = 1


class AuthorityServiceError(RuntimeError):
    """A factual request failure at the operational service boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def serve_historical_authority(
    database_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    start_time_utc: int | None = None,
    end_time_utc: int | None = None,
) -> dict[str, object]:
    """Return one consumer-independent authority response without mutation."""

    normalized_symbol = symbol.strip().upper()
    normalized_timeframe = timeframe.strip().upper()
    if not normalized_symbol or not normalized_timeframe:
        raise AuthorityServiceError("INVALID_REQUEST", "symbol and timeframe are required")
    if start_time_utc is not None and end_time_utc is not None and start_time_utc > end_time_utc:
        raise AuthorityServiceError("INVALID_DATE_RANGE", "start time must not follow end time")

    connection = open_read_only(database_path)
    try:
        registration = connection.execute(
            """
            SELECT asset, timeframe, aliases_json, provider_id, provider_contract,
                   provider_symbol, registration_status, evidence_confirmed_at_utc
            FROM instrument_registrations
            WHERE asset=? AND timeframe=?
            """,
            (normalized_symbol, normalized_timeframe),
        ).fetchone()
        if registration is None:
            registration = _registration_by_alias(connection, normalized_symbol, normalized_timeframe)
        if registration is None:
            raise AuthorityServiceError(
                "UNREGISTERED_LANE", f"{normalized_symbol}:{normalized_timeframe}"
            )
        canonical_symbol = str(registration[0])
        lane = connection.execute(
            "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",
            (canonical_symbol, normalized_timeframe),
        ).fetchone()
        if lane is None:
            raise AuthorityServiceError(
                "UNDECLARED_LANE", f"{canonical_symbol}:{normalized_timeframe}"
            )

        clauses = ["asset=?", "timeframe=?"]
        parameters: list[object] = [canonical_symbol, normalized_timeframe]
        if start_time_utc is not None:
            clauses.append("open_time_utc>=?")
            parameters.append(start_time_utc)
        if end_time_utc is not None:
            clauses.append("open_time_utc<=?")
            parameters.append(end_time_utc)
        bars = connection.execute(
            f"""
            SELECT open_time_utc, close_time_utc, open, high, low, close, volume
            FROM bars WHERE {' AND '.join(clauses)} ORDER BY open_time_utc
            """,
            parameters,
        ).fetchall()
        if not bars:
            raise AuthorityServiceError(
                "NO_AUTHORITY_IN_RANGE", f"{canonical_symbol}:{normalized_timeframe}"
            )

        lane_state = connection.execute(
            "SELECT validation_summary FROM lane_state WHERE asset=? AND timeframe=?",
            (canonical_symbol, normalized_timeframe),
        ).fetchone()
        validation = json.loads(lane_state[0]) if lane_state and lane_state[0] else None
        provenance_count = connection.execute(
            "SELECT count(*) FROM provenance WHERE symbol=? AND timeframe=?",
            (canonical_symbol, normalized_timeframe),
        ).fetchone()[0]
        return _response(
            canonical_symbol, normalized_timeframe, registration, bars, validation, provenance_count
        )
    finally:
        connection.close()


def _registration_by_alias(connection, symbol: str, timeframe: str):
    rows = connection.execute(
        """
        SELECT asset, timeframe, aliases_json, provider_id, provider_contract,
               provider_symbol, registration_status, evidence_confirmed_at_utc
        FROM instrument_registrations WHERE timeframe=? ORDER BY asset
        """,
        (timeframe,),
    ).fetchall()
    matches = []
    for row in rows:
        aliases = json.loads(row[2])
        if any(alias.get("normalized_alias") == symbol for alias in aliases):
            matches.append(row)
    if len(matches) > 1:
        raise AuthorityServiceError("AMBIGUOUS_SYMBOL", symbol)
    return matches[0] if matches else None


def _response(symbol, timeframe, registration, rows, validation, provenance_count):
    earliest = rows[0][0]
    latest = rows[-1][0]
    caodt = _iso_utc(latest)
    validation_state, validation_score = _validation_state(validation)
    expected = validation.get("expected_session_count", 0) if validation else 0
    present = validation.get("present_expected_session_count", 0) if validation else 0
    coverage_score = round(100 * present / expected) if expected else 0
    authority_score = 100 if registration[6] == "REGISTERED_WITH_EVIDENCE" else 75
    freshness_score = (
        100 if validation and validation.get("latest_expected_session_present") else 50
    )
    components = {
        "authority": {"score": authority_score, "basis": registration[6]},
        "freshness": {
            "score": freshness_score,
            "basis": "LATEST_EXPECTED_SESSION_PRESENT"
            if freshness_score == 100
            else "LATEST_EXPECTED_SESSION_NOT_CONFIRMED",
        },
        "validation": {"score": validation_score, "basis": validation_state},
        "coverage": {
            "score": coverage_score,
            "basis": f"{present}/{expected} expected sessions" if expected else "NOT_MEASURED",
        },
    }
    truth_score = round(sum(item["score"] for item in components.values()) / len(components))
    authority_state = "GREEN" if truth_score >= 80 else "AMBER" if truth_score >= 50 else "RED"
    missing = validation.get("missing_expected_session_count", 0) if validation else None
    current = 0 if validation and validation.get("latest_expected_session_present") else (1 if validation else None)
    historical = max(0, missing - (current or 0)) if missing is not None else None
    impact = _gap_impact(validation, missing)
    provider_confidence = 100 if registration[6] == "REGISTERED_WITH_EVIDENCE" else 50
    return {
        "contract": AUTHORITY_CONTRACT,
        "historical_bars": [
            {
                "open_time_utc": row[0],
                "close_time_utc": row[1],
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "volume": row[6],
            }
            for row in rows
        ],
        "caodt": caodt,
        "authority_state": authority_state,
        "validation_state": validation_state,
        "truth_score": {"score": truth_score, "maximum": 100, "components": components},
        "gap_summary": {
            "current_gaps": current,
            "recent_gaps": None,
            "historical_gaps": historical,
            "total_known_gaps": missing,
            "operational_impact": impact,
            "limitations": [] if validation else ["NO_PERSISTED_VALIDATION_SUMMARY"],
        },
        "provider_summary": {
            "provider": registration[3],
            "provider_contract": registration[4],
            "provider_symbol": registration[5],
            "provider_freshness": caodt,
            "provider_confidence": provider_confidence,
            "provider_entitlement": "NOT_RECORDED",
        },
        "operational_metadata": {
            "row_count": len(rows),
            "earliest_bar": _iso_utc(earliest),
            "latest_bar": caodt,
            "timeframe": timeframe,
            "symbol": symbol,
            "authority_version": AUTHORITY_VERSION,
            "provenance_reference_count": provenance_count,
        },
    }


def _validation_state(validation):
    if validation is None:
        return "LIMITED", 25
    if validation.get("material_gap_count", 0) or validation.get("outside_expected_session_count", 0):
        return "WARNING", 60
    if validation.get("missing_expected_session_count", 0):
        return "WARNING", 80
    return "PASS", 100


def _gap_impact(validation, missing):
    if validation is None:
        return "HIGH"
    if not missing and not validation.get("outside_expected_session_count", 0):
        return "NONE"
    if validation.get("material_gap_count", 0):
        return "HIGH" if not validation.get("latest_expected_session_present") else "MEDIUM"
    return "LOW"


def _iso_utc(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, UTC).isoformat()
