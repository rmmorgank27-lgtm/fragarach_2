from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fragarach_ii.external_consumer_service import (
    ExternalConsumerServiceError,
    HistoryService,
)
from fragarach_ii.history_range_contract import ordered_range_fingerprint
from fragarach_ii.publication_service import publication_path
from fragarach_ii.replica_lite import (
    FragarachLiteError,
    market_history,
    sync_lite,
)
from fragarach_ii.synthetic_repository import SyntheticRepository
from tests.operations.test_replica_lite import _stop, _system
from tests.operations.test_spec045_synthetic_repository import add_intraday
from tests.validation.test_d1_session_validation import _create_lane


CONSUMER = "com.example.historical-runner"


def _range(service: HistoryService, **changes):
    values = {
        "symbol": "AUDUSD",
        "timeframe": "D1",
        "start_utc": "2026-07-09T00:00:00Z",
        "end_utc_exclusive": "2026-07-11T00:00:00Z",
        "as_of_utc": "2026-07-11T00:00:00Z",
        "consumer": CONSUMER,
    }
    values.update(changes)
    return service.get_history_range(**values)


def test_bounded_range_is_exact_completed_and_read_only() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _create_lane(
            database,
            "AUDUSD",
            ["2026-07-09", "2026-07-10", "2026-07-11"],
        )
        before = database.read_bytes()

        response = _range(HistoryService(database))

        assert response["availability_state"] == "AVAILABLE"
        assert [row["timestamp"] for row in response["observations"]] == [
            "2026-07-09T00:00:00+00:00",
            "2026-07-10T00:00:00+00:00",
        ]
        assert response["observation_count"] == 2
        assert response["final_completed_observation_time"] == "2026-07-10T21:00:00+00:00"
        assert response["consumer_identity"] == CONSUMER
        assert response["source_receipt"]["authority_kind"] == "FRAGARACH_II"
        assert database.read_bytes() == before


def test_as_of_and_intraday_completion_boundaries_exclude_future_bars() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
        d1 = _range(
            HistoryService(database),
            as_of_utc="2026-07-10T12:00:00Z",
        )
        assert [row["timestamp"] for row in d1["observations"]] == [
            "2026-07-09T00:00:00+00:00"
        ]
        assert d1["availability_state"] == "PARTIAL"
        assert "INCOMPLETE_OBSERVATIONS_EXCLUDED" in d1["warnings"]

        opened = int(datetime(2026, 7, 10, 10, tzinfo=UTC).timestamp())
        add_intraday(database, "H1", opened, 2, 3600)
        publication_path(database).unlink(missing_ok=True)
        intraday = _range(
            HistoryService(database),
            timeframe="H1",
            start_utc="2026-07-10T10:00:00Z",
            end_utc_exclusive="2026-07-10T13:00:00Z",
            as_of_utc="2026-07-10T11:00:00Z",
        )
        assert [row["timestamp"] for row in intraday["observations"]] == [
            "2026-07-10T10:00:00+00:00"
        ]
        assert intraday["final_completed_observation_time"] == "2026-07-10T11:00:00+00:00"


def test_empty_unavailable_unsupported_partial_and_invalid_are_explicit() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _create_lane(database, "AUDUSD", ["2026-07-09", "2026-07-10"])
        service = HistoryService(database)

        empty = _range(
            service,
            start_utc="2025-01-01T00:00:00Z",
            end_utc_exclusive="2025-01-02T00:00:00Z",
            as_of_utc="2026-07-11T00:00:00Z",
        )
        unavailable = _range(service, symbol="AAPL")
        unsupported = _range(service, timeframe="H4")
        partial = _range(service, start_utc="2026-07-01T00:00:00Z")

        assert empty["availability_state"] == "EMPTY"
        assert empty["final_completed_observation_time"] == "NO_COMPLETED_OBSERVATION"
        assert unavailable["availability_state"] == "UNAVAILABLE"
        assert unsupported["availability_state"] == "UNSUPPORTED"
        assert partial["availability_state"] == "PARTIAL"
        assert partial["truncation"]["state"] == "TRUNCATED"

        with pytest.raises(ExternalConsumerServiceError) as reversed_range:
            _range(
                service,
                start_utc="2026-07-11T00:00:00Z",
                end_utc_exclusive="2026-07-09T00:00:00Z",
            )
        assert reversed_range.value.code == "INVALID_TIME_WINDOW"
        with pytest.raises(ExternalConsumerServiceError) as malformed:
            _range(service, start_utc="not-a-time")
        assert malformed.value.code == "INVALID_TIMESTAMP"


