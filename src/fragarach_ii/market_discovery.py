"""Deterministic market identity discovery and reviewed onboarding plans."""
from __future__ import annotations

import base64, json, re
from dataclasses import asdict, dataclass
from pathlib import Path

from .storage import open_read_only
from .truth_engine import TruthEngineError, truth_state_for_lane
from .fx_orientation import orientation_for
from .retirement import retirement_state

MARKET_DISCOVERY_CONTRACT = "fragarach_ii.market_discovery.v2"
_CURRENCIES = frozenset("AUD CAD CHF CNY EUR GBP HKD JPY NZD SGD USD ZAR".split())
_GAP = "FRAGARACH_II_D1_GAP_DOCTRINE_V1"

@dataclass(frozen=True, slots=True)
class Representation:
    representation_type:str; symbol:str; display_name:str; aliases:tuple[str,...]=()
    exchange:str|None=None; currency:str|None=None; contract_or_share_class:str|None=None
    provider:str|None=None; provider_symbol:str|None=None; provider_instrument_type:str|None=None

@dataclass(frozen=True, slots=True)
class MarketDefinition:
    underlying_market:str; canonical_identity:str; market_type:str; asset_class:str; description:str
    aliases:tuple[str,...]; timezone:str|None; sessions:tuple[str,...]; representations:tuple[Representation,...]; default_symbol:str|None=None

def R(kind,symbol,name,*aliases,exchange=None,currency="USD",detail=None,provider=None,provider_symbol=None,provider_type=None):
    return Representation(kind,symbol,name,aliases,exchange,currency,detail,provider,provider_symbol,provider_type)
def M(name,identity,kind,asset,description,aliases,reps,default=None,timezone="UTC",sessions=("WEEKDAY",)):
    return MarketDefinition(name,identity,kind,asset,description,aliases,timezone,sessions,reps,default)

