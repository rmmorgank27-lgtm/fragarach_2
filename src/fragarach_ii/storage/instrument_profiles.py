"""Evidence-backed instrument profiles and derived governed-history facts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .database import open_read_only, registered_writer, transaction
from .migrations import apply_migrations


ORIGIN_EVENT_TYPES = frozenset({
    "IPO", "DIRECT_LISTING", "FIRST_PUBLIC_TRADING", "FUND_INCEPTION",
    "INDEX_LAUNCH", "GENESIS_BLOCK", "FIRST_BLOCK", "MAINNET_LAUNCH",
    "TOKEN_GENERATION", "CONTRACT_LAUNCH",
})
EVENT_TYPES = ORIGIN_EVENT_TYPES | frozenset({
    "REDENOMINATION", "STOCK_SPLIT", "CHAIN_MIGRATION", "RELISTING", "OTHER",
})
VERIFICATION_STATUSES = frozenset({
    "VERIFIED_PRIMARY_SOURCE", "VERIFIED_SECONDARY_SOURCE", "NEEDS_REVIEW",
})


class InstrumentProfileError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True, slots=True)
class InstrumentProfileEventCandidate:
    asset: str
    event_type: str
    occurred_at_utc: str
    date_precision: str
    title: str
    source_url: str
    source_name: str
    source_retrieved_at_utc: str
    evidence_sha256: str
    verification_status: str
    is_primary_origin: bool = False
    block_height: int | None = None
    notes: str | None = None
    supersedes_event_id: str | None = None


def required_origin_event(asset_class: str, instrument_type: str) -> str | None:
    asset_class = asset_class.upper()
    instrument_type = instrument_type.upper()
    if instrument_type == "COMMON_STOCK":
        return "IPO_OR_FIRST_PUBLIC_TRADING"
    if asset_class == "CRYPTO":
        return "FIRST_BLOCK_OR_NETWORK_LAUNCH"
    if instrument_type == "ETF":
        return "FUND_INCEPTION"
    if instrument_type == "INDEX":
        return "INDEX_LAUNCH"
    return None


def record_instrument_profile_event(
    database_path: str | Path,
    candidate: InstrumentProfileEventCandidate,
    *,
    recorded_at_utc: str,
) -> dict[str, Any]:
    values = _canonical_values(candidate, recorded_at_utc=recorded_at_utc)
    event_id = hashlib.sha256(
        json.dumps(
            asdict(candidate), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    with registered_writer(database_path) as connection:
        apply_migrations(connection)
        with transaction(connection):
            registration = connection.execute(
                "SELECT 1 FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
                (candidate.asset,),
            ).fetchone()
            if registration is None:
                raise InstrumentProfileError("UNREGISTERED_SYMBOL", candidate.asset)
            if candidate.supersedes_event_id:
                prior = connection.execute(
                    "SELECT asset FROM instrument_profile_events WHERE profile_event_id=?",
                    (candidate.supersedes_event_id,),
                ).fetchone()
                if prior is None or prior[0] != candidate.asset:
                    raise InstrumentProfileError(
                        "INVALID_SUPERSEDED_PROFILE_EVENT", str(candidate.supersedes_event_id)
                    )
            if candidate.is_primary_origin and candidate.event_type not in ORIGIN_EVENT_TYPES:
                raise InstrumentProfileError(
                    "INVALID_PRIMARY_ORIGIN_TYPE", candidate.event_type
                )
            if candidate.is_primary_origin:
                current_origin = connection.execute(
                    """SELECT e.profile_event_id FROM instrument_profile_events e
                       WHERE e.asset=? AND e.is_primary_origin=1 AND NOT EXISTS (
                           SELECT 1 FROM instrument_profile_events newer
                           WHERE newer.supersedes_event_id=e.profile_event_id
                       )""",
                    (candidate.asset,),
                ).fetchone()
                if (current_origin and current_origin[0] != event_id
                        and candidate.supersedes_event_id != current_origin[0]):
                    raise InstrumentProfileError(
                        "PRIMARY_ORIGIN_ALREADY_RECORDED", str(current_origin[0])
                    )
            cursor = connection.execute(
                """INSERT OR IGNORE INTO instrument_profile_events
                   (profile_event_id,asset,registration_timeframe,event_type,is_primary_origin,
                    occurred_at_utc,date_precision,block_height,title,source_url,source_name,
                    source_retrieved_at_utc,evidence_sha256,verification_status,notes,
                    supersedes_event_id,recorded_at_utc)
                   VALUES (?,?,'D1',?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (event_id, candidate.asset, candidate.event_type,
                 int(candidate.is_primary_origin), candidate.occurred_at_utc,
                 candidate.date_precision, candidate.block_height, candidate.title,
                 candidate.source_url, candidate.source_name,
                 candidate.source_retrieved_at_utc, candidate.evidence_sha256,
                 candidate.verification_status, candidate.notes,
                 candidate.supersedes_event_id, recorded_at_utc),
            )
    return {"contract": "fragarach.instrument_profile_event.v1",
            "profile_event_id": event_id, "symbol": candidate.asset,
            "outcome": "RECORDED" if cursor.rowcount else "ALREADY_RECORDED"}


