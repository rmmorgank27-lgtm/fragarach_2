"""Yahoo Finance D1 adapter using the common immutable ingestion pipeline."""
from __future__ import annotations
import hashlib,json
from datetime import UTC,date,datetime,time
from pathlib import Path
from urllib.parse import quote,urlencode
from urllib.request import Request,urlopen
from fragarach_ii.ingestion import RawEvidence,ingest_staged_batch
from fragarach_ii.ingestion.validation import RowValidationError,deduplicate_bars,stage_record
from fragarach_ii.providers.yahoo_symbols import yahoo_equity_symbol_for_representation
from fragarach_ii.staging import StagingBatch,StagingRejection
from .twelve_data import AcquisitionError

def yahoo_symbol(asset:str,asset_class:str)->str:
    if asset_class=="FX":return f"{asset[:3]}{asset[3:]}=X"
    listed=yahoo_equity_symbol_for_representation(asset)
    if listed:return listed
    return {"SPX":"^GSPC","DJI":"^DJI","NDX":"^NDX","FTSE":"^FTSE","DAX":"^GDAXI","XJO":"^AXJO"}.get(asset,asset)

def acquire_yahoo(database_path:str|Path,*,asset:str,asset_class:str,from_date:str,through_date:str,merge_mode:str="preserve",fetch=None,provider_symbol_override:str|None=None,mapping_class:str|None=None):
    symbol=provider_symbol_override or yahoo_symbol(asset,asset_class);start=date.fromisoformat(from_date);end=date.fromisoformat(through_date)
    params=urlencode({"period1":int(datetime.combine(start,time.min,UTC).timestamp()),"period2":int(datetime.combine(end,time.max,UTC).timestamp()),"interval":"1d","events":"history"})
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol,safe='')}?{params}"
    body=(fetch or _fetch)(url)
    try:
        payload=json.loads(body)
    except (TypeError,json.JSONDecodeError) as error:
        raise AcquisitionError("INVALID_RESPONSE", "Yahoo returned malformed JSON") from error
    result=payload.get("chart",{}).get("result")
    if not result:
        raise AcquisitionError("INVALID_RESPONSE", str(payload.get("chart",{}).get("error") or "Yahoo returned no valid data"))
    chart=result[0];returned=chart.get("meta",{}).get("symbol")
    if returned!=symbol:
        raise AcquisitionError("INVALID_RESPONSE", f"Yahoo symbol mismatch: expected {symbol}, received {returned}")
    timestamps=chart.get("timestamp") or [];quote_data=(chart.get("indicators",{}).get("quote") or [{}])[0];received_at=datetime.now(UTC).isoformat();checksum=hashlib.sha256(body).hexdigest();raw_id=f"raw-{checksum}";bars=[];row_rejections=[]
    for index,timestamp in enumerate(timestamps,start=1):
        values={name:(quote_data.get(name) or [None]*len(timestamps))[index-1] for name in ("open","high","low","close","volume")}
        if any(values[name] is None for name in ("open","high","low","close")):continue
        values["timestamp"]=datetime.fromtimestamp(timestamp,UTC).date().isoformat()
        try:
            bars.append(stage_record({k:str(v) if v is not None else "" for k,v in values.items()},explicit_symbol=asset,explicit_timeframe="D1",provider="YAHOO_FINANCE",source="YAHOO_FINANCE_CHART_D1_V1",raw_block_id=raw_id,source_row_number=index,received_at=received_at))
        except RowValidationError as error:
            row_rejections.append(StagingRejection(index,error.code,str(error)))
    ordered,rejections,identical,conflicting=deduplicate_bars(bars)
    all_rejections=tuple(row_rejections)+tuple(rejections)
    if not ordered:
        # A valid route can occasionally yield an incomplete chart response
        # while Yahoo is refreshing its daily aggregate.  This is provider
        # evidence to retry, not a local programming fault that blocks a lane.
        raise AcquisitionError("INVALID_RESPONSE", "Yahoo returned no valid unambiguous D1 observations")
    batch=StagingBatch(bars=ordered,rejections=all_rejections,source_rows=len(timestamps),duplicate_identical=identical,duplicate_conflicting=conflicting)
    ingestion=ingest_staged_batch(database_path,batch=batch,evidence=RawEvidence(raw_id,checksum,body,"YAHOO_FINANCE_CHART_D1_V1",url,"application/json",received_at),run_kind="provider_acquisition",merge_mode=merge_mode,outcome_facts={"asset":asset,"timeframe":"D1","provider":"YAHOO_FINANCE","provider_contract":"YAHOO_FINANCE_CHART_D1_V1","provider_symbol":symbol,"mapping_state":"CONFIRMED_BY_VALID_EVIDENCE","mapping_class":mapping_class or "EXACT_REPRESENTATION","from_date":from_date,"through_date":through_date,"merge_mode":merge_mode,"checksum":checksum},preserve_rejected_evidence=bool(all_rejections))
    warnings=(f"{len(all_rejections)} row-local Yahoo observation(s) quarantined; valid observations were preserved.",) if all_rejections else ()
    return {**ingestion.as_dict(),"provider_id":"YAHOO_FINANCE","provider_contract":"YAHOO_FINANCE_CHART_D1_V1","provider_symbol":symbol,"asset":asset,"timeframe":"D1","from_date":from_date,"through_date":through_date,"actual_range":f"{ordered[0].source_timestamp_text} → {ordered[-1].source_timestamp_text}","received":len(timestamps),"warnings":warnings}

def _fetch(url:str)->bytes:
    response=urlopen(Request(url,headers={"User-Agent":"Fragarach-II/1","Connection":"close"}),timeout=30)
    try:return response.read(20*1024*1024)
    finally:response.close()