_MARKETS=(
 M("Gold","COMMODITY:GOLD","PRECIOUS_METAL","METALS","International gold market.",( "XAU",),(
   R("SPOT","XAUUSD","Gold Spot / US Dollar","XAU/USD",exchange="OTC",provider="TWELVE_DATA",provider_symbol="XAU/USD",provider_type="Precious Metal"),R("CFD","GOLD CFD","Gold CFD",exchange="OTC"),R("FUTURES","GC","COMEX Gold Futures",exchange="COMEX",detail="Futures family; contract policy required"),R("ETF","GLD","SPDR Gold Shares",exchange="NYSE Arca",provider="TWELVE_DATA",provider_symbol="GLD",provider_type="ETF")),"XAUUSD"),
 M("Silver","COMMODITY:SILVER","PRECIOUS_METAL","METALS","International silver market with spot, CFD, futures and ETF representations.",( "XAG",),(
   R("SPOT","XAGUSD","Silver Spot / US Dollar","XAG/USD",exchange="OTC",provider="TWELVE_DATA",provider_symbol="XAG/USD",provider_type="Precious Metal"),R("CFD","XAGUSD CFD","Silver CFD",exchange="OTC"),R("FUTURES","SI","COMEX Silver Futures",exchange="COMEX",detail="Futures family; contract selection or continuous-series policy required"),R("ETF","SLV","iShares Silver Trust",exchange="NYSE Arca",provider="TWELVE_DATA",provider_symbol="SLV",provider_type="ETF")),"XAGUSD"),
 M("Platinum","COMMODITY:PLATINUM","PRECIOUS_METAL","METALS","International platinum market.",( "XPT",), (R("SPOT","XPTUSD","Platinum Spot / US Dollar","XPT/USD",exchange="OTC"),),"XPTUSD"),
 M("Palladium","COMMODITY:PALLADIUM","PRECIOUS_METAL","METALS","International palladium market.",( "XPD",), (R("SPOT","XPDUSD","Palladium Spot / US Dollar","XPD/USD",exchange="OTC"),),"XPDUSD"),
 M("Alphabet Inc.","COMPANY:ALPHABET","COMPANY_EQUITY","US_EQUITIES","Alphabet Inc., formerly Google Inc., with distinct listed share classes.",( "GOOGLE","GOOGLE INC","ALPHABET"),(
   R("COMMON_STOCK","GOOGL","Alphabet Class A Common Stock",exchange="NASDAQ",detail="Class A",provider="TWELVE_DATA",provider_symbol="GOOGL",provider_type="Common Stock"),R("COMMON_STOCK","GOOG","Alphabet Class C Capital Stock",exchange="NASDAQ",detail="Class C",provider="TWELVE_DATA",provider_symbol="GOOG",provider_type="Common Stock"))),
 M("Apple Inc.","COMPANY:APPLE","COMPANY_EQUITY","US_EQUITIES","Apple Inc. listed equity.",( "APPLE",),(R("COMMON_STOCK","AAPL","Apple Inc. Common Stock",exchange="NASDAQ",provider="TWELVE_DATA",provider_symbol="AAPL",provider_type="Common Stock"),),"AAPL"),
 M("Tesla, Inc.","COMPANY:TESLA","COMPANY_EQUITY","US_EQUITIES","Tesla listed equity.",( "TESLA",),(R("COMMON_STOCK","TSLA","Tesla, Inc. Common Stock",exchange="NASDAQ",provider="TWELVE_DATA",provider_symbol="TSLA",provider_type="Common Stock"),),"TSLA"),
 M("Microsoft Corporation","COMPANY:MICROSOFT","COMPANY_EQUITY","US_EQUITIES","Microsoft listed equity.",( "MICROSOFT",),(R("COMMON_STOCK","MSFT","Microsoft Common Stock",exchange="NASDAQ",provider="TWELVE_DATA",provider_symbol="MSFT",provider_type="Common Stock"),),"MSFT"),
 M("Amazon.com, Inc.","COMPANY:AMAZON","COMPANY_EQUITY","US_EQUITIES","Amazon listed equity.",( "AMAZON",),(R("COMMON_STOCK","AMZN","Amazon Common Stock",exchange="NASDAQ",provider="TWELVE_DATA",provider_symbol="AMZN",provider_type="Common Stock"),),"AMZN"),
 M("Meta Platforms, Inc.","COMPANY:META","COMPANY_EQUITY","US_EQUITIES","Meta Platforms, formerly Facebook.",( "META","FACEBOOK"),(R("COMMON_STOCK","META","Meta Platforms Common Stock",exchange="NASDAQ",provider="TWELVE_DATA",provider_symbol="META",provider_type="Common Stock"),),"META"),
 M("NVIDIA Corporation","COMPANY:NVIDIA","COMPANY_EQUITY","US_EQUITIES","NVIDIA listed equity.",( "NVIDIA",),(R("COMMON_STOCK","NVDA","NVIDIA Common Stock",exchange="NASDAQ",provider="TWELVE_DATA",provider_symbol="NVDA",provider_type="Common Stock"),),"NVDA"),
 M("BHP Group Limited — Australia","COMPANY:BHP:ASX","COMPANY_EQUITY","AUSTRALIAN_EQUITIES","BHP primary Australian listing.",( "BHP",),(R("COMMON_STOCK","ASX:BHP","BHP Group Limited",exchange="ASX",currency="AUD"),),"ASX:BHP",timezone="Australia/Sydney",sessions=("REGULAR",)),
 M("BHP Group Limited ADR — United States","COMPANY:BHP:NYSE","DEPOSITARY_RECEIPT","US_EQUITIES","BHP US depositary receipt.",( "BHP","BHP ADR"),(R("COMMON_STOCK","NYSE:BHP","BHP Group ADR",exchange="NYSE"),),"NYSE:BHP",timezone="America/New_York",sessions=("REGULAR",)),
 M("Dow Jones Industrial Average","INDEX:DJIA","EQUITY_INDEX","INDICES","Thirty large US companies represented by the Dow.",( "DOW","DOW JONES","DJIA"),(
   R("INDEX","DJI","Dow Jones Industrial Average Index","DJIA",exchange="US index market",provider="TWELVE_DATA",provider_symbol="DJI",provider_type="Index"),R("CFD","US30","US30 CFD","DJ30","WALL STREET 30",exchange="OTC"),R("ETF","DIA","SPDR Dow Jones ETF",exchange="NYSE Arca",provider="TWELVE_DATA",provider_symbol="DIA",provider_type="ETF"),R("INDEX","^DJI","Dow Jones index namespace symbol",exchange="Index namespace"),R("FUTURES","YM","E-mini Dow Futures",exchange="CBOT",detail="Futures family; contract policy required")),"DJI",timezone="America/New_York",sessions=("REGULAR",)),
 M("S&P 500","INDEX:SP500","EQUITY_INDEX","INDICES","Large-cap US equity index.",( "S&P500","SP500"),(R("INDEX","SPX","S&P 500 Index",exchange="Cboe"),R("CFD","US500","US500 CFD","SPX500",exchange="OTC"),R("ETF","SPY","SPDR S&P 500 ETF",exchange="NYSE Arca",provider="TWELVE_DATA",provider_symbol="SPY",provider_type="ETF"),R("FUTURES","ES","E-mini S&P Futures",exchange="CME",detail="Futures family; contract policy required")),"SPX"),
 M("Nasdaq 100","INDEX:NASDAQ100","EQUITY_INDEX","INDICES","Nasdaq 100 equity index.",( "NASDAQ 100",),(R("INDEX","NDX","Nasdaq 100 Index",exchange="NASDAQ"),R("CFD","US100","US100 CFD",exchange="OTC"),R("ETF","QQQ","Invesco QQQ",exchange="NASDAQ",provider="TWELVE_DATA",provider_symbol="QQQ",provider_type="ETF"),R("FUTURES","NQ","E-mini Nasdaq Futures",exchange="CME",detail="Futures family; contract policy required")),"NDX"),
 M("DAX","INDEX:DAX","EQUITY_INDEX","INDICES","German blue-chip equity index.",( "DE40","GER40"),(R("INDEX","DAX","DAX Index",exchange="Deutsche Börse"),R("CFD","DE40","Germany 40 CFD","GER40",exchange="OTC")),"DAX"),
 M("FTSE 100","INDEX:FTSE100","EQUITY_INDEX","INDICES","UK large-cap equity index.",( "UK100",),(R("INDEX","FTSE","FTSE 100 Index",exchange="FTSE Russell"),R("CFD","UK100","UK 100 CFD",exchange="OTC")),"FTSE"),
 M("S&P/ASX 200","INDEX:ASX200","EQUITY_INDEX","INDICES","Australian benchmark equity index.",( "ASX 200","AUS200"),(R("INDEX","XJO","S&P/ASX 200 Index",exchange="ASX"),R("CFD","AUS200","Australia 200 CFD",exchange="OTC",currency="AUD")),"XJO",timezone="Australia/Sydney"),
 M("West Texas Intermediate Crude Oil","COMMODITY:WTI","ENERGY_COMMODITY","ENERGY","US benchmark crude oil.",( "WTI","WEST TEXAS INTERMEDIATE"),(R("CFD","USOIL","US Oil CFD",exchange="OTC"),R("FUTURES","CL","WTI Crude Futures",exchange="NYMEX",detail="Futures family; contract policy required"),R("ETF","USO","United States Oil Fund",exchange="NYSE Arca",provider="TWELVE_DATA",provider_symbol="USO",provider_type="ETF")),"USOIL"),
 M("Brent Crude Oil","COMMODITY:BRENT","ENERGY_COMMODITY","ENERGY","Global Brent crude benchmark.",( "BRENT",),(R("CFD","UKOIL","UK Oil CFD",exchange="OTC"),R("FUTURES","BZ","Brent Futures",exchange="ICE",detail="Futures family; contract policy required")),"UKOIL"),
 M("Natural Gas","COMMODITY:NATGAS","ENERGY_COMMODITY","ENERGY","Natural gas market.",( "NATGAS",),(R("FUTURES","NG","Henry Hub Natural Gas Futures",exchange="NYMEX",detail="Futures family; contract policy required"),),"NG"),
 M("Copper","COMMODITY:COPPER","INDUSTRIAL_METAL","METALS","Copper market.",( "COPPER",),(R("FUTURES","HG","COMEX Copper Futures",exchange="COMEX",detail="Futures family; contract policy required"),),"HG"),
 M("Bitcoin","CRYPTO:BITCOIN","CRYPTO_ASSET","CRYPTO","Canonical Bitcoin market.",( "BTC",),(R("CRYPTO_SPOT_PAIR","BTCUSD","Bitcoin / US Dollar","BTC/USD",exchange="Digital asset venues",provider="TWELVE_DATA",provider_symbol="BTC/USD",provider_type="Digital Currency"),R("CRYPTO_SPOT_PAIR","BTCUSDT","Bitcoin / Tether","BTC/USDT",exchange="Digital asset venues")),"BTCUSD",sessions=("CONTINUOUS",)),
 M("Ethereum","CRYPTO:ETHEREUM","CRYPTO_ASSET","CRYPTO","Canonical Ethereum market.",( "ETH",),(R("CRYPTO_SPOT_PAIR","ETHUSD","Ethereum / US Dollar","ETH/USD",exchange="Digital asset venues",provider="TWELVE_DATA",provider_symbol="ETH/USD",provider_type="Digital Currency"),R("CRYPTO_SPOT_PAIR","ETHUSDT","Ethereum / Tether","ETH/USDT",exchange="Digital asset venues")),"ETHUSD",sessions=("CONTINUOUS",)),
 M("Solana","CRYPTO:SOLANA","CRYPTO_ASSET","CRYPTO","Canonical Solana market.",( "SOL",),(R("CRYPTO_SPOT_PAIR","SOLUSD","Solana / US Dollar","SOL/USD",exchange="Digital asset venues",provider="TWELVE_DATA",provider_symbol="SOL/USD",provider_type="Digital Currency"),R("CRYPTO_SPOT_PAIR","SOLUSDT","Solana / Tether","SOL/USDT",exchange="Digital asset venues",provider="TWELVE_DATA",provider_symbol="SOL/USDT",provider_type="Digital Currency")),"SOLUSD",sessions=("CONTINUOUS",)),
)

