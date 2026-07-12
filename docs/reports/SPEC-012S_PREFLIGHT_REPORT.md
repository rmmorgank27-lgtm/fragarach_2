# SPEC-012S Preflight Report

Date: 2026-07-12

## Registration Authority

1. `instrument_registrations` is keyed by `(asset, timeframe)` with provider identity also unique per timeframe.
2. Timeframe is an immutable identity field and part of the canonical registration JSON/checksum.
3. The writer can be called sequentially, but both Python validation and SQLite currently accept only D1.
4. Provider capability authority exists in `config/providers/authority/TWELVE_DATA_TIME_SERIES_{D1,H1,M30,M5}_V1.json`; each lists FX and CRYPTO among supported market families.
5. Discovery exposed D1 because registration plans, provider mappings, calendar assignment, gap doctrine, and evidence-lane creation were hard-coded to D1.
6. The approved H1/M30/M5 provider contracts retain the same provider instrument mapping, but no schema-authorised intraday registration can be inserted.
7. Acquire previously received one symbol through `ConsoleStore.acquisitionAsset`.
8. Multi-lane handoff would require selected timeframe state and an Acquire timeframe set; mutation cannot be completed before authority revision.
9. Discovery and capability transparency need no schema change. Actual intraday registration does.

## Exact Constraint Found

Migration 4 defines `CHECK (timeframe='D1')` on `instrument_registrations`. Migration 5 defines `CHECK (registration_timeframe='D1')` on `evidence_lanes` and its foreign key points to `(asset, registration_timeframe)`.

SPEC-012S forbids schema migration. This is therefore a genuine immutable-authority incompatibility, not missing application code.

## Safe Implementation Scope

- OIL family ambiguity
- Solana symbols and representations
- restricted Solana spelling correction
- provider capability and registration state per timeframe
- explicit authority-blocked intraday rows
- responsive native lane matrix
- automated and direct native verification
