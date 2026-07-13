"""Zero-blocking D1 provider resolution and acquisition."""
from __future__ import annotations
import json
from datetime import date,timedelta
from pathlib import Path
from fragarach_ii.storage import open_read_only
from .twelve_data import AcquisitionError,acquire_twelve_data
from .yahoo_finance import acquire_yahoo,yahoo_symbol

def acquire_resolved(database_path:str|Path,*,asset:str,from_date:str,through_date:str,merge_mode:str,credential:str|None,twelve_transport=None,yahoo_fetch=None)->dict:
    registration=_registration(database_path,asset);asset_class=registration[0];attempts=[]
    confirmed=_confirmed_mapping(database_path,asset) or ((registration[1],registration[2]) if registration[1] and registration[2] else None)
    candidates=[]
    if confirmed:candidates.append(confirmed)
    if asset_class in {"US_EQUITIES","UK_EQUITIES","GERMAN_EQUITIES","AUSTRALIAN_EQUITIES"} and not confirmed:candidates.append(("YAHOO_FINANCE",yahoo_symbol(asset,asset_class)))
    if not any(p=="TWELVE_DATA" for p,_ in candidates):candidates.append(("TWELVE_DATA",f"{asset[:3]}/{asset[3:]}" if asset_class=="FX" else asset.split(":")[-1]))
    if not any(p=="YAHOO_FINANCE" for p,_ in candidates):candidates.append(("YAHOO_FINANCE",yahoo_symbol(asset,asset_class)))
    for provider,symbol in candidates:
        try:
            if provider=="TWELVE_DATA":
                end=date.fromisoformat(through_date);start=max(date.fromisoformat(from_date),end-timedelta(days=4999))
                result=acquire_twelve_data(database_path,asset=asset,timeframe="D1",from_date=start.isoformat(),through_date=through_date,merge_mode=merge_mode,credential=credential,transport=twelve_transport,provider_symbol_override=symbol if not registration[1] else None).as_dict()
                result["warnings"]=[*result.get("warnings",[]),*(["Twelve Data best-available history is limited to 5,000 calendar days."] if start>date.fromisoformat(from_date) else [])]
            else:result=acquire_yahoo(database_path,asset=asset,asset_class=asset_class,from_date=from_date,through_date=through_date,merge_mode=merge_mode,fetch=yahoo_fetch)
            result["provider_attempts"]=attempts+[{"provider":provider,"result":"SUCCESS"}];return result
        except Exception as error:attempts.append({"provider":provider,"result":"FAILED","reason":str(error)})
    raise AcquisitionError("NO_PROVIDER_RETURNED_VALID_DATA",json.dumps({"message":"No provider returned valid data.","attempts":attempts},separators=(",",":")))

def _registration(database_path,asset):
    with open_read_only(database_path) as connection:
        row=connection.execute("select asset_class,provider_id,provider_symbol from instrument_registrations where asset=? and timeframe='D1'",(asset,)).fetchone()
    if not row:raise ValueError(f"unregistered D1 instrument: {asset}")
    return row

def _confirmed_mapping(database_path,asset):
    with open_read_only(database_path) as connection:
        row=connection.execute("select json_extract(detail,'$.provider'),json_extract(detail,'$.provider_symbol') from ingest_runs where status='committed' and json_extract(detail,'$.asset')=? and json_extract(detail,'$.mapping_state')='CONFIRMED_BY_VALID_EVIDENCE' order by finished_at_utc desc limit 1",(asset,)).fetchone()
    return tuple(row) if row and all(row) else None
