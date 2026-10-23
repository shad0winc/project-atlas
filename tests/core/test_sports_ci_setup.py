"""Exercise CI dependency setup without sudo, package downloads or live services."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/prepare-sports-runtime.sh"

# A private PATH makes absent binaries genuinely absent, even on FFmpeg hosts.
STUB = '''#!PYTHON
from pathlib import Path
import json, os, sys
root = Path(os.environ["FAKE_ROOT"])
name = Path(sys.argv[0]).name
with (root / "calls").open("a") as stream:
    stream.write(json.dumps([name, *sys.argv[1:]]) + "\\n")
if name == "sudo":
    assert sys.argv[1:4] == ["env", "DEBIAN_FRONTEND=noninteractive", "apt-get"]
    action = sys.argv[4]
    if os.environ.get("FAIL_APT") == action:
        sys.exit(42)
    if action == "install":
        assert sys.argv[5:] == ["-y", "--no-install-recommends", "ffmpeg"]
        for tool in ("ffmpeg", "ffprobe"):
            if os.environ.get("OMIT_TOOL") == tool:
                continue
            dest = root / tool
            dest.write_bytes(Path(__file__).read_bytes())
            dest.chmod(0o755)
        (root / "installed").touch()
elif name in ("ffmpeg", "ffprobe"):
    assert sys.argv[1:] == ["-version"]
    installed = (root / "installed").exists()
    if os.environ.get("BROKEN_TOOL") == name and not installed:
        sys.exit(43)
    if os.environ.get("BROKEN_AFTER") == name and installed:
        sys.exit(44)
    print(name + " version fixture")
else:
    raise AssertionError(name)
'''.replace("PYTHON", sys.executable, 1)


class SportsCISetupTests(unittest.TestCase):
    def run_setup(self, tools=("ffmpeg", "ffprobe"), **options):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("sudo", *tools):
                path = root / name
                path.write_text(STUB)
                path.chmod(0o755)
            result = subprocess.run(
                ["/bin/bash", str(SCRIPT)],
                env={"PATH": directory, "FAKE_ROOT": directory,
                     "PYTHONDONTWRITEBYTECODE": "1", **options},
                capture_output=True, timeout=15,
            )
            calls = [json.loads(row) for row in
                     (root / "calls").read_text().splitlines()]
            return result, calls

    def test_available_tools_need_no_package_manager(self):
        result, calls = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(row[0] == "sudo" for row in calls))
        self.assertIn(b"ffprobe version", result.stdout)

    def test_missing_tools_install_and_validate_both(self):
        for tools in ((), ("ffmpeg",), ("ffprobe",)):
            with self.subTest(tools=tools):
                result, calls = self.run_setup(tools)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([row[4] for row in calls if row[0] == "sudo"],
                                 ["update", "install"])
                self.assertEqual([row[0] for row in calls[-2:]],
                                 ["ffmpeg", "ffprobe"])

    def test_broken_available_tool_requires_install(self):
        for tool in ("ffmpeg", "ffprobe"):
            with self.subTest(tool=tool):
                result, calls = self.run_setup(BROKEN_TOOL=tool)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(any(row[0] == "sudo" for row in calls))

    def test_update_failure_stops_before_install(self):
        result, calls = self.run_setup((), FAIL_APT="update")
        self.assertEqual(result.returncode, 42)
        self.assertEqual([row[4] for row in calls if row[0] == "sudo"], ["update"])

    def test_install_failure_is_not_ignored(self):
        result, _ = self.run_setup((), FAIL_APT="install")
        self.assertEqual(result.returncode, 42)

    def test_install_success_without_tools_still_fails(self):
        for tool in ("ffmpeg", "ffprobe"):
            with self.subTest(tool=tool):
                result, _ = self.run_setup((), OMIT_TOOL=tool)
                self.assertNotEqual(result.returncode, 0)

    def test_broken_installed_tool_still_fails(self):
        for tool in ("ffmpeg", "ffprobe"):
            with self.subTest(tool=tool):
                result, _ = self.run_setup((), BROKEN_AFTER=tool)
                self.assertEqual(result.returncode, 44)


if __name__ == "__main__":
    unittest.main()
