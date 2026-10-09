import sqlite3
from datetime import UTC, datetime

import pytest

from fragarach_ii import matrix_chart_consumer as matrix


@pytest.fixture
def authority(tmp_path, monkeypatch):
    p = tmp_path / "authority.sqlite3"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE instrument_registrations(asset TEXT,timeframe TEXT,asset_class TEXT,calendar_id TEXT,calendar_version INTEGER,provider_id TEXT,provider_contract TEXT,provider_symbol TEXT)")
    c.execute("INSERT INTO instrument_registrations VALUES ('AUDUSD','D1','FOREX','FX',1,'MT5','real','AUDUSD')")
    c.execute("CREATE TABLE bars(asset TEXT,timeframe TEXT,open_time_utc INTEGER,open REAL,high REAL,low REAL,close REAL,volume REAL,PRIMARY KEY(asset,timeframe,open_time_utc)) WITHOUT ROWID")
    epoch = int(datetime(2026, 10, 9, tzinfo=UTC).timestamp())
    c.executemany("INSERT INTO bars VALUES ('AUDUSD','M5',?,1,2,0,1,10)", [(epoch - day * 86400,) for day in range(90)])
    c.commit(); c.close()
    monkeypatch.setattr(matrix, "lane_publication_state", lambda *_: "PUBLISHED")
    monkeypatch.setattr(matrix, "authority_revision_for_lane", lambda *a, **kw: "revision-one")
    monkeypatch.setattr(matrix, "truth_state_for_lane", lambda *a, **kw: {"authority_state": "GREEN", "authority_revision": "revision-one", "truth_score": 95, "caodt": "2026-10-09"})
    return p


def read(p, **kw):
    return matrix.get_matrix_chart_context("AUDUSD", "M5", consumer=matrix.CONSUMER, database_path=p, **kw)


def test_bounded_price_read_does_not_require_activity_tables(authority):
    r = read(authority)
    assert r["available"]
    assert len(r["bars"]) == 36
    assert r["bars"][0]["observation_time"] < r["bars"][-1]["observation_time"]
    assert r["descriptor"]["provider"] == "MT5"


def test_descriptor_does_not_materialize_history(authority):
    r = read(authority, descriptor_only=True)
    assert r["available"] and r["bars"] == [] and r["content_digest"] is None


def test_content_digest_changes_on_same_timestamp_price_correction(authority):
    before = read(authority)
    c = sqlite3.connect(authority);c.execute("UPDATE bars SET close=1.5 WHERE open_time_utc=(SELECT max(open_time_utc) FROM bars)");c.commit();c.close()
    after = read(authority)
    assert before["content_digest"] != after["content_digest"]
    assert before["bars"][-1]["observation_time"] == after["bars"][-1]["observation_time"]


def test_publication_in_progress_cannot_serve_ready_prices(authority, monkeypatch):
    monkeypatch.setattr(matrix, "lane_publication_state", lambda *_: "PUBLISHING")
    assert read(authority)["reason"] == "PUBLICATION_PENDING"


def test_authority_withdrawal_cannot_serve_cached_ready_descriptor(authority, monkeypatch):
    monkeypatch.setattr(matrix, "truth_state_for_lane", lambda *a, **kw: {"authority_state": "RED"})
    assert read(authority)["reason"] == "AUTHORITY_WITHDRAWN"


def test_concurrent_publication_revision_must_not_mix_prices(authority, monkeypatch):
    monkeypatch.setattr(matrix, "authority_revision_for_lane", lambda *a, **kw: "revision-two")
    assert read(authority)["reason"] == "REVISION_CHANGED"


def test_only_matrix_consumer_can_use_this_projection(authority):
    with pytest.raises(matrix.ExternalConsumerServiceError, match="other"):
        matrix.get_matrix_chart_context("AUDUSD", "M5", consumer="other", database_path=authority)
