# SPEC-017 Preflight Report

## Scope and baseline

- Repository baseline: `7779164 repair: restore operational capabilities after navigation refactor`.
- Reviewed authority runtime: `data/runtime/spec002_real_evidence_acceptance.sqlite3`.
- Preflight SHA-256: `da7dfaa6450b95c739f19e70e9912dfa88a6edc4b3584a7107aaf99f12b5cb07`.
- Mutation acceptance runtime: `/tmp/fragarach-spec017.sqlite3`.
- Push is forbidden; the reviewed runtime and unrelated working-tree files are outside the implementation scope.

## Findings

Discovery depended on repeatedly assembled market results, the V1 registration schema required provider identity, Fetch could select an unavailable intent, and History shared a constrained layout with the mutation modes. Existing ingestion, immutable evidence, retirement, backup, settings, credentials, and Truth algorithms were retained.

The minimum compatible repair was a local versioned identity registry, a provider-independent registration contract and migration, registry-first discovery, repaired intent selection and receipts, and a dedicated History presentation.
