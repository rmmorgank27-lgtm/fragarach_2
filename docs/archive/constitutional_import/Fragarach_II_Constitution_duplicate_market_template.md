# Fragarach II Constitution

# MARKET_AUTHORITY_TEMPLATE_V1

**Constitution Document**

**Authority ID:** MARKET_AUTHORITY_TEMPLATE_V1

**Version:** 1

**Status:** Ratified Template

**Classification:** Constitutional Authority

**Doctrine:** Operations is King

---

# Article 1 — Purpose

This document defines the mandatory structure of every Market Authority document within Fragarach II.

A Market Authority describes how a market fundamentally operates.

It is not software.

It is not implementation.

It is not configuration.

It is constitutional truth.

Every Market Authority shall conform to this template.

---

# Article 2 — Authority

A Market Authority defines only market behaviour.

It shall never define:

- providers
- APIs
- evidence
- storage
- application behaviour
- operator preferences

Those belong to separate authorities.

---

# Article 3 — Scope

A Market Authority applies to one market ecosystem.

Examples include:

- Global OTC Foreign Exchange
- Global Cryptocurrency
- US Equities
- UK Equities
- German Equities
- Australian Equities
- Spot Metals
- Energy
- Equity Indices

Every ecosystem owns one Base Doctrine.

---

# Article 4 — Mandatory Sections

Every Market Authority shall contain the following Articles.

No Article may be omitted.

No Article may be reordered.

---

## Identity

- Authority ID
- Version
- Classification
- Status

---

## Purpose

Why the authority exists.

---

## Scope

Exactly which markets are governed.

Exactly which markets are excluded.

---

## Market Description

Plain-language description.

---

## Market Type

One of:

- OTC
- Exchange
- Continuous
- Auction
- Hybrid

---

## Market Model

How the market fundamentally operates.

Examples:

- continuous trading
- exchange session
- rolling market
- auction

---

## Trading Time

The market's operational clock.

Not evidence storage.

---

## Trading Day Convention

How the market partitions trading days.

Examples:

- New York Close
- Exchange Close
- UTC Day

---

## Trading Week

Definition of:

- weekly open
- weekly close

---

## Session Doctrine

Definition of:

- regular sessions
- maintenance
- overnight
- breaks

---

## Holiday Doctrine

Definition of:

- holidays
- exceptional closures
- early closes

---

## DST Doctrine

Definition of:

- timezone authority
- daylight-saving authority
- historical revision policy

---

## Evidence Doctrine

Definition of:

Expected market behaviour.

Not provider behaviour.

---

## Gap Doctrine

Definition of:

Expected missing periods caused by market operation.

Not provider outages.

---

## Effective Range

Every authority shall define:

effective_from

effective_to

No authority is timeless.

---

## Revision Doctrine

Operational changes require a new authority version.

Previous versions remain immutable.

---

## Cross References

References to:

- Trading Day Convention
- Timeframe Authorities
- Validation Authorities

---

## Acceptance Fixtures

Every Market Authority shall contain canonical examples proving:

- market open
- market close
- holidays
- session boundaries
- trading-day ownership

These fixtures become permanent acceptance tests.

---

# Article 5 — Evidence Doctrine

Market Authority shall never modify evidence.

It describes markets.

It does not transform evidence.

---

# Article 6 — Provider Independence

Market Authority shall never define:

- API behaviour
- request limits
- maintenance windows caused by providers
- retries
- paging
- authentication

Those belong exclusively to Provider Authority.

---

# Article 7 — Validation Independence

Market Authority shall never define validation algorithms.

It defines only market facts.

Validators consume Market Authority.

---

# Article 8 — Storage Independence

Market Authority shall never define:

- SQLite
- schemas
- tables
- indexes
- migrations

Those belong to implementation.

---

# Article 9 — Operator Independence

Market Authority shall never define:

- user interface
- application behaviour
- display timezone
- workflows

Those belong elsewhere.

---

# Article 10 — Constitutional Principles

Every Market Authority shall satisfy:

1. Immutable once accepted.

2. Versioned forever.

3. Checksummed.

4. Human readable.

5. Machine readable.

6. Free of implementation detail.

7. Free of provider behaviour.

8. Free of application behaviour.

9. Deterministic.

10. Complete.

Nothing may be inferred.

---

# Article 11 — Constitutional Rule

When implementation and Market Authority disagree:

Market Authority is correct.

Implementation shall change.

The Constitution shall not.

---

# Completion Statement

This document establishes the mandatory constitutional structure for every Market Authority within Fragarach II.

Every future Base Doctrine shall conform exactly to this template.

Fragarach II remains **CANDIDATE AUTHORITY**.

**Operations is King.**