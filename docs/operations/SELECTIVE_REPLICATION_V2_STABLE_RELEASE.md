# Selective Replication v2 Stable Release

Stable baseline: **Fragarach Lite 2.0 build 16**
Frozen: **2026-08-07 Australia/Brisbane**

## Accepted behaviour

- Clicking a Studio-only lane immediately changes it to requested/orange.
- The Lite service wakes immediately rather than waiting for its 300-second scheduled cycle.
- Transfer and verification use real byte counts.
- A verified lane becomes MacBook cache/green.
- Active lanes retain their Studio asset class and remain in the correct market group.
- The Replication page reports stored bytes, bar counts and ranges, receipt/check times, and current state for every local lane.
- Replica lanes can be searched, ordered, grouped, re-requested, or removed without changing Studio authority data.
- New-symbol discovery and onboarding flow from the MacBook to Studio and back to the requested replica lanes.
- Index, equity, crypto, FX, metal, energy, and other classifications remain visible as separate market groups.
- Recent requests, searches, failed searches, and ranked suggestions are display-only local history in a collapsible panel.
- Studio status polling does not collide with operator controls.
- The legacy full replica is retained for rollback but is excluded from v2 ownership and reads.

## Verification record

- Focused Python replication and discovery suites: **36 passed**.
- Swift release product: **FragarachLite built** in debug and release configurations.
- Packaged and installed Build 16 executables and Info.plists match byte-for-byte.
- Publisher and Lite services are healthy.
- Live Lite catalogue at freeze: **READY, 67 local lanes, 72 retained request records**.

## Stable component fingerprints

- `replica_lite.py`: `sha256:8834874c1f2b3ee2b6658752a0583b936a6c66553ceda8ef7c8005e0af32041e`
- `replica_lite_service.py`: `sha256:4b986c6172588fa2a417caf4e531ff6014dbe7bcc97d0d3e536bfd401ea7b532`
- Installed Fragarach Lite executable: `sha256:1a147125faef84f7e70f42c23640839658e0cedf66a3376e3ba3aac1f5540ff2`
- Fragarach Lite Info.plist: `sha256:017ee2d17b30ada4de608c091495d50468d0891636476c7a97b067b6e1af683b`

## Change policy

Treat this build and its archive as the rollback-safe stable baseline. Future replication changes should use a new build number, preserve this archive and the existing MacBook rollback directories, rerun the focused suite, and repeat live request-state verification before installation.
