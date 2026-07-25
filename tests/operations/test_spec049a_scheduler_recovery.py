from __future__ import annotations

import hashlib
import json
import socket
import struct
import tempfile
import threading
import time
import unittest
import subprocess
from pathlib import Path

from fragarach_ii.scheduler_daemon import (
    AcquisitionOwnership,
    MUTATION_CONTRACT,
    ServiceMutation,
    ServicePaths,
    SchedulerCommandServer,
    cancel_service_mutation,
    manage_service_lifecycle,
    reconcile_service_mutation,
    service_diagnostics,
    service_status,
)
from fragarach_ii.storage import initialize_database, verify_integrity
from fragarach_ii.storage.schema import APPLICATION_TABLES


class _LaunchResult:
    returncode = 0
    stderr = b""


class Spec049ASchedulerRecoveryTests(unittest.TestCase):
    def paths(self, root: Path) -> ServicePaths:
        database = root / "authority.sqlite3"
        initialize_database(database)
        paths = ServicePaths.create(database, support=root / "support", home=root / "home")
        paths.prepare()
        paths.launch_agent.parent.mkdir(parents=True, exist_ok=True)
        paths.launch_agent.write_text("placeholder", encoding="utf-8")
        paths.metadata.write_text("{}", encoding="utf-8")
        return paths

    def test_start_timeout_releases_mutation_and_preserves_canonical_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            before = hashlib.sha256(paths.database.read_bytes()).hexdigest()
            calls: list[list[str]] = []

            def launchctl(arguments: list[str], **_: object) -> _LaunchResult:
                calls.append(arguments)
                return _LaunchResult()

            result = manage_service_lifecycle(
                paths,
                "START",
                launchctl=launchctl,
                stage_timeouts={"WAITING_FOR_PROCESS": 0.03},
            )
            self.assertEqual(result["operation_status"], "TIMED_OUT")
            self.assertEqual(result["operation_stage"], "WAITING_FOR_PROCESS")
            self.assertEqual(result["failure_code"], "MUTATION_STAGE_TIMEOUT")
            self.assertTrue(any("kickstart" in call for call in calls))

            document = json.loads(paths.mutation.read_text())
            self.assertIsNone(document["active_mutation"])
            self.assertEqual(document["last_operation"]["status"], "TIMED_OUT")
            self.assertEqual(hashlib.sha256(paths.database.read_bytes()).hexdigest(), before)
            integrity = verify_integrity(paths.database)
            self.assertTrue(integrity.ok)
            self.assertEqual(integrity.application_tables, APPLICATION_TABLES)
            self.assertEqual(len(APPLICATION_TABLES), 12)

    def test_live_acquisition_owner_with_broken_socket_never_launches_second_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            owner = AcquisitionOwnership(paths, instance="live-owner", generation="generation-one")
            owner.acquire()
            calls: list[list[str]] = []
            try:
                result = manage_service_lifecycle(
                    paths,
                    "START",
                    launchctl=lambda arguments, **_: calls.append(arguments) or _LaunchResult(),
                )
                self.assertEqual(result["operation_status"], "FAILED")
                self.assertEqual(result["failure_code"], "SERVICE_PROCESS_ALIVE_MONITOR_UNREACHABLE")
                self.assertEqual(result["recommended_action"], "REPAIR_MONITOR")
                self.assertEqual(calls, [])
                self.assertTrue(paths.ownership.exists())
            finally:
                owner.release()

    def test_process_without_socket_times_out_at_socket_stage_and_releases_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            owner = AcquisitionOwnership(paths, instance="launched-owner", generation="generation-two")

            def launchctl(_arguments: list[str], **_: object) -> _LaunchResult:
                owner.acquire()
                return _LaunchResult()

            try:
                result = manage_service_lifecycle(
                    paths,
                    "START",
                    launchctl=launchctl,
                    stage_timeouts={"WAITING_FOR_SOCKET": 0.03},
                )
                self.assertEqual(result["operation_status"], "TIMED_OUT")
                self.assertEqual(result["operation_stage"], "WAITING_FOR_SOCKET")
                self.assertIsNone(json.loads(paths.mutation.read_text())["active_mutation"])
                self.assertTrue(paths.ownership.exists())
            finally:
                owner.release()

    def test_launch_failure_records_exact_failure_and_allows_immediate_repair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))

            def launchctl(arguments: list[str], **_: object) -> _LaunchResult:
                raise subprocess.CalledProcessError(5, arguments, stderr=b"bootstrap rejected the service")

            failed = manage_service_lifecycle(paths, "START", launchctl=launchctl)
            self.assertEqual(failed["operation_status"], "FAILED")
            self.assertEqual(failed["failure_code"], "LAUNCH_AGENT_COMMAND_FAILED")
            self.assertIn("bootstrap rejected", failed["failure_detail"])
            self.assertIsNone(json.loads(paths.mutation.read_text())["active_mutation"])

            repaired = manage_service_lifecycle(
                paths,
                "REPAIR",
                launchctl=lambda *_args, **_kwargs: _LaunchResult(),
                stage_timeouts={"WAITING_FOR_PROCESS": 0.01},
            )
            self.assertNotEqual(repaired.get("recommended_action"), "VIEW_ACTIVE_OPERATION")

    def test_disabled_launch_agent_is_identified_without_launch_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            paths.metadata.write_text('{"automatic_login_start":false}\n', encoding="utf-8")
            calls: list[list[str]] = []
            result = manage_service_lifecycle(
                paths,
                "START",
                launchctl=lambda arguments, **_: calls.append(arguments) or _LaunchResult(),
            )
            self.assertEqual(result["failure_code"], "LAUNCH_AGENT_DISABLED")
            self.assertEqual(result["recommended_action"], "ENABLE_SERVICE")
            self.assertEqual(calls, [])

    def test_app_crash_record_is_abandoned_without_clearing_acquisition_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            paths.ownership.write_text('{"sentinel":"preserve-me"}\n', encoding="utf-8")
            now = "2026-07-14T00:00:00+00:00"
            record = {
                "operation_id": "crashed-repair",
                "operation_type": "REPAIR",
                "status": "RUNNING",
                "requested_at": now,
                "started_at": now,
                "last_progress_at": now,
                "completed_at": None,
                "requesting_app_pid": 999_999_991,
                "requesting_app_build": "Development",
                "requesting_app_instance": "crashed-app",
                "helper_process_pid": 999_999_992,
                "target_service_generation": None,
                "current_stage": "CHECKING_SOCKET",
                "progress_message": "Checking socket",
                "failure_code": None,
                "failure_detail": None,
                "cancellable": True,
            }
            paths.mutation.write_text(json.dumps({
                "contract": MUTATION_CONTRACT,
                "generation": 1,
                "active_mutation": record,
                "last_operation": None,
                "history": [],
                "reconciliation_status": "ACTIVE_OPERATION_CONFIRMED",
            }), encoding="utf-8")

            outcome = reconcile_service_mutation(paths)
            self.assertEqual(outcome["outcome"], "STALE_OPERATION_CLEARED")
            document = json.loads(paths.mutation.read_text())
            self.assertIsNone(document["active_mutation"])
            self.assertEqual(document["last_operation"]["status"], "ABANDONED")
            self.assertIn("preserve-me", paths.ownership.read_text())

    def test_second_mutation_names_active_operation_and_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            first = ServiceMutation(paths, "REPAIR")
            first.begin()
            first.stage("CHECKING_SOCKET", "Checking monitor socket")
            try:
                second = manage_service_lifecycle(paths, "START")
                self.assertEqual(second["recommended_action"], "VIEW_ACTIVE_OPERATION")
                self.assertEqual(second["active_operation"]["operation_type"], "REPAIR")
                self.assertEqual(second["active_operation"]["current_stage"], "CHECKING_SOCKET")
                self.assertIn("Repair is active", second["reason"])
            finally:
                first.fail(RuntimeError("test cleanup"))

    def test_cancellable_wait_becomes_cancelled_and_unlocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            result: dict[str, object] = {}

            def run() -> None:
                result.update(manage_service_lifecycle(
                    paths,
                    "START",
                    launchctl=lambda *_args, **_kwargs: _LaunchResult(),
                    stage_timeouts={"WAITING_FOR_PROCESS": 2.0},
                ))

            thread = threading.Thread(target=run)
            thread.start()
            deadline = time.monotonic() + 2
            operation_id = None
            while time.monotonic() < deadline:
                document = json.loads(paths.mutation.read_text()) if paths.mutation.exists() else {}
                active = document.get("active_mutation")
                if isinstance(active, dict) and active.get("current_stage") == "WAITING_FOR_PROCESS":
                    operation_id = active["operation_id"]
                    break
                time.sleep(0.01)
            self.assertIsNotNone(operation_id)
            cancellation = cancel_service_mutation(paths, str(operation_id))
            self.assertTrue(cancellation["cancelled"])
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result["operation_status"], "CANCELLED")
            self.assertIsNone(json.loads(paths.mutation.read_text())["active_mutation"])

    def test_status_and_diagnostics_expose_recovery_contract_without_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            mutation = ServiceMutation(paths, "REPAIR", app_build="test-build", requesting_app_pid=999_999_993)
            mutation.begin()
            mutation.stage("INSPECTING_EXECUTABLE", "Inspecting executable")
            try:
                status = service_status(paths, app_build="Development")
                self.assertEqual(status["active_mutation"]["operation_type"], "REPAIR")
                self.assertEqual(status["mutation_stage"], "INSPECTING_EXECUTABLE")
                self.assertIn("VIEW_DETAILS", status["recommended_actions"])
                diagnostics = service_diagnostics(paths)
                self.assertFalse(diagnostics["credentials_included"])
                self.assertIn("checks", diagnostics)
                serialized = json.dumps(diagnostics).lower()
                self.assertNotIn("api_key", serialized)
                self.assertNotIn("password", serialized)
            finally:
                mutation.fail(RuntimeError("test cleanup"))

    def test_large_monitor_and_disconnected_client_do_not_kill_command_server(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            payload = "x" * (2 * 1024 * 1024)
            server = SchedulerCommandServer(paths, lambda request: {"request": request.get("request"), "payload": payload})
            server.start()
            try:
                abandoned = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                abandoned.connect(str(paths.socket))
                abandoned.sendall(b'{"request":"abandoned"}\n')
                abandoned.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                abandoned.close()
                time.sleep(0.05)

                from fragarach_ii.scheduler_daemon import send_service_request

                response = send_service_request(paths, {"request": "survived"}, timeout=3)
                self.assertEqual(response["request"], "survived")
                self.assertEqual(len(response["payload"]), len(payload))
                self.assertTrue(server.thread and server.thread.is_alive())
            finally:
                server.stop()

    def test_partial_client_cannot_block_bounded_monitor_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            server = SchedulerCommandServer(
                paths, lambda request: {"request": request.get("request"), "live": True}
            )
            server.start()
            stalled = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                stalled.connect(str(paths.socket))
                stalled.sendall(b'{"request":"partial"')

                from fragarach_ii.scheduler_daemon import send_service_request

                started = time.monotonic()
                response = send_service_request(
                    paths, {"request": "status"}, timeout=0.5
                )
                self.assertTrue(response["live"])
                self.assertEqual(response["request"], "status")
                self.assertLess(time.monotonic() - started, 0.5)
                self.assertTrue(server.thread and server.thread.is_alive())
            finally:
                stalled.close()
                server.stop()


if __name__ == "__main__":
    unittest.main()
