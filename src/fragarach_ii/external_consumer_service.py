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
from .history_range_contract import (
    HISTORY_RANGE_CONTRACT_VERSION,
    HistoryRangeContractError,
    canonical_utc,
    ordered_range_fingerprint,
    request_identity,
    validate_range,
)


CONTRACT = "fragarach_ii.external_consumer_history.v1"
INTRADAY_CONTRACT="fragarach_ii.external_consumer_history.v2"
CATALOG_CONTRACT = "fragarach_ii.external_consumer_catalog.v2"
ESTATE_CATALOGUE_CONTRACT = "fragarach.catalogue.v1"
LANE_STATUS_CONTRACT = "fragarach_ii.lane_status.v1"
SUPPORTED_TIMEFRAMES={"D1","H1","M30","M15","M5"}
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


def lane_status_contract() -> dict[str, object]:
    """Return the additive four-band freshness notice for every consumer.

    ``authority`` remains the legacy three-band compatibility alias. New
    consumers must make display or admission decisions from ``lane_status``.
    """

    return {
        "contract": LANE_STATUS_CONTRACT,
        "unit": "eligible_completed_timeframe_boundary",
        "states": {
            "GOLD": {
                "lag_completed_units": 0,
                "meaning": "canonical edge is present at the expected completed boundary",
            },
            "GREEN": {
                "lag_completed_units": "1-3",
                "meaning": "behind the canonical edge, but within three completed timeframe units",
            },
            "AMBER": {
                "lag_completed_units": "4-12",
                "meaning": "behind by four to twelve completed timeframe units",
            },
            "RED": {
                "lag_completed_units": ">=13",
                "meaning": "behind by more than twelve units, unavailable, or blocked by integrity failure",
            },
        },
        "consumer_guidance": {
            "read": "Use lane_status for the four-band state.",
            "legacy_authority": "authority remains GREEN for a GOLD lane so existing three-band readers continue to work.",
            "safety_days_eligible": ["GOLD", "GREEN", "AMBER"],
        },
    }


def get_history(
    symbol: str, timeframe: str, *, consumer: str | None = None,
    evidence_requirement: str = "REAL_ONLY",
) -> dict[str, object]:
    """Return governed real or explicitly permitted synthetic history."""

    return HistoryService(canonical_database_path()).get_history(
        symbol, timeframe, consumer=consumer,
        evidence_requirement=evidence_requirement,
    )


def get_history_range(
    symbol: str,
    timeframe: str,
    start_utc: str,
    end_utc_exclusive: str,
    as_of_utc: str,
    consumer: str,
    *,
    evidence_requirement: str = "REAL_ONLY",
) -> dict[str, object]:
    """Return a completed, bounded history range from the authority."""

    return HistoryService(canonical_database_path()).get_history_range(
        symbol,
        timeframe,
        start_utc,
        end_utc_exclusive,
        as_of_utc,
        consumer,
        evidence_requirement=evidence_requirement,
    )


