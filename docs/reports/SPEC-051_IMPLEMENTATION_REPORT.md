# SPEC-051 — Canonical Observation Publication Lineage Repair

## Outcome

Accepted. Estate, market, subgroup, lane, Swift DTO, and native presentation now
publish the current `latest_canonical_observation`. The `caodt` compatibility
field remains available and is derived from that value.

## Deterministic root cause

Canonical publication and lane snapshots were current. The first incorrect
stage was summary publication:

- Python stored `overall_caodt` as the minimum lane CAODT and described it as
  `EARLIEST_LANE_CAODT`.
- Swift independently repeated `lanes.map(...caodt).min()` for estate, market,
  and subgroup summaries.

Consequently, a genuine D1 observation at
`2026-07-13T00:00:00+00:00` was copied into every summary and displayed as if it
were the latest canonical observation, while newer intraday lane authority was
discarded from the publication lineage.

## Repair

- Estate publication now selects the newest non-null lane
  `latest_canonical_observation` once.
- Root, estate-summary, `caodt`, and `overall_caodt` publication fields all
  expose that same value.
- Swift DTOs retain lane/root `latest_canonical_observation`,
  `authority_generated`, and `authority_revision` instead of discarding them.
- Native market, subgroup, and estate summaries derive their CAODT compatibility
  value from the newest decoded lane observation.
- Native CAODT views read the repaired canonical-observation fields.

No Scheduler, acquisition, Queue, provider-authority, Truth-score, freshness,
synthetic-repository, or canonical-evidence code was changed.

## Canonical and lane evidence

At the final read-only verification (`authority_generated`
`2026-07-14T22:45:58.429757+00:00`):

| Lane | latest canonical observation | authority revision |
|---|---|---|
| AUDUSD D1 | `2026-07-13T00:00:00+00:00` | `sha256:dc6b05bb25f80c7b607b8ab93691173b57cc81a6543bae5f8232e0b508a73e5f` |
| AUDUSD H1 | `2026-07-14T05:00:00+00:00` | `sha256:0d2e74db32ab632c637444d14e05e1d2bfcdc0f4ba4f376d2f1048a18be41d24` |
| AUDUSD M30 | `2026-07-14T04:30:00+00:00` | `sha256:3a82e0491414045d507b0fca11a6bdf9fb8bd0c8e7050eb41583953c26e4f0d0` |
| AUDUSD M5 | `2026-07-14T04:05:00+00:00` | `sha256:d575dba60a08f19f140c66b41c17b28bdd4f5108e8e6d96a90e2d32f44f2a422` |
| XAUUSD D1 | `2026-07-13T00:00:00+00:00` | `sha256:875277f24e5bdd8025f0605ece9272531ab4076267defd78983ee22616169130` |
| USO D1 | `2026-07-13T00:00:00+00:00` | `sha256:fcc91eaf4d9f45db0ab310786fe70c6c9d1e34f30d1c929e9d648b0d10de102f` |

The estate's newest published canonical observation was
`2026-07-14T22:25:00+00:00`; root `latest_canonical_observation`, root `caodt`,
estate-summary `latest_canonical_observation`, and estate-summary `caodt` were
identical. D1 lanes correctly retained July 13 because that was genuinely their
latest canonical observation.

## Verification

- Focused Python publication/Truth/freshness suite: `22 passed`.
- Focused release-native lineage check: `1 passed` across populated Forex,
  Metals, Energy, market, subgroup, estate, and lane DTOs.
- Full Python suite: `277 passed, 2 subtests passed`.
- Full native OperationsCore suite: `32 passed`.
- Final signed release build completed, codesign verification passed, and the
  Fragarach II process remained alive.

`authority_generated` continued advancing independently of canonical
observation timestamps. Lane Truth scores and freshness states were read back
unchanged from their existing engines; their implementation files were not
modified.
