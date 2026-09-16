"""Constitution-bound core intraday interval profiles."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from datetime import UTC,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DURATIONS={"H1":3600,"M30":1800,"M15":900,"M5":300}

@dataclass(frozen=True,slots=True)
class IntradayProfile:
    asset_class:str;timeframe:str;calendar_id:str;session_profile_id:str;timezone:str;continuous:bool;checksum:str
    @property
    def seconds(self):return DURATIONS[self.timeframe]

def profile_for(asset_class:str,timeframe:str)->IntradayProfile:
    asset_class=asset_class.upper();timeframe=timeframe.upper()
    if timeframe not in DURATIONS:raise ValueError(f"UNSUPPORTED_TIMEFRAME: {timeframe}")
    if asset_class=="BROKER_INDEX_CFDS":
        path=Path(__file__).resolve().parents[3]/"constitution"/"authorities"/"index_cfds"/"MT5_BROKER_FAMILY_INDEX_CFD_AUTHORITY_V1.json"
        checksum=hashlib.sha256(path.read_bytes()).hexdigest()
        return IntradayProfile(
            asset_class,timeframe,"MT5_BROKER_INDEX_CFD_24X5_UTC_V1",
            "MT5_BROKER_INDEX_CFD_DAILY_SESSION_V1","UTC",False,checksum,
        )
    if asset_class=="US_EQUITIES":
        path=Path(__file__).resolve().parents[3]/"constitution"/"doctrines"/"US_EQUITIES_BASE_DOCTRINE_V1.md"
        checksum=hashlib.sha256(path.read_bytes()).hexdigest()
        return IntradayProfile(
            asset_class,timeframe,"US_EQUITIES_D1_V1",
            "US_EQUITIES_REGULAR_SESSION_V1","America/New_York",False,checksum,
        )
    family={
        "FX":"fx/FX",
        "METALS":"metals/METALS",
        "CRYPTO":"crypto/CRYPTO",
        "ENERGY":"energy/ENERGY",
    }.get(asset_class)
    if family is None:raise ValueError(f"INTRADAY_PROFILE_NOT_COMMISSIONED: {asset_class}")
    path=Path(__file__).resolve().parents[3]/"constitution"/"authorities"/f"{family}_{timeframe}_AUTHORITY_V1.md"
    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    if asset_class=="CRYPTO":return IntradayProfile(asset_class,timeframe,"CRYPTO_24X7_UTC_V1","CRYPTO_CONTINUOUS_UTC_V1","UTC",True,checksum)
    if asset_class=="ENERGY":return IntradayProfile(asset_class,timeframe,"ENERGY_REFERENCE_24X5_NEW_YORK_ROLLOVER_V1","ENERGY_REFERENCE_DAILY_SESSION_V1","America/New_York",False,checksum)
    prefix="FX" if asset_class=="FX" else "METALS"
    return IntradayProfile(asset_class,timeframe,f"{prefix}_24X5_NEW_YORK_ROLLOVER_V1",f"{prefix}_DAILY_SESSION_V1","America/New_York",False,checksum)

def canonical_open(text:str,profile:IntradayProfile)->int:
    raw=text.strip()
    candidate=raw[:-1]+"+00:00" if raw.endswith("Z") else raw
    value=datetime.fromisoformat(candidate)
    if value.tzinfo is None:
        value=value.replace(tzinfo=ZoneInfo(profile.timezone))
    value=value.astimezone(UTC)
    epoch=int(value.timestamp())
    if not is_aligned_open(epoch,profile):raise ValueError("MISALIGNED_INTERVAL_OPEN")
    return epoch

def is_aligned_open(epoch:int,profile:IntradayProfile)->bool:
    value=datetime.fromtimestamp(epoch,UTC)
    if profile.continuous or profile.asset_class=="BROKER_INDEX_CFDS":return epoch%profile.seconds==0
    local=value.astimezone(ZoneInfo(profile.timezone))
    return not (local.second or local.microsecond or (local.minute*60)%profile.seconds)

def is_expected_open(epoch:int,profile:IntradayProfile)->bool:
    if profile.continuous:return True
    local=datetime.fromtimestamp(epoch,UTC).astimezone(ZoneInfo(profile.timezone))
    weekday=local.weekday()
    if profile.asset_class=="BROKER_INDEX_CFDS":
        return weekday in (0,1,2,3,4) and local.hour>=1
    if profile.asset_class=="US_EQUITIES":
        opened=local.hour*60+local.minute
        return weekday in (0,1,2,3,4) and 9*60+30<=opened<16*60
    return weekday in (0,1,2,3) or (weekday==4 and local.hour<17) or (weekday==6 and local.hour>=17)

def expected_opens(start:int,end_exclusive:int,profile:IntradayProfile)->tuple[int,...]:
    first=start-(start%profile.seconds) if profile.continuous else start
    values=[];current=first
    while current+profile.seconds<=end_exclusive:
        if is_aligned_open(current,profile) and is_expected_open(current,profile):values.append(current)
        current+=profile.seconds
    return tuple(values)

def iso(epoch:int)->str:return datetime.fromtimestamp(epoch,UTC).isoformat()
