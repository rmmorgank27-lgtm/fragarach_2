"""Bounded Twelve Data acquisition followed by the one canonical pipeline."""

from __future__ import annotations

import http.client
import json
import socket
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass,replace
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode

from fragarach_ii.ingestion import RawEvidence, ingest_staged_batch
from fragarach_ii.ingestion.pipeline import IngestionResult
from fragarach_ii.storage import open_read_only, registered_writer, transaction, registration_for_lane, RegistrationError, initialize_database
from fragarach_ii.validation import validate_lane
from .post_ingest_validation import persist_committed_lane_validation
from fragarach_ii.validation.price_outliers import find_extreme_price_outliers
from fragarach_ii.staging import StagingBatch, StagingRejection
from fragarach_ii.fx_orientation import validate_direct_mapping
from fragarach_ii.retirement import is_permanently_removed,is_retired
from fragarach_ii.credentials import CredentialAuthority, CredentialState
from fragarach_ii.twelve_data_credit import authority_for_credential, endpoint_credit_cost

from .config import ProviderConfig, ProviderConfigurationError, load_provider_config
from .http import (
    BoundedHttpsTransport,
    HttpRequest,
    HttpResponse,
    HttpTransport,
    ResponseTooLarge,
)
from .twelve_data_adapter import (
    ProviderPayloadError,
    evidence_identity,
    stage_twelve_data_response,
)


Clock = Callable[[], datetime]
Sleeper = Callable[[float], None]


class AcquisitionError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, evidence_committed: bool = False,
        http_status: int | None = None, response_body: bytes | None = None,
        retry_after: str | None = None,
    ) -> None:
        self.code = code
        self.evidence_committed = evidence_committed
        self.http_status = http_status
        self.response_body = response_body
        self.retry_after = retry_after
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    provider_id: str
    provider_contract: str
    configuration_checksum: str
    asset: str
    timeframe: str
    provider_symbol: str
    from_date: str
    through_date: str
    actual_range: str
    request_target: str
    response_count: int
    response_checksums: tuple[str, ...]
    response_bytes: int
    received: int
    staged: int
    inserted: int
    unchanged: int
    conflicts_preserved: int
    corrected: int
    rejected: int
    ingest_run_id: str
    ingest_state: str
    raw_block_id: str
    raw_block_reused: bool
    canonical_high_watermark: str | None
    validation_calendar_id: str
    validation_boundary: str
    validation_expected: int
    validation_present_expected: int
    validation_missing_expected: int
    validation_outside_expected: int
    validation_result_checksum: str
    read_only_verification: bool
    sqlite_write: dict[str, object]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))


