"""Reviewed activation of core evidence lanes under the D1 identity anchor."""
from __future__ import annotations
from datetime import UTC,datetime
from pathlib import Path
from .commissioning_authority import ALL_TIMEFRAMES,commissioning_policy
from .market_registry import load_registry
from .storage import AuthorityEventManifest,append_authority_event,open_read_only,registered_writer,transaction
from .storage.migrations import apply_migrations

CORE=set(ALL_TIMEFRAMES)
STOCK_CLASSES={"US_EQUITIES","UK_EQUITIES","GERMAN_EQUITIES","AUSTRALIAN_EQUITIES","STOCK","STOCKS"}
STOCK_D1_AUTHORITIES={"US_EQUITIES":"US_EQUITIES_D1_AUTHORITY_V1","AUSTRALIAN_EQUITIES":"AUSTRALIAN_EQUITIES_D1_AUTHORITY_V1","UK_EQUITIES":"UK_EQUITIES_D1_AUTHORITY_V1"}
STOCK_D1_CALENDARS={"US_EQUITIES":"US_EQUITIES_D1_V1","AUSTRALIAN_EQUITIES":"AUSTRALIAN_EQUITIES_D1_V1","UK_EQUITIES":"UK_EQUITIES_D1_V1"}
US_MARKET_VENUES={
    "NASDAQ","NYSE","NYSE ARCA","CBOE","CBOE GLOBAL INDICES",
    "NASDAQ GLOBAL INDEX DATA SERVICE","US INDEX MARKET",
}
GENERIC_MARKET_VENUES={"","UNKNOWN","OTC","INDEX NAMESPACE"}

def market_policy(asset_class:str,timeframe:str)->str:
    return commissioning_policy(asset_class,timeframe)

def _reviewed_market_venue(
    *,asset_class:str,exchange_name:str|None,canonical_symbol:str|None
)->str:
    exchange=(exchange_name or "").strip()
    if exchange.upper() not in GENERIC_MARKET_VENUES:
        return exchange
    if canonical_symbol:
        symbol=canonical_symbol.strip().upper()
        record=next((
            item for item in load_registry().records
            if item.get("active") and str(item.get("canonical_symbol")).upper()==symbol
            and str(item.get("asset_class")).upper()==asset_class.upper()
        ),None)
        if record:
            return str(record.get("exchange_or_venue") or exchange)
    return exchange

def resolved_calendar_authority(*,asset_class:str,calendar_id:str,exchange_name:str|None,canonical_symbol:str|None=None)->str|None:
    """Resolve acquisition authority without claiming that evidence is consumable.

    Legacy discovery registrations used ``REGISTRY_D1_V1`` as a placeholder.  A
    stock registration still has a factual primary venue and a ratified market D1
    authority, so the acquisition planner can name that authority without
    rewriting the registration or fabricating a venue.
    """
    exchange=_reviewed_market_venue(
        asset_class=asset_class,exchange_name=exchange_name,
        canonical_symbol=canonical_symbol,
    )
    resolved=resolved_calendar_id(
        asset_class=asset_class,calendar_id=calendar_id,
        exchange_name=exchange_name,canonical_symbol=canonical_symbol,
    )
    if resolved=="US_EQUITIES_D1_V1":
        return f"US_EQUITIES_D1_AUTHORITY_V1 · {exchange} · REGULAR_SESSION_ONLY"
    if resolved=="AUSTRALIAN_EQUITIES_D1_V1":
        return f"AUSTRALIAN_EQUITIES_D1_AUTHORITY_V1 · {exchange} · REGULAR_SESSION_ONLY"
    if resolved=="UK_EQUITIES_D1_V1":
        return f"UK_EQUITIES_D1_AUTHORITY_V1 · {exchange} · REGULAR_SESSION_ONLY"
    if resolved:return resolved
    return None

def resolved_calendar_id(*,asset_class:str,calendar_id:str,exchange_name:str|None,canonical_symbol:str|None=None)->str|None:
    if calendar_id and calendar_id!="REGISTRY_D1_V1":return calendar_id
    exchange=_reviewed_market_venue(
        asset_class=asset_class,exchange_name=exchange_name,
        canonical_symbol=canonical_symbol,
    ).upper()
    if asset_class in STOCK_D1_CALENDARS and exchange not in GENERIC_MARKET_VENUES:
        return STOCK_D1_CALENDARS[asset_class]
    if exchange in US_MARKET_VENUES:
        return "US_EQUITIES_D1_V1"
    return None

