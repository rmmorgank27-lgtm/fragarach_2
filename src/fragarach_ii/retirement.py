"""SPEC-013 immutable-ledger retirement and evidence quarantine projection."""
from __future__ import annotations
import hashlib,json
from dataclasses import asdict,dataclass
from datetime import UTC,datetime
from pathlib import Path
from .storage import AuthorityEventManifest,append_authority_event,inspect_authority,open_read_only

RETIREMENT_REASONS={"INCORRECT_INSTRUMENT_IDENTITY","INCORRECT_PAIR_ORIENTATION","INCORRECT_PROVIDER_MAPPING","WRONG_SYMBOL","DUPLICATE_REGISTRATION","ERRONEOUS_OPERATOR_REGISTRATION","INVALID_VENUE_OR_LISTING","PROVIDER_EVIDENCE_MISMATCH","OTHER_REVIEWED_REASON"}

class RetirementError(RuntimeError):
    def __init__(self,code,message):self.code=code;super().__init__(message)

def retirement_state(database_path:str|Path,asset:str,timeframe:str|None=None):
    connection=open_read_only(database_path)
    try:
        clauses=["event_kind IN ('REGISTRATION_SUPERSEDED','LANE_SUPERSEDED')","json_extract(canonical_payload,'$.body.asset')=?"];args=[asset.strip().upper()]
        if timeframe:clauses.append("json_extract(canonical_payload,'$.body.timeframe')=?");args.append(timeframe.strip().upper())
        row=connection.execute("SELECT authority_event_id,event_kind,canonical_payload,recorded_at_utc FROM authority_events WHERE "+" AND ".join(clauses)+" ORDER BY effective_from_utc DESC,recorded_at_utc DESC,authority_event_id DESC LIMIT 1",args).fetchone()
        if not row:return None
        body=json.loads(row[2])["body"];return {"retirement_id":body["retirement_id"],"event_id":row[0],"event_kind":row[1],"recorded_at":row[3],**body}
    finally:connection.close()

def is_retired(database_path,asset,timeframe=None):
    if not Path(database_path).expanduser().exists():return False
    return retirement_state(database_path,asset,timeframe) is not None or (timeframe is not None and retirement_state(database_path,asset) is not None)

def retirement_impact(database_path:str|Path,asset:str,scope="WHOLE_INSTRUMENT",selected_lanes:tuple[str,...]=()):
    symbol=asset.strip().upper();connection=open_read_only(database_path)
    try:
        registrations=connection.execute("SELECT timeframe,registration_contract_version,provider_id,provider_symbol,registration_status FROM instrument_registrations WHERE asset=? ORDER BY timeframe",(symbol,)).fetchall()
        if not registrations:raise RetirementError("UNREGISTERED_INSTRUMENT",symbol)
        all_lanes=tuple(r[0] for r in registrations);lanes=all_lanes if scope=="WHOLE_INSTRUMENT" else tuple(sorted(set(x.upper() for x in selected_lanes)))
        if not lanes or not set(lanes)<=set(all_lanes):raise RetirementError("INVALID_RETIREMENT_SCOPE",str(lanes))
        placeholders=",".join("?" for _ in lanes);args=(symbol,*lanes)
        bars=connection.execute(f"SELECT count(*),min(open_time_utc),max(open_time_utc) FROM bars WHERE asset=? AND timeframe IN ({placeholders})",args).fetchone()
        provenance=connection.execute(f"SELECT count(*),count(DISTINCT raw_block_id),count(DISTINCT ingest_run_id) FROM provenance WHERE symbol=? AND timeframe IN ({placeholders})",args).fetchone()
        active_runs=connection.execute("SELECT count(*) FROM ingest_runs WHERE status IN ('registered','active') AND json_extract(detail,'$.asset')=?",(symbol,)).fetchone()[0]
        retired=tuple(lane for lane in lanes if is_retired(database_path,symbol,lane));truth=None
        try:
            from .truth_engine import truth_state_for_lane
            truth=truth_state_for_lane(database_path,symbol=symbol,timeframe=lanes[0])
        except Exception:pass
        return {"contract":"fragarach_ii.retirement_impact.v1","canonical_instrument":symbol,"display_symbol":symbol,"scope":scope,"selected_lanes":lanes,"provider_mappings":tuple({"timeframe":r[0],"provider":r[2],"symbol":r[3]} for r in registrations if r[0] in lanes),"active_registration_versions":tuple({"timeframe":r[0],"version":r[1],"status":r[4]} for r in registrations if r[0] in lanes and r[0] not in retired),"active_timeframe_lanes":tuple(x for x in lanes if x not in retired),"already_retired_lanes":retired,"scheduled_acquisition_jobs":"NOT_RECORDED","in_progress_acquisition_jobs":active_runs,"completed_acquisition_runs":provenance[2],"raw_evidence_blocks":provenance[1],"canonical_bars":bars[0],"provenance_records":provenance[0],"earliest_evidence_timestamp":bars[1],"latest_evidence_timestamp":bars[2],"current_truth_score":truth["truth_score"] if truth else None,"current_caodt":truth["caodt"] if truth else None,"current_serving_state":"ACTIVE" if len(retired)<len(lanes) else "HISTORICAL_ONLY","downstream_active_references":"NOT_MEASURED","typed_confirmation_required":bars[0]>0,"required_confirmation":f"RETIRE {symbol}" if bars[0]>0 else None}
    finally:connection.close()

