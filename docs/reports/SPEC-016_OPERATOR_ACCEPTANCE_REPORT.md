# SPEC-016 Operator Acceptance Report

Date: 2026-07-12

Signed application baseline build: `50a6c6f` plus the reviewed SPEC-016 working tree. Launch and process verification passed.

Direct acceptance confirmed:

- Silver/XAGUSD and registered D1 were selected only from authority-backed controls.
- Custom Range displayed native locale date controls and the exact completed D1 maximum.
- Clipboard `01/01/1980` and `01/01/1990` were parsed using `en_AU`, visibly interpreted, and normalised to canonical `1980-01-01 → 1990-01-01`.
- Review displayed the canonical inclusive backend range.
- A reversed 1990→1980 range showed inline correction guidance, disabled review, ran no command, and displayed no stale result.
- The through-date control constrained selection to the visible completed D1 boundary; model tests also reject injected future values.
- Changing instrument, mode, dates, file, intent, or conflict policy cleared current plan/result ownership.
- Failure rendering is plan-revision-owned and reports zero mutation facts with `No evidence was written`; prior receipt fields cannot be combined with it.
- Previous receipts remained available through History.

Screenshots:

1. `SPEC-016/screenshots/01-calendar-controlled-range.png`
2. `SPEC-016/screenshots/02-pasted-normalized-canonical-range.png`
3. `SPEC-016/screenshots/03-canonical-reviewed-range.png`
4. `SPEC-016/screenshots/04-reversed-range-validation.png`
5. `SPEC-016/screenshots/05-controlled-instrument-timeframe.png`
6. `SPEC-016/screenshots/06-future-boundary-control.png`
7. `SPEC-016/screenshots/07-clean-invalid-plan-no-stale-result.png`
8. `SPEC-016/screenshots/08-history-previous-receipts.png`

Runtime database SHA-256 before and after: `88f962b004ac359bf9263c1102a2b265105d5365764f28252d3d15c259d061c6`. Invalid-input acceptance created no raw block, evidence, registration, retirement, or authority event.
