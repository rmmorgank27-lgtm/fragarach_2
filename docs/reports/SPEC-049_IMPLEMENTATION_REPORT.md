# SPEC-049 Implementation Report

## Result

The Scheduler production lifetime is no longer owned by `Fragarach II.app`. A user-scoped LaunchAgent owns continuous execution, a versioned user-only Unix socket carries monitor/status and operator commands, and normal app termination only closes the monitor polling task.

## Implemented boundaries

- user LaunchAgent with login start, controlled failed-exit restart throttling, enable/disable/update/uninstall controls, and no credentials in its plist;
- lifetime acquisition owner lock keyed to the canonical authority database;
- independent two-second heartbeat and persisted monitor snapshot;
- v1 status and command contracts plus v3 live monitor contract;
- target-generation validation and bounded persisted idempotency acknowledgements;
- service-owned Pause/Resume, Retry Now, Run Queue Now, queue bandwidth, manual request, ingestion hold, and Operator Fetch execution;
- graceful explicit stop distinct from Pause All;
- bounded restart history, exponential crash backoff, and crash-loop protection;
- shared environment/Keychain/approved-file credential resolution without credential publication;
- native Scheduler Service section and compact Overview health separated from authority integrity;
- CLI service ownership detection and explicit recovery/development-only standalone execution;
- repair diagnostics for installation, executable/signature, authority, journal, credential, ownership, monitor, and compatibility;
- operational persistence outside SQLite; canonical authority remains exactly ten tables.

## Verification

- focused SPEC-049 lifecycle, LaunchAgent, single-owner, heartbeat, idempotency, graceful-stop, and ten-table tests;
- existing SPEC-041, SPEC-046, SPEC-047, SPEC-048, and SPEC-045 focused regression coverage;
- SwiftPM debug and release builds;
- release Swift build, ad-hoc bundle integrity verification, and a detached app-closed/service-running lifecycle proof.

## Acceptance boundary

The on-machine production-signed journey is not yet claimable. `security find-identity -v -p codesigning` reports zero valid identities; the generated bundle therefore has `Signature=adhoc`, no Team Identifier, and Gatekeeper rejects it. The minimum remaining prerequisite is installation of an appropriate Developer ID/Application signing identity (and any required provisioning), followed by rebuilding with that identity and repeating the LaunchAgent/app-close journey against the operator-selected authority and credential.

The detached lifecycle proof did establish a stable service generation and independent heartbeat while `FragarachII` was not running, followed by an acknowledged graceful stop and clean ownership release. The copied authority remained exactly ten tables with integrity `ok` and no foreign-key findings.
