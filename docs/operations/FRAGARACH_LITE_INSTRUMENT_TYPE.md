# Fragarach Lite instrument type replication

Fragarach Lite build 17 adds canonical `instrument_type` to replicated symbol metadata.

- Full snapshot databases use `fragarach.replica_database.v2`.
- Selective lane databases use `fragarach.lane_database.v3`.
- New `registrations` rows contain both `asset_class` and `instrument_type`.
- Publisher control, selective manifests, Lite receipts, and `/v1/catalogue` lane records expose `instrument_type`.
- Active v2 requests are treated as update-eligible even when their bar revision is unchanged. One schema upgrade is scheduled per registry poll so the publisher remains responsive while replacing them with v3 artifacts.
- Lite's native `LiteLane` model decodes the field and shows it in lane help text.
- Previously admitted full v1 and selective v2 databases remain readable. Because those artifacts did not carry the field, Lite reports their `instrument_type` as `UNKNOWN` until a new artifact is admitted.

This is a replicated metadata change only. Fragarach II remains the registration authority, and the market-history response contract is unchanged.
