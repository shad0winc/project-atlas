"""Explicit cleanup activation survives config loading and scheduler sync."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from atlas import scheduler_cli
from atlas.cleanup.scheduler import CLEANUP_EXECUTION_CALLBACK
from atlas.scheduler import TaskScheduler


ROOT = Path(__file__).resolve().parents[2]
ACTIVATION = "ATLAS_CLEANUP_EXECUTION_ENABLED"


class CleanupActivationTests(unittest.TestCase):
    def sync(self, scheduler, value, module=None):
        environment = os.environ.copy()
        environment.pop(ACTIVATION, None)
        if value is not None:
            environment[ACTIVATION] = value
        with patch.dict(os.environ, environment, clear=True), patch.object(
            scheduler_cli, "sync_module_jobs",
            return_value={"registered": [], "removed": [], "skipped": []},
        ):
            scheduler_cli._sync_scheduler_jobs(
                scheduler, Path("/unused"), Path("/unused/modules.json"), module,
            )

    def test_only_exact_true_activates_cleanup(self):
        for value in (None, "", "false", "TRUE", "1", " true ", "true"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                scheduler = TaskScheduler(Path(directory) / "tasks.json")
                self.sync(scheduler, value)
                task = next(row for row in scheduler.list_tasks()
                            if row["name"] == "cleanup.execute")
                self.assertEqual(task["enabled"], value == "true")
                self.assertEqual(task["callback"], CLEANUP_EXECUTION_CALLBACK)
                self.assertEqual(task["interval_seconds"], 3600)
                self.assertEqual(task["run_count"], 0)

    def test_repeated_sync_preserves_opt_in_and_revocation_disables(self):
        with tempfile.TemporaryDirectory() as directory:
            scheduler = TaskScheduler(Path(directory) / "tasks.json")
            self.sync(scheduler, "true")
            self.sync(scheduler, "true")
            task = next(row for row in scheduler.list_tasks()
                        if row["name"] == "cleanup.execute")
            self.assertTrue(task["enabled"])
            self.sync(scheduler, None)
            task = next(row for row in scheduler.list_tasks()
                        if row["name"] == "cleanup.execute")
            self.assertFalse(task["enabled"])

    def test_targeted_module_sync_does_not_register_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            scheduler = TaskScheduler(Path(directory) / "tasks.json")
            self.sync(scheduler, "true", "sports")
            self.assertEqual(scheduler.list_tasks(), [])

    def load_config_child(self, setting, inherited=None, module_setting=None):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            config = project / "config"
            (config / "modules").mkdir(parents=True)
            (config / "atlas.conf").write_text(
                "" if setting is None else f'{ACTIVATION}="{setting}"\n'
            )
            if module_setting is not None:
                (config / "modules/modules.conf").write_text(
                    f'{ACTIVATION}="{module_setting}"\n'
                )
            environment = os.environ.copy()
            environment.pop(ACTIVATION, None)
            environment["ATLAS_PROJECT_DIR"] = str(project)
            if inherited is not None:
                environment[ACTIVATION] = inherited
            return subprocess.check_output([
                "bash", "-c",
                'set -euo pipefail; source "$1"; atlas_load_config; '
                "bash -c 'printf \"%s\" \"${ATLAS_CLEANUP_EXECUTION_ENABLED-UNSET}\"'",
                "config-test", str(ROOT / "scripts/lib/config.sh"),
            ], env=environment, text=True, timeout=5)

    def test_unexported_configuration_reaches_child(self):
        self.assertEqual(self.load_config_child("true"), "true")

    def test_missing_configuration_does_not_activate_child(self):
        self.assertEqual(self.load_config_child(None), "UNSET")

    def test_configuration_can_revoke_inherited_activation(self):
        self.assertEqual(self.load_config_child("false", inherited="true"), "false")

    def test_final_module_configuration_reaches_child(self):
        self.assertEqual(self.load_config_child("true", module_setting="false"), "false")


if __name__ == "__main__":
    unittest.main()
