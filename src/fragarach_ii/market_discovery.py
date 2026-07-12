"""SPEC-012 deterministic market discovery and onboarding guidance."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .storage import open_read_only
from .truth_engine import TruthEngineError, truth_state_for_lane


MARKET_DISCOVERY_CONTRACT = "fragarach_ii.market_discovery.v1"
_CURRENCIES = frozenset("AUD CAD CHF CNY EUR GBP HKD JPY NZD SGD USD ZAR".split())


@dataclass(frozen=True, slots=True)
class Representation:
    representation_type: str
    symbol: str
    display_name: str
    aliases: tuple[str, ...]
    exchange: str | None
    currency: str | None
    provider: str | None
    provider_symbol: str | None


@dataclass(frozen=True, slots=True)
class MarketDefinition:
    underlying_market: str
    canonical_identity: str
    market_type: str
    asset_class: str
    description: str
    aliases: tuple[str, ...]
    exchange: str | None
    timezone: str | None
    sessions: tuple[str, ...]
    currencies: tuple[str, ...]
    representations: tuple[Representation, ...]
    default_symbol: str


_MARKETS = (
    MarketDefinition("Dow Jones Industrial Average", "US_EQUITY_INDEX:DJIA", "EQUITY_INDEX", "INDICES", "Thirty large US companies represented by the Dow Jones Industrial Average.", ("DOW", "DOW JONES", "DJIA"), "US index market", "America/New_York", ("REGULAR",), ("USD",), (
        Representation("INDEX", "DJI", "Dow Jones Industrial Average Index", ("DJI", "DJIA"), "NASDAQ Global Index Data Service", "USD", "TWELVE_DATA", "DJI"),
        Representation("CFD", "US30", "US30 CFD", ("US30", "DJ30", "WALL STREET 30"), "OTC", "USD", None, None),
        Representation("ETF", "DIA", "SPDR Dow Jones Industrial Average ETF", ("DIA",), "NYSE Arca", "USD", "TWELVE_DATA", "DIA"),
        Representation("INDEX_SYMBOL", "^DJI", "Dow Jones Index Symbol", ("^DJI",), "Index namespace", "USD", None, None),
        Representation("FUTURES", "YM", "E-mini Dow Futures", ("YM", "YM FUTURES"), "CBOT", "USD", None, None),
    ), "DJI"),
    MarketDefinition("S&P 500", "US_EQUITY_INDEX:SP500", "EQUITY_INDEX", "INDICES", "Large-cap US equity market represented by the S&P 500.", ("S&P500", "S&P 500", "SP500"), "US index market", "America/New_York", ("REGULAR",), ("USD",), (
        Representation("INDEX", "SPX", "S&P 500 Index", ("SPX",), "Cboe Global Indices", "USD", "TWELVE_DATA", "SPX"),
        Representation("CFD", "US500", "US500 CFD", ("US500", "SPX500"), "OTC", "USD", None, None),
        Representation("ETF", "SPY", "SPDR S&P 500 ETF", ("SPY",), "NYSE Arca", "USD", "TWELVE_DATA", "SPY"),
        Representation("INDEX_SYMBOL", "^GSPC", "S&P 500 Index Symbol", ("^GSPC",), "Index namespace", "USD", None, None),
        Representation("FUTURES", "ES", "E-mini S&P 500 Futures", ("ES", "ES FUTURES"), "CME", "USD", None, None),
    ), "SPX"),
    MarketDefinition("Gold", "COMMODITY:GOLD", "PRECIOUS_METAL", "METALS", "International gold market with spot, CFD, ETF, and futures representations.", ("GOLD", "XAU"), "OTC / listed venues", "UTC", ("WEEKDAY",), ("XAU", "USD"), (
        Representation("SPOT", "XAUUSD", "Gold Spot / US Dollar", ("XAUUSD", "XAU/USD"), "OTC", "USD", "TWELVE_DATA", "XAU/USD"),
        Representation("CFD", "GOLD CFD", "Gold CFD", ("GOLD CFD",), "OTC", "USD", None, None),
        Representation("ETF", "GLD", "SPDR Gold Shares", ("GLD",), "NYSE Arca", "USD", "TWELVE_DATA", "GLD"),
        Representation("FUTURES", "GC", "COMEX Gold Futures", ("GC", "GC FUTURES"), "COMEX", "USD", None, None),
    ), "XAUUSD"),
    MarketDefinition("West Texas Intermediate Crude Oil", "COMMODITY:WTI", "ENERGY_COMMODITY", "ENERGY", "US benchmark crude-oil market with CFD, ETF, and futures representations.", ("OIL", "WTI", "CRUDE OIL"), "OTC / listed venues", "America/New_York", ("WEEKDAY",), ("USD",), (
        Representation("CFD", "USOIL", "US Oil CFD", ("USOIL", "WTI CFD"), "OTC", "USD", None, None),
        Representation("ETF", "USO", "United States Oil Fund", ("USO",), "NYSE Arca", "USD", "TWELVE_DATA", "USO"),
        Representation("FUTURES", "CL", "WTI Crude Oil Futures", ("CL", "CL FUTURES"), "NYMEX", "USD", None, None),
    ), "USOIL"),
    MarketDefinition("Apple Inc.", "COMPANY:APPLE", "COMPANY_EQUITY", "US_EQUITIES", "Apple Inc. listed equity and related tradable forms.", ("APPLE",), "NASDAQ", "America/New_York", ("REGULAR",), ("USD",), (
        Representation("COMMON_STOCK", "AAPL", "Apple Inc. Common Stock", ("AAPL",), "NASDAQ", "USD", "TWELVE_DATA", "AAPL"),
        Representation("CFD", "AAPL CFD", "Apple CFD", ("AAPL CFD",), "OTC", "USD", None, None),
    ), "AAPL"),
    MarketDefinition("Tesla, Inc.", "COMPANY:TESLA", "COMPANY_EQUITY", "US_EQUITIES", "Tesla, Inc. listed equity and related tradable forms.", ("TESLA",), "NASDAQ", "America/New_York", ("REGULAR",), ("USD",), (
        Representation("COMMON_STOCK", "TSLA", "Tesla, Inc. Common Stock", ("TSLA",), "NASDAQ", "USD", "TWELVE_DATA", "TSLA"),
        Representation("CFD", "TSLA CFD", "Tesla CFD", ("TSLA CFD",), "OTC", "USD", None, None),
    ), "TSLA"),
    MarketDefinition("BHP Group Limited — Australia", "COMPANY:BHP:ASX", "COMPANY_EQUITY", "AUSTRALIAN_EQUITIES", "BHP Group primary Australian listing.", ("BHP", "BHP AUSTRALIA"), "ASX", "Australia/Sydney", ("REGULAR",), ("AUD",), (
        Representation("COMMON_STOCK", "ASX:BHP", "BHP Group Limited", ("BHP",), "ASX", "AUD", "TWELVE_DATA", "BHP"),
        Representation("CFD", "BHP.AX CFD", "BHP Australia CFD", ("BHP CFD AU"), "OTC", "AUD", None, None),
    ), "ASX:BHP"),
    MarketDefinition("BHP Group Limited ADR — United States", "COMPANY:BHP:NYSE", "DEPOSITARY_RECEIPT", "US_EQUITIES", "BHP Group US depositary receipt.", ("BHP", "BHP ADR"), "NYSE", "America/New_York", ("REGULAR",), ("USD",), (
        Representation("DEPOSITARY_RECEIPT", "NYSE:BHP", "BHP Group Limited ADR", ("BHP ADR",), "NYSE", "USD", "TWELVE_DATA", "BHP"),
        Representation("CFD", "BHP US CFD", "BHP US CFD", ("BHP CFD US"), "OTC", "USD", None, None),
    ), "NYSE:BHP"),
)


def discover_market(database_path: str | Path, query: str) -> dict[str, object]:
    raw=query.strip()
    if not raw:raise ValueError("market discovery query is required")
    normalized=_normalize(raw)
    dynamic=_currency_market(normalized)
    definitions=(*_MARKETS, *((dynamic,) if dynamic else ()))
    ranked=[]
    for definition in definitions:
        score,reason,requested=_rank(definition,normalized)
        if score:ranked.append((score,definition.canonical_identity,definition,reason,requested))
    ranked.sort(key=lambda value:(-value[0],value[1]))
    if not ranked:return _unknown(raw,normalized,definitions)
    top=ranked[0][0];selected=[entry for entry in ranked if entry[0]>=max(72,top-5)]
    markets=tuple(_market_result(database_path,*entry[2:5],entry[0]) for entry in selected)
    return {"contract":MARKET_DISCOVERY_CONTRACT,"query":raw,"discovery_status":"AMBIGUOUS" if len(markets)>1 else ("KNOWN" if top>=95 else "LIKELY"),"confidence":top,"markets":markets,"explanation":"Market intent resolved before onboarding actions.","suggested_searches":(),"similar_markets":(),"operator_guidance":"Select a market and review its representations, provider mappings, and recommendation."}


def _market_result(database_path,definition,reason,requested,confidence):
    registrations=_registrations(database_path)
    representations=[];existing=[]
    for representation in definition.representations:
        registration=_registration_for(representation,registrations)
        if registration:existing.append(_registration_context(database_path,registration))
        representations.append({**asdict(representation),"registration_status":registration[1] if registration else "NOT_REGISTERED"})
    recommended=next((r for r in definition.representations if r.symbol==requested),None) or next(r for r in definition.representations if r.symbol==definition.default_symbol)
    providers=tuple(_provider_mapping(r,_registration_for(r,registrations)) for r in definition.representations)
    alternatives=tuple(r.symbol for r in definition.representations if r.symbol!=recommended.symbol)
    return {"underlying_market":definition.underlying_market,"canonical_identity":definition.canonical_identity,"confidence":confidence,"market_type":definition.market_type,"asset_class":definition.asset_class,"description":definition.description,"known_aliases":definition.aliases,"representations":tuple(representations),"provider_discovery":providers,"recommendation":{"representation_type":recommended.representation_type,"symbol":recommended.symbol,"display_name":recommended.display_name,"reason":f"Operator input matched {requested}." if requested else f"Default canonical representation for {definition.underlying_market}.","alternatives":alternatives},"metadata":{"market":definition.underlying_market,"asset_class":definition.asset_class,"exchange":definition.exchange,"timezone":definition.timezone,"sessions":definition.sessions,"currencies":definition.currencies,"aliases":definition.aliases,"provider_mappings":tuple(p["known_symbol"] for p in providers if p["known_symbol"] is not None),"registration_state":"REGISTERED" if existing else "NOT_REGISTERED"},"existing_registrations":tuple(existing),"acquisition_readiness":"OPEN_EXISTING" if existing else "ENTITLEMENT_REVIEW_REQUIRED" if recommended.provider else "PROVIDER_DISCOVERY_REQUIRED","resolution_reason":reason}


def _provider_mapping(representation,registration):
    return {"representation_symbol":representation.symbol,"provider":representation.provider or "UNRESOLVED","availability":"KNOWN_MAPPING" if representation.provider_symbol else "DISCOVERY_REQUIRED","supported_timeframes":("D1",) if representation.provider_symbol else (),"entitlement":"NOT_MEASURED","confidence":90 if representation.provider_symbol else None,"known_symbol":representation.provider_symbol,"registration_status":registration[1] if registration else "NOT_REGISTERED"}


def _registrations(database_path):
    connection=open_read_only(database_path)
    try:return connection.execute("SELECT identity_json,registration_status,registration_contract_version FROM instrument_registrations ORDER BY asset,timeframe").fetchall()
    finally:connection.close()


def _registration_for(representation,registrations):
    names={_normalize(representation.symbol),_normalize(representation.provider_symbol or ""),*(_normalize(a) for a in representation.aliases)}
    for identity_json,status,version in registrations:
        value=json.loads(identity_json);registered={_normalize(str(value.get(k,""))) for k in ("asset","local_symbol","provider_symbol")}
        if names & registered:return value,status,version
    return None


def _registration_context(database_path,registration):
    value,status,version=registration;truth=None
    try:truth=truth_state_for_lane(database_path,symbol=value["asset"],timeframe="D1")
    except TruthEngineError:pass
    return {"canonical_symbol":value["asset"],"registration_status":status,"registration_version":version,"authority_state":truth["authority_state"] if truth else status,"truth_score":truth["truth_score"] if truth else None,"caodt":truth["caodt"] if truth else None}


def _rank(definition,normalized):
    canonical=_normalize(definition.canonical_identity);name=_normalize(definition.underlying_market);aliases=tuple(_normalize(a) for a in definition.aliases)
    if normalized==canonical:return 100,"Exact canonical market identity match.",None
    for representation in definition.representations:
        names=(_normalize(representation.symbol),*(_normalize(a) for a in representation.aliases))
        if normalized in names:return 99,"Exact tradable representation or representation alias match.",representation.symbol
    if normalized in aliases:return 97,"Exact established market alias match.",None
    if normalized==name:return 96,"Exact underlying market name match.",None
    if len(normalized)>=3 and (normalized in name or any(normalized in alias for alias in aliases)):return 82,"Partial established market name or alias match.",None
    return 0,"",None


def _currency_market(normalized):
    compact=re.sub(r"[^A-Z]","",normalized)
    if len(compact)!=6 or compact[:3] not in _CURRENCIES or compact[3:] not in _CURRENCIES or compact[:3]==compact[3:]:return None
    base,quote=compact[:3],compact[3:]
    return MarketDefinition(f"{base} / {quote}",f"FX:{compact}","FOREIGN_EXCHANGE","FX",f"Foreign-exchange market for {base} against {quote}.",(compact,f"{base}/{quote}"),"OTC","UTC",("WEEKDAY",),(base,quote),(Representation("FX_SPOT_PAIR",compact,f"{base} / {quote} Spot",(f"{base}/{quote}",),"OTC",quote,"TWELVE_DATA",f"{base}/{quote}"),),compact)


def _unknown(raw,normalized,definitions):
    similar=tuple(d.underlying_market for d in definitions if len(normalized)>=2 and normalized[:2] in _normalize(d.underlying_market))[:5]
    return {"contract":MARKET_DISCOVERY_CONTRACT,"query":raw,"discovery_status":"UNKNOWN","confidence":0,"markets":(),"explanation":"Canonical knowledge, aliases, trading names, abbreviations, representation symbols, and ISO conventions were exhausted.","suggested_searches":similar or (f"Try the full market name for {raw}","Try an exchange-qualified symbol","Try a common CFD, ETF, futures, or index alias"),"similar_markets":similar,"operator_guidance":"Clarify the underlying market or representation before provider discovery."}


def _normalize(value):return re.sub(r"\s+"," ",value.strip().upper())
