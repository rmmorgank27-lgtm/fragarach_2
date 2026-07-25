from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.estate_truth_service import _estate_summary, estate_truth_state
from tests.validation.test_d1_session_validation import _create_lane


def _lane(symbol: str, asset_class: str, observation: str, score: int) -> dict[str, object]:
    return {
        "symbol": symbol,
        "latest_canonical_observation": observation,
        "authority_generated": "2026-07-15T00:05:00+00:00",
        "authority_revision": f"sha256:{symbol.lower()}",
        "search_metadata": {"asset_class": asset_class},
        "truth_state": {
            "truth_score": score,
            "authority_state": "GREEN",
            "caodt": observation,
            "latest_canonical_observation": observation,
        },
    }


def test_estate_caodt_is_only_an_alias_of_newest_published_canonical_observation() -> None:
    lanes = [
        _lane("USO", "ENERGY", "2026-07-13T00:00:00+00:00", 70),
        _lane("XAUUSD", "METALS", "2026-07-14T00:00:00+00:00", 80),
        _lane("AUDUSD", "FX", "2026-07-14T05:00:00+00:00", 90),
    ]

    summary = _estate_summary(
        lanes,
        "2026-07-15T00:05:00+00:00",
        "2026-07-14T05:00:00+00:00",
    )

    expected = "2026-07-14T05:00:00+00:00"
    assert summary["latest_canonical_observation"] == expected
    assert summary["caodt"] == expected
    assert summary["overall_caodt"] == expected
    assert summary["aggregation"]["caodt"] == "ALIAS_OF_LATEST_CANONICAL_OBSERVATION"
    assert summary["generated_at"] == "2026-07-15T00:05:00+00:00"
    assert summary["overall_truth_score"] == 80


def test_canonical_lane_root_and_summary_publish_identical_lineage() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _create_lane(database, "AUDUSD", ["2026-07-14"])
        generated = datetime(2026, 7, 15, 0, 5, tzinfo=UTC)

        snapshot = estate_truth_state(database, clock=lambda: generated)
        lane = snapshot["truth_matrix"][0]
        expected = "2026-07-14T00:00:00+00:00"

        assert lane["latest_canonical_observation"] == expected
        assert lane["truth_state"]["latest_canonical_observation"] == expected
        assert lane["truth_state"]["caodt"] == expected
        assert snapshot["latest_canonical_observation"] == expected
        assert snapshot["caodt"] == expected
        assert snapshot["estate_summary"]["latest_canonical_observation"] == expected
        assert snapshot["estate_summary"]["caodt"] == expected
        assert lane["authority_generated"] == generated.isoformat()
        assert lane["authority_revision"].startswith("sha256:")
