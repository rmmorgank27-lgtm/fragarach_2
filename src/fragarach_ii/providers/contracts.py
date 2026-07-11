"""Checksummed declarative provider contracts used by authority declarations."""
from __future__ import annotations
import hashlib,json
from pathlib import Path

class ProviderContractError(RuntimeError): pass

def contract_directory() -> Path:
    return Path(__file__).resolve().parents[3]/"config"/"providers"/"authority"

def list_provider_contracts() -> list[dict]:
    return [load_provider_contract(p.stem) for p in sorted(contract_directory().glob("*.json"))]

def load_provider_contract(contract_id: str) -> dict:
    matches=[p for p in contract_directory().glob("*.json") if p.stem==contract_id]
    if len(matches)!=1: raise ProviderContractError(f"unknown provider contract: {contract_id}")
    value=json.loads(matches[0].read_text())
    checksum=value.get("contract_checksum_sha256"); unsigned=dict(value);unsigned.pop("contract_checksum_sha256",None)
    canonical=json.dumps(unsigned,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    if checksum!=hashlib.sha256(canonical.encode()).hexdigest(): raise ProviderContractError(f"provider contract checksum mismatch: {contract_id}")
    if value.get("provider_hard_maximum")!=5000 or value.get("fragarach_request_ceiling")!=4000: raise ProviderContractError("invalid provider/request ceiling")
    return value
