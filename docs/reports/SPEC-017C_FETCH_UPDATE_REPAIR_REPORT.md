# SPEC-017C Fetch / Update Repair Report

## Result

Fetch / Update now resolves a provider at operation time. Registration remains provider-independent.

- Existing confirmed mappings are attempted first.
- Otherwise market preference selects Twelve Data or Yahoo Finance, with the other provider retained as fallback.
- FX candidates use the exact direct slash convention for Twelve Data and exact `PAIR=X` convention for Yahoo. Returned provider symbols must match; inverse evidence is rejected.
- A failed attempt advances to the next provider. If all attempts fail, the native result retains Import CSV and Try Again actions with attempt reasons under Technical Details.
- Successful responses enter the existing raw-evidence, staging, Preserve merge, provenance, and canonical ingestion pipeline.
- Confirmed provider, exact symbol, D1 capability state, and canonical asset are recorded only in the successful immutable ingest receipt. Later fetches and the native reader reuse that evidence; no schema change was required.

## Native workflow

No-evidence lanes default to **Fetch Full D1 History**. Evidence lanes default to **Update D1**, starting five completed trading sessions before the latest stored D1 observation. Import CSV and retirement remain available.

The signed native smoke used isolated runtime `/tmp/fragarach-spec017c.sqlite3`:

```text
EURUSD REGISTERED_UNMAPPED
→ Find Provider and Fetch Full History
→ TWELVE_DATA / EUR/USD confirmed
→ 3,642 D1 rows inserted
→ acquired 2012-11-05 through 2026-07-11
→ CAODT 2026-07-11
→ Truth Score 87
```

The receipt reported the 5,000-calendar-day Twelve Data best-available limit rather than rejecting the useful history. After refresh, Data Operations displayed the confirmed mapping for reuse.

## Focused verification

- 24 focused provider, acquisition, and registry tests passed.
- Forced Twelve Data failure continued to Yahoo Finance and committed through the same immutable pipeline.
- Yahoo inverse/mismatched FX evidence was rejected.
- OperationsCoreChecks: 25 passed.
- Swift build: passed.
- One signed application build and native smoke acquisition: passed.

Registry universes, registration authority, Truth scoring, retirement, navigation, and storage schema were not changed.

Acceptance result: **PASS**.
