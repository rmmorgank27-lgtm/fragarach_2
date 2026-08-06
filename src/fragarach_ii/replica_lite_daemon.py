"""Per-user LaunchAgent lifecycle for Fragarach Lite on the MacBook."""

from __future__ import annotations

import os
import plistlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .replica_lite import FragarachLiteError, LitePaths, _read_json
from .replica_lite_service import DEFAULT_LITE_PORT


SERVICE_LABEL = "com.raymorgan.fragarach-lite"
SERVICE_CONTRACT = "fragarach_lite.lifecycle.v1"


@dataclass(frozen=True, slots=True)
class LiteLifecyclePaths:
    lite: LitePaths
    launch_agent: Path
    stdout_log: Path
    stderr_log: Path

    @classmethod
    def create(cls, lite: LitePaths, *, home: str | Path | None = None) -> "LiteLifecyclePaths":
        user_home = Path(home).expanduser().resolve() if home else Path.home()
        return cls(
            lite=lite,
            launch_agent=user_home / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist",
            stdout_log=lite.root / "service.log",
            stderr_log=lite.root / "service-error.log",
        )


def launch_agent_definition(
    paths: LiteLifecyclePaths,
    *,
    python: str | Path,
    repository: str | Path,
    port: int = DEFAULT_LITE_PORT,
    sync_interval: int = 300,
    allow_unsigned: bool = False,
) -> dict[str, Any]:
    arguments = [
        str(Path(python).expanduser().resolve()), "-m", "fragarach_ii.commands.fragarach_lite",
        "--root", str(paths.lite.root), "serve", "--host", "127.0.0.1", "--port", str(port),
        "--sync-interval", str(sync_interval),
    ]
    if allow_unsigned:
        arguments.append("--allow-unsigned")
    return {
        "Label": SERVICE_LABEL,
        "ProgramArguments": arguments,
        "EnvironmentVariables": {"PYTHONPATH": str(Path(repository).expanduser().resolve() / "src")},
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ProcessType": "Background",
        "StandardOutPath": str(paths.stdout_log),
        "StandardErrorPath": str(paths.stderr_log),
        "ThrottleInterval": 5,
    }


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _service() -> str:
    return f"{_domain()}/{SERVICE_LABEL}"


def _launchctl(*arguments: str, accepted: frozenset[int] = frozenset({0})) -> None:
    result = subprocess.run(["/bin/launchctl", *arguments], text=True, capture_output=True, timeout=15)
    if result.returncode not in accepted:
        raise FragarachLiteError(
            "LITE_LAUNCHCTL_FAILED", (result.stderr or result.stdout).strip() or "launchctl failed"
        )


def _write_plist(path: Path, definition: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            plistlib.dump(definition, stream, fmt=plistlib.FMT_XML, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        Path(temporary).unlink(missing_ok=True)


def install_lite_service(paths: LiteLifecyclePaths, **definition_options: Any) -> dict[str, Any]:
    paths.lite.prepare()
    paths.stdout_log.touch(mode=0o600, exist_ok=True)
    paths.stderr_log.touch(mode=0o600, exist_ok=True)
    _write_plist(paths.launch_agent, launch_agent_definition(paths, **definition_options))
    _launchctl("bootout", _service(), accepted=frozenset({0, 3, 113}))
    _launchctl("bootstrap", _domain(), str(paths.launch_agent))
    _launchctl("enable", _service())
    _launchctl("kickstart", "-k", _service())
    return lite_service_status(paths)


def start_lite_service(paths: LiteLifecyclePaths) -> dict[str, Any]:
    if not paths.launch_agent.is_file():
        raise FragarachLiteError("LITE_NOT_INSTALLED", str(paths.launch_agent))
    _launchctl("bootstrap", _domain(), str(paths.launch_agent), accepted=frozenset({0, 5}))
    _launchctl("enable", _service())
    _launchctl("kickstart", "-k", _service())
    return lite_service_status(paths)


def stop_lite_service(paths: LiteLifecyclePaths) -> dict[str, Any]:
    _launchctl("bootout", _service(), accepted=frozenset({0, 3, 113}))
    return lite_service_status(paths)


def uninstall_lite_service(paths: LiteLifecyclePaths) -> dict[str, Any]:
    _launchctl("bootout", _service(), accepted=frozenset({0, 3, 113}))
    paths.launch_agent.unlink(missing_ok=True)
    return lite_service_status(paths)


def lite_service_status(paths: LiteLifecyclePaths) -> dict[str, Any]:
    observed = _read_json(paths.lite.service_status, {})
    pid = observed.get("pid") if isinstance(observed, dict) else None
    running = False
    if isinstance(pid, int) and pid > 0 and observed.get("state") == "RUNNING":
        try:
            os.kill(pid, 0)
            running = True
        except OSError:
            pass
    installed = paths.launch_agent.is_file()
    return {
        "contract": SERVICE_CONTRACT,
        "state": "RUNNING" if running else "STOPPED" if installed else "NOT_INSTALLED",
        "installed": installed,
        "running": running,
        "host": observed.get("host", "127.0.0.1") if isinstance(observed, dict) else "127.0.0.1",
        "port": observed.get("port", DEFAULT_LITE_PORT) if isinstance(observed, dict) else DEFAULT_LITE_PORT,
        "pid": pid if running else None,
        "last_sync_at_utc": observed.get("last_sync_at_utc") if isinstance(observed, dict) else None,
        "last_sync_outcome": observed.get("last_sync_outcome") if isinstance(observed, dict) else None,
        "last_sync_error": observed.get("last_sync_error") if isinstance(observed, dict) else None,
        "launch_agent": str(paths.launch_agent),
    }