def acquire_twelve_data(
    database_path: str | Path,
    *,
    asset: str,
    timeframe: str,
    from_date: str,
    through_date: str,
    merge_mode: str = "preserve",
    credential: str | None,
    transport: HttpTransport | None = None,
    config_root: str | Path | None = None,
    clock: Clock | None = None,
    sleeper: Sleeper = time.sleep,
    before_ingest: Callable[[], None] | None = None,
    validator: Callable[..., object] = validate_lane,
    provider_symbol_override: str | None = None,
    mapping_class: str | None = None,
    defer_validation: bool = False,
    allow_empty: bool = False,
    progress: Callable[[str], None] | None = None,
    credit_authority_managed: bool = False,
) -> AcquisitionResult:
    normalized_asset = asset.strip().upper()
    normalized_timeframe = timeframe.strip().upper()
    if is_permanently_removed(database_path,normalized_asset,normalized_timeframe):
        raise AcquisitionError("INSTRUMENT_REMOVED",f"{normalized_asset}:{normalized_timeframe}")
    if is_retired(database_path,normalized_asset,normalized_timeframe):
        raise AcquisitionError("INSTRUMENT_RETIRED",f"{normalized_asset}:{normalized_timeframe}")
    if not credential:
        raise AcquisitionError("MISSING_CREDENTIAL", "required provider credential is absent")
    if normalized_timeframe not in {"D1","H1","M30","M5"}:raise AcquisitionError("UNSUPPORTED_TIMEFRAME",normalized_timeframe)
    if merge_mode not in {"preserve", "correct"}:
        raise AcquisitionError("INVALID_MERGE_MODE", "merge mode must be preserve or correct")
    start = _date(from_date, "INVALID_FROM_DATE")
    end = _date(through_date, "INVALID_THROUGH_DATE")
    if end < start:
        raise AcquisitionError("INVALID_BOUNDARY", "through_date precedes from_date")
    try:
        config = load_provider_config(config_root,normalized_timeframe)
        initialize_database(database_path)
        registration = registration_for_lane(database_path, normalized_asset, normalized_timeframe)
        asset_class=normalized_asset_class(database_path,normalized_asset,normalized_timeframe)
        provider_timezone = _provider_timezone(
            asset_class, normalized_timeframe, config.timezone
        )
        config = replace(config, timezone=provider_timezone)
        if provider_symbol_override:
            provider_symbol = provider_symbol_override
        else:
            if registration[0] != config.provider_id or (normalized_timeframe=="D1" and registration[1] != config.provider_contract):
                raise ProviderConfigurationError("registered provider contract mismatch")
            provider_symbol = registration[2]
        if normalized_asset_class(database_path,normalized_asset,normalized_timeframe)=="FX":
            if provider_symbol_override:
                expected=f"{normalized_asset[:3]}/{normalized_asset[3:]}"
                if provider_symbol != expected:raise AcquisitionError("PROVIDER_ORIENTATION_MISMATCH",f"expected exact direct symbol {expected}")
            else:
                try:validate_direct_mapping(normalized_asset,registration[0],provider_symbol)
                except ValueError as error:raise AcquisitionError("PROVIDER_ORIENTATION_MISMATCH",str(error)) from error
    except (ProviderConfigurationError, RegistrationError) as error:
        raise AcquisitionError("PROVIDER_CONFIGURATION_ERROR", str(error)) from error
    days = (end - start).days + 1
    bars_per_day={"D1":1,"H1":24,"M30":48,"M5":288}[normalized_timeframe]
    outputsize=days*bars_per_day
    if days > config.max_calendar_days or outputsize>config.request_ceiling:
        raise AcquisitionError(
            "RANGE_TOO_LARGE",
            "request exceeds the 4,000-bar reviewed request ceiling",
        )
    request = _request(config, provider_symbol, start, end)
    authority = None if credit_authority_managed else authority_for_credential(
        credential, clock=clock, sleeper=sleeper
    )
    response = _acquire_response(
        transport or BoundedHttpsTransport(), request, credential, config, sleeper,
        authority=authority, endpoint="time_series",
    )
    _record_authority_response(credential, CredentialState.AVAILABLE, "Twelve Data HTTP response", "Accepted", response.status)
    if progress:progress("validating")
    received_at = (clock or (lambda: datetime.now(UTC)))().astimezone(UTC).isoformat()
    raw_block_id, checksum = evidence_identity(response.body)
    try:
        batch = stage_twelve_data_response(
            response.body,
            asset=normalized_asset,
            provider_symbol=provider_symbol,
            from_date=start,
            through_date=end,
            raw_block_id=raw_block_id,
            received_at=received_at,
            timeframe=normalized_timeframe,asset_class=asset_class,observed_at=datetime.fromisoformat(received_at),
            allow_empty=allow_empty,
        )
        batch = _quarantine_extreme_price_outliers(
            database_path, batch=batch, asset_class=asset_class
        )
    except ProviderPayloadError as error:
        if error.code == "AUTHENTICATION_FAILED":
            _record_authority_response(credential, CredentialState.INVALID, "Twelve Data response payload", "Authentication Failed", response.status)
        raise AcquisitionError(
            error.code, str(error), http_status=response.status, response_body=response.body
        ) from error
    if before_ingest is not None:
        before_ingest()
    if progress:progress("ingesting")
    evidence = RawEvidence(
        raw_block_id=raw_block_id,
        checksum=checksum,
        payload=response.body,
        source_name=f"{config.provider_contract}:{normalized_asset}:{from_date}:{through_date}",
        source_locator=f"{config.base_url}{config.endpoint_path}",
        media_type="application/json",
        received_at=received_at,
    )
    ingestion = ingest_staged_batch(
        database_path,
        batch=batch,
        evidence=evidence,
        run_kind="provider_acquisition",
        merge_mode=merge_mode,
        outcome_facts={
            "asset": normalized_asset,
            "checksum": checksum,
            "configuration_checksum": config.configuration_checksum,
            "provider_contract_checksum": config.contract_checksum,
            "from_date": from_date,
            "merge_mode": merge_mode,
            "provider": config.provider_id,
            "provider_contract": config.provider_contract,
            "provider_symbol": provider_symbol,
            "mapping_state": "CONFIRMED_BY_VALID_EVIDENCE",
            "mapping_class": mapping_class or "EXACT_REPRESENTATION",
            "response_bytes": len(response.body),
            "through_date": through_date,
            "timeframe": normalized_timeframe,
        },
        preserve_rejected_evidence=True,
    )
    if batch.source_rows and not batch.bars:
        rejection_codes = {item.code for item in batch.rejections}
        if normalized_timeframe == "D1" and rejection_codes == {"OUT_OF_RANGE_OBSERVATION"}:
            # Daily FX and metals aggregates can roll their label before the
            # completed session is queryable during a busy provider window.
            # The immutable packet remains recorded, but it must be routed as
            # transient so the Scheduler can use an approved fallback or retry
            # the exact governed boundary after a short delay.
            raise AcquisitionError(
                "PROVIDER_D1_NOT_READY",
                f"{config.provider_id} returned only observations outside "
                f"the completed D1 window {from_date}..{through_date}",
                response_body=response.body,
            )
        raise AcquisitionError(
            "NO_USABLE_OBSERVATIONS",
            f"{config.provider_id} returned no admissible observations",
            response_body=response.body,
        )
    validation = None
    if not defer_validation and batch.bars:
        try:
            validation = persist_committed_lane_validation(
                database_path,
                asset=normalized_asset,
                timeframe=normalized_timeframe,
                through_date=through_date,
                clock=clock,
                canonical_inserts=ingestion.inserted,
                canonical_corrections=ingestion.corrected,
                validator=validator,
            )
        except BaseException as error:
            _clear_validation_summary(database_path, normalized_asset, normalized_timeframe)
            raise AcquisitionError(
                "POST_INGEST_VALIDATION_FAILED",
                f"evidence committed but validation failed: {type(error).__name__}",
                evidence_committed=True,
            ) from error
    verified = _verify_committed(
        database_path, ingestion, response.body, len(batch.bars), normalized_asset,normalized_timeframe,
        require_validation=not defer_validation and bool(batch.bars),
    )
    validation_data = validation.as_dict() if validation is not None else {}  # type: ignore[attr-defined]
    return AcquisitionResult(
        provider_id=config.provider_id,
        provider_contract=config.provider_contract,
        configuration_checksum=config.configuration_checksum,
        asset=normalized_asset,
        timeframe=normalized_timeframe,
        provider_symbol=provider_symbol,
        from_date=from_date,
        through_date=through_date,
        actual_range=(f"{datetime.fromtimestamp(batch.bars[0].timestamp,UTC).date().isoformat()} → {datetime.fromtimestamp(batch.bars[-1].timestamp,UTC).date().isoformat()}" if batch.bars else "No returned bars"),
        request_target=request.target,
        response_count=1,
        response_checksums=(checksum,),
        response_bytes=len(response.body),
        received=batch.source_rows,
        staged=len(batch.bars),
        inserted=ingestion.inserted,
        unchanged=ingestion.unchanged,
        conflicts_preserved=ingestion.conflicts_preserved,
        corrected=ingestion.corrected,
        rejected=ingestion.rejected,
        ingest_run_id=ingestion.ingest_run_id,
        ingest_state=ingestion.transaction_state,
        raw_block_id=ingestion.raw_block_id,
        raw_block_reused=ingestion.raw_block_reused,
        canonical_high_watermark=ingestion.latest,
        validation_calendar_id=validation_data.get("calendar_id","DEFERRED"),
        validation_boundary=validation_data.get("through_date",validation_data.get("boundary_utc",through_date)),
        validation_expected=validation_data.get("expected_session_count",validation_data.get("expected_interval_count",0)),
        validation_present_expected=validation_data.get("present_expected_session_count",validation_data.get("present_expected_interval_count",0)),
        validation_missing_expected=validation_data.get("missing_expected_session_count",validation_data.get("missing_expected_interval_count",0)),
        validation_outside_expected=validation_data.get("outside_expected_session_count",validation_data.get("outside_expected_interval_count",0)),
        validation_result_checksum=validation_data.get("result_checksum","DEFERRED"),
        read_only_verification=verified,
        sqlite_write=ingestion.sqlite_write,
        warnings=(f"{len(batch.rejections)} row-local provider observation(s) quarantined; valid observations were preserved.",) if batch.rejections else (),
    )

