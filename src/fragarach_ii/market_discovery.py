"""Deterministic market identity discovery and reviewed onboarding plans."""
from __future__ import annotations

import base64, json, re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlencode

from .storage import open_read_only
from .truth_engine import TruthEngineError, truth_state_for_lane
from .fx_orientation import orientation_for
from .retirement import removal_state,retirement_state
from .market_registry import load_registry,provider_mapping,ranked_text_match,search_registry
from .lane_commissioning import market_policy
from .acquisition_orchestrator import acquisition_capability_projection, load_provider_profiles
from .provider_facts import representation_mapping
from .providers.yahoo_symbols import yahoo_equity_symbol_for_representation
from .providers.config import load_provider_config
from .providers.http import BoundedHttpsTransport, HttpRequest
from .credentials import CredentialAuthority
from .twelve_data_credit import credited_send

MARKET_DISCOVERY_CONTRACT = "fragarach_ii.market_discovery.v2"
_CURRENCIES = frozenset("AUD CAD CHF CNY EUR GBP HKD JPY NZD SGD USD ZAR".split())
_GAP = "FRAGARACH_II_D1_GAP_DOCTRINE_V1"

@dataclass(frozen=True, slots=True)
class Representation:
    representation_type:str; symbol:str; display_name:str; aliases:tuple[str,...]=()
    exchange:str|None=None; currency:str|None=None; contract_or_share_class:str|None=None
    provider:str|None=None; provider_symbol:str|None=None; provider_instrument_type:str|None=None
    catalogue_verified:bool=False

@dataclass(frozen=True, slots=True)
class MarketDefinition:
    underlying_market:str; canonical_identity:str; market_type:str; asset_class:str; description:str
    aliases:tuple[str,...]; timezone:str|None; sessions:tuple[str,...]; representations:tuple[Representation,...]; default_symbol:str|None=None

def R(kind,symbol,name,*aliases,exchange=None,currency="USD",detail=None,provider=None,provider_symbol=None,provider_type=None,catalogue_verified=False):
    return Representation(kind,symbol,name,aliases,exchange,currency,detail,provider,provider_symbol,provider_type,catalogue_verified)
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
 M("BHP Group Limited — Australia","COMPANY:BHP:ASX","COMPANY_EQUITY","AUSTRALIAN_EQUITIES","BHP primary Australian listing.",( "BHP",),(R("COMMON_STOCK","ASX:BHP","BHP Group Limited",exchange="ASX",currency="AUD",provider="YAHOO_FINANCE",provider_type="Common Stock"),),"ASX:BHP",timezone="Australia/Sydney",sessions=("REGULAR",)),
 M("BHP Group Limited ADR — United States","COMPANY:BHP:NYSE","DEPOSITARY_RECEIPT","US_EQUITIES","BHP US depositary receipt.",( "BHP","BHP ADR"),(R("DEPOSITARY_RECEIPT","NYSE:BHP","BHP Group ADR",exchange="NYSE",provider="YAHOO_FINANCE",provider_type="Depositary Receipt"),),"NYSE:BHP",timezone="America/New_York",sessions=("REGULAR",)),
 M("Rio Tinto plc — United Kingdom","COMPANY:RIO:LSE","COMPANY_EQUITY","UK_EQUITIES","Rio Tinto primary London listing.",( "RIO","RIO TINTO"),(R("COMMON_STOCK","LSE:RIO","Rio Tinto plc",exchange="LSE",currency="GBP",provider="YAHOO_FINANCE",provider_type="Common Stock"),),"LSE:RIO",timezone="Europe/London",sessions=("REGULAR",)),
 M("Rio Tinto plc ADR — United States","COMPANY:RIO:NYSE","DEPOSITARY_RECEIPT","US_EQUITIES","Rio Tinto US depositary receipt.",( "RIO","RIO ADR"),(R("DEPOSITARY_RECEIPT","NYSE:RIO","Rio Tinto plc ADR",exchange="NYSE",provider="YAHOO_FINANCE",provider_type="Depositary Receipt"),),"NYSE:RIO",timezone="America/New_York",sessions=("REGULAR",)),
 M("Rio Tinto Limited — Australia","COMPANY:RIO:ASX","COMPANY_EQUITY","AUSTRALIAN_EQUITIES","Rio Tinto Australian listed ordinary shares.",( "RIO","RIO TINTO"),(R("COMMON_STOCK","ASX:RIO","Rio Tinto Limited",exchange="ASX",currency="AUD",provider="YAHOO_FINANCE",provider_type="Common Stock"),),"ASX:RIO",timezone="Australia/Sydney",sessions=("REGULAR",)),
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