def instrument_profile(connection_or_path: Any, symbol: str) -> dict[str, Any]:
    owns_connection = not hasattr(connection_or_path, "execute")
    connection = open_read_only(connection_or_path) if owns_connection else connection_or_path
    try:
        registration = connection.execute(
            """SELECT asset_class,instrument_type FROM instrument_registrations
               WHERE asset=? AND timeframe='D1'""",
            (symbol,),
        ).fetchone()
        if registration is None:
            raise InstrumentProfileError("UNREGISTERED_SYMBOL", symbol)
        rows = connection.execute(
            """SELECT e.profile_event_id,e.event_type,e.is_primary_origin,e.occurred_at_utc,
                      e.date_precision,e.block_height,e.title,e.source_url,e.source_name,
                      e.source_retrieved_at_utc,e.evidence_sha256,e.verification_status,e.notes
               FROM instrument_profile_events e
               WHERE e.asset=? AND NOT EXISTS (
                   SELECT 1 FROM instrument_profile_events newer
                   WHERE newer.supersedes_event_id=e.profile_event_id
               )
               ORDER BY e.occurred_at_utc,e.event_type,e.profile_event_id""",
            (symbol,),
        ).fetchall()
        events = [_event_dict(row) for row in rows]
        origins = [item for item in events if item["is_primary_origin"]]
        origin = origins[-1] if origins else None
        history = connection.execute(
            """SELECT count(*),min(open_time_utc),max(open_time_utc)
               FROM bars WHERE asset=? AND timeframe='D1'""",
            (symbol,),
        ).fetchone()
        high = connection.execute(
            """SELECT open_time_utc,high FROM bars
               WHERE asset=? AND timeframe='D1'
               ORDER BY CAST(high AS REAL) DESC,open_time_utc LIMIT 1""",
            (symbol,),
        ).fetchone()
        low = connection.execute(
            """SELECT open_time_utc,low FROM bars
               WHERE asset=? AND timeframe='D1'
               ORDER BY CAST(low AS REAL),open_time_utc LIMIT 1""",
            (symbol,),
        ).fetchone()
        requirement = required_origin_event(str(registration[0]), str(registration[1]))
        return {
            "contract": "fragarach.instrument_profile.v1",
            "symbol": symbol,
            "origin_requirement": requirement,
            "origin_status": "VERIFIED" if origin and str(origin["verification_status"]).startswith("VERIFIED_")
            else "NEEDS_REVIEW" if origin else "NOT_REQUIRED" if requirement is None else "REQUIRED_MISSING",
            "origin": origin,
            "history": {
                "basis": "FRAGARACH_GOVERNED_D1_HISTORY",
                "start_utc": _iso_epoch(history[1]),
                "end_utc": _iso_epoch(history[2]),
                "bar_count": int(history[0] or 0),
                # A populated lane proves a stored range, not that the provider's
                # earliest-available boundary was reached.  Completeness must be
                # asserted only from a separately governed acquisition receipt.
                "all_available_history_held": None,
                "completeness_status": "UNVERIFIED",
            },
            "extrema": {
                "basis": "FRAGARACH_AVAILABLE_GOVERNED_D1_HISTORY",
                "high": None if high is None else {"price": str(high[1]), "at_utc": _iso_epoch(high[0])},
                "low": None if low is None else {"price": str(low[1]), "at_utc": _iso_epoch(low[0])},
                "as_of_utc": _iso_epoch(history[2]),
            },
            "milestones": [item for item in events if not item["is_primary_origin"]],
        }
    finally:
        if owns_connection:
            connection.close()


def _canonical_values(candidate: InstrumentProfileEventCandidate, *, recorded_at_utc: str) -> dict[str, Any]:
    for value in (candidate.occurred_at_utc, candidate.source_retrieved_at_utc, recorded_at_utc):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise InstrumentProfileError("INVALID_PROFILE_TIMESTAMP", value) from error
        if parsed.utcoffset() is None or parsed.astimezone(UTC).utcoffset() is None:
            raise InstrumentProfileError("INVALID_PROFILE_TIMESTAMP", value)
    if candidate.date_precision not in {"YEAR", "MONTH", "DAY", "SECOND"}:
        raise InstrumentProfileError("INVALID_DATE_PRECISION", candidate.date_precision)
    if candidate.event_type not in EVENT_TYPES:
        raise InstrumentProfileError("INVALID_PROFILE_EVENT_TYPE", candidate.event_type)
    if candidate.verification_status not in VERIFICATION_STATUSES:
        raise InstrumentProfileError("INVALID_VERIFICATION_STATUS", candidate.verification_status)
    if not candidate.source_url.startswith("https://"):
        raise InstrumentProfileError("INVALID_SOURCE_URL", candidate.source_url)
    if len(candidate.evidence_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in candidate.evidence_sha256
    ):
        raise InstrumentProfileError("INVALID_EVIDENCE_SHA256", candidate.evidence_sha256)
    return {**asdict(candidate), "recorded_at_utc": recorded_at_utc}


def _event_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "profile_event_id": row[0], "event_type": row[1],
        "is_primary_origin": bool(row[2]), "occurred_at_utc": row[3],
        "date_precision": row[4], "block_height": row[5], "title": row[6],
        "source_url": row[7], "source_name": row[8],
        "source_retrieved_at_utc": row[9], "evidence_sha256": row[10],
        "verification_status": row[11], "notes": row[12],
    }


def _iso_epoch(value: int | None) -> str | None:
    return None if value is None else datetime.fromtimestamp(int(value), UTC).isoformat()
