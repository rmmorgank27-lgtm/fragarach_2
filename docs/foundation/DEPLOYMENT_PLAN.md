# Fragarach II — Deployment Plan

## Purpose

This plan sequences Fragarach II from a small storage foundation toward a possible operational authority. It does not declare a deployment date or production readiness.

## Stage 1 — Storage foundation

Implement and prove SPEC-001: one SQLite database, WAL mode, foreign keys, seven foundation tables, immutable raw blocks, provenance constraints, registered-writer exclusion, concurrent readers, transactional rollback, restart persistence, integrity verification, and backup/restoration procedure.

Exit evidence is a repeatable focused test run and a factual implementation report. The outcome remains a candidate authority.

## Stage 2 — Manual evidence path

Under later specifications, define the common staging contract and manual CSV boundary adapter. Prove raw capture, validation, deterministic merge behaviour, rejection handling, reruns, crash recovery, and restoration before any automated acquisition begins.

Initial assets are AUDUSD, XAUUSD, and BTCUSD. Native timeframes are D1 and H1. W1 and MN1 are later stored rollups derived from D1.

## Stage 3 — Temporal doctrine

Under later Foundation Specifications, introduce asset-aware versioned calendars and versioned gap doctrine. Neither may create a competing authority or interpret evidence for a consumer.

## Stage 4 — Incremental rollups

Implement deterministic D1-derived W1 and MN1 storage with explicit provenance and restartable `rollup_state`. Prove boundary periods, calendar versioning, replay, correction, and recovery.

## Stage 5 — Automated provider boundary

Only after manual ingestion, deterministic merging, and database recovery are proven may one automated provider be introduced. Provider-specific behaviour ends when it emits the common staging contract.

## Stage 6 — Operational proving

Run the candidate authority under controlled operations. Exercise backup restoration, interruption, disk and lock faults, integrity monitoring, and read-consumer concurrency. Define evidence thresholds and observation duration in a later deployment specification.

## Explicit exclusions from Stage 1

Provider acquisition, full CSV ingestion, calendars, rollup processing, Morphix integration, background scheduling, dashboards, native applications, chart work, migration from Fragarach, and recovery of the existing Fragarach project are not part of SPEC-001.

Promotion to operational authority requires an explicit decision based on runtime evidence. It is never implied by test success.

