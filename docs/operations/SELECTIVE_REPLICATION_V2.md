# Selective Replication v2

## Decision

Fragarach Lite v2 does not infer lane ownership from the legacy full snapshot. The Studio publishes a per-client registry and immutable, independently downloadable lane artifacts. A lane is local only after that lane's artifact has been downloaded, verified, and atomically admitted.

The v1 full snapshot remains readable only until a client first receives a v2 registry. It is then retained as a migration backup but is excluded from catalogue counts and Market History reads.

## Authoritative contract

- The Studio owns a persistent registry in `clients.json`. Both UIs read projections of this same registry.
- Every `(client_id, symbol, timeframe)` request has a UUID `request_id`.
- Normal lifecycle: `REQUESTED → ACCEPTED → TRANSFERRING → VERIFYING → ACTIVE`.
- Control/error states: `PAUSED`, `FAILED`, `CANCELLED`, and `REMOVED`. Retry returns a failed request to `ACCEPTED`; resume restores the preceding usable state; removal deletes the Lite admission while retaining registry history.
- The registry distinguishes all Studio-available lanes from the client's requested, transferring, active, paused, and failed lanes.
- Every request records `expected_bytes`, `transferred_bytes`, and `verified_bytes`. Progress is derived only from these persisted counters.
- Every active lane records its CAODT, authority source revision, artifact SHA-256, lane fingerprint, and bar count.

## Artifacts and admission

The Studio creates one immutable gzip-compressed SQLite artifact per lane revision. An artifact ID is content-addressed. The authority database is opened read-only; publishing never mutates it.

Lite downloads into staging and reports transferred bytes. Before activation it verifies:

1. compressed byte count and SHA-256;
2. decompression and SQLite integrity;
3. manifest identity, symbol, timeframe, and row count;
4. deterministic lane fingerprint.

Only a fully verified database is renamed into the lane store and added to `active-lanes-v2.json`. Both writes are atomic. An interrupted or invalid transfer therefore leaves the previously active lane intact.

## Control and retention

- Pausing retains the verified local database and stops update admission.
- Resuming permits transfer/admission again.
- Cancelling stops a request that has not become the retained subscription.
- Removing deletes the active admission and local lane database, but preserves registry history on Studio.
- Retrying never weakens verification or reuses incomplete staging data.

## Recovery

Registry, request, progress, and active-lane receipts are disk-backed. Studio restart repairs incomplete registry writes; Lite restart reconciles its local request records with the Studio registry. Sleep, loss of Tailscale, or reboot leaves active verified lanes readable and resumes pending work on the next 300-second service cycle or manual refresh.

## Security and boundaries

Transport remains Tailscale HTTPS with the existing client credential. Lite's service remains loopback-only and read-only. Lite receives no provider acquisition code and no authority write capability. Tokens are neither logged, copied into artifacts, nor rotated during migration.

## Migration and installation order

1. Preserve the current Lite application-support directory, LaunchAgent, configuration, credential, and v1 full replica.
2. Record the installed app version and newest FragarachLite crash report before replacement.
3. Install the Studio v2 publisher files and restart only the publisher after a successful preflight.
4. Install the Lite v2 service files and Fragarach Lite 2.0 (build 5), preserving its 300-second interval and explicit `--allow-unsigned` option.
5. On the first successful v2 registry read, show zero local lanes until specifically requested; retain but ignore the legacy full replica.
6. Prove two requested lanes transfer and activate while a third unrequested lane is neither transferred nor readable.

Rollback restores the preserved application/service files and continues to use the untouched v1 replica. No authority database rollback is required.
