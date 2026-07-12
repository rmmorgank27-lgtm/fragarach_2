# SPEC-012 — Market Discovery & Instrument Onboarding

**Document ID:** `SPEC-012_MARKET_DISCOVERY_AND_INSTRUMENT_ONBOARDING`

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`

**Status:** Implementation

**Authority:** Candidate Authority

**Doctrine:** Operations is King

**Push:** Forbidden

---

# 1. Objective

Replace the current Resolve Instrument workflow with a complete Market Discovery and Instrument Onboarding workflow.

The objective is **not** to identify a ticker.

The objective is to help the operator onboard a market into Fragarach II.

Identity resolution becomes one internal stage of onboarding.

The standalone Resolve Instrument screen shall be removed.

---

# 2. Mission

When an operator enters:

```text
US30
```

Fragarach shall answer:

> "I understand the market you mean."

It shall then guide the operator through:

* underlying market
* tradable representations
* provider mappings
* recommended registration
* acquisition readiness

The operator should never receive a simple "Unknown" response for widely recognised market names without first exhausting Fragarach's own market knowledge.

---

# 3. Engineering Authority

The implementation engineer is authorised to create any internal read-only services required to complete this specification, including:

* market discovery services
* canonical market catalogue
* alias dictionaries
* relationship models
* onboarding DTOs
* helper modules
* native bridge models
* caches
* ranking logic

provided:

* no schema changes
* no migration
* no constitutional changes
* no authority fabrication
* no persistence changes
* no weakening of existing authority

Do not stop because additional internal services are required.

Build them.

---

# 4. Market Discovery

Input may be:

* ticker
* CFD
* ETF
* futures symbol
* index name
* commodity
* company
* alias
* partial name

Examples:

```text
US30

DJI

Dow

Dow Jones

SPX

SPX500

US500

Gold

Oil

WTI

AUDJPY

Apple

Tesla

BHP
```

---

# 5. Discovery Output

Return one deterministic object.

```text
MarketDiscovery
```

Containing:

```text
Underlying Market

Canonical Identity

Confidence

Market Type

Asset Class

Description
```

---

# 6. Tradable Representations

For every discovered market return known representations.

Examples:

```text
Underlying

Dow Jones Industrial Average

Representations

Index
DJI

CFD
US30

ETF
DIA

Index Symbol
^DJI

Futures
YM

Known Aliases

Dow

Dow Jones

DJIA

US30
```

The service is expected to use established financial knowledge.

Not only existing registrations.

---

# 7. Provider Discovery

After identity is confirmed perform provider discovery.

Display:

```text
Provider

Availability

Supported Timeframes

Entitlement

Confidence

Known Symbol

Registration Status
```

Provider discovery is informational.

No registration occurs.

---

# 8. Registration Recommendation

Display one recommended registration.

Example:

```text
Recommended

US30 CFD

Reason

Operator requested tradable CFD.

Alternative

DJI

Alternative

DIA ETF
```

The operator always remains in control.

---

# 9. Metadata

Immediately construct preliminary metadata.

Display:

* market
* asset class
* exchange
* timezone
* sessions
* currencies
* aliases
* provider mappings
* registration state

Unknown remains explicit.

No invention.

---

# 10. Existing Registration

If already registered display:

* Authority
* Truth Score
* CAODT
* Registration Version

Offer:

```text
Open Existing
```

instead of onboarding.

---

# 11. Unknown Markets

Unknown is the final state.

Not the first.

Before returning UNKNOWN the service shall exhaust:

* canonical knowledge
* aliases
* common trading names
* market abbreviations
* established financial naming
* ISO conventions

If still unknown return:

* suggested searches
* similar markets
* operator guidance

Never simply:

```text
Not Found
```

---

# 12. User Interface

Replace:

```text
Resolve Instrument
```

with:

```text
Discover Market
```

or

```text
Onboard Market
```

The page becomes a guided workflow.

Identity resolution becomes an internal implementation detail.

---

# 13. Workflow

```text
Operator

↓

Discover Market

↓

Resolve Identity

↓

Display Market

↓

Display Tradable Forms

↓

Provider Discovery

↓

Registration Recommendation

↓

Register

↓

Acquire

↓

Validate

↓

Truth
```

The operator always knows the next step.

---

# 14. Explicit Exclusions

Do not implement:

Acquisition

Registration mutation

Authority changes

Truth calculation

Maintenance

Forecasting

Consumer-specific behaviour

Database schema changes

Migration

---

# 15. Tests

Add tests proving:

* CFD aliases
* ETF aliases
* Futures aliases
* Index aliases
* Commodity aliases
* Currency aliases
* Company aliases
* Multiple representations
* Provider discovery
* Existing registration detection
* Recommended registration
* Unknown handling

All previous tests remain green.

---

# 16. Acceptance

Acceptance requires:

✓ Common market names recognised.

✓ CFD names recognised.

✓ ETF names recognised.

✓ Futures recognised.

✓ Tradable forms displayed.

✓ Provider discovery displayed.

✓ Registration recommendation displayed.

✓ Existing registrations detected.

✓ No schema changes.

✓ No migration.

✓ Existing suites remain green.

✓ Native application builds.

✓ No push.

---

# 17. Reports

Produce:

```text
SPEC-012_PREFLIGHT_REPORT.md

SPEC-012_IMPLEMENTATION_REPORT.md

SPEC-012_ACCEPTANCE_REPORT.md
```

If blocked:

```text
SPEC-012_MARKET_DISCOVERY_BLOCKER.md
```

---

# 18. Local Checkpoint

Create one reviewed local checkpoint.

No push.

---

# Completion Statement

SPEC-012 transforms onboarding from a ticker resolver into an operator-guided market discovery workflow.

Fragarach no longer asks:

> **"What ticker is this?"**

It asks:

> **"What market is the operator trying to onboard?"**

Identity, provider discovery, registration recommendation, and acquisition readiness become one continuous workflow.

The operator is guided from market intent to operational historical authority.

**Operations is King.**