def discover_market(database_path:str|Path,query:str)->dict[str,object]:
    raw=query.strip()
    if not raw: raise ValueError("market discovery query is required")
    normalized=_normalize(raw); dynamic=_currency_market(normalized); definitions=(*_MARKETS,*((dynamic,) if dynamic else ()))
    if normalized=="OIL":
        chosen=[(95,"Generic oil-family alias; operator selection required.",None,d) for d in definitions if d.canonical_identity in {"COMMODITY:WTI","COMMODITY:BRENT"}]
        markets=tuple(_market_result(database_path,x[3],x[1],x[2],x[0]) for x in chosen)
        for market in markets:
            market["recommendation"]={"representation_type":"OPERATOR_SELECTION_REQUIRED","symbol":"","display_name":"Select a representation","reason":"Select the oil benchmark first.","alternatives":tuple(r["symbol"] for r in market["representations"])}
            market["required_operator_decisions"]=("Select the intended oil benchmark.","Select the intended tradable representation.")
            market["available_actions"]=()
        return {"contract":MARKET_DISCOVERY_CONTRACT,"query":raw,"discovery_status":"AMBIGUOUS","confidence":95,"markets":markets,"explanation":"Oil is a commodity-family term; select WTI or Brent.","suggested_searches":(),"similar_markets":(),"operator_guidance":"Select the intended oil benchmark.","required_operator_decisions":True}
    ranked=[(*_rank(d,normalized),d) for d in definitions]; ranked=[x for x in ranked if x[0]>0]; ranked.sort(key=lambda x:(-x[0],x[3].canonical_identity))
    if not ranked and len(normalized)>=5 and _edit_distance(normalized,"SOLANA")==1:
        definition=next(d for d in definitions if d.canonical_identity=="CRYPTO:SOLANA")
        market=_market_result(database_path,definition,"Restricted same-family spelling correction; operator confirmation required.",None,90)
        for representation in market["representations"]:representation["registration_plan"]=None;representation["acquisition_readiness"]="CORRECTION_CONFIRMATION_REQUIRED"
        market["recommendation"]={"representation_type":"OPERATOR_CONFIRMATION_REQUIRED","symbol":"","display_name":"Confirm Solana","reason":"Spelling correction requires confirmation.","alternatives":tuple(r["symbol"] for r in market["representations"])};market["available_actions"]=();market["required_operator_decisions"]=("Confirm the corrected Solana identity.",)
        return {"contract":MARKET_DISCOVERY_CONTRACT,"query":raw,"discovery_status":"PARTIAL","confidence":90,"markets":(market,),"explanation":"Did you mean Solana?","suggested_searches":("Did you mean Solana?",),"similar_markets":(),"operator_guidance":"Confirm Solana before selecting a representation or registering.","required_operator_decisions":True,"correction_required":True}
    if not ranked:return _unknown(raw)
    top=ranked[0][0]; chosen=[x for x in ranked if x[0]>=max(90,top-3)]
    markets=tuple(_market_result(database_path,x[3],x[1],x[2],x[0]) for x in chosen)
    requires_selection=len(markets)>1 or any(m["required_operator_decisions"] for m in markets)
    status="AMBIGUOUS" if len(markets)>1 else "PARTIAL" if top<95 else "KNOWN"
    return {"contract":MARKET_DISCOVERY_CONTRACT,"query":raw,"discovery_status":status,"confidence":top,"markets":markets,"explanation":"Market identity resolved independently from tradable representation and provider mapping.","suggested_searches":(),"similar_markets":(),"operator_guidance":"Select the intended market and representation before registration.","required_operator_decisions":requires_selection}

