# Fragarach II — Truth Store Doctrine

## Status and authority

This document governs Fragarach II. Any change to the Truth Store itself is a **Foundation Specification** and must be reviewed as such.

Fragarach II remains a candidate authority until runtime operation proves otherwise. Structural tests, successful migrations, and local demonstrations are necessary evidence, but they are not operational trust and do not make the system production-ready.

## Mission

Fragarach II exists only to provide trusted historical market-bar evidence. It may read evidence, validate evidence, store evidence, and serve evidence.

It must not trade, forecast, generate signals, decide engine readiness, interpret what evidence means, maintain consumer-specific truth, or promote data through competing authorities. There is one canonical truth store and one canonical `bars` table.

## Evidence principles

1. Raw source material is evidence and is immutable after registration.
2. Canonical bars never lose their relationship to contributing raw evidence.
3. Provenance is data, not an optional log message.
4. A provider may differ only at the boundary adapter that produces the common staging contract. After staging, every source follows one ingestion pipeline.
5. Stored values, identities, ordering, and merge outcomes must be deterministic.
6. Consumers read the same SQLite authority directly in read-only mode. Consumer-specific copies are not truth.
7. Only the registered writer may mutate the database. Writer ownership is enforced outside the Python API by a process-held filesystem lock.
8. Recovery, integrity verification, and restoration are part of storage correctness.

## Storage form

The authority is one SQLite database using WAL mode, foreign-key enforcement, one registered writer, and concurrent read-only consumers. The initial foundation contains exactly these application tables:

- `raw_blocks`
- `bars`
- `provenance`
- `ingest_runs`
- `lane_state`
- `rollup_state`
- `schema_migrations`

There are no Bronze, Silver, or Gold layers. Raw blocks are immutable. Rollups, when later authorised, are incremental stored evidence derived through the common pipeline. Calendars and gap doctrine, when later authorised, are asset-aware and versioned.

## Change discipline

Schema changes, canonical identity changes, mutation rules, writer registration, transaction semantics, integrity rules, backup or recovery behaviour, and read contracts require a numbered Foundation Specification. Feature work cannot silently redefine them.

## Operating maxim

**Operations is King.** Claims about authority must be supported by continuing runtime evidence, not aspiration.

