"""Read-only SPEC-009B operational Truth Engine."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .freshness import assess_lane_freshness, authority_revision_for_lane, normalized_utc
from .storage import open_read_only
from .retirement import is_permanently_removed,is_retired


TRUTH_STATE_CONTRACT = "fragarach_ii.truth_state.v1"
TRUTH_ENGINE_VERSION = 2

# Operational Truth weights. Freshness dominates the current edge, while
# historical depth is intentionally more valuable than perfect continuity over
# a shallow record. Each lane is scored against its own timeframe horizon.
TRUTH_COMPONENT_WEIGHTS = {
    "authority": 15,
    "integrity": 20,
    "freshness": 30,
    "historical_depth": 25,
    "continuity": 10,
}
_TIMEFRAME_SECONDS = {"D1": 86_400, "H1": 3_600, "M30": 1_800, "M5": 300}
_DEPTH_HORIZON_DAYS = {"D1": 3_652.5, "H1": 1_095.75, "M30": 730.5, "M5": 365.25}


class TruthEngineError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def truth_state_for_lane(
    database_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    as_of: datetime | None = None,
    authority_generated: str | None = None,
) -> dict[str, object]:
    """Calculate TruthState from persisted authority for one canonical lane."""

    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()
    if is_permanently_removed(database_path,symbol,timeframe):raise TruthEngineError("REMOVED_LANE",f"{symbol}:{timeframe}")
    if is_retired(database_path,symbol,timeframe):raise TruthEngineError("RETIRED_LANE",f"{symbol}:{timeframe}")
    connection = open_read_only(database_path)
    try:
        registration = connection.execute(
            """
            SELECT provider_id,provider_contract,provider_symbol,registration_status
            FROM instrument_registrations WHERE asset=? AND timeframe='D1'
            """,
            (symbol,),
        ).fetchone()
        if registration is None:
            raise TruthEngineError("UNREGISTERED_LANE", f"{symbol}:{timeframe}")
        if connection.execute(
            "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?", (symbol, timeframe)
        ).fetchone() is None:
            raise TruthEngineError("UNDECLARED_LANE", f"{symbol}:{timeframe}")
        range_row = connection.execute(
            "SELECT count(*),min(open_time_utc),max(open_time_utc),max(close_time_utc) FROM bars WHERE asset=? AND timeframe=?",
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
            SELECT authority_event_id,canonical_payload FROM authority_events
            WHERE entity_kind='EVIDENCE_LANE'
              AND (json_extract(canonical_payload,'$.body.legacy_key.asset')=? OR json_extract(canonical_payload,'$.body.asset')=?)
              AND (json_extract(canonical_payload,'$.body.legacy_key.timeframe')=? OR json_extract(canonical_payload,'$.body.timeframe')=?)
            ORDER BY effective_from_utc DESC,recorded_at_utc DESC,authority_event_id DESC LIMIT 1
            """,
            (symbol,symbol,timeframe,timeframe),
        ).fetchone()
        freshness = assess_lane_freshness(
            connection,
            symbol=symbol,
            timeframe=timeframe,
            as_of=normalized_utc(as_of),
        )
        authority_revision = authority_revision_for_lane(
            connection, symbol=symbol, timeframe=timeframe
        )
        return _calculate(
            symbol,
            timeframe,
            registration,
            range_row,
            validation,
            ledger,
            freshness,
            authority_revision,
            authority_generated,
        )
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


def truth_state_from_persisted_facts(
    *,
    symbol: str,
    timeframe: str,
    registration: tuple[object, object, object, object],
    range_row: tuple[int, int, int, int],
    validation: dict[str, object] | None,
    ledger_bound: bool,
    freshness: dict[str, object],
    authority_revision: str,
    authority_generated: str | None = None,
) -> dict[str, object]:
    """Build TruthState from an already-indexed Estate projection row.

    Estate reads use this to avoid reopening SQLite and repeating the lane
    freshness/revision work that has already been performed for the same
    authoritative snapshot.  The single-lane public API remains unchanged.
    """
    return _calculate(
        symbol, timeframe, registration, range_row, validation,
        ("ESTATE_PROJECTION",) if ledger_bound else None, freshness,
        authority_revision, authority_generated,
    )


