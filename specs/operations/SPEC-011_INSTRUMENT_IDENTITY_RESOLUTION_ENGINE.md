# SPEC-011 — Instrument Identity Resolution Engine

**Document ID:** `SPEC-011_INSTRUMENT_IDENTITY_RESOLUTION_ENGINE`

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`

**Status:** Implementation

**Authority:** Candidate Authority

**Doctrine:** Operations is King

**Push:** Forbidden

---

# 1. Objective

Implement the Instrument Identity Resolution Engine.

The Identity Resolver becomes the first stage of instrument onboarding.

Its responsibility is to determine **what instrument the operator means** before any provider discovery, registration, or acquisition occurs.

Identity resolution is owned by Fragarach.

Provider discovery is a separate phase.

---

# 2. Mission

When an operator enters:

```text
AUDJPY
```

Fragarach should answer:

> "I know what instrument you mean."

before asking:

> "Which providers can supply authoritative data?"

Identity always precedes provider discovery.

---

# 3. Operational Principle

The Identity Resolver is permitted to use accumulated market knowledge.

It is **not** permitted to invent authority.

Identity knowledge may originate from:

* existing registrations
* aliases
* canonical instrument registry
* ISO currency codes
* exchange conventions
* market conventions
* established financial naming
* previous accepted authority
* internal resolver knowledge

Identity resolution alone shall never create registration or authority.

---

# 4. Inputs

Operator input may include:

* ticker
* symbol
* alias
* company name
* commodity name
* currency pair
* index name
* partial text

Examples:

```text
AUDJPY

AUD/JPY

Apple

Gold

Dow

S&P500

BTC

ETH

BHP
```

---

# 5. Resolver Output

Return one deterministic object.

```text
InstrumentIdentity
```

Containing:

```text
Canonical Name

Canonical Symbol

Instrument Type

Market

Asset Class

Confidence

Known Aliases

Known Exchange

Known Currency

Known Quote/Base

Resolution Reason

Identity Status
```

---

# 6. Identity Status

Return one of:

```text
KNOWN

LIKELY

AMBIGUOUS

UNKNOWN
```

Explanation shall always accompany the result.

---

# 7. Confidence

Return:

```text
0–100
```

Confidence describes identity confidence only.

It does **not** describe provider confidence.

---

# 8. Multiple Matches

When multiple identities exist:

Example:

```text
BHP
```

Return:

```text
ASX:BHP

NYSE:BHP

Confidence

98
```

Operator selects.

No automatic registration.

---

# 9. Unknown Instruments

Unknown shall never simply return:

```text
Not Found
```

Instead:

```text
UNKNOWN

No known identity

Suggested Searches

Suggested Providers

Suggested Aliases
```

Always continue helping.

---

# 10. Provider Separation

Identity Resolver shall not:

* query providers for identity
* register instruments
* acquire data
* create authority

Identity ends here.

Provider Discovery begins afterwards.

---

# 11. Existing Registration

If already registered:

Return:

```text
REGISTERED

Authority

Current Truth Score

Current CAODT
```

The operator immediately knows the instrument already exists.

---

# 12. Metadata Construction

Before registration build preliminary metadata:

* canonical identity
* aliases
* market
* asset class
* exchange
* currencies
* timezone (if known)
* sessions (if known)

Unknown values remain explicit.

No invention.

---

# 13. Operator Workflow

The onboarding workflow becomes:

```text
Resolve Identity

↓

Review Metadata

↓

Discover Providers

↓

Register Instrument

↓

Acquire Data

↓

Validate

↓

Truth
```

The operator always understands where the instrument is within its lifecycle.

---

# 14. Native Integration

Replace the current Add Instrument search.

Searching shall become:

```text
Resolve Instrument
```

Display:

* identity
* confidence
* aliases
* metadata
* registration state

No acquisition yet.

---

# 15. Explicit Engineering Authority

The implementation engineer is authorised to introduce any internal read-only infrastructure required to complete this specification, including:

* resolver services
* alias dictionaries
* canonical lookup tables (non-persistent)
* helper modules
* DTOs
* native bridge models
* caches
* ranking algorithms

provided:

* no schema changes
* no database migration
* no constitutional changes
* no authority fabrication
* no public contract weakening

Internal implementation details do not require additional specifications.

---

# 16. Explicit Exclusions

Do not implement:

Provider Discovery

Registration

Acquisition

Validation

Truth Score

Truth Console

Maintenance

Forecasting

Consumer-specific behaviour

Database schema changes

Migration

---

# 17. Tests

Add tests proving:

* deterministic identity resolution
* alias resolution
* currency pair resolution
* commodity resolution
* company resolution
* ambiguous identity handling
* unknown identity handling
* confidence calculation
* no authority creation
* no provider dependency
* repeatable results

All previous acceptance tests remain green.

---

# 18. Acceptance

Acceptance requires:

✓ Operator can enter common instrument names.

✓ Identity resolved without requiring provider lookup.

✓ Aliases displayed.

✓ Confidence displayed.

✓ Ambiguous identities supported.

✓ Unknown identities provide useful guidance.

✓ Existing registrations recognised.

✓ Preliminary metadata generated.

✓ No authority fabricated.

✓ No schema changes.

✓ No migration.

✓ Existing tests remain green.

✓ Native application builds.

✓ No push.

---

# 19. Reports

Produce:

```text
SPEC-011_PREFLIGHT_REPORT.md

SPEC-011_IMPLEMENTATION_REPORT.md

SPEC-011_ACCEPTANCE_REPORT.md
```

If blocked:

```text
SPEC-011_IDENTITY_RESOLUTION_BLOCKER.md
```

---

# 20. Local Checkpoint

After successful acceptance:

Create one reviewed local checkpoint.

No push.

---

# Completion Statement

SPEC-011 establishes Fragarach II as the owner of **instrument identity**.

Identity is no longer delegated to individual providers.

Providers become evidence sources.

Fragarach becomes the authoritative resolver of what an instrument **is**, before determining who can supply data for it.

This removes the largest source of operator friction and creates the first stage of a scalable onboarding pipeline.

**Operations is King.**
