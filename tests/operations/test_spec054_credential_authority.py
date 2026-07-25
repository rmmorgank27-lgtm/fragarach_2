from __future__ import annotations

import plistlib
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.acquisition_orchestrator import classify_failure, credential_map, update_provider_health
from fragarach_ii.credentials import CredentialAuthority, CredentialState
from fragarach_ii.providers.twelve_data import AcquisitionError
from fragarach_ii.scheduler_daemon import ServicePaths, launch_agent_definition


class MemoryStore:
    def __init__(self, values=None, *, unavailable=False):
        self.values = dict(values or {})
        self.unavailable = unavailable

    def read(self, account: str) -> str | None:
        if self.unavailable:
            raise OSError("secure storage unavailable")
        return self.values.get(account)

    def write(self, account: str, credential: str) -> None:
        if self.unavailable:
            raise OSError("secure storage unavailable")
        self.values[account] = credential


def authority(tmp_path: Path, store: MemoryStore) -> CredentialAuthority:
    return CredentialAuthority(
        store=store,
        metadata_path=tmp_path / "credential-authority.json",
        clock=lambda: datetime(2026, 7, 15, 5, 0, tzinfo=UTC),
    )


def test_every_consumer_observes_one_revision_and_updates_immediately(tmp_path):
    store = MemoryStore({"TWELVE_DATA_API_KEY": "shared-secret"})
    native = authority(tmp_path, store)
    scheduler = authority(tmp_path, store)
    cli = authority(tmp_path, store)
    router = authority(tmp_path, store)

    first = [consumer.resolve("TWELVE_DATA") for consumer in (native, scheduler, cli, router)]
    assert {item.state for item in first} == {CredentialState.AVAILABLE}
    assert len({item.authority_revision for item in first}) == 1
    assert {item.credential for item in first} == {"shared-secret"}

    native.store_credential("TWELVE_DATA", "updated-secret")
    second = [consumer.resolve("TWELVE_DATA") for consumer in (native, scheduler, cli, router)]
    assert {item.credential for item in second} == {"updated-secret"}
    assert len({item.authority_revision for item in second}) == 1
    assert second[0].authority_revision != first[0].authority_revision


def test_local_states_are_deterministic_and_redacted(tmp_path):
    missing = authority(tmp_path, MemoryStore()).resolve("TWELVE_DATA")
    unavailable = authority(tmp_path, MemoryStore(unavailable=True)).resolve("TWELVE_DATA")
    assert missing.state is CredentialState.MISSING
    assert unavailable.state is CredentialState.UNAVAILABLE
    assert "credential" not in missing.public_dict()

    store = MemoryStore({"TWELVE_DATA_API_KEY": "invalid-secret"})
    owner = authority(tmp_path, store)
    owner.record_validation(
        "TWELVE_DATA", credential_state=CredentialState.INVALID,
        validation_source="Twelve Data HTTP response",
        provider_response_state="Authentication Failed", provider_response_code=401,
    )
    invalid = owner.resolve("TWELVE_DATA")
    assert invalid.state is CredentialState.INVALID
    assert invalid.last_validation == "2026-07-15T05:00:00+00:00"
    assert "invalid-secret" not in str(owner.snapshot())


def test_router_uses_authority_projection_not_process_environment(tmp_path, monkeypatch):
    owner = authority(tmp_path, MemoryStore({"TWELVE_DATA_API_KEY": "authority-secret"}))
    monkeypatch.setattr("fragarach_ii.acquisition_orchestrator.CredentialAuthority", lambda: owner)
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "wrong-environment-secret")
    assert credential_map() == {"TWELVE_DATA": "authority-secret"}


def test_launch_agent_contains_no_secret_and_uses_same_service_entrypoint(tmp_path):
    database = tmp_path / "authority.sqlite3"
    database.touch()
    paths = ServicePaths.create(database, support=tmp_path / "support", home=tmp_path / "home")
    definition = launch_agent_definition(paths, python="/usr/bin/python3", repository=tmp_path)
    serialized = plistlib.dumps(definition).decode()
    assert "TWELVE_DATA_API_KEY" not in serialized
    assert definition["ProgramArguments"][-2:] == ["--mode", "service-run"]


def test_provider_responses_never_mask_as_local_missing():
    assert classify_failure(AcquisitionError("MISSING_CREDENTIAL", "absent"))[0] == "CREDENTIAL_MISSING"
    assert classify_failure(AcquisitionError("AUTHENTICATION_FAILED", "Twelve Data HTTP 401"))[0] == "AUTHENTICATION_FAILED"
    assert classify_failure(AcquisitionError("RATE_LIMITED", "Twelve Data HTTP 429"))[0] == "TWELVEDATA_RATE_LIMIT_429"
    assert classify_failure(AcquisitionError("QUOTA_EXCEEDED", "credits exhausted"))[0] == "QUOTA_EXCEEDED"
    assert classify_failure(TimeoutError("provider timed out"))[0] == "TWELVEDATA_TRANSPORT_FAILURE"


def test_provider_health_distinguishes_missing_from_remote_authentication():
    profile = type("Profile", (), {"cooldown_seconds": 60, "provider": "TWELVE_DATA"})()
    now = datetime(2026, 7, 15, tzinfo=UTC)
    missing = {}
    update_provider_health(missing, profile, "CREDENTIAL_MISSING", now)
    assert (missing["health"], missing["wait_reason"]) == ("Credential Missing", "CREDENTIAL_MISSING")
    rejected = {}
    update_provider_health(rejected, profile, "AUTHENTICATION_FAILED", now)
    assert (rejected["health"], rejected["wait_reason"]) == ("Authentication Failed", "AUTHENTICATION_FAILED")


def test_listed_consumers_do_not_implement_storage_lookup_chains():
    root = Path(__file__).resolve().parents[2]
    consumers = [
        root / "src/fragarach_ii/commands/acquire.py",
        root / "src/fragarach_ii/commands/provider_facts.py",
        root / "src/fragarach_ii/commands/search_instrument.py",
        root / "src/fragarach_ii/commands/scheduler.py",
        root / "src/fragarach_ii/acquisition_orchestrator.py",
        root / "Sources/FragarachII/Stores/ConsoleStore.swift",
        root / "Sources/OperationsCore/ProcessBridge.swift",
        root / "Sources/OperationsCore/SchedulerBridge.swift",
    ]
    forbidden = ("find-generic-password", "Morphix_Data_Hot", "credentials.env", 'os.environ.get("TWELVE_DATA_API_KEY")', 'environment["TWELVE_DATA_API_KEY"]')
    for consumer in consumers:
        text = consumer.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), consumer