def _calculate(
    symbol,
    timeframe,
    registration,
    range_row,
    validation,
    ledger,
    freshness=None,
    authority_revision="UNPUBLISHED_TEST_AUTHORITY",
    authority_generated=None,
):
    row_count, earliest, latest, latest_close = range_row
    if freshness is None:
        intraday_validation = bool(
            validation
            and validation.get("format")
            == "fragarach_ii.lane_validation_summary.v2"
        )
        presence_key = (
            "latest_expected_closed_interval_present"
            if intraday_validation
            else "latest_expected_session_present"
        )
        expected_key = (
            "latest_expected_closed_interval_end_utc"
            if intraday_validation
            else "latest_expected_session"
        )
        freshness = {
            "state": (
                "Current"
                if validation and validation.get(presence_key)
                else "Behind"
                if validation
                else "Unavailable"
            ),
            "latest_canonical_observation": _iso_utc(
                latest if timeframe == "D1" else latest_close
            ),
            "expected_latest": validation.get(expected_key) if validation else None,
            "reason_code": (
                "LATEST_CANONICAL_OBSERVATION_AT_OR_AHEAD_OF_EXPECTED_LATEST"
                if validation and validation.get(presence_key)
                else "LATEST_CANONICAL_OBSERVATION_BEHIND_EXPECTED_LATEST"
                if validation
                else "NOT_MEASURED"
            ),
        }
    caodt = freshness["latest_canonical_observation"]
    authority_score = 100 if registration[3] == "REGISTERED_WITH_EVIDENCE" and ledger else 90 if registration[3] == "REGISTERED_WITH_EVIDENCE" else 75
    authority_basis = f"{registration[3]};" + ("LEDGER_BOUND" if ledger else "LEDGER_BINDING_NOT_PRESENT")
    validation_stale = _validation_snapshot_stale(
        validation, timeframe=timeframe, latest=latest, latest_close=latest_close,
    )
    validation_state, integrity_score = _integrity(validation)
    intraday=bool(validation and validation.get("format")=="fragarach_ii.lane_validation_summary.v2")
    expected = validation.get("expected_interval_count" if intraday else "expected_session_count") if validation else None
    present = validation.get("present_expected_interval_count" if intraday else "present_expected_session_count") if validation else None
    missing = validation.get("missing_expected_interval_count" if intraday else "missing_expected_session_count") if validation else None
    continuity_score = _continuity(validation, expected, present, missing)
    if validation_stale:
        # A persisted validation summary is a point-in-time audit.  Once the
        # canonical edge has moved beyond its checked boundary it cannot be
        # used to claim current gaps or reduce live operational health.  Keep
        # its factual counts visible, but wait for a fresh audit before using
        # integrity/continuity as score inputs again.
        validation_state, integrity_score, continuity_score = "STALE", None, None
    # Retained as a compatibility alias for accepted v1 consumers. Coverage is
    # no longer a separately weighted Truth component.
    coverage_score = round(100 * present / expected) if expected else None
    freshness_score = (
        100
        if freshness["state"] == "Current"
        else 0
        if freshness["state"] == "Behind"
        else None
    )
    depth_score, depth_basis = _historical_depth(timeframe, earliest, latest)
    gap_classification, gap_impact = _gaps(
        validation, freshness, validation_stale=validation_stale,
    )
    provider_summary = {
        "provider": registration[0],
        "provider_contract": registration[1] if timeframe=="D1" else f"TWELVE_DATA_TIME_SERIES_{timeframe}_V1",
        "provider_symbol": registration[2],
        "confidence": "NOT_MEASURED",
        "score": None,
        "basis": "NO_PERSISTED_PROVIDER_CONFIDENCE_FACT",
    }
    components: dict[str, dict[str, object]] = {
        "authority": {"score": authority_score, "basis": authority_basis},
        "freshness": {"score": freshness_score, "basis": freshness["reason_code"]},
        "integrity": {
            "score": integrity_score,
            "basis": "STALE_VALIDATION_SNAPSHOT" if validation_stale else validation_state,
        },
        "historical_depth": {"score": depth_score, "basis": depth_basis},
        "continuity": {
            "score": continuity_score,
            "basis": (
                "STALE_VALIDATION_SNAPSHOT"
                if validation_stale
                else f"{missing} missing of {expected} expected sessions"
                if expected else "NOT_MEASURED"
            ),
        },
        "provider": {"score": None, "basis": provider_summary["basis"]},
    }
    measured = {
        name: components[name]["score"]
        for name in TRUTH_COMPONENT_WEIGHTS
        if components[name]["score"] is not None
    }
    measured_weight = sum(TRUTH_COMPONENT_WEIGHTS[name] for name in measured)
    truth_score = round(
        sum(measured[name] * TRUTH_COMPONENT_WEIGHTS[name] for name in measured)
        / measured_weight
    )
    if truth_score == 100 and any(score < 100 for score in measured.values()):
        truth_score = 99
    state = "GREEN" if truth_score >= 80 else "AMBER" if truth_score >= 50 else "RED"
    if freshness.get("severity") == "CRITICAL":
        state = "RED"
    elif freshness.get("state") == "Behind" and state == "GREEN":
        state = "AMBER"
    limitations = [name.upper() + "_NOT_MEASURED" for name, item in components.items() if item["score"] is None]
    if validation_stale:
        limitations = [item for item in limitations if item not in {"INTEGRITY_NOT_MEASURED", "CONTINUITY_NOT_MEASURED"}]
        limitations.append("VALIDATION_SNAPSHOT_STALE")
    result = {
        "contract": TRUTH_STATE_CONTRACT,
        "engine_version": TRUTH_ENGINE_VERSION,
        "symbol": symbol,
        "timeframe": timeframe,
        "truth_score": truth_score,
        "authority_score": authority_score,
        "integrity_score": integrity_score,
        "freshness_score": freshness_score,
        "historical_depth_score": depth_score,
        "coverage_score": coverage_score,
        "continuity_score": continuity_score,
        "validation_score": integrity_score,
        "provider_score": None,
        "authority_state": state,
        "evidence_integrity": {
            "state": "Healthy" if validation_state == "PASS" else "Attention" if validation_state == "WARNING" else "Not current" if validation_state == "STALE" else "Limited",
            "score": integrity_score,
        },
        "freshness_dimension": {
            "state": freshness.get("severity"),
            "label": freshness.get("operational_state", freshness.get("state")),
            "lag": freshness.get("lag"),
        },
        "overall_operational_state": (
            "Critical" if state == "RED" else "Attention" if state == "AMBER" else "Healthy"
        ),
        "operational_state_label": f"{'Valid' if validation_state == 'PASS' else 'Validation snapshot stale' if validation_state == 'STALE' else 'Incomplete'} · {freshness.get('operational_state', freshness.get('state'))}",
        "validation_state": validation_state,
        "caodt": caodt,
        "latest_canonical_observation": caodt,
        "authority_revision": authority_revision,
        "freshness": freshness,
        "validation": {"state": validation_state, "summary": validation, "snapshot_stale": validation_stale},
        "gap_classification": gap_classification,
        "gap_impact": gap_impact,
        "coverage": {
            "earliest_bar": _iso_utc(earliest),
            "latest_bar": caodt,
            "row_count": row_count,
            "expected_range": {"start": _iso_utc(earliest), "end": freshness["expected_latest"]},
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
            "method": "WEIGHTED_AUTHORITY_INTEGRITY_FRESHNESS_HISTORICAL_DEPTH_CONTINUITY_V2",
            "weights": TRUTH_COMPONENT_WEIGHTS,
            "components": components,
            "limitations": limitations,
        },
    }
    if authority_generated is not None:
        result["authority_generated"] = authority_generated
    return result


