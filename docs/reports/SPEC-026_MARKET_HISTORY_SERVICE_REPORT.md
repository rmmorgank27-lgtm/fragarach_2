# SPEC-026 Revision 1 — Market History Service Report

Date: 2026-07-13

## Contract

Request:

```text
Market History
Symbol
Timeframe
Time Window
```

Response keys, with no additional analysis-facing metadata:

```text
OHLC
CAODT
Status
Warnings
```

Provider, evidence, provenance, validation mechanics, source timeframe, derivation, alignment, calendar, session, and bar-count mechanics are absent from the response.

## Determinism and consumer invariance

The focused consumer-invariance test sends the same request under SignalBar, Sea Eagle, and HARP conceptual callers and asserts complete response equality. A production integration comparison also queried Fragarach directly and through SignalBar for every required AUDUSD/XAUUSD lane. All 12 responses were identical.

| Symbol | Timeframe | Status | OHLC rows (5 trading days) | CAODT |
|---|---|---|---:|---|
| AUDUSD | D1 | AVAILABLE_WITH_WARNINGS | 5 | 2026-07-11T00:00:00+00:00 |
| AUDUSD | H4 | TIMEFRAME_NOT_ACTIVE | 0 | — |
| AUDUSD | H1 | AVAILABLE_WITH_WARNINGS | 102 | 2026-07-13T03:00:00+00:00 |
| AUDUSD | M30 | AVAILABLE_WITH_WARNINGS | 205 | 2026-07-13T03:30:00+00:00 |
| AUDUSD | M15 | TIMEFRAME_NOT_ACTIVE | 0 | — |
| AUDUSD | M5 | AVAILABLE_WITH_WARNINGS | 1,235 | 2026-07-13T03:55:00+00:00 |
| XAUUSD | D1 | AVAILABLE_WITH_WARNINGS | 5 | 2026-07-10T00:00:00+00:00 |
| XAUUSD | H4 | TIMEFRAME_NOT_ACTIVE | 0 | — |
| XAUUSD | H1 | AVAILABLE_WITH_WARNINGS | 102 | 2026-07-13T03:00:00+00:00 |
| XAUUSD | M30 | AVAILABLE_WITH_WARNINGS | 205 | 2026-07-13T03:30:00+00:00 |
| XAUUSD | M15 | TIMEFRAME_NOT_ACTIVE | 0 | — |
| XAUUSD | M5 | AVAILABLE_WITH_WARNINGS | 1,235 | 2026-07-13T03:55:00+00:00 |

Direct lanes factually report `HISTORICAL_GAPS_PRESENT`. Inactive construction lanes factually report `CONSTRUCTION_AUTHORITY_NOT_COMMISSIONED` and never fabricate bars.

## Read-only and non-promotion proof

- The service opens the authority database read-only.
- The derived engine is a pure function over an authority-supplied bounded plan.
- Its test verifies deterministic OHLC, rejects an incomplete plan, and verifies byte-for-byte database identity before and after execution.
- No H4 or M15 evidence lane, canonical bar, Truth lane, or Estate Truth lane is created.

## Focused verification

```text
30 tests passed
```

The run covered Market History, SPEC-018, Truth, Estate Truth, and SPEC-025 direct-timeframe compatibility. No unrelated regression suite was run.
