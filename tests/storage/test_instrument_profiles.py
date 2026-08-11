from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from fragarach_ii.storage import (
    InstrumentProfileError,
    InstrumentProfileEventCandidate,
    instrument_profile,
    record_instrument_profile_event,
)
from tests.validation.test_d1_session_validation import _create_lane


def _event(**changes: object) -> InstrumentProfileEventCandidate:
    values: dict[str, object] = {
        "asset": "BTCUSD",
        "event_type": "GENESIS_BLOCK",
        "occurred_at_utc": "2009-01-03T18:15:05+00:00",
        "date_precision": "SECOND",
        "block_height": 0,
        "title": "Bitcoin genesis block",
        "source_url": "https://example.test/bitcoin-genesis",
        "source_name": "Primary protocol source",
        "source_retrieved_at_utc": "2026-08-11T02:00:00+00:00",
        "evidence_sha256": hashlib.sha256(b"bitcoin genesis evidence").hexdigest(),
        "verification_status": "VERIFIED_PRIMARY_SOURCE",
        "is_primary_origin": True,
    }
    values.update(changes)
    return InstrumentProfileEventCandidate(**values)


def test_profile_combines_sourced_origin_with_derived_history_and_extrema(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    _create_lane(database, "BTCUSD", ["2026-07-09", "2026-07-10"])

    result = record_instrument_profile_event(
        database, _event(), recorded_at_utc="2026-08-11T02:00:01+00:00"
    )
    profile = instrument_profile(database, "BTCUSD")

    assert result["outcome"] == "RECORDED"
    assert profile["origin_status"] == "VERIFIED"
    assert profile["origin"]["event_type"] == "GENESIS_BLOCK"
    assert profile["origin"]["block_height"] == 0
    assert profile["history"]["bar_count"] == 2
    assert profile["history"]["start_utc"] == "2026-07-09T00:00:00+00:00"
    assert profile["history"]["all_available_history_held"] is None
    assert profile["history"]["completeness_status"] == "UNVERIFIED"
    assert profile["extrema"]["high"]["price"] == "2"
    assert profile["extrema"]["low"]["price"] == "0"


def test_profile_event_requires_registered_symbol(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    _create_lane(database, "BTCUSD", ["2026-07-09"])

    with pytest.raises(InstrumentProfileError, match="NOPE"):
        record_instrument_profile_event(
            database, _event(asset="NOPE"),
            recorded_at_utc="2026-08-11T02:00:01+00:00",
        )


def test_profile_event_import_is_idempotent_and_origin_replacement_is_explicit(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    _create_lane(database, "BTCUSD", ["2026-07-09"])

    first = record_instrument_profile_event(
        database, _event(), recorded_at_utc="2026-08-11T02:00:01+00:00"
    )
    repeated = record_instrument_profile_event(
        database, _event(), recorded_at_utc="2026-08-12T02:00:01+00:00"
    )

    assert first["outcome"] == "RECORDED"
    assert repeated["outcome"] == "ALREADY_RECORDED"
    with pytest.raises(InstrumentProfileError, match="PRIMARY_ORIGIN_ALREADY_RECORDED"):
        record_instrument_profile_event(
            database,
            _event(
                occurred_at_utc="2009-01-03T00:00:00+00:00",
                date_precision="DAY",
            ),
            recorded_at_utc="2026-08-11T02:00:02+00:00",
        )


def test_profile_event_accepts_honest_month_precision(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    _create_lane(database, "BTCUSD", ["2026-07-09"])

    record_instrument_profile_event(
        database,
        _event(
            event_type="MAINNET_LAUNCH",
            occurred_at_utc="2012-06-01T00:00:00+00:00",
            date_precision="MONTH",
            block_height=None,
        ),
        recorded_at_utc="2026-08-11T02:00:01+00:00",
    )

    assert instrument_profile(database, "BTCUSD")["origin"]["date_precision"] == "MONTH"
