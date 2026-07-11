"""Canonical instrument registration authority and registered-writer operation."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from .database import open_read_only, registered_writer, transaction
from .migrations import apply_migrations

_CODE = re.compile(r"^[A-Z0-9._-]+$")
_CURRENCY = re.compile(r"^[A-Z0-9]+$")
_MIC = re.compile(r"^[A-Z0-9]{4}$")
_ALIAS_TYPES = {"OPERATOR_SYMBOL", "COMMON_NAME", "PLATFORM_SYMBOL", "LEGACY_SYMBOL"}
_REPRESENTATIONS = {"CFD", "INDEX", "ETF", "FUTURES", "SPOT", "FX_SPOT_PAIR", "CRYPTO_SPOT_PAIR", "COMMON_STOCK"}


class RegistrationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class Alias:
    alias: str
    normalized_alias: str
    alias_type: str


@dataclass(frozen=True, slots=True)
class RegistrationCandidate:
    asset: str; timeframe: str; instrument_family: str; local_symbol: str
    display_name: str; instrument_type: str; asset_class: str; representation_type: str
    trading_currency: str; exchange_name: str; provider_id: str; provider_contract: str
    provider_symbol: str; provider_instrument_type: str; calendar_id: str
    calendar_version: int; gap_doctrine_id: str; gap_doctrine_version: int
    aliases: tuple[Alias, ...] = (); underlying_reference: str | None = None
    contract_or_series: str | None = None; jurisdiction: str | None = None
    exchange_mic: str | None = None; provider_exchange: str | None = None
    provider_country: str | None = None


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    operation_contract: str; outcome: str; asset: str; timeframe: str
    identity_checksum_sha256: str; provider_identity_key: str; registration_status: str
    def as_json(self) -> str: return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def canonical_registration(candidate: RegistrationCandidate) -> tuple[str, str, str, str]:
    _validate(candidate)
    aliases = sorted((asdict(a) for a in candidate.aliases), key=lambda a: (a["normalized_alias"], a["alias_type"]))
    aliases_json = json.dumps(aliases, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    provider_key = json.dumps([candidate.provider_id, candidate.provider_symbol, candidate.provider_exchange,
        candidate.provider_instrument_type, candidate.trading_currency, candidate.provider_country], separators=(",", ":"), ensure_ascii=False)
    identity = {
        "aliases": aliases, "asset": candidate.asset, "asset_class": candidate.asset_class,
        "calendar_id": candidate.calendar_id, "calendar_version": candidate.calendar_version,
        "contract_or_series": candidate.contract_or_series, "display_name": candidate.display_name,
        "exchange_mic": candidate.exchange_mic, "exchange_name": candidate.exchange_name,
        "gap_doctrine_id": candidate.gap_doctrine_id, "gap_doctrine_version": candidate.gap_doctrine_version,
        "instrument_family": candidate.instrument_family, "instrument_type": candidate.instrument_type,
        "jurisdiction": candidate.jurisdiction, "local_symbol": candidate.local_symbol,
        "provider_contract": candidate.provider_contract, "provider_country": candidate.provider_country,
        "provider_exchange": candidate.provider_exchange, "provider_id": candidate.provider_id,
        "provider_identity_key": provider_key, "provider_instrument_type": candidate.provider_instrument_type,
        "provider_symbol": candidate.provider_symbol, "registration_contract": "INSTRUMENT_REGISTRATION_V1",
        "registration_contract_version": 1, "representation_type": candidate.representation_type,
        "semantic_equivalence": "DISTINCT_INSTRUMENT", "timeframe": candidate.timeframe,
        "trading_currency": candidate.trading_currency, "underlying_reference": candidate.underlying_reference,
    }
    identity_json = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return aliases_json, provider_key, identity_json, hashlib.sha256(identity_json.encode()).hexdigest()


def register_instrument(database_path: str | Path, candidate: RegistrationCandidate, *, registered_at_utc: str) -> RegistrationResult:
    aliases_json, provider_key, identity_json, checksum = canonical_registration(candidate)
    values = (candidate.asset,candidate.timeframe,"INSTRUMENT_REGISTRATION_V1",1,candidate.instrument_family,candidate.local_symbol,
        aliases_json,candidate.display_name,candidate.instrument_type,candidate.asset_class,candidate.representation_type,
        candidate.underlying_reference,candidate.contract_or_series,"DISTINCT_INSTRUMENT",candidate.jurisdiction,candidate.trading_currency,
        candidate.exchange_name,candidate.exchange_mic,candidate.provider_id,candidate.provider_contract,candidate.provider_symbol,
        candidate.provider_exchange,candidate.provider_country,candidate.provider_instrument_type,provider_key,candidate.calendar_id,
        candidate.calendar_version,candidate.gap_doctrine_id,candidate.gap_doctrine_version,"REGISTERED_NO_EVIDENCE",registered_at_utc,None,identity_json,checksum)
    with registered_writer(database_path) as connection:
        apply_migrations(connection)
        with transaction(connection):
            existing = connection.execute("SELECT identity_checksum_sha256,provider_identity_key,registration_status FROM instrument_registrations WHERE asset=? AND timeframe=?",(candidate.asset,candidate.timeframe)).fetchone()
            if existing:
                if existing[0] != checksum: raise RegistrationError("CANONICAL_ASSET_COLLISION", candidate.asset)
                outcome, status = "EXISTING_IDENTICAL", existing[2]
            else:
                try: connection.execute("INSERT INTO instrument_registrations VALUES ("+",".join("?" for _ in values)+")",values)
                except sqlite3.IntegrityError as error: raise RegistrationError("PROVIDER_OR_NAME_COLLISION",str(error)) from error
                outcome, status = "INSERTED", "REGISTERED_NO_EVIDENCE"
    connection = open_read_only(database_path)
    try:
        row=connection.execute("SELECT identity_json,identity_checksum_sha256 FROM instrument_registrations WHERE asset=? AND timeframe=?",(candidate.asset,candidate.timeframe)).fetchone()
        if row is None or hashlib.sha256(row[0].encode()).hexdigest()!=row[1]: raise RegistrationError("READBACK_FAILED",candidate.asset)
    finally: connection.close()
    return RegistrationResult("fragarach_ii.instrument_registration_result.v1",outcome,candidate.asset,candidate.timeframe,checksum,provider_key,status)


def registration_for_lane(database_path: str | Path, asset: str, timeframe: str) -> sqlite3.Row | tuple:
    connection=open_read_only(database_path)
    try:
        row=connection.execute("SELECT provider_id,provider_contract,provider_symbol,calendar_id,calendar_version,gap_doctrine_id,gap_doctrine_version,registration_status,identity_checksum_sha256 FROM instrument_registrations WHERE asset=? AND timeframe=?",(asset,timeframe)).fetchone()
        if row is None: raise RegistrationError("UNREGISTERED_LANE",f"{asset}:{timeframe}")
        return row
    finally: connection.close()


def _validate(c: RegistrationCandidate) -> None:
    for name in ("asset","instrument_family","local_symbol"):
        value=getattr(c,name)
        if not _CODE.fullmatch(value): raise RegistrationError("INVALID_CODE",name)
    if c.timeframe!="D1": raise RegistrationError("UNSUPPORTED_TIMEFRAME",c.timeframe)
    for name in ("display_name","instrument_type","asset_class","exchange_name","provider_id","provider_contract","provider_symbol","provider_instrument_type","calendar_id","gap_doctrine_id"):
        value=getattr(c,name)
        if not value or value != value.strip(): raise RegistrationError("INVALID_FIELD",name)
    if c.representation_type not in _REPRESENTATIONS or (c.representation_type=="FUTURES" and not c.contract_or_series): raise RegistrationError("INVALID_REPRESENTATION",c.representation_type)
    if not _CURRENCY.fullmatch(c.trading_currency): raise RegistrationError("INVALID_CURRENCY",c.trading_currency)
    if c.exchange_mic is not None and not _MIC.fullmatch(c.exchange_mic): raise RegistrationError("INVALID_MIC",c.exchange_mic)
    if c.calendar_version<1 or c.gap_doctrine_version<1: raise RegistrationError("INVALID_VERSION","version")
    if "." in c.asset and c.asset != f"{c.instrument_family}.{c.local_symbol}": raise RegistrationError("FAMILY_IDENTITY_MISMATCH",c.asset)
    normalized=[a.normalized_alias for a in c.aliases]
    if normalized != sorted(normalized) or len(normalized)!=len(set(normalized)): raise RegistrationError("INVALID_ALIASES","ordering or duplicate")
    for a in c.aliases:
        if a.alias_type not in _ALIAS_TYPES or not a.alias.strip() or not _CODE.fullmatch(a.normalized_alias): raise RegistrationError("INVALID_ALIAS",a.alias)
