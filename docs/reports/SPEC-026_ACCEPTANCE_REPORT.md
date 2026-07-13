# SPEC-026 Revision 1 — Acceptance Report

Date: 2026-07-13

Decision: accepted for the permanent Market History/Analysis authority boundary and commissioned direct history. H4 and M15 remain correctly inactive.

## Signed-native evidence

### Fragarach II

- Release bundle: `dist/Fragarach II.app`
- Bundle identifier: `com.raymorgan.fragarach-ii.operations`
- Architecture: arm64
- Signature: ad-hoc, verified with `codesign --verify --deep --strict`
- Journey: launched signed bundle in Market History mode for AUDUSD; the view requested D1/H4/H1/M30/M15/M5 and the process remained alive beyond backend completion.

### SignalBar

- Release bundle: `/Users/raymorgan/VSC/SignalBar/build/SignalBar.app`
- Bundle identifier: `local.signalbar.app`
- Architecture: arm64
- Signature: ad-hoc, verified with `codesign --verify --deep --strict`
- Journeys: launched signed bundle in Market History mode for AUDUSD and XAUUSD. Each journey requested D1/H4/H1/M30/M15/M5 and remained alive beyond backend completion.
- The acceptance run also repaired a pre-existing Swift async-process crash exposed by the signed journey; the backend bridge is now serialized and uses a dispatch continuation rather than detached concurrent Foundation processes.

## D1, Truth, Estate Truth, and evidence non-regression

The operational database SHA-256 was captured before implementation and after all tests/native journeys. It is identical:

```text
8f91aea8aa15c6a7bbbbcda2767d93b0c138d6a0882f62760d608223eb3320e9
```

Additional deterministic boundaries are unchanged:

| Boundary | Before | After |
|---|---|---|
| D1 canonical rows | 166,999 | 166,999 |
| D1 bars fingerprint | `8eb80ba2696cfefd2cf7885bccc3e2fd0d0ce9a027551bb8aa9682a5fa8cef4d` | same |
| SPEC-018 AUDUSD D1 response | `e62c9a7c1563c8dd7bb69a6cd26733b1489c344e55bb37faa80022cbe2bc083f` | same |
| AUDUSD D1 Truth response | `5d4777b29fc2db6b46ad93c895901df7197efd889c3038848dd06f33c7ecee83` | same |
| Estate Truth response | `04abdac8c6c9cae16563f4e0db911d59805e663612b008fdb85357de64e76da4` | same |

Because the complete authority database file is identical, canonical evidence, provenance, registrations, lane summaries, Truth inputs, and Estate inputs are unchanged.

## Remaining construction-authority blockers

H4 and M15 are not operational defects. They are intentionally inactive capabilities until separate authority approves, per market and representation:

- target duration and boundary grid;
- session and trading-day ownership;
- timestamp meaning;
- contributor eligibility, exact expected timestamps, and required count;
- short/exceptional-session behaviour;
- completion and latest-closed rules;
- effective-range, unit, and price-basis compatibility;
- gap, warning, and CAODT semantics.

Until that approval, stable service behaviour is:

```text
Status: TIMEFRAME_NOT_ACTIVE
OHLC: []
CAODT: null
Warnings: [CONSTRUCTION_AUTHORITY_NOT_COMMISSIONED]
```

## Push state

No push was performed.
