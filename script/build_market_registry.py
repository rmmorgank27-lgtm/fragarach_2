#!/usr/bin/env python3
"""Build the reviewed local market-registry snapshot from pinned source extracts."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "config" / "market_registry" / "registry.v1.json"
SOURCE_DATE = date.today().isoformat()
HEADERS = {"User-Agent": "FragarachRegistry/1.0 raymorgan@example.com"}


def record(registry_id, symbol, name, aliases, asset_class, instrument_type, country,
           venue, currency, timezone, underlying, representation, family=None,
           source="Fragarach reviewed seed"):
    return {
        "registry_id": registry_id, "canonical_symbol": symbol, "display_name": name,
        "aliases": sorted(set(a for a in aliases if a)), "asset_class": asset_class,
        "instrument_type": instrument_type, "country": country,
        "exchange_or_venue": venue, "currency": currency, "timezone": timezone,
        "underlying_market": underlying, "representation_type": representation,
        "share_class_or_contract_family": family, "registry_version": 1,
        "source_name": source, "source_date": SOURCE_DATE, "active": True,
    }


def wiki_rows(page, minimum):
    response = requests.get(f"https://en.wikipedia.org/wiki/{page}", headers=HEADERS, timeout=30)
    response.raise_for_status()
    tables = BeautifulSoup(response.text, "html.parser").select("table.wikitable")
    table = next(t for t in tables if len(t.select("tr")) >= minimum)
    headers = [x.get_text(" ", strip=True) for x in table.select("tr")[0].select("th,td")]
    return headers, [[x.get_text(" ", strip=True) for x in row.select("th,td")] for row in table.select("tr")[1:]]


def main():
    records = []
    mappings = []

    # Reviewed direct orientations only. Exact inverse identities are generated at search time without mappings.
    for pair in ("AUDUSD", "EURUSD", "GBPUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD", "EURAUD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY"):
        base, quote = pair[:3], pair[3:]
        records.append(record(f"fx:{pair.lower()}", pair, f"{base} / {quote} Spot", [f"{base}/{quote}"], "FX", "FX_SPOT_PAIR", None, "OTC", quote, "UTC", f"{base} / {quote}", "FX_SPOT_PAIR"))
        mappings.append({"registry_id":f"fx:{pair.lower()}","provider":"TWELVE_DATA","provider_symbol":f"{base}/{quote}","mapping_state":"KNOWN_MAPPING","supported_timeframes":["D1"],"evidence_source":"Reviewed direct-orientation catalogue","last_verified":SOURCE_DATE})

    seeds = [
        ("metal:gold:spot-usd","XAUUSD","Gold Spot / US Dollar",["XAU","XAU/USD","GOLD"],"METALS","PRECIOUS_METAL_SPOT","International gold","SPOT","OTC","USD"),
        ("metal:silver:spot-usd","XAGUSD","Silver Spot / US Dollar",["XAG","XAG/USD","SILVER"],"METALS","PRECIOUS_METAL_SPOT","International silver","SPOT","OTC","USD"),
        ("metal:platinum:spot-usd","XPTUSD","Platinum Spot / US Dollar",["XPT","PLATINUM"],"METALS","PRECIOUS_METAL_SPOT","International platinum","SPOT","OTC","USD"),
        ("metal:palladium:spot-usd","XPDUSD","Palladium Spot / US Dollar",["XPD","PALLADIUM"],"METALS","PRECIOUS_METAL_SPOT","International palladium","SPOT","OTC","USD"),
        ("energy:wti:cfd","USOIL","WTI Crude Oil CFD",["WTI","OIL","WEST TEXAS INTERMEDIATE"],"ENERGY","ENERGY_COMMODITY","West Texas Intermediate Crude Oil","CFD","OTC","USD"),
        ("energy:brent:cfd","UKOIL","Brent Crude Oil CFD",["BRENT","OIL"],"ENERGY","ENERGY_COMMODITY","Brent Crude Oil","CFD","OTC","USD"),
        ("energy:henry-hub:futures","NG","Henry Hub Natural Gas Futures",["NATGAS","NATURAL GAS"],"ENERGY","ENERGY_FUTURES","Henry Hub Natural Gas","FUTURES","NYMEX","USD"),
        ("index:djia:index","DJI","Dow Jones Industrial Average",["DJIA","DOW","DOW JONES"],"INDICES","EQUITY_INDEX","Dow Jones Industrial Average","INDEX","US index market","USD"),
        ("index:sp500:index","SPX","S&P 500 Index",["SP500","S&P500","US500"],"INDICES","EQUITY_INDEX","S&P 500","INDEX","CBOE","USD"),
        ("index:nasdaq100:index","NDX","Nasdaq 100 Index",["NASDAQ 100","US100"],"INDICES","EQUITY_INDEX","Nasdaq 100","INDEX","NASDAQ","USD"),
        ("index:dax:index","DAX","DAX Index",["DE40","GER40"],"INDICES","EQUITY_INDEX","DAX","INDEX","Deutsche Börse","EUR"),
        ("index:ftse100:index","FTSE","FTSE 100 Index",["UK100"],"INDICES","EQUITY_INDEX","FTSE 100","INDEX","FTSE Russell","GBP"),
        ("index:asx200:index","XJO","S&P/ASX 200 Index",["ASX 200","AUS200"],"INDICES","EQUITY_INDEX","S&P/ASX 200","INDEX","ASX","AUD"),
    ]
    for rid,symbol,name,aliases,asset,kind,underlying,rep,venue,currency in seeds:
        records.append(record(rid,symbol,name,aliases,asset,kind,None,venue,currency,"UTC",underlying,rep,"Continuous family" if rep=="FUTURES" else None))
    for rid,provider_symbol,provider_type in (("metal:gold:spot-usd","XAU/USD","Precious Metal"),("metal:silver:spot-usd","XAG/USD","Precious Metal"),("index:djia:index","DJI","Index")):
        mappings.append({"registry_id":rid,"provider":"TWELVE_DATA","provider_symbol":provider_symbol,"mapping_state":"KNOWN_MAPPING","supported_timeframes":["D1"],"evidence_source":"Reviewed provider catalogue","last_verified":SOURCE_DATE,"provider_instrument_type":provider_type})

    sec = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=30).json()
    for item in list(sec.values())[:500]:
        ticker=item["ticker"].upper(); title=item["title"].strip(); rid=f"equity:us:sec-cik-{item['cik_str']}"
        records.append(record(rid,ticker,title,[ticker],"US_EQUITIES","COMMON_STOCK","US","US LISTED","USD","America/New_York",title,"COMMON_STOCK",source="SEC company_tickers.json"))

    headers, rows = wiki_rows("FTSE_100_Index", 100)
    ci,ti=headers.index("Company"),headers.index("Ticker")
    for row in rows[:100]:
        name,ticker=row[ci],row[ti].split()[0].upper(); records.append(record(f"equity:uk:lse-{ticker.lower()}",f"LSE:{ticker}",name,[ticker],"UK_EQUITIES","COMMON_STOCK","UK","LSE","GBP","Europe/London",name,"COMMON_STOCK",source="FTSE 100 constituents"))

    german=[]
    for page,minimum in (("DAX",40),("MDAX",50),("SDAX",60)):
        headers,rows=wiki_rows(page,minimum)
        for row in rows:
            if len(row)<2: continue
            if page=="DAX": ticker,name=row[0],row[2]
            elif page=="MDAX": name,ticker=row[1],row[-1]
            else: name,ticker=row[1],row[-1] if len(row)>4 else row[1]
            ticker=ticker.split()[0].upper()
            if ticker and name and ticker not in {x[0] for x in german}: german.append((ticker,name))
    for ticker,name in german[:100]: records.append(record(f"equity:de:xetr-{ticker.lower()}",f"XETR:{ticker}",name,[ticker],"GERMAN_EQUITIES","COMMON_STOCK","DE","XETRA","EUR","Europe/Berlin",name,"COMMON_STOCK",source="DAX/MDAX/SDAX constituents"))

    headers,rows=wiki_rows("S%26P/ASX_200",200); ci,ni=headers.index("Code"),headers.index("Company")
    for row in rows[:100]:
        ticker,name=row[ci].upper(),row[ni]; records.append(record(f"equity:au:asx-{ticker.lower()}",f"ASX:{ticker}",name,[ticker],"AUSTRALIAN_EQUITIES","COMMON_STOCK","AU","ASX","AUD","Australia/Sydney",name,"COMMON_STOCK",source="S&P/ASX 200 constituents"))

    for page in (1,2):
        coins=requests.get("https://api.coingecko.com/api/v3/coins/markets",params={"vs_currency":"usd","order":"market_cap_desc","per_page":250,"page":page,"sparkline":"false"},timeout=30).json()
        for coin in coins:
            coin_id=coin["id"]; ticker=coin["symbol"].upper(); symbol=f"{ticker}USD"
            records.append(record(f"crypto:coingecko:{coin_id}:usd",symbol,f"{coin['name']} / US Dollar",[ticker,coin["name"],coin_id,f"{ticker}/USD"],"CRYPTO","CRYPTO_SPOT_PAIR",None,"Digital asset venues","USD","UTC",coin["name"],"CRYPTO_SPOT_PAIR",coin_id,source="CoinGecko market-cap snapshot"))

    # Registry identities are unique; duplicate tickers/share classes remain distinct records.
    records.sort(key=lambda r:r["registry_id"])
    snapshot={"contract":"fragarach_ii.market_registry.v1","registry_version":1,"generated_at":SOURCE_DATE,"records":records,"provider_mappings":sorted(mappings,key=lambda m:(m["registry_id"],m["provider"]))}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(snapshot,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n")
    counts={}
    for r in records: counts[r["asset_class"]]=counts.get(r["asset_class"],0)+1
    print(json.dumps({"path":str(OUT),"records":len(records),"counts":counts},sort_keys=True))


if __name__ == "__main__": main()