def eligibility_reason(*,asset_class:str,representation_type:str,provider_id:str|None,provider_contract:str|None,provider_symbol:str|None,calendar_id:str,exchange_name:str|None,identity_json:str,timeframe:str,registration_status:str|None="REGISTERED_NO_EVIDENCE",canonical_symbol:str|None=None)->str|None:
    if not registration_status or not registration_status.startswith("REGISTERED_"):return "INSTRUMENT_REGISTRATION_INACTIVE"
    if not provider_id or not provider_symbol:return "PROVIDER_SYMBOL_MAPPING_REQUIRED"
    expected=f"TWELVE_DATA_TIME_SERIES_{timeframe}_V1"
    if provider_id=="TWELVE_DATA" and (provider_contract if timeframe=="D1" else expected)!=expected:return f"{timeframe}_ACQUISITION_CONTRACT_UNAVAILABLE"
    if timeframe=="D1":
        if asset_class in STOCK_CLASSES:
            if representation_type not in {"COMMON_STOCK","ORDINARY_SHARE"}:return "EXCHANGE_IDENTITY_REQUIRED"
            if not (exchange_name or "").strip() or (exchange_name or "").strip().upper() in {"UNKNOWN","OTC"}:return "EXCHANGE_IDENTITY_REQUIRED"
        if resolved_calendar_authority(asset_class=asset_class,calendar_id=calendar_id,exchange_name=exchange_name,canonical_symbol=canonical_symbol) is None:
            return "TRADING_CALENDAR_REQUIRED"
        return None
    if market_policy(asset_class,timeframe)!="REQUIRED":return f"{market_policy(asset_class,timeframe)}"
    if not provider_id or not provider_symbol:return "PROVIDER_MAPPING_REQUIRED"
    if asset_class=="CRYPTO":
        if representation_type!="CRYPTO_SPOT_PAIR":return "CRYPTO_SPOT_IDENTITY_REQUIRED"
        if calendar_id!="CRYPTO_D1_V1":return "CRYPTO_CONTINUOUS_SESSION_REQUIRED"
        return None
    if asset_class=="ENERGY":
        if representation_type in {"ETF","FUTURES"}:return f"ENERGY_INTRADAY_EXCLUDES_{representation_type}"
        if '"source_nature":"PROVIDER_DERIVED_REFERENCE"' not in identity_json.replace(" ",""):return "ENERGY_SOURCE_NATURE_REQUIRED"
        return None
    if asset_class=="INDICES":
        if representation_type!="INDEX":return f"INDICES_INTRADAY_EXCLUDES_{representation_type}"
        compact=identity_json.replace(" ","")
        required=("administrator","methodology_reference","calculation_calendar","calculation_window")
        missing=[name for name in required if f'"{name}":' not in compact]
        if missing:return "INDEX_PROFILE_REQUIRED:"+",".join(missing)
        return None
    return None

_DIRECT_MAPPING_CLASSES={
    "EXACT_REPRESENTATION",
    "APPROVED_PROVIDER_ALIAS",
    "APPROVED_EQUIVALENT_REPRESENTATION",
}
_PROVIDER_CONTRACTS={
    "TWELVE_DATA":"TWELVE_DATA_TIME_SERIES_{timeframe}_V1",
    "YAHOO_FINANCE":"YAHOO_FINANCE_CHART_D1_V1",
    "BINANCE":"BINANCE_KLINES_V1",
    "COINGECKO":"COINGECKO_OHLC_V1",
}


def lane_eligibility(database_path:str|Path,asset:str,timeframe:str)->tuple[bool,str|None]:
    connection=open_read_only(database_path)
    try:
        row=connection.execute("SELECT asset_class,representation_type,provider_id,provider_contract,provider_symbol,calendar_id,exchange_name,identity_json,registration_status FROM instrument_registrations WHERE asset=? AND timeframe='D1'",(asset.strip().upper(),)).fetchone()
    finally:connection.close()
    if not row:return False,"UNREGISTERED_INSTRUMENT"
    provider_id,provider_contract,provider_symbol=row[2],row[3],row[4]
    if not provider_id or not provider_symbol:
        resolved=resolved_provider_mapping_for_lane(database_path,asset.strip().upper(),timeframe.strip().upper())
        if resolved:
            provider_id=str(resolved["provider"])
            provider_contract=str(resolved["provider_contract"])
            provider_symbol=str(resolved["provider_symbol"])
    reason=eligibility_reason(asset_class=row[0],representation_type=row[1],provider_id=provider_id,provider_contract=provider_contract,provider_symbol=provider_symbol,calendar_id=row[5],exchange_name=row[6],identity_json=row[7],registration_status=row[8],timeframe=timeframe.strip().upper(),canonical_symbol=asset.strip().upper())
    return reason is None,reason

