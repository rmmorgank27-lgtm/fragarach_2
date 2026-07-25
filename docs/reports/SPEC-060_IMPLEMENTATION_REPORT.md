# SPEC-060 — Scheduler Liveness, Progress and Monitor Reliability

## Acceptance result

Accepted on 2026-07-15 (Australia/Brisbane). The Scheduler remained productive during the reported monitor failure. The repaired service now reports operational health independently from monitor transport, answers bounded monitor probes, and can rebuild only its listener without restarting or mutating Scheduler authority.

## Deterministic root cause

The first authoritative historical transport failure is preserved in `scheduler-service-error.log`: an uncaught `BrokenPipeError` escaped `SchedulerCommandServer._serve` while the accept thread wrote a large status response. That killed the monitor listener while leaving the Scheduler process and heartbeat running.

The current occurrence had a second deterministic trigger in the same publication path:

- the live Scheduler status document had grown to 4,599,377 bytes;
- diagnostics sent the full status request with a 0.5 second timeout;
- normal status used a 5 second timeout and also timed out during the reproduced occurrence;
- the native client treated `status.live == false` as proof that the Scheduler itself was unavailable.

This made a monitor response timeout indistinguishable from Scheduler process loss. It was not a Scheduler cadence, selection, worker, provider, admission, publication, or queue failure.

## Evidence from the occurrence

- Scheduler process: alive, PID 78518 before deployment.
- Ownership: active and unchanged while the app was restarted for the signed build.
- Heartbeat: continued advancing at the service interval.
- Retry Connection before repair: failed after the large full-status response exceeded the request window.
- Scheduler selections and queue work: continued.
- Provider requests and responses: continued.
- Evidence admission and canonical publication: continued.
- Worker pool: workers were allocated during requests and available between requests; no stuck worker or deadlock was found.
- Exceptions: the historical listener `BrokenPipeError` was confirmed. No Scheduler-process crash, queue lock deadlock, or provider-wide failure was found in the current occurrence.
- Remaining queue work after deployment: zero actionable items and one terminal failed artifact (`XAGUSD:M30`, `ATTEMPT_FAILED`, `DISPATCH_REJECTED`). It is classified as blocked, not as an actionable stall.

The post-deployment progress projection recorded:

- selection: `2026-07-15T12:50:00.158900+00:00`;
- provider request: `2026-07-15T12:51:14.399526+00:00`;
- provider response: `2026-07-15T12:51:18.189715+00:00`;
- evidence admission: `2026-07-15T12:51:19.124535+00:00`;
- canonical publication: `2026-07-15T12:51:19.124753+00:00`;
- queue progress: `2026-07-15T12:51:19.124819+00:00`.

## Minimal repair

- Added a service-owned `scheduler_operational_health` projection with independent process, heartbeat, monitor transport, selection, worker, provider, evidence, publication, and queue states.
- Added a dynamic progress window derived from observed cycle duration and active worker allowance. `STALLED` requires actionable or active work with no meaningful progress beyond that window. An empty actionable queue is `IDLE`; process loss is `UNAVAILABLE`.
- Classified non-retryable terminal queue residue as blocked so its age cannot manufacture a stall.
- Replaced diagnostic full-snapshot reachability checks with a small framed `ping` response.
- Bounded the wire-only manual-request and archived-history projections to 50 rows each. Durable journal authority is unchanged.
- Kept client handling isolated, caught disconnect/reset/write failures per client, made the accept loop survive transient socket errors, and reject incomplete or oversized frames explicitly.
- Added `repair-monitor`: it signals the existing process to rebuild only the listener and then verifies the same PID and service generation. It does not restart the Scheduler or change ownership, queue, journal, budgets, cadence, provider state, or commissioning.
- Updated native models and presentation so `HEALTHY`, `IDLE`, `STALLED`, and `UNAVAILABLE` come from the service projection. A disconnected monitor is shown as a transport fact, not reinterpreted as Scheduler failure.

## Focused verification

- 18 focused Python tests passed across SPEC-060, persistent-service, socket-disconnect, framing, and recovery scenarios.
- 36 `OperationsCoreChecks` passed, including the native `HEALTHY + MONITOR_DISCONNECTED` contract and monitor-only action routing.
- One signed release build completed; strict code-sign verification passed; `FragarachII` launched and remained alive (PID 99032 during smoke verification).
- Post-repair status completed in 1.64 seconds and was 2,492,720 bytes, with `live=true`, monitor `CONNECTED`, heartbeat current, and operational health `IDLE`.
- Diagnostics reported process alive, socket present, socket reachable, heartbeat current, and journal writable.
- Native/app restart did not restart the Scheduler: pre-deployment Scheduler PID 78518 remained alive until the explicit service deployment restart.
- Live `repair-monitor` returned `MONITOR_REPAIRED` for PID 2126. Service generation `73826637-e39f-4cde-b53a-a2e0f4a3afc1` and the queue were identical before and after; `scheduler_restarted=false`, `ownership_changed=false`, and `queue_changed=false`.

## Regression protection

This failure mode is protected at each boundary: status size no longer controls diagnostics, a disconnected client cannot kill the listener, transient accept failures do not terminate it, malformed frames are rejected deterministically, service health is not derived from monitor connectivity, and Repair Monitor cannot invoke a full service lifecycle repair. Focused backend and native checks enforce those invariants.

No Scheduler cadence, provider priority, budgets, throughput, commissioning, eligibility, mappings, credentials, canonical publication, or SQLite schema logic was changed.
