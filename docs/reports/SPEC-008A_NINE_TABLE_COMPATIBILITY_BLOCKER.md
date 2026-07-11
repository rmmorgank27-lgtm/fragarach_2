# SPEC-008A Nine-Table Compatibility Blocker

**Date:** 2026-07-11
**Status:** Material specification incompatibility; stopped before implementation mutation
**Authority:** Candidate Authority

## Exact blocker

SPEC-008A simultaneously requires:

- immutable append-only registration revisions;
- multiple provider mappings per registration;
- exact mapping identity bound by each lane;
- retained rejected/conflicting lane declarations;
- immutable lane supersession chains;
- unchanged existing primary keys;
- no tenth application table.

The accepted schema provides only one registration row per `(asset,D1)` and one lane row per `(asset,timeframe)`. Both authority identities are their primary keys. The lane table prohibits every update; registration identity is immutable. No existing append-only table has a compatible contract or unconstrained parent identity that can hold these new authority records.

Therefore:

- adding columns can store only one snapshot and cannot create required revision/mapping/declaration multiplicity;
- JSON arrays would require in-place mutation, lack exact FK binding, and would not provide immutable element identity;
- reusing provenance or ingest tables would redefine accepted bar-evidence contracts;
- changing the authority-table primary keys is explicitly forbidden;
- adding normalized authority tables would exceed the exact nine-table boundary.

## Affected requirements

| Requirement | Consequence |
|---|---|
| Registration revision and supersession | Cannot insert a second version for the same canonical identity |
| Multiple provider mappings | Cannot attach multiple independently checksummed/reviewed mappings without mutating a row |
| Exact lane-to-mapping binding | No provider-mapping key exists for a foreign key |
| Conflict evidence | Cannot retain a conflicting declaration alongside the accepted lane |
| Lane supersession | Cannot insert a new immutable version for the same asset/timeframe |
| Registration metadata service | `revise` and append-mapping operations cannot meet append-only doctrine |
| Generic lane service | `supersede` and retained-conflict behavior cannot meet the specification |
| Native/CLI completion | Read models would expose a weakened persistence model, not the required authority |

## Unaffected preservation

- Historical migrations 1–5 remain unchanged.
- Runtime database remains unmigrated.
- Existing three registrations, three D1 lanes, bars, raw evidence, provenance, validation, and reads remain unchanged.
- Exact nine-table boundary remains intact.
- No Stage A acquisition or Stage B work began.
- No constitutional document was changed.
- No provider credential was accessed.
- No push was performed.

## Owner decision required

Resume requires one explicit amendment choosing one of these authority models:

1. Authorise additional normalized append-only tables for registration revisions, provider mappings, and lane declaration versions, increasing the table boundary; or
2. Authorise a forward migration that rebuilds `instrument_registrations` and `evidence_lanes` with version-bearing surrogate/composite primary keys and updates dependent foreign keys while preserving old IDs and evidence; or
3. Materially narrow SPEC-008A by removing append-only revisions, multiple mappings, retained conflicts, and supersession, explicitly accepting one immutable metadata snapshot per current identity.

Provider-contract declarations, command scaffolding, and UI work were not implemented independently because Section 8.1 makes persistence compatibility the mandatory implementation gate.

**Operations is King.**
