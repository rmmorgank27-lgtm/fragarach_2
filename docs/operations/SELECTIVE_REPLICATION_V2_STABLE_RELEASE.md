# Selective Replication v2 Stable Release

Stable baseline: **Fragarach Lite 2.0 build 6**
Frozen: **2026-08-06 Australia/Brisbane**

## Accepted behaviour

- Clicking a Studio-only lane immediately changes it to requested/orange.
- The Lite service wakes immediately rather than waiting for its 300-second scheduled cycle.
- Transfer and verification use real byte counts.
- A verified lane becomes MacBook cache/green.
- Active lanes retain their Studio asset class and remain in the correct market group.
- Studio status polling does not collide with operator controls.
- The legacy full replica is retained for rollback but is excluded from v2 ownership and reads.

## Verification record

- Focused Python replication suite: **21 passed**.
- Swift release products: **FragarachLite built**, **FragarachII built**.
- Installed Lite service source matches the tested Studio source byte-for-byte.
- Both installed app bundles pass strict deep code-signature verification.
- Publisher and Lite services are healthy.
- Live selective state at freeze: **8 active local lanes of 159 Studio-available lanes**.
- Lite service error log: empty; FragarachLite crash reports: none.

## Stable component fingerprints

- `replica_lite.py`: `sha256:9924bb7d1545141cc010831baf6ec01c0893011cca35ed86b53861a785cca650`
- `replica_lite_service.py`: `sha256:a78b56b8aebf64245528bfa712620fa9b8ed26512a4efb623f3464a27109654e`
- Installed Fragarach Lite executable: `sha256:f7ccff95553389601735574e9ea7cdb5530b818b9f7ec92760e11569d5027255`
- Fragarach Lite Info.plist: `sha256:8a8dd742929b5aa88fffb061cc55bfea1154e69245756974672376b580c57747`
- Installed Fragarach II executable: `sha256:66994069e02f9cee90eb8de037cf277d8d4f6ac0ee133fb2d8039e0db404ea24`
- Fragarach II Info.plist: `sha256:bcbe44aa8bdd2084d23dc47f6e5c47a617863fcb17f450ad3026fd7b474cc328`

## Change policy

Treat this build and its archive as the rollback-safe stable baseline. Future replication changes should use a new build number, preserve this archive and the existing MacBook rollback directories, rerun the focused suite, and repeat live request-state verification before installation.
