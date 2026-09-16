# Global Prime Index CFD Authority V1

**Document Class:** Constitutional evidence authority
**Authority Name:** `GLOBAL_PRIME_INDEX_CFD_AUTHORITY_V1`
**Market:** Broker index CFDs
**Market Code:** `BROKER_INDEX_CFDS`
**Status:** SUPERSEDED FOR NEW ADMISSION ROUTING
**Approved By:** Ray Morgan
**Approval Date:** 2026-09-04

## Purpose and boundary

This document records the historical Global Prime admission baseline for the
exact MT5 CFD representations `US30`, `US500`, and `NAS100`. New admission
routing is governed by `MT5_BROKER_FAMILY_INDEX_CFD_AUTHORITY_V1.json`; it
allows approved equivalent broker routes while retaining the actual route on
each immutable receipt and bar-ingest record.
They remain distinct tradable CFD instruments. They are not the official
DJIA, S&P 500, or Nasdaq-100 calculated indices, and must not replace or amend
the existing `INDICES_*` calculated-index authorities.

The active approved native timeframes are `D1`, `H1`, `M30`, and `M5`. `M15` is
constructed by Fragarach from governed `M5` evidence and is not collected from Windows. Every admitted
bar must come directly from the matching native MetaTrader 5 timeframe. No
resampling, proxy substitution, gap filling, or cross-provider blending is
allowed.

## Identity

| Canonical symbol | Exact provider symbol | Underlying reference |
|---|---|---|
| `US30` | `US30` | Dow Jones Industrial Average reference CFD |
| `US500` | `US500` | S&P 500 reference CFD |
| `NAS100` | `NAS100` | Nasdaq-100 reference CFD |

Historical provider identity remains immutable in existing evidence. New
registrations use the broker-family identity and resolve permitted routes from
the active authority catalogue rather than from importer source code.

## Timestamp and completion authority

The collector must use the MetaTrader5 Python `copy_rates_range` or
`copy_rates_from` API with timezone-aware UTC bounds and preserve the returned
integer `time` field unchanged. Under the official MetaTrader5 Python API
contract, returned bar times are UTC interval-open Unix seconds. The recorded
timestamp policy is `MT5_PYTHON_COPY_RATES_UNIX_UTC_V1`.

Intraday bars use `[open, open + duration)` and are admissible only after the
interval closes. D1 bars are keyed by the returned UTC owner date and are
admissible only after the next D1 bar has opened or the collector otherwise
proves the bar is fully closed. The receiver receipt time never substitutes
for market time.

## Session profile

The observed Global Prime index-CFD session is Monday through Friday from
`01:00` UTC through the interval ending at `00:00` UTC, with the daily
`00:00–01:00` maintenance closure. D1 owner dates are Monday through Friday.
Unexpected missing intervals remain visible as gaps; the importer never fills
them.

## Admission and operations

Only an immutable package accepted in receiver lane `divergence.market_data`,
matching a route and contract declared by the active broker-family authority,
with all three exact symbols, all four native timeframes, valid embedded
checksums, and resolved timestamp policy may enter canonical authority.

Fragarach stores the accepted package identity and delta evidence provenance,
commissions each exact lane, validates its canonical edge, and publishes the
lane through the normal external-consumer contract. The Mac importer owns
updates for these lanes; the general HTTP provider scheduler must not invent a
route beyond the active authority catalogue.
