"""Canonical provider credential authority.

Runtime consumers import this module; they do not inspect environments, files,
or Keychain locations themselves.  Credential material is never included in a
public authority projection.
"""

from __future__ import annotations

import hashlib
import json
from urllib.parse import urlencode
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Protocol


AUTHORITY_CONTRACT = "fragarach_ii.credential_authority.v1"
KEYCHAIN_SERVICE = "com.raymorgan.fragarach-ii.operations"
METADATA_PATH = Path("~/Library/Application Support/Fragarach II/credential-authority.json").expanduser()
LEGACY_TWELVE_DATA_PATH = Path("/Users/raymorgan/VSC/Morphix_Data_Hot/runtime_state/secrets/local.env")


class CredentialState(str, Enum):
    AVAILABLE = "Available"
    MISSING = "Missing"
    INVALID = "Invalid"
    EXPIRED = "Expired"
    UNAVAILABLE = "Unavailable"
    UNKNOWN = "Unknown"


PROVIDERS: dict[str, dict[str, object]] = {
    "TWELVE_DATA": {"account": "TWELVE_DATA_API_KEY", "required": True},
    "YAHOO_FINANCE": {"account": "YAHOO_API_KEY", "required": False},
    "BINANCE": {"account": "BINANCE_API_KEY", "required": False},
    "COINGECKO": {"account": "COINGECKO_API_KEY", "required": False},
}


class SecureCredentialStore(Protocol):
    def read(self, account: str) -> str | None: ...
    def write(self, account: str, credential: str) -> None: ...


class MacOSKeychainStore:
    """The one canonical secure store behind the authority boundary."""

    def read(self, account: str) -> str | None:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
            check=False, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 44:
            return None
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or "Keychain lookup failed")
        value = result.stdout.strip()
        return value or None

    def write(self, account: str, credential: str) -> None:
        result = subprocess.run(
            [
                "/usr/bin/security", "add-generic-password", "-U",
                "-s", KEYCHAIN_SERVICE, "-a", account, "-w", credential,
            ],
            check=False, capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or "Keychain update failed")


@dataclass(frozen=True, slots=True)
class CredentialResolution:
    provider: str
    state: CredentialState
    authority_revision: str
    last_validation: str | None
    validation_source: str
    credential: str | None = None

    def public_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "credential_state": self.state.value,
            "authority_revision": self.authority_revision,
            "last_validation": self.last_validation,
            "validation_source": self.validation_source,
        }