def discover_market(
    database_path:str|Path,query:str,*,resolve_crypto_catalogue:bool=False,
)->dict[str,object]:
    raw=query.strip()
    if not raw: raise ValueError("market discovery query is required")
    normalized=_normalize(raw);snapshot=load_registry();registry_records=search_registry(raw,snapshot);registry_definitions=[]
    for record in registry_records:
        legacy=next((market for market in _MARKETS if any(_normalize(rep.symbol)==_normalize(record["canonical_symbol"]) for rep in market.representations)),None)
        # The immutable registry seeds reviewed mappings, while the provider
        # fact store holds later bounded reference lookups.  Discover must use
        # either exact authority source; otherwise a verified non-Estate FX
        # pair stays incorrectly labelled "Provider Mapping Required".
        mapping = provider_mapping(snapshot, record["registry_id"]) or _runtime_exact_mapping(
            database_path, record["canonical_symbol"]
        )
        catalogue_mapping=(
            _twelve_data_crypto_catalogue_mapping(record)
            if resolve_crypto_catalogue else None
        )
        definition=legacy or _registry_market(
            record,mapping or catalogue_mapping or _configured_crypto_d1_mapping(record)
        )
        if definition.canonical_identity not in {d.canonical_identity for d in registry_definitions}:registry_definitions.append(definition)
    dynamic=_currency_market(normalized);legacy_exact=any(_rank(m,normalized)[0]>=90 for m in _MARKETS)
    # A syntactically valid ordered FX pair is an exact canonical identity. It
    # must outrank fuzzy registry suggestions such as similarly named crypto
    # assets and must preserve the requested base/quote orientation. Prefer its
    # exact registry definition when present so reviewed/runtime provider facts
    # remain attached to that ordered pair.
    dynamic_registry=next((
        definition for definition in registry_definitions
        if dynamic and any(
            _compact_symbol(representation.symbol)==_compact_symbol(dynamic.representations[0].symbol)
            for representation in definition.representations
        )
    ),None)
    definitions=((dynamic_registry or dynamic),) if dynamic else (*_MARKETS,) if legacy_exact or not registry_definitions else tuple(registry_definitions)
    if normalized=="OIL":
        chosen=[(95,"Generic oil-family alias; operator selection required.",None,d) for d in definitions if d.canonical_identity in {"COMMODITY:WTI","COMMODITY:BRENT"}]
        markets=tuple(_market_result(database_path,x[3],x[1],x[2],x[0]) for x in chosen)
        for market in markets:
            market["recommendation"]={"representation_type":"OPERATOR_SELECTION_REQUIRED","symbol":"","display_name":"Select a representation","reason":"Select the oil benchmark first.","alternatives":tuple(r["symbol"] for r in market["representations"])}
            market["required_operator_decisions"]=("Select the intended oil benchmark.","Select the intended tradable representation.")
            market["available_actions"]=()
        return {"contract":MARKET_DISCOVERY_CONTRACT,"query":raw,"discovery_status":"AMBIGUOUS","confidence":95,"markets":markets,"explanation":"Oil is a commodity-family term; select WTI or Brent.","suggested_searches":(),"similar_markets":(),"operator_guidance":"Select the intended oil benchmark.","required_operator_decisions":True}
    ranked=[(*_rank(d,normalized),d) for d in definitions]; ranked=[x for x in ranked if x[0]>0]; ranked.sort(key=lambda x:(-x[0],x[3].canonical_identity))
    if len(normalized)>=5 and _edit_distance(normalized,"SOLANA")==1:
        definition=next(d for d in _MARKETS if d.canonical_identity=="CRYPTO:SOLANA")
        market=_market_result(database_path,definition,"Restricted same-family spelling correction; operator confirmation required.",None,90)
        for representation in market["representations"]:representation["registration_plan"]=None;representation["acquisition_readiness"]="CORRECTION_CONFIRMATION_REQUIRED"
        market["recommendation"]={"representation_type":"OPERATOR_CONFIRMATION_REQUIRED","symbol":"","display_name":"Confirm Solana","reason":"Spelling correction requires confirmation.","alternatives":tuple(r["symbol"] for r in market["representations"])};market["available_actions"]=();market["required_operator_decisions"]=("Confirm the corrected Solana identity.",)
        return {"contract":MARKET_DISCOVERY_CONTRACT,"query":raw,"discovery_status":"PARTIAL","confidence":90,"markets":(market,),"explanation":"Did you mean Solana?","suggested_searches":("Did you mean Solana?",),"similar_markets":(),"operator_guidance":"Confirm Solana before selecting a representation or registering.","required_operator_decisions":True,"correction_required":True}
    if not ranked:return _unknown(raw)
    top=ranked[0][0]
    floor=top-3 if top>=95 else max(80,top-7)
    chosen=[x for x in ranked if x[0]>=floor][:8]
    markets=tuple(_market_result(database_path,x[3],x[1],x[2],x[0]) for x in chosen)
    requires_selection=len(markets)>1 or any(m["required_operator_decisions"] for m in markets)
    status="AMBIGUOUS" if len(markets)>1 else "PARTIAL" if top<95 else "KNOWN"
    suggestions=tuple(dict.fromkeys(
        market["recommendation"]["symbol"] or market["representations"][0]["symbol"]
        for market in markets if market["representations"]
    )) if top<95 else ()
    explanation="Showing ranked suggestions; select the intended market." if top<95 else "Market identity resolved independently from tradable representation and provider mapping."
    return {"contract":MARKET_DISCOVERY_CONTRACT,"query":raw,"discovery_status":status,"confidence":top,"markets":markets,"explanation":explanation,"suggested_searches":suggestions,"similar_markets":tuple(market["underlying_market"] for market in markets) if top<95 else (),"operator_guidance":"Select the intended market and representation before registration.","required_operator_decisions":requires_selection}