def _integrity(validation: dict[str, Any] | None) -> tuple[str, int | None]:
    if validation is None:
        return "LIMITED", None
    outside=validation.get("outside_expected_interval_count",validation.get("outside_expected_session_count",0))
    if validation.get("material_gap_count", 0) or outside:
        return "WARNING", 60
    if validation.get("missing_expected_interval_count",validation.get("missing_expected_session_count",0)):
        return "WARNING", 100
    return "PASS", 100


def _continuity(
    validation: dict[str, Any] | None,
    expected: int | None,
    present: int | None,
    missing: int | None,
) -> int | None:
    if validation is None or not expected or present is None or missing is None:
        return None
    ratio = max(0.0, min(1.0, present / expected))
    if missing and not validation.get("material_gap_count", 0):
        # Old, explicitly non-material gaps remain visible but occupy only the
        # upper continuity band; they cannot erase years of usable authority.
        return min(99, round(90 + 10 * ratio))
    return round(100 * ratio)


def _historical_depth(timeframe: str, earliest: int, latest: int) -> tuple[int, str]:
    interval_seconds = _TIMEFRAME_SECONDS[timeframe]
    horizon_days = _DEPTH_HORIZON_DAYS[timeframe]
    span_seconds = max(interval_seconds, latest - earliest + interval_seconds)
    span_days = span_seconds / 86_400
    progress = min(1.0, span_days / horizon_days)
    # A validated but shallow lane receives half-credit for depth. The remaining
    # half is earned strictly through elapsed historical span.
    score = round(50 + 50 * progress)
    basis = f"{span_days:.2f} elapsed days / {horizon_days:.2f} day {timeframe} horizon"
    return score, basis


