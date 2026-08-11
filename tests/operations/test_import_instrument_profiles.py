from __future__ import annotations

import json
from pathlib import Path

from fragarach_ii.commands.import_instrument_profiles import main
from fragarach_ii.storage import instrument_profile
from tests.validation.test_d1_session_validation import _create_lane


def test_reviewed_catalogue_covers_registered_crypto_funds_and_index() -> None:
    payload = json.loads(Path("config/instrument_profiles/events.v1.json").read_text())
    origins = [event for event in payload["events"] if event["is_primary_origin"]]
    symbols = {event["asset"] for event in origins}

    assert len(symbols) == len(origins)
    assert {
        "ADAUSD", "AVAXUSD", "BNBUSD", "BTCUSD", "DOGEUSD", "DOTUSD", "ETHUSD",
        "HYPEUSD", "LINKUSD", "PEPEUSD", "SOLUSD", "SUIUSD", "XRPUSD",
        "QQQ", "SPY", "USO", "DJI",
    } <= symbols


def test_reviewed_catalogue_imports_one_symbol_idempotently(
    tmp_path: Path, capsys: object
) -> None:
    database = tmp_path / "authority.sqlite3"
    _create_lane(database, "BTCUSD", ["2026-07-09"])
    catalogue = Path("config/instrument_profiles/events.v1.json").resolve()
    arguments = [
        "--database", str(database), "--catalogue", str(catalogue), "--symbol", "BTCUSD",
    ]

    assert main(arguments) == 0
    first = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert first["imported"] == 1
    assert first["events"][0]["outcome"] == "RECORDED"
    assert main(arguments) == 0
    repeated = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert repeated["events"][0]["outcome"] == "ALREADY_RECORDED"
    assert instrument_profile(database, "BTCUSD")["origin_status"] == "VERIFIED"