def _market_result(db,definition,reason,requested,confidence):
    registrations=_registrations(db); reps=[]; existing=[]
    for r in definition.representations:
        physical_reg=_registration_for(r,registrations); retired=retirement_state(db,r.symbol);removed=removal_state(db,r.symbol);reg=None if removed else physical_reg;context=_registration_context(db,reg,retired) if reg else None
        if context:existing.append(context)
        approved=_approved_provider_mapping(db,r,reg)
        provider_symbol=_provider_symbol(r)
        review_required=bool(r.provider=="YAHOO_FINANCE" and provider_symbol and not approved)
        setup_needed=bool(reg and reg[1]=="REGISTERED_UNMAPPED" and provider_symbol and not approved)
        plan=_registration_plan(definition,r) if ((not reg or setup_needed) and not retired and (provider_symbol or r.representation_type=="FX_SPOT_PAIR")) else None
        warning=_warning(r)
        lanes=_timeframe_lanes(db,r,definition,() if removed else registrations,retired)
        mapping_status="APPROVED_REPRESENTATION" if approved else "REVIEW_REQUIRED" if review_required else "KNOWN_MAPPING" if provider_symbol else "MAPPING_REQUIRED" if r.provider=="YAHOO_FINANCE" else "DISCOVERY_REQUIRED"
        readiness="HISTORICAL_ONLY" if retired else "PROVIDER_SETUP_INCOMPLETE" if setup_needed else "READY_FOR_REGISTRATION" if plan else "OPEN_EXISTING" if reg else "PROVIDER_DISCOVERY_REQUIRED"
        reps.append({**asdict(r),"provider_symbol":provider_symbol,"registration_status":retired["lifecycle_state"] if retired else "PERMANENTLY_REMOVED" if removed else _publication_status(db,reg) if reg else "NOT_REGISTERED","provider_mapping_status":mapping_status,"acquisition_readiness":readiness,"warnings":tuple(filter(None,(warning,))),"registration_plan":plan,"timeframe_lanes":lanes,"retirement":retired,"removal":removed})
    selected=requested or (None if definition.canonical_identity in {"COMPANY:ALPHABET","COMMODITY:SILVER"} else definition.default_symbol)
    recommendation=next((r for r in reps if r["symbol"]==selected),None)
    providers=tuple(_provider_mapping(r,None if removal_state(db,r.symbol) else _registration_for(r,registrations),bool(_approved_provider_mapping(db,r,None if removal_state(db,r.symbol) else _registration_for(r,registrations)))) for r in definition.representations)
    result={"underlying_market":definition.underlying_market,"canonical_identity":definition.canonical_identity,"confidence":confidence,"market_type":definition.market_type,"asset_class":definition.asset_class,"description":definition.description,"known_aliases":definition.aliases,"representations":tuple(reps),"provider_discovery":providers,"recommendation":{"representation_type":recommendation["representation_type"] if recommendation else "OPERATOR_SELECTION_REQUIRED","symbol":recommendation["symbol"] if recommendation else "","display_name":recommendation["display_name"] if recommendation else "Select a representation","reason":reason,"alternatives":tuple(r.symbol for r in definition.representations if r.symbol!=selected)},"metadata":{"market":definition.underlying_market,"asset_class":definition.asset_class,"exchange":recommendation["exchange"] if recommendation else None,"timezone":definition.timezone,"sessions":definition.sessions,"currencies":tuple(dict.fromkeys(r.currency for r in definition.representations if r.currency)),"aliases":definition.aliases,"provider_mappings":tuple(p["known_symbol"] for p in providers if p["known_symbol"]),"registration_state":"REGISTERED" if existing else "NOT_REGISTERED"},"existing_registrations":tuple(existing),"acquisition_readiness":recommendation["acquisition_readiness"] if recommendation else "REPRESENTATION_SELECTION_REQUIRED","resolution_reason":reason,"required_operator_decisions":(() if recommendation else ("Select the intended tradable representation.",)),"available_actions":(("COMPLETE_PROVIDER_SETUP",) if recommendation and recommendation["acquisition_readiness"]=="PROVIDER_SETUP_INCOMPLETE" else ("OPEN_EXISTING",) if recommendation and recommendation["registration_status"]!="NOT_REGISTERED" else ("ADD_TO_FRAGARACH",) if recommendation and recommendation["registration_plan"] else ())}
    if recommendation and recommendation.get("retirement"):
        result["available_actions"]=("REACTIVATE","PERMANENTLY_REMOVE","VIEW_RETIREMENT");result["acquisition_readiness"]="DISABLED_RETIRED";result["metadata"]["registration_state"]="HISTORICAL_RETIRED"
    elif recommendation and recommendation.get("removal"):
        result["available_actions"]=("ADD_TO_FRAGARACH",);result["acquisition_readiness"]="READY_FOR_REGISTRATION";result["metadata"]["registration_state"]="PERMANENTLY_REMOVED"
    if definition.asset_class=="FX":
        orientation=orientation_for(definition.canonical_identity.split(":",1)[1]);result["fx_orientation"]=orientation
        if orientation["orientation_state"]!="DIRECT_PROVIDER_SUPPORTED":
            if recommendation and recommendation["registration_status"]=="NOT_REGISTERED":result["available_actions"]=("ADD_TO_FRAGARACH","OPEN_INVERSE") if orientation["orientation_state"]=="INVERSE_ONLY" else ("ADD_TO_FRAGARACH",)
            result["acquisition_readiness"]="READY_FOR_UNMAPPED_REGISTRATION" if recommendation and recommendation.get("registration_plan") else orientation["acquisition_readiness"]
    return result

