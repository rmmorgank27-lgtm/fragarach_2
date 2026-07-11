# Fragarach II Constitutional Authority Manifest V1

**Document ID:** `CONSTITUTIONAL_AUTHORITY_MANIFEST_V1`  
**Repository:** `/Users/raymorgan/VSC/Fragarach_2`  
**Date:** `2026-07-11`  
**Status:** `RATIFIED`  
**Authority State:** `RATIFIED CONSTITUTIONAL AUTHORITY`  
**Doctrine:** `Operations is King`

---

# 1. Purpose

This manifest identifies the complete Version 1 constitutional authority set for Fragarach II.

The governing hierarchy is:

```text
Constitution
↓
Base Doctrine
↓
Timeframe and Other Authority Documents
↓
Specifications
↓
Implementation
↓
Acceptance Proof
```

Implementation MUST NOT invent authority.

---

# 2. Ratification Scope

The complete controlled set is:

```text
1 constitutional root
2 authority templates
9 market-family base doctrines
36 timeframe authorities
1 constitutional manifest
49 controlled constitutional documents
```

The 47 market-authority documents are:

```text
2 templates
9 doctrines
36 timeframe authorities
```

The Constitutional Root and this Manifest are additional controlled documents.

No implementation specification, schema migration, database operation, provider client, native workflow, or runtime behaviour is approved by this manifest.

---

# 3. Canonical Repository Paths

```text
constitution/CONSTITUTION.md
constitution/CONSTITUTIONAL_AUTHORITY_MANIFEST_V1.md
constitution/templates/
constitution/doctrines/
constitution/authorities/
```

The directory name `constitution/doctrine/` is not canonical.

---

# 4. Authority Templates

| Document | Repository path | Controlled state |
|---|---|---|
| Market Authority Template V1 | `constitution/templates/MARKET_AUTHORITY_TEMPLATE_V1.md` | `TEMPLATE` |
| Timeframe Authority Template V1 | `constitution/templates/TIMEFRAME_AUTHORITY_TEMPLATE_V1.md` | `TEMPLATE` |

Templates retain status `TEMPLATE`.

A clean ratification records them as accepted controlled templates; it does not convert them to `APPROVED`.

Intentional template placeholders are valid template content.

---

# 5. Base Doctrines

| Market family | Repository path | Ratification state |
|---|---|---|
| FX | `constitution/doctrines/FX_BASE_DOCTRINE_V1.md` | Pending ratification |
| Crypto | `constitution/doctrines/CRYPTO_BASE_DOCTRINE_V1.md` | Pending ratification |
| Metals | `constitution/doctrines/METALS_BASE_DOCTRINE_V1.md` | Pending ratification |
| Energy | `constitution/doctrines/ENERGY_BASE_DOCTRINE_V1.md` | Pending ratification |
| US Equities | `constitution/doctrines/US_EQUITIES_BASE_DOCTRINE_V1.md` | Pending ratification |
| UK Equities | `constitution/doctrines/UK_EQUITIES_BASE_DOCTRINE_V1.md` | Pending ratification |
| German Equities | `constitution/doctrines/GERMAN_EQUITIES_BASE_DOCTRINE_V1.md` | Pending ratification |
| Australian Equities | `constitution/doctrines/AUSTRALIAN_EQUITIES_BASE_DOCTRINE_V1.md` | Pending ratification |
| Indices | `constitution/doctrines/INDICES_BASE_DOCTRINE_V1.md` | Pending ratification |

---

# 6. Timeframe Authorities

| Family | Directory | Required files |
|---|---|---:|
| FX | `constitution/authorities/fx/` | D1, H1, M30, M5 |
| Crypto | `constitution/authorities/crypto/` | D1, H1, M30, M5 |
| Metals | `constitution/authorities/metals/` | D1, H1, M30, M5 |
| Energy | `constitution/authorities/energy/` | D1, H1, M30, M5 |
| Indices | `constitution/authorities/indices/` | D1, H1, M30, M5 |
| US Equities | `constitution/authorities/equities_us/` | D1, H1, M30, M5 |
| UK Equities | `constitution/authorities/equities_uk/` | D1, H1, M30, M5 |
| German Equities | `constitution/authorities/equities_de/` | D1, H1, M30, M5 |
| Australian Equities | `constitution/authorities/equities_au/` | D1, H1, M30, M5 |

Total timeframe authorities:

```text
9 families × 4 timeframes = 36
```

---

# 7. Ratification State Model

## 7.1 Constitutional Root, Doctrines, and Timeframe Authorities

Clean ratification changes:

```text
DRAFT FOR APPROVAL
```

to:

```text
APPROVED
```

for:

- `constitution/CONSTITUTION.md`;
- 9 Base Doctrines;
- 36 Timeframe Authorities.

Total documents changed to `APPROVED`:

```text
46
```

## 7.2 Templates

Templates retain:

```text
Status: TEMPLATE
```

Their acceptance is recorded in the acceptance report and digest inventory.

## 7.3 Manifest

Clean ratification changes this Manifest from:

```text
PENDING RATIFICATION
```

to:

```text
RATIFIED
```

---

# 8. Structural Review Rules

The current constitutional house style permits multiple level-one Markdown headings.

That style is not a material blocker.

Review MUST prove:

- readable UTF-8;
- correct document identity;
- correct canonical path;
- resolvable governing and parent references;
- ordered numbered Articles or Sections where used;
- balanced code fences;
- no competing authority identity;
- no unresolved placeholders outside controlled templates;
- no secrets.

Heading normalization MAY be proposed as separate mechanical cleanup but is not required for ratification.

---

# 9. Ratification Conditions

Ratification requires:

- all 49 controlled documents at canonical paths;
- no competing constitutional document identity;
- no duplicate market-template claimant;
- doctrines under `constitution/doctrines/`;
- all 36 timeframe parent links resolving;
- market, timeframe, validator, and parent identities agreeing;
- complete approval, effective-date, amendment, and governing sections;
- no material contradiction;
- D1/H1/M30/M5 construction chains internally consistent;
- request-ceiling distinction consistently preserved;
- no silent unit, venue, session, adjustment, contract, index-variant, provider-scope, or identity conversion;
- no implementation, schema, configuration, database, or runtime mutation during ratification;
- exact nine-table boundary preserved;
- existing D1 behaviour preserved.

---

# 10. Ratification Outcomes

## 10.1 Clean Ratification

If review is clean:

- approve the Constitutional Root, 9 doctrines, and 36 timeframe authorities;
- retain both templates as `TEMPLATE`;
- record template acceptance in the acceptance report;
- set this Manifest to `RATIFIED`;
- record approval date and effective date;
- record the authority owner;
- record final SHA-256 digests;
- create immutable acceptance evidence;
- create one local checkpoint;
- do not push.

## 10.2 Material Blocker

If a material conflict remains:

- do not approve the affected document;
- do not invent a resolution;
- do not implement around it;
- write an exact blocker report;
- leave unaffected material unchanged unless partial ratification is explicitly authorised.

---

# 11. Governing Statement

> Constitution defines what is true.  
> Specification defines how Fragarach II implements that truth.  
> Implementation must conform to both.  
> Implementation must never invent authority.

**Operations is King.**
