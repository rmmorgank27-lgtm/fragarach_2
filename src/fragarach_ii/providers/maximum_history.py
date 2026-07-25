"""Provider-compliant maximum-available history acquisition."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from fragarach_ii.ingestion import RawEvidence, ingest_staged_batch
from fragarach_ii.staging import StagingBatch
from fragarach_ii.storage import initialize_database,open_read_only, registration_for_lane
from fragarach_ii.truth_engine import truth_state_for_lane
from fragarach_ii.validation import validate_lane

from .config import load_provider_config
from .http import BoundedHttpsTransport, HttpRequest, HttpTransport
from .twelve_data import (
    AcquisitionError,
    _acquire_response,
    acquire_twelve_data,
)
from .twelve_data_adapter import evidence_identity
from fragarach_ii.twelve_data_credit import authority_for_credential


Progress = Callable[[str], None]


def acquire_maximum_twelve_data(
    database_path: str | Path,
    *,
    asset: str,
    timeframe: str,
    through_date: str,
    merge_mode: str,
    credential: str | None,
    transport: HttpTransport | None = None,
    provider_symbol_override: str | None = None,
    progress: Progress | None = None,
    validator: Callable[..., object] = validate_lane,
) -> dict[str, object]:
    """Acquire newest-to-oldest until Twelve Data's factual boundary is reached."""
    normalized_asset=asset.strip().upper();normalized_timeframe=timeframe.strip().upper()
    end=date.fromisoformat(through_date);config=load_provider_config(timeframe=normalized_timeframe)
    if not credential:raise AcquisitionError("MISSING_CREDENTIAL","required provider credential is absent")
    initialize_database(database_path)
    registration=registration_for_lane(database_path,normalized_asset,normalized_timeframe)
    provider_symbol=provider_symbol_override or registration[2]
    if not provider_symbol:raise AcquisitionError("PROVIDER_CONFIGURATION_ERROR","provider symbol mapping required")
    network=transport or BoundedHttpsTransport()

    earliest, boundary_run_id = _discover_earliest(
        database_path, asset=normalized_asset, timeframe=normalized_timeframe,
        provider_symbol=provider_symbol, credential=credential, transport=network,
    )
    if earliest>end:raise AcquisitionError("EARLIEST_BOUNDARY_AFTER_REQUEST","provider earliest observation is after the latest completed boundary")
    bars_per_day={"D1":1,"H1":24,"M30":48,"M5":288}[normalized_timeframe]
    window_days=max(1,config.request_ceiling//bars_per_day)
    overlap_days=min(4,max(0,window_days-1))
    chunks=[];history_requests=0;termination_reason=""
    cursor=end
    while True:
        start=max(earliest or date.min,cursor-timedelta(days=window_days-1))
        if progress:progress("requesting" if history_requests==0 else "acquiring_earlier")
        result=acquire_twelve_data(
            database_path,asset=normalized_asset,timeframe=normalized_timeframe,
            from_date=start.isoformat(),through_date=cursor.isoformat(),merge_mode=merge_mode,
            credential=credential,transport=network,provider_symbol_override=provider_symbol_override,
            defer_validation=True,allow_empty=True,progress=progress,
        )
        history_requests+=1;chunks.append(result)
        if result.received==0:
            termination_reason="PROVIDER_RETURNED_NO_EARLIER_OBSERVATIONS"
            break
        if earliest is not None and start==earliest:
            termination_reason="PROVIDER_REPORTED_EARLIEST_AVAILABLE_OBSERVATION"
            break
        if start==date.min:
            termination_reason="PROVIDER_SUPPORTED_DATE_FLOOR_REACHED"
            break
        previous_cursor=cursor
        cursor=start+timedelta(days=overlap_days-1) if overlap_days else start-timedelta(days=1)
        if cursor>=previous_cursor:  # pragma: no cover - defensive date progress stop
            raise AcquisitionError("NON_PROGRESSING_HISTORY_PLAN","backward acquisition did not advance")

    nonempty=[chunk for chunk in chunks if chunk.staged]
    if not nonempty:raise AcquisitionError("NO_USABLE_OBSERVATIONS","provider supplied no history")
    if progress:progress("validating")
    try:
        validation=validator(database_path,symbol=normalized_asset,timeframe=normalized_timeframe,through_date=through_date,persist=True)
    except BaseException as error:
        raise AcquisitionError("POST_INGEST_VALIDATION_FAILED",f"evidence committed but validation failed: {type(error).__name__}",evidence_committed=True) from error
    run_ids=[chunk.ingest_run_id for chunk in chunks]
    receipt=_aggregate_receipt(database_path,normalized_asset,normalized_timeframe,chunks,run_ids)
    truth=truth_state_for_lane(database_path,symbol=normalized_asset,timeframe=normalized_timeframe)
    return {
        **receipt,
        "provider_id":config.provider_id,"provider":config.provider_id,
        "provider_contract":config.provider_contract,"provider_symbol":provider_symbol,
        "asset":normalized_asset,"symbol":normalized_asset,"timeframe":normalized_timeframe,
        "acquisition_intent":"MAXIMUM_AVAILABLE_HISTORY",
        "from_date":receipt["earliest_provider_observation"],"through_date":through_date,
        "request_count":history_requests+1,"history_request_count":history_requests,
        "boundary_request_count":1,"boundary_ingest_run_id":boundary_run_id,
        "provider_per_request_limit":config.request_ceiling,
        "chunking_strategy":f"BACKWARD_{window_days}_CALENDAR_DAY_WINDOWS_{overlap_days}_DAY_OVERLAP",
        "termination_reason":termination_reason,
        "caodt":truth.get("caodt"),"truth_score":truth.get("truth_score"),
        "validation_calendar_id":validation.as_dict().get("calendar_id"),  # type: ignore[attr-defined]
        "warnings":[],
    }


def _discover_earliest(database_path,*,asset,timeframe,provider_symbol,credential,transport):
    config=load_provider_config(timeframe=timeframe)
    request=HttpRequest(config.provider_host,"/earliest_timestamp?"+urlencode({"interval":config.interval,"symbol":provider_symbol}),config.user_agent)
    response=_acquire_response(
        transport,request,credential,config,lambda _:None,
        authority=authority_for_credential(credential), endpoint="earliest_timestamp",
    )
    received_at=datetime.now(UTC).isoformat();raw_id,checksum=evidence_identity(response.body)
    ingestion=ingest_staged_batch(
        database_path,batch=StagingBatch((),(),0,0,0),
        evidence=RawEvidence(raw_id,checksum,response.body,f"{config.provider_contract}:{asset}:earliest_timestamp",f"{config.base_url}{request.target}","application/json",received_at),
        run_kind="provider_boundary_discovery",merge_mode="preserve",
        outcome_facts={"asset":asset,"timeframe":timeframe,"provider":config.provider_id,"provider_symbol":provider_symbol,"boundary_kind":"EARLIEST_AVAILABLE"},
        preserve_rejected_evidence=True,
    )
    try:payload=json.loads(response.body)
    except (UnicodeDecodeError,json.JSONDecodeError) as error:raise AcquisitionError("MALFORMED_BOUNDARY_RESPONSE","earliest boundary response is not JSON") from error
    value=payload.get("datetime") if isinstance(payload,dict) else None
    if value is None and isinstance(payload,dict):value=payload.get("earliest_timestamp")
    if not isinstance(value,str):raise AcquisitionError("EARLIEST_BOUNDARY_UNAVAILABLE","provider did not report an earliest timestamp")
    try:earliest=date.fromisoformat(value[:10])
    except ValueError as error:raise AcquisitionError("MALFORMED_BOUNDARY_RESPONSE","provider earliest timestamp is invalid") from error
    return earliest,ingestion.ingest_run_id


def _aggregate_receipt(database_path,asset,timeframe,chunks,run_ids):
    placeholders=",".join("?" for _ in run_ids)
    with open_read_only(database_path) as connection:
        unique=connection.execute(f"SELECT count(DISTINCT timestamp),min(timestamp),max(timestamp) FROM provenance WHERE ingest_run_id IN ({placeholders})",run_ids).fetchone()
        canonical=connection.execute("SELECT min(open_time_utc),max(open_time_utc) FROM bars WHERE asset=? AND timeframe=?",(asset,timeframe)).fetchone()
    iso=lambda value:datetime.fromtimestamp(value,UTC).isoformat() if value is not None else None
    return {
        "provider_rows_received":sum(chunk.received for chunk in chunks),
        "received":sum(chunk.received for chunk in chunks),
        "unique_observations_received":unique[0],"staged":unique[0],
        "inserted":sum(chunk.inserted for chunk in chunks),
        "unchanged":sum(chunk.unchanged for chunk in chunks),
        "conflicts_preserved":sum(chunk.conflicts_preserved for chunk in chunks),
        "corrected":sum(chunk.corrected for chunk in chunks),
        "rejected":sum(chunk.rejected for chunk in chunks),
        "earliest_provider_observation":iso(unique[1]),"latest_provider_observation":iso(unique[2]),
        "canonical_earliest_bar":iso(canonical[0]),"canonical_latest_bar":iso(canonical[1]),
        "actual_range":f"{iso(unique[1])} → {iso(unique[2])}",
        "ingest_run_ids":run_ids,"raw_block_ids":[chunk.raw_block_id for chunk in chunks],
        "raw_block_id":chunks[-1].raw_block_id,
    }
