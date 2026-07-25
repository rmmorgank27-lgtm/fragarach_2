"""Registry-derived SPEC-025 estate timeframe audit."""
from __future__ import annotations
from datetime import UTC,datetime
from pathlib import Path
from .lane_commissioning import CORE,lane_eligibility,market_policy
from .storage import open_read_only
from .truth_engine import truth_state_for_lane

TARGET_MARKETS={"CRYPTO":"Crypto","ENERGY":"Energy","INDICES":"Indices"}

def audit_target_timeframes(database_path:str|Path)->dict[str,object]:
    connection=open_read_only(database_path)
    try:
        registrations=connection.execute("""SELECT asset,asset_class,display_name,representation_type,exchange_name,registration_status,
          coalesce(provider_id,(SELECT json_extract(i.detail,'$.provider') FROM ingest_runs i WHERE i.status='committed' AND json_extract(i.detail,'$.asset')=instrument_registrations.asset ORDER BY i.finished_at_utc DESC LIMIT 1)),calendar_id
          FROM instrument_registrations WHERE timeframe='D1' AND asset_class IN ('CRYPTO','ENERGY','INDICES') ORDER BY asset_class,asset""").fetchall()
        rows=[]
        for asset,asset_class,display_name,representation,exchange,registration_state,provider,calendar_id in registrations:
            for timeframe in ("D1","H1","M30","M5"):
                lane=connection.execute("SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",(asset,timeframe)).fetchone()
                facts=connection.execute("SELECT count(*),min(open_time_utc),max(open_time_utc) FROM bars WHERE asset=? AND timeframe=?",(asset,timeframe)).fetchone()
                count,earliest,latest=facts
                eligible,reason=lane_eligibility(database_path,asset,timeframe)
                truth=truth_state_for_lane(database_path,symbol=asset,timeframe=timeframe) if count else None
                if timeframe=="D1" and not count:reason="D1_NO_USABLE_EVIDENCE"+(":PROVIDER_MAPPING_REQUIRED" if not provider else "")+(f":CALENDAR_AUTHORITY_REQUIRED:{calendar_id}" if calendar_id=="REGISTRY_D1_V1" else "")
                elif eligible and not lane:reason="EVIDENCE_LANE_NOT_DECLARED"
                elif eligible and lane and not count:reason="HISTORY_NOT_ACQUIRED"
                rows.append({
                    "market":TARGET_MARKETS[asset_class],"subgroup":_subgroup(asset_class,asset,exchange),"symbol":asset,"display_name":display_name,"timeframe":timeframe,
                    "registration_state":registration_state if timeframe=="D1" else "D1_IDENTITY_ANCHOR",
                    "evidence_lane_state":"PRESENT" if count else "DECLARED_NO_EVIDENCE" if lane else "ABSENT",
                    "canonical_row_count":count,"earliest_bar":_iso(earliest),"latest_bar":_iso(latest),
                    "caodt":truth["caodt"] if truth else None,"authority_state":"BLOCKED" if not eligible else truth["authority_state"] if truth else "ACTIVE_NO_EVIDENCE",
                    "source_provider":provider,"missing_reason":reason,"representation_type":representation,"policy_state":market_policy(asset_class,timeframe),
                })
    finally:connection.close()
    return {"contract":"fragarach_ii.spec025_estate_audit.v1","generated_at":datetime.now(UTC).isoformat(),"database":str(Path(database_path).resolve()),"required_timeframes":["D1","H1","M30","M5"],"symbols_by_market":{name:sum(r[1]==code for r in registrations) for code,name in TARGET_MARKETS.items()},"rows":rows}

def _iso(epoch:int|None)->str|None:return datetime.fromtimestamp(epoch,UTC).isoformat() if epoch is not None else None
def _subgroup(asset_class:str,symbol:str,exchange:str)->str:
    if asset_class=="CRYPTO":return "All"
    if asset_class=="ENERGY":return "Unspecified"
    value=f"{symbol} {exchange}".upper()
    if any(x in value for x in ("XJO","ASX","AUS200")):return "Australia"
    if any(x in value for x in ("NIKKEI","N225","HSI","HANG SENG","ASIA")):return "Asia"
    if any(x in value for x in ("DAX","FTSE","STOXX","EUROPE","DEUTSCHE")):return "Europe"
    return "US"
