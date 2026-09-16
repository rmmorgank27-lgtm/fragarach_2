from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fragarach_ii.energy_mt5 import (
    INSTRUMENTS, admit_energy_mt5, daily_rollup, fixed_rollup, read_mt5_m5,
)
from fragarach_ii.lane_update_register import LaneUpdateRegister
from fragarach_ii.oil_history import bootstrap_tradingview_oil_history
from fragarach_ii.provider_facts import load_provider_facts
from fragarach_ii.storage import initialize_database, open_read_only


def _write_session(path: Path, start_hour: int, count: int) -> None:
    lines = ["time_utc,open,high,low,close,tick_volume,spread,real_volume"]
    start = datetime(2026, 9, 1, start_hour, tzinfo=UTC)
    for index in range(count):
        stamp = start + timedelta(minutes=5 * index)
        value = 80 + index / 1000
        lines.append(f"{stamp.isoformat()},{value},{value + 1},{value - 1},{value + .5},1,2,0")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_xtiusd_rollups_require_complete_components_and_complete_session(tmp_path: Path) -> None:
    path = tmp_path / "XTIUSD_M5_test.csv"
    _write_session(path, 1, 276)
    _, bars = read_mt5_m5(path, instrument=INSTRUMENTS["USOIL"])
    assert len(fixed_rollup(bars, "M15")) == 92
    assert len(fixed_rollup(bars, "M30")) == 46
    assert len(fixed_rollup(bars, "H1")) == 23
    daily = daily_rollup(bars, instrument=INSTRUMENTS["USOIL"])
    assert len(daily) == 1
    assert daily[0].timestamp == datetime(2026, 9, 1, tzinfo=UTC)
    assert daily[0].open == bars[0].open
    assert daily[0].close == bars[-1].close


def test_xbrusd_partial_session_is_not_published_as_d1(tmp_path: Path) -> None:
    path = tmp_path / "XBRUSD_M5_test.csv"
    _write_session(path, 3, 251)
    _, bars = read_mt5_m5(path, instrument=INSTRUMENTS["UKOIL"])
    assert daily_rollup(bars, instrument=INSTRUMENTS["UKOIL"]) == ()


def test_file_identity_must_match_exact_mt5_symbol(tmp_path: Path) -> None:
    path = tmp_path / "WTIUSD_M5_test.csv"
    _write_session(path, 1, 276)
    try:
        read_mt5_m5(path, instrument=INSTRUMENTS["USOIL"])
    except ValueError as error:
        assert "MT5_SYMBOL_FILE_MISMATCH" in str(error)
    else:
        raise AssertionError("wrong MT5 symbol spelling was accepted")


def test_admission_makes_mt5_primary_and_records_twelve_data_fallback(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    usoil_d1 = tmp_path / "TVC_USOIL, 1D_test.csv"
    ukoil_d1 = tmp_path / "TVC_UKOIL, 1D_test.csv"
    history = "time,open,high,low,close\n1/9/2026,79,82,78,80\n"
    usoil_d1.write_text(history, encoding="utf-8")
    ukoil_d1.write_text(history, encoding="utf-8")
    observed = datetime(2026, 9, 2, 12, tzinfo=UTC)
    bootstrap_tradingview_oil_history(
        database, usoil_file=usoil_d1, ukoil_file=ukoil_d1,
        clock=lambda: observed,
    )
    xti = tmp_path / "XTIUSD_M5_test.csv"
    xbr = tmp_path / "XBRUSD_M5_test.csv"
    _write_session(xti, 1, 276)
    _write_session(xbr, 3, 252)
    registry = tmp_path / "synthetic_registry.json"
    registry_payload = json.loads(Path("config/synthetic/synthetic_registry.v1.json").read_text())
    registry_payload["registrations"] = []
    registry.write_text(json.dumps(registry_payload), encoding="utf-8")
    monkeypatch.setattr("fragarach_ii.synthetic_repository.CONFIG_PATH", registry)

    result = admit_energy_mt5(
        database, usoil_file=xti, ukoil_file=xbr, observed_at=observed,
    )

    assert result["primary_provider"] == "GLOBAL_PRIME_MT5"
    assert result["fallback_provider"] == "TWELVE_DATA"
    assert result["results"]["USOIL"]["complete_d1"] == 1
    assert result["results"]["UKOIL"]["complete_d1"] == 1
    assert result["results"]["UKOIL"]["complete_m30"] == 42
    mappings = load_provider_facts(database)["mappings"]
    for symbol in ("USOIL", "UKOIL"):
        assert set(mappings[f"TWELVE_DATA:{symbol}"]["timeframe_capabilities"]) == {"D1", "H1", "M30", "M5"}
        assert set(mappings[f"TWELVE_DATA:{symbol}"]["supported_intervals"]) == {"1day", "1h", "30min", "5min"}
    with LaneUpdateRegister(database)._connection() as register:
        indexed = {
            (row[0], row[1])
            for row in register.execute(
                "SELECT asset,timeframe FROM lane_update_register WHERE asset IN ('USOIL','UKOIL')"
            )
        }
    assert indexed == {
        ("USOIL", "D1"), ("USOIL", "H1"), ("USOIL", "M30"), ("USOIL", "M5"),
        ("UKOIL", "D1"), ("UKOIL", "H1"), ("UKOIL", "M30"), ("UKOIL", "M5"),
    }
    with open_read_only(database) as connection:
        providers = {
            (row[0], row[1]): row[2]
            for row in connection.execute(
                """SELECT b.asset,b.timeframe,json_extract(i.detail,'$.provider')
                     FROM bars b JOIN ingest_runs i
                       ON i.ingest_run_id=b.updated_by_ingest_run_id
                    WHERE b.asset IN ('USOIL','UKOIL')
                      AND b.timeframe IN ('M5','H1','D1')
                      AND b.open_time_utc=unixepoch('2026-09-01')
                         OR (b.asset IN ('USOIL','UKOIL') AND b.timeframe IN ('M5','H1')
                             AND date(b.open_time_utc,'unixepoch')='2026-09-01')"""
            ).fetchall()
        }
        assert providers[("USOIL", "D1")] == "GLOBAL_PRIME_MT5"
        assert providers[("UKOIL", "D1")] == "GLOBAL_PRIME_MT5"
