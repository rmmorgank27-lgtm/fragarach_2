from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.lane_commissioning import commissioned_lane_keys
from fragarach_ii.oil_history import bootstrap_tradingview_oil_history
from fragarach_ii.storage import initialize_database, open_read_only


NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def _write(path: Path, close: str) -> None:
    path.write_text(
        "time,open,high,low,close\n"
        f"1/9/2026,90,92,89,{close}\n"
        "2/9/2026,91,93,90,92\n"
        "3/9/2026,92,94,91,93\n",
        encoding="utf-8",
    )


def test_reviewed_tvc_bootstrap_registers_distinct_manual_only_oil_lanes(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    usoil = tmp_path / "TVC_USOIL, 1D_test.csv"
    ukoil = tmp_path / "TVC_UKOIL, 1D_test.csv"
    _write(usoil, "91")
    _write(ukoil, "91.5")

    result = bootstrap_tradingview_oil_history(
        database,
        usoil_file=usoil,
        ukoil_file=ukoil,
        clock=lambda: NOW,
    )

    assert result["provider"] == "TRADINGVIEW_TVC"
    assert result["scheduler_commissioning"] == "NOT_COMMISSIONED"
    assert result["results"]["USOIL"]["inserted"] == 2
    assert result["results"]["UKOIL"]["inserted"] == 2
    assert result["results"]["USOIL"]["rejected"] == 1
    with open_read_only(database) as connection:
        registrations = connection.execute(
            """SELECT asset,underlying_reference FROM instrument_registrations
               WHERE asset IN ('USOIL','UKOIL') ORDER BY asset"""
        ).fetchall()
        assert registrations == [
            ("UKOIL", "COMMODITY:BRENT"),
            ("USOIL", "COMMODITY:WTI"),
        ]
        assert ("USOIL", "D1") not in commissioned_lane_keys(connection)
        assert ("UKOIL", "D1") not in commissioned_lane_keys(connection)
        details = [
            json.loads(row[0])
            for row in connection.execute("SELECT detail FROM ingest_runs ORDER BY ingest_run_id")
        ]
        assert {item["provider"] for item in details} == {"TRADINGVIEW_TVC"}
