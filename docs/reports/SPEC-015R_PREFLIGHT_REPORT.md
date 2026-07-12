# SPEC-015R Preflight Report

Status: COMPLETE

## Baseline finding

The requested checkpoint `5849a47` is the current `HEAD` and already contains the navigation refactor from `50a6c6f`. The last checkpoint before that refactor is `68f0896`. Capability tracing therefore compared the current tree with both `5849a47` (rejected operator state) and `68f0896` (pre-navigation implementation).

## Safety controls

- Reviewed runtime: `data/runtime/spec002_real_evidence_acceptance.sqlite3`
- Reviewed-runtime SHA-256 before acceptance: `88f962b004ac359bf9263c1102a2b265105d5365764f28252d3d15c259d061c6`
- Native mutation acceptance used `/tmp/fragarach-spec015r.sqlite3`, created with SQLite backup.
- No provider fetch was executed; bounded D1 Custom Range was accepted through enabled final confirmation.
- No push was performed during repair.

## Capability trace

The proven services remained available: market discovery and registration, bounded acquisition, immutable CSV import, SPEC-013 retirement, verification, backup, diagnostics settings, Authority Ledger, and operation history. The regression was in the navigation/control layer: segmented pickers displayed destinations without explicit selection tags, and retirement receipt state could be cleared during the post-mutation selector refresh.
