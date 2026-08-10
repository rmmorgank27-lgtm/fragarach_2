# Integration Manual

## Supported integration boundaries

Fragarach II has two intentional integration modes:

1. **Read evidence** through a read-only SQLite connection or a repository
   command that emits JSON.
2. **Request an operation** through the scheduler command transport or the
   configured Python CLI.

An integration must not write the authority database, edit scheduler files, or
create a second acquisition loop.

## Bounded market-history ranges

Historical analysis and back-testing use the additive
`fragarach.market_history_range.v1` contract. Existing full-history, latest,
current, catalogue, and command interfaces retain their established defaults
and response meaning.

The Fragarach II library operation is:

```text
get_history_range(
    symbol,
    timeframe,
    start_utc,
    end_utc_exclusive,
    as_of_utc,
    consumer
)
```

Fragarach Lite continues to expose the compatible loopback endpoint:

```text
GET /v1/market-history?symbol=<symbol>&timeframe=<timeframe>
    &start_utc=<inclusive>&end_utc_exclusive=<exclusive>
    &as_of_utc=<evidence-cutoff>&consumer=<application>
```

Legacy Lite requests that omit `consumer` remain accepted and are identified
explicitly as `UNSPECIFIED_LEGACY_CONSUMER`. New historical runners must send
their stable application identity. A synthetic lane also requires
`evidence_requirement=SYNTHETIC_PERMITTED`; Fragarach II enforces the synthetic
registry's consumer permission.

Responses identify the request and consumer, explicit availability and
coverage states, requested and effective boundaries, completed observations,
CAODT, authority kind and revision, source receipt, evidence class, warnings,
and truncation. Callers must branch on `availability_state`; an empty or
unavailable result never relies on a null value to convey evidence meaning.

The range is `[start_utc, end_utc_exclusive)` by observation open time. A row
is returned only when its approved completion time is no later than both the
requested end and the independent `as_of_utc` cutoff. D1 completion uses the
registered market calendar. Intraday completion uses its admitted close time
and approved interval profile. If `as_of_utc` or authority coverage shortens a
request, the response declares `PARTIAL` and names each truncation reason.

### Ordered-range fingerprint

`ordered_range_fingerprint` is SHA-256 over one compact UTF-8 JSON line for
each returned observation, in returned order:

```text
[symbol,timeframe,open_epoch,completed_epoch,open,high,low,close,volume]\n
```

The canonical JSON has no insignificant whitespace. Symbol and timeframe are
normalised, timestamps are UTC epoch seconds, and stored OHLCV representations
are preserved. Changing an observation's identity, order, completion time, or
content therefore changes the fingerprint. Equivalent Fragarach II and Lite
lanes produce the same ordered-range fingerprint even though their
authority-specific receipts differ.

All bounded reads use read-only database connections. They do not acquire,
refresh, generate, admit, or copy market history.

## Read-only SQLite contract

Open the authority with SQLite read-only URI mode and enforce query-only
access. Use fixed, bounded `SELECT` statements. The native app follows this
same rule.

```text
file:/absolute/path/to/authority.sqlite3?mode=ro
```

The authoritative tables are:

| Table | Purpose |
| --- | --- |
| `bars` | Canonical OHLCV observations |
| `raw_blocks` | Deduplicated source-response evidence |
| `provenance` | Insert, conflict-preserved, and correction lineage |
| `ingest_runs` | Admission outcome receipts |
| `lane_state` | Canonical lane watermark and validation state |
| `rollup_state` | Derived rollup watermark, if used |
| `instrument_registrations` | Approved instrument identity |
| `evidence_lanes` | Commissioned `(symbol, timeframe)` lanes |
| `authority_events` | Append-only authority ledger |
| `scheduler_runtime_state` | Current scheduler state document |
| `scheduler_audit_events` | Immutable scheduler event receipts |
| `schema_migrations` | Executed schema history |

### Evidence semantics

`bars` is current canonical truth. `raw_blocks` and `ingest_runs` prove what
was received and admitted. `provenance` is deliberately sparse:

- `INSERT` proves an admitted canonical observation.
- `CONFLICT_PRESERVED` proves conflicting provider evidence was retained.
- `CORRECTED` proves an explicit canonical correction and links to the prior
  supporting event.
- Equal observations are not provenance events. Their raw block and ingest-run
  receipt are sufficient evidence.

Never infer that the absence of a provenance row means a provider request did
not happen; inspect the associated ingest run and raw block.

## JSON command interfaces

Run commands from the repository root with the intended Python executable and
`PYTHONPATH=src`.

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.operations \
  verify --database /absolute/path/to/authority.sqlite3 --json

PYTHONPATH=src python3 -m fragarach_ii.commands.lane_freshness \
  --database /absolute/path/to/authority.sqlite3 --format json
```

Useful command modules include:

| Module | Responsibility |
| --- | --- |
| `commands.operations` | Identity, integrity verification, and backup |
| `commands.acquire` | Reviewed provider acquisition |
| `commands.ingest_file` | Manual evidence ingestion |
| `commands.validate_lane` | Lane validation |
| `commands.scheduler` | Service status and command transport |
| `commands.provider_facts` | Provider capability facts |
| `commands.authority` | Authority and provider-contract inspection |

Use `--json` where supplied. Treat contract identifiers and named reason codes
as stable integration values; do not parse human-readable UI text.

## Scheduler command transport

The persistent service owns recurring acquisition. Query it with:

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.scheduler \
  --database /absolute/path/to/authority.sqlite3 \
  --mode service-status --json
```

Commands are idempotently acknowledged and tied to a service generation. A
direct CLI scheduler run is diagnostic or recovery-only; it must not compete
with a live LaunchAgent.

## Versioning and invalidation

Consumers should retain the source database path, schema migration version,
authority change token, CAODT, and relevant provider/engine version. A cache
key based only on symbol and CAODT is insufficient when an engine execution,
scientific version, or published result revision changes.

## Failure handling

Return the upstream reason and prescribed repair path to the caller. Do not
silently retry a `BLOCKED`, provider-credential, route, or authority failure.
For transient transport or budget failures, obey the scheduler's recorded
retry time rather than creating a parallel retry loop.