def retire_instrument(database_path:str|Path,asset:str,*,scope:str,selected_lanes:tuple[str,...],reason:str,operator_note:str,typed_confirmation:str,completed_at:str|None=None):
    if reason not in RETIREMENT_REASONS:raise RetirementError("INVALID_RETIREMENT_REASON",reason)
    if reason=="OTHER_REVIEWED_REASON" and not operator_note.strip():raise RetirementError("OPERATOR_NOTE_REQUIRED",reason)
    impact=retirement_impact(database_path,asset,scope,selected_lanes);symbol=impact["canonical_instrument"]
    if impact["typed_confirmation_required"] and typed_confirmation.strip().upper()!=impact["required_confirmation"]:raise RetirementError("TYPED_CONFIRMATION_REQUIRED",impact["required_confirmation"])
    existing=retirement_state(database_path,symbol)
    if existing:
        if existing["reason"]==reason and existing["scope"]==scope and tuple(existing["selected_lanes"])==tuple(impact["selected_lanes"]):return {"contract":"fragarach_ii.retirement_receipt.v1","outcome":"ALREADY_RETIRED_IDENTICAL",**existing}
        raise RetirementError("RETIREMENT_REASON_CONFLICT","existing retirement differs")
    observed=completed_at or datetime.now(UTC).isoformat();retirement_id=hashlib.sha256(json.dumps([symbol,scope,impact["selected_lanes"],reason,operator_note.strip(),observed],separators=(",",":")).encode()).hexdigest()
    base={"retirement_id":retirement_id,"asset":symbol,"scope":scope,"selected_lanes":impact["selected_lanes"],"reason":reason,"operator_note":operator_note.strip(),"completed_at":observed,"lifecycle_state":_lifecycle(reason)}
    results=[]
    for lane in impact["selected_lanes"]:
        for kind,entity,event,extra in (("INSTRUMENT_REGISTRATION",f"registration:{symbol}:{lane}","REGISTRATION_SUPERSEDED",{"lifecycle_state":_lifecycle(reason)}),("EVIDENCE_LANE",f"lane:{symbol}:{lane}","LANE_SUPERSEDED",{"operational_state":"HISTORICAL_ONLY","acquisition_state":"ACQUISITION_DISABLED","evidence_state":"EVIDENCE_QUARANTINED" if impact["canonical_bars"] else "NO_EVIDENCE","serving_state":"NOT_SERVED","timeframe":lane})):
            predecessor=_leaf_event(database_path,kind,symbol,lane)
            if predecessor:entity=predecessor[1]
            else:
                declaration="REGISTRATION_DECLARED" if kind=="INSTRUMENT_REGISTRATION" else "LANE_DECLARED";declared={"asset":symbol,"timeframe":lane,"activation_state":"ACTIVE","bound_for_retirement_review":True}
                declared_result=append_authority_event(database_path,AuthorityEventManifest(kind,entity,declaration,observed,"SPEC-013_OPERATOR",(),"COMPATIBLE",(),declared),recorded_at_utc=observed);results.append(declared_result);predecessor=(declared_result.authority_event_id,entity)
            body={**base,"timeframe":lane,**extra};manifest=AuthorityEventManifest(kind,entity,event,observed,"SPEC-013_OPERATOR",(),"UNRESOLVED_MATERIAL_FACT",({"code":"OPERATOR_REVIEWED_RETIREMENT"},),body,supersedes_event_id=predecessor[0])
            results.append(append_authority_event(database_path,manifest,recorded_at_utc=observed))
    verification=retirement_impact(database_path,symbol,scope,tuple(impact["selected_lanes"]));return {"contract":"fragarach_ii.retirement_receipt.v1","outcome":"RETIRED","retirement_id":retirement_id,"canonical_instrument":symbol,"scope":scope,"selected_lanes":impact["selected_lanes"],"reason":reason,"operator_note":operator_note.strip(),"previous_authority_state":"ACTIVE","new_authority_state":_lifecycle(reason),"acquisition_shutdown_state":"DISABLED","evidence_quarantine_state":"QUARANTINED" if impact["canonical_bars"] else "NOT_REQUIRED","truth_serving_state":"NOT_SERVED","affected_registration_versions":impact["active_registration_versions"],"affected_acquisition_runs":impact["completed_acquisition_runs"],"affected_raw_blocks":impact["raw_evidence_blocks"],"affected_canonical_bars":impact["canonical_bars"],"completed_timestamp":observed,"warnings":(),"per_lane_outcomes":tuple({"timeframe":lane,"outcome":"RETIRED"} for lane in impact["selected_lanes"]),"verification_results":{"active_lanes":verification["active_timeframe_lanes"],"historical_rows_preserved":True,"events_appended":len(results)}}