def test_ordered_fingerprint_is_deterministic_and_order_content_sensitive() -> None:
    observations = [
        {
            "timestamp": "2026-07-09T00:00:00Z",
            "close_timestamp": "2026-07-09T21:00:00Z",
            "open": "1", "high": "2", "low": "0", "close": "1",
            "volume": None,
        },
        {
            "timestamp": "2026-07-10T00:00:00Z",
            "close_timestamp": "2026-07-10T21:00:00Z",
            "open": "1", "high": "2", "low": "0", "close": "1",
            "volume": None,
        },
    ]
    first = ordered_range_fingerprint("AUDUSD", "D1", observations)
    assert first == ordered_range_fingerprint("AUDUSD", "D1", observations)
    assert first != ordered_range_fingerprint("AUDUSD", "D1", reversed(observations))
    changed = [dict(row) for row in observations]
    changed[1]["close"] = "1.1"
    assert first != ordered_range_fingerprint("AUDUSD", "D1", changed)


def test_fragarach_ii_and_lite_share_observations_and_range_fingerprint(tmp_path: Path) -> None:
    database, _, _, server, thread, lite = _system(tmp_path)
    before_authority = database.read_bytes()
    try:
        sync_lite(lite, allow_unsigned=True, allow_insecure_transport=True)
        lite_database = next(lite.revisions.glob("*.sqlite3"))
        before_lite = lite_database.read_bytes()

        authority = _range(HistoryService(database))
        replica = market_history(
            lite,
            symbol="AUDUSD",
            timeframe="D1",
            start_utc="2026-07-09T00:00:00Z",
            end_utc_exclusive="2026-07-11T00:00:00Z",
            as_of_utc="2026-07-11T00:00:00Z",
            consumer=CONSUMER,
            evidence_requirement="REAL_ONLY",
        )

        assert replica["observations"] == authority["observations"]
        assert replica["ordered_range_fingerprint"] == authority["ordered_range_fingerprint"]
        assert replica["contract_version"] == authority["contract_version"]
        assert replica["bar_count"] == replica["observation_count"] == 2
        assert replica["data_fingerprint"] == replica["ordered_range_fingerprint"]
        assert database.read_bytes() == before_authority
        assert lite_database.read_bytes() == before_lite

        with pytest.raises(FragarachLiteError) as malformed:
            market_history(
                lite,
                symbol="AUDUSD",
                timeframe="D1",
                start_utc="bad",
                end_utc_exclusive="2026-07-11T00:00:00Z",
                as_of_utc="2026-07-11T00:00:00Z",
            )
        assert malformed.value.code == "INVALID_TIMESTAMP"
    finally:
        _stop(server, thread)


def test_synthetic_range_retains_class_and_consumer_permission() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "authority.sqlite3"
        _create_lane(database, "AUDUSD", ["2026-07-13"])
        opened = int(datetime(2026, 7, 13, 21, tzinfo=UTC).timestamp())
        add_intraday(database, "M5", opened, 6, 300)
        add_intraday(database, "M30", opened, 2, 1800)
        add_intraday(database, "H1", opened, 1, 3600)
        repository = SyntheticRepository(database)
        repository.activate_registry(generate_on_activation=False)
        repository.generate(
            "AUDUSD:M15", generated_at=datetime(2026, 7, 13, 22, tzinfo=UTC)
        )
        service = HistoryService(database)

        denied = _range(
            service,
            timeframe="M15",
            start_utc="2026-07-13T21:00:00Z",
            end_utc_exclusive="2026-07-13T22:00:00Z",
            as_of_utc="2026-07-13T22:00:00Z",
        )
        allowed = _range(
            service,
            timeframe="M15",
            start_utc="2026-07-13T21:00:00Z",
            end_utc_exclusive="2026-07-13T22:00:00Z",
            as_of_utc="2026-07-13T22:00:00Z",
            consumer="com.raymorgan.echo",
            evidence_requirement="SYNTHETIC_PERMITTED",
        )

        assert denied["status"] == "SYNTHETIC_NOT_PERMITTED"
        assert allowed["evidence_class"] == "SYNTHETIC"
        assert allowed["observation_count"] == 2
