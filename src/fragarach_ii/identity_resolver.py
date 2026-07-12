"""SPEC-011 deterministic, provider-free instrument identity resolution."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .storage import open_read_only
from .truth_engine import TruthEngineError, truth_state_for_lane


IDENTITY_CONTRACT = "fragarach_ii.instrument_identity_resolution.v1"
IDENTITY_STATUSES = {"KNOWN", "LIKELY", "AMBIGUOUS", "UNKNOWN"}
_CURRENCIES = frozenset(
    "AUD CAD CHF CNY EUR GBP HKD JPY NZD SGD USD ZAR".split()
)


@dataclass(frozen=True, slots=True)
class CatalogueIdentity:
    canonical_name: str
    canonical_symbol: str
    instrument_type: str
    market: str
    asset_class: str
    aliases: tuple[str, ...]
    exchange: str | None = None
    currency: str | None = None
    base_currency: str | None = None
    quote_currency: str | None = None
    timezone: str | None = None
    sessions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InstrumentIdentity:
    canonical_name: str
    canonical_symbol: str
    instrument_type: str
    market: str
    asset_class: str
    confidence: int
    known_aliases: tuple[str, ...]
    known_exchange: str | None
    known_currency: str | None
    base_currency: str | None
    quote_currency: str | None
    timezone: str | None
    sessions: tuple[str, ...]
    resolution_reason: str
    identity_status: str
    registration_state: str
    authority_state: str | None
    current_truth_score: int | None
    current_caodt: str | None


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    contract: str
    query: str
    identity_status: str
    confidence: int
    matches: tuple[InstrumentIdentity, ...]
    explanation: str
    suggested_searches: tuple[str, ...]
    suggested_providers: tuple[str, ...]
    suggested_aliases: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))


_CATALOGUE = (
    CatalogueIdentity("Apple Inc.", "NASDAQ:AAPL", "COMMON_STOCK", "NASDAQ", "US_EQUITIES", ("AAPL", "APPLE"), "NASDAQ", "USD", timezone="America/New_York", sessions=("REGULAR",)),
    CatalogueIdentity("BHP Group Limited", "ASX:BHP", "COMMON_STOCK", "ASX", "AUSTRALIAN_EQUITIES", ("BHP", "BHP GROUP"), "ASX", "AUD", timezone="Australia/Sydney", sessions=("REGULAR",)),
    CatalogueIdentity("BHP Group Limited ADR", "NYSE:BHP", "DEPOSITARY_RECEIPT", "NYSE", "US_EQUITIES", ("BHP", "BHP ADR"), "NYSE", "USD", timezone="America/New_York", sessions=("REGULAR",)),
    CatalogueIdentity("Gold Spot / US Dollar", "XAUUSD", "PRECIOUS_METAL_SPOT_PAIR", "OTC", "METALS", ("GOLD", "XAU", "XAU/USD"), "OTC", "USD", "XAU", "USD", "UTC", ("WEEKDAY",)),
    CatalogueIdentity("Silver Spot / US Dollar", "XAGUSD", "PRECIOUS_METAL_SPOT_PAIR", "OTC", "METALS", ("SILVER", "XAG", "XAG/USD"), "OTC", "USD", "XAG", "USD", "UTC", ("WEEKDAY",)),
    CatalogueIdentity("Bitcoin / US Dollar", "BTCUSD", "CRYPTO_SPOT_PAIR", "CRYPTO", "CRYPTO", ("BTC", "BITCOIN", "BTC/USD"), None, "USD", "BTC", "USD", "UTC", ("CONTINUOUS",)),
    CatalogueIdentity("Ethereum / US Dollar", "ETHUSD", "CRYPTO_SPOT_PAIR", "CRYPTO", "CRYPTO", ("ETH", "ETHEREUM", "ETH/USD"), None, "USD", "ETH", "USD", "UTC", ("CONTINUOUS",)),
    CatalogueIdentity("Dow Jones Industrial Average", "DJI", "CASH_INDEX", "US_INDICES", "INDICES", ("DOW", "DOW JONES", "DJIA"), "NASDAQ Global Index Data Service", "USD", timezone="America/New_York", sessions=("REGULAR",)),
    CatalogueIdentity("S&P 500 Price Return Index", "SPX", "CASH_INDEX", "US_INDICES", "INDICES", ("S&P500", "S&P 500", "SP500"), "Cboe Global Indices", "USD", timezone="America/New_York", sessions=("REGULAR",)),
)


def resolve_instrument(database_path: str | Path, query: str) -> IdentityResolution:
    raw = query.strip()
    if not raw:
        raise ValueError("instrument identity query is required")
    normalized = _normalize(raw)
    registered = _registered_matches(database_path, normalized)
    if registered:
        matches = tuple(_registered_identity(database_path, row, normalized) for row in registered)
        return _resolution(raw, matches, "Existing registration authority matched the operator input.")

    dynamic = _currency_pair(normalized)
    if dynamic is not None:
        return _resolution(raw, (_identity(dynamic, 99, "Recognized ISO 4217 base and quote currency codes."),), "ISO currency-pair convention resolved the identity without provider discovery.")

    ranked = []
    for item in _CATALOGUE:
        score, reason = _score(item, normalized)
        if score:
            ranked.append(_identity(item, score, reason))
    ranked.sort(key=lambda item: (-item.confidence, item.canonical_symbol))
    if ranked:
        top = ranked[0].confidence
        selected = tuple(item for item in ranked if item.confidence >= max(70, top - 8))
        return _resolution(raw, selected, "Canonical market knowledge matched the operator input.")
    suggestions = tuple(item.canonical_symbol for item in _CATALOGUE if normalized and normalized[:2] in _normalize(item.canonical_name))[:5]
    return IdentityResolution(
        IDENTITY_CONTRACT, raw, "UNKNOWN", 0, (),
        "No known identity matched. No registration or authority was created.",
        suggestions or (f"Try an exchange-qualified symbol for {raw}", f"Try the full instrument or company name"),
        ("Continue to approved provider discovery only after identity is clarified",),
        (normalized, re.sub(r"[^A-Z0-9]", "", normalized)),
    )


def _resolution(query: str, matches: tuple[InstrumentIdentity, ...], explanation: str) -> IdentityResolution:
    status = "AMBIGUOUS" if len(matches) > 1 else matches[0].identity_status
    return IdentityResolution(IDENTITY_CONTRACT, query, status, max(item.confidence for item in matches), matches, explanation, (), (), ())


def _identity(item: CatalogueIdentity, confidence: int, reason: str) -> InstrumentIdentity:
    status = "KNOWN" if confidence >= 95 else "LIKELY"
    return InstrumentIdentity(item.canonical_name, item.canonical_symbol, item.instrument_type, item.market, item.asset_class, confidence, item.aliases, item.exchange, item.currency, item.base_currency, item.quote_currency, item.timezone, item.sessions, reason, status, "NOT_REGISTERED", None, None, None)


def _registered_matches(database_path: str | Path, normalized: str):
    connection = open_read_only(database_path)
    try:
        rows = connection.execute("SELECT identity_json,registration_status FROM instrument_registrations ORDER BY asset,timeframe").fetchall()
    finally:
        connection.close()
    matches = []
    for identity_json, status in rows:
        value = json.loads(identity_json)
        names = {_normalize(str(value.get(key, ""))) for key in ("asset", "local_symbol", "display_name", "provider_symbol")}
        names.update(_normalize(str(alias.get("normalized_alias", ""))) for alias in value.get("aliases", []))
        if normalized in names:
            matches.append((value, status))
    return matches


def _registered_identity(database_path, row, normalized):
    value, registration_status = row
    aliases = tuple(alias["alias"] for alias in value.get("aliases", []))
    aliases = tuple(dict.fromkeys((*aliases, value["local_symbol"], value["provider_symbol"])))
    truth = None
    try:
        truth = truth_state_for_lane(database_path, symbol=value["asset"], timeframe="D1")
    except TruthEngineError:
        pass
    base, quote = _split_pair(_normalize(value["asset"]))
    return InstrumentIdentity(
        value["display_name"], value["asset"], value["instrument_type"], value["exchange_name"], value["asset_class"], 100,
        aliases, value.get("exchange_name"), value.get("trading_currency"), base, quote, None, (),
        f"Matched immutable registration identity using {normalized}.", "KNOWN", "REGISTERED",
        truth["authority_state"] if truth else registration_status,
        truth["truth_score"] if truth else None, truth["caodt"] if truth else None,
    )


def _currency_pair(normalized: str) -> CatalogueIdentity | None:
    compact = re.sub(r"[^A-Z]", "", normalized)
    if len(compact) != 6:
        return None
    base, quote = compact[:3], compact[3:]
    if base not in _CURRENCIES or quote not in _CURRENCIES or base == quote:
        return None
    return CatalogueIdentity(f"{base} / {quote}", compact, "FX_SPOT_PAIR", "OTC", "FX", (f"{base}/{quote}",), "OTC", quote, base, quote, "UTC", ("WEEKDAY",))


def _score(item: CatalogueIdentity, normalized: str) -> tuple[int, str]:
    canonical = _normalize(item.canonical_symbol)
    name = _normalize(item.canonical_name)
    aliases = tuple(_normalize(alias) for alias in item.aliases)
    if normalized == canonical:
        return 100, "Exact canonical-symbol match."
    if normalized in aliases:
        return 98, "Exact established-alias match."
    if normalized == name:
        return 96, "Exact canonical-name match."
    if len(normalized) >= 3 and (normalized in name or any(normalized in alias for alias in aliases)):
        return 82, "Partial established-name or alias match."
    return 0, ""


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().upper())


def _split_pair(value: str) -> tuple[str | None, str | None]:
    compact = re.sub(r"[^A-Z]", "", value)
    if len(compact) == 6 and (compact[:3] in _CURRENCIES or compact[:3] in {"BTC", "ETH", "XAU", "XAG"}) and compact[3:] in _CURRENCIES:
        return compact[:3], compact[3:]
    return None, None
