from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fragarach_ii.external_consumer_service import HistoryService
from fragarach_ii.stock_cfd_mt5 import (
    CANONICAL_TIMESTAMP_POLICY,
    SOURCE_TIMESTAMP_STATUS,
    admit_xom_stock_cfd_overlay,
    broker_stock_cfd_intraday_enabled,
)
from fragarach_ii.storage import RegistrationCandidate, initialize_database, open_read_only, register_instrument


def _xom_registration(database: Path) -> None:
    register_instrument(
        database,
        RegistrationCandidate(
            asset="XOM", timeframe="D1", instrument_family="XOM", local_symbol="XOM",
            display_name="Exxon Mobil Corporation", instrument_type="COMMON_STOCK",
            asset_class="US_EQUITIES", representation_type="COMMON_STOCK",
            trading_currency="USD", exchange_name="NYSE", provider_id=None,
            provider_contract=None, provider_symbol=None, provider_instrument_type=None,
            calendar_id="US_EQUITIES_D1_V1", calendar_version=1,
            gap_doctrine_id="FRAGARACH_II_D1_GAP_DOCTRINE_V1", gap_doctrine_version=1,
        ),
        registered_at_utc="2026-03-01T00:00:00+00:00",
    )


def _write_native(path: Path, timeframe: str) -> None:
    step = 5 if timeframe == "M5" else 15
    count = 18 if timeframe == "M5" else 6
    rows: list[list[object]] = []
    for owner_day in (datetime(2026, 3, 6, 16, 30, tzinfo=UTC), datetime(2026, 3, 9, 16, 30, tzinfo=UTC)):
        m5 = []
        for index in range(18):
            opened = owner_day + timedelta(minutes=5 * index)
            value = 100 + index / 10
            m5.append((opened, value, value + .2, value - .2, value + .1, 10))
        source = m5 if timeframe == "M5" else [
            (group[0][0], group[0][1], max(item[2] for item in group),
             min(item[3] for item in group), group[-1][4], sum(item[5] for item in group))
            for group in (m5[index:index + 3] for index in range(0, len(m5), 3))
        ]
        assert len(source) == count
        for opened, o, h, l, c, volume in source:
            rows.append([
                int(opened.timestamp()), opened.isoformat(timespec="seconds").replace("+00:00", "Z"),
                o, h, l, c, volume, 2, 0,
            ])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("mt5_time", "mt5_documented_utc_rendering", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"))
        writer.writerows(rows)


def _bundle(root: Path) -> None:
    data = root / "data" / "history_730d"
    data.mkdir(parents=True)
    artifacts = []
    for timeframe in ("M5", "M15"):
        path = data / f"ExxonMobil_{timeframe}.csv"
        _write_native(path, timeframe)
        artifacts.append({
            "file": str(path.relative_to(root)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    (root / "manifest.json").write_text(json.dumps({
        "contract": "global_prime.mt5.echo_short.phase2.v1",
        "artifacts": artifacts,
        "instruments": {"XOM": {"exact_terminal_symbol": "ExxonMobil"}},
        "source_semantics": {"representation": "STOCK_CFD"},
    }), encoding="utf-8")


def test_xom_overlay_preserves_d1_identity_and_admits_native_and_rollup_lanes(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    _xom_registration(database)
    bundle = tmp_path / "bundle"
    _bundle(bundle)

    result = admit_xom_stock_cfd_overlay(
        database, bundle, observed_at=datetime(2026, 3, 10, tzinfo=UTC),
    )

    assert result["source_timestamp_status"] == SOURCE_TIMESTAMP_STATUS
    assert result["canonical_timestamp_policy"] == CANONICAL_TIMESTAMP_POLICY
    assert result["rows"] == {"M5": 36, "M15": 12, "M30": 6, "H1": 2}
    with open_read_only(database) as connection:
        registration = connection.execute(
            "SELECT asset_class,representation_type,exchange_name FROM instrument_registrations WHERE asset='XOM'"
        ).fetchone()
        counts = dict(connection.execute(
            "SELECT timeframe,count(*) FROM bars WHERE asset='XOM' GROUP BY timeframe"
        ).fetchall())
    assert tuple(registration) == ("US_EQUITIES", "COMMON_STOCK", "NYSE")
    assert counts == {"H1": 2, "M15": 12, "M30": 6, "M5": 36}
    assert broker_stock_cfd_intraday_enabled(database, "XOM", "M30") is True
    assert HistoryService(database).get_history("XOM", "M30")["status"] == "AVAILABLE"
