from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fragarach_ii.execution_trace import scheduler_progress_projection
from fragarach_ii.scheduler_daemon import (
    PersistentSchedulerRuntime,
    STATUS_CONTRACT,
    ServicePaths,
    scheduler_operational_health,
    send_service_request,
    service_status,
)
from fragarach_ii.storage import initialize_database


class Spec060SchedulerHealthTests(unittest.TestCase):
    def health(self, *, queue: list[dict[str, object]], events: list[dict[str, object]], active: int = 0):
        now = datetime.now(UTC)
        progress = scheduler_progress_projection(
            {"acquisition_queue": queue, "execution_trace_events": events},
            {"active_workers": active, "available_workers": 0 if active else 1, "duration_seconds": 2},
            now,
        )
        return scheduler_operational_health(
            {"scheduler_progress": progress}, process_alive=True,
            heartbeat_time=now.isoformat(), monitor_state="MONITOR_DISCONNECTED", now=now,
        )

    def test_monitor_disconnect_does_not_make_productive_scheduler_unavailable(self) -> None:
        now = datetime.now(UTC)
        health = self.health(
            queue=[{"lane": "AUDUSD:M5", "trace_id": "t", "enqueued_at": now.isoformat(), "operational_state": "Running"}],
            events=[{"trace_id": "t", "event": "REQUEST_STARTED", "timestamp": now.isoformat()}],
            active=1,
        )
        self.assertEqual(health["overall_operational_health"], "HEALTHY")
        self.assertEqual(health["monitor_transport"]["state"], "MONITOR_DISCONNECTED")
        self.assertEqual(health["process"]["state"], "ALIVE")

    def test_idle_stalled_and_unavailable_are_distinct(self) -> None:
        idle = self.health(queue=[], events=[])
        self.assertEqual(idle["overall_operational_health"], "IDLE")

        now = datetime.now(UTC)
        stale = (now - timedelta(minutes=3)).isoformat()
        stalled = self.health(
            queue=[{"lane": "AUDUSD:M5", "trace_id": "t", "enqueued_at": stale, "operational_state": "Ready", "current_stage": "SELECTED"}],
            events=[{"trace_id": "t", "event": "SELECTED", "timestamp": stale}],
        )
        self.assertEqual(stalled["overall_operational_health"], "STALLED")
        self.assertEqual(stalled["current_lane"], "AUDUSD:M5")
        unavailable = scheduler_operational_health(
            {"scheduler_progress": {}}, process_alive=False,
            heartbeat_time=None, monitor_state="MONITOR_DISCONNECTED", now=now,
        )
        self.assertEqual(unavailable["overall_operational_health"], "UNAVAILABLE")

    def test_terminal_failed_queue_artifact_is_blocked_not_a_false_stall(self) -> None:
        now = datetime.now(UTC)
        health = self.health(
            queue=[{"lane": "USDCHF:M30", "trace_id": "terminal", "enqueued_at": (now - timedelta(hours=1)).isoformat(), "operational_state": "Ready"}],
            events=[{"trace_id": "terminal", "event": "ATTEMPT_FAILED", "timestamp": now.isoformat(), "retryable": False, "reason_code": "DISPATCH_REJECTED"}],
        )
        self.assertEqual(health["overall_operational_health"], "IDLE")
        self.assertEqual(health["actionable_queue_depth"], 0)
        self.assertEqual(health["blocked_queue_depth"], 1)

    def test_monitor_listener_rebuild_preserves_scheduler_generation_and_queue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "authority.sqlite3"
            initialize_database(database)
            paths = ServicePaths.create(database, support=root / "support", home=root / "home")
            runtime = PersistentSchedulerRuntime(paths, credential=None, monitor_only=True)
            thread = threading.Thread(target=runtime.run, daemon=True)
            thread.start()
            deadline = time.monotonic() + 10
            while not paths.socket.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            before = send_service_request(paths, {"contract": STATUS_CONTRACT, "request": "ping"})
            queue_before = json.loads(paths.journal.read_text()).get("acquisition_queue", [])
            runtime.request_monitor_repair()
            after = before
            deadline = time.monotonic() + 5
            while after.get("monitor_generation") == before.get("monitor_generation") and time.monotonic() < deadline:
                time.sleep(0.05)
                try:
                    after = send_service_request(paths, {"contract": STATUS_CONTRACT, "request": "ping"}, timeout=1)
                except (OSError, ValueError):
                    pass
            self.assertEqual(after["process_id"], before["process_id"])
            self.assertEqual(after["service_generation"], before["service_generation"])
            self.assertNotEqual(after["monitor_generation"], before["monitor_generation"])
            self.assertEqual(json.loads(paths.journal.read_text()).get("acquisition_queue", []), queue_before)
            self.assertEqual(service_status(paths)["operational_health"]["monitor_transport"]["state"], "CONNECTED")
            runtime.scheduler.stop()
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
