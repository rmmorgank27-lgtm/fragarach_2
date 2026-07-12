# SPEC-012S Multi-Timeframe Authority Blocker

Date: 2026-07-12

## Exact Immutable Constraints

`src/fragarach_ii/storage/schema.py`, migration 4, defines:

```sql
CHECK (timeframe='D1')
```

on `instrument_registrations`.

Migration 5 defines:

```sql
CHECK (registration_timeframe='D1')
```

on `evidence_lanes`, whose foreign key is:

```sql
FOREIGN KEY (asset,registration_timeframe)
  REFERENCES instrument_registrations(asset,timeframe)
```

The registered writer also rejects any candidate whose timeframe is not D1, mirroring the immutable database rule.

## Operational Effect

An attempted H1, M30, or M5 registration cannot satisfy the existing table contract. Sequential writer coordination cannot bypass the SQLite CHECK constraint. Altering it requires a schema migration, explicitly forbidden by SPEC-012S.

Approved provider contracts establish that Twelve Data has timeframe contracts for these market families, but provider capability does not override registration authority.

## Required Resolution

Authorise a foundation amendment and migration that:

- permits controlled registration timeframes beyond D1;
- defines how intraday calendar/timeframe authority and gap doctrine are stored;
- revises evidence-lane registration linkage without weakening immutability;
- preserves existing D1 identities and checksums;
- proves migration and rollback against real evidence.

## Checkpoint

No local checkpoint was created because SPEC-012S permits it only after every acceptance gate passes. No push was performed.
