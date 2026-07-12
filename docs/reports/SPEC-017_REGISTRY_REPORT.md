# SPEC-017 Registry Report

Registry snapshot: `config/market_registry/registry.v1.json`

- Contract: `fragarach_ii.market_registry.v1`
- Registry version: 1
- Records: 1,326
- SHA-256: `846eab10d08527ea39907e68cab897e4862a24958c891367efc4d75aabd723ef`

| Universe | Records |
| --- | ---: |
| Crypto | 500 |
| US equities | 500 |
| UK equities | 100 |
| German equities | 100 |
| Australian equities | 100 |
| Forex | 13 |
| Metals | 4 |
| Energy | 3 |
| Indices | 6 |

Every record contains the required provider-independent identity, representation, provenance, version, and active fields. Optional provider mappings are stored separately. Crypto registry IDs use stable CoinGecko asset IDs; equity listings and share classes remain separate; FX orientations are exact and inverse provider data is not inferred.

Automated integrity tests prove deterministic loading, required counts, SOL/Silver/Google/WTI/Brent/index resolution, exact FX orientation, distinct share classes, and unmapped registration behaviour. `script/build_market_registry.py` records the source date and generates a new auditable snapshot rather than mutating runtime registrations.
