"""Independent user LaunchAgent lifecycle for the read-only publisher."""

from __future__ import annotations

import os
import plistlib
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .replica_publication import DEFAULT_PUBLISHER_PORT, ReplicaControlError, ReplicaPaths, _read_json


SERVICE_LABEL = "com.raymorgan.fragarach-ii.replica-publisher"
SERVICE_CONTRACT = "fragarach_ii.replica_publisher_lifecycle.v1"


@dataclass(frozen=True, slots=True)
class PublisherLifecyclePaths:
    replica: ReplicaPaths
    launch_agent: Path
    stdout_log: Path
    stderr_log: Path

    @classmethod
    def create(
        cls,
        replica: ReplicaPaths,
        *,
        home: str | Path | None = None,
    ) -> "PublisherLifecyclePaths":
        user_home = Path(home).expanduser().resolve() if home else Path.home()
        return cls(
            replica=replica,
            launch_agent=user_home / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist",
            stdout_log=replica.support / "publisher.log",
            stderr_log=replica.support / "publisher-error.log",
        )


def launch_agent_definition(
    paths: PublisherLifecyclePaths,
    *,
    python: str | Path,
    repository: str | Path,
    port: int = DEFAULT_PUBLISHER_PORT,
) -> dict[str, Any]:
    executable = Path(python).expanduser().resolve()
    repo = Path(repository).expanduser().resolve()
    return {
        "Label": SERVICE_LABEL,
        "ProgramArguments": [
            str(executable),
            "-m",
            "fragarach_ii.commands.replica_publisher",
            "--database",
            str(paths.replica.database),
            "--support",
            str(paths.replica.support),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        "EnvironmentVariables": {"PYTHONPATH": str(repo / "src")},
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


def _launchctl(*arguments: str, accepted: frozenset[int] = frozenset({0})) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["/bin/launchctl", *arguments],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    if result.returncode not in accepted:
        detail = (result.stderr or result.stdout).strip()
        raise ReplicaControlError("PUBLISHER_LAUNCHCTL_FAILED", detail or "launchctl failed")
    return result


def _atomic_plist(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            plistlib.dump(value, stream, fmt=plistlib.FMT_XML, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def install_publisher_service(
    paths: PublisherLifecyclePaths,
    *,
    python: str | Path,
    repository: str | Path,
    port: int = DEFAULT_PUBLISHER_PORT,
) -> dict[str, Any]:
    paths.replica.prepare()
    paths.stdout_log.touch(mode=0o600, exist_ok=True)
    paths.stderr_log.touch(mode=0o600, exist_ok=True)
    definition = launch_agent_definition(paths, python=python, repository=repository, port=port)
    _atomic_plist(paths.launch_agent, definition)
    _launchctl("bootout", _service(), accepted=frozenset({0, 3, 113}))
    _launchctl("bootstrap", _domain(), str(paths.launch_agent))
    _launchctl("enable", _service())
    _launchctl("kickstart", "-k", _service())
    _wait_for_running(paths)
    return publisher_service_status(paths)


def start_publisher_service(paths: PublisherLifecyclePaths) -> dict[str, Any]:
    if not paths.launch_agent.is_file():
        raise ReplicaControlError("PUBLISHER_NOT_INSTALLED", str(paths.launch_agent))
    _launchctl("bootstrap", _domain(), str(paths.launch_agent), accepted=frozenset({0, 5}))
    _launchctl("enable", _service())
    _launchctl("kickstart", "-k", _service())
    _wait_for_running(paths)
    return publisher_service_status(paths)


def stop_publisher_service(paths: PublisherLifecyclePaths) -> dict[str, Any]:
    _launchctl("bootout", _service(), accepted=frozenset({0, 3, 113}))
    return publisher_service_status(paths)


def uninstall_publisher_service(paths: PublisherLifecyclePaths) -> dict[str, Any]:
    _launchctl("bootout", _service(), accepted=frozenset({0, 3, 113}))
    paths.launch_agent.unlink(missing_ok=True)
    return publisher_service_status(paths)


def _pid_live(pid: object) -> bool:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid < 1:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _wait_for_running(paths: PublisherLifecyclePaths, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if publisher_service_status(paths)["running"]:
            return
        time.sleep(0.05)


def publisher_service_status(paths: PublisherLifecyclePaths) -> dict[str, Any]:
    observed = _read_json(paths.replica.service_status, {})
    if not isinstance(observed, dict):
        observed = {}
    running = _pid_live(observed.get("pid")) and observed.get("state") == "RUNNING"
    installed = paths.launch_agent.is_file()
    return {
        "contract": SERVICE_CONTRACT,
        "state": "RUNNING" if running else "STOPPED" if installed else "NOT_INSTALLED",
        "installed": installed,
        "running": running,
        "host": observed.get("host") or "127.0.0.1",
        "port": observed.get("port") or DEFAULT_PUBLISHER_PORT,
        "pid": observed.get("pid") if running else None,
        "started_at_utc": observed.get("started_at_utc") if running else None,
        "launch_agent": str(paths.launch_agent),
        "stdout_log": str(paths.stdout_log),
        "stderr_log": str(paths.stderr_log),
    }
