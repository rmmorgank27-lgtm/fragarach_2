"""Atomic provider-aware onboarding over registration and provider authority."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from .acquisition_orchestrator import acquisition_capability_projection, load_provider_profiles
from .freshness import authority_revision_for_lane
from .commissioning_authority import required_timeframes
from .lane_commissioning import ensure_commissioned_lane
from .lane_update_register import LaneUpdateRegister
from .provider_facts import (
    approve_reviewed_provider_mapping,
    load_provider_facts,
    provider_facts_path,
    representation_mapping,
    resolve_exact_fx_mapping_for_admission,
)
from .credentials import CredentialAuthority
from .storage import RegistrationCandidate, RegistrationError, open_read_only, register_instrument


def register_provider_aware_instrument(
    database_path: str | Path, candidate: RegistrationCandidate, *,
    registered_at_utc: str,
    mapping_writer: Callable[..., dict[str, object]] = approve_reviewed_provider_mapping,
    exact_fx_mapping_resolver: Callable[..., dict[str, object] | None] = resolve_exact_fx_mapping_for_admission,
) -> dict[str, object]:
    """Commit selected mapping + registration, with rollback and readback proof."""
    automatically_resolved_fx_mapping = False

    if (
        candidate.asset_class == "FX"
        and not all((candidate.provider_id, candidate.provider_contract, candidate.provider_symbol, candidate.provider_instrument_type))
    ):
        # Treat an exact provider representation as normal admission work, not
        # a second operator workflow.  The resolver uses the bounded provider
        # reference catalogue only; it cannot acquire or publish price bars.
        # A missing, ambiguous or failed lookup retains the explicit pending
        # state below and never fabricates a provider mapping.
        quote = candidate.trading_currency.strip().upper()
        base = candidate.asset[:-len(quote)] if candidate.asset.endswith(quote) else ""
        discovered = exact_fx_mapping_resolver(
            database_path,
            canonical_symbol=candidate.asset,
            base_asset=base,
            quote_asset=quote,
            instrument_type=candidate.instrument_type,
            aliases=tuple(alias.normalized_alias for alias in candidate.aliases),
            credential=CredentialAuthority().credential_for("TWELVE_DATA"),
        )
        if discovered and discovered.get("provider_symbol"):
            automatically_resolved_fx_mapping = True
            candidate = replace(
                candidate,
                provider_id="TWELVE_DATA",
                provider_contract="TWELVE_DATA_TIME_SERIES_D1_V1",
                provider_symbol=str(discovered["provider_symbol"]),
                provider_instrument_type=str(discovered.get("provider_instrument_type") or "Physical Currency"),
                provider_exchange=None,
                provider_country=None,
            )
        else:
            return _register_unmapped_fx_for_discovery(
                database_path, candidate, registered_at_utc=registered_at_utc,
            )

    if not all((candidate.provider_id, candidate.provider_contract, candidate.provider_symbol, candidate.provider_instrument_type)):
        raise RegistrationError(
            "REVIEWED_PROVIDER_REPRESENTATION_REQUIRED",
            "Select and approve a provider representation before registration.",
        )
    provider = str(candidate.provider_id).upper()
    profile = next((value for value in load_provider_profiles() if value.provider == provider), None)
    if profile is None or not profile.enabled:
        raise RegistrationError("UNSUPPORTED_PROVIDER", provider)
    if candidate.asset_class not in profile.supported_asset_classes or candidate.timeframe not in profile.supported_timeframes:
        raise RegistrationError("UNSUPPORTED_PROVIDER_CAPABILITY", f"{provider}:{candidate.asset_class}:{candidate.timeframe}")

    existing = _existing_registration(database_path, candidate.asset, candidate.timeframe)
    if existing is not None:
        _assert_same_canonical_identity(existing["identity"], candidate)
        if existing["provider_id"] is not None:
            prior = existing["identity"]
            if (
                str(prior.get("provider_id") or "").upper() != provider
                or prior.get("provider_symbol") != candidate.provider_symbol
            ):
                raise RegistrationError("CANONICAL_ASSET_COLLISION", candidate.asset)

    facts_file = provider_facts_path(database_path)
    prior_exists = facts_file.exists()
    prior_bytes = facts_file.read_bytes() if prior_exists else None
    try:
        if not automatically_resolved_fx_mapping:
            mapping_writer(
                database_path,
                canonical_symbol=candidate.asset,
                provider=provider,
                provider_symbol=str(candidate.provider_symbol),
                timeframe=candidate.timeframe,
                asset_class=candidate.asset_class,
                representation_type=candidate.representation_type,
                provider_instrument_type=str(candidate.provider_instrument_type),
                decided_at=datetime.fromisoformat(registered_at_utc),
            )
        if existing is None:
            registration = register_instrument(
                database_path, candidate, registered_at_utc=registered_at_utc
            )
            outcome = registration.outcome
            registration_status = registration.registration_status
            checksum = registration.identity_checksum_sha256
        else:
            outcome = "PROVIDER_SETUP_COMPLETED" if existing["provider_id"] is None else "EXISTING_IDENTICAL"
            registration_status = str(existing["registration_status"])
            checksum = str(existing["identity_checksum_sha256"])

        mapping = representation_mapping(database_path, provider, candidate.asset)
        projection = acquisition_capability_projection(
            database_path, symbol=candidate.asset, timeframe=candidate.timeframe
        )
        selected = next((
            row for row in projection["rows"]
            if row.get("provider") == provider and row.get("eligibility") == "ELIGIBLE"
        ), None)
        if not mapping or mapping.get("provider_symbol") != candidate.provider_symbol or selected is None:
            raise RegistrationError("PROVIDER_MAPPING_READBACK_FAILED", candidate.asset)
    except BaseException:
        _restore_provider_facts(facts_file, prior_exists, prior_bytes)
        raise

    # Estate admission is the commissioning decision.  Every enabled lane with
    # an approved, eligible route becomes Scheduler-owned immediately; a
    # separate operator commissioning step would strand newly admitted symbols
    # in a manual-only state.
    commissioned_timeframes, commissioning_skips = _commission_estate_lanes(
        database_path, symbol=candidate.asset, asset_class=candidate.asset_class,
        observed_at=registered_at_utc,
    )

    # Queue governed initial work durably.  The scheduler service owns actual
    # dispatch, so registration stays fast and the manual Required Set control
    # remains available as an explicit operator override.
    from .scheduler_service import queue_estate_admission_initial_fetch
    try:
        scheduler_reconciliation = queue_estate_admission_initial_fetch(
            database_path, symbol=candidate.asset,
            credential=CredentialAuthority().credential_for("TWELVE_DATA"),
            at=datetime.fromisoformat(registered_at_utc),
        )
    except (OSError, RuntimeError, ValueError) as error:
        scheduler_reconciliation = {
            "outcome": "ESTATE_ADMISSION_QUEUE_PENDING",
            "reason": str(error),
        }

    facts = load_provider_facts(database_path)
    with open_read_only(database_path) as connection:
        lane_revision = authority_revision_for_lane(
            connection, symbol=candidate.asset, timeframe=candidate.timeframe
        )
        registration_count = int(connection.execute(
            "SELECT count(*) FROM instrument_registrations WHERE asset=? AND timeframe=?",
            (candidate.asset, candidate.timeframe),
        ).fetchone()[0])
    provider_revision = int(facts.get("revision", 0) or 0)
    estate_revision = "sha256:" + hashlib.sha256(
        f"{lane_revision}|provider-facts:{provider_revision}".encode()
    ).hexdigest()
    operator_action = (
        "APPROVE_PROVIDER_MAPPING_AND_ADD"
        if existing is None else
        "APPROVE_PROVIDER_MAPPING"
        if outcome == "PROVIDER_SETUP_COMPLETED" else
        "CONFIRM_EXISTING_APPROVED_MAPPING"
    )
    selected_representation = candidate.selected_representation or candidate.local_symbol
    return {
        "operation_contract": "fragarach_ii.atomic_provider_onboarding.v1",
        "outcome": outcome,
        "symbol": candidate.asset,
        "asset": candidate.asset,
        "timeframe": candidate.timeframe,
        "canonical_identity": candidate.underlying_reference,
        "representation": selected_representation,
        "representation_type": candidate.representation_type,
        "identity_checksum_sha256": checksum,
        "registration_status": registration_status,
        "registration_event": outcome,
        "provider_setup_status": "COMPLETE",
        "provider": provider,
        "provider_symbol": candidate.provider_symbol,
        "mapping_status": "APPROVED_REPRESENTATION",
        "mapping_class": mapping.get("mapping_class"),
        "timeframe_supported": True,
        "commissioned_timeframes": commissioned_timeframes,
        "commissioning_skips": commissioning_skips,
        "operator_action": operator_action,
        "timestamp": registered_at_utc,
        "atomic_steps": [
            {"step": 1, "name": "selected canonical identity", "status": "COMPLETE", "value": candidate.underlying_reference},
            {"step": 2, "name": "selected tradable representation", "status": "COMPLETE", "value": selected_representation},
            {"step": 3, "name": "provider mapping approved", "status": "COMPLETE", "provider": provider, "provider_symbol": candidate.provider_symbol},
            {"step": 4, "name": "registration added to Estate", "status": "COMPLETE", "event": outcome},
            {"step": 5, "name": "enabled estate lanes auto-commissioned", "status": "COMPLETE", "timeframes": commissioned_timeframes},
            {"step": 6, "name": "initial acquisition queued", "status": "COMPLETE", "timeframes": scheduler_reconciliation.get("queued_timeframes", [])},
        ],
        "provider_fact_revision": provider_revision,
        "estate_revision": estate_revision,
        "registration_count": registration_count,
        "readback_eligible": True,
        "scheduler_reconciliation": scheduler_reconciliation,
    }


def _register_unmapped_fx_for_discovery(
    database_path: str | Path, candidate: RegistrationCandidate, *, registered_at_utc: str,
) -> dict[str, object]:
    """Keep an unresolved FX symbol visible without making a false mapping."""

    existing = _existing_registration(database_path, candidate.asset, candidate.timeframe)
    if existing is None:
        registration = register_instrument(database_path, candidate, registered_at_utc=registered_at_utc)
        outcome = registration.outcome
        registration_status = registration.registration_status
        checksum = registration.identity_checksum_sha256
    else:
        _assert_same_canonical_identity(existing["identity"], candidate)
        outcome = "EXISTING_IDENTICAL"
        registration_status = str(existing["registration_status"])
        checksum = str(existing["identity_checksum_sha256"])

    commissioned_timeframes, commissioning_skips = _commission_estate_lanes(
        database_path, symbol=candidate.asset, asset_class=candidate.asset_class,
        observed_at=registered_at_utc,
    )
    from .scheduler_service import queue_estate_admission_initial_fetch
    try:
        scheduler_reconciliation = queue_estate_admission_initial_fetch(
            database_path, symbol=candidate.asset,
            credential=CredentialAuthority().credential_for("TWELVE_DATA"),
            at=datetime.fromisoformat(registered_at_utc),
        )
    except (OSError, RuntimeError, ValueError) as error:
        scheduler_reconciliation = {
            "outcome": "PROVIDER_MAPPING_DISCOVERY_PENDING",
            "reason": str(error),
            "queued_timeframes": [],
        }
    scheduler_reconciliation.setdefault("queued_timeframes", [])
    return {
        "operation_contract": "fragarach_ii.atomic_provider_onboarding.v1",
        "outcome": outcome,
        "symbol": candidate.asset,
        "asset": candidate.asset,
        "timeframe": candidate.timeframe,
        "canonical_identity": candidate.underlying_reference,
        "representation": candidate.selected_representation or candidate.local_symbol,
        "representation_type": candidate.representation_type,
        "identity_checksum_sha256": checksum,
        "registration_status": registration_status,
        "registration_event": outcome,
        "provider_setup_status": "MAPPING_DISCOVERY_PENDING",
        "provider": None,
        "provider_symbol": None,
        "mapping_status": "MAPPING_REQUIRED",
        "timeframe_supported": False,
        "commissioned_timeframes": commissioned_timeframes,
        "commissioning_skips": commissioning_skips,
        "operator_action": "WAIT_FOR_PROVIDER_MAPPING_DISCOVERY",
        "timestamp": registered_at_utc,
        "atomic_steps": [
            {"step": 1, "name": "selected canonical identity", "status": "COMPLETE", "value": candidate.underlying_reference},
            {"step": 2, "name": "registered in Estate", "status": "COMPLETE", "event": outcome},
            {"step": 3, "name": "provider mapping discovery", "status": "PENDING"},
            {"step": 4, "name": "initial acquisition", "status": "WAITING_FOR_PROVIDER_MAPPING"},
        ],
        "scheduler_reconciliation": scheduler_reconciliation,
    }


def _commission_estate_lanes(
    database_path: str | Path, *, symbol: str, asset_class: str, observed_at: str,
) -> tuple[list[str], list[dict[str, str]]]:
    """Commission enabled lanes only when provider authority can serve them."""
    commissioned: list[str] = []
    skipped: list[dict[str, str]] = []
    for timeframe in required_timeframes(asset_class):
        if timeframe == "D1":
            # Registration creates the D1 evidence lane and makes it active.
            commissioned.append(timeframe)
            continue
        projection = acquisition_capability_projection(
            database_path, symbol=symbol, timeframe=timeframe,
            now=datetime.fromisoformat(observed_at),
        )
        eligible = [
            row for row in projection.get("rows", [])
            if row.get("eligibility") == "ELIGIBLE"
        ]
        if not eligible:
            reasons = sorted({
                str(row.get("rejection_reason") or "NO_ELIGIBLE_PROVIDER")
                for row in projection.get("rows", [])
            })
            skipped.append({"timeframe": timeframe, "reason": ", ".join(reasons)})
            continue
        try:
            ensure_commissioned_lane(
                database_path, symbol, timeframe, observed_at=observed_at
            )
        except ValueError as error:
            skipped.append({"timeframe": timeframe, "reason": str(error)})
        else:
            commissioned.append(timeframe)
    # The runtime register is intentionally not rebuilt on every normal wake.
    # Add only the lanes admitted in this transaction so they can receive both
    # their initial fetch and later time-triggered updates immediately.
    register = LaneUpdateRegister(database_path)
    for timeframe in commissioned:
        register.ensure_commissioned_lane(
            asset=symbol, timeframe=timeframe,
            at=datetime.fromisoformat(observed_at),
        )
    return commissioned, skipped


def activate_existing_estate_admission(
    database_path: str | Path, *, observed_at: str | None = None,
) -> dict[str, object]:
    """Apply estate-admission automation to registrations created before it.

    This is deliberately idempotent: a daemon restart can repair legacy
    ``NOT_COMMISSIONED`` lanes without duplicating a pending initial fetch.
    """
    observed = observed_at or datetime.now(UTC).isoformat()
    with open_read_only(database_path) as connection:
        registrations = connection.execute(
            """SELECT asset, asset_class FROM instrument_registrations
               WHERE timeframe='D1' AND registration_status LIKE 'REGISTERED_%'
               ORDER BY asset"""
        ).fetchall()
    activated: list[dict[str, object]] = []
    from .scheduler_service import queue_estate_admission_initial_fetch
    for symbol, asset_class in registrations:
        commissioned, skipped = _commission_estate_lanes(
            database_path, symbol=str(symbol), asset_class=str(asset_class), observed_at=observed,
        )
        try:
            queued = queue_estate_admission_initial_fetch(
                database_path, symbol=str(symbol),
                credential=CredentialAuthority().credential_for("TWELVE_DATA"),
                at=datetime.fromisoformat(observed),
            )
        except (OSError, RuntimeError, ValueError) as error:
            queued = {"queued_timeframes": [], "reason": str(error)}
            skipped.append({"timeframe": "*", "reason": str(error)})
        activated.append({
            "symbol": str(symbol), "commissioned_timeframes": commissioned,
            "commissioning_skips": skipped,
            "queued_timeframes": queued.get("queued_timeframes", []),
        })
    return {
        "contract": "fragarach_ii.estate_admission_migration.v1",
        "activated": activated,
    }


def _existing_registration(database_path: str | Path, asset: str, timeframe: str) -> dict[str, object] | None:
    with open_read_only(database_path) as connection:
        row = connection.execute(
            "SELECT identity_json,provider_id,registration_status,identity_checksum_sha256,registered_at_utc FROM instrument_registrations WHERE asset=? AND timeframe=?",
            (asset, timeframe),
        ).fetchone()
    if row is None:
        return None
    return {
        "identity": json.loads(row[0]), "provider_id": row[1],
        "registration_status": row[2], "identity_checksum_sha256": row[3],
        "registered_at_utc": row[4],
    }


def _assert_same_canonical_identity(identity: dict[str, object], candidate: RegistrationCandidate) -> None:
    ignored = {
        "provider_id", "provider_contract", "provider_symbol", "provider_instrument_type",
        "provider_exchange", "provider_country", "provider_identity_key",
        "registration_contract", "registration_contract_version",
        "selected_representation",
    }
    for field in RegistrationCandidate.__dataclass_fields__:
        if field in ignored or field == "aliases":
            continue
        prior = identity.get(field)
        current = getattr(candidate, field)
        if prior != current:
            raise RegistrationError("CANONICAL_ASSET_COLLISION", candidate.asset)


def _restore_provider_facts(path: Path, existed: bool, payload: bytes | None) -> None:
    if not existed:
        path.unlink(missing_ok=True)
        return
    assert payload is not None
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.rollback.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
