"""Read-only SPEC-009A operational historical-authority service."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Callable

from .freshness import normalized_utc
from .storage import open_read_only
from .truth_engine import TruthEngineError, truth_state_for_lane


AUTHORITY_CONTRACT = "fragarach_ii.operational_authority.v1"
AUTHORITY_VERSION = 2


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
    clock: Callable[[], datetime] | None = None,
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
            WHERE asset=? AND timeframe='D1'
            """,
            (normalized_symbol,),
        ).fetchone()
        if registration is None:
            registration = _registration_by_alias(connection, normalized_symbol, "D1")
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
        provenance = connection.execute(
            "SELECT count(*),max(recorded_at) FROM provenance WHERE symbol=? AND timeframe=?",
            (canonical_symbol, normalized_timeframe),
        ).fetchone()
        authority_generated = normalized_utc(clock() if clock else None)
        try:
            truth_state = truth_state_for_lane(
                database_path,
                symbol=canonical_symbol,
                timeframe=normalized_timeframe,
                as_of=authority_generated,
                authority_generated=authority_generated.isoformat(),
            )
        except TruthEngineError as error:
            raise AuthorityServiceError(error.code, str(error)) from error
        return _response(
            canonical_symbol,
            normalized_timeframe,
            registration,
            bars,
            validation,
            provenance[0],
            provenance[1],
            truth_state,
            authority_generated.isoformat(),
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


def _response(
    symbol,
    timeframe,
    registration,
    rows,
    validation,
    provenance_count,
    provider_observed_at,
    truth_state,
    authority_generated,
):
    earliest = rows[0][0]
    latest_canonical_observation = truth_state["latest_canonical_observation"]
    missing = validation.get("missing_expected_session_count", 0) if validation else None
    current = (
        0
        if truth_state["freshness"]["state"] == "Current"
        else 1
        if truth_state["freshness"]["state"] == "Behind"
        else None
    )
    historical = max(0, missing - (current or 0)) if missing is not None else None
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
        "caodt": latest_canonical_observation,
        "latest_canonical_observation": latest_canonical_observation,
        "authority_generated": authority_generated,
        "authority_revision": truth_state["authority_revision"],
        "freshness": truth_state["freshness"],
        "validation": {"state": truth_state["validation_state"], "summary": validation},
        "authority_state": truth_state["authority_state"],
        "validation_state": truth_state["validation_state"],
        "truth_score": {"score": truth_state["truth_score"], "maximum": 100, "components": {name: truth_state["explanation"]["components"][name] for name in ("authority", "integrity", "freshness", "historical_depth", "continuity")}},
        "truth_state": truth_state,
        "gap_summary": {
            "current_gaps": current,
            "recent_gaps": None,
            "historical_gaps": historical,
            "total_known_gaps": missing,
            "operational_impact": truth_state["gap_impact"],
            "limitations": [] if validation else ["NO_PERSISTED_VALIDATION_SUMMARY"],
        },
        "provider_summary": {
            "provider": registration[3],
            "provider_contract": registration[4],
            "provider_symbol": registration[5],
            "provider_freshness": provider_observed_at or "NOT_RECORDED",
            "provider_confidence": truth_state["provider_score"],
            "provider_entitlement": "NOT_RECORDED",
        },
        "operational_metadata": {
            "row_count": len(rows),
            "earliest_bar": _iso_utc(earliest),
            "latest_bar": latest_canonical_observation,
            "timeframe": timeframe,
            "symbol": symbol,
            "authority_version": AUTHORITY_VERSION,
            "provenance_reference_count": provenance_count,
        },
    }
def _iso_utc(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, UTC).isoformat()
