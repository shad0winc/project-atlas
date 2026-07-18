from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlas.scheduler import TaskScheduler


class TaskSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.state_file = (
            Path(self.temporary_directory.name)
            / "scheduler.json"
        )
        self.scheduler = TaskScheduler(self.state_file)
        self.now = datetime(
            2026,
            7,
            18,
            12,
            0,
            tzinfo=timezone.utc,
        )

    def test_new_task_is_immediately_due(self) -> None:
        self.assertTrue(
            self.scheduler.due(
                "maintenance",
                3600,
                now=self.now,
            )
        )

    def test_task_lifecycle_is_persisted(self) -> None:
        self.scheduler.started(
            "maintenance",
            now=self.now,
        )

        running = self.scheduler.task_state("maintenance")
        self.assertEqual(running["status"], "running")

        self.scheduler.succeeded(
            "maintenance",
            now=self.now,
            details={"removed": 2},
        )

        self.assertFalse(
            self.scheduler.due(
                "maintenance",
                3600,
                now=self.now + timedelta(minutes=30),
            )
        )
        self.assertTrue(
            self.scheduler.due(
                "maintenance",
                3600,
                now=self.now + timedelta(hours=1),
            )
        )

        self.scheduler.failed(
            "maintenance",
            "simulated failure",
            now=self.now + timedelta(hours=1),
        )

        failed = self.scheduler.task_state("maintenance")
        self.assertEqual(failed["status"], "degraded")
        self.assertEqual(failed["consecutive_failures"], 1)

        parsed_state = json.loads(
            self.state_file.read_text(encoding="utf-8")
        )
        self.assertIn("tasks", parsed_state)

    def test_negative_interval_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.scheduler.due(
                "maintenance",
                -1,
                now=self.now,
            )
