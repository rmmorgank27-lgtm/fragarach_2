# SPEC-013 JPYCHF Retirement Impact Report

Date: 2026-07-12

## Reviewed Pre-Mutation Impact

| Fact | Value |
|---|---|
| Canonical instrument | JPYCHF |
| Scope | Whole instrument |
| Active lanes | D1 |
| Provider mapping | TWELVE_DATA / JPY/CHF |
| Registration | Version 1, REGISTERED_WITH_EVIDENCE |
| Completed acquisition runs | 1 |
| In-progress runs | 0 |
| Raw evidence blocks | 1 |
| Canonical bars | 9 |
| Provenance records | 9 |
| Truth Score | 90 |
| CAODT | 2026-07-10T00:00:00+00:00 |
| Scheduled jobs | Not recorded |
| Typed confirmation | RETIRE JPYCHF |

## Selected Decision

- Reason: `INCORRECT_INSTRUMENT_IDENTITY`
- Note: `Operator confirmed JPYCHF was acquired incorrectly`
- New lifecycle: `RETIRED_INCORRECT_IDENTITY`
- Lane operation: `HISTORICAL_ONLY`
- Acquisition: `ACQUISITION_DISABLED`
- Evidence: `EVIDENCE_QUARANTINED`
- Serving: `NOT_SERVED`

## Preservation Verification

Before and after counts were identical for:

- instrument registrations: 7
- evidence lanes: 7
- canonical bars: 33,566
- raw blocks: 8
- provenance rows: 81,434

Authority events increased from 6 to 10: two current-authority declaration events and two supersession events. The JPYCHF raw block remained:

`raw-c3fa31d780d5b70a73ad224e86d5cec38c42fd839bf6d53566aca0be389aa08c`

Checksum remained `c3fa31d780d5b70a73ad224e86d5cec38c42fd839bf6d53566aca0be389aa08c`; byte length remained 1,074.
