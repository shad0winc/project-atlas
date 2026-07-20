from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from atlas.scheduler import SchedulerLockedError, TaskScheduler
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
        self.assertEqual(parsed_state["schema_version"], 2)
        self.assertIn("tasks", parsed_state)

    def test_negative_interval_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.scheduler.due("maintenance", -1, now=self.now)

        with self.assertRaises(ValueError):
            self.scheduler.register("maintenance", -1, "maintenance.py")

    def test_registration_rejects_empty_callback(self) -> None:
        with self.assertRaises(ValueError):
            self.scheduler.register("maintenance", 60, " ")

    def test_run_task_success_updates_history(self) -> None:
        events: list[tuple[str, dict[str, object]]] = []
        scheduler = TaskScheduler(
            self.state_file,
            event_publisher=lambda name, payload: events.append((name, dict(payload))),
        )
        scheduler.register("success", 60, "/bin/true")

        result = scheduler.run_task("success")

        self.assertEqual(result.result, "success")
        self.assertEqual(result.return_code, 0)
        state = scheduler.task_state("success")
        self.assertEqual(state["run_count"], 1)
        self.assertEqual(state["status"], "healthy")
        self.assertEqual(scheduler.history(1)[0]["task"], "success")
        self.assertEqual([event[0] for event in events], [
            "scheduler.task.started",
            "scheduler.task.completed",
        ])

    def test_run_task_failure_records_error(self) -> None:
        self.scheduler.register("failure", 60, "/bin/false")

        result = self.scheduler.run_task("failure")

        self.assertEqual(result.result, "failed")
        self.assertNotEqual(result.return_code, 0)
        state = self.scheduler.task_state("failure")
        self.assertEqual(state["failure_count"], 1)
        self.assertEqual(state["consecutive_failures"], 1)
        self.assertEqual(state["status"], "degraded")

    def test_run_due_tasks_skips_disabled_and_not_due(self) -> None:
        self.scheduler.register("due", 60, "/bin/true")
        self.scheduler.register("disabled", 60, "/bin/true", enabled=False)
        self.scheduler.register("recent", 3600, "/bin/true")
        self.scheduler.succeeded("recent", now=datetime.now(timezone.utc))

        results = self.scheduler.run_due_tasks()

        self.assertEqual([result.task for result in results], ["due"])

    def test_dry_run_does_not_execute(self) -> None:
        marker = Path(self.temporary_directory.name) / "marker"
        self.scheduler.register("touch", 60, f"/usr/bin/touch {marker}")

        tasks = self.scheduler.dry_run()

        self.assertEqual([task["name"] for task in tasks], ["touch"])
        self.assertFalse(marker.exists())

    def test_runtime_lock_prevents_overlap(self) -> None:
        self.scheduler.register("success", 60, "/bin/true")
        self.scheduler.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.scheduler.lock_file.write_text(f"{__import__('os').getpid()}\n", encoding="utf-8")

        with self.assertRaises(SchedulerLockedError):
            self.scheduler.run_due_tasks()

    def test_history_is_bounded(self) -> None:
        self.scheduler.register("success", 0, "/bin/true")
        with patch.object(self.scheduler, "HISTORY_LIMIT", 2):
            self.scheduler.run_task("success")
            self.scheduler.run_task("success")
            self.scheduler.run_task("success")

        self.assertEqual(len(self.scheduler.history(10)), 2)

    def test_event_failure_does_not_fail_task(self) -> None:
        def fail_event(name: str, payload: dict[str, object]) -> None:
            raise RuntimeError("event unavailable")

        scheduler = TaskScheduler(self.state_file, event_publisher=fail_event)
        scheduler.register("success", 60, "/bin/true")

        result = scheduler.run_task("success")

        self.assertEqual(result.result, "success")
        self.assertEqual(result.event_error, "event unavailable")


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
    def test_cli_run_dry_run_and_history(self) -> None:
        self.assertEqual(main(["register", "success", "0", "/bin/true"]), 0)
        self.assertEqual(main(["dry-run"]), 0)
        self.assertEqual(main(["run"]), 0)
        self.assertEqual(main(["history", "--limit", "1"]), 0)

    def test_cli_failed_task_returns_one(self) -> None:
        self.assertEqual(main(["register", "failure", "0", "/bin/false"]), 0)
        self.assertEqual(main(["run", "failure"]), 1)


class ModuleSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.project_directory = Path(self.temporary_directory.name)
        self.modules_directory = self.project_directory / "modules"
        self.registry_file = self.project_directory / "config" / "modules" / "modules.conf"
        self.registry_file.parent.mkdir(parents=True)
        self.state_file = self.project_directory / "scheduler.json"
        self.scheduler = TaskScheduler(self.state_file)

    def _write_module(self, name: str, manifest: dict[str, object]) -> None:
        module_directory = self.modules_directory / name
        (module_directory / "scripts").mkdir(parents=True, exist_ok=True)
        callback = module_directory / "scripts" / "job.py"
        callback.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        (module_directory / "scheduler.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    def _sync(self, module_name: str | None = None) -> dict[str, object]:
        from atlas.module_scheduler import sync_module_jobs

        return sync_module_jobs(
            self.scheduler,
            self.project_directory,
            self.registry_file,
            module_name,
        )

    def test_sync_registers_enabled_module_jobs(self) -> None:
        self.registry_file.write_text("ATLAS_MODULE_SPORTS_ENABLED=true\n", encoding="utf-8")
        self._write_module(
            "sports",
            {
                "schema_version": 1,
                "jobs": [{
                    "name": "provider-sync",
                    "callback": "scripts/job.py",
                    "interval_seconds": 300,
                    "description": "Refresh providers",
                    "enabled": True,
                }],
            },
        )

        result = self._sync()
        task = self.scheduler.task_state("sports.provider-sync")

        self.assertEqual(result["registered"], ["sports.provider-sync"])
        self.assertEqual(task["module"], "sports")
        self.assertEqual(task["callback"], "modules/sports/scripts/job.py")

    def test_sync_updates_definition_and_preserves_runtime_state(self) -> None:
        self.registry_file.write_text("ATLAS_MODULE_SPORTS_ENABLED=true\n", encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "jobs": [{
                "name": "provider-sync",
                "callback": "scripts/job.py",
                "interval_seconds": 300,
            }],
        }
        self._write_module("sports", manifest)
        self._sync()
        self.scheduler.succeeded("sports.provider-sync", now=datetime.now(timezone.utc))
        manifest["jobs"][0]["interval_seconds"] = 600
        self._write_module("sports", manifest)

        self._sync("sports")
        task = self.scheduler.task_state("sports.provider-sync")

        self.assertEqual(task["interval_seconds"], 600)
        self.assertEqual(task["run_count"], 1)

    def test_sync_removes_stale_module_jobs(self) -> None:
        self.registry_file.write_text("ATLAS_MODULE_SPORTS_ENABLED=true\n", encoding="utf-8")
        self._write_module(
            "sports",
            {"schema_version": 1, "jobs": [{
                "name": "old", "callback": "scripts/job.py", "interval_seconds": 60
            }]},
        )
        self._sync()
        self._write_module("sports", {"schema_version": 1, "jobs": []})

        result = self._sync()

        self.assertEqual(result["removed"], ["sports.old"])
        self.assertEqual(self.scheduler.task_state("sports.old"), {})

    def test_disabled_module_jobs_are_removed(self) -> None:
        self.registry_file.write_text("ATLAS_MODULE_SPORTS_ENABLED=true\n", encoding="utf-8")
        self._write_module(
            "sports",
            {"schema_version": 1, "jobs": [{
                "name": "sync", "callback": "scripts/job.py", "interval_seconds": 60
            }]},
        )
        self._sync()
        self.registry_file.write_text("ATLAS_MODULE_SPORTS_ENABLED=false\n", encoding="utf-8")

        result = self._sync()

        self.assertEqual(result["removed"], ["sports.sync"])
        self.assertIn("sports", result["skipped"])

    def test_sync_rejects_callback_escape(self) -> None:
        self.registry_file.write_text("ATLAS_MODULE_SPORTS_ENABLED=true\n", encoding="utf-8")
        self._write_module(
            "sports",
            {"schema_version": 1, "jobs": [{
                "name": "unsafe", "callback": "../../outside.py", "interval_seconds": 60
            }]},
        )

        with self.assertRaisesRegex(ValueError, "escapes module directory"):
            self._sync()

    def test_sync_rejects_malformed_manifest(self) -> None:
        self.registry_file.write_text("ATLAS_MODULE_SPORTS_ENABLED=true\n", encoding="utf-8")
        module_directory = self.modules_directory / "sports"
        module_directory.mkdir(parents=True)
        (module_directory / "scheduler.json").write_text("not json", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "invalid scheduler manifest"):
            self._sync()

    def test_sync_specific_unknown_module_is_rejected(self) -> None:
        self.registry_file.write_text("ATLAS_MODULE_SPORTS_ENABLED=true\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "module not found"):
            self._sync("unknown")


class SportsSchedulerManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_directory = Path(__file__).resolve().parents[2]

    def test_sports_maintenance_uses_module_command_callback(self) -> None:
        manifest = json.loads(
            (
                self.project_directory
                / "modules"
                / "sports"
                / "scheduler.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(len(manifest["jobs"]), 1)
        job = manifest["jobs"][0]
        self.assertEqual(job["name"], "maintenance")
        self.assertEqual(job["callback"], "scripts/maintenance_job.py")
        self.assertEqual(job["interval_seconds"], 3600)

    def test_sports_worker_has_no_private_scheduler(self) -> None:
        worker_source = (
            self.project_directory
            / "modules"
            / "sports"
            / "src"
            / "worker.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("TaskScheduler", worker_source)
        self.assertNotIn("run_scheduled_maintenance", worker_source)


class ModuleSchedulerCliTests(unittest.TestCase):
    def test_cli_sync_registers_module_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            module = project / "modules" / "sports"
            (module / "scripts").mkdir(parents=True)
            (module / "scripts" / "job.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (module / "scheduler.json").write_text(
                json.dumps({"schema_version": 1, "jobs": [{
                    "name": "sync",
                    "callback": "scripts/job.py",
                    "interval_seconds": 60,
                }]}),
                encoding="utf-8",
            )
            registry = project / "config" / "modules" / "modules.conf"
            registry.parent.mkdir(parents=True)
            registry.write_text("ATLAS_MODULE_SPORTS_ENABLED=true\n", encoding="utf-8")
            state = project / "tasks.json"
            with patch.dict("os.environ", {
                "ATLAS_PROJECT_DIR": str(project),
                "ATLAS_MODULES_CONFIG_FILE": str(registry),
                "ATLAS_SCHEDULER_STATE_FILE": str(state),
            }):
                self.assertEqual(main(["sync", "sports"]), 0)
            stored = json.loads(state.read_text(encoding="utf-8"))
            self.assertIn("sports.sync", stored["tasks"])
