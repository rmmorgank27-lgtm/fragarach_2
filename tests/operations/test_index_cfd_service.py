from __future__ import annotations

from pathlib import Path

from fragarach_ii.index_cfd_service import SERVICE_LABEL, launch_agent_definition


def test_launch_agent_is_persistent_and_uses_explicit_authority_paths(tmp_path: Path) -> None:
    paths = {
        "database": tmp_path / "authority.sqlite3",
        "receiver_root": tmp_path / "receiver",
        "state": tmp_path / "state.json",
        "stdout": tmp_path / "stdout.log",
        "stderr": tmp_path / "stderr.log",
        "launch_agent": tmp_path / f"{SERVICE_LABEL}.plist",
    }
    definition = launch_agent_definition(
        repository=tmp_path / "repo", python=tmp_path / "python3", paths=paths,
    )

    assert definition["Label"] == SERVICE_LABEL
    assert definition["RunAtLoad"] is True
    assert definition["KeepAlive"] is True
    assert definition["EnvironmentVariables"]["PYTHONPATH"] == str(tmp_path / "repo/src")
    arguments = definition["ProgramArguments"]
    assert arguments[1:3] == ["-m", "fragarach_ii.index_cfd_mt5"]
    assert "--watch" in arguments
    assert str(paths["database"]) in arguments
    assert str(paths["receiver_root"]) in arguments