def resolved_provider_mapping_for_lane(
    database_path:str|Path,asset:str,timeframe:str,
) -> dict[str,str] | None:
    """Return a reviewed provider mapping already proven by Fragarach evidence.

    Manual imports establish canonical bars but cannot establish a provider
    representation.  A committed provider acquisition with an exact reviewed
    mapping can: it is the same bounded, immutable evidence used for future
    updates.  This repairs registrations created before the provider mapping
    was persisted without promoting a manual file into a provider fact.
    """
    asset=asset.strip().upper();timeframe=timeframe.strip().upper()
    try:
        from .provider_facts import representation_mapping
        mapping=representation_mapping(database_path,"TWELVE_DATA",asset)
    except Exception:
        mapping=None
    if mapping and mapping.get("status") in {"RESOLVED_AUTOMATICALLY","OPERATOR_RESOLVED"}:
        mapping_class=str(mapping.get("mapping_class") or "").upper()
        capabilities=mapping.get("timeframe_capabilities")
        capability=capabilities.get(timeframe,{}) if isinstance(capabilities,dict) else {}
        provider_symbol=mapping.get("provider_symbol")
        if mapping_class in _DIRECT_MAPPING_CLASSES and provider_symbol and not (
            capability and capability.get("supported") is False
        ):
            return {
                "provider":"TWELVE_DATA",
                "provider_contract":f"TWELVE_DATA_TIME_SERIES_{timeframe}_V1",
                "provider_symbol":str(provider_symbol),
                "mapping_class":mapping_class,
                "authority_source":"PROVIDER_FACTS",
            }

    connection=open_read_only(database_path)
    try:
        row=connection.execute(
            """SELECT json_extract(detail,'$.provider'),
                      json_extract(detail,'$.provider_contract'),
                      json_extract(detail,'$.provider_symbol'),
                      json_extract(detail,'$.mapping_class')
               FROM ingest_runs
               WHERE status='committed'
                 AND json_extract(detail,'$.asset')=?
                 AND json_extract(detail,'$.timeframe')=?
                 AND upper(json_extract(detail,'$.provider')) IN
                     ('TWELVE_DATA','YAHOO_FINANCE','BINANCE','COINGECKO')
                 AND json_extract(detail,'$.provider_symbol') IS NOT NULL
                 AND upper(json_extract(detail,'$.mapping_class')) IN
                     ('EXACT_REPRESENTATION','APPROVED_PROVIDER_ALIAS','APPROVED_EQUIVALENT_REPRESENTATION')
               ORDER BY finished_at_utc DESC,ingest_run_id DESC LIMIT 1""",
            (asset,timeframe),
        ).fetchone()
    finally:connection.close()
    if not row:return None
    provider=str(row[0]).upper()
    provider_symbol=str(row[2])
    mapping_class=str(row[3]).upper()
    contract=str(row[1] or _PROVIDER_CONTRACTS[provider].format(timeframe=timeframe))
    return {
        "provider":provider,
        "provider_contract":contract,
        "provider_symbol":provider_symbol,
        "mapping_class":mapping_class,
        "authority_source":"COMMITTED_PROVIDER_EVIDENCE",
    }

def commissioned_lane_keys(connection)->set[tuple[str,str]]:
    """Return evidence lanes carrying Scheduler ownership.

    Evidence-lane existence remains the canonical-admission prerequisite.  Only
    lanes with an explicit current NOT_COMMISSIONED marker are excluded; this
    backward-compatible default preserves every pre-SPEC-058 commissioned lane.
    """
    evidence={
        (str(row[0]),str(row[1]))
        for row in connection.execute(
            "SELECT asset,timeframe FROM evidence_lanes"
        ).fetchall()
    }
    manual_only={
        (str(row[0]),str(row[1]))
        for row in connection.execute(
            """SELECT json_extract(e.canonical_payload,'$.body.asset'),
                      json_extract(e.canonical_payload,'$.body.timeframe')
               FROM authority_events e
               WHERE e.entity_kind='EVIDENCE_LANE'
                 AND json_extract(e.canonical_payload,'$.body.commissioning_state')='NOT_COMMISSIONED'
                 AND NOT EXISTS (
                   SELECT 1 FROM authority_events successor
                   WHERE successor.supersedes_event_id=e.authority_event_id
                 )"""
        ).fetchall()
        if row[0] and row[1]
    }
    return evidence-manual_only

def _manual_lane_event(connection,asset:str,timeframe:str):
    return connection.execute(
        """SELECT e.authority_event_id
           FROM authority_events e
           WHERE e.entity_kind='EVIDENCE_LANE'
             AND json_extract(e.canonical_payload,'$.body.asset')=?
             AND json_extract(e.canonical_payload,'$.body.timeframe')=?
             AND json_extract(e.canonical_payload,'$.body.commissioning_state')='NOT_COMMISSIONED'
             AND NOT EXISTS (
               SELECT 1 FROM authority_events successor
               WHERE successor.supersedes_event_id=e.authority_event_id
             )
           ORDER BY e.recorded_at_utc DESC,e.authority_event_id DESC LIMIT 1""",
        (asset,timeframe),
    ).fetchone()

