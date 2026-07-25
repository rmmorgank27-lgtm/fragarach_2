from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fragarach_ii.freshness import authority_revision_for_lane
from fragarach_ii.lane_commissioning import ensure_commissioned_lane
from fragarach_ii.storage import open_read_only, registered_writer
from fragarach_ii.synthetic_repository import (
    SyntheticConsumerService,
    SyntheticRepository,
    SyntheticRepositoryError,
    load_registry,
    notify_source_revision_advanced,
)
from tests.validation.test_d1_session_validation import _create_lane


def add_intraday(database: Path, timeframe: str, start: int, count: int, seconds: int) -> None:
    ensure_commissioned_lane(database, "AUDUSD", timeframe)
    with registered_writer(database) as connection:
        for index in range(count):
            opened = start + index * seconds
            base = 100 + index
            connection.execute(
                """INSERT INTO bars(asset,timeframe,open_time_utc,close_time_utc,open,high,low,close,volume,
                   created_by_ingest_run_id,updated_by_ingest_run_id)
                   VALUES('AUDUSD',?,?,?,?,?,?,?,?, 'run-1','run-1')""",
                (timeframe, opened, opened + seconds, str(base), str(base + 2), str(base - 1), str(base + 1), str(index + 1)),
            )
        latest = start + (count - 1) * seconds
        connection.execute(
            """INSERT INTO lane_state(asset,timeframe,high_watermark_open_time_utc,state_version,last_ingest_run_id,updated_at_utc)
               VALUES('AUDUSD',?,?,1,'run-1','2026-07-14T02:00:00+00:00')
               ON CONFLICT(asset,timeframe) DO UPDATE SET high_watermark_open_time_utc=excluded.high_watermark_open_time_utc,
               state_version=lane_state.state_version+1,last_ingest_run_id='run-1',updated_at_utc=excluded.updated_at_utc""",
            (timeframe, latest),
        )


