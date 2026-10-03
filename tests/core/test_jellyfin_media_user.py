"""Jellyfin must use the configured media identity without losing GPU access."""

import os
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]


class JellyfinMediaUserTests(unittest.TestCase):
    def block(self):
        source = (ROOT / "docker-compose.yml").read_text()
        match = re.search(r"(?ms)^  jellyfin:\n.*?(?=^  [a-z]|\Z)", source)
        self.assertIsNotNone(match)
        return match.group(0)

    def identity(self, uid, gid):
        match = re.search(r'^    user: "([^"]+)"$', self.block(), re.M)
        self.assertIsNotNone(match)
        environment = os.environ.copy()
        for name, value in (("PUID", uid), ("PGID", gid)):
            environment.pop(name, None)
            if value is not None:
                environment[name] = value
        return subprocess.run(
            ["bash", "-c", 'printf "%s" "' + match.group(1) + '"'],
            env=environment, capture_output=True, text=True, timeout=5,
        )

    def test_configured_media_identity_replaces_root(self):
        result = self.identity("1000", "1000")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "1000:1000")

    def test_identity_follows_configuration(self):
        result = self.identity("1001", "1002")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "1001:1002")

    def test_missing_or_empty_identity_fails_closed(self):
        for uid, gid in ((None, "1000"), ("1000", None), ("", "1000"), ("1000", "")):
            with self.subTest(uid=uid, gid=gid):
                result = self.identity(uid, gid)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

    def test_gpu_device_and_supplementary_groups_remain(self):
        block = self.block()
        self.assertIn("      - /dev/dri:/dev/dri\n", block)
        self.assertIn('    group_add:\n      - "44"\n      - "104"\n', block)

    def test_config_cache_and_canonical_media_mounts_remain(self):
        block = self.block()
        for mount in (
            "${CONFIG}/jellyfin:/config",
            "${CONFIG}/jellyfin-cache:/cache",
            "${ATLAS_MEDIA_ROOT:?ATLAS_MEDIA_ROOT is required}:/media",
        ):
            self.assertIn("      - " + mount + "\n", block)


if __name__ == "__main__":
    unittest.main()
