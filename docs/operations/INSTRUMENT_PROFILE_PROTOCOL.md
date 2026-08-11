# Instrument profile protocol

Fragarach records slow-changing symbol facts as immutable, sourced profile events. The
instrument registration remains the authority for symbol identity; profile corrections
append a replacement event that explicitly supersedes the prior event.

## Required origin research

New-symbol onboarding reports an origin requirement and its current status:

- common stock: `IPO`, `DIRECT_LISTING`, or `FIRST_PUBLIC_TRADING` for the exact listed security;
- crypto: `GENESIS_BLOCK`, `FIRST_BLOCK`, `MAINNET_LAUNCH`, `TOKEN_GENERATION`, or `CONTRACT_LAUNCH` for the represented asset;
- ETF: `FUND_INCEPTION`;
- index: `INDEX_LAUNCH`.

Each event must contain an HTTPS source, source name, retrieval timestamp, evidence
SHA-256, verification status, and explicit `YEAR`, `MONTH`, `DAY`, or `SECOND`
precision. A first-party issuer, network, fund sponsor, index administrator, regulator,
or chain explorer is preferred. Secondary evidence remains `NEEDS_REVIEW` or
`VERIFIED_SECONDARY_SOURCE`; it is never silently promoted to primary evidence.

The reviewed source catalogue is
`config/instrument_profiles/events.v1.json`. Import is intentionally one symbol at a
time:

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.import_instrument_profiles \
  --database /absolute/path/to/fragarach.sqlite3 --symbol AAPL
```

Imports are idempotent. Replacing an origin requires a new event whose
`supersedes_event_id` names the current origin; profile events cannot be updated or
deleted.

## History and extrema

The profile derives its stored D1 start, end, bar count, high, and low from governed
Fragarach bars. These extrema describe the available governed range, not an external
claim about the instrument's lifetime record.

Having one or more bars does not prove maximum history. Until a governed acquisition
receipt proves the provider's earliest boundary, `all_available_history_held` is null
and `completeness_status` is `UNVERIFIED`.

## Existing-symbol review state

The initial reviewed catalogue covers all 13 registered crypto symbols, QQQ, SPY, USO,
DJI, and 16 of the 20 registered stock origins. Important sourced milestones are also
recorded for the four unresolved lineages below, which will appear as
`REQUIRED_MISSING` until suitable origin evidence is recorded:

- `DE`, `DIS`, `JPM`, `LSERIO`.

This is intentional: long-lived companies, mergers, holding-company reorganizations,
dual listings, and predecessor securities must not be flattened into a guessed IPO
date.
