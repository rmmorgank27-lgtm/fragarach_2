# SPEC-041 — Fragarach II Scheduled Acquisition & Scheduler Monitor

## Status

Implemented.

## Objective

Fragarach II automatically acquires every commissioned lane at its approved operational-calendar boundary and exposes the health of that authority through a native Scheduler workspace.

The implementation does not change canonical history, ingestion doctrine, validation, SignalBar, or MorphixFC.

## Authority flow

```text
Operational calendar
→ determine due commissioned lanes
→ acquire only the missing edge range
→ canonical validation
→ immutable ingest
→ publish authority revision
→ recompute freshness
```

The scheduler is a Fragarach II core service started and stopped with the native application. It sleeps until the exact next approved boundary; it does not poll and has no cron or external scheduler dependency.

## Scheduling

- `M5`, `M30`, and `H1` use the approved closed-interval profile.
- `D1` uses the calendar's explicit session close, timezone, owner-day offset, and acquisition delay.
- Startup performs one bounded catch-up pass for lanes already behind, then waits for exact boundaries.
- A lane is attempted at most once for one scheduled boundary.

## Acquisition and publication

- Bounds begin at the first missing canonical observation and end at the expected canonical edge.
- Existing immutable merge and validation paths remain the only publication route.
- A successful ingest advances `lane_state.state_version`; the published authority revision includes that publication state.
- One failed lane never stops another lane.

## Operational state

Scheduler state and recent events are kept in `<database>.scheduler.json`. This file is an operational journal, not canonical market history. The constitutional ten-table database boundary is unchanged.

Each lane exposes `Current`, `Waiting`, `Running`, `Behind`, `Unavailable`, or `Failed`, plus canonical and expected edges, lag, next acquisition, last acquisition, duration, result, and reason.

## Native monitor

Primary navigation is:

```text
Overview
Estate
Scheduler
History
Manage Data
```

The Scheduler workspace includes Authority Health, scheduler runtime, next run, Current, Behind, Unavailable, last success, last failure, live acquisition activity, a commissioned-lane table, and a recent event log. It receives live JSON-line snapshots without an application restart.

## Acceptance

Automated coverage proves startup lane loading, timeframe-specific due selection, D1 session-close eligibility, failure isolation, authority-revision advancement, freshness advancement, live stage updates, and immediate consumer visibility after publication.
