# SPEC-040 Canonical Freshness Authority Repair

## Outcome

Fragarach II now separates the timestamp of the latest stored canonical observation from the timestamp at which an authority snapshot is constructed.

The backward-compatible `caodt` field is explicitly the Latest Canonical Observation. `authority_generated` is diagnostic publication provenance and is not an input to freshness. `authority_revision` is a stable SHA-256 revision of lane and registration authority metadata; it does not change merely because a snapshot is republished or another market bar is stored.

Freshness is evaluated at publication from only:

- the approved operational calendar;
- the commissioned timeframe; and
- the latest canonical observation stored in `bars`.

Persisted validation summaries remain visible as validation evidence but no longer determine current-edge freshness. This removes the defect where an old validation boundary could continue to report a stale lane as fresh.

## Published lane fields

Each served lane with authority now exposes:

- `latest_canonical_observation`;
- `authority_generated`;
- `authority_revision`;
- `freshness` (`Current`, `Behind`, or `Unavailable`); and
- `validation`.

For D1, Latest Canonical Observation is the newest canonical bar open. For H1, M30, and M5 it is the end of the newest canonical closed interval. Range-filtering historical bars cannot change this lane-level value.

The estate response includes the same fields per served lane and embeds a Lane Freshness report containing every active commissioned lane, including lanes with no canonical observations.

## Scheduled acquisition audit

The live read-only audit is recorded in [spec040/LANE_FRESHNESS_AUDIT.md](spec040/LANE_FRESHNESS_AUDIT.md).

At `2026-07-14T03:11:56.534134+00:00` it found:

| State | Lanes |
|---|---:|
| Current | 0 |
| Behind | 69 |
| Unavailable | 5 |
| Total | 74 |

The repository and runtime contain no scheduled acquisition implementation or scheduler-run record. The report therefore states `NO_SCHEDULED_ACQUISITION_IMPLEMENTATION`; it does not infer scheduler health from publication time. Provider-run facts and whether the last recorded run advanced the canonical edge are reported separately per lane.

No provider acquisition was executed and no canonical observation was inserted, updated, or deleted during this repair. Consequently, the audit reports the actual stale estate rather than masking it as current.

## Acceptance evidence

Automated coverage proves:

1. XAUUSD D1 publishes the newest D1 bar as Latest Canonical Observation.
2. H1 publishes the newest canonical closed-bar end.
3. M30 publishes the newest canonical closed-bar end.
4. M5 publishes the newest canonical closed-bar end.
5. Republishing without data changes advances Authority Generated while Latest Canonical Observation and Authority Revision remain stable.
6. Adding a new canonical test observation advances Latest Canonical Observation and a later publication advances Authority Generated.
7. Existing external-consumer and market-history contract tests pass without consumer-side freshness changes.
8. The Lane Freshness audit deterministically reports Current, Behind, and Unavailable reasons and is read-only.
9. A persisted validation summary that was current at its old boundary cannot keep a lane current on the following operational day.

## Verification

- SPEC-040 focused Python tests: 30 passed.
- Full Python discovery: 181 passed; one pre-existing unrelated retirement re-registration test errors with `INVALID_SUPERSESSION_RANGE` in the already-modified retirement/authority-ledger path.
- `swift build`: passed.
- `swift test`: package builds, then reports that no Swift test target exists.
- `swift run OperationsCoreChecks`: existing check executable stops at `AUD outside sessions`; this path was already modified outside SPEC-040 and is not used by the freshness implementation.

SignalBar and MorphixFC were not modified. Their existing CAODT-compatible consumer surface continues to receive canonical market time, while Fragarach II now owns the explicit freshness decision and the distinct publication timestamp.