def _market_result(db,definition,reason,requested,confidence):
    registrations=_registrations(db); reps=[]; existing=[]
    for r in definition.representations:
        reg=_registration_for(r,registrations); retired=retirement_state(db,r.symbol);context=_registration_context(db,reg,retired) if reg else None
        if context:existing.append(context)
        plan=_registration_plan(definition,r) if not reg and not retired else None
        warning=_warning(r)
        lanes=_timeframe_lanes(r,definition,registrations,retired)
        reps.append({**asdict(r),"registration_status":retired["lifecycle_state"] if retired else reg[1] if reg else "NOT_REGISTERED","provider_mapping_status":"KNOWN_MAPPING" if r.provider_symbol else "DISCOVERY_REQUIRED","acquisition_readiness":"HISTORICAL_ONLY" if retired else "READY_FOR_REGISTRATION" if plan else "OPEN_EXISTING" if reg else "PROVIDER_DISCOVERY_REQUIRED","warnings":tuple(filter(None,(warning,))),"registration_plan":plan,"timeframe_lanes":lanes,"retirement":retired})
    selected=requested or (None if definition.canonical_identity in {"COMPANY:ALPHABET","COMMODITY:SILVER"} else definition.default_symbol)
    recommendation=next((r for r in reps if r["symbol"]==selected),None)
    providers=tuple(_provider_mapping(r,_registration_for(r,registrations)) for r in definition.representations)
    result={"underlying_market":definition.underlying_market,"canonical_identity":definition.canonical_identity,"confidence":confidence,"market_type":definition.market_type,"asset_class":definition.asset_class,"description":definition.description,"known_aliases":definition.aliases,"representations":tuple(reps),"provider_discovery":providers,"recommendation":{"representation_type":recommendation["representation_type"] if recommendation else "OPERATOR_SELECTION_REQUIRED","symbol":recommendation["symbol"] if recommendation else "","display_name":recommendation["display_name"] if recommendation else "Select a representation","reason":reason,"alternatives":tuple(r.symbol for r in definition.representations if r.symbol!=selected)},"metadata":{"market":definition.underlying_market,"asset_class":definition.asset_class,"exchange":recommendation["exchange"] if recommendation else None,"timezone":definition.timezone,"sessions":definition.sessions,"currencies":tuple(dict.fromkeys(r.currency for r in definition.representations if r.currency)),"aliases":definition.aliases,"provider_mappings":tuple(p["known_symbol"] for p in providers if p["known_symbol"]),"registration_state":"REGISTERED" if existing else "NOT_REGISTERED"},"existing_registrations":tuple(existing),"acquisition_readiness":recommendation["acquisition_readiness"] if recommendation else "REPRESENTATION_SELECTION_REQUIRED","resolution_reason":reason,"required_operator_decisions":(() if recommendation else ("Select the intended tradable representation.",)),"available_actions":(("OPEN_EXISTING",) if recommendation and recommendation["registration_status"]!="NOT_REGISTERED" else ("ADD_TO_FRAGARACH",) if recommendation and recommendation["registration_plan"] else ())}
    if recommendation and recommendation.get("retirement"):
        result["available_actions"]=("VIEW_RETIREMENT",);result["acquisition_readiness"]="DISABLED_RETIRED";result["metadata"]["registration_state"]="HISTORICAL_RETIRED"
    if definition.asset_class=="FX":
        orientation=orientation_for(definition.canonical_identity.split(":",1)[1]);result["fx_orientation"]=orientation
        if orientation["orientation_state"]!="DIRECT_PROVIDER_SUPPORTED":result["available_actions"]=("OPEN_INVERSE",) if orientation["orientation_state"]=="INVERSE_ONLY" else ();result["acquisition_readiness"]=orientation["acquisition_readiness"]
    return result

