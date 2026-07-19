from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from atlas.scheduler import TaskScheduler
from atlas.scheduler_cli import main


class TaskSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.state_file = Path(self.temporary_directory.name) / "scheduler.json"
        self.scheduler = TaskScheduler(self.state_file)
        self.now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)

    def test_new_task_is_immediately_due(self) -> None:
        self.assertTrue(
            self.scheduler.due("maintenance", 3600, now=self.now)
        )

    def test_register_persists_task_metadata(self) -> None:
        task = self.scheduler.register(
            "sports-sync",
            300,
            "modules/sports/scripts/sync.py",
            description="Refresh Sports providers",
            module="sports",
        )

        self.assertEqual(task["interval_seconds"], 300)
        self.assertEqual(task["module"], "sports")
        self.assertTrue(task["enabled"])
        self.assertEqual(task["run_count"], 0)
        self.assertEqual(task["failure_count"], 0)

    def test_registered_task_uses_stored_interval(self) -> None:
        self.scheduler.register("maintenance", 3600, "maintenance.py")
        self.scheduler.succeeded("maintenance", now=self.now)

        self.assertFalse(
            self.scheduler.due(
                "maintenance", now=self.now + timedelta(minutes=30)
            )
        )
        self.assertTrue(
            self.scheduler.due(
                "maintenance", now=self.now + timedelta(hours=1)
            )
        )

    def test_disabled_task_is_not_due(self) -> None:
        self.scheduler.register(
            "maintenance", 0, "maintenance.py", enabled=False
        )
        self.assertFalse(self.scheduler.due("maintenance", now=self.now))

    def test_list_tasks_is_sorted_and_includes_schedule(self) -> None:
        self.scheduler.register("z-task", 60, "z.py")
        self.scheduler.register("a-task", 120, "a.py")

        tasks = self.scheduler.list_tasks()
        self.assertEqual([task["name"] for task in tasks], ["a-task", "z-task"])
        self.assertTrue(tasks[0]["due"])
        self.assertIsNotNone(tasks[0]["next_run"])

    def test_remove_task(self) -> None:
        self.scheduler.register("maintenance", 60, "maintenance.py")
        self.assertTrue(self.scheduler.remove("maintenance"))
        self.assertFalse(self.scheduler.remove("maintenance"))
        self.assertEqual(self.scheduler.task_state("maintenance"), {})

    def test_task_lifecycle_is_persisted(self) -> None:
        self.scheduler.register("maintenance", 3600, "maintenance.py")
        self.scheduler.started("maintenance", now=self.now)

        running = self.scheduler.task_state("maintenance")
        self.assertEqual(running["status"], "running")

        self.scheduler.succeeded(
            "maintenance",
            now=self.now,
            details={"removed": 2},
            duration_ms=125,
        )

        succeeded = self.scheduler.task_state("maintenance")
        self.assertEqual(succeeded["run_count"], 1)
        self.assertEqual(succeeded["last_duration_ms"], 125)

        self.scheduler.failed(
            "maintenance",
            "simulated failure",
            now=self.now + timedelta(hours=1),
            duration_ms=25,
        )

        failed = self.scheduler.task_state("maintenance")
        self.assertEqual(failed["status"], "degraded")
        self.assertEqual(failed["consecutive_failures"], 1)
        self.assertEqual(failed["failure_count"], 1)
        self.assertEqual(failed["run_count"], 2)

        parsed_state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(parsed_state["schema_version"], 1)
        self.assertIn("tasks", parsed_state)

    def test_negative_interval_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.scheduler.due("maintenance", -1, now=self.now)

        with self.assertRaises(ValueError):
            self.scheduler.register("maintenance", -1, "maintenance.py")

    def test_registration_rejects_empty_callback(self) -> None:
        with self.assertRaises(ValueError):
            self.scheduler.register("maintenance", 60, " ")


class SchedulerCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.state_file = Path(self.temporary_directory.name) / "tasks.json"
        self.environment = patch.dict(
            "os.environ",
            {"ATLAS_SCHEDULER_STATE_FILE": str(self.state_file)},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_cli_register_inspect_list_and_remove(self) -> None:
        self.assertEqual(
            main(["register", "maintenance", "60", "maintenance.py"]),
            0,
        )
        self.assertEqual(main(["inspect", "maintenance"]), 0)
        self.assertEqual(main(["list"]), 0)
        self.assertEqual(main(["remove", "maintenance"]), 0)
        self.assertEqual(main(["inspect", "maintenance"]), 1)
