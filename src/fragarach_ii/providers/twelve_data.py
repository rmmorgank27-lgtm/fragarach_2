"""Bounded Twelve Data acquisition followed by the one canonical pipeline."""

from __future__ import annotations

import http.client
import json
import socket
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode

from fragarach_ii.ingestion import RawEvidence, ingest_staged_batch
from fragarach_ii.ingestion.pipeline import IngestionResult
from fragarach_ii.storage import open_read_only, registered_writer, transaction, registration_for_lane, RegistrationError, initialize_database
from fragarach_ii.validation import validate_lane

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
    def __init__(self, code: str, message: str, *, evidence_committed: bool = False) -> None:
        self.code = code
        self.evidence_committed = evidence_committed
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
) -> AcquisitionResult:
    if not credential:
        raise AcquisitionError("MISSING_CREDENTIAL", "required provider credential is absent")
    normalized_asset = asset.strip().upper()
    normalized_timeframe = timeframe.strip().upper()
    if normalized_timeframe != "D1":
        raise AcquisitionError("UNSUPPORTED_TIMEFRAME", "provider contract supports D1 only")
    if merge_mode not in {"preserve", "correct"}:
        raise AcquisitionError("INVALID_MERGE_MODE", "merge mode must be preserve or correct")
    start = _date(from_date, "INVALID_FROM_DATE")
    end = _date(through_date, "INVALID_THROUGH_DATE")
    if end < start:
        raise AcquisitionError("INVALID_BOUNDARY", "through_date precedes from_date")
    try:
        config = load_provider_config(config_root)
        initialize_database(database_path)
        registration = registration_for_lane(database_path, normalized_asset, normalized_timeframe)
        if registration[0] != config.provider_id or registration[1] != config.provider_contract:
            raise ProviderConfigurationError("registered provider contract mismatch")
        provider_symbol = registration[2]
    except (ProviderConfigurationError, RegistrationError) as error:
        raise AcquisitionError("PROVIDER_CONFIGURATION_ERROR", str(error)) from error
    days = (end - start).days + 1
    if days > config.max_calendar_days:
        raise AcquisitionError(
            "RANGE_TOO_LARGE",
            f"request exceeds {config.max_calendar_days} calendar-day contract limit",
        )
    request = _request(config, provider_symbol, start, end, days)
    response = _acquire_response(
        transport or BoundedHttpsTransport(), request, credential, config, sleeper
    )
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
        )
    except ProviderPayloadError as error:
        raise AcquisitionError(error.code, str(error)) from error
    if before_ingest is not None:
        before_ingest()
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
            "from_date": from_date,
            "merge_mode": merge_mode,
            "provider": config.provider_id,
            "provider_contract": config.provider_contract,
            "provider_symbol": provider_symbol,
            "response_bytes": len(response.body),
            "through_date": through_date,
            "timeframe": normalized_timeframe,
        },
        preserve_rejected_evidence=False,
    )
    try:
        validation = validator(
            database_path,
            symbol=normalized_asset,
            timeframe=normalized_timeframe,
            through_date=through_date,
            persist=True,
            clock=clock,
        )
    except BaseException as error:
        _clear_validation_summary(database_path, normalized_asset, normalized_timeframe)
        raise AcquisitionError(
            "POST_INGEST_VALIDATION_FAILED",
            f"evidence committed but validation failed: {type(error).__name__}",
            evidence_committed=True,
        ) from error
    verified = _verify_committed(
        database_path, ingestion, response.body, len(batch.bars), normalized_asset
    )
    validation_data = validation.as_dict()  # type: ignore[attr-defined]
    return AcquisitionResult(
        provider_id=config.provider_id,
        provider_contract=config.provider_contract,
        configuration_checksum=config.configuration_checksum,
        asset=normalized_asset,
        timeframe=normalized_timeframe,
        provider_symbol=provider_symbol,
        from_date=from_date,
        through_date=through_date,
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
        validation_calendar_id=validation_data["calendar_id"],
        validation_boundary=validation_data["through_date"],
        validation_expected=validation_data["expected_session_count"],
        validation_present_expected=validation_data["present_expected_session_count"],
        validation_missing_expected=validation_data["missing_expected_session_count"],
        validation_outside_expected=validation_data["outside_expected_session_count"],
        validation_result_checksum=validation_data["result_checksum"],
        read_only_verification=verified,
    )


def _request(
    config: ProviderConfig,
    symbol: str,
    start: date,
    end: date,
    outputsize: int,
) -> HttpRequest:
    parameters = [
        ("end_date", end.isoformat()),
        ("format", "JSON"),
        ("interval", config.interval),
        ("order", config.order),
        ("outputsize", str(outputsize)),
        ("start_date", start.isoformat()),
        ("symbol", symbol),
        ("timezone", config.timezone),
    ]
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
) -> HttpResponse:
    retryable_statuses = {429, 500, 502, 503, 504}
    for attempt in range(config.max_attempts):
        try:
            response = transport.send(request, credential, config)
        except ResponseTooLarge as error:
            raise AcquisitionError("RESPONSE_TOO_LARGE", str(error)) from error
        except (TimeoutError, socket.timeout, OSError, http.client.HTTPException) as error:
            if attempt + 1 == config.max_attempts:
                raise AcquisitionError(
                    "RETRY_EXHAUSTED", f"transport failed after {config.max_attempts} attempts"
                ) from error
            sleeper(config.retry_backoff_seconds[attempt])
            continue
        if response.host != config.provider_host:
            raise AcquisitionError("UNEXPECTED_HOST", "response host is not configured provider")
        if 300 <= response.status < 400:
            raise AcquisitionError("UNEXPECTED_REDIRECT", "provider redirect is not accepted")
        if response.status in retryable_statuses:
            if attempt + 1 == config.max_attempts:
                code = "RATE_LIMIT" if response.status == 429 else "RETRY_EXHAUSTED"
                raise AcquisitionError(code, f"provider HTTP {response.status} after bounded retries")
            sleeper(config.retry_backoff_seconds[attempt])
            continue
        if response.status != 200:
            raise AcquisitionError("HTTP_ERROR", f"provider HTTP status {response.status}")
        media_type = response.content_type.split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            raise AcquisitionError("UNSUPPORTED_MEDIA_TYPE", "provider response is not JSON")
        if len(response.body) > config.max_response_bytes:
            raise AcquisitionError("RESPONSE_TOO_LARGE", "response exceeds configured byte limit")
        return response
    raise AssertionError("bounded retry loop did not terminate")


def _verify_committed(
    database_path: str | Path,
    ingestion: IngestionResult,
    body: bytes,
    staged_count: int,
    asset: str,
) -> bool:
    connection = open_read_only(database_path)
    try:
        raw = connection.execute(
            "SELECT payload,byte_length FROM raw_blocks WHERE raw_block_id=?",
            (ingestion.raw_block_id,),
        ).fetchone()
        run = connection.execute(
            "SELECT status,raw_block_id FROM ingest_runs WHERE ingest_run_id=?",
            (ingestion.ingest_run_id,),
        ).fetchone()
        provenance = connection.execute(
            "SELECT count(*) FROM provenance WHERE ingest_run_id=?",
            (ingestion.ingest_run_id,),
        ).fetchone()[0]
        lane = connection.execute(
            "SELECT validation_summary FROM lane_state WHERE asset=? AND timeframe='D1'",
            (asset,),
        ).fetchone()
        return (
            raw == (body, len(body))
            and run == ("committed", ingestion.raw_block_id)
            and provenance == staged_count
            and lane is not None
            and lane[0] is not None
        )
    finally:
        connection.close()


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