def _registration_plan(m,r):
    if not r.provider_symbol:return None
    calendar="FX_D1_V1" if r.representation_type=="FX_SPOT_PAIR" else "CRYPTO_D1_V1" if r.representation_type=="CRYPTO_SPOT_PAIR" else "METALS_D1_V1" if m.asset_class=="METALS" else "US_EQUITIES_D1_V1" if m.asset_class=="US_EQUITIES" else "INDICES_D1_V1"
    asset=re.sub(r"[^A-Z0-9._-]","",r.symbol.upper())
    candidate={"asset":asset,"timeframe":"D1","instrument_family":asset,"local_symbol":asset,"display_name":r.display_name,"instrument_type":r.provider_instrument_type.upper().replace(" ","_") if r.provider_instrument_type else r.representation_type,"asset_class":m.asset_class,"representation_type":r.representation_type,"trading_currency":r.currency or "USD","exchange_name":r.exchange or "UNKNOWN","provider_id":r.provider,"provider_contract":"TWELVE_DATA_TIME_SERIES_D1_V1","provider_symbol":r.provider_symbol,"provider_instrument_type":r.provider_instrument_type or r.representation_type,"calendar_id":calendar,"calendar_version":1,"gap_doctrine_id":_GAP,"gap_doctrine_version":1,"aliases":[],"underlying_reference":m.canonical_identity,"contract_or_series":r.contract_or_share_class,"jurisdiction":None,"exchange_mic":None,"provider_exchange":None if r.exchange=="OTC" else r.exchange,"provider_country":None}
    payload=base64.urlsafe_b64encode(json.dumps(candidate,sort_keys=True,separators=(",",":")).encode()).decode()
    return {"underlying_market":m.underlying_market,"selected_representation":r.symbol,"canonical_registration_symbol":asset,"display_name":r.display_name,"asset_class":m.asset_class,"instrument_type":candidate["instrument_type"],"exchange_or_venue":r.exchange,"timezone":m.timezone,"session_authority":calendar,"base_currency":asset[:3] if r.representation_type in ("FX_SPOT_PAIR","CRYPTO_SPOT_PAIR","SPOT") and len(asset)>=6 else None,"quote_currency":r.currency,"provider_mappings":({"provider":r.provider,"symbol":r.provider_symbol,"state":"KNOWN_MAPPING"},),"known_unknowns":(),"registration_warnings":tuple(filter(None,(_warning(r),))),"candidate":payload}

