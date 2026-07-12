# SPEC-013 Preflight Report

Date: 2026-07-12

## Authority Mapping

1. Registration identity and uniqueness: `(asset,timeframe)`, provider identity plus timeframe, and canonical identity checksum.
2. Lane identity and uniqueness: `(asset,timeframe)`; lane registration links to `(asset,registration_timeframe)`.
3. Supersession: immutable `authority_events` supports `REGISTRATION_SUPERSEDED` and `LANE_SUPERSEDED`, one successor per predecessor, with free structured body facts.
4. Registration rows have only `REGISTERED_NO_EVIDENCE` and `REGISTERED_WITH_EVIDENCE`; they cannot be rewritten to retired states.
5. Ledger events are append-only, checksum-addressed, update/delete prohibited, and support compatibility facts and supersession chains.
6. Acquisition currently checks registration/provider configuration but not lifecycle supersession.
7. Active lanes are currently all `evidence_lanes` containing bars.
8. Truth and Estate Truth currently include every registered lane with bars, irrespective of lifecycle supersession.
9. Discovery treats any matching registration as normal `OPEN_EXISTING`.
10. Consumer serving paths are `truth_state_for_lane`, `truth_states`, `estate_truth_state`, authority listing, and native SQLite lane reads.
11. Raw blocks link through ingest runs and provenance; provenance links symbol/timeframe/timestamp to canonical bars.
12. No evidence status column exists. Non-serving quarantine can be represented by a latest `LANE_SUPERSEDED` event and enforced in every active resolver while preserving physical rows.
13. JPYCHF registrations: D1, `REGISTERED_WITH_EVIDENCE`, version 1, provider `TWELVE_DATA`, symbol `JPY/CHF`.
14. JPYCHF acquisition runs: 1 completed provider acquisition.
15. JPYCHF footprint: 1 evidence lane, 9 canonical bars, 9 provenance rows, 1 raw block, persisted validation/Truth with score 90 and CAODT 2026-07-10.
16. Retirement is representable without schema change by atomically appending registration and lane supersession events, then treating their structured lifecycle body as controlling active authority.
17. No compatibility blocker found. Registration/evidence rows remain immutable; lifecycle is projected from the existing immutable ledger.

## Controlled Mapping

- registration event body: `lifecycle_state=RETIRED_*`, reason, note, scope, completed timestamp
- lane event body: `operational_state=HISTORICAL_ONLY`, `acquisition_state=ACQUISITION_DISABLED`, `evidence_state=EVIDENCE_QUARANTINED`, `serving_state=NOT_SERVED`
- acquisition guard: reject before provider transport when the latest lane or registration event is retired
- active Truth/estate/discovery/native lane lists: exclude or mark retired by ledger projection
- historical audit: retain registration, lane, bars, raw blocks, provenance, ingest runs, validation, and event chains

No retirement mutation was performed before this report was completed.
