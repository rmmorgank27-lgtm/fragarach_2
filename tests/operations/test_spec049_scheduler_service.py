from __future__ import annotations

import json
import os
import plistlib
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from fragarach_ii.scheduler_daemon import (
    COMMAND_CONTRACT,
    MONITOR_CONTRACT,
    AcquisitionOwnership,
    PersistentSchedulerRuntime,
    ServicePaths,
    authority_database_identity,
    install_service,
    launch_agent_definition,
    make_command,
    ownership_is_active,
    send_service_request,
    service_status,
)
from fragarach_ii.lane_update_register import LaneUpdateRegister
from fragarach_ii.storage import initialize_database, verify_integrity
from fragarach_ii.storage.schema import APPLICATION_TABLES


class Spec049SchedulerServiceTests(unittest.TestCase):
    def paths(self, root: Path, database: Path) -> ServicePaths:
        return ServicePaths.create(database, support=root / "support", home=root / "home")

    def test_launch_agent_is_user_scoped_and_contains_no_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "authority.sqlite3"
            initialize_database(database)
            paths = self.paths(root, database)
            definition = launch_agent_definition(paths, python="/usr/bin/python3", repository=root)
            self.assertTrue(definition["RunAtLoad"])
            self.assertEqual(definition["KeepAlive"], {"SuccessfulExit": False})
            self.assertEqual(definition["ProgramArguments"][-2:], ["--mode", "service-run"])
            self.assertNotIn("--monitor-only", definition["ProgramArguments"])
            serialized = plistlib.dumps(definition).decode()
            self.assertNotIn("TWELVE_DATA_API_KEY", serialized)
            self.assertNotIn("credential", serialized.lower())
            metadata = install_service(paths, python="/usr/bin/python3", repository=root, enable=False)
            self.assertTrue(paths.launch_agent.exists())
            self.assertEqual(metadata["authority_database"], str(database.resolve()))
            self.assertEqual(paths.launch_agent.stat().st_mode & 0o777, 0o600)

    def test_only_one_process_can_own_one_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "authority.sqlite3"
            initialize_database(database)
            paths = self.paths(root, database)
            first = AcquisitionOwnership(paths, instance="one", generation="g1")
            second = AcquisitionOwnership(paths, instance="two", generation="g2")
            first.acquire()
            try:
                self.assertTrue(ownership_is_active(paths))
                with self.assertRaisesRegex(RuntimeError, "SERVICE_OWNS_ACQUISITION"):
                    second.acquire()
                metadata = json.loads(paths.ownership.read_text())
                self.assertEqual(len(metadata["authority_database_identity"]), 64)
                self.assertEqual(metadata["scheduler_instance_identifier"], "one")
                self.assertIn("heartbeat_time", metadata)
            finally:
                first.release()
            self.assertFalse(ownership_is_active(paths))

    def test_database_identity_survives_atomic_authority_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "authority.sqlite3"
            initialize_database(database)
            identity_before = authority_database_identity(database)
            support_before = ServicePaths.create(database, home=root / "home").support

            replacement = root / "compacted.sqlite3"
            initialize_database(replacement)
            os.replace(replacement, database)

            self.assertEqual(authority_database_identity(database), identity_before)
            self.assertEqual(ServicePaths.create(database, home=root / "home").support, support_before)

    def test_database_identity_distinguishes_configured_authority_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.sqlite3"
            second = root / "second.sqlite3"
            initialize_database(first)
            initialize_database(second)
            self.assertNotEqual(
                authority_database_identity(first), authority_database_identity(second)
            )

    def test_live_status_idempotent_command_and_graceful_stop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "authority.sqlite3"
            initialize_database(database)
            paths = self.paths(root, database)
            runtime = PersistentSchedulerRuntime(paths, credential=None, monitor_only=True)
            thread = threading.Thread(target=runtime.run, daemon=True)
            thread.start()
            deadline = time.monotonic() + 10
            while not paths.socket.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            status = service_status(paths, app_build="Development")
            self.assertTrue(status["live"])
            self.assertEqual(status["service_state"], "RUNNING")
            self.assertEqual(status["service_generation"], runtime.generation)
            self.assertEqual(status["monitor_contract_version"], 3)
            self.assertEqual(status["scheduler_mode"], "TIME_TRIGGERED_REGISTER")

            command = make_command(
                "RUN_QUEUE_NOW",
                target_generation=runtime.generation,
                command_identifier="same-button-press",
            )
            first = send_service_request(paths, command)
            second = send_service_request(paths, command)
            third = send_service_request(paths, make_command(
                "RUN_QUEUE_NOW", target_generation=runtime.generation,
                command_identifier="second-button-press",
            ))
            self.assertEqual(first["result"], "accepted")
            self.assertEqual(first["detail"]["outcome"], "QUEUE_WAKE_REQUESTED")
            self.assertEqual(second["result"], "already applied")
            self.assertEqual(third["result"], "already applied")
            self.assertEqual(first["contract"], COMMAND_CONTRACT)

            stopped = send_service_request(paths, make_command("STOP_SERVICE", target_generation=runtime.generation))
            self.assertEqual(stopped["result"], "accepted")
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            self.assertFalse(ownership_is_active(paths))
            cached = json.loads(paths.status.read_text())
            self.assertEqual(cached["contract"], MONITOR_CONTRACT)
            self.assertEqual(cached["service_state"], "STOPPED")
            self.assertFalse(cached["live"])
            report = verify_integrity(database)
            self.assertTrue(report.ok)
            self.assertEqual(report.application_tables, APPLICATION_TABLES)
            self.assertEqual(len(APPLICATION_TABLES), 13)

    def test_live_status_overlays_running_register_workers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "authority.sqlite3"
            initialize_database(database)
            paths = self.paths(root, database)
            runtime = PersistentSchedulerRuntime(paths, credential=None, monitor_only=True)
            register = LaneUpdateRegister(database)
            with sqlite3.connect(register.path) as connection:
                connection.executemany(
                    """INSERT INTO lane_update_register
                       (asset,timeframe,state,updated_at_utc,priority)
                       VALUES(?,?,'RUNNING','2026-07-30T13:00:00+00:00',30)""",
                    [(symbol, "M5") for symbol in ("SUIUSD", "LINKUSD", "BTCUSD", "ETHUSD")],
                )
            runtime._snapshot = {
                "scheduler_mode": "TIME_TRIGGERED_REGISTER",
                "execution": {
                    "cycle_id": "prior", "active_workers": 0,
                    "available_workers": 4, "completed_at": "2026-07-30T12:59:00+00:00",
                },
                "scheduler_progress": {},
                "active_activity": None,
            }

            status = runtime._current_status()

            self.assertEqual(status["execution"]["active_workers"], 4)
            self.assertEqual(status["execution"]["available_workers"], 0)
            self.assertEqual(status["register"]["running_count"], 4)
            self.assertEqual(status["heartbeat_cycle_state"], "ACTIVE")
            self.assertEqual(status["operational_health"]["worker_pool"]["active_workers"], 4)


if __name__ == "__main__":
    unittest.main()