def _registration_plan(m,r):
    calendar=_registration_calendar_id(m,r)
    asset=re.sub(r"[^A-Z0-9._-]","",r.symbol.upper())
    provider_symbol=_provider_symbol(r)
    provider_contract={
        "TWELVE_DATA":"TWELVE_DATA_TIME_SERIES_D1_V1",
        "YAHOO_FINANCE":"YAHOO_FINANCE_CHART_D1_V1",
        "BINANCE":"BINANCE_KLINES_V1",
        "COINGECKO":"COINGECKO_OHLC_V1",
    }.get(r.provider)
    registration_representation="COMMON_STOCK" if r.representation_type=="DEPOSITARY_RECEIPT" else r.representation_type
    candidate={"asset":asset,"timeframe":"D1","instrument_family":asset,"local_symbol":asset,"selected_representation":r.symbol,"display_name":r.display_name,"instrument_type":r.provider_instrument_type.upper().replace(" ","_") if r.provider_instrument_type else r.representation_type,"asset_class":m.asset_class,"representation_type":registration_representation,"trading_currency":r.currency or "USD","exchange_name":r.exchange or "UNKNOWN","provider_id":r.provider,"provider_contract":provider_contract,"provider_symbol":provider_symbol,"provider_instrument_type":r.provider_instrument_type if r.provider else None,"calendar_id":calendar,"calendar_version":1,"gap_doctrine_id":_GAP,"gap_doctrine_version":1,"aliases":[],"underlying_reference":m.canonical_identity,"contract_or_series":r.contract_or_share_class,"jurisdiction":None,"exchange_mic":None,"provider_exchange":None if not r.provider or r.exchange=="OTC" else r.exchange,"provider_country":None}
    payload=base64.urlsafe_b64encode(json.dumps(candidate,sort_keys=True,separators=(",",":")).encode()).decode()
    mappings=({"provider":r.provider,"symbol":provider_symbol,"state":"SELECTED_FOR_REVIEW"},) if provider_symbol else ()
    return {"underlying_market":m.underlying_market,"selected_representation":r.symbol,"canonical_registration_symbol":asset,"display_name":r.display_name,"asset_class":m.asset_class,"instrument_type":candidate["instrument_type"],"exchange_or_venue":r.exchange,"timezone":m.timezone,"session_authority":calendar,"base_currency":asset[:3] if r.representation_type in ("FX_SPOT_PAIR","CRYPTO_SPOT_PAIR","SPOT") and len(asset)>=6 else None,"quote_currency":r.currency,"provider_mappings":mappings,"known_unknowns":(("Provider representation requires operator approval",) if provider_symbol else ("Provider mapping required",)),"registration_warnings":tuple(filter(None,(_warning(r),))),"candidate":payload}

def _registration_calendar_id(m,r):
    if r.representation_type=="FX_SPOT_PAIR":return "FX_D1_V1"
    if r.representation_type=="CRYPTO_SPOT_PAIR":return "CRYPTO_D1_V1"
    if m.asset_class=="METALS":return "METALS_D1_V1"
    if m.asset_class=="US_EQUITIES":return "US_EQUITIES_D1_V1"
    if m.asset_class=="AUSTRALIAN_EQUITIES":return "AUSTRALIAN_EQUITIES_D1_V1"
    if m.asset_class=="UK_EQUITIES":return "UK_EQUITIES_D1_V1"
    return "REGISTRY_D1_V1"

def _provider_symbol(r):
    if r.provider=="YAHOO_FINANCE":
        return yahoo_equity_symbol_for_representation(r.symbol,r.exchange)
    return r.provider_symbol

