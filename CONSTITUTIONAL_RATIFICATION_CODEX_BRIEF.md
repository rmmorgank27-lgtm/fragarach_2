# Fragarach II — Corrected Constitutional Ratification Codex Brief

**Date:** `2026-07-11`  
**Repository:** `/Users/raymorgan/VSC/Fragarach_2`  
**Task:** Repair canonical constitutional layout, review, and ratify if clean  
**Implementation work:** Forbidden  
**Push:** Forbidden  
**Doctrine:** `Operations is King`

---

# Mission

Repair the known mechanical repository-layout issues, then review and, only if clean, ratify the complete Fragarach II Version 1 constitutional authority set.

This task does not implement market-data functionality.

---

# Known Mechanical Repairs Authorised

The following repairs are expressly authorised:

1. Rename:

   ```text
   constitution/doctrine/
   ```

   to:

   ```text
   constitution/doctrines/
   ```

2. Ensure the ratification brief is at repository root:

   ```text
   CONSTITUTIONAL_RATIFICATION_CODEX_BRIEF.md
   ```

3. Install the genuine Constitutional Root at:

   ```text
   constitution/CONSTITUTION.md
   ```

4. Replace the manifest with the corrected:

   ```text
   constitution/CONSTITUTIONAL_AUTHORITY_MANIFEST_V1.md
   ```

5. Remove empty temporary file:

   ```text
   constitution/cons.txt
   ```

6. Remove `.DS_Store` files under `constitution/`.

7. Move the duplicate/misnamed file:

   ```text
   constitution/Fragarach II Constitution.md
   ```

   out of the constitutional authority tree, because its internal identity is `MARKET_AUTHORITY_TEMPLATE_V1`.

   Preserve it for audit at:

   ```text
   docs/archive/constitutional_import/Fragarach_II_Constitution_duplicate_market_template.md
   ```

   Do not treat it as the Constitutional Root.

These are authorised path and housekeeping corrections. Do not alter constitutional meaning while performing them.

---

# Canonical Inventory

Expected controlled constitutional documents:

```text
1 Constitutional Root
2 authority templates
9 Base Doctrines
36 Timeframe Authorities
1 Manifest
49 controlled constitutional documents
```

Canonical paths:

```text
constitution/CONSTITUTION.md
constitution/CONSTITUTIONAL_AUTHORITY_MANIFEST_V1.md
constitution/templates/
constitution/doctrines/
constitution/authorities/
```

The root-level brief is not counted as constitutional authority.

---

# Corrected Structural Rules

Do not treat multiple level-one Markdown headings as a material blocker.

The current constitutional house style permits them.

Do not treat intentional placeholders inside the two controlled template files as unresolved constitutional placeholders.

Unresolved placeholders remain forbidden in:

- the Constitutional Root;
- doctrines;
- timeframe authorities;
- the manifest;
- reports.

Templates retain:

```text
Status: TEMPLATE
```

They are accepted as controlled templates and are not converted to `APPROVED`.

---

# Absolute Prohibitions

Do not:

- implement H1, M30, M5, or any runtime behaviour;
- write an implementation specification;
- change Python, Swift, SQL, schemas, configuration, databases, acquisition, ingestion, registration, or evidence lanes;
- invent missing authority;
- silently resolve a material semantic conflict;
- push any commit;
- discard or include unrelated user work.

---

# Phase 1 — Baseline and Mechanical Repair

Record:

```bash
git status --short
git rev-parse --short HEAD
git log -1 --oneline
```

Preserve unrelated changes.

Perform only the authorised mechanical repairs listed above.

After repair, prove:

- `constitution/CONSTITUTION.md` exists;
- `constitution/doctrines/` exists;
- `constitution/doctrine/` does not exist;
- all 36 timeframe parent paths resolve;
- the duplicate market-template claimant is outside `constitution/`;
- root brief is at repository root;
- no `.DS_Store` or temporary `cons.txt` remains under `constitution/`.

---

# Phase 2 — Inventory and Structural Audit

Prove exact counts:

