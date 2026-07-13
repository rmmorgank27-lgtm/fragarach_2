# SPEC-023 — Instrument Reactivation and Permanent Removal

## Objective

Complete the operational lifecycle for retired instruments without duplicate canonical identity, duplicate provider mappings, silent overwrite, or direct database manipulation.

## Lifecycle

Discovery must project the current immutable authority head. A retired registration offers:

- **Reactivate** (preferred): append registration and lane revisions that restore `ACTIVE`; preserve canonical identity, provider mappings, evidence, provenance, and Truth history.
- **Permanently Remove**: an exceptional, explicitly confirmed authority tombstone. Because Fragarach evidence, provenance, registrations, and ledger events are immutable, this action is available only when the retired registration has no accepted bars, raw evidence blocks, or provenance records. Audit history remains preserved.

A fresh registration after permanent removal must match the preserved canonical identity checksum. It appends a new active authority revision and must not insert a duplicate registration or provider mapping.

## Operator contract

Discovery presents retirement state, retirement timestamp, reason, and actions. Reactivation routes directly to Fetch. Permanent removal requires the typed confirmation:

```text
PERMANENTLY REMOVE <SYMBOL>
```

If immutable evidence exists, permanent removal is blocked with a factual explanation and Reactivate remains available.

## Acceptance

For `XAGUSD`, both paths are deterministic:

```text
Existing retired authority → Reactivate → Fetch → Truth refreshed
Existing retired authority → Permanently Remove → Fresh registration → Fetch → Truth
```

No manual database edit, direct SQLite manipulation, duplicate canonical registration, or duplicate provider mapping is permitted.
