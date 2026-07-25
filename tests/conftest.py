from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_twelve_data_credit_authority(tmp_path, monkeypatch):
    """Keep cross-process production accounting isolated between test cases."""

    monkeypatch.setenv(
        "FRAGARACH_TWELVE_DATA_CREDIT_ROOT",
        str(tmp_path / "twelve-data-credit-authority"),
    )
