from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fragarach_ii.commands import scheduler as scheduler_command
from fragarach_ii.scheduler_daemon import ServicePaths, _atomic_json, enrich_monitor, record_restart
from fragarach_ii.storage import initialize_database, open_read_only


def descriptor_count() -> int:
    """Portable enough for the supported macOS runtime and tolerant in tests."""
    return len(os.listdir("/dev/fd"))


class IFI004DescriptorLifecycleTests(unittest.TestCase):
    def test_read_only_context_closes_database_and_wal_handles_after_each_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            initialize_database(database)
            baseline = descriptor_count()
            samples: list[int] = []
            for _ in range(40):
                with open_read_only(database) as connection:
                    self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)
                with self.assertRaises(Exception):
                    connection.execute("SELECT 1")
                samples.append(descriptor_count())
            self.assertLessEqual(max(samples) - baseline, 3)
            self.assertLessEqual(max(samples) - min(samples), 2)

    def test_atomic_json_releases_descriptor_and_preserves_existing_state_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "restart-history.json"
            _atomic_json(target, {"before": True})
            baseline = descriptor_count()
            for index in range(30):
                _atomic_json(target, {"index": index})
            self.assertLessEqual(descriptor_count() - baseline, 2)
            expected = target.read_text(encoding="utf-8")
            with patch("fragarach_ii.scheduler_daemon.json.dump", side_effect=RuntimeError("injected write failure")):
                with self.assertRaisesRegex(RuntimeError, "injected write failure"):
                    _atomic_json(target, {"after": False})
            self.assertEqual(target.read_text(encoding="utf-8"), expected)
            self.assertEqual(list(target.parent.glob(f".{target.name}.*")), [])
            self.assertLessEqual(descriptor_count() - baseline, 2)

    def test_restart_history_writes_remain_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "authority.sqlite3"
            initialize_database(database)
            paths = ServicePaths.create(database, support=root / "support", home=root / "home")
            paths.prepare()
            baseline = descriptor_count()
            for index in range(30):
                state = record_restart(paths, f"failure-{index}")
                self.assertIn(state["service_state"], {"DEGRADED_RESTARTING", "CRASH_LOOP_PROTECTED"})
            self.assertLessEqual(descriptor_count() - baseline, 3)
            self.assertEqual(len(__import__("json").loads(paths.restart_history.read_text(encoding="utf-8"))), 20)

    def test_healthy_monitor_does_not_replay_an_old_exit_as_a_live_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "authority.sqlite3"
            initialize_database(database)
            paths = ServicePaths.create(database, support=root / "support", home=root / "home")

            monitor = enrich_monitor(
                {"last_exit_reason": "OSError: [Errno 24] Too many open files"},
                paths, instance="fixture", generation="fixture", started_at="2026-07-23T00:00:00+00:00",
            )

            self.assertNotIn("last_exit_reason", monitor)

    def test_restart_recording_failure_keeps_primary_failure_visible(self) -> None:
        class FailingRuntime:
            def __init__(self, *_args, **_kwargs) -> None:
                self.scheduler = type("Scheduler", (), {"stop": lambda self: None, "wake": lambda self: None})()

            def run(self) -> None:
                raise RuntimeError("primary scheduler failure")

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "authority.sqlite3"
            initialize_database(database)
            with patch.object(scheduler_command, "PersistentSchedulerRuntime", FailingRuntime), patch.object(
                scheduler_command, "resolve_scheduler_credential", return_value=(None, "test")
            ), patch.object(scheduler_command, "record_restart", side_effect=OSError("restart history unavailable")):
                from io import StringIO
                import contextlib

                stderr = StringIO()
                with contextlib.redirect_stderr(stderr):
                    result = scheduler_command.main(["--database", str(database), "--mode", "service-run"])
            self.assertEqual(result, 1)
            self.assertIn("SCHEDULER_SERVICE_FAILURE: RuntimeError: primary scheduler failure", stderr.getvalue())
            self.assertIn("SCHEDULER_RESTART_RECORDING_FAILURE: OSError: restart history unavailable", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
