"""SPEC-018 read-only canonical-history contract for external consumers."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from .storage import open_read_only
from .truth_engine import TruthEngineError, truth_state_for_lane


CONTRACT = "fragarach_ii.external_consumer_history.v1"
CATALOG_CONTRACT = "fragarach_ii.external_consumer_catalog.v1"
SUPPORTED_TIMEFRAME = "D1"
DATABASE_ENVIRONMENT_VARIABLE = "FRAGARACH_AUTHORITY_DATABASE"
DEFAULT_DATABASE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "runtime"
    / "spec002_real_evidence_acceptance.sqlite3"
)


class ExternalConsumerServiceError(RuntimeError):
    """A malformed request or unavailable authority runtime."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def canonical_database_path() -> Path:
    """Resolve the authority-owned database location, never a consumer database."""

    configured = os.environ.get(DATABASE_ENVIRONMENT_VARIABLE)
    return Path(configured).expanduser().resolve() if configured else DEFAULT_DATABASE.resolve()


def get_history(symbol: str, timeframe: str) -> dict[str, object]:
    """Return one complete canonical history from the configured authority."""

    return HistoryService(canonical_database_path()).get_history(symbol, timeframe)


def list_histories() -> dict[str, object]:
    """List canonical histories that external consumers may request."""

    return HistoryService(canonical_database_path()).list_histories()


class HistoryService:
    """Read-only service bound by Fragarach to one canonical database."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    def get_history(self, symbol: str, timeframe: str) -> dict[str, object]:
        requested_symbol = symbol.strip().upper()
        requested_timeframe = timeframe.strip().upper()
        if not requested_symbol or not requested_timeframe:
            raise ExternalConsumerServiceError(
                "INVALID_REQUEST", "symbol and timeframe are required"
            )
        if requested_timeframe != SUPPORTED_TIMEFRAME:
            raise ExternalConsumerServiceError(
                "UNSUPPORTED_TIMEFRAME", "SPEC-018 serves D1 only"
            )

        connection = open_read_only(self.database_path)
        try:
            canonical_symbol = _registered_symbol(
                connection, requested_symbol, requested_timeframe
            )
            if canonical_symbol is None:
                return _unavailable(
                    "NOT_REGISTERED",
                    requested_symbol,
                    requested_timeframe,
                    f"{requested_symbol}:{requested_timeframe} is not registered",
                )

            rows = connection.execute(
                """
                SELECT open_time_utc,open,high,low,close,volume
                FROM bars
                WHERE asset=? AND timeframe=?
                ORDER BY open_time_utc
                """,
                (canonical_symbol, requested_timeframe),
            ).fetchall()
            if not rows:
                return _unavailable(
                    "NO_HISTORY",
                    canonical_symbol,
                    requested_timeframe,
                    f"{canonical_symbol}:{requested_timeframe} has no canonical history",
                )
        finally:
            connection.close()

        try:
            truth = truth_state_for_lane(
                self.database_path,
                symbol=canonical_symbol,
                timeframe=requested_timeframe,
            )
        except TruthEngineError as error:
            return _unavailable(
                "NO_HISTORY",
                canonical_symbol,
                requested_timeframe,
                f"{error.code}: {error}",
            )

        authority = str(truth["authority_state"])
        reason = _authority_reason(truth) if authority == "RED" else None
        return {
            "contract": CONTRACT,
            "status": "AVAILABLE",
            "authority": authority,
            "reason": reason,
            "truth_score": truth["truth_score"],
            "CAODT": truth["caodt"],
            "symbol": canonical_symbol,
            "timeframe": requested_timeframe,
            "first_bar": _iso_utc(rows[0][0]),
            "last_bar": _iso_utc(rows[-1][0]),
            "bar_count": len(rows),
            "bars": [
                {
                    "timestamp": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                }
                for row in rows
            ],
        }

    def list_histories(self) -> dict[str, object]:
        connection = open_read_only(self.database_path)
        try:
            lanes = connection.execute(
                """
                SELECT asset,timeframe,count(*),min(open_time_utc),max(open_time_utc)
                FROM bars
                WHERE timeframe=?
                GROUP BY asset,timeframe
                ORDER BY asset,timeframe
                """,
                (SUPPORTED_TIMEFRAME,),
            ).fetchall()
        finally:
            connection.close()

        histories = []
        for symbol, timeframe, count, earliest, latest in lanes:
            try:
                truth = truth_state_for_lane(
                    self.database_path, symbol=symbol, timeframe=timeframe
                )
            except TruthEngineError:
                continue
            histories.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "authority": truth["authority_state"],
                    "truth_score": truth["truth_score"],
                    "CAODT": truth["caodt"],
                    "first_bar": _iso_utc(earliest),
                    "last_bar": _iso_utc(latest),
                    "bar_count": count,
                }
            )
        return {
            "contract": CATALOG_CONTRACT,
            "status": "AVAILABLE",
            "histories": histories,
        }


def _registered_symbol(connection, symbol: str, timeframe: str) -> str | None:
    direct = connection.execute(
        "SELECT asset FROM instrument_registrations WHERE asset=? AND timeframe=?",
        (symbol, timeframe),
    ).fetchone()
    if direct:
        return str(direct[0])

    aliases = connection.execute(
        """
        SELECT DISTINCT r.asset
        FROM instrument_registrations AS r,json_each(r.aliases_json) AS alias
        WHERE r.timeframe=?
          AND json_extract(alias.value,'$.normalized_alias')=?
        ORDER BY r.asset
        """,
        (timeframe, symbol),
    ).fetchall()
    if len(aliases) > 1:
        raise ExternalConsumerServiceError("AMBIGUOUS_SYMBOL", symbol)
    return str(aliases[0][0]) if aliases else None


def _unavailable(
    status: str, symbol: str, timeframe: str, reason: str
) -> dict[str, object]:
    return {
        "contract": CONTRACT,
        "status": status,
        "authority": None,
        "reason": reason,
        "truth_score": None,
        "CAODT": None,
        "symbol": symbol,
        "timeframe": timeframe,
        "first_bar": None,
        "last_bar": None,
        "bar_count": 0,
        "bars": [],
    }


def _authority_reason(truth: dict[str, object]) -> str:
    explanation = truth.get("explanation")
    components = explanation.get("components") if isinstance(explanation, dict) else None
    if isinstance(components, dict):
        low_components = []
        for name, value in components.items():
            if not isinstance(value, dict):
                continue
            score = value.get("score")
            if isinstance(score, int | float) and score < 50:
                low_components.append(
                    f"{str(name).upper()} {score}: {value.get('basis', 'no basis supplied')}"
                )
        if low_components:
            return "; ".join(low_components)
    limitations = explanation.get("limitations") if isinstance(explanation, dict) else None
    if isinstance(limitations, list) and limitations:
        return ", ".join(str(value) for value in limitations)
    return f"Truth Score {truth['truth_score']}"


def _iso_utc(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, UTC).isoformat()
