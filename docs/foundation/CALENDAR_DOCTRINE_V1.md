# Fragarach II — Calendar Doctrine V1

## Purpose

Calendars state which canonical UTC D1 dates are expected for a configured lane. They do not decide whether evidence is correct, tradable, sufficient, repairable, or suitable for any consumer.

Definitions are immutable versioned JSON assets. Every definition has a stable ID, positive version, asset class, timeframe, timezone basis, effective range, explicit rules and overrides, and a SHA-256 checksum over canonical JSON excluding the checksum field. Any rule or override change requires a new version and checksum.

Operational symbol assignment is read from `instrument_registrations`. The historical `symbol_calendars.v1.json` is retained only as migration evidence. Validators never infer asset class from spelling and never choose a generic fallback.

## V1 definitions

### FX_D1_V1

- Assigned initially to AUDUSD only.
- Expected weekdays: Monday through Friday.
- Recurring full-day closures: 1 January and 25 December.
- Weekend holidays do not create invented observed-weekday closures.
- Good Friday and other reduced-liquidity dates remain expected unless a versioned dated closure override says otherwise.

### METALS_D1_V1

- Assigned initially to XAUUSD only; it is not a generic metals or futures calendar.
- Expected weekdays: Monday through Friday.
- Recurring full-day closures: 1 January and 25 December.
- Calculated full-day closure: Gregorian Good Friday.
- Early-close weekdays remain expected D1 sessions.

### CRYPTO_D1_V1

- Assigned initially to BTCUSD only.
- Every Gregorian UTC date is expected.
- V1 has no weekend or holiday closure.

## Overrides

`EXPECTED_OVERRIDE` and `CLOSED_OVERRIDE` entries contain an ISO date and factual reason and take precedence over recurring rules. Missing evidence never generates an override. Applied overrides are listed in validation results.

The initial V1 definition files contain no dated overrides. Their support is structural and tested; additions require a new versioned definition.

## Validation boundary

Every request supplies `through_date`. Expected sessions begin at the earliest canonical date for the lane and end at the declared boundary inclusive. Dates after the boundary are reported separately. Wall-clock time never chooses or changes the boundary.

Bars on dates the selected calendar marks closed are preserved and reported as `OUTSIDE_EXPECTED_SESSION`. A calendar must never delete, conceal, synthesize, or correct evidence.

## Authority statement

Calendar agreement is internal rule agreement, not proof of market correctness. Consumers own every interpretation of the reported facts.

**Operations is King.**
