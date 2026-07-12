# SPEC-016 Native Input Audit

| Field | Classification | Domain / control | Normalisation and validation |
|---|---|---|---|
| Discover Market query | AUTHORITY_SEARCH | Free-form intent search retained | Deterministic discovery resolves a selected canonical representation before registration. |
| Data Operations instrument | CONTROLLED_SELECTION | Searchable immutable registration list | Emits exact `asset:timeframe`; retired hidden unless requested. |
| Data Operations mode and intent | CONTROLLED_SELECTION | Segmented enums | Emits controlled Swift enum/backend intent. |
| Custom Range dates | DATE_OR_TIME | Native date-only `DatePicker` controls | Locale display; canonical Gregorian UTC `YYYY-MM-DD`; reversed, future, and >5,000-day ranges rejected locally. |
| Date presets | CONTROLLED_SELECTION | Menu | Populates both controlled dates; never defaults an empty lane to seven days. |
| Timeframe | CONTROLLED_SELECTION | Selected registered lane | Emits exact registered D1 currently; no text entry. |
| Provider | CONTROLLED_SELECTION | Read-only registration/provider context | Emits exact registered `TWELVE_DATA`; no text entry. |
| Conflict policy | CONTROLLED_SELECTION | Picker | Emits `preserve` or `correct`. |
| Import file | FILE_SELECTION | macOS file panel | Derives path, name, bytes, checksum, format, and rows. Instrument/timeframe come from selected registration. |
| Retirement reason/scope | CONTROLLED_SELECTION | Picker/segmented controls | Emits reviewed reason/scope enum values. |
| Retirement note | FREE_TEXT_NOTE | Text field retained | Trimmed by retirement service; genuinely unconstrained. |
| Retirement confirmation | TYPED_SAFETY_CONFIRMATION | Exact text field retained | Compared with controlled case/whitespace normalisation; never autocorrected or reused. |
| Truth and Audit search | AUTHORITY_SEARCH | Search fields retained | Filters read-only projections; never becomes an authority identity. |
| Backup destination | FILE_SELECTION | macOS file panel | Canonical filesystem path selected by operator. |
| Database/repository/Python settings | FILE_SELECTION / advanced path configuration | Existing path fields plus database chooser | Operator configuration only; credentials and authority facts remain excluded. |

No uncontrolled symbol, timeframe, provider, enum, numeric threshold, or operation date remains in the Data Operations execution path.
