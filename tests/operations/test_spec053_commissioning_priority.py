from __future__ import annotations

import tempfile
from datetime import UTC,datetime
from pathlib import Path

from fragarach_ii.commissioning_authority import (
    OPERATIONAL_MARKET_ORDER,
    project_required_lanes,
    required_timeframes,
)
from fragarach_ii.estate_truth_service import estate_truth_state
from fragarach_ii.lane_commissioning import ensure_commissioned_lane
from fragarach_ii.scheduler_service import (
    _fair_bounded_selection,
    scheduler_snapshot,
)
from tests.validation.test_d1_session_validation import _create_lane


NOW=datetime(2026,7,15,0,0,tzinfo=UTC)


class Journal:
    def __init__(self):
        self.data={"fairness_cursor":0}


def work(symbol,asset_class,priority="BEHIND_COMMISSIONED",*,age=0,timeframe="D1",provider="TWELVE_DATA"):
    return {
        "symbol":symbol,"timeframe":timeframe,"asset_class":asset_class,
        "dispatch_priority":priority,"work_class":"QUEUE",
        "queue_age_seconds":age,"missed_boundaries":2,
        "expected_edge":NOW.isoformat(),"selected_provider":provider,
    }


def test_required_timeframes_are_generated_from_one_asset_class_authority() -> None:
    for asset_class in ("FX","METALS","ENERGY","INDICES","CRYPTO"):
        assert required_timeframes(asset_class) == ("D1","H1","M30","M5")
    assert required_timeframes("US_EQUITIES") == ("D1",)
    assert OPERATIONAL_MARKET_ORDER == ("FOREX","METALS","INDICES","ENERGY","CRYPTO","STOCKS")


def test_missing_commissions_are_first_class_and_no_required_cell_is_omitted() -> None:
    rows=project_required_lanes(
        [("AUDSGD","FX")],{("AUDSGD","D1")},
        evidence_counts={("AUDSGD","D1"):58},
        operational_states={("AUDSGD","D1"):"Current"},
        operational_lanes={("AUDSGD","D1")},
    )
    assert [row["timeframe"] for row in rows] == ["D1","H1","M30","M5"]
    assert [row["operational_state"] for row in rows] == [
        "Current","Not Commissioned","Not Commissioned","Not Commissioned"
    ]
    assert [row["timeframe"] for row in rows if row["missing_commission"]] == ["H1","M30","M5"]


def test_unenabled_lower_timeframes_are_visible_but_non_blocking() -> None:
    rows = project_required_lanes(
        [("SPY", "INDICES")], {("SPY", "D1")},
        evidence_counts={("SPY", "D1"): 10},
        operational_states={("SPY", "D1"): "Current"},
        operational_lanes={("SPY", "D1")},
        enabled_lanes={("SPY", "D1")},
    )
    deferred = [row for row in rows if row["timeframe"] != "D1"]
    assert all(row["commissioning_state"] == "NOT_ENABLED" for row in deferred)
    assert all(row["operational_state"] == "Not Enabled" for row in deferred)
    assert all(row["non_blocking"] and not row["missing_commission"] for row in deferred)


def test_estate_coverage_uses_commissioned_over_required_and_new_lane_is_visible() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database=Path(directory)/"authority.sqlite3"
        _create_lane(database,"AUDUSD",["2026-07-14"])
        initial=estate_truth_state(database,clock=lambda:NOW)
        summary=initial["estate_summary"]
        assert summary["required_lanes"] == 3
        assert summary["commissioned_lanes"] == 3
        assert summary["missing_commissions"] == 0
        assert initial["estate_summary"]["not_enabled_lanes"] == 9
        assert initial["estate_summary"]["operational_coverage_percent"] == 100
        ensure_commissioned_lane(database,"AUDUSD","H1",observed_at=NOW.isoformat())
        updated=estate_truth_state(database,clock=lambda:NOW)
        assert updated["estate_summary"]["commissioned_lanes"] == summary["commissioned_lanes"] + 1
        assert updated["estate_summary"]["required_lanes"] == 4
        assert updated["estate_summary"]["operational_coverage_percent"] == 100
        h1=next(row for row in updated["commissioning_matrix"] if row["id"] == "AUDUSD:H1")
        assert h1["operational_state"] == "Behind"
        assert not h1["missing_commission"]


def test_scheduler_exposes_missing_required_lanes_without_fabricating_them() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database=Path(directory)/"authority.sqlite3"
        _create_lane(database,"AUDUSD",["2026-07-14"])
        snapshot=scheduler_snapshot(database,clock=lambda:NOW,journal_path=Path(directory)/"scheduler.json")
        missing=[row for row in snapshot["missing_commissions"] if row["symbol"] == "AUDUSD"]
        assert [row["timeframe"] for row in missing] == ["H1","M30","M5"]
        assert all(row["commissioning_state"] == "MISSING_COMMISSION" for row in missing)


def test_operator_and_current_boundary_precede_forex_then_market_order() -> None:
    due=[
        work("STOCK","US_EQUITIES"),work("BTC","CRYPTO"),work("OIL","ENERGY"),
        work("INDEX","INDICES"),work("GOLD","METALS"),work("AUDUSD","FX"),
        work("BOUNDARY","US_EQUITIES","CURRENT_BOUNDARY"),
        work("OPERATOR","US_EQUITIES","OPERATOR_FETCH"),
        work("HISTORY","FX","HISTORICAL_CATCH_UP"),
    ]
    selected=_fair_bounded_selection(due,None,Journal())
    assert [row["symbol"] for row in selected] == ["BOUNDARY","OPERATOR","AUDUSD"]
    after_forex=_fair_bounded_selection(
        [row for row in due if row["symbol"] not in {"OPERATOR","BOUNDARY","AUDUSD"}],
        None,Journal(),
    )
    assert [row["symbol"] for row in after_forex] == ["GOLD"]


def test_aged_lower_priority_work_gets_bounded_starvation_relief() -> None:
    due=[
        work("AUDUSD","FX"),
        work("OLD-STOCK","US_EQUITIES","STARVATION_RELIEF",age=8*3600),
    ]
    assert _fair_bounded_selection(due,1,Journal())[0]["symbol"] == "OLD-STOCK"


def test_mixed_provider_queue_keeps_operational_order_provider_neutral() -> None:
    due=[
        work("GOLD","METALS",provider="YAHOO_FINANCE"),
        work("EURUSD","FX",provider="TWELVE_DATA"),
        work("BTCUSD","CRYPTO",provider="BINANCE"),
    ]
    selected=[]
    remaining=list(due)
    while remaining:
        cycle=_fair_bounded_selection(remaining,None,Journal())
        selected.extend(cycle)
        remaining=[row for row in remaining if row not in cycle]
    assert [(row["symbol"],row["selected_provider"]) for row in selected] == [
        ("EURUSD","TWELVE_DATA"),("GOLD","YAHOO_FINANCE"),("BTCUSD","BINANCE")
    ]
