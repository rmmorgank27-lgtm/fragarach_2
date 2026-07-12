# SPEC-016 Preflight Report

Date: 2026-07-12

Data Operations already used an authority-backed registration list, controlled D1 lane context, a read-only Twelve Data provider mapping, segmented operation intent/mode controls, controlled conflict policy, and the system file picker. Custom Range alone used unrestricted `String` fields and forwarded them verbatim to the ISO-only acquisition command.

The result defect came from combining `store.lastProcessResult` for the current failure with `store.snapshot.operations.first` for counts and raw-block identity. Those values had independent ownership and could describe different operations.

Required changes are confined to a controlled date/range model, locale parser, plan revision/result ownership, Data Operations calendar controls/validation, ConsoleStore isolation, native checks, and reports. No authority, provider, ingestion, Truth, schema, migration, or database change is required.