def normalized_asset_class(database_path,asset,timeframe):
    connection=open_read_only(database_path)
    try:
        row=connection.execute("SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",(asset,)).fetchone()
        return row[0] if row else None
    finally:connection.close()


def _provider_timezone(asset_class: str | None, timeframe: str, configured: str) -> str:
    """Return the provider label timezone for the governed market session."""
    if asset_class == "CRYPTO":
        return "UTC"
    if timeframe != "D1" or asset_class == "US_EQUITIES":
        return "America/New_York"
    return configured


def _request(
    config: ProviderConfig,
    symbol: str,
    start: date,
    end: date,
    outputsize: int | None = None,
) -> HttpRequest:
    parameters = [
        ("format", "JSON"),
        ("interval", config.interval),
        ("order", config.order),
    ]
    if config.interval == "1day":
        # Date-only end bounds are material here. Twelve Data has been
        # observed returning the currently forming FX day for both its `date`
        # selector and an end-of-day timestamp. A date-only end bound plus an
        # explicit bounded output size returns the requested completed day.
        if start != end:
            parameters.append(("start_date", start.isoformat()))
        parameters.extend((
            ("end_date", end.isoformat()),
            ("outputsize", str((end - start).days + 1)),
        ))
    else:
        parameters.extend((
            ("start_date", f"{start.isoformat()}T00:00:00"),
            ("end_date", f"{end.isoformat()}T23:59:59"),
        ))
    parameters.extend((("symbol", symbol), ("timezone", config.timezone)))
    return HttpRequest(
        host=config.provider_host,
        target=f"{config.endpoint_path}?{urlencode(parameters)}",
        user_agent=config.user_agent,
    )


