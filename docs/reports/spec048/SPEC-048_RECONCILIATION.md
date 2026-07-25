# SPEC-048 Before/After Reconciliation

## Final counts

| Measure | Before | After |
|---|---:|---:|
| Lane rows originally flagged | 27 | 0 lane-scoped mapping decisions |
| Retired `XAGUSDCFD` rows removed | 0 | 4 |
| Active representation/provider pairs in the review set | 9 including retired | 8 active |
| Representation mappings automatically resolved | 0 | 6 |
| Timeframe capabilities verified | 0 | 24 |
| Credential/access failures | 27 lane displays reported missing | 0 |
| Provider lookup failures | Not actionable | 0 |
| Genuine operator decisions remaining | 27 lane rows | 2 representation decisions |

## Automatic exact mappings

| Canonical | Twelve Data | Mapping | Timeframe facts |
|---|---|---|---|
| AUDSGD | `AUD/SGD` | `EXACT_REPRESENTATION` | M5, M30, H1, D1 supported |
| EURUSD | `EUR/USD` | `EXACT_REPRESENTATION` | M5, M30, H1, D1 supported |
| GBPAUD | `GBP/AUD` | `EXACT_REPRESENTATION` | M5, M30, H1, D1 supported |
| GBPJPY | `GBP/JPY` | `EXACT_REPRESENTATION` | M5, M30, H1, D1 supported |
| USDCAD | `USD/CAD` | `EXACT_REPRESENTATION` | M5, M30, H1, D1 supported |
| USDCHF | `USD/CHF` | `EXACT_REPRESENTATION` | M5, M30, H1, D1 supported |

Each mapping preserves the prior confirmed D1 provider symbol and ingest-run provenance while serving every commissioned timeframe from one representation-scoped fact.

## Material decisions

- `DJI × TWELVE_DATA`: search results include ETFs, warrants, and a common stock; none proves the canonical equity index representation.
- `USOIL × TWELVE_DATA`: `WTI/USD` is an Energy Resource spot representation, while other results include common stocks, ETFs, and depositary receipts. The canonical WTI CFD is not inferred equivalent.

## Retired/non-actionable

`XAGUSDCFD` registration and evidence remain preserved. Its four original review rows do not participate in active reconciliation, Scheduler diagnostics, capability projection, acquisition eligibility, or provider lookup. Restart resolution skips it.
