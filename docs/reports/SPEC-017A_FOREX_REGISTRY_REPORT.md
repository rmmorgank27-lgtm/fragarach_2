# SPEC-017A Forex Registry Report

## Result

The Forex registry now contains exactly the 31 operator-approved ordered pairs. Each record stores its canonical `FX:<PAIR>` identity, base and quote currencies, full display name, slash-symbol and currency-name aliases, and the original base/quote orientation.

- Forex records: 31
- Known provider mappings: 4
- Explicitly unknown provider mappings: 27
- Registry SHA-256: `45f30a92046a21bcad21f7089c13dd4dc20f5013915ca83fcecb694a09ff47a4`

The retained known mappings are AUDUSD, EURAUD, EURGBP, and NZDJPY. Each is supported by `config/providers/mappings/TWELVE_DATA_FX_DIRECT_PAIRS_V1.json`. No provider name or symbol was fabricated for the other pairs.

## Integrity

- All 31 canonical symbols resolve through Discover Market.
- No inverse orientation absent from the approved list was generated.
- An approved unmapped pair, USDMXN, registered as `REGISTERED_UNMAPPED` in an isolated authority database.
- Existing Zero Blocking behaviour keeps import and retirement available while provider fetch is unavailable only when mapping evidence is unknown.
- Canonical comparisons prove that every non-Forex registry record and non-Forex provider mapping is unchanged from SPEC-017.
- The builder exposes `--forex-only` and a data-driven approved-pair list so later Forex expansion does not refresh or alter other universes.

## Verification

- Python: 148 tests passed.
- Swift build: passed.
- OperationsCoreChecks: 25 passed.
- Signed native application: built, signed, launched, and process-verified.
- Application runtime preference remained on the reviewed authority database.

Acceptance result: **PASS**.
