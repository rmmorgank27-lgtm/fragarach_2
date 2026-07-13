# SPEC-018 — External Consumer Data Contract (Morphix FCv1)

## Authority

Fragarach II owns this contract and remains the single historical-data authority.
Morphix FCv1 is a read-only consumer. The scope is D1, the existing canonical
database, the existing Truth Engine, and the existing registration authority.

## Logical interface

```python
get_history(symbol, timeframe)
```

The local process transport is:

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.get_history \
  --symbol EURUSD --timeframe D1 --json
```

Consumers that need to discover newly servable lanes may use the additive,
read-only catalog operation:

```sh
PYTHONPATH=src python3 -m fragarach_ii.commands.list_histories
```

The catalog returns requestable D1 symbols and their authority metadata without
bars. It does not change the `get_history` request or response contract.

The authority database is selected by Fragarach, not by the request. Deployment
may set `FRAGARACH_AUTHORITY_DATABASE`; otherwise Fragarach uses its canonical
runtime database. The service opens SQLite with `mode=ro` and `query_only=ON`.

## Version 1 response

Successful responses have `status=AVAILABLE` and contain `authority`,
`truth_score`, `CAODT`, canonical `symbol`, `timeframe`, `first_bar`, `last_bar`,
`bar_count`, and `bars`. Each bar contains an integer UTC epoch `timestamp` and
the exact canonical SQLite text values for `open`, `high`, `low`, `close`, and
nullable `volume`. Bars are ordered from earliest to latest.

Unavailable data is returned without fabricated bars:

- `NOT_REGISTERED` when registration authority cannot resolve the request.
- `NO_HISTORY` when the canonical lane has no servable history or Truth state.

Every unavailable response has `bar_count=0`, `bars=[]`, and a factual `reason`.
A RED successful response also supplies a reason. Consumers must display AMBER
or RED authority state and must not acquire, import, repair, recalculate, or
substitute data.

## Acceptance dataset

`EURUSD`, `BTCUSD`, and `AAPL`, all at `D1`. Acceptance compares first bar, last
bar, bar count, Truth Score, and CAODT with Fragarach's canonical database.