def _timeframe_lanes(db,r,m,rows,retired=None):
    orientation=orientation_for(m.canonical_identity.split(":",1)[1]) if m.asset_class=="FX" else None
    projection=acquisition_capability_projection(db,symbol=r.symbol)
    lanes=[]
    for timeframe in ("D1","H1","M30","M5"):
        if retired and timeframe in retired["selected_lanes"]:
            lanes.append({"timeframe":timeframe,"registration_state":"RETIRED","provider_capability":"HISTORICAL_ONLY","provider_mapping":"PRESERVED","authority_state":retired["lifecycle_state"],"acquisition_readiness":"UNSUPPORTED","reason":"Retired authority; evidence is preserved and quarantined.","selectable":False});continue
        existing=next((row for row in rows if json.loads(row[0]).get("timeframe")==timeframe and _registration_for(r,(row,))),None)
        facts=[item for item in projection["rows"] if item["timeframe"]==timeframe]
        resolved_representation=any(item.get("mapping_status") in {"EXACT_REPRESENTATION","APPROVED_PROVIDER_ALIAS"} for item in facts)
        if orientation and orientation["orientation_state"]!="DIRECT_PROVIDER_SUPPORTED" and not resolved_representation:
            state="INVERSE_ONLY" if orientation["orientation_state"]=="INVERSE_ONLY" else "CAPABILITY_UNKNOWN";reason=f"Capability belongs to authoritative inverse {orientation['inverse_pair']} mapping; no direct mapping exists." if state=="INVERSE_ONLY" else "No direct or inverse provider mapping evidence exists."
            lanes.append({"timeframe":timeframe,"registration_state":"REGISTERED_UNMAPPED" if existing else "IMPLEMENTATION_INCOMPATIBILITY","provider_capability":state,"provider_mapping":state,"authority_state":orientation["orientation_state"],"acquisition_readiness":"MAPPING_REQUIRED","reason":reason+" Canonical identity and unrelated operations remain available.","selectable":False});continue
        catalogue_exact_crypto=(
            m.asset_class=="CRYPTO"
            and r.provider=="TWELVE_DATA"
            and r.catalogue_verified
            and _compact_symbol(_provider_symbol(r) or "") == _compact_symbol(r.symbol)
        )
        if catalogue_exact_crypto:
            lanes.append({
                "timeframe": timeframe,
                "policy_state": market_policy(m.asset_class, timeframe),
                "registration_state": "EXISTING" if existing else "MISSING",
                "provider_capability": "SUPPORTED_WITH_APPROVED_MAPPING",
                "provider_mapping": "EXACT_REPRESENTATION",
                "authority_state": "READY_FOR_LANE_COMMISSIONING",
                "acquisition_readiness": "NOT_YET_ACQUIRED",
                "reason": f"Twelve Data cryptocurrency catalogue exact mapping: {_provider_symbol(r)}.",
                "selectable": True,
            });continue
        configured_crypto = _configured_crypto_mapping({
            "asset_class": m.asset_class,
            "canonical_symbol": r.symbol,
            "currency": r.currency,
        }, timeframe)
        if configured_crypto and not facts:
            profile, mapping = configured_crypto
            lanes.append({
                "timeframe": timeframe,
                "policy_state": market_policy(m.asset_class, timeframe),
                "registration_state": "EXISTING" if existing else "MISSING",
                "provider_capability": "SUPPORTED_WITH_APPROVED_MAPPING",
                "provider_mapping": str(mapping.get("mapping_class") or "APPROVED_REPRESENTATION"),
                "authority_state": "READY_FOR_LANE_COMMISSIONING",
                "acquisition_readiness": "NOT_YET_ACQUIRED",
                "reason": f"Reviewed {profile.provider} crypto catalogue mapping: {mapping.get('symbol', mapping.get('provider_symbol'))}.",
                "selectable": True,
            });continue
        if facts:
            supported=[item for item in facts if item["capability_state"] in {"SUPPORTED","SUPPORTED_WITH_APPROVED_MAPPING","CREDENTIAL_REQUIRED","ENTITLEMENT_REQUIRED","RATE_POLICY_UNVERIFIED"}]
            eligible=[item for item in facts if item["eligibility"]=="ELIGIBLE"]
            capability="SUPPORTED" if supported else "CAPABILITY_UNKNOWN"
            mappings=sorted({str(item["mapping_status"]) for item in supported})
            reasons="; ".join(f"{item['provider']}: {'Eligible' if item['eligibility']=='ELIGIBLE' else item['rejection_reason'] or item['capability_state']}" for item in facts)
            last=next((item["last_successful_provider"] for item in facts if item.get("last_successful_provider")),None)
            lanes.append({"timeframe":timeframe,"policy_state":market_policy(m.asset_class,timeframe),"registration_state":"EXISTING" if existing else "MISSING","provider_capability":capability,"provider_mapping":", ".join(mappings) if mappings else "MAPPING_REQUIRED","authority_state":"COMMISSIONED" if any(item["existing_commissioned_lane"] for item in facts) else "READY_FOR_LANE_COMMISSIONING","acquisition_readiness":"ELIGIBLE" if eligible else "TEMPORARILY_UNAVAILABLE" if supported else "CAPABILITY_UNKNOWN","reason":reasons,"selectable":bool(supported),"provider_capabilities":facts,"last_successful_provider":last});continue
        provider_symbol=_provider_symbol(r);mapped=bool(provider_symbol);reviewed=bool(_approved_provider_mapping(db,r,existing));approved=reviewed or (mapped and r.provider!="YAHOO_FINANCE");review_required=bool(mapped and r.provider=="YAHOO_FINANCE" and not reviewed);policy=market_policy(m.asset_class,timeframe)
        if policy=="INTENTIONALLY_DEFERRED":capability="INTENTIONALLY_DEFERRED";reason="Market policy is intentionally D1-only; no intraday warning or acquisition action applies."
        elif timeframe=="D1": capability="SUPPORTED" if mapped else "MAPPING_REQUIRED"; reason="Approved D1 provider contract and calendar authority." if approved else "Provider candidate requires operator approval before provider acquisition." if mapped else "Provider mapping required."
        elif m.asset_class in {"FX","METALS"} and mapped: capability="SUPPORTED";reason=f"Approved TWELVE_DATA_TIME_SERIES_{timeframe}_V1 provider contract; lane uses the canonical D1 registration anchor." if approved else f"Provider candidate requires operator approval before {timeframe} provider acquisition."
        else: capability="CAPABILITY_UNKNOWN";reason="Required representation-specific authority facts remain a local commissioning stop."
        registration="EXISTING" if existing else "MISSING" if timeframe=="D1" else "IMPLEMENTATION_INCOMPATIBILITY" if capability=="SUPPORTED" else "MISSING"
        acquisition="INTENTIONALLY_DEFERRED" if policy=="INTENTIONALLY_DEFERRED" else "NOT_YET_ACQUIRED" if approved and capability=="SUPPORTED" else "REVIEW_REQUIRED" if review_required and capability=="SUPPORTED" else "CAPABILITY_UNKNOWN" if capability=="CAPABILITY_UNKNOWN" else "MAPPING_REQUIRED" if capability=="MAPPING_REQUIRED" else "IMPLEMENTATION_INCOMPATIBILITY"
        mapping_state="APPROVED_REPRESENTATION" if reviewed else "REVIEW_REQUIRED" if review_required else "KNOWN_MAPPING" if mapped else "MAPPING_REQUIRED"
        lanes.append({"timeframe":timeframe,"policy_state":policy,"registration_state":registration,"provider_capability":capability,"provider_mapping":mapping_state,"authority_state":"D1_REGISTRATION_AUTHORITY" if timeframe=="D1" else "INTENTIONALLY_DEFERRED" if policy=="INTENTIONALLY_DEFERRED" else "READY_FOR_LANE_COMMISSIONING" if capability=="SUPPORTED" else "AUTHORITY_PRESENT_CAPABILITY_UNKNOWN","acquisition_readiness":acquisition,"reason":reason,"selectable":policy=="REQUIRED" and capability=="SUPPORTED"})
    return tuple(lanes)