def _timeframe_lanes(r,m,rows,retired=None):
    orientation=orientation_for(m.canonical_identity.split(":",1)[1]) if m.asset_class=="FX" else None
    lanes=[]
    for timeframe in ("D1","H1","M30","M5"):
        if retired and timeframe in retired["selected_lanes"]:
            lanes.append({"timeframe":timeframe,"registration_state":"RETIRED","provider_capability":"HISTORICAL_ONLY","provider_mapping":"PRESERVED","authority_state":retired["lifecycle_state"],"acquisition_readiness":"UNSUPPORTED","reason":"Retired authority; evidence is preserved and quarantined.","selectable":False});continue
        existing=next((row for row in rows if json.loads(row[0]).get("timeframe")==timeframe and _registration_for(r,(row,))),None)
        if orientation and orientation["orientation_state"]!="DIRECT_PROVIDER_SUPPORTED":
            state="INVERSE_ONLY" if orientation["orientation_state"]=="INVERSE_ONLY" else "CAPABILITY_UNKNOWN";reason=f"Capability belongs to authoritative inverse {orientation['inverse_pair']} mapping; no direct mapping exists." if state=="INVERSE_ONLY" else "No direct or inverse provider mapping evidence exists."
            lanes.append({"timeframe":timeframe,"registration_state":"REGISTERED_UNMAPPED" if existing else "IMPLEMENTATION_INCOMPATIBILITY","provider_capability":state,"provider_mapping":state,"authority_state":orientation["orientation_state"],"acquisition_readiness":"MAPPING_REQUIRED","reason":reason+" Canonical identity and unrelated operations remain available.","selectable":False});continue
        mapped=bool(r.provider_symbol)
        if timeframe=="D1": capability="SUPPORTED" if mapped else "MAPPING_REQUIRED"; reason="Approved D1 provider contract and calendar authority." if mapped else "Provider mapping required."
        elif m.asset_class in {"FX","CRYPTO"} and mapped: capability="SUPPORTED";reason=f"Approved TWELVE_DATA_TIME_SERIES_{timeframe}_V1 provider contract; registration schema remains D1-only."
        else: capability="CAPABILITY_UNKNOWN";reason="No approved representation-specific intraday calendar assignment is registered."
        registration="EXISTING" if existing else "MISSING" if timeframe=="D1" and capability=="SUPPORTED" else "IMPLEMENTATION_INCOMPATIBILITY" if capability=="SUPPORTED" else "MISSING"
        acquisition="NOT_YET_ACQUIRED" if existing else "REGISTRATION_REQUIRED" if registration=="MISSING" and capability=="SUPPORTED" else "CAPABILITY_UNKNOWN" if capability=="CAPABILITY_UNKNOWN" else "MAPPING_REQUIRED" if capability=="MAPPING_REQUIRED" else "IMPLEMENTATION_INCOMPATIBILITY"
        lanes.append({"timeframe":timeframe,"registration_state":registration,"provider_capability":capability,"provider_mapping":"KNOWN_MAPPING" if mapped else "MAPPING_REQUIRED","authority_state":"D1_REGISTRATION_AUTHORITY" if timeframe=="D1" else "IMPLEMENTATION_NARROWER_THAN_RATIFIED_AUTHORITY" if capability=="SUPPORTED" else "AUTHORITY_PRESENT_CAPABILITY_UNKNOWN","acquisition_readiness":acquisition,"reason":reason,"selectable":timeframe=="D1" and registration=="MISSING" and capability=="SUPPORTED"})
    return tuple(lanes)

