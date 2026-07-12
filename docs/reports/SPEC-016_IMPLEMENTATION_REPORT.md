# SPEC-016 Implementation Report

Date: 2026-07-12

Custom Range now uses native locale-aware date pickers, a visible completed D1 boundary, canonical ISO preview, and safe presets. `ControlledDateRange` serialises Gregorian UTC `YYYY-MM-DD` and prevents reversed, future, or provider-contract-incompatible ranges before review. `ControlledDateParser` supports ISO, current-locale numeric, and recognised English month-name inputs and returns an explicit interpretation for ambiguous numeric input.

Registered instruments, timeframe, provider, conflict policy, modes, intents, retirement reasons, and file selection remain controlled. Typed retirement confirmation and genuine operator notes remain deliberately free-form.

Current results are now owned by a unique plan revision. Instrument, mode, intent, date, file, or conflict changes clear the current result. Failures render zero mutation counts and `No evidence was written`; success values come only from the same current process JSON. Historical receipts remain under Data Operations → History.

Changed files include `ControlledInputs.swift`, `ConsoleStore.swift`, `DataOperationsView.swift`, OperationsCore checks, and SPEC-016 reports/screenshots. No schema, migration, authority, provider fact, Truth, registration, retirement, or runtime evidence behavior changed.
