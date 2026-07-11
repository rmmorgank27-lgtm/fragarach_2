"""Bounded Twelve Data instrument lookup mapped to authority candidates."""
from __future__ import annotations
import json, re
from dataclasses import asdict, dataclass
from urllib.parse import urlencode
from fragarach_ii.storage import Alias, RegistrationCandidate, open_read_only
from .config import load_provider_config
from .http import BoundedHttpsTransport, HttpRequest, HttpTransport

class InstrumentSearchError(RuntimeError):
    def __init__(self, code: str, message: str) -> None: self.code=code;super().__init__(message)

@dataclass(frozen=True, slots=True)
class InstrumentSearchResult:
    operation_contract: str; query: str; found: bool; already_registered: bool
    candidate: RegistrationCandidate | None; registration_status: str | None
    def as_dict(self):
        value=asdict(self);value["candidate"]=asdict(self.candidate) if self.candidate else None;return value
    def as_json(self): return json.dumps(self.as_dict(),sort_keys=True,separators=(",",":"))

def search_instrument(database_path: str, query: str, *, credential: str | None, transport: HttpTransport | None=None) -> InstrumentSearchResult:
    normalized=query.strip()
    if not normalized: raise InstrumentSearchError("INVALID_QUERY","Search instrument is required")
    existing=_existing(database_path,normalized)
    if existing:
        candidate,status=existing;return InstrumentSearchResult("fragarach_ii.instrument_search_result.v1",normalized,True,True,candidate,status)
    if not credential: raise InstrumentSearchError("PROVIDER_UNAVAILABLE","Provider authentication is unavailable")
    config=load_provider_config();request=HttpRequest(config.provider_host,"/symbol_search?"+urlencode({"symbol":normalized,"outputsize":30}),"Fragarach-II/1 SPEC-006")
    response=(transport or BoundedHttpsTransport()).send(request,credential,config)
    if response.status!=200: raise InstrumentSearchError("PROVIDER_UNAVAILABLE",f"Provider returned HTTP {response.status}")
    try: payload=json.loads(response.body)
    except (UnicodeDecodeError,json.JSONDecodeError) as error: raise InstrumentSearchError("PROVIDER_UNAVAILABLE","Provider returned malformed data") from error
    rows=payload.get("data",[]) if isinstance(payload,dict) else []
    if not isinstance(rows,list): raise InstrumentSearchError("PROVIDER_UNAVAILABLE","Provider returned malformed search results")
    supported=[];unsupported=False
    for row in rows:
        try:
            candidate=_candidate(row)
            if candidate:supported.append(candidate)
        except InstrumentSearchError as error:
            if error.code=="CALENDAR_UNAVAILABLE":unsupported=True
    if not supported:
        if unsupported: raise InstrumentSearchError("CALENDAR_UNAVAILABLE","Calendar unavailable for the matched instrument")
        return InstrumentSearchResult("fragarach_ii.instrument_search_result.v1",normalized,False,False,None,None)
    chosen=min(supported,key=lambda c:_rank(c,normalized));collision=_existing(database_path,chosen.asset)
    return InstrumentSearchResult("fragarach_ii.instrument_search_result.v1",normalized,True,collision is not None,chosen,collision[1] if collision else None)

def candidate_from_dict(value: dict[str,object]) -> RegistrationCandidate:
    fields=dict(value);aliases=tuple(Alias(**item) for item in fields.pop("aliases",[]));return RegistrationCandidate(aliases=aliases,**fields)  # type: ignore[arg-type]

def _existing(database_path: str, query: str):
    normalized=query.strip().upper();connection=open_read_only(database_path)
    try:
        row=connection.execute("""SELECT identity_json,registration_status FROM instrument_registrations r WHERE r.asset=? OR r.local_symbol=? OR upper(r.display_name)=? OR upper(r.provider_symbol)=? OR EXISTS(SELECT 1 FROM json_each(r.aliases_json) WHERE json_extract(value,'$.normalized_alias')=?) ORDER BY r.asset LIMIT 1""",(normalized,normalized,normalized,normalized,normalized)).fetchone()
        if not row:return None
        identity=json.loads(row[0]);names=set(RegistrationCandidate.__dataclass_fields__);return candidate_from_dict({k:v for k,v in identity.items() if k in names}),row[1]
    finally:connection.close()

def _candidate(row: object):
    if not isinstance(row,dict):return None
    symbol=str(row.get("symbol","")).strip().upper();name=str(row.get("instrument_name") or row.get("name") or "").strip();provider_type=str(row.get("instrument_type","")).strip();currency=str(row.get("currency","")).strip().upper();exchange=str(row.get("exchange","")).strip() or "OTC";country=str(row.get("country","")).strip() or None
    if not symbol or not name or not currency or not provider_type:return None
    compact=re.sub(r"[^A-Z0-9]","",symbol)
    if provider_type=="Physical Currency":asset_class,representation,instrument_type,calendar,exchange="FX","FX_SPOT_PAIR","FX_SPOT_PAIR","FX_D1_V1","OTC"
    elif provider_type=="Digital Currency":asset_class,representation,instrument_type,calendar="CRYPTO","CRYPTO_SPOT_PAIR","CRYPTO_SPOT_PAIR","CRYPTO_D1_V1"
    elif provider_type=="Precious Metal":asset_class,representation,instrument_type,calendar,exchange="METALS","SPOT","PRECIOUS_METAL_SPOT_PAIR","METALS_D1_V1","OTC"
    else:raise InstrumentSearchError("CALENDAR_UNAVAILABLE",provider_type)
    aliases=()
    return RegistrationCandidate(asset=compact,timeframe="D1",instrument_family=compact,local_symbol=compact,aliases=aliases,display_name=name,instrument_type=instrument_type,asset_class=asset_class,representation_type=representation,trading_currency=currency,exchange_name=exchange,provider_id="TWELVE_DATA",provider_contract="TWELVE_DATA_TIME_SERIES_D1_V1",provider_symbol=symbol,provider_instrument_type=provider_type,provider_exchange=None if exchange=="OTC" else exchange,provider_country=country,calendar_id=calendar,calendar_version=1,gap_doctrine_id="FRAGARACH_II_D1_GAP_DOCTRINE_V1",gap_doctrine_version=1)

def _rank(candidate,query):
    normalized=query.strip().upper();compact=re.sub(r"[^A-Z0-9]","",normalized);return (0 if candidate.provider_symbol==normalized or candidate.asset==compact else 1,candidate.asset,candidate.provider_symbol)