def _lifecycle(reason):
    return {"INCORRECT_INSTRUMENT_IDENTITY":"RETIRED_INCORRECT_IDENTITY","INCORRECT_PAIR_ORIENTATION":"RETIRED_INCORRECT_ORIENTATION","WRONG_SYMBOL":"RETIRED_WRONG_SYMBOL","DUPLICATE_REGISTRATION":"RETIRED_DUPLICATE","INCORRECT_PROVIDER_MAPPING":"QUARANTINED_PROVIDER_MISMATCH","PROVIDER_EVIDENCE_MISMATCH":"QUARANTINED_EVIDENCE_CONCERN"}.get(reason,"RETIRED_OPERATOR_REQUEST")

def _leaf_event(database_path,kind,asset,timeframe):
    events=inspect_authority(database_path,entity_kind=kind);matching=[e for e in events if e["entity_id"].endswith(f":{asset}:{timeframe}") or (e["payload"]["body"].get("asset")==asset and e["payload"]["body"].get("timeframe")==timeframe) or (e["payload"]["body"].get("legacy_key") or {}).get("asset")==asset]
    superseded={e["supersedes_event_id"] for e in matching if e["supersedes_event_id"]};leaves=[e for e in matching if e["authority_event_id"] not in superseded]
    if not leaves:return None
    event=sorted(leaves,key=lambda e:(e["effective_from_utc"],e["recorded_at_utc"],e["authority_event_id"]))[-1];return event["authority_event_id"],event["entity_id"]
