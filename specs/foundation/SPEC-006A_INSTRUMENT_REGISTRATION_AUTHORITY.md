# SPEC-006A — Instrument Registration Authority Foundation Amendment

**Classification:** Foundation Specification

**Status:** Implemented; real-evidence migration proven 2026-07-11

## Authority

`instrument_registrations` is the sole operational authority for canonical asset/timeframe identity, family and representation, aliases, real-world instrument facts, provider mapping, calendar assignment, Gap Doctrine assignment, factual evidence status, and deterministic identity checksum. The exact application-table boundary is eight.

Identity uses contract `INSTRUMENT_REGISTRATION_V1`. Canonical JSON is UTF-8, lexicographically key-sorted, compact, and contains explicit nulls. It includes all immutable identity, family, representation, provider, calendar, and doctrine fields and excludes timestamps and mutable status. SHA-256 identifies the exact canonical bytes.

Provider identity keys are compact canonical JSON arrays ordered as provider ID, exact provider symbol, provider exchange, provider instrument type, trading currency, and provider country. Null discriminators remain explicit. SQLite uniqueness protects canonical lanes, provider identities, checksums, and normalized names.

## Family and representation

Each registration is a distinct evidence identity. New multi-representation families use `<INSTRUMENT_FAMILY>.<LOCAL_SYMBOL>`. `semantic_equivalence` is always `DISTINCT_INSTRUMENT`. Family membership never permits merge, substitution, fill, repair, rollup, or price equivalence across CFD, index, ETF, futures, spot, or other representations.

Typed aliases contain exactly alias, normalized alias, and alias type, sort by normalized alias/type, and are naming alternatives only. SQLite JSON1 triggers prevent duplicate and cross-registration collisions with assets, local symbols, and aliases. Provider symbols are mappings, not aliases.

## Mutation doctrine

Registration uses the process-held registered writer and one transaction. Exact-identical registration is idempotent. Every immutable field and registered-at timestamp is protected from update; deletion is prohibited. The only status transition is `REGISTERED_NO_EVIDENCE` to `REGISTERED_WITH_EVIDENCE`, in the ingestion transaction, after a canonical bar exists. It cannot regress.

Bars require an existing registration. Manual ingestion rejects an unregistered lane before preserving raw evidence. Provider acquisition and calendar validation resolve mapping and assignment from SQLite, not historical per-symbol configuration.

Migration 4 transactionally creates the table, backfills AUDUSD, XAUUSD, and BTCUSD from the reviewed manifest, checks coverage, installs enforcement, and records its checksum. Restoration of the verified pre-migration backup is the rollback path; no reverse migration is authorized.

No AAPL registration, discovery, US-equity calendar, Add Symbol UI, new evidence, legacy access, or consumer migration is part of this amendment.

Fragarach II remains a **CANDIDATE AUTHORITY**. **Operations is King.**
