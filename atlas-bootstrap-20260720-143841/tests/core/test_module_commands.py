from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from atlas.module_commands import (
    execute_module_command,
    module_commands,
)


class ModuleCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_directory = Path(self.temporary_directory.name)
        self.registry_file = (
            self.project_directory / "config" / "modules" / "modules.conf"
        )
        self.registry_file.parent.mkdir(parents=True)
        self.registry_file.write_text(
            "ATLAS_MODULE_SPORTS_ENABLED=true\n"
            "ATLAS_MODULE_DISABLED_ENABLED=false\n",
            encoding="utf-8",
        )
        self.module_directory = self.project_directory / "modules" / "sports"
        (self.module_directory / "src").mkdir(parents=True)
        self.callback = self.module_directory / "src" / "command.py"
        self.callback.write_text("raise SystemExit(0)\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_manifest(self, commands: object) -> None:
        (self.module_directory / "commands.json").write_text(
            json.dumps({"schema_version": 1, "commands": commands}),
            encoding="utf-8",
        )

    def test_lists_normalized_commands(self) -> None:
        self.write_manifest(
            {
                "sync": {
                    "callback": "src/command.py",
                    "arguments": ["sync"],
                    "description": "Synchronize data",
                }
            }
        )

        commands = module_commands(
            self.project_directory,
            self.registry_file,
            "sports",
        )

        self.assertEqual([command.name for command in commands], ["sync"])
        self.assertEqual(commands[0].arguments, ("sync",))

    def test_disabled_module_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "module is disabled"):
            module_commands(
                self.project_directory,
                self.registry_file,
                "disabled",
            )

    def test_unknown_module_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "module not found"):
            module_commands(
                self.project_directory,
                self.registry_file,
                "missing",
            )

    def test_missing_manifest_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "manifest not found"):
            module_commands(
                self.project_directory,
                self.registry_file,
                "sports",
            )

    def test_callback_escape_is_rejected(self) -> None:
        outside = self.project_directory / "outside.py"
        outside.write_text("raise SystemExit(0)\n", encoding="utf-8")
        self.write_manifest(
            {"unsafe": {"callback": "../../outside.py"}}
        )

        with self.assertRaisesRegex(ValueError, "escapes module directory"):
            module_commands(
                self.project_directory,
                self.registry_file,
                "sports",
            )

    def test_unknown_command_is_rejected(self) -> None:
        self.write_manifest(
            {"known": {"callback": "src/command.py"}}
        )

        with self.assertRaisesRegex(ValueError, "unknown module command"):
            execute_module_command(
                self.project_directory,
                self.registry_file,
                "sports",
                "missing",
            )

    @patch("atlas.module_commands.subprocess.run")
    def test_execution_uses_argument_list_and_propagates_return_code(
        self,
        run_mock,
    ) -> None:
        run_mock.return_value.returncode = 7
        self.write_manifest(
            {
                "sync": {
                    "callback": "src/command.py",
                    "arguments": ["sync"],
                }
            }
        )

        return_code = execute_module_command(
            self.project_directory,
            self.registry_file,
            "sports",
            "sync",
            ["--force", "value with spaces"],
        )

        self.assertEqual(return_code, 7)
        invocation = run_mock.call_args.args[0]
        self.assertEqual(
            invocation[-3:],
            ["sync", "--force", "value with spaces"],
        )
        self.assertNotIn("shell", run_mock.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
