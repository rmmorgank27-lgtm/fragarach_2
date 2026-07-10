# Fragarach II — Gap Doctrine V1

## Identity and purpose

`FRAGARACH_II_D1_GAP_DOCTRINE_V1` classifies missing expected D1 sessions factually. It never labels a lane safe, ready, tradable, healthy, promoted, or engine-ready.

## Material reasons

- `CURRENT_EDGE_MISSING`: an expected session after the latest present expected session and through the declared boundary is absent.
- `EMPTY_EXPECTED_WEEK`: an ISO week has at least one expected session and zero present expected sessions.
- `EMPTY_EXPECTED_MONTH`: a calendar month has at least one expected session and zero present expected sessions.

A missing date with one or more of these reasons is reported as `MATERIAL_BY_GAP_DOCTRINE_V1`.

## Non-material reason

A missing expected date that is not on the current edge and belongs to a represented ISO week and represented calendar month receives `ISOLATED_EXPECTED_SESSION_MISSING` and wording `NON_MATERIAL_BY_GAP_DOCTRINE_V1`.

“Non-material” means only that weekly and monthly representation remains under this exact doctrine. It is not a universal importance judgment.

## Counting

`material_gap_count` and `non_material_gap_count` count missing expected session dates, not reason assignments or ranges. A date carrying current-edge, empty-week, and empty-month reasons is counted once as material. Each result lists every reason for every missing date, making multiple classification explicit without double counting.

Weekly and monthly summaries report expected, present, and missing session counts and whether at least one expected session is present. Missing ranges compress consecutive positions in the ordered expected-session sequence; intervening calendar closures are not implied missing.

## Determinism

Classification depends only on canonical dates, explicit calendar definitions, this doctrine, validator version, and declared boundary. Stable JSON ordering produces the factual result checksum. Observation time is excluded from that checksum.

## Consumer boundary

The doctrine does not decide repair, provider substitution, acquisition priority, readiness, promotion, or whether a consumer continues. It reports facts; consumers decide what those facts mean.

**Operations is King.**
