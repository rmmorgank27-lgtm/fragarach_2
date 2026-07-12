"""Provider-independent, versioned canonical market registry."""
from __future__ import annotations

import json, re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY=ROOT/"config"/"market_registry"/"registry.v1.json"

@dataclass(frozen=True,slots=True)
class RegistrySnapshot:
    version:int; records:tuple[dict,...]; mappings:tuple[dict,...]; path:Path
    @property
    def counts(self):
        result={}
        for record in self.records:
            if record["active"]:result[record["asset_class"]]=result.get(record["asset_class"],0)+1
        return result

@lru_cache(maxsize=8)
def load_registry(path:str|Path=DEFAULT_REGISTRY)->RegistrySnapshot:
    source=Path(path); payload=json.loads(source.read_text())
    if payload.get("contract")!="fragarach_ii.market_registry.v1" or payload.get("registry_version")!=1:raise ValueError("unsupported market registry snapshot")
    required={"registry_id","canonical_symbol","display_name","aliases","asset_class","instrument_type","country","exchange_or_venue","currency","timezone","underlying_market","representation_type","share_class_or_contract_family","registry_version","source_name","source_date","active"}
    records=tuple(payload["records"])
    optional={"base_currency","quote_currency","canonical_identity"}
    if any(not required.issubset(record) or set(record)-required-optional for record in records):raise ValueError("market registry record shape mismatch")
    ids=[r["registry_id"] for r in records]
    if ids!=sorted(ids) or len(ids)!=len(set(ids)):raise ValueError("market registry IDs must be unique and sorted")
    return RegistrySnapshot(1,records,tuple(payload.get("provider_mappings",())),source)

def provider_mapping(snapshot:RegistrySnapshot,registry_id:str):
    return next((m for m in snapshot.mappings if m["registry_id"]==registry_id and m["mapping_state"]=="KNOWN_MAPPING"),None)

def search_registry(query:str,snapshot:RegistrySnapshot|None=None)->tuple[dict,...]:
    snapshot=snapshot or load_registry(); q=_normal(query)
    ranked=[]
    for record in snapshot.records:
        if not record["active"]:continue
        symbol=_normal(record["canonical_symbol"]); listed=_normal(record["canonical_symbol"].split(":")[-1]);aliases={_normal(a) for a in record["aliases"]};name=_normal(record["display_name"]);underlying=_normal(record["underlying_market"])
        score=100 if q==symbol else 99 if q==listed else 98 if q in aliases else 97 if q in {name,underlying} else 90 if q==_normal(record["canonical_symbol"].replace(":","")) else 78 if len(q)>=3 and q in name else 0
        if score:ranked.append((score,record["registry_id"],record))
    ranked.sort(key=lambda x:(-x[0],x[1]));return tuple(x[2] for x in ranked if x[0]>=max(78,(ranked[0][0]-3 if ranked else 0)))

def _normal(value):return re.sub(r"[^A-Z0-9^&]+"," ",value.strip().upper()).strip()
