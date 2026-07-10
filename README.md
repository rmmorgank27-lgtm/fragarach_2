# Fragarach II

Fragarach II is a candidate authority for trusted historical market-bar evidence. Its only responsibilities are to read, validate, store, and serve evidence.

The current implementation is deliberately limited to the SQLite storage foundation defined by [`SPEC-001_STORAGE_FOUNDATION.md`](specs/foundation/SPEC-001_STORAGE_FOUNDATION.md). Passing its tests proves storage structure and local runtime behaviour; it does not establish operational trust or production readiness.

## Development

Requires Python 3.12 or later and has no runtime dependencies outside the standard library.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

**Operations is King.**