def ensure_manual_acquisition_lane(
    database_path:str|Path,asset:str,timeframe:str,*,observed_at:str|None=None
)->bool:
    """Declare canonical admission for one manual acquisition without automation."""
    asset=asset.strip().upper();timeframe=timeframe.strip().upper()
    if timeframe not in CORE:raise ValueError(f"NOT_AUTHORISED: {timeframe}")
    connection=open_read_only(database_path)
    try:
        registration=connection.execute(
            "SELECT asset_class,registration_status FROM instrument_registrations WHERE asset=? AND timeframe='D1'",
            (asset,),
        ).fetchone()
        exists=connection.execute(
            "SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",
            (asset,timeframe),
        ).fetchone()
    finally:connection.close()
    if not registration:raise ValueError(f"UNREGISTERED_INSTRUMENT: {asset}")
    if not str(registration[1]).startswith("REGISTERED_"):
        raise ValueError(f"INSTRUMENT_REGISTRATION_INACTIVE: {asset}")
    if exists:return False
    observed=observed_at or datetime.now(UTC).isoformat()
    append_authority_event(
        database_path,
        AuthorityEventManifest(
            "EVIDENCE_LANE",f"lane:{asset}:{timeframe}","LANE_DECLARED",observed,
            "SPEC-058_OPERATOR",(),"COMPATIBLE",(),{
                "asset":asset,"timeframe":timeframe,
                "policy_state":market_policy(str(registration[0]),timeframe),
                "activation_state":"DECLARED",
                "commissioning_state":"NOT_COMMISSIONED",
                "automation_enabled":False,
                "registration_entity_id":f"registration:{asset}:D1",
            },
        ),
        recorded_at_utc=observed,
    )
    with registered_writer(database_path) as connection:
        apply_migrations(connection)
        with transaction(connection):
            connection.execute(
                "INSERT OR IGNORE INTO evidence_lanes VALUES(?,?, 'D1','EVIDENCE_LANE_V1',1,?)",
                (asset,timeframe,observed),
            )
    from .publication_service import enqueue_publication
    enqueue_publication(database_path, [(asset, timeframe)], trigger="MANUAL_LANE_DECLARATION")
    return True

def ensure_commissioned_lane(database_path:str|Path,asset:str,timeframe:str,*,observed_at:str|None=None)->None:
    asset=asset.strip().upper();timeframe=timeframe.strip().upper()
    if timeframe=="D1":return
    if timeframe not in CORE:raise ValueError(f"NOT_AUTHORISED: {timeframe}")
    c=open_read_only(database_path)
    try:
        row=c.execute("SELECT asset_class FROM instrument_registrations WHERE asset=? AND timeframe='D1'",(asset,)).fetchone()
        exists=c.execute("SELECT 1 FROM evidence_lanes WHERE asset=? AND timeframe=?",(asset,timeframe)).fetchone()
        manual_event=_manual_lane_event(c,asset,timeframe) if exists else None
    finally:c.close()
    if not row:raise ValueError(f"UNREGISTERED_INSTRUMENT: {asset}")
    policy=market_policy(row[0],timeframe)
    if policy!="REQUIRED":raise ValueError(f"{policy}: {asset}:{timeframe}")
    eligible,reason=lane_eligibility(database_path,asset,timeframe)
    if not eligible:raise ValueError(f"AUTHORITY_STOP: {reason}")
    observed=observed_at or datetime.now(UTC).isoformat()
    if exists and not manual_event:return
    event_kind="LANE_REVISED" if manual_event else "LANE_DECLARED"
    append_authority_event(database_path,AuthorityEventManifest("EVIDENCE_LANE",f"lane:{asset}:{timeframe}",event_kind,observed,"SPEC-025_OPERATOR",(),"COMPATIBLE",(),{"asset":asset,"timeframe":timeframe,"policy_state":policy,"activation_state":"ACTIVE_NO_EVIDENCE","commissioning_state":"COMMISSIONED","automation_enabled":True,"registration_entity_id":f"registration:{asset}:D1"},manual_event[0] if manual_event else None),recorded_at_utc=observed)
    if exists:
        from .publication_service import enqueue_publication
        enqueue_publication(database_path, [(asset, timeframe)], trigger="LANE_COMMISSIONING")
        return
    with registered_writer(database_path) as connection:
        apply_migrations(connection)
        with transaction(connection):connection.execute("INSERT OR IGNORE INTO evidence_lanes VALUES(?,?, 'D1','EVIDENCE_LANE_V1',1,?)",(asset,timeframe,observed))
    from .publication_service import enqueue_publication
    enqueue_publication(database_path, [(asset, timeframe)], trigger="LANE_COMMISSIONING")
