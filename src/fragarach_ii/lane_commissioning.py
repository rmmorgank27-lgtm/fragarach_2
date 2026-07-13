"""Reviewed activation of core evidence lanes under the D1 identity anchor."""
from __future__ import annotations
from datetime import UTC,datetime
from pathlib import Path
from .storage import AuthorityEventManifest,append_authority_event,open_read_only,registered_writer,transaction
from .storage.migrations import apply_migrations

CORE={"D1","H1","M30","M5"};MULTI={"FX","METALS"}

def market_policy(asset_class:str,timeframe:str)->str:
    if timeframe=="D1":return "REQUIRED"
    if "EQUIT" in asset_class or asset_class in {"STOCK","STOCKS"}:return "INTENTIONALLY_DEFERRED"
    return "REQUIRED" if asset_class in {"FX","METALS","ENERGY","INDICES","CRYPTO"} else "NOT_AUTHORISED"

def ensure_commissioned_lane(database_path:str|Path,asset:str,timeframe:str,*,observed_at:str|None=None)->None:
    asset=asset.strip().upper();timeframe=timeframe.strip().upper()
    if timeframe=="D1":return
    if timeframe not in CORE:raise ValueError(f"NOT_AUTHORISED: {timeframe}")
    c=open_read_only(database_path)
    try:
        row=c.execute("SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",(asset,)).fetchone()
        exists=c.execute("SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",(asset,timeframe)).fetchone()
    finally:c.close()
    if not row:raise ValueError(f"UNREGISTERED_INSTRUMENT: {asset}")
    policy=market_policy(row[0],timeframe)
    if policy!="REQUIRED":raise ValueError(f"{policy}: {asset}:{timeframe}")
    if row[0] not in MULTI:raise ValueError(f"LOCAL_AUTHORITY_STOP: {row[0]}")
    if exists:return
    observed=observed_at or datetime.now(UTC).isoformat()
    append_authority_event(database_path,AuthorityEventManifest("EVIDENCE_LANE",f"lane:{asset}:{timeframe}","LANE_DECLARED",observed,"SPEC-025_OPERATOR",(),"COMPATIBLE",(),{"asset":asset,"timeframe":timeframe,"policy_state":policy,"activation_state":"ACTIVE_NO_EVIDENCE","registration_entity_id":f"registration:{asset}:D1"}),recorded_at_utc=observed)
    with registered_writer(database_path) as connection:
        apply_migrations(connection)
        with transaction(connection):connection.execute("INSERT OR IGNORE INTO evidence_lanes VALUES(?,?, 'D1','EVIDENCE_LANE_V1',1,?)",(asset,timeframe,observed))