def _warning(r):
    if r.representation_type=="FUTURES":return "Futures family recognised. Contract selection or continuous-series policy required."
    if not r.provider_symbol:return "Provider mapping and entitlement remain unresolved; registration is unavailable."
    return "Provider entitlement is unknown and must be checked before acquisition."
def _provider_mapping(r,registration):return {"representation_symbol":r.symbol,"provider":r.provider or "UNRESOLVED","availability":"KNOWN_MAPPING" if r.provider_symbol else "DISCOVERY_REQUIRED","mapping_state":"KNOWN_MAPPING" if r.provider_symbol else "DISCOVERY_REQUIRED","supported_timeframes":("D1",) if r.provider_symbol else (),"entitlement":"NOT_MEASURED","readiness":"PARTIALLY_READY" if r.provider_symbol else "DISCOVERY_REQUIRED","confidence":100 if r.provider_symbol else None,"known_symbol":r.provider_symbol,"evidence_source":"Deterministic Fragarach catalogue" if r.provider_symbol else "None","registration_status":registration[1] if registration else "NOT_REGISTERED"}
def _registrations(db):
    c=open_read_only(db)
    try:return c.execute("SELECT identity_json,registration_status,registration_contract_version FROM instrument_registrations ORDER BY asset,timeframe").fetchall()
    finally:c.close()
