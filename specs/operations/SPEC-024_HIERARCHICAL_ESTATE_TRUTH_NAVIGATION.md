# SPEC-024 — Hierarchical Estate Truth Navigation

## Objective

Evolve the native Truth workspace from a flat symbol matrix into an Estate → Market → Subgroup → Symbol operations console without changing Truth, authority, registration, acquisition, ingestion, validation, or consumer contracts.

## Operator hierarchy

The canonical market order is Forex, Metals, Energy, Indices, Stocks, and Crypto. Unknown future asset classes become additional market groups without redesign. Forex, Stocks, Indices, and Crypto use deterministic logical subgroups; markets without subdivisions drill directly into their symbol matrix.

Scorecards are presentation projections over the existing Estate Truth lanes. SwiftUI does not calculate Truth or group summaries.

Global search remains hierarchy-independent and exact symbol searches open symbol context immediately.

## Acceptance gate

The signed native application must demonstrate Estate, market, subgroup, and symbol context transitions; symbol detail, Manage Data, Authority History, and global search must remain available.

**A feature is not accepted until the operator can successfully execute the complete workflow from the signed native application. Backend implementation alone is insufficient.**
