# SPEC-012T Implementation Report

Date: 2026-07-12

## Implemented

- Added exact ordered FX mapping authority with evidence source, version, and timestamp.
- ISO parsing now creates semantic identity only; it never constructs provider authority.
- EURAUD is direct with exact `EUR/AUD` evidence.
- AUDEUR is a separate `FX:AUDEUR` identity classified `INVERSE_ONLY`.
- Unknown valid pairs remain `PROVIDER_CAPABILITY_UNKNOWN`.
- Inverse-only lanes show `INVERSE_ONLY`, are non-selectable, and cannot create registration plans.
- Native UI displays base, quote, orientation, exact/inverse symbols, evidence source, warning, and Open EURAUD.
- Registration command revalidates exact FX orientation before the immutable writer.
- Acquisition revalidates the registered ordered identity before transport or persistence.
- Added read-only runtime orientation audit with controlled suspect states.
- No reciprocal bars, schema changes, migrations, historical rewrites, or network discovery.

## Verification

- Python: 134 passed.
- Native checks: 15 passed.
- Mismatch safety fixture: zero provider requests and unchanged evidence/persistence counts.
- Swift app built, signed, launched, and remained running.