def _warning(r):
    if r.representation_type=="FUTURES":return "Futures family recognised. Contract selection or continuous-series policy required."
    if not _provider_symbol(r):return "Provider mapping required; canonical registration and file import remain available."
    if r.provider=="YAHOO_FINANCE":return "Confirm the exact Yahoo Finance representation before provider onboarding."
    return "Provider entitlement is unknown and must be checked before acquisition."
def _provider_mapping(r,registration,approved=False):
    provider_symbol=_provider_symbol(r)
    review_required=bool(r.provider=="YAHOO_FINANCE" and provider_symbol and not approved)
    state="APPROVED_REPRESENTATION" if approved else "REVIEW_REQUIRED" if review_required else "KNOWN_MAPPING" if provider_symbol else "MAPPING_REQUIRED"
    crypto_catalogue_route=(
        r.representation_type=="CRYPTO_SPOT_PAIR"
        and r.provider=="TWELVE_DATA"
        and r.catalogue_verified
        and _compact_symbol(provider_symbol or "") == _compact_symbol(r.symbol)
    )
    timeframes=("D1","H1","M30","M5") if crypto_catalogue_route else ("D1",) if provider_symbol else ()
    source="Twelve Data cryptocurrency catalogue" if crypto_catalogue_route else "Operator-approved provider facts" if approved else "Discover provider representation candidate" if review_required else "Reviewed provider catalogue" if provider_symbol else None
    return {"representation_symbol":r.symbol,"provider":r.provider,"availability":state,"mapping_state":state,"supported_timeframes":timeframes,"entitlement":"NOT_MEASURED","readiness":"READY" if approved or crypto_catalogue_route else "REVIEW_REQUIRED" if review_required else "READY" if provider_symbol else "MAPPING_REQUIRED","confidence":100 if approved or crypto_catalogue_route else None,"known_symbol":provider_symbol,"evidence_source":source,"registration_status":registration[1] if registration else "NOT_REGISTERED"}

def _approved_provider_mapping(db,r,registration):
    if not r.provider:return None
    direct=representation_mapping(db,r.provider,r.symbol)
    if direct:return direct
    if registration:
        identity=registration[0]
        if isinstance(identity,str):
            identity=json.loads(identity)
        asset=str(identity.get("asset","")) if isinstance(identity,dict) else ""
        if asset:
            return representation_mapping(db,r.provider,asset)
    compact=_compact_symbol(r.symbol)
    return representation_mapping(db,r.provider,compact) if compact else None