def _acquire_response(
    transport: HttpTransport,
    request: HttpRequest,
    credential: str,
    config: ProviderConfig,
    sleeper: Sleeper,
    *,
    authority=None,
    endpoint: str = "time_series",
) -> HttpResponse:
    if authority is not None:
        reservation = authority.reserve(endpoint_credit_cost(endpoint), endpoint=endpoint)
        if not reservation["eligible"]:
            raise AcquisitionError(
                "TWELVEDATA_CREDIT_WINDOW_EXHAUSTED",
                f"Twelve Data credit window unavailable until {reservation.get('next_available')}",
            )
        authority.dispatch(str(reservation["reservation_id"]), endpoint_credit_cost(endpoint))
    try:
        response = transport.send(request, credential, config)
    except ResponseTooLarge as error:
        raise AcquisitionError("TWELVEDATA_INVALID_RESPONSE", str(error)) from error
    except (TimeoutError, socket.timeout, OSError, http.client.HTTPException) as error:
        raise AcquisitionError("TWELVEDATA_TRANSPORT_FAILURE", str(error)) from error
    if response.host != config.provider_host:
        raise AcquisitionError("TWELVEDATA_INVALID_RESPONSE", "response host is not configured provider")
    if response.status == 429:
        retry_after = response.header("retry-after")
        if authority is not None:
            authority.record_429(
                response_body=response.body, retry_after=retry_after, endpoint=endpoint,
            )
        raise AcquisitionError(
            "TWELVEDATA_RATE_LIMIT_429", "Twelve Data HTTP 429",
            http_status=429, response_body=response.body, retry_after=retry_after,
        )
    if response.status >= 500:
        raise AcquisitionError(
            "TWELVEDATA_UPSTREAM_5XX", f"Twelve Data HTTP {response.status}",
            http_status=response.status, response_body=response.body,
        )
    if 300 <= response.status < 400:
        raise AcquisitionError(
            "TWELVEDATA_INVALID_RESPONSE", "provider redirect is not accepted",
            http_status=response.status, response_body=response.body,
        )
    if response.status in {401, 403}:
        _record_authority_response(credential, CredentialState.INVALID, "Twelve Data HTTP response", "Authentication Failed", response.status)
        raise AcquisitionError(
            "AUTHENTICATION_FAILED", f"Twelve Data HTTP {response.status}",
            http_status=response.status, response_body=response.body,
        )
    if response.status != 200:
        raise AcquisitionError(
            "TWELVEDATA_INVALID_RESPONSE", f"provider HTTP status {response.status}",
            http_status=response.status, response_body=response.body,
        )
    media_type = response.content_type.split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise AcquisitionError(
            "TWELVEDATA_INVALID_RESPONSE", "provider response is not JSON",
            http_status=response.status, response_body=response.body,
        )
    if len(response.body) > config.max_response_bytes:
        raise AcquisitionError(
            "TWELVEDATA_INVALID_RESPONSE", "response exceeds configured byte limit",
            http_status=response.status, response_body=response.body,
        )
    return response


