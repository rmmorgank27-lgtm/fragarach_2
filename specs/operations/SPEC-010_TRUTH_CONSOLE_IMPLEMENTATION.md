# SPEC-010 — Truth Console (Implementation)

**Document ID:** `SPEC-010_TRUTH_CONSOLE_IMPLEMENTATION`

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`

**Status:** Implementation

**Authority:** Candidate Authority

**Doctrine:** Operations is King

**Push:** Forbidden

---

# 1. Objective

Implement the first operational Truth Console.

The Truth Console is the primary operational interface for Fragarach II.

It consumes existing authority and Truth Engine services only.

It performs no calculations, data acquisition, or validation. It visualises operational truth.

---

# 2. Scope

Use only existing services:

- Authority Service
- Truth Engine
- Read-only SQLite
- Existing OperationsCore bridge

No database schema changes, migration, new authority calculations, or business logic duplication.

---

# 3. Main Screen

The application shall launch into `Truth`. Truth becomes the default operational view.

---

# 4. Estate Summary

Display Overall Truth Score, Overall Authority State, Overall CAODT, Total Symbols, Healthy, Attention, and Critical.

Display latest Validation, Provider Update, Snapshot (placeholder), and Backup (placeholder).

---

# 5. Truth Matrix

Display every Symbol × Timeframe. Each cell displays Truth Score and Authority colour. Selecting a cell loads Symbol Detail.

---

# 6. Symbol Detail

Display Symbol, Timeframe, Truth Score, Authority State, CAODT, Provider, Coverage, Freshness, Validation, Gap Classification, Gap Impact, Truth Components, and Explanation.

No charts or editing. Version 1 is informational.

---

# 7. Truth Components

Display every Truth Engine component and its explanation directly from TruthState. Do not recalculate.

---

# 8. Provider Summary

Display Provider, Confidence, Freshness, and Entitlement. Unknown values remain visible.

---

# 9. Gap Summary

Display Classification, Impact, Current, Recent, Historical, and Total. Do not implement repair or maintenance.

---

# 10. Search

Support fast filtering by Symbol, Alias, and Market. No database mutation.

---

# 11. Refresh

Provide a Manual Refresh button. Refresh reloads TruthState. No automatic polling in Version 1.

---

# 12. Performance

The console shall remain responsive. The Truth Matrix loads from cached Truth Engine output. Sorting and filtering shall never invoke authority recomputation.

---

# 13. Native Rules

SwiftUI only. Read-only. No write path, database mutation, provider access, or background maintenance.

---

# 14. Explicit Exclusions

Do not implement charts, trend graphs, maintenance, snapshots, backups, gap repair, provider management, administration, settings, editing, consumer integration, forecasting, research, or trading.

---

# 15. Acceptance

Acceptance requires:

- Truth becomes default application view.
- Estate summary visible.
- Truth Matrix operational.
- Symbol Detail operational.
- Truth components displayed.
- Provider summary displayed.
- Gap summary displayed.
- Search operational.
- Manual refresh operational.
- No schema changes.
- No migration.
- Existing tests remain green.
- Native build passes.
- No push.

---

# 16. Reports

Produce `SPEC-010_PREFLIGHT_REPORT.md`, `SPEC-010_IMPLEMENTATION_REPORT.md`, and `SPEC-010_ACCEPTANCE_REPORT.md`. If blocked, produce `SPEC-010_TRUTH_CONSOLE_BLOCKER.md`.

---

# 17. Local Checkpoint

Create one reviewed local checkpoint after successful acceptance. No push.

---

## Engineering Instruction

Build the Truth Console as a thin operational client. It shall consume the Authority Service and Truth Engine and never duplicate operational calculations. It shall make the operational state of the historical data estate visible within five seconds of application launch.

Do not improve the architecture. Do not redesign the UI. Build the console using the services that already exist. If additional capability is required, stop and report the missing service rather than implementing it in the UI.

**Operations is King.**