class CredentialAuthority:
    def __init__(
        self,
        *,
        store: SecureCredentialStore | None = None,
        metadata_path: str | Path | None = None,
        clock=None,
    ) -> None:
        self.store = store or MacOSKeychainStore()
        self.metadata_path = Path(metadata_path).expanduser() if metadata_path else METADATA_PATH
        self.clock = clock or (lambda: datetime.now(UTC))

    def resolve(self, provider: str) -> CredentialResolution:
        provider_id = provider.strip().upper()
        definition = PROVIDERS.get(provider_id)
        if definition is None:
            return self._resolution(provider_id, CredentialState.UNKNOWN, None, {})
        if not bool(definition["required"]):
            return self._resolution(
                provider_id, CredentialState.AVAILABLE, None,
                {"validation_source": "Credential not required"},
            )
        try:
            credential = self.store.read(str(definition["account"]))
        except (OSError, subprocess.SubprocessError):
            return self._resolution(
                provider_id, CredentialState.UNAVAILABLE, None,
                {"validation_source": "Credential Authority secure storage"},
            )
        if not credential:
            return self._resolution(
                provider_id, CredentialState.MISSING, None,
                {"validation_source": "Credential Authority secure storage"},
            )
        metadata = self._metadata().get("providers", {}).get(provider_id, {})
        fingerprint = _fingerprint(credential)
        state = CredentialState.AVAILABLE
        if isinstance(metadata, dict) and metadata.get("credential_fingerprint") == fingerprint:
            try:
                state = CredentialState(str(metadata.get("credential_state", CredentialState.AVAILABLE.value)))
            except ValueError:
                state = CredentialState.UNKNOWN
        return self._resolution(provider_id, state, credential, metadata if isinstance(metadata, dict) else {})

    def credential_for(self, provider: str) -> str | None:
        resolution = self.resolve(provider)
        return resolution.credential

    def snapshot(self) -> dict[str, object]:
        rows = [self.resolve(provider).public_dict() for provider in PROVIDERS]
        revision = hashlib.sha256(
            json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "contract": AUTHORITY_CONTRACT,
            "generated_at": self.clock().astimezone(UTC).isoformat(),
            "authority_revision": revision,
            "providers": rows,
        }

    def store_credential(self, provider: str, credential: str) -> CredentialResolution:
        provider_id = provider.strip().upper()
        definition = PROVIDERS.get(provider_id)
        value = credential.strip()
        if definition is None:
            raise ValueError(f"unsupported provider: {provider_id}")
        if not value:
            raise ValueError("credential is empty")
        self.store.write(str(definition["account"]), value)
        self.record_validation(
            provider_id,
            credential_state=CredentialState.AVAILABLE,
            validation_source="Credential Authority secure storage update",
        )
        return self.resolve(provider_id)

    def record_validation(
        self,
        provider: str,
        *,
        credential_state: CredentialState,
        validation_source: str,
        provider_response_state: str | None = None,
        provider_response_code: int | None = None,
    ) -> CredentialResolution:
        provider_id = provider.strip().upper()
        definition = PROVIDERS.get(provider_id)
        if definition is None:
            raise ValueError(f"unsupported provider: {provider_id}")
        try:
            credential = self.store.read(str(definition["account"]))
        except (OSError, subprocess.SubprocessError):
            credential = None
        document = self._metadata()
        providers = document.setdefault("providers", {})
        providers[provider_id] = {
            "credential_state": credential_state.value,
            "credential_fingerprint": _fingerprint(credential) if credential else None,
            "last_validation": self.clock().astimezone(UTC).isoformat(),
            "validation_source": validation_source,
            "provider_response_state": provider_response_state,
            "provider_response_code": provider_response_code,
        }
        self._write_metadata(document)
        return self.resolve(provider_id)

    def validate(self, provider: str) -> dict[str, object]:
        """Perform one read-only provider probe and retain local/remote separation."""
        provider_id = provider.strip().upper()
        resolution = self.resolve(provider_id)
        if provider_id != "TWELVE_DATA":
            return {**resolution.public_dict(), "provider_response_state": "Validation Not Required", "http_status": None}
        if not resolution.credential:
            return {**resolution.public_dict(), "provider_response_state": "Not Transmitted", "http_status": None}

        # Imports are local to keep the provider adapter free to depend on the
        # authority without creating a module initialization cycle.
        from .providers.config import load_provider_config
        from .providers.http import BoundedHttpsTransport, HttpRequest
        from .twelve_data_credit import credited_send

        config = load_provider_config(timeframe="D1")
        target = f"{config.endpoint_path}?{urlencode([('format','JSON'),('interval','1day'),('outputsize','1'),('symbol','AUD/USD')])}"
        try:
            transport = BoundedHttpsTransport()
            response = credited_send(
                resolution.credential, endpoint="credential_validation", clock=self.clock,
                send=lambda: transport.send(
                    HttpRequest(host=config.provider_host, target=target, user_agent=config.user_agent),
                    resolution.credential, config,
                ),
            )
        except OSError as error:
            return {
                **resolution.public_dict(), "provider_response_state": "Provider Unavailable",
                "http_status": None, "provider_code": None, "provider_message": str(error),
            }
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            payload = {}
        provider_code = payload.get("code") if isinstance(payload, dict) else None
        provider_message = payload.get("message") if isinstance(payload, dict) else None
        normalized = str(provider_message or "").lower()
        if response.status in {401, 403} or provider_code in {401, 403} or "api key" in normalized or "authentication" in normalized:
            local_state, remote_state = CredentialState.INVALID, "Authentication Failed"
        elif response.status == 429 or provider_code == 429 or "rate limit" in normalized:
            local_state, remote_state = CredentialState.AVAILABLE, "Rate Limited"
        elif "quota" in normalized or "credits" in normalized:
            local_state, remote_state = CredentialState.AVAILABLE, "Quota Exceeded"
        elif response.status >= 500:
            local_state, remote_state = CredentialState.AVAILABLE, "Provider Unavailable"
        elif response.status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
            local_state, remote_state = CredentialState.AVAILABLE, "Accepted"
        else:
            local_state, remote_state = CredentialState.AVAILABLE, "Other Provider Failure"
        updated = self.record_validation(
            provider_id, credential_state=local_state,
            validation_source="Credential Authority Twelve Data probe",
            provider_response_state=remote_state, provider_response_code=response.status,
        )
        return {
            **updated.public_dict(), "provider_response_state": remote_state,
            "http_status": response.status, "provider_code": provider_code,
            "provider_message": provider_message,
        }

    def migrate_legacy_twelve_data(self, path: str | Path = LEGACY_TWELVE_DATA_PATH) -> dict[str, object]:
        current = self.resolve("TWELVE_DATA")
        if current.state is CredentialState.AVAILABLE:
            return {"outcome": "ALREADY_CANONICAL", **current.public_dict()}
        value = _read_legacy_value(Path(path), {"TWELVEDATA_API_KEY", "TWELVE_DATA_API_KEY"})
        if not value:
            return {"outcome": "LEGACY_CREDENTIAL_NOT_FOUND", **current.public_dict()}
        migrated = self.store_credential("TWELVE_DATA", value)
        return {"outcome": "MIGRATED_TO_CANONICAL_AUTHORITY", **migrated.public_dict()}

    def _resolution(
        self,
        provider: str,
        state: CredentialState,
        credential: str | None,
        metadata: dict[str, object],
    ) -> CredentialResolution:
        fingerprint = _fingerprint(credential) if credential else "none"
        revision = hashlib.sha256(
            f"{AUTHORITY_CONTRACT}|{provider}|{state.value}|{fingerprint}".encode("utf-8")
        ).hexdigest()
        return CredentialResolution(
            provider=provider,
            state=state,
            authority_revision=revision,
            last_validation=metadata.get("last_validation") if isinstance(metadata.get("last_validation"), str) else None,
            validation_source=str(metadata.get("validation_source") or "Credential Authority secure storage"),
            credential=credential,
        )

    def _metadata(self) -> dict[str, object]:
        try:
            value = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"contract": AUTHORITY_CONTRACT, "providers": {}}
        except (OSError, ValueError):
            return {"contract": AUTHORITY_CONTRACT, "providers": {}}

    def _write_metadata(self, document: dict[str, object]) -> None:
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.metadata_path.with_suffix(f"{self.metadata_path.suffix}.tmp")
        temporary.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.metadata_path)


def resolve_scheduler_credential(**_ignored: object) -> tuple[str | None, str]:
    """Compatibility boundary; all service callers now use the authority."""

    resolution = CredentialAuthority().resolve("TWELVE_DATA")
    return resolution.credential, resolution.state.value


def _fingerprint(credential: str) -> str:
    return hashlib.sha256(credential.encode("utf-8")).hexdigest()


def _read_legacy_value(path: Path, names: set[str]) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw = stripped.split("=", 1)
        if key.strip() in names:
            value = raw.strip().strip("\"'")
            return value or None
    return None
