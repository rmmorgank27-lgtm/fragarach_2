"""LaunchAgent lifecycle for the governed MT5 broker-family index-CFD importer."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import time
from typing import Any

from .external_consumer_service import canonical_database_path


SERVICE_LABEL = "com.raymorgan.fragarach-ii.mt5-broker-family-index-cfd-importer"
SERVICE_CONTRACT = "fragarach_ii.mt5_broker_family_index_cfd_service.v2"


def default_paths(*, home: str | Path | None = None) -> dict[str, Path]:
    user_home = Path(home).expanduser().resolve() if home else Path.home()
    runtime = Path(__file__).resolve().parents[2] / "data" / "runtime"
    return {
        "database": canonical_database_path(),
        "receiver_root": user_home / "Library/Application Support/Datagather/MT5Receiver",
        "state": runtime / "mt5-broker-family-index-cfd-importer.json",
        "stdout": runtime / "mt5-broker-family-index-cfd-importer.log",
        "stderr": runtime / "mt5-broker-family-index-cfd-importer-error.log",
        "launch_agent": user_home / "Library/LaunchAgents" / f"{SERVICE_LABEL}.plist",
    }


def launch_agent_definition(
    *, repository: str | Path, python: str | Path, paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    selected = paths or default_paths()
    repo = Path(repository).expanduser().resolve()
    executable = Path(python).expanduser().resolve()
    user = os.environ.get("USER", "raymorgan")
    return {
        "Label": SERVICE_LABEL,
        "ProgramArguments": [
            str(executable), "-m", "fragarach_ii.index_cfd_mt5",
            "--database", str(selected["database"]),
            "--receiver-root", str(selected["receiver_root"]),
            "--state", str(selected["state"]),
            "--watch", "--poll-seconds", "20",
        ],
        "EnvironmentVariables": {
            "PYTHONPATH": str(repo / "src"),
            "HOME": str(Path.home()),
            "USER": user,
            "LOGNAME": os.environ.get("LOGNAME", user),
            "__CF_USER_TEXT_ENCODING": os.environ.get(
                "__CF_USER_TEXT_ENCODING", f"0x{os.getuid():X}:0:0"
            ),
        },
        "WorkingDirectory": str(repo),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(selected["stdout"]),
        "StandardErrorPath": str(selected["stderr"]),
        "ThrottleInterval": 10,
    }


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _service() -> str:
    return f"{_domain()}/{SERVICE_LABEL}"


def _launchctl(*arguments: str, accepted: frozenset[int] = frozenset({0})) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["/bin/launchctl", *arguments], text=True, capture_output=True,
        check=False, timeout=15,
    )
    if result.returncode not in accepted:
        raise RuntimeError((result.stderr or result.stdout).strip() or "launchctl failed")
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


def service_status(paths: dict[str, Path] | None = None) -> dict[str, Any]:
    selected = paths or default_paths()
    probe = _launchctl("print", _service(), accepted=frozenset({0, 113}))
    state: dict[str, Any] = {}
    try:
        loaded = json.loads(selected["state"].read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            state = loaded
    except (OSError, json.JSONDecodeError):
        pass
    running = probe.returncode == 0 and "state = running" in probe.stdout
    return {
        "contract": SERVICE_CONTRACT,
        "status": "RUNNING" if running else "STOPPED",
        "installed": selected["launch_agent"].is_file(),
        "running": running,
        "launch_agent": str(selected["launch_agent"]),
        "importer": state,
    }


def install_service(
    *, repository: str | Path, python: str | Path, paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    selected = paths or default_paths()
    selected["state"].parent.mkdir(parents=True, exist_ok=True)
    selected["stdout"].touch(mode=0o600, exist_ok=True)
    selected["stderr"].touch(mode=0o600, exist_ok=True)
    _atomic_plist(
        selected["launch_agent"],
        launch_agent_definition(repository=repository, python=python, paths=selected),
    )
    _launchctl("bootout", _service(), accepted=frozenset({0, 3, 113}))
    time.sleep(0.25)
    try:
        _launchctl("bootstrap", _domain(), str(selected["launch_agent"]))
    except RuntimeError:
        # launchd can briefly retain the prior job after bootout even though
        # print already reports it absent. One bounded retry handles that race.
        time.sleep(0.75)
        _launchctl("bootstrap", _domain(), str(selected["launch_agent"]))
    _launchctl("enable", _service())
    _launchctl("kickstart", "-k", _service())
    deadline = time.monotonic() + 5
    result = service_status(selected)
    while not result["running"] and time.monotonic() < deadline:
        time.sleep(0.1)
        result = service_status(selected)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "status", "start", "stop", "uninstall"))
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--python", type=Path, default=Path("/opt/homebrew/bin/python3"))
    args = parser.parse_args(argv)
    paths = default_paths()
    if args.action == "install":
        result = install_service(repository=args.repository, python=args.python, paths=paths)
    elif args.action == "start":
        _launchctl("bootstrap", _domain(), str(paths["launch_agent"]), accepted=frozenset({0, 5}))
        _launchctl("enable", _service())
        _launchctl("kickstart", "-k", _service())
        result = service_status(paths)
    elif args.action == "stop":
        _launchctl("bootout", _service(), accepted=frozenset({0, 3, 113}))
        result = service_status(paths)
    elif args.action == "uninstall":
        _launchctl("bootout", _service(), accepted=frozenset({0, 3, 113}))
        paths["launch_agent"].unlink(missing_ok=True)
        result = service_status(paths)
    else:
        result = service_status(paths)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
