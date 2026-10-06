"""Exercise publication through real task execution without external work."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlas.dashboard_runtime import publish_scheduler_runtime
from atlas.scheduler import TaskScheduler, SchedulerLockedError
from atlas.scheduler_cli import main


class SchedulerSnapshotPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "tasks.json"
        self.snapshot = self.root / "dashboard/scheduler.json"
        environment = patch.dict("os.environ", {
            "ATLAS_RUNTIME_CONFIG_DIR": str(self.root),
            "ATLAS_SCHEDULER_STATE_FILE": str(self.state),
            "ATLAS_DASHBOARD_SCHEDULER_SNAPSHOT_PATH": str(self.snapshot),
        })
        environment.start()
        self.addCleanup(environment.stop)
        for name in ("chown", "fchown"):
            ownership = patch("atlas.dashboard_runtime.os." + name, lambda *args: None)
            ownership.start()
            self.addCleanup(ownership.stop)
        self.scheduler = TaskScheduler(self.state)

    def invoke(self, args):
        with contextlib.redirect_stdout(io.StringIO()):
            return main(args)

    def payload(self):
        return json.loads(self.snapshot.read_bytes())

    def test_success_is_published_after_recording_without_a_second_execution(self):
        self.scheduler.register("requests.reconcile", 60, "/bin/true")
        self.assertEqual(self.invoke(["run", "requests.reconcile"]), 0)
        task = self.payload()["tasks"][0]
        self.assertEqual(task["status"], "healthy")
        self.assertEqual(task["run_count"], 1)
        self.assertEqual(task["last_success"], self.scheduler.task_state(task["name"])["last_success"])
        self.assertNotIn("callback", task)
        self.assertEqual(self.snapshot.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.invoke(["run", "--due-only"]), 0)
        self.assertEqual(self.scheduler.task_state(task["name"])["run_count"], 1)

    def test_failed_task_is_published_without_claiming_success(self):
        self.scheduler.register("failure", 60, "/bin/false")
        self.assertEqual(self.invoke(["run", "failure"]), 1)
        row = self.payload()["tasks"][0]
        self.assertEqual(row["status"], "degraded")
        self.assertEqual(row["consecutive_failures"], 1)
        self.assertFalse(row.get("last_success"))

    def test_publication_failure_preserves_success_and_never_reexecutes(self):
        self.scheduler.register("success", 60, "/bin/true")
        error = io.StringIO()
        with patch("atlas.scheduler_cli.publish_scheduler_runtime", side_effect=RuntimeError("SECRET")), contextlib.redirect_stderr(error):
            self.assertEqual(self.invoke(["run", "success"]), 4)
        self.assertNotIn("SECRET", error.getvalue())
        self.assertIn("records are preserved", error.getvalue())
        row = self.scheduler.task_state("success")
        self.assertEqual(row["run_count"], 1)
        self.assertEqual(row["status"], "healthy")
        self.assertFalse(self.snapshot.exists())

    def test_empty_due_run_publishes_but_read_only_commands_do_not(self):
        self.assertEqual(self.invoke(["run", "--due-only"]), 0)
        self.assertEqual(self.payload()["tasks"], [])
        before = self.snapshot.read_bytes()
        for command in (["list"], ["history"], ["dry-run"]):
            self.assertEqual(self.invoke(command), 0)
        self.assertEqual(self.snapshot.read_bytes(), before)

    def test_failed_atomic_replace_preserves_previous_observation(self):
        self.assertEqual(self.invoke(["run", "--due-only"]), 0)
        before = self.snapshot.read_bytes()
        self.scheduler.register("success", 60, "/bin/true")
        replace = os.replace
        def fail_snapshot_replace(source, target):
            if Path(target) == self.snapshot:
                raise OSError("SECRET")
            return replace(source, target)
        with patch("atlas.dashboard_runtime.os.replace", side_effect=fail_snapshot_replace), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.invoke(["run", "success"]), 4)
        self.assertEqual(self.snapshot.read_bytes(), before)
        self.assertEqual(self.scheduler.task_state("success")["run_count"], 1)
        self.assertEqual(list(self.snapshot.parent.glob(".scheduler.json.*")), [])

    def test_locked_run_does_not_publish_or_execute(self):
        self.scheduler.register("success", 60, "/bin/true")
        with patch("atlas.scheduler_cli.deployment_scheduler_execution_lock", side_effect=SchedulerLockedError("locked")), patch("atlas.scheduler_cli.publish_scheduler_runtime") as publisher:
            self.assertEqual(self.invoke(["run"]), 3)
            publisher.assert_not_called()
        self.assertEqual(self.scheduler.task_state("success")["run_count"], 0)

    def test_projection_is_sanitized_and_preserves_authoritative_state(self):
        self.scheduler.register("failure", 60, "/bin/false")
        self.scheduler.failed("failure", "SECRET-TOKEN-URL")
        before = self.state.read_bytes()
        publish_scheduler_runtime(self.scheduler, self.snapshot)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertNotIn("SECRET-TOKEN-URL", self.snapshot.read_text())
        self.assertEqual(self.payload()["tasks"][0]["last_error"], "Scheduler task failed.")