class Spec045SyntheticRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.database = root / "authority.sqlite3"
        self.synthetic = root / "synthetic.sqlite3"
        _create_lane(self.database, "AUDUSD", ["2026-07-13"])
        self.start = int(datetime(2026, 7, 13, 21, tzinfo=UTC).timestamp())
        add_intraday(self.database, "M5", self.start, 48, 300)
        add_intraday(self.database, "M30", self.start, 8, 1800)
        add_intraday(self.database, "H1", self.start, 4, 3600)
        self.generated = datetime(2026, 7, 14, 2, tzinfo=UTC)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def repository(self, registry: Path | None = None) -> SyntheticRepository:
        return SyntheticRepository(self.database, self.synthetic, registry)

    def test_default_registry_generates_m15_h2_h4_deterministically(self) -> None:
        repository = self.repository()
        results = repository.rebuild(generated_at=self.generated)
        self.assertEqual({item["id"] for item in results}, {"AUDUSD:M15", "AUDUSD:H2", "AUDUSD:H4"})
        for product_id, expected in (("AUDUSD:M15", 16), ("AUDUSD:H2", 2), ("AUDUSD:H4", 1)):
            product = repository.product(product_id)
            self.assertEqual(product["status"], "Available")
            self.assertEqual(product["evidence_class"], "SYNTHETIC")
            self.assertEqual(product["observation_count"], expected)
        first = repository.observations("AUDUSD:M15")[0]
        self.assertEqual((first["open"], first["high"], first["low"], first["close"]), ("100", "104", "99", "103"))
        before = repository.observations("AUDUSD:M15")
        repository.generate("AUDUSD:M15", generated_at=self.generated)
        after = repository.observations("AUDUSD:M15")
        self.assertEqual(
            [{key: row[key] for key in ("timestamp", "open", "high", "low", "close", "volume")} for row in before],
            [{key: row[key] for key in ("timestamp", "open", "high", "low", "close", "volume")} for row in after],
        )

    def test_missing_component_is_incomplete_and_never_fabricated(self) -> None:
        with registered_writer(self.database) as connection:
            connection.execute("DELETE FROM bars WHERE asset='AUDUSD' AND timeframe='M5' AND open_time_utc=?", (self.start + 300,))
            connection.execute("UPDATE lane_state SET state_version=state_version+1 WHERE asset='AUDUSD' AND timeframe='M5'")
        repository = self.repository()
        repository.rebuild(generated_at=self.generated)
        product = repository.product("AUDUSD:M15")
        self.assertEqual(product["status"], "Incomplete")
        self.assertEqual(product["observation_count"], 15)
        opens = {item["timestamp"] for item in repository.observations("AUDUSD:M15")}
        self.assertNotIn(self.start, opens)

    def test_partial_current_target_is_not_published(self) -> None:
        repository = self.repository()
        repository.activate_registry()
        repository.generate("AUDUSD:M15", generated_at=datetime(2026, 7, 13, 21, 12, tzinfo=UTC))
        product = repository.product("AUDUSD:M15")
        self.assertEqual(product["observation_count"], 0)
        self.assertEqual(product["status"], "Unavailable")

    def test_lineage_staleness_and_revision_are_separate_from_real_authority(self) -> None:
        repository = self.repository()
        repository.rebuild(generated_at=self.generated)
        before = repository.product("AUDUSD:M15")
        with open_read_only(self.database) as connection:
            real_before = authority_revision_for_lane(connection, symbol="AUDUSD", timeframe="M5")
            table_count = connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
        self.assertEqual(table_count, 10)
        self.assertEqual(before["synthetic_revision"], 1)
        self.assertEqual(before["complete_lineage"][0]["evidence_class"], "REAL")
        with registered_writer(self.database) as connection:
            connection.execute("UPDATE lane_state SET state_version=state_version+1 WHERE asset='AUDUSD' AND timeframe='M5'")
        stale = repository.product("AUDUSD:M15")
        self.assertEqual(stale["status"], "Stale")
        self.assertEqual(stale["synthetic_revision"], 1)
        refreshed = repository.generate("AUDUSD:M15", generated_at=self.generated)
        self.assertEqual(refreshed["synthetic_revision"], 2)
        with open_read_only(self.database) as connection:
            real_after = authority_revision_for_lane(connection, symbol="AUDUSD", timeframe="M5")
            self.assertEqual(connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0], 10)
        self.assertNotEqual(real_before, real_after)

    def test_synthetic_to_synthetic_retains_complete_real_lineage(self) -> None:
        registry = Path(self.temporary.name) / "chain.json"
        payload = json.loads(Path("config/synthetic/synthetic_registry.v1.json").read_text())
        payload["rules"] = [payload["rules"][0], {
            "rule_id": "FX_M15_TO_H2_SESSION_V1", "version": 1,
            "source_timeframe": "M15", "target_timeframe": "H2",
            "calendar": "FX_24X5_NEW_YORK_ROLLOVER_V1", "session_anchor": "17:00",
            "interval_closure": "LEFT_CLOSED_RIGHT_OPEN", "timezone": "America/New_York",
            "required_component_count": 8, "ohlc_calculation": "FIRST_OPEN_MAX_HIGH_MIN_LOW_LAST_CLOSE",
            "volume_handling": "SUM_IF_ALL_PRESENT_ELSE_NULL",
            "missing_component_behaviour": "INCOMPLETE_NO_PUBLICATION",
            "partial_current_period_behaviour": "UNPUBLISHED"
        }]
        parent = payload["registrations"][0]
        child = {
            "symbol": "AUDUSD", "target_timeframe": "H2", "evidence_class": "SYNTHETIC",
            "immediate_source_symbol": "AUDUSD", "immediate_source_timeframe": "M15",
            "immediate_source_evidence_class": "SYNTHETIC", "originating_real_symbol": "AUDUSD",
            "originating_real_timeframe": "M5", "aggregation_rule": "FX_M15_TO_H2_SESSION_V1",
            "aggregation_rule_version": 1, "calendar_authority": "FX_24X5_NEW_YORK_ROLLOVER_V1",
            "session_alignment": "17:00 America/New_York", "authorised_consumers": ["SignalBar"], "status": "ACTIVE"
        }
        payload["registrations"] = [parent, child]
        registry.write_text(json.dumps(payload))
        repository = self.repository(registry)
        repository.rebuild(generated_at=self.generated)
        product = repository.product("AUDUSD:H2")
        self.assertEqual([stage["evidence_class"] for stage in product["complete_lineage"]], ["REAL", "SYNTHETIC", "SYNTHETIC"])
        provenance = repository.observations("AUDUSD:H2")[0]["provenance"]
        self.assertIsNotNone(provenance["source_synthetic_revision"])
        self.assertTrue(provenance["originating_real_authority_revision"].startswith("sha256:"))
        with registered_writer(self.database) as connection:
            connection.execute("UPDATE lane_state SET state_version=state_version+1 WHERE asset='AUDUSD' AND timeframe='M5'")
        self.assertEqual(repository.product("AUDUSD:M15")["status"], "Stale")
        self.assertEqual(repository.product("AUDUSD:H2")["status"], "Stale")

    def test_consumer_contract_enforces_evidence_and_authorisation(self) -> None:
        repository = self.repository()
        repository.rebuild(generated_at=self.generated)
        service = SyntheticConsumerService(repository)
        rejected = service.get_product(symbol="AUDUSD", timeframe="H4", consumer="SignalBar", evidence_requirement="REAL_ONLY")
        self.assertEqual(rejected["status"], "SYNTHETIC_NOT_PERMITTED")
        allowed = service.get_product(symbol="AUDUSD", timeframe="H4", consumer="SignalBar", evidence_requirement="SYNTHETIC_PERMITTED")
        self.assertEqual(allowed["evidence_class"], "SYNTHETIC")
        self.assertTrue(allowed["observations"])
        with self.assertRaisesRegex(SyntheticRepositoryError, "Intruder"):
            service.get_product(symbol="AUDUSD", timeframe="H4", consumer="Intruder", evidence_requirement="SYNTHETIC_PERMITTED")
        unavailable = service.get_product(symbol="AUDUSD", timeframe="H3", consumer="SignalBar", evidence_requirement="SYNTHETIC_PERMITTED")
        self.assertEqual(unavailable["status"], "Unavailable")
        self.assertEqual(unavailable["observations"], [])

    def test_repository_delete_and_rebuild_does_not_change_canonical(self) -> None:
        repository = self.repository()
        with open_read_only(self.database) as connection:
            before = {
                "tables": connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall(),
                "bars": connection.execute("SELECT count(*),sum(open_time_utc) FROM bars").fetchone(),
                "revision": authority_revision_for_lane(connection, symbol="AUDUSD", timeframe="M5"),
            }
        repository.rebuild(generated_at=self.generated)
        expected = [(row["timestamp"], row["open"], row["high"], row["low"], row["close"]) for row in repository.observations("AUDUSD:M15")]
        repository.path.unlink()
        repository.rebuild(generated_at=self.generated)
        rebuilt = [(row["timestamp"], row["open"], row["high"], row["low"], row["close"]) for row in repository.observations("AUDUSD:M15")]
        self.assertEqual(expected, rebuilt)
        with open_read_only(self.database) as connection:
            after = {
                "tables": connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall(),
                "bars": connection.execute("SELECT count(*),sum(open_time_utc) FROM bars").fetchone(),
                "revision": authority_revision_for_lane(connection, symbol="AUDUSD", timeframe="M5"),
            }
        self.assertEqual(before, after)

    def test_registry_forbids_synthetic_promotion_to_real(self) -> None:
        registry = Path(self.temporary.name) / "invalid.json"
        payload = json.loads(Path("config/synthetic/synthetic_registry.v1.json").read_text())
        payload["registrations"][0]["evidence_class"] = "REAL"
        registry.write_text(json.dumps(payload))
        with self.assertRaisesRegex(SyntheticRepositoryError, "AUDUSD:M15"):
            load_registry(registry)

    def test_source_revision_notification_incrementally_generates_dependents(self) -> None:
        repository = self.repository()
        repository.rebuild(generated_at=self.generated)
        before = repository.observations("AUDUSD:M15")
        add_intraday(self.database, "M5", self.start + 48 * 300, 3, 300)
        results = notify_source_revision_advanced(
            self.database, "AUDUSD", "M5", repository_path=self.synthetic
        )
        self.assertEqual(results[0]["id"], "AUDUSD:M15")
        after = repository.observations("AUDUSD:M15")
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(repository.product("AUDUSD:M15")["synthetic_revision"], 2)
        self.assertEqual(after[0]["synthetic_revision"], 1)


if __name__ == "__main__":
    unittest.main()