def _record_authority_response(
    credential: str,
    state: CredentialState,
    source: str,
    provider_response_state: str,
    response_code: int,
) -> None:
    """Update authority metadata only when the request used its canonical key."""
    authority = CredentialAuthority()
    current = authority.resolve("TWELVE_DATA")
    if current.credential != credential:
        return
    try:
        authority.record_validation(
            "TWELVE_DATA", credential_state=state, validation_source=source,
            provider_response_state=provider_response_state,
            provider_response_code=response_code,
        )
    except OSError:
        # Provider response remains factual even if non-secret metadata cannot persist.
        pass


def _verify_committed(
    database_path: str | Path,
    ingestion: IngestionResult,
    body: bytes,
    staged_count: int,
    asset: str,
    timeframe: str,
    *,
    require_validation: bool = True,
) -> bool:
    """Verify the atomic receipt without rescanning immutable provenance.

    ``ingest_runs`` and its per-action counts are committed in the same SQLite
    transaction as provenance.  Counting provenance by ``ingest_run_id`` was
    both redundant and unindexed; on the production authority it scanned 5.8
    million historical events after every packet.  The keyed receipt and raw
    block lookups prove the same committed transaction while keeping routine
    boundary admission proportional to the new packet.
    """
    connection = open_read_only(database_path)
    try:
        raw = connection.execute(
            "SELECT payload,byte_length FROM raw_blocks WHERE raw_block_id=?",
            (ingestion.raw_block_id,),
        ).fetchone()
        run = connection.execute(
            "SELECT status,raw_block_id,detail FROM ingest_runs WHERE ingest_run_id=?",
            (ingestion.ingest_run_id,),
        ).fetchone()
        lane = connection.execute(
            "SELECT validation_summary FROM lane_state WHERE asset=? AND timeframe=?",
            (asset,timeframe),
        ).fetchone()
        try:
            receipt = json.loads(run[2]) if run is not None else None
        except (json.JSONDecodeError, TypeError):
            receipt = None
        recorded_actions = (
            sum(int(receipt.get(key, 0) or 0) for key in (
                "inserted", "corrected", "unchanged", "conflicts_preserved",
            ))
            if isinstance(receipt, dict) else -1
        )
        recorded_staged = int(receipt.get("staged", -1)) if isinstance(receipt, dict) else -1
        committed_actions = (
            ingestion.inserted + ingestion.corrected + ingestion.unchanged
            + ingestion.conflicts_preserved
        )
        return (
            raw == (body, len(body))
            and run is not None
            and run[:2] == ("committed", ingestion.raw_block_id)
            and recorded_staged == staged_count
            and recorded_actions == committed_actions
            and (not require_validation or (lane is not None and lane[0] is not None))
        )
    finally:
        connection.close()


