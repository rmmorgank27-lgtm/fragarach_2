# SPEC-026 Revision 1 — Implementation Summary

Date: 2026-07-13

Status: implemented and accepted for the consumer-authority boundary and direct Market History. H4 and M15 construction remain inactive pending separate construction authority.

## Outcome

Fragarach is now the ecosystem Market History Service. The versioned analytical request is Symbol + Timeframe + Time Window. The complete analytical response is exactly OHLC, CAODT, Status, and Warnings.

SignalBar is the first migrated consumer. Its production adapter requests Market History by trading-day window and performs analysis only. It no longer imports a Fragarach data module, selects a provider, audits provider currentness, derives timeframe completion, filters returned rows by wall-clock completion, or requests an implementation bar count.

## Implemented boundaries

- Direct bounded service: D1, H1, M30, M5.
- Time windows: last N trading days and inclusive between A/B.
- Approved calendar and owner-day resolution remain inside Fragarach.
- Deterministic inactive derived-view engine accepts only complete authority-supplied interval plans, performs no boundary selection, writes nothing, and is not connected to H4 or M15.
- H4 and M15 return `TIMEFRAME_NOT_ACTIVE`, empty OHLC, null CAODT, and `CONSTRUCTION_AUTHORITY_NOT_COMMISSIONED`.
- Legacy SPEC-018 remains unchanged.
- Fragarach and SignalBar native applications expose a Market History surface for AUDUSD/XAUUSD and D1/H4/H1/M30/M15/M5.

## Principal Fragarach files

- `src/fragarach_ii/market_history_service.py`
- `src/fragarach_ii/commands/get_market_history.py`
- `tests/operations/test_market_history_service.py`
- `Sources/OperationsCore/Models.swift`
- `Sources/OperationsCore/ProcessBridge.swift`
- `Sources/FragarachII/Stores/ConsoleStore.swift`
- `Sources/FragarachII/Views/MarketHistoryView.swift`
- `specs/operations/SPEC-026_MARKET_HISTORY_SERVICE_AND_CONSUMER_AUTHORITY_CONTRACT.md`

## Scope protection

No canonical history, evidence lane, Truth lane, Estate Truth lane, registration, or accepted D1 row was created, modified, or promoted by SPEC-026. Derived output is request-scoped and non-persistent.
