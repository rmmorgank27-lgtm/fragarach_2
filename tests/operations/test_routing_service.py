from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fragarach_ii.acquisition_orchestrator import (
    acquisition_plan,
    build_rate_budgets,
    load_provider_profiles,
)
from fragarach_ii.lane_commissioning import ensure_commissioned_lane
from fragarach_ii.market_discovery import discover_market
from fragarach_ii.provider_facts import load_provider_facts, save_provider_facts
from fragarach_ii.providers.instrument_search import candidate_from_dict
from fragarach_ii.retirement import retire_instrument
from fragarach_ii.routing_service import (
    RoutingServiceError,
    activate_draft,
    restore_estate_default,
    routing_root,
    routing_snapshot,
    save_draft,
    validate_draft,
)
from fragarach_ii.storage import initialize_database, register_instrument


NOW = datetime(2026, 9, 16, 12, tzinfo=UTC)


def _register_crypto(database: Path, symbol: str = "ETHUSD") -> None:
    initialize_database(database)
    representations = discover_market(database, symbol)["markets"][0]["representations"]
    representation = next(item for item in representations if item.get("registration_plan"))
    raw = json.loads(base64.urlsafe_b64decode(representation["registration_plan"]["candidate"]))
    register_instrument(database, candidate_from_dict(raw), registered_at_utc=NOW.isoformat())
    facts = load_provider_facts(database)
    facts["mappings"][f"TWELVE_DATA:{symbol}"] = {
        "canonical_symbol": symbol,
        "provider": "TWELVE_DATA",
        "provider_symbol": "ETH/USD",
        "mapping_class": "EXACT_REPRESENTATION",
        "status": "OPERATOR_RESOLVED",
        "timeframe_capabilities": {
            timeframe: {"timeframe": timeframe, "supported": True}
            for timeframe in ("D1", "H1", "M30", "M5")
        },
    }
    save_provider_facts(database, facts)
    ensure_commissioned_lane(database, symbol, "H1", observed_at=NOW.isoformat())