def _quarantine_extreme_price_outliers(
    database_path: str | Path, *, batch: StagingBatch, asset_class: str
) -> StagingBatch:
    """Keep statistically implausible FX D1 observations out of authority."""

    if asset_class != "FX" or not batch.bars or batch.bars[0].timeframe != "D1":
        return batch
    candidate_timestamps = {bar.timestamp for bar in batch.bars}
    first, last = min(candidate_timestamps), max(candidate_timestamps)
    reference: dict[int, tuple[int, str, str, str, str]] = {}
    if Path(database_path).expanduser().exists():
        connection = open_read_only(database_path)
        try:
            rows = connection.execute(
                """SELECT open_time_utc,open,high,low,close FROM bars
                   WHERE asset=? AND timeframe='D1'
                     AND open_time_utc BETWEEN ? AND ?
                   ORDER BY open_time_utc""",
                (batch.bars[0].symbol, first - 60 * 86_400, last + 60 * 86_400),
            ).fetchall()
        finally:
            connection.close()
        reference.update({int(row[0]): tuple(row) for row in rows})
    reference.update(
        {
            bar.timestamp: (bar.timestamp, bar.open, bar.high, bar.low, bar.close)
            for bar in batch.bars
        }
    )
    findings = find_extreme_price_outliers(
        reference.values(), candidate_timestamps=candidate_timestamps
    )
    if not findings:
        return batch
    by_timestamp = {finding.timestamp: finding for finding in findings}
    accepted = tuple(bar for bar in batch.bars if bar.timestamp not in by_timestamp)
    rejected = tuple(
        StagingRejection(
            bar.source_row_number,
            "EXTREME_PRICE_OUTLIER",
            (
                f"{by_timestamp[bar.timestamp].field}={by_timestamp[bar.timestamp].observed} "
                f"is an extreme local price outlier"
            ),
        )
        for bar in batch.bars
        if bar.timestamp in by_timestamp
    )
    return StagingBatch(
        bars=accepted,
        rejections=tuple((*batch.rejections, *rejected)),
        source_rows=batch.source_rows,
        duplicate_identical=batch.duplicate_identical,
        duplicate_conflicting=batch.duplicate_conflicting,
    )


def _clear_validation_summary(database_path: str | Path, asset: str, timeframe: str) -> None:
    with registered_writer(database_path) as connection:
        with transaction(connection):
            connection.execute(
                "UPDATE lane_state SET validation_summary=NULL WHERE asset=? AND timeframe=?",
                (asset, timeframe),
            )


def _date(value: str, code: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise AcquisitionError(code, f"invalid ISO date: {value}") from error
    if parsed.isoformat() != value:
        raise AcquisitionError(code, f"date is not canonical ISO text: {value}")
    return parsed
