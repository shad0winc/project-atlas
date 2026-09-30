"""Core Compose must use the configured pool, including in child processes."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CoreMediaRootTests(unittest.TestCase):
    def run_loader(self, *, inherited=False, module_override=False):
        with tempfile.TemporaryDirectory(prefix="atlas-config-test.") as directory:
            root = Path(directory)
            (root / "config" / "modules").mkdir(parents=True)
            (root / "config" / "atlas.conf").write_text(
                'ATLAS_MEDIA_ROOT="/pool with spaces/media"\n'
                'ATLAS_DOWNLOADS_ROOT="/pool with spaces/downloads"\n'
            )
            if module_override:
                (root / "config" / "modules" / "modules.conf").write_text(
                    'ATLAS_MEDIA_ROOT="/module pool/media"\n'
                )
            environment = os.environ.copy()
            for name in ("ATLAS_MEDIA_ROOT", "ATLAS_DOWNLOADS_ROOT"):
                environment.pop(name, None)
            environment["ATLAS_PROJECT_DIR"] = str(root)
            environment["MEDIA"] = "/legacy/media"
            if inherited:
                environment["ATLAS_MEDIA_ROOT"] = "/stale/media"
            result = subprocess.run(
                ["bash", "-c", 'set -euo pipefail; source "$1"; '
                 'atlas_load_config; bash -c \'printf "%s\\n" '
                 '"${ATLAS_MEDIA_ROOT:?}" "${ATLAS_DOWNLOADS_ROOT:?}"\'',
                 "test", str(ROOT / "scripts/lib/config.sh")],
                env=environment, capture_output=True, text=True,
                timeout=5, check=True,
            )
            return result.stdout.splitlines()

    def test_configured_roots_reach_child_without_manual_export(self):
        self.assertEqual(self.run_loader(), [
            "/pool with spaces/media", "/pool with spaces/downloads",
        ])

    def test_configuration_replaces_inherited_stale_root(self):
        self.assertEqual(self.run_loader(inherited=True)[0], "/pool with spaces/media")

    def test_final_module_configuration_reaches_child(self):
        self.assertEqual(self.run_loader(module_override=True)[0], "/module pool/media")

    def test_all_core_media_mounts_require_canonical_root(self):
        source = (ROOT / "docker-compose.yml").read_text()
        self.assertNotIn("${MEDIA}:/media", source)
        self.assertEqual(source.count(
            "${ATLAS_MEDIA_ROOT:?ATLAS_MEDIA_ROOT is required}:/media"
        ), 7)

    def test_missing_canonical_root_cannot_use_legacy_media(self):
        environment = os.environ.copy()
        environment.pop("ATLAS_MEDIA_ROOT", None)
        environment["MEDIA"] = "/legacy/media"
        result = subprocess.run(
            ["bash", "-c", 'printf "%s" "${ATLAS_MEDIA_ROOT:?ATLAS_MEDIA_ROOT is required}"'],
            env=environment, capture_output=True, text=True, timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