def _registry_market(record,mapping):
    equity=str(record["asset_class"]).upper() in {"US_EQUITIES","UK_EQUITIES","GERMAN_EQUITIES","AUSTRALIAN_EQUITIES"}
    provider=mapping.get("provider") if mapping else "YAHOO_FINANCE" if equity else None;provider_symbol=mapping.get("provider_symbol") if mapping else None;provider_type=(mapping.get("provider_instrument_type") or ("Physical Currency" if record["asset_class"]=="FX" else record["instrument_type"])) if mapping else record["instrument_type"] if equity else None
    rep=R(record["representation_type"],record["canonical_symbol"],record["display_name"],*record["aliases"],exchange=record["exchange_or_venue"],currency=record["currency"],detail=record["share_class_or_contract_family"],provider=provider,provider_symbol=provider_symbol,provider_type=provider_type,catalogue_verified=bool(mapping and mapping.get("catalogue_verified")))
    identity=f"FX:{re.sub(r'[^A-Z]','',record['canonical_symbol'])}" if record["asset_class"]=="FX" else f"REGISTRY:{record['registry_id']}"
    market_type="FOREIGN_EXCHANGE" if record["asset_class"]=="FX" else record["instrument_type"]
    return M(record["underlying_market"],identity,market_type,record["asset_class"],f"Canonical registry identity from {record['source_name']}.",tuple(record["aliases"]),(rep,),record["canonical_symbol"],record["timezone"] or "UTC")


def _runtime_exact_mapping(database_path: str | Path, symbol: str) -> dict[str, object] | None:
    """Return a previously verified, representation-safe Twelve Data route."""

    mapping = representation_mapping(database_path, "TWELVE_DATA", symbol)
    if not isinstance(mapping, dict):
        return None
    if (
        mapping.get("status") not in {"RESOLVED_AUTOMATICALLY", "OPERATOR_RESOLVED"}
        or mapping.get("mapping_class") not in {"EXACT_REPRESENTATION", "APPROVED_PROVIDER_ALIAS"}
        or not mapping.get("provider_symbol")
    ):
        return None
    return mapping

def _configured_crypto_mapping(record, timeframe):
    """Return a reviewed crypto route for one pre-registration timeframe.

    Provider routing deliberately remains registration-gated; this only turns a
    registry-resolved crypto identity into a reviewable, concrete plan.  It
    never grants scheduler ownership or starts acquisition.
    """
    if str(record.get("asset_class", "")).upper() != "CRYPTO":
        return None
    canonical = str(record.get("canonical_symbol", "")).upper()
    quote = str(record.get("quote_currency") or record.get("currency") or "").upper()
    requested_timeframe = str(timeframe).upper()
    candidates = []
    for profile in load_provider_profiles():
        for raw in profile.mappings:
            if (
                str(raw.get("asset", raw.get("canonical_symbol", ""))).upper() != canonical
                or str(raw.get("reviewed_status", "")).upper() != "REVIEWED"
                or requested_timeframe not in {str(value).upper() for value in raw.get("timeframes", ())}
            ):
                continue
            if (
                requested_timeframe != "D1"
                and profile.provider == "TWELVE_DATA"
                and not raw.get("crypto_intraday_approved")
            ):
                continue
            candidates.append((profile, raw))
    if not candidates:
        return None
    profile, raw = min(candidates, key=lambda value: (
        # Admission must choose the governed initial-history route, not a
        # short D1 discovery fallback.  Binance has an unbounded contract and
        # is therefore the correct selected representation whenever a reviewed
        # crypto USD/USDT equivalent exists.  CoinGecko remains in the later
        # provider-candidate projection as its D1-only fallback.
        requested_timeframe == "D1" and value[0].provider != "BINANCE",
        str(value[1].get("provider_quote_asset") or "").upper() != quote,
        value[0].priority,
        value[0].provider,
    ))
    return profile, raw


def _configured_crypto_d1_mapping(record):
    """Expose a reviewed D1 mapping as an onboarding path before registration."""
    configured = _configured_crypto_mapping(record, "D1")
    if configured is None:
        return None
    profile, raw = configured
    return {
        "provider": profile.provider,
        "provider_symbol": raw.get("symbol", raw.get("provider_symbol")),
        "provider_instrument_type": record["instrument_type"],
    }


def _twelve_data_crypto_catalogue_mapping(record:dict[str,object])->dict[str,object]|None:
    """Resolve an exact USD crypto pair from Twelve Data's daily catalogue.

    This is provider metadata, not a price/history acquisition.  A positive
    result is an exact canonical representation and may safely seed the
    review-and-register flow; failure deliberately leaves identity discovery
    intact rather than turning a transient catalogue lookup into a dead end.
    """
    if str(record.get("asset_class") or "").upper()!="CRYPTO":
        return None
    canonical=str(record.get("canonical_symbol") or "").upper()
    if not canonical.endswith("USD") or len(canonical)<=3:
        return None
    base=canonical[:-3]
    provider_symbol=f"{base}/USD"
    credential=CredentialAuthority().credential_for("TWELVE_DATA")
    if not credential:
        return None
    try:
        config=load_provider_config(timeframe="D1")
        target="/cryptocurrencies?"+urlencode({"symbol":provider_symbol,"outputsize":30})
        response=credited_send(
            credential,endpoint="cryptocurrencies",
            send=lambda: BoundedHttpsTransport().send(
                HttpRequest(config.provider_host,target,"Fragarach-II/1 crypto-catalogue"),
                credential,config,
            ),
        )
        payload=json.loads(response.body)
        rows=payload.get("data",[]) if response.status==200 and isinstance(payload,dict) else []
        if not isinstance(rows,list):
            return None
        exact=next((
            row for row in rows if isinstance(row,dict)
            and _compact_symbol(row.get("symbol"))==canonical
            and str(row.get("currency_quote") or "").strip().upper() in {"USD","US DOLLAR"}
        ),None)
        if exact is None:
            return None
        exchanges=exact.get("available_exchanges")
        return {
            "provider":"TWELVE_DATA",
            "provider_symbol":str(exact.get("symbol") or provider_symbol).upper(),
            "provider_instrument_type":"Digital Currency",
            "catalogue_verified":True,
            "provider_exchange":(
                str(exchanges[0]) if isinstance(exchanges,list) and exchanges else None
            ),
        }
    except (OSError,ValueError,TypeError,json.JSONDecodeError):
        return None