def test_lane_override_can_reorder_disable_and_restore(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("fragarach_ii.routing_service.ACTIVATION_GATE", None)
    database = tmp_path / "authority.sqlite3"
    monkeypatch.setenv("FRAGARACH_ROUTING_ROOT", str(tmp_path / "routing"))
    _register_crypto(database)

    before = routing_snapshot(database)
    lane = next(item for item in before["lanes"] if item["id"] == "ETHUSD:D1")
    providers = [item["provider"] for item in lane["candidates"]]
    assert providers[:2] == ["MT5_BRIDGE", "BINANCE"]
    assert "TWELVE_DATA" in providers

    requested = ["TWELVE_DATA"] + [item for item in providers if item != "TWELVE_DATA"]
    draft = save_draft(
        database, symbol="ETHUSD", timeframe="D1", provider_order=requested,
        disabled_providers=["MT5_BRIDGE", "BINANCE"],
        operator_reason="TEST_CONTROLLED_FAILOVER",
    )
    validation = validate_draft(database, draft["draft_id"])
    assert validation["valid"] is True
    assert validation["after_order"][0] == "TWELVE_DATA"
    activation = activate_draft(database, draft["draft_id"])

    revision_path = routing_root(database) / "revisions" / f"{activation['routing_revision']}.json"
    revision = json.loads(revision_path.read_text(encoding="utf-8"))
    assert revision["content_hash"] == f"sha256:{activation['routing_revision']}"
    assert len(revision["effective_lane_routes"]) == len(before["lanes"])
    assert next(
        item for item in revision["effective_lane_routes"] if item["lane"] == "ETHUSD:D1"
    )["effective_provider_order"][0] == "TWELVE_DATA"

    after = routing_snapshot(database)
    lane = next(item for item in after["lanes"] if item["id"] == "ETHUSD:D1")
    assert lane["inheritance"] == "LANE_OVERRIDE"
    assert lane["effective_provider_order"][0] == "TWELVE_DATA"
    assert after["routing_revision"] == activation["routing_revision"]

    restore_preview = save_draft(
        database, symbol="ETHUSD", timeframe="D1", provider_order=(),
        disabled_providers=(), operator_reason="TEST_RESTORE_PREVIEW",
        restore_default=True,
    )
    restore_validation = validate_draft(database, restore_preview["draft_id"])
    assert restore_validation["configured_after_order"][0] == "MT5_BRIDGE"
    assert restore_validation["after_order"][0] == "BINANCE"

    restore = restore_estate_default(
        database, symbol="ETHUSD", timeframe="D1", operator_reason="TEST_RESTORE_DEFAULT",
    )
    restored = routing_snapshot(database)
    lane = next(item for item in restored["lanes"] if item["id"] == "ETHUSD:D1")
    assert lane["inheritance"] == "ESTATE_DEFAULT"
    assert restored["routing_revision"] == restore["routing_revision"]


def test_disabling_every_reviewed_provider_is_explicit_fail_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("fragarach_ii.routing_service.ACTIVATION_GATE", None)
    database = tmp_path / "authority.sqlite3"
    monkeypatch.setenv("FRAGARACH_ROUTING_ROOT", str(tmp_path / "routing"))
    _register_crypto(database)
    snapshot = routing_snapshot(database)
    lane = next(item for item in snapshot["lanes"] if item["id"] == "ETHUSD:H1")
    providers = [item["provider"] for item in lane["candidates"]]
    draft = save_draft(
        database, symbol="ETHUSD", timeframe="H1", provider_order=providers,
        disabled_providers=providers, operator_reason="TEST_FAIL_CLOSED",
    )
    validation = validate_draft(database, draft["draft_id"])
    assert validation["warnings"] == ["LANE_WILL_FAIL_CLOSED"]
    activate_draft(database, draft["draft_id"])
    lane = next(item for item in routing_snapshot(database)["lanes"] if item["id"] == "ETHUSD:H1")
    assert lane["route_state"] == "NO_PROVIDER_FAIL_CLOSED"
    assert lane["effective_provider_order"] == []


def test_http_acquisition_planner_uses_activated_lane_order(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("fragarach_ii.routing_service.ACTIVATION_GATE", None)
    database = tmp_path / "authority.sqlite3"
    monkeypatch.setenv("FRAGARACH_ROUTING_ROOT", str(tmp_path / "routing"))
    _register_crypto(database)
    lane = next(item for item in routing_snapshot(database)["lanes"] if item["id"] == "ETHUSD:D1")
    providers = [item["provider"] for item in lane["candidates"]]
    ordered = ["TWELVE_DATA"] + [item for item in providers if item != "TWELVE_DATA"]
    draft = save_draft(
        database, symbol="ETHUSD", timeframe="D1", provider_order=ordered,
        disabled_providers=["MT5_BRIDGE"], operator_reason="TEST_TWELVE_DATA_FIRST",
    )
    activate_draft(database, draft["draft_id"])

    profiles = load_provider_profiles()
    plan = acquisition_plan(
        database, symbol="ETHUSD", timeframe="D1", canonical_edge=None,
        expected_edge=NOW.isoformat(), missing_start="2026-09-15", missing_end="2026-09-16",
        scheduled_boundary="test:ETHUSD:D1", profiles=profiles, provider_state={},
        budgets=build_rate_budgets(profiles, {}, wall_clock=lambda: NOW, credential="fixture"),
        credentials={"TWELVE_DATA": "fixture"}, now=NOW,
    )
    assert plan["selected_provider"] == "TWELVE_DATA"
    considered = {item["provider"]: item for item in plan["providers_considered"]}
    assert considered["BINANCE"]["fallback_rank"] == 2


def test_activation_is_gated_until_fusion_receipt_scope_is_repaired(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "authority.sqlite3"
    monkeypatch.setenv("FRAGARACH_ROUTING_ROOT", str(tmp_path / "routing"))
    _register_crypto(database)
    lane = next(item for item in routing_snapshot(database)["lanes"] if item["id"] == "ETHUSD:D1")
    draft = save_draft(
        database, symbol="ETHUSD", timeframe="D1",
        provider_order=[item["provider"] for item in lane["candidates"]],
        disabled_providers=[], operator_reason="TEST_GATE",
    )
    assert validate_draft(database, draft["draft_id"])["activation_gate"] == (
        "FUSION_AUTHORITY_LIVE_RECEIPT_VERIFICATION_REQUIRED"
    )
    with pytest.raises(RoutingServiceError, match="FUSION_AUTHORITY_LIVE_RECEIPT_VERIFICATION_REQUIRED"):
        activate_draft(database, draft["draft_id"])


def test_retired_lanes_remain_visible_but_cannot_be_routed(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "authority.sqlite3"
    monkeypatch.setenv("FRAGARACH_ROUTING_ROOT", str(tmp_path / "routing"))
    _register_crypto(database)
    before = routing_snapshot(database)
    retire_instrument(
        database, "ETHUSD", scope="WHOLE_INSTRUMENT",
        selected_lanes=("D1", "H1"), reason="OTHER_REVIEWED_REASON",
        operator_note="test retirement", typed_confirmation="RETIRE ETHUSD",
        completed_at=NOW.isoformat(),
    )
    after = routing_snapshot(database)
    assert {row["id"] for row in after["lanes"]} == {row["id"] for row in before["lanes"]}
    retired_rows = [row for row in after["lanes"] if row["symbol"] == "ETHUSD"]
    assert retired_rows
    assert all(row["route_state"] == "INACTIVE" for row in retired_rows)
    assert all(row["candidates"] == [] for row in retired_rows)
    with pytest.raises(RoutingServiceError, match="INACTIVE_LANE_CANNOT_ROUTE"):
        save_draft(
            database, symbol="ETHUSD", timeframe="D1", provider_order=(),
            disabled_providers=(), operator_reason="TEST_BLOCKED",
        )