```text
Constitutional Root: 1
Templates:           2
Base Doctrines:      9
Timeframe Authorities: 36
Manifest:            1
Controlled total:    49
```

Validate:

- UTF-8 readability;
- filenames and document IDs;
- repository-location metadata;
- governing Constitution references;
- parent doctrine references;
- market and timeframe codes;
- validator identities;
- ordered numbered Articles or Sections;
- balanced code fences;
- local constitutional references;
- duplicate identities;
- secrets;
- unresolved placeholders outside templates.

Compute SHA-256 for every controlled constitutional document.

---

# Phase 3 — Semantic Audit

Audit universal invariants:

- Constitution → Doctrine → Authority → Specification → Implementation → Acceptance;
- Instrument Registration → Evidence Lane → Evidence;
- implementation never invents authority;
- only affected incompatible paths stop;
- Current-As-Of Truth remains visible;
- accepted evidence remains readable during repair;
- no silent cross-provider, cross-venue, cross-session, cross-adjustment, cross-unit, or cross-identity construction;
- no fabricated no-trade bars;
- no previous-close gap filling;
- immutable correction and conflict evidence;
- direct and derived evidence remain distinguishable.

Audit timeframe chain:

```text
D1 may consume authorised H1, M30, or M5
H1 may consume authorised M30 or M5
M30 may consume authorised M5
M5 is direct evidence only in Version 1
```

Audit request ceilings:

```text
Provider documented hard maximum: 5,000
Fragarach constitutional ceiling: 4,000
```

Audit each family against its Base Doctrine and four Timeframe Authorities.

---

# Phase 4 — Decision Gate

## Clean Result

Only if there are zero material blockers:

Change to `APPROVED`:

- `constitution/CONSTITUTION.md`;
- 9 Base Doctrines;
- 36 Timeframe Authorities.

Record:

```text
Approval Date: 2026-07-11
Effective Date: 2026-07-11
Constitutional Authority Owner: Ray Morgan
```

Retain both template statuses as:

```text
TEMPLATE
```

Record their disposition as accepted controlled templates in the acceptance report.

Change the Manifest to:

```text
RATIFIED
```

Recompute SHA-256 after status changes.

## Material Blocker

If a material semantic conflict remains:

- do not approve the affected document;
- do not invent a correction;
- do not implement around it;
- create `docs/reports/CONSTITUTIONAL_AUTHORITY_RATIFICATION_BLOCKER_REPORT.md`;
- identify exact files, sections, consequence, and owner decision.

Mechanical repairs may still be committed separately only if the final report clearly proves that they changed no constitutional meaning.

---

# Phase 5 — Verification

Run the current repository verification:

- Python suite;
- native Swift checks;
- Swift build;
- native application launch verification;
- nine-table read-only authority check;
- secret scan;
- runtime database hash before and after;
- final Git diff review.

Expected:

- no implementation change;
- no schema or database change;
- existing D1 behaviour unchanged;
- only authorised layout repairs, constitutional status fields, manifest, and reports changed.

---

# Phase 6 — Acceptance Report and Commit

For clean ratification, create:

```text
docs/reports/CONSTITUTIONAL_AUTHORITY_RATIFICATION_ACCEPTANCE_REPORT.md
docs/reports/CONSTITUTIONAL_AUTHORITY_RATIFICATION_ACCEPTANCE_REPORT.json
```

Include:

- baseline;
- repair proof;
- inventory;
- SHA-256 table;
- structural audit;
- semantic audit by family;
- test/build/launch results;
- database immutability proof;
- exact ratification state;
- final diff;
- checkpoint.

Create one local checkpoint:

```text
Ratify Fragarach II constitutional authority
```

Do not push.

If semantic blockers remain but the authorised mechanical repair is clean, create a separate local checkpoint only if repository practice and the final report justify it:

```text
Repair Fragarach II constitutional layout
```

Do not push.

---

# Final Response

Return:

- mechanical repair result;
- clean ratification or blocker result;
- exact inventory;
- verification results;
- report paths;
- checkpoint hash if created;
- confirmation that nothing was pushed.

**Operations is King.**
