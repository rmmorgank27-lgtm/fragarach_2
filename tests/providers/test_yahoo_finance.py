from __future__ import annotations

import json
from datetime import UTC, datetime

from fragarach_ii.providers.yahoo_finance import acquire_yahoo
from fragarach_ii.providers.twelve_data import AcquisitionError
from fragarach_ii.acquisition_orchestrator import classify_failure
from fragarach_ii.storage import RegistrationCandidate, initialize_database, register_instrument


def _epoch(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp())


def test_yahoo_row_local_ohlc_rejection_preserves_valid_observations(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    register_instrument(
        database,
        RegistrationCandidate(
            asset="ASXCBA",
            timeframe="D1",
            instrument_family="ASXCBA",
            local_symbol="ASXCBA",
            selected_representation="ASX:CBA",
            display_name="Commonwealth Bank",
            instrument_type="COMMON_STOCK",
            asset_class="AUSTRALIAN_EQUITIES",
            representation_type="COMMON_STOCK",
            trading_currency="AUD",
            exchange_name="ASX",
            provider_id="YAHOO_FINANCE",
            provider_contract="YAHOO_FINANCE_CHART_D1_V1",
            provider_symbol="CBA.AX",
            provider_instrument_type="COMMON_STOCK",
            provider_exchange="ASX",
            calendar_id="AUSTRALIAN_EQUITIES_D1_V1",
            calendar_version=1,
            gap_doctrine_id="FRAGARACH_II_D1_GAP_DOCTRINE_V1",
            gap_doctrine_version=1,
        ),
        registered_at_utc="2026-07-17T00:00:00+00:00",
    )
    body = json.dumps({
        "chart": {
            "result": [{
                "meta": {"symbol": "CBA.AX"},
                "timestamp": [_epoch("2024-11-13"), _epoch("2024-11-14"), _epoch("2024-11-15")],
                "indicators": {"quote": [{
                    "open": [153.0, 154.0, 156.0],
                    "high": [154.0, 154.945, 157.0],
                    "low": [152.0, 152.53, 155.0],
                    "close": [153.5, 155.13, 156.5],
                    "volume": [1000, 2493400, 1200],
                }]},
            }]
        }
    }).encode()

    result = acquire_yahoo(
        database,
        asset="ASXCBA",
        asset_class="AUSTRALIAN_EQUITIES",
        from_date="2024-11-13",
        through_date="2024-11-15",
        provider_symbol_override="CBA.AX",
        mapping_class="APPROVED_PROVIDER_ALIAS",
        fetch=lambda _url: body,
    )

    assert result["transaction_state"] == "COMPLETED_WITH_WARNINGS"
    assert result["source_rows"] == 3
    assert result["accepted"] == 2
    assert result["inserted"] == 2
    assert result["rejected"] == 1
    assert result["rejections"] == (
        {"source_row_number": 2, "code": "INVALID_OHLC", "message": "high is below close"},
    )


def test_yahoo_empty_valid_rows_is_retryable_provider_response(tmp_path):
    database = tmp_path / "authority.sqlite3"
    initialize_database(database)
    body = json.dumps({
        "chart": {"result": [{
            "meta": {"symbol": "DE"},
            "timestamp": [_epoch("2026-07-22")],
            "indicators": {"quote": [{
                "open": [None], "high": [None], "low": [None], "close": [None], "volume": [None],
            }]},
        }]},
    }).encode()

    try:
        acquire_yahoo(
            database, asset="DE", asset_class="US_EQUITIES",
            from_date="2026-07-22", through_date="2026-07-22",
            provider_symbol_override="DE", fetch=lambda _url: body,
        )
    except AcquisitionError as error:
        assert error.code == "INVALID_RESPONSE"
        assert classify_failure(error)[0] == "TWELVEDATA_INVALID_RESPONSE"
    else:
        raise AssertionError("an empty Yahoo daily response must not be accepted")
