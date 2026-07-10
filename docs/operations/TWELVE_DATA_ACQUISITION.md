# Twelve Data Bounded Acquisition

## Credential

Provide the Twelve Data API key to the process through environment variable:

```text
TWELVE_DATA_API_KEY
```

Provision it outside the repository and outside project-generated command text. Do not place it in `.env`, shell scripts, command arguments, SQLite, reports, fixtures, or logs. The adapter uses the official recommended HTTP header authentication method.

## Command

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.acquire \
  --database /absolute/path/to/authority.sqlite3 \
  --provider TWELVE_DATA \
  --asset AUDUSD \
  --timeframe D1 \
  --from-date 2026-07-01 \
  --through-date 2026-07-10 \
  --conflict-mode preserve \
  --json
```

Both dates are inclusive and required. Preserve is the default. Correct must be explicit and retains correction lineage under existing doctrine.

The V1 adapter rejects ranges longer than 5,000 calendar dates. It does not perform implicit latest requests or paging.

## Failure interpretation

Pre-ingestion failures return non-zero and leave authority state unchanged. Provider error and rate-limit bodies are diagnostic for the running command only and are not stored as evidence.

If ingestion commits but calendar validation fails, the command reports committed evidence and clears the affected validation summary rather than leaving stale facts. Rerun only after diagnosing the factual error; no automatic retry path exists after commit.

## Official contract references

- [Twelve Data API usage and header authentication](https://twelvedata.com/docs/advanced/api-usage)
- [Twelve Data time-series documentation](https://twelvedata.com/docs)
- [Twelve Data error responses](https://twelvedata.com/docs/introduction/errors)

Provider availability and plan entitlements are external operational facts. A structurally successful response does not certify market completeness or correctness.
