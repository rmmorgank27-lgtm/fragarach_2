"""Provider-independent, versioned canonical market registry."""
from __future__ import annotations

import json, re
from difflib import SequenceMatcher
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
    """Return a bounded, ranked suggestion set from the canonical registry.

    Discovery runs while the operator types, so this deliberately accepts
    prefixes, company-name fragments, and conservative spelling errors. Exact
    identifiers still outrank suggestions and the bounded result never mutates
    authority or provider state.
    """
    snapshot=snapshot or load_registry(); q=_normal(query)
    if not q:return ()
    ranked=[]
    for record in snapshot.records:
        if not record["active"]:continue
        score=_record_search_score(record,q)
        if score:ranked.append((score,record["registry_id"],record))
    if not ranked:return ()
    ranked.sort(key=lambda x:(-x[0],x[1]))
    top=ranked[0][0]
    floor=top-3 if top>=95 else max(80,top-7)
    return tuple(x[2] for x in ranked if x[0]>=floor)[:8]


def ranked_text_match(query:str,*values:str)->int:
    """Score human-entered text against names and aliases without guessing low-quality matches."""
    q=_normal(query)
    if len(q)<2:return 0
    candidates=tuple(dict.fromkeys(_normal(value) for value in values if _normal(value)))
    if not candidates:return 0
    compact=_compact(q)
    if any(q==candidate for candidate in candidates):return 97
    if len(compact)>=3 and any(compact==_compact(candidate) for candidate in candidates):return 95
    if len(q)>=3 and any(candidate.startswith(q) for candidate in candidates):return 91
    if len(q)>=3 and any(q in candidate for candidate in candidates):return 88

    query_tokens=tuple(token for token in q.split() if len(token)>=2)
    candidate_tokens=tuple({
        token for candidate in candidates for token in candidate.split() if len(token)>=2
    })
    if not query_tokens or not candidate_tokens:return 0
    exact=sum(token in candidate_tokens for token in query_tokens)
    if exact==len(query_tokens):return 87
    if len(q)<4:return 0
    coverage=sum(
        max(SequenceMatcher(None,token,candidate).ratio() for candidate in candidate_tokens)
        for token in query_tokens
    )/len(query_tokens)
    if coverage>=0.82:return min(86,76+round(coverage*10))
    whole=max(SequenceMatcher(None,q,candidate).ratio() for candidate in candidates)
    return min(82,73+round(whole*10)) if whole>=0.80 else 0


def _record_search_score(record:dict,query:str)->int:
    symbol=_normal(record["canonical_symbol"])
    listed=_normal(record["canonical_symbol"].split(":")[-1])
    aliases=tuple(_normal(alias) for alias in record["aliases"])
    if query==symbol:return 100
    if query==listed:return 99
    if query in aliases:return 98
    if query==_normal(record["canonical_symbol"].replace(":","")):return 96
    if len(_compact(query))>=2 and _compact(listed).startswith(_compact(query)):return 92
    return ranked_text_match(
        query,record["display_name"],record["underlying_market"],*record["aliases"]
    )

def _normal(value):return re.sub(r"[^A-Z0-9^&]+"," ",value.strip().upper()).strip()
def _compact(value):return re.sub(r"[^A-Z0-9^&]+","",value.strip().upper())