def _validation_snapshot_stale(
    validation: dict[str, Any] | None,
    *, timeframe: str, latest: int, latest_close: int,
) -> bool:
    """Whether a persisted validation snapshot predates canonical evidence.

    Validation can be expensive and is intentionally decoupled from every
    scheduler poll.  Its historical findings remain available, but it must
    not be projected as a live current-edge failure after a provider has
    advanced the canonical lane.
    """

    if not validation:
        return False
    try:
        if timeframe == "D1":
            boundary = validation.get("through_date") or validation.get("latest_expected_session")
            return bool(boundary) and date.fromisoformat(str(boundary)) < datetime.fromtimestamp(latest, UTC).date()
        boundary = validation.get("latest_expected_closed_interval_end_utc")
        return bool(boundary) and int(datetime.fromisoformat(str(boundary)).timestamp()) < int(latest_close)
    except (TypeError, ValueError, OverflowError):
        # A legacy/malformed summary remains subject to its normal validation
        # path.  Only an exact, comparable boundary is marked stale.
        return False


def _gaps(
    validation: dict[str, Any] | None, freshness: dict[str, object], *, validation_stale: bool = False,
) -> tuple[str, str]:
    if freshness["state"] == "Behind":
        return "CURRENT", "HIGH"
    if validation_stale:
        return "HISTORICAL_SNAPSHOT", "NONE"
    if validation is None:
        return "NOT_MEASURED", "HIGH"
    missing = validation.get("missing_expected_interval_count",validation.get("missing_expected_session_count", 0))
    outside = validation.get("outside_expected_interval_count",validation.get("outside_expected_session_count", 0))
    if not missing and not outside:
        return "NONE", "NONE"
    if not validation.get("latest_expected_closed_interval_present",validation.get("latest_expected_session_present")):
        return "CURRENT", "HIGH"
    if validation.get("material_gap_count", 0):
        return "RECENT", "MEDIUM"
    return "HISTORICAL", "LOW"


def _iso_utc(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, UTC).isoformat()