def _registration_for(r,rows):
    names={_normalize(r.symbol),_normalize(r.provider_symbol or "")}
    for identity,status,version in rows:
        v=json.loads(identity)
        if names & {_normalize(str(v.get(k,""))) for k in ("asset","local_symbol","provider_symbol")}:return v,status,version
def _registration_context(db,reg,retired=None):
    v,status,version=reg;truth=None
    try:truth=truth_state_for_lane(db,symbol=v["asset"],timeframe="D1")
    except TruthEngineError:pass
    return {"canonical_symbol":v["asset"],"registration_status":retired["lifecycle_state"] if retired else status,"registration_version":version,"authority_state":retired["lifecycle_state"] if retired else truth["authority_state"] if truth else status,"truth_score":truth["truth_score"] if truth else None,"caodt":truth["caodt"] if truth else None,"validation_state":truth["validation_state"] if truth else "NOT_MEASURED","acquisition_state":"DISABLED_RETIRED" if retired else "READY" if v.get("provider_symbol") else "PROVIDER_DISCOVERY_REQUIRED","retirement":retired}
def _rank(d,q):
    if q==_normalize(d.canonical_identity):return 100,"Exact canonical identity match.",None
    for r in d.representations:
        if q in {_normalize(r.symbol),*(_normalize(a) for a in r.aliases)}:return 99,"Exact tradable representation symbol match.",r.symbol
    if q in {_normalize(a) for a in d.aliases}:return 98,"Exact financial alias or trading name match.",None
    if q==_normalize(d.underlying_market):return 97,"Exact market or company name match.",None
    tokens=set(q.split()); name_tokens=set(_normalize(d.underlying_market).split())|set().union(*[set(_normalize(a).split()) for a in d.aliases])
    if len(q)>=3 and tokens & name_tokens:return 78,"Token-aware partial market name match.",None
    return 0,"",None
def _currency_market(q):
    compact=re.sub(r"[^A-Z]","",q)
    if len(compact)!=6 or compact[:3] not in _CURRENCIES or compact[3:] not in _CURRENCIES or compact[:3]==compact[3:]:return None
    base,quote=compact[:3],compact[3:];orientation=orientation_for(compact);provider_symbol=orientation["requested_provider_symbol"]
    return M(f"{base} / {quote}",f"FX:{compact}","FOREIGN_EXCHANGE","FX",f"Ordered foreign-exchange identity for {base} against {quote}.",(compact,f"{base}/{quote}"),(R("FX_SPOT_PAIR",compact,f"{base} / {quote} Spot",f"{base}/{quote}",exchange="OTC",currency=quote,provider="TWELVE_DATA" if provider_symbol else None,provider_symbol=provider_symbol,provider_type="Physical Currency" if provider_symbol else None),),compact)
def _unknown(raw):return {"contract":MARKET_DISCOVERY_CONTRACT,"query":raw,"discovery_status":"UNKNOWN","confidence":0,"markets":(),"explanation":"No recognised market identity found.","search_attempted":("canonical markets","tradable representations","aliases","company names","index names","commodity names","ISO currency pairs"),"suggested_searches":("Try a canonical market or company name.","Try a listed symbol or known financial alias."),"similar_markets":(),"operator_guidance":"Check the spelling or enter a canonical market name, listed symbol, or known financial alias.","required_operator_decisions":False}
def _normalize(v):return re.sub(r"[^A-Z0-9^&]+"," ",v.strip().upper()).strip()
def _edit_distance(a,b):
    previous=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        current=[i]
        for j,cb in enumerate(b,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(ca!=cb)))
        previous=current
    return previous[-1]
