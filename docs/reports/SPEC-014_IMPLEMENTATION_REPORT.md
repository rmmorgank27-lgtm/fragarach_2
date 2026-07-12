# SPEC-014 Implementation Report

Implemented one primary **Data Operations** sidebar destination replacing Acquire and Import Evidence. Its selector reads immutable registrations plus lifecycle supersession state on every refresh, searches display name, symbol, asset class, and provider, hides retired instruments by default, and provides an audit toggle.

The selected instrument supplies shared context to Fetch / Update, Import File, and Retire modes. The surface includes an instrument header, lane matrix, evidence-aware default intent, custom-range review, file checksum/size/row preview, Preserve conflict explanation, readable completion summary, and collapsed technical output.

Retirement invokes the existing SPEC-013 plan and execution bridge, including controlled reason, impact counts, typed confirmation, preservation guarantees, and receipt. Successful mutation triggers immediate selector, lane, and Estate Truth refresh.

Maximum Available and automatic Update to Current are presented as unavailable implementation capabilities with Custom Range and Import File continuations. Ratified intraday authority is acknowledged; the narrower D1 implementation is not described as missing authority. No schema, migration, ingestion pipeline, retirement engine, or public backend authority contract was added or changed.

Verification:

- `swift build`: passed.
- `swift run OperationsCoreChecks`: 15/15 passed.
- `PYTHONPATH=src pytest -q`: 137 passed.
- `./script/build_and_run.sh --verify`: built, ad-hoc signed, launched, and process verification passed.