def _registrations(db):
    c=open_read_only(db)
    try:return c.execute("SELECT identity_json,registration_status,registration_contract_version FROM instrument_registrations ORDER BY asset,timeframe").fetchall()
    finally:c.close()
def _registration_for(r,rows):
    provider_symbol=_provider_symbol(r)
    names={value for value in (_normalize(r.symbol),_normalize(provider_symbol or ""),_compact_symbol(r.symbol),_compact_symbol(provider_symbol or "")) if value}
    for identity,status,version in rows:
        v=json.loads(identity)
        values={str(v.get(k,"")) for k in ("asset","local_symbol","provider_symbol","selected_representation") if v.get(k)}
        comparisons={_normalize(value) for value in values if value} | {_compact_symbol(value) for value in values if value}
        if names & comparisons:return v,status,version
def _registration_context(db,reg,retired=None):
    v,status,version=reg;truth=None
    try:truth=truth_state_for_lane(db,symbol=v["asset"],timeframe="D1")
    except TruthEngineError:pass
    publication_status="ACTIVE_PUBLISHED" if truth else status
    return {"canonical_symbol":v["asset"],"registration_status":retired["lifecycle_state"] if retired else publication_status,"registration_version":version,"authority_state":retired["lifecycle_state"] if retired else truth["authority_state"] if truth else status,"truth_score":truth["truth_score"] if truth else None,"caodt":truth["caodt"] if truth else None,"validation_state":truth["validation_state"] if truth else "NOT_MEASURED","acquisition_state":"DISABLED_RETIRED" if retired else "READY" if v.get("provider_symbol") else "PROVIDER_DISCOVERY_REQUIRED","retirement":retired}

def _publication_status(db,reg):
    v,status,_version=reg
    try:
        truth_state_for_lane(db,symbol=v["asset"],timeframe="D1")
    except TruthEngineError:
        return status
    return "ACTIVE_PUBLISHED"
def _rank(d,q):
    if q==_normalize(d.canonical_identity):return 100,"Exact canonical identity match.",None
    for r in d.representations:
        if q in {_normalize(r.symbol),*(_normalize(a) for a in r.aliases)}:return 99,"Exact tradable representation symbol match.",r.symbol
    if q in {_normalize(a) for a in d.aliases}:return 98,"Exact financial alias or trading name match.",None
    if q==_normalize(d.underlying_market):return 97,"Exact market or company name match.",None
    score=ranked_text_match(q,d.underlying_market,*d.aliases)
    if score:return score,"Ranked company, market-name, or spelling suggestion.",None
    return 0,"",None
def _currency_market(q):
    compact=re.sub(r"[^A-Z]","",q)
    if len(compact)!=6 or compact[:3] not in _CURRENCIES or compact[3:] not in _CURRENCIES or compact[:3]==compact[3:]:return None
    base,quote=compact[:3],compact[3:];orientation=orientation_for(compact);provider_symbol=orientation["requested_provider_symbol"]
    return M(f"{base} / {quote}",f"FX:{compact}","FOREIGN_EXCHANGE","FX",f"Ordered foreign-exchange identity for {base} against {quote}.",(compact,f"{base}/{quote}"),(R("FX_SPOT_PAIR",compact,f"{base} / {quote} Spot",f"{base}/{quote}",exchange="OTC",currency=quote,provider="TWELVE_DATA" if provider_symbol else None,provider_symbol=provider_symbol,provider_type="Physical Currency" if provider_symbol else None),),compact)
def _unknown(raw):return {"contract":MARKET_DISCOVERY_CONTRACT,"query":raw,"discovery_status":"UNKNOWN","confidence":0,"markets":(),"explanation":"No recognised market identity found after ranked local search.","search_attempted":("canonical markets","tradable representations","aliases","company names","index names","commodity names","ISO currency pairs","prefix and spelling suggestions"),"suggested_searches":("AMD","Disney","Uber","Gold","EURUSD","Bitcoin"),"similar_markets":(),"operator_guidance":"Choose a suggested search or enter another company name, listed symbol, market, or alias.","required_operator_decisions":False}
def _normalize(v):return re.sub(r"[^A-Z0-9^&]+"," ",v.strip().upper()).strip()
def _compact_symbol(v):return re.sub(r"[^A-Z0-9^&]+","",v.strip().upper())
def _edit_distance(a,b):
    previous=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        current=[i]
        for j,cb in enumerate(b,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(ca!=cb)))
        previous=current
    return previous[-1]
