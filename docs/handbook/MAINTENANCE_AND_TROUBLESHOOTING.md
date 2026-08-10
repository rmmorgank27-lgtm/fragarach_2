# Maintenance and Troubleshooting

## Routine health checks

Run these from the repository root:

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.operations \
  verify --database data/runtime/spec002_real_evidence_acceptance.sqlite3 --json

PYTHONPATH=src python3 -m fragarach_ii.commands.scheduler \
  --database data/runtime/spec002_real_evidence_acceptance.sqlite3 \
  --mode service-status --json
```

Check the native System and Scheduler views for the same facts: service state,
heartbeat, queue depth, blocked lanes, provider facts, CAODT, and integrity.

## Backup and restore doctrine

Create a verified backup before a material migration or compaction. Do not copy
an actively mutating SQLite main file without its WAL; use the governed backup
command instead.

When a large rebuild is required:

1. Stop the scheduler gracefully.
2. Build a new database at a different path.
3. Verify integrity, foreign keys, raw-block totals, and canonical-bar digest.
4. Preserve the old database as a named archive.
5. Atomically switch the live path.
6. Restart the scheduler and verify its status.

Never use in-place deletes against append-only raw evidence or provenance.

## Storage growth doctrine

Expected persistent evidence is bounded by unique raw responses and meaningful
canonical events. It is **not** proportional to scheduler polls.

- `raw_blocks`: one content-addressed raw response.
- `ingest_runs`: one compact receipt per admission attempt.
- `provenance`: inserts, conflicts, and corrections only.
- `UNCHANGED`: must remain zero in provenance. Equal observations are proven by
  their raw block and ingest run.

Use the rebuild utility for legacy authorities that contain historical
unchanged provenance:

```sh
PYTHONPATH=src python3 -m fragarach_ii.authority_rebuild \
  /absolute/source.sqlite3 /absolute/rebuilt.sqlite3
```

It never overwrites the source. Inspect its JSON result and perform the path
swap only after verification succeeds.

## Scheduler lifecycle

The persistent service is managed by:

```text
~/Library/LaunchAgents/com.raymorgan.fragarach-ii.scheduler.plist
```

Use the native Scheduler workspace first. For a controlled diagnostic restart:

```sh
launchctl bootout gui/$(id -u) \
  ~/Library/LaunchAgents/com.raymorgan.fragarach-ii.scheduler.plist
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.raymorgan.fragarach-ii.scheduler.plist
```

After a restart, temporary CPU use can be legitimate while due lanes are
claimed and catch-up work completes. It is not legitimate when the service
reports zero work and remains CPU-bound across multiple monitor intervals.

## Troubleshooting table

| Symptom | Evidence to inspect | Repair |
| --- | --- | --- |
| Lane is Behind after Fetch | Lane reason, expected edge, provider outcome | Use the named repair; confirm whether Fetch was deferred to the scheduler boundary. |
| Lane is Blocked | Block reason, provider facts, retry time | Repair credentials, mapping, or authority as named; do not force a generic retry. |
| Service is high CPU | Service status, queue depth, current stage, recent cycle duration | Allow bounded catch-up to finish. If idle but CPU-bound, capture a process sample and inspect scheduler cycle queries. |
| Repeated provider calls | `ingest_runs`, raw-block hashes, scheduler audit | Confirm each lane's next boundary and retry time; ensure no parallel service is running. |
| Database grows rapidly | `provenance` actions and raw-block count | `UNCHANGED` must be zero. Stop the service, verify the ingestion version, and rebuild a legacy authority if necessary. |
| Provider facts missing | System Provider Facts, provider-facts command | Re-resolve facts or configure/validate the provider credential. The UI must name the affected provider and action. |
| Stale app result | Engine version, execution ID, cache revision, selected-symbol response | Refresh the selected symbol; invalidate presentation cache on a newer engine or result revision. |
| `too many open files` | Service error log and process descriptor count | Restart the LaunchAgent once, then investigate descriptor growth before retrying repeated starts. |

## Escalation packet

For an unresolved issue, capture:

- database path and authority identity;
- service generation, PID, heartbeat, and scheduler status JSON;
- symbol, timeframe, CAODT, expected and actual canonical edge;
- provider, request bounds, response classification, and retry time;
- engine scientific version, execution ID, cache revision, and result status;
- relevant command JSON and a bounded process sample if CPU is abnormal.

Never include provider credentials or raw secret-bearing headers in the packet.
