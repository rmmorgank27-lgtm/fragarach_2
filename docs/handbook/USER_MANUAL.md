# User Manual

## What Fragarach II does

Fragarach II presents the condition of a historical-market evidence authority.
Use it to discover approved instruments, inspect health and freshness, request
governed data acquisition, and review the scheduler. Do not interpret a green
status, data coverage score, or historical match as trade advice.

## Start the native console

From the repository root:

```sh
./script/build_and_run.sh
```

Use `./script/build_and_run.sh --verify` when a launch proof is needed. The
application is staged at `dist/Fragarach II.app`.

The default development authority is:

```text
data/runtime/spec002_real_evidence_acceptance.sqlite3
```

Changing the selected authority or repository in Settings is explicit. The
console never searches the disk for a database and never writes SQL directly.

## Main workspaces

### Discover

Use Discover to find registered instruments and inspect their approved provider
representation. Registration, provider mapping, and evidence lanes are
authority facts. If a symbol is absent or retired, register or correct it via
the governed onboarding path rather than creating an ad-hoc symbol.

### Acquire & Import

Use **Manage Data** for an approved lane.

- **Fetch initial history** obtains governed historical coverage.
- **Update** requests the next approved closed boundary.
- **Force refresh** is exceptional; it still validates and preserves conflicts.
- **Custom range** requires reviewed, governed bounds.

The interface shows the provider, requested range, expected edge, and any
reason it cannot proceed. A blocked result must identify both the reason and
the repair action. Do not repeatedly press Fetch for an unchanged boundary:
the scheduler is responsible for normal recurring acquisition.

### Estate Truth

Estate Truth summarizes lanes by market and severity.

- **Healthy / green**: evidence is current for the applicable doctrine.
- **Attention / behind**: evidence is valid but behind its expected boundary.
- **Critical**: evidence cannot currently satisfy an operational requirement.

Select a symbol to see its CAODT, latest canonical edge, provider eligibility,
integrity evidence, and the exact repair path. A lower score is a prompt to
inspect the lane evidence; it is not a market signal.

### Scheduler

The Scheduler view is the operating surface for the persistent LaunchAgent.
It remains active after the app quits. Use it to inspect ready, retrying,
blocked, and running lanes; change the catch-up policy; and use a bounded
repair command when the view names one.

`Pause All` stops dispatch but leaves monitoring alive. `Stop Service` requests
a graceful stop. Do not kill the process during a transaction unless a recovery
procedure specifically requires it.

### System

Use System for provider facts, credentials, configuration, backups, and audit
evidence. Credentials are resolved through the approved chain; never paste a
credential into a log, report, or source file.

## Reading outcomes

| Outcome | Meaning | Operator action |
| --- | --- | --- |
| `committed` | Evidence was accepted. | Review counts and canonical edge if needed. |
| `COMPLETED_WITH_WARNINGS` | Some source rows were rejected but admissible rows committed. | Inspect the listed rejection reasons. |
| `CONFLICT_PRESERVED` | Provider values differ from canonical evidence. | Review; use an explicit correction only with authority. |
| `CORRECTED` | A reviewed correction replaced canonical values with lineage. | Confirm the correction and downstream consumers. |
| `NO_RESULTS` / no matches | The engine found no admissible result. | Read the supplied diagnostic or rejection histogram; do not invent a result. |

## Safe daily routine

1. Open Estate Truth and address Critical items first.
2. Read a Behind lane's reason and prescribed repair action.
3. Let the scheduler perform ordinary boundary updates.
4. Use a manual fetch only for a reviewed operational need.
5. Check System after provider configuration or credential changes.

For a repair, restart, database growth, or provider failure, use the
[maintenance runbook](MAINTENANCE_AND_TROUBLESHOOTING.md).
