from __future__ import annotations

from unittest.mock import patch

import pytest

from fragarach_ii.providers.resolution import acquire_resolved


def test_legacy_entrypoint_submits_to_unified_operator_fetch() -> None:
    expected = {"work_class": "OPERATOR_FETCH", "outcome": "SUCCESS"}
    with patch(
        "fragarach_ii.providers.resolution.run_operator_fetch", return_value=expected
    ) as unified:
        result = acquire_resolved(
            "/tmp/authority.sqlite3",
            asset="EURUSD",
            timeframe="D1",
            from_date="2026-07-01",
            through_date="2026-07-11",
            merge_mode="preserve",
            credential="fixture",
            intent="custom",
        )
    assert result == expected
    unified.assert_called_once()
    submitted = unified.call_args.kwargs
    assert submitted["symbol"] == "EURUSD"
    assert submitted["requested_start"] == "2026-07-01"
    assert submitted["requested_end"] == "2026-07-11"
    assert submitted["reviewed_historical_range"] is True
    assert submitted["operator_reason"] == "LEGACY_CALLER_UNIFIED_BY_SPEC_047"


def test_legacy_provider_specific_injection_is_rejected() -> None:
    with pytest.raises(ValueError, match="LEGACY_PROVIDER_INJECTION_REMOVED"):
        acquire_resolved(
            "/tmp/authority.sqlite3",
            asset="EURUSD",
            from_date="2026-07-01",
            through_date="2026-07-11",
            merge_mode="preserve",
            credential=None,
            twelve_transport=object(),
        )
