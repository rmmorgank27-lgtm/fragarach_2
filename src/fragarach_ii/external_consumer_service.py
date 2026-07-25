"""SPEC-018 read-only canonical-history contract for external consumers."""

from __future__ import annotations

import os
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .history_depth import D1_MORPHIX_MIN_OBSERVATIONS, has_morphix_d1_depth
from .storage import open_read_only
from .truth_engine import TruthEngineError, truth_state_for_lane
from .publication_service import lane_publication_state


CONTRACT = "fragarach_ii.external_consumer_history.v1"
INTRADAY_CONTRACT="fragarach_ii.external_consumer_history.v2"
CATALOG_CONTRACT = "fragarach_ii.external_consumer_catalog.v2"
ESTATE_CATALOGUE_CONTRACT = "fragarach.catalogue.v1"
SUPPORTED_TIMEFRAMES={"D1","H1","M30","M5"}
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


def get_catalogue() -> dict[str, object]:
    """Return one atomic, read-only active-Estate projection for consumers.

    This intentionally reports authority facts only.  It neither consults a
    provider nor derives a replacement Estate from consumer cache state.
    """

    return HistoryService(canonical_database_path()).get_catalogue()


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
        if requested_timeframe not in SUPPORTED_TIMEFRAMES:
            raise ExternalConsumerServiceError(
                "UNSUPPORTED_TIMEFRAME",requested_timeframe
            )
        publication = lane_publication_state(
            self.database_path, requested_symbol, requested_timeframe
        )
        if publication != "PUBLISHED":
            return _unavailable(
                "PUBLICATION_PENDING" if publication == "PUBLISHING" else publication,
                requested_symbol, requested_timeframe,
                f"{requested_symbol}:{requested_timeframe} canonical evidence is {publication.lower()}",
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
            asset_class=connection.execute("SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",(canonical_symbol,)).fetchone()[0]
            from .lane_commissioning import market_policy
            policy=market_policy(asset_class,requested_timeframe)
            if policy=="INTENTIONALLY_DEFERRED":return _unavailable("INTENTIONALLY_DEFERRED",canonical_symbol,requested_timeframe,"Stock intraday authority is intentionally deferred")
            if connection.execute("SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",(canonical_symbol,requested_timeframe)).fetchone() is None:
                return _unavailable("TIMEFRAME_NOT_ACTIVE",canonical_symbol,requested_timeframe,f"{canonical_symbol}:{requested_timeframe} is not active")

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
            "contract": CONTRACT if requested_timeframe=="D1" else INTRADAY_CONTRACT,
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
                WHERE timeframe IN ('D1','H1','M30','M5')
                GROUP BY asset,timeframe
                ORDER BY asset,timeframe
                """,
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
        from .estate_truth_service import estate_truth_state
        return {
            "contract": CATALOG_CONTRACT,
            "status": "AVAILABLE",
            "histories": histories,
            "capabilities":estate_truth_state(self.database_path)["timeframe_capabilities"],
        }

    def get_catalogue(self) -> dict[str, object]:
        """Project registration, lifecycle and canonical D1 availability once."""

        # A single read transaction gives this response one SQLite snapshot.
        connection = open_read_only(self.database_path)
        try:
            connection.execute("BEGIN")
            registrations = connection.execute(
                """
                SELECT asset,asset_class,registration_status,registered_at_utc,provider_id
                FROM instrument_registrations
                WHERE timeframe='D1'
                ORDER BY asset
                """
            ).fetchall()
            lanes = {
                str(row[0]) for row in connection.execute(
                    "SELECT asset FROM evidence_lanes WHERE timeframe='D1'"
                ).fetchall()
            }
            bar_counts = {
                str(row[0]): int(row[1]) for row in connection.execute(
                    "SELECT asset,count(*) FROM bars WHERE timeframe='D1' GROUP BY asset"
                ).fetchall()
            }
            latest_ingests = {
                str(row[0]): {
                    "provider": row[1],
                    "provider_symbol": row[2],
                    "from_date": row[3],
                    "through_date": row[4],
                    "source_rows": int(row[5] or 0),
                    "inserted": int(row[6] or 0),
                    "unchanged": int(row[7] or 0),
                    "corrected": int(row[8] or 0),
                    "rejected": int(row[9] or 0),
                }
                for row in connection.execute(
                    """
                    WITH ranked AS (
                        SELECT json_extract(detail,'$.asset') asset,
                               json_extract(detail,'$.provider') provider,
                               json_extract(detail,'$.provider_symbol') provider_symbol,
                               json_extract(detail,'$.from_date') from_date,
                               json_extract(detail,'$.through_date') through_date,
                               json_extract(detail,'$.source_rows') source_rows,
                               json_extract(detail,'$.inserted') inserted,
                               json_extract(detail,'$.unchanged') unchanged,
                               json_extract(detail,'$.corrected') corrected,
                               json_extract(detail,'$.rejected') rejected,
                               row_number() OVER (
                                   PARTITION BY json_extract(detail,'$.asset')
                                   ORDER BY finished_at_utc DESC, ingest_run_id DESC
                               ) ordinal
                        FROM ingest_runs
                        WHERE status='committed'
                          AND json_extract(detail,'$.timeframe')='D1'
                    )
                    SELECT asset,provider,provider_symbol,from_date,through_date,
                           source_rows,inserted,unchanged,corrected,rejected
                    FROM ranked WHERE ordinal=1
                    """
                ).fetchall()
                if row[0]
            }
            events = connection.execute(
                """
                SELECT authority_event_id,supersedes_event_id,recorded_at_utc,canonical_payload
                FROM authority_events
                ORDER BY recorded_at_utc,authority_event_id
                """
            ).fetchall()
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

        # This is the established Fragarach lifecycle interpretation used by
        # the scheduler integrity projection; importing it avoids a second
        # membership doctrine in a consumer endpoint.
        from .scheduler_integrity import _lifecycle_projection

        lifecycle = _lifecycle_projection(events)
        symbols: list[dict[str, object]] = []
        revision_facts: list[dict[str, object]] = []
        for asset, asset_class, registration_status, registered_at, provider_id in registrations:
            symbol = str(asset)
            leaf = lifecycle.get((symbol, "D1")) or lifecycle.get((symbol, None)) or {}
            lifecycle_state = str(leaf.get("lifecycle_state") or "ACTIVE")
            registered = str(registration_status).startswith("REGISTERED_")
            retired = lifecycle_state.startswith(("RETIRED", "QUARANTINED")) or lifecycle_state == "PERMANENTLY_REMOVED"
            active = registered and not retired
            bars = bar_counts.get(symbol, 0)
            d1_governed = symbol in lanes and bars > 0
            availability = "AVAILABLE" if d1_governed else "UNAVAILABLE"
            morphix_ready = active and d1_governed and has_morphix_d1_depth(bars)
            morphix_reason = None if morphix_ready else _morphix_ineligibility_reason(
                asset_class=str(asset_class),
                provider_id=str(provider_id or ""),
                bar_count=bars,
                latest_ingest=latest_ingests.get(symbol),
                active=active,
                d1_governed=d1_governed,
            )
            market = _catalogue_market(str(asset_class))
            item = {
                "symbol": symbol,
                "market": market,
                "lifecycle": lifecycle_state if not active else "ACTIVE",
                "availability": availability,
                "histories": [{
                    "timeframe": "D1",
                    "governed": d1_governed,
                    "eligible_for_morphix": morphix_ready,
                    "morphix_eligibility_reason": morphix_reason,
                    "minimum_required_bar_count": D1_MORPHIX_MIN_OBSERVATIONS,
                    "bar_count": bars,
                }],
            }
            symbols.append(item)
            revision_facts.append({
                "symbol": symbol, "market": market, "lifecycle": item["lifecycle"],
                "availability": availability, "d1_governed": d1_governed,
                "registered_at": registered_at, "bar_count": bars,
                "eligible_for_morphix": morphix_ready,
                "morphix_eligibility_reason": morphix_reason,
            })
        revision = "sha256:" + hashlib.sha256(
            json.dumps(revision_facts, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "contract": ESTATE_CATALOGUE_CONTRACT,
            "status": "AVAILABLE",
            "catalogue_revision": revision,
            "generated_at": datetime.now(UTC).isoformat(),
            "symbols": symbols,
        }


def _catalogue_market(asset_class: str) -> str:
    """Expose the existing authoritative asset class as the consumer market."""

    return {
        "CRYPTO": "Crypto",
        "FX": "Forex",
        "US_EQUITIES": "Equities",
        "METALS": "Metals",
        "ENERGY": "Energy",
        "INDICES": "Indices",
        "AUSTRALIAN_EQUITIES": "Equities",
        "UK_EQUITIES": "Equities",
        "GERMAN_EQUITIES": "Equities",
    }.get(asset_class, asset_class)


def _morphix_ineligibility_reason(
    *,
    asset_class: str,
    provider_id: str,
    bar_count: int,
    latest_ingest: dict[str, object] | None,
    active: bool,
    d1_governed: bool,
) -> str:
    if not active:
        return "LIFECYCLE_INACTIVE"
    if not d1_governed or bar_count == 0:
        return "NO_HISTORICAL_ROWS_RETURNED"
    if latest_ingest and int(latest_ingest.get("rejected") or 0) > 0:
        return "VALIDATION_REJECTED_ROWS"
    if "EQUITIES" in asset_class and provider_id and provider_id != "YAHOO_FINANCE":
        return "WRONG_PROVIDER_SELECTED"
    if latest_ingest and _requested_day_span(
        latest_ingest.get("from_date"), latest_ingest.get("through_date")
    ) < 365:
        return "SHORT_HISTORY_FETCH_USED"
    return "PROVIDER_HISTORY_LIMIT"


def _requested_day_span(start: object, end: object) -> int:
    try:
        first = datetime.fromisoformat(str(start)).date()
        last = datetime.fromisoformat(str(end)).date()
    except (TypeError, ValueError):
        return 0
    return max(0, (last - first).days + 1)


def _registered_symbol(connection, symbol: str, timeframe: str) -> str | None:
    direct = connection.execute(
        "SELECT asset FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
        (symbol,),
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
        ("D1", symbol),
    ).fetchall()
    if len(aliases) > 1:
        raise ExternalConsumerServiceError("AMBIGUOUS_SYMBOL", symbol)
    return str(aliases[0][0]) if aliases else None


def _unavailable(
    status: str, symbol: str, timeframe: str, reason: str
) -> dict[str, object]:
    return {
        "contract": CONTRACT if timeframe=="D1" else INTRADAY_CONTRACT,
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
