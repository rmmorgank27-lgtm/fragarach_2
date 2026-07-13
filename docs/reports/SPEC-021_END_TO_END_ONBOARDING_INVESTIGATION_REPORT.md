# SPEC-021 End-to-End Instrument Onboarding — Investigation Report

Date: 2026-07-13 (Australia/Brisbane)

## Conclusion

GBPJPY was absent from the canonical database and was a valid reviewed registry
instrument. Discovery, selection, and provider-independent registration all
succeeded. The first failed boundary was **provider payload staging**, after a
successful HTTP response.

Twelve Data returned 3,698 GBP/JPY observations with HTTP 200 and `status=ok`.
Seven observations had an invalid OHLC envelope. The first was:

```text
2019-07-02
open  137.089996
high  137.23500
low   135.84500
close 135.83000
```

The close is below the supplied low. The strict common validator correctly
rejected the row, but the Twelve Data adapter incorrectly converted that one row
rejection into failure of the entire valid response. The previous Fragarach
implementation rejected invalid provider observations individually and retained
the valid observations.

After repairing that boundary, the trace reached GREEN Truth and SPEC-018
serving. Continuing the journey exposed two latent consumer-boundary defects:

1. Morphix populated its symbol sidebar only from the pre-existing engine-cache
   manifest, so it did not discover newly servable authority symbols.
2. Once GBPJPY was selectable, Morphix successfully received its SPEC-018
   metadata and bars, but the no-engine-cache detail branch discarded those
   bars and constructed an empty chart.

These were sequential workflow boundaries. They were not provider, canonical
identity, Truth, or engine failures.

## Minimal repairs

- The Twelve Data adapter now records only `INVALID_OHLC` observations as
  explicit staging rejections and continues when valid observations remain.
  Raw response bytes and rejection details are preserved. The common OHLC
  validator is unchanged and no invalid row enters canonical history.
- The existing acquisition pipeline now permits that bounded partial provider
  batch and surfaces the rejection count as a warning.
- Fragarach adds a read-only external-consumer catalog operation alongside the
  unchanged SPEC-018 `get_history` response. It lists only histories with
  servable Truth state.
- Morphix merges that catalog into its existing overview on Reload and passes
  authority candles through the existing display policy when no engine cache
  exists. No engine or forecast logic changed.

Registration, provider selection, canonical identity, ingestion merge rules,
validation, Truth, `get_history`, and Morphix engines were not redesigned.

## Focused verification

- Focused onboarding/provider/consumer tests: 23 passed.
- One Fragarach build: passed.
- Morphix compiled and its existing focused checks passed.
- No CSV import or direct database edit was used.