def list_histories(
    *, consumer: str | None = None, evidence_requirement: str = "REAL_ONLY",
    timeframes: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """List governed histories that an identified consumer may request."""

    return HistoryService(canonical_database_path()).list_histories(
        consumer=consumer, evidence_requirement=evidence_requirement,
        timeframes=timeframes,
    )


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

    def get_history(
        self, symbol: str, timeframe: str, *, consumer: str | None = None,
        evidence_requirement: str = "REAL_ONLY",
    ) -> dict[str, object]:
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
        if requested_timeframe == "M15" and not self._has_direct_history(
            requested_symbol, requested_timeframe
        ):
            return self._get_synthetic_history(
                requested_symbol, requested_timeframe,
                consumer=consumer, evidence_requirement=evidence_requirement,
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
            if policy=="INTENTIONALLY_DEFERRED":
                from .stock_cfd_mt5 import broker_stock_cfd_intraday_enabled
                if not broker_stock_cfd_intraday_enabled(
                    self.database_path, canonical_symbol, requested_timeframe
                ):
                    return _unavailable("INTENTIONALLY_DEFERRED",canonical_symbol,requested_timeframe,"Stock intraday authority is intentionally deferred")
            if connection.execute("SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",(canonical_symbol,requested_timeframe)).fetchone() is None:
                return _unavailable("TIMEFRAME_NOT_ACTIVE",canonical_symbol,requested_timeframe,f"{canonical_symbol}:{requested_timeframe} is not active")

            rows = connection.execute(
                """
                WITH ranked_activity AS (
                    SELECT open_time_utc,tick_volume,real_volume,spread,
                           activity_source_label,provider_symbol,
                           row_number() OVER (
                               PARTITION BY open_time_utc
                               ORDER BY r.rowid DESC,activity_observation_id DESC
                           ) AS rank
                    FROM market_activity_observations a
                    JOIN ingest_runs r ON r.ingest_run_id=a.admission_run_id
                    WHERE a.asset=? AND a.timeframe=?
                )
                SELECT b.open_time_utc,b.open,b.high,b.low,b.close,b.volume,
                       a.tick_volume,a.real_volume,a.spread,
                       a.activity_source_label,a.provider_symbol
                FROM bars b LEFT JOIN ranked_activity a
                  ON a.open_time_utc=b.open_time_utc AND a.rank=1
                WHERE b.asset=? AND b.timeframe=?
                ORDER BY b.open_time_utc
                """,
                (canonical_symbol, requested_timeframe, canonical_symbol, requested_timeframe),
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

        lane_status = str(truth["authority_state"])
        authority = _legacy_consumer_authority(lane_status)
        reason = _authority_reason(truth) if lane_status == "RED" else None
        return {
            "contract": CONTRACT if requested_timeframe=="D1" else INTRADAY_CONTRACT,
            "lane_status_contract": lane_status_contract(),
            "status": "AVAILABLE",
            "authority": authority,
            "lane_status": lane_status,
            "reason": reason,
            "truth_score": truth["truth_score"],
            "CAODT": truth["caodt"],
            "symbol": canonical_symbol,
            "timeframe": requested_timeframe,
            "first_bar": _iso_utc(rows[0][0]),
            "last_bar": _iso_utc(rows[-1][0]),
            "bar_count": len(rows),
            "bars": [_history_bar(row) for row in rows],
        }

    def get_history_range(
        self,
        symbol: str,
        timeframe: str,
        start_utc: str,
        end_utc_exclusive: str,
        as_of_utc: str,
        consumer: str,
        *,
        evidence_requirement: str = "REAL_ONLY",
    ) -> dict[str, object]:
        """Return only observations complete within the declared evidence cutoff."""

        requested_symbol = symbol.strip().upper()
        requested_timeframe = timeframe.strip().upper()
        consumer_identity = consumer.strip()
        if not requested_symbol or not requested_timeframe:
            raise ExternalConsumerServiceError(
                "INVALID_REQUEST", "symbol and timeframe are required"
            )
        if not consumer_identity:
            raise ExternalConsumerServiceError(
                "CONSUMER_REQUIRED", "consumer identity is required"
            )
        try:
            start, end, as_of = validate_range(
                start_utc, end_utc_exclusive, as_of_utc
            )
        except HistoryRangeContractError as error:
            raise ExternalConsumerServiceError(error.code, str(error)) from error
        identity = request_identity(
            symbol=requested_symbol,
            timeframe=requested_timeframe,
            start=start,
            end=end,
            as_of=as_of,
            consumer=consumer_identity,
        )
        request = _range_request_fields(
            identity, consumer_identity, requested_symbol, requested_timeframe,
            start, end, as_of,
        )
        if requested_timeframe not in SUPPORTED_TIMEFRAMES:
            return _range_empty_response(
                request,
                availability_state="UNSUPPORTED",
                status="UNSUPPORTED_TIMEFRAME",
                warnings=["TIMEFRAME_NOT_SUPPORTED"],
            )
        if requested_timeframe == "M15" and not self._has_direct_history(
            requested_symbol, requested_timeframe
        ):
            return self._get_synthetic_history_range(
                request,
                start=start,
                end=end,
                as_of=as_of,
                evidence_requirement=evidence_requirement,
            )

        publication = lane_publication_state(
            self.database_path, requested_symbol, requested_timeframe
        )
        if publication != "PUBLISHED":
            status = "PUBLICATION_PENDING" if publication == "PUBLISHING" else publication
            return _range_empty_response(
                request,
                availability_state="UNAVAILABLE",
                status=status,
                warnings=[status],
            )

        connection = open_read_only(self.database_path)
        try:
            canonical_symbol = _registered_symbol(
                connection, requested_symbol, requested_timeframe
            )
            if canonical_symbol is None:
                return _range_empty_response(
                    request,
                    availability_state="UNAVAILABLE",
                    status="NOT_REGISTERED",
                    warnings=["SYMBOL_NOT_REGISTERED"],
                )
            registration = connection.execute(
                """SELECT asset_class,calendar_id,exchange_name
                   FROM instrument_registrations
                   WHERE asset=? AND timeframe='D1'""",
                (canonical_symbol,),
            ).fetchone()
            if registration is None:
                return _range_empty_response(
                    request,
                    availability_state="UNAVAILABLE",
                    status="NOT_REGISTERED",
                    warnings=["SYMBOL_NOT_REGISTERED"],
                )
            asset_class, calendar_id, exchange_name = map(
                lambda value: None if value is None else str(value), registration
            )
            from .lane_commissioning import market_policy
            policy = market_policy(str(asset_class), requested_timeframe)
            if policy == "INTENTIONALLY_DEFERRED":
                return _range_empty_response(
                    request,
                    availability_state="UNSUPPORTED",
                    status="INTENTIONALLY_DEFERRED",
                    warnings=["TIMEFRAME_INTENTIONALLY_DEFERRED"],
                )
            lane_state = connection.execute(
                """SELECT l.asset,s.state_version,s.updated_at_utc
                   FROM evidence_lanes l
                   LEFT JOIN lane_state s
                     ON s.asset=l.asset AND s.timeframe=l.timeframe
                   WHERE l.asset=? AND l.timeframe=?""",
                (canonical_symbol, requested_timeframe),
            ).fetchone()
            if lane_state is None:
                return _range_empty_response(
                    request,
                    availability_state="UNAVAILABLE",
                    status="TIMEFRAME_NOT_ACTIVE",
                    warnings=["TIMEFRAME_NOT_ACTIVE"],
                )
            raw_rows = connection.execute(
                """
                WITH ranked_activity AS (
                    SELECT open_time_utc,tick_volume,real_volume,spread,
                           activity_source_label,provider_symbol,
                           row_number() OVER (
                               PARTITION BY open_time_utc
                               ORDER BY r.rowid DESC,activity_observation_id DESC
                           ) AS rank
                    FROM market_activity_observations a
                    JOIN ingest_runs r ON r.ingest_run_id=a.admission_run_id
                    WHERE a.asset=? AND a.timeframe=?
                )
                SELECT b.open_time_utc,b.close_time_utc,b.open,b.high,b.low,b.close,b.volume,
                       a.tick_volume,a.real_volume,a.spread,
                       a.activity_source_label,a.provider_symbol
                FROM bars b LEFT JOIN ranked_activity a
                  ON a.open_time_utc=b.open_time_utc AND a.rank=1
                WHERE b.asset=? AND b.timeframe=? ORDER BY b.open_time_utc
                """,
                (canonical_symbol, requested_timeframe, canonical_symbol, requested_timeframe),
            ).fetchall()
        finally:
            connection.close()

        if not raw_rows:
            return _range_empty_response(
                {**request, "symbol": canonical_symbol},
                availability_state="UNAVAILABLE",
                status="NO_HISTORY",
                warnings=["NO_CANONICAL_HISTORY"],
            )
        try:
            all_observations = [
                _direct_observation(
                    row,
                    timeframe=requested_timeframe,
                    asset_class=str(asset_class),
                    calendar_id=calendar_id,
                    exchange_name=exchange_name,
                    symbol=canonical_symbol,
                )
                for row in raw_rows
            ]
        except (RuntimeError, ValueError) as error:
            return _range_empty_response(
                {**request, "symbol": canonical_symbol},
                availability_state="UNSUPPORTED",
                status="COMPLETION_AUTHORITY_UNAVAILABLE",
                warnings=[f"COMPLETION_AUTHORITY_UNAVAILABLE: {error}"],
            )
        observations = _bounded_observations(all_observations, start, end, as_of)
        authority_revision = ordered_range_fingerprint(
            canonical_symbol, requested_timeframe, all_observations
        )
        quality_warnings: list[str] = []
        authority_state = "UNKNOWN"
        lane_status = "UNKNOWN"
        truth_score: object = None
        try:
            truth = truth_state_for_lane(
                self.database_path,
                symbol=canonical_symbol,
                timeframe=requested_timeframe,
            )
            lane_status = str(truth["authority_state"])
            authority_state = _legacy_consumer_authority(lane_status)
            truth_score = truth.get("truth_score")
            if authority_state not in {"GOLD", "GREEN"}:
                quality_warnings.append(
                    f"AUTHORITY_STATE_{authority_state}: {_authority_reason(truth)}"
                )
        except TruthEngineError as error:
            quality_warnings.append(f"TRUTH_STATE_UNAVAILABLE: {error.code}")
        receipt = {
            "authority_kind": "FRAGARACH_II",
            "authority_revision": authority_revision,
            "authority_state": authority_state,
            "lane_status": lane_status,
            "truth_score": truth_score,
            "lane_state_version": lane_state[1],
            "lane_updated_at_utc": lane_state[2],
            "calendar_id": calendar_id,
        }
        return _range_available_response(
            {**request, "symbol": canonical_symbol},
            observations=observations,
            all_observations=all_observations,
            start=start,
            end=end,
            as_of=as_of,
            authority_kind="FRAGARACH_II",
            authority_revision=authority_revision,
            source_receipt=receipt,
            evidence_class="REAL",
            additional_warnings=quality_warnings,
        )

    def _get_synthetic_history_range(
        self,
        request: dict[str, object],
        *,
        start: datetime,
        end: datetime,
        as_of: datetime,
        evidence_requirement: str,
    ) -> dict[str, object]:
        if evidence_requirement.strip().upper() != "SYNTHETIC_PERMITTED":
            return _range_empty_response(
                request,
                availability_state="UNAVAILABLE",
                status="SYNTHETIC_NOT_PERMITTED",
                warnings=["SYNTHETIC_EVIDENCE_NOT_PERMITTED"],
                evidence_class="SYNTHETIC",
            )
        from .synthetic_repository import (
            SyntheticRepository,
            SyntheticRepositoryError,
        )
        repository = SyntheticRepository(self.database_path)
        if not repository.path.is_file():
            return _range_empty_response(
                request,
                availability_state="UNAVAILABLE",
                status="SYNTHETIC_REPOSITORY_UNAVAILABLE",
                warnings=["SYNTHETIC_REPOSITORY_UNAVAILABLE"],
                evidence_class="SYNTHETIC",
            )
        registration_id = f"{request['symbol']}:{request['timeframe']}"
        try:
            product = repository.product(registration_id)
            if request["consumer_identity"] not in product["authorised_consumers"]:
                return _range_empty_response(
                    request,
                    availability_state="UNAVAILABLE",
                    status="CONSUMER_NOT_AUTHORISED",
                    warnings=["CONSUMER_NOT_AUTHORISED"],
                    evidence_class="SYNTHETIC",
                )
            rows = repository.observations(
                registration_id, include_provenance=False
            )
        except SyntheticRepositoryError as error:
            return _range_empty_response(
                request,
                availability_state="UNAVAILABLE",
                status=error.code,
                warnings=[error.code],
                evidence_class="SYNTHETIC",
            )
        product_status = str(product.get("status") or "Unavailable")
        if product_status not in {"Available", "Incomplete", "Stale"}:
            return _range_empty_response(
                request,
                availability_state="UNAVAILABLE",
                status=product_status.upper(),
                warnings=[f"SYNTHETIC_PRODUCT_{product_status.upper()}"],
                evidence_class="SYNTHETIC",
            )
        all_observations = [
            {
                "timestamp": canonical_utc(int(row["timestamp"])),
                "close_timestamp": canonical_utc(int(row["close_time_utc"])),
                "open": row["open"], "high": row["high"],
                "low": row["low"], "close": row["close"],
                "volume": row["volume"],
            }
            for row in rows
        ]
        observations = _bounded_observations(all_observations, start, end, as_of)
        revision = f"synthetic:{int(product['synthetic_revision'])}"
        return _range_available_response(
            request,
            observations=observations,
            all_observations=all_observations,
            start=start,
            end=end,
            as_of=as_of,
            authority_kind="FRAGARACH_II_SYNTHETIC",
            authority_revision=revision,
            source_receipt={
                "authority_kind": "FRAGARACH_II_SYNTHETIC",
                "authority_revision": revision,
                "source_lineage": product["complete_lineage"],
            },
            evidence_class="SYNTHETIC",
            additional_warnings=(
                [] if product_status == "Available"
                else [f"SYNTHETIC_PRODUCT_{product_status.upper()}"]
            ),
        )

    def _get_synthetic_history(
        self, symbol: str, timeframe: str, *, consumer: str | None,
        evidence_requirement: str,
    ) -> dict[str, object]:
        requirement = evidence_requirement.strip().upper()
        if requirement != "SYNTHETIC_PERMITTED":
            return _unavailable(
                "SYNTHETIC_NOT_PERMITTED", symbol, timeframe,
                f"{symbol}:{timeframe} is derived evidence; "
                "the consumer must request SYNTHETIC_PERMITTED",
            )
        if not consumer:
            raise ExternalConsumerServiceError(
                "CONSUMER_REQUIRED",
                "consumer identity is required for synthetic history",
            )
        connection = open_read_only(self.database_path)
        try:
            canonical_symbol = _registered_symbol(connection, symbol, "D1")
            if canonical_symbol is None:
                return _unavailable(
                    "NOT_REGISTERED", symbol, timeframe,
                    f"{symbol}:{timeframe} is not registered",
                )
            asset_class = str(connection.execute(
                """SELECT asset_class FROM instrument_registrations
                   WHERE asset=? AND timeframe='D1'""",
                (canonical_symbol,),
            ).fetchone()[0])
        finally:
            connection.close()
        from .commissioning_authority import canonical_market
        if canonical_market(asset_class) == "STOCKS":
            return _unavailable(
                "INTENTIONALLY_DEFERRED", canonical_symbol, timeframe,
                "Stock intraday authority is intentionally deferred",
            )
        from .synthetic_repository import (
            SyntheticConsumerService, SyntheticRepository,
            SyntheticRepositoryError,
        )
        try:
            product = SyntheticConsumerService(
                SyntheticRepository(self.database_path)
            ).get_product(
                symbol=canonical_symbol, timeframe=timeframe,
                consumer=consumer, evidence_requirement=requirement,
                include_provenance=False,
            )
        except SyntheticRepositoryError as error:
            raise ExternalConsumerServiceError(error.code, str(error)) from error
        rows = product.get("observations") or []
        if product.get("status") not in {"Available", "Incomplete"} or not rows:
            return _unavailable(
                str(product.get("status") or "NO_HISTORY").upper(),
                canonical_symbol, timeframe,
                f"{canonical_symbol}:{timeframe} derived history is unavailable",
            )
        authority = "AMBER"
        reason = (
            "Derived M15 contains only complete M5 triplets; incomplete "
            "historical buckets remain unpublished"
            if product.get("status") == "Incomplete" else
            "Governed synthetic evidence derived from immutable M5"
        )
        return {
            "contract": INTRADAY_CONTRACT,
            "lane_status_contract": lane_status_contract(),
            "status": "AVAILABLE",
            "authority": authority,
            "lane_status": "AMBER",
            "reason": reason,
            "truth_score": None,
            "CAODT": _iso_utc(rows[-1]["timestamp"]),
            "symbol": canonical_symbol,
            "timeframe": timeframe,
            "evidence_class": "SYNTHETIC",
            "source_lineage": product.get("source_lineage") or [],
            "synthetic_revision": product.get("synthetic_revision"),
            "first_bar": _iso_utc(rows[0]["timestamp"]),
            "last_bar": _iso_utc(rows[-1]["timestamp"]),
            "bar_count": len(rows),
            "bars": [
                {
                    "timestamp": row["timestamp"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                }
                for row in rows
            ],
        }

    def list_histories(
        self, *, consumer: str | None = None,
        evidence_requirement: str = "REAL_ONLY",
        timeframes: tuple[str, ...] | None = None,
    ) -> dict[str, object]:
        requested = {
            str(value).strip().upper() for value in timeframes
        } if timeframes else set(SUPPORTED_TIMEFRAMES)
        direct = tuple(
            value for value in ("D1", "H1", "M30", "M15", "M5")
            if value in requested
        )
        lanes = []
        if direct:
            placeholders = ",".join("?" for _ in direct)
            connection = open_read_only(self.database_path)
            try:
                lanes = connection.execute(
                    f"""
                    SELECT asset,timeframe,count(*),min(open_time_utc),max(open_time_utc)
                    FROM bars
                    WHERE timeframe IN ({placeholders})
                    GROUP BY asset,timeframe
                    ORDER BY asset,timeframe
                    """,
                    direct,
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
                    "authority": _legacy_consumer_authority(str(truth["authority_state"])),
                    "lane_status": truth["authority_state"],
                    "truth_score": truth["truth_score"],
                    "CAODT": truth["caodt"],
                    "first_bar": _iso_utc(earliest),
                    "last_bar": _iso_utc(latest),
                    "bar_count": count,
                }
            )
        if (
            "M15" in requested
            and
            evidence_requirement.strip().upper() == "SYNTHETIC_PERMITTED"
            and consumer
        ):
            from .synthetic_repository import SyntheticRepository
            repository = SyntheticRepository(self.database_path)
            repository.activate_registry(generate_on_activation=False)
            for product in repository.list_products(refresh_status=False):
                if (
                    product["target_timeframe"] != "M15"
                    or consumer not in product["authorised_consumers"]
                    or product["status"] not in {
                        "Available", "Incomplete", "Stale",
                    }
                    or not product["observation_count"]
                    or any(
                        item["symbol"] == product["symbol"] and item["timeframe"] == "M15"
                        for item in histories
                    )
                ):
                    continue
                histories.append({
                    "symbol": product["symbol"],
                    "timeframe": "M15",
                    "authority": "AMBER",
                    "lane_status": "AMBER",
                    "truth_score": None,
                    "CAODT": _iso_utc(
                        product["latest_synthetic_observation"]
                    ),
                    "first_bar": _iso_utc(
                        product["first_synthetic_observation"]
                    ),
                    "last_bar": _iso_utc(
                        product["latest_synthetic_observation"]
                    ),
                    "bar_count": product["observation_count"],
                    "evidence_class": "SYNTHETIC",
                    "synthetic_revision": product["synthetic_revision"],
                })
        histories.sort(key=lambda item: (item["symbol"], item["timeframe"]))
        if timeframes is None:
            from .estate_truth_service import estate_truth_state
            capabilities = estate_truth_state(
                self.database_path
            )["timeframe_capabilities"]
        else:
            capabilities = {}
        return {
            "contract": CATALOG_CONTRACT,
            "lane_status_contract": lane_status_contract(),
            "status": "AVAILABLE",
            "histories": histories,
            "capabilities": capabilities,
        }

    def _has_direct_history(self, symbol: str, timeframe: str) -> bool:
        connection = open_read_only(self.database_path)
        try:
            return connection.execute(
                "SELECT 1 FROM bars WHERE asset=? AND timeframe=? LIMIT 1",
                (symbol.strip().upper(), timeframe.strip().upper()),
            ).fetchone() is not None
        finally:
            connection.close()

    def get_catalogue(self) -> dict[str, object]:
        """Project registration, lifecycle and canonical D1 availability once."""

        # A single read transaction gives this response one SQLite snapshot.
        connection = open_read_only(self.database_path)
        try:
            connection.execute("BEGIN")
            registrations = connection.execute(
                """
                SELECT asset,asset_class,instrument_type,registration_status,
                       registered_at_utc,provider_id
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
        from .storage.instrument_profiles import instrument_profile

        for asset, asset_class, instrument_type, registration_status, registered_at, provider_id in registrations:
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
            profile = instrument_profile(self.database_path, symbol)
            item = {
                "symbol": symbol,
                "market": market,
                "asset_class": str(asset_class),
                "instrument_type": str(instrument_type),
                "lifecycle": lifecycle_state if not active else "ACTIVE",
                "availability": availability,
                "profile": profile,
                "histories": [{
                    "timeframe": "D1",
                    "governed": d1_governed,
                    "eligible_for_morphix": morphix_ready,
                    "morphix_eligibility_reason": morphix_reason,
                    "minimum_required_bar_count": D1_MORPHIX_MIN_OBSERVATIONS,
                    "bar_count": bars,
                    "first_bar": profile["history"]["start_utc"],
                    "last_bar": profile["history"]["end_utc"],
                }],
            }
            symbols.append(item)
            revision_facts.append({
                "symbol": symbol, "market": market, "lifecycle": item["lifecycle"],
                "availability": availability, "d1_governed": d1_governed,
                "registered_at": registered_at, "bar_count": bars,
                "eligible_for_morphix": morphix_ready,
                "morphix_eligibility_reason": morphix_reason,
                "profile": profile,
            })
        revision = "sha256:" + hashlib.sha256(
            json.dumps(revision_facts, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "contract": ESTATE_CATALOGUE_CONTRACT,
            "lane_status_contract": lane_status_contract(),
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
        "lane_status_contract": lane_status_contract(),
        "status": status,
        "authority": None,
        "lane_status": None,
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


def _legacy_consumer_authority(lane_status: str) -> str:
    """Keep v1 consumers that accept only GREEN compatible with Gold lanes."""

    return "GREEN" if lane_status == "GOLD" else lane_status


def _iso_utc(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, UTC).isoformat()


def _range_request_fields(
    identity: str,
    consumer: str,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    as_of: datetime,
) -> dict[str, object]:
    return {
        "contract": HISTORY_RANGE_CONTRACT_VERSION,
        "contract_version": HISTORY_RANGE_CONTRACT_VERSION,
        "lane_status_contract": lane_status_contract(),
        "request_identity": identity,
        "request_id": identity,
        "consumer_identity": consumer,
        "consumer": consumer,
        "symbol": symbol,
        "timeframe": timeframe,
        "requested_start_utc": canonical_utc(start),
        "requested_end_utc_exclusive": canonical_utc(end),
        "as_of_utc": canonical_utc(as_of),
        "requested_range": {
            "start_utc": canonical_utc(start),
            "end_utc_exclusive": canonical_utc(end),
            "as_of_utc": canonical_utc(as_of),
        },
    }


def _range_empty_response(
    request: dict[str, object],
    *,
    availability_state: str,
    status: str,
    warnings: list[str],
    evidence_class: str = "UNKNOWN",
) -> dict[str, object]:
    fingerprint = ordered_range_fingerprint(
        str(request["symbol"]), str(request["timeframe"]), []
    )
    return {
        **request,
        "availability_state": availability_state,
        "status": status,
        "effective_range": {
            "state": "EMPTY",
            "start_utc": None,
            "end_utc_exclusive": None,
        },
        "observations": [],
        "observation_count": 0,
        "final_completed_observation_time": "NO_COMPLETED_OBSERVATION",
        "CAODT": "NO_CANONICAL_AS_OF_DATA_TIME",
        "authority_kind": "UNAVAILABLE",
        "authority_revision": "UNAVAILABLE",
        "authority": {"kind": "UNAVAILABLE", "revision": "UNAVAILABLE"},
        "ordered_range_fingerprint": fingerprint,
        "source_receipt": {"state": "UNAVAILABLE", "reason": status},
        "evidence_class": evidence_class,
        "data_quality_warnings": list(warnings),
        "warnings": list(warnings),
        "coverage": {"state": availability_state, "reasons": list(warnings)},
        "truncation": {"state": "NOT_APPLICABLE", "reasons": []},
        "partial_coverage": False,
        "truncated": False,
    }


def _history_bar(row: object) -> dict[str, object]:
    value = {
        "timestamp": row[0], "open": row[1], "high": row[2],
        "low": row[3], "close": row[4], "volume": row[5],
    }
    if len(row) > 6 and row[6] is not None:
        value.update({
            "tick_activity": row[6],
            "tick_activity_source": row[9],
            "tick_activity_provider_symbol": row[10],
            "broker_reported_volume": row[7],
            "mt5_spread": row[8],
        })
    return value


def _direct_observation(
    row,
    *,
    timeframe: str,
    asset_class: str,
    calendar_id: str | None,
    exchange_name: str | None,
    symbol: str,
) -> dict[str, object]:
    opened = int(row[0])
    completed = row[1]
    if completed is None:
        if timeframe == "D1":
            from .calendars import CalendarRegistry
            from .lane_commissioning import resolved_calendar_id
            from .operational_schedule import session_close_at

            resolved = resolved_calendar_id(
                asset_class=asset_class,
                calendar_id=calendar_id,
                exchange_name=exchange_name,
                canonical_symbol=symbol,
            )
            if not resolved:
                raise RuntimeError("D1 calendar is not configured")
            definition = CalendarRegistry(
                load_symbol_assignments=False
            ).calendar_by_id(resolved)
            owner_date = datetime.fromtimestamp(opened, UTC).date()
            completed = int(session_close_at(owner_date, definition).timestamp())
        else:
            from .validation.intraday_profiles import DURATIONS

            seconds = DURATIONS.get(timeframe)
            if seconds is None:
                raise ValueError(f"unsupported completion rule: {timeframe}")
            completed = opened + seconds
    result = {
        "timestamp": canonical_utc(opened),
        "close_timestamp": canonical_utc(int(completed)),
        "open": row[2],
        "high": row[3],
        "low": row[4],
        "close": row[5],
        "volume": row[6],
    }
    if len(row) > 7 and row[7] is not None:
        result.update({
            "tick_activity": row[7],
            "tick_activity_source": row[10],
            "tick_activity_provider_symbol": row[11],
            "broker_reported_volume": row[8],
            "mt5_spread": row[9],
        })
    return result


def _bounded_observations(
    observations: list[dict[str, object]],
    start: datetime,
    end: datetime,
    as_of: datetime,
) -> list[dict[str, object]]:
    start_epoch = int(start.timestamp())
    end_epoch = int(end.timestamp())
    as_of_epoch = int(as_of.timestamp())
    return [
        row for row in observations
        if start_epoch <= int(
            datetime.fromisoformat(str(row["timestamp"])).timestamp()
        ) < end_epoch
        and int(
            datetime.fromisoformat(str(row["close_timestamp"])).timestamp()
        ) <= end_epoch
        and int(
            datetime.fromisoformat(str(row["close_timestamp"])).timestamp()
        ) <= as_of_epoch
    ]


def _range_available_response(
    request: dict[str, object],
    *,
    observations: list[dict[str, object]],
    all_observations: list[dict[str, object]],
    start: datetime,
    end: datetime,
    as_of: datetime,
    authority_kind: str,
    authority_revision: str,
    source_receipt: dict[str, object],
    evidence_class: str,
    additional_warnings: list[str] | None = None,
) -> dict[str, object]:
    warnings = list(additional_warnings or [])
    truncation_reasons: list[str] = []
    if as_of < end:
        truncation_reasons.append("TRUNCATED_BY_AS_OF")
    if all_observations:
        first_available = datetime.fromisoformat(
            str(all_observations[0]["timestamp"])
        )
        if first_available > start:
            truncation_reasons.append("REQUESTED_START_PRECEDES_AVAILABLE_HISTORY")
        incomplete_in_window = any(
            start <= datetime.fromisoformat(str(row["timestamp"])) < end
            and datetime.fromisoformat(str(row["close_timestamp"])) > min(end, as_of)
            for row in all_observations
        )
        if incomplete_in_window:
            truncation_reasons.append("INCOMPLETE_OBSERVATIONS_EXCLUDED")
    warnings.extend(value for value in truncation_reasons if value not in warnings)
    partial = bool(observations and truncation_reasons)
    availability = "PARTIAL" if partial else "AVAILABLE" if observations else "EMPTY"
    status = availability
    fingerprint = ordered_range_fingerprint(
        str(request["symbol"]), str(request["timeframe"]), observations
    )
    return {
        **request,
        "availability_state": availability,
        "status": status,
        "effective_range": {
            "state": availability,
            "start_utc": observations[0]["timestamp"] if observations else None,
            "end_utc_exclusive": (
                observations[-1]["close_timestamp"] if observations else None
            ),
        },
        "observations": observations,
        "observation_count": len(observations),
        "final_completed_observation_time": (
            observations[-1]["close_timestamp"]
            if observations else "NO_COMPLETED_OBSERVATION"
        ),
        "CAODT": (
            observations[-1]["timestamp"]
            if observations else "NO_CANONICAL_AS_OF_DATA_TIME"
        ),
        "authority_kind": authority_kind,
        "authority_revision": authority_revision,
        "authority": {"kind": authority_kind, "revision": authority_revision},
        "ordered_range_fingerprint": fingerprint,
        "source_receipt": source_receipt,
        "evidence_class": evidence_class,
        "data_quality_warnings": list(warnings),
        "warnings": list(warnings),
        "coverage": {"state": availability, "reasons": list(truncation_reasons)},
        "truncation": {
            "state": "TRUNCATED" if truncation_reasons else "NOT_TRUNCATED",
            "reasons": list(truncation_reasons),
        },
        "partial_coverage": partial,
        "truncated": bool(truncation_reasons),
    }
