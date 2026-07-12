"""Exact ordered FX provider mapping authority and read-only registration audit."""
from __future__ import annotations
import json,re
from pathlib import Path
from .storage import open_read_only

FX_MAPPING_VERSION="TWELVE_DATA_FX_DIRECT_PAIRS_V1"
FX_MAPPING_EVIDENCE="config/providers/mappings/TWELVE_DATA_FX_DIRECT_PAIRS_V1.json"
FX_DIRECT_MAPPINGS={
    "AUDUSD":"AUD/USD","EURAUD":"EUR/AUD","EURGBP":"EUR/GBP","USDJPY":"USD/JPY",
    "NZDJPY":"NZD/JPY","JPYCHF":"JPY/CHF",
}

def normalize_pair(value:str)->str:return re.sub(r"[^A-Z]","",value.upper())

def orientation_for(pair:str,mappings:dict[str,str]|None=None)->dict[str,object]:
    direct=mappings or FX_DIRECT_MAPPINGS;canonical=normalize_pair(pair)
    if len(canonical)!=6:raise ValueError("ordered FX pair must contain two ISO currency codes")
    base,quote=canonical[:3],canonical[3:];inverse=quote+base
    if canonical in direct:
        state="DIRECT_PROVIDER_SUPPORTED";mapping="DIRECT_MAPPING_CONFIRMED";symbol=direct[canonical];inverse_state="DIRECT_MAPPING_CONFIRMED" if inverse in direct else "DIRECT_MAPPING_UNKNOWN"
    elif inverse in direct:
        state="INVERSE_ONLY";mapping="INVERSE_MAPPING_CONFIRMED";symbol=None;inverse_state="DIRECT_MAPPING_CONFIRMED"
    else:
        state="PROVIDER_CAPABILITY_UNKNOWN";mapping="DIRECT_MAPPING_UNKNOWN";symbol=None;inverse_state="DIRECT_MAPPING_UNKNOWN"
    return {"canonical_identity":f"FX:{canonical}","ordered_pair":canonical,"base_currency":base,"quote_currency":quote,"orientation_state":state,"provider":"TWELVE_DATA","requested_provider_symbol":symbol,"exact_mapping_state":mapping,"inverse_pair":inverse,"inverse_provider_symbol":direct.get(inverse),"inverse_mapping_state":inverse_state,"evidence_source":FX_MAPPING_EVIDENCE if canonical in direct or inverse in direct else None,"mapping_version":FX_MAPPING_VERSION,"evidence_timestamp":"2026-07-12","supported_timeframes":("D1","H1","M30","M5") if canonical in direct else (),"entitlement_state":"NOT_MEASURED","acquisition_readiness":"READY_WITH_ENTITLEMENT_UNKNOWN" if canonical in direct else "INVERSE_ONLY" if inverse in direct else "MAPPING_REQUIRED"}

def validate_direct_mapping(asset:str,provider:str,provider_symbol:str)->dict[str,object]:
    orientation=orientation_for(asset)
    if provider!="TWELVE_DATA" or orientation["orientation_state"]!="DIRECT_PROVIDER_SUPPORTED":
        code="INVERSE_ONLY_NOT_DIRECTLY_REGISTERABLE" if orientation["orientation_state"]=="INVERSE_ONLY" else "DIRECT_PROVIDER_MAPPING_REQUIRED"
        raise ValueError(code)
    if provider_symbol!=orientation["requested_provider_symbol"]:raise ValueError("PROVIDER_ORIENTATION_MISMATCH")
    return orientation

def audit_fx_registrations(database_path:str|Path)->dict[str,object]:
    connection=open_read_only(database_path)
    try:
        rows=connection.execute("SELECT identity_json,registration_status,registered_at_utc FROM instrument_registrations WHERE asset_class='FX' ORDER BY asset,timeframe").fetchall();results=[]
        for identity_json,status,registered_at in rows:
            identity=json.loads(identity_json);asset=identity["asset"];provider=identity["provider_id"];symbol=identity["provider_symbol"]
            orientation=orientation_for(asset);expected=orientation["requested_provider_symbol"]
            if orientation["orientation_state"]=="INVERSE_ONLY" and symbol==orientation["inverse_provider_symbol"]:audit_state="INVERSE_EVIDENCE_REUSED"
            elif expected and symbol==expected:audit_state="ORIENTATION_CONFIRMED"
            elif symbol==f"{asset[:3]}/{asset[3:]}" and expected is None:audit_state="SYNTHETIC_PROVIDER_SYMBOL"
            elif expected and symbol!=expected:audit_state="ORIENTATION_MISMATCH"
            else:audit_state="PROVIDER_EVIDENCE_MISSING"
            bars=connection.execute("SELECT count(*) FROM bars WHERE asset=? AND timeframe=?",(asset,identity["timeframe"])).fetchone()[0]
            results.append({"asset":asset,"timeframe":identity["timeframe"],"base_currency":asset[:3],"quote_currency":asset[3:],"provider":provider,"provider_symbol":symbol,"registration_status":status,"registered_at":registered_at,"orientation_state":orientation["orientation_state"],"audit_state":audit_state,"evidence_source":orientation["evidence_source"],"canonical_bar_count":bars,"future_acquisition_allowed":audit_state=="ORIENTATION_CONFIRMED"})
        return {"contract":"fragarach_ii.fx_orientation_audit.v1","mapping_version":FX_MAPPING_VERSION,"registrations":tuple(results),"mutations_performed":0}
    finally:connection.close()
