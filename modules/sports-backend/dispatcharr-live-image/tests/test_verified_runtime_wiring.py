"""Default-off wiring installs both authorities or neither."""

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "apps/m3u/verified_live_runtime.py"
spec = importlib.util.spec_from_file_location("staged_verified_runtime", path)
runtime = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runtime
spec.loader.exec_module(runtime)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.key_path = Path(self.directory.name) / "scope.key"
        self.key_path.write_bytes(bytes(range(32)))
        self.env = {
            "ATLAS_VERIFIED_LIVE_MODE": "strict",
            "ATLAS_SPORTS_POLICY_ORIGIN": "http://atlas-sports-controller:9000",
            "ATLAS_SPORTS_LIVE_POLICY_TOKEN": "server-held-token-012345678901234567890",
            "ATLAS_VERIFIED_LIVE_SCOPE_KEY_FILE": str(self.key_path),
        }

    def test_off_and_partial_strict_never_install_one_authority(self):
        self.assertEqual(runtime.build_verified_live_dependencies({}), (None, None))
        for removed in (
            "ATLAS_SPORTS_POLICY_ORIGIN", "ATLAS_SPORTS_LIVE_POLICY_TOKEN",
            "ATLAS_VERIFIED_LIVE_SCOPE_KEY_FILE",
        ):
            with self.subTest(removed=removed):
                settings = dict(self.env)
                settings.pop(removed)
                with self.assertRaises(runtime.VerifiedLiveConfigurationError):
                    runtime.build_verified_live_dependencies(settings)
        with self.assertRaises(runtime.VerifiedLiveConfigurationError):
            runtime.build_verified_live_dependencies(dict(self.env,
                ATLAS_VERIFIED_LIVE_MODE="partial"))

    def test_strict_uses_one_server_held_origin_token_and_key(self):
        made = []
        def constructor(name):
            def create(**kwargs):
                made.append((name, kwargs))
                return name
            return create
        names = {
            "apps.m3u.atlas_channel_classification":
                ("AtlasManagedChannelClient", "classifier"),
            "apps.m3u.atlas_policy_claims": ("AtlasPolicyClaimClient", "claims"),
            "apps.m3u.atlas_verified_policy_adapter":
                ("AtlasVerifiedPolicyAdapter", "policy"),
            "apps.m3u.provider_capacity_observation":
                ("XtreamCapacityReader", "capacity"),
        }
        modules = {}
        for module_name, (class_name, value) in names.items():
            module = types.ModuleType(module_name)
            setattr(module, class_name, constructor(value))
            modules[module_name] = module
        credentials = types.ModuleType("apps.m3u.strict_effective_credentials")
        credentials.strict_effective_credentials = lambda *_: ()
        modules[credentials.__name__] = credentials
        with patch.dict(sys.modules, modules):
            self.assertEqual(runtime.build_verified_live_dependencies(self.env),
                             ("classifier", "policy"))
        self.assertEqual(made[0][1], {
            "origin": self.env["ATLAS_SPORTS_POLICY_ORIGIN"],
            "token": self.env["ATLAS_SPORTS_LIVE_POLICY_TOKEN"],
        })
        self.assertEqual(made[1][1], made[0][1])
        self.assertEqual(made[-1][1]["scope_key"], bytes(range(32)))
        self.assertIs(made[-1][1]["transformed_credentials"],
                      credentials.strict_effective_credentials)

    def test_bad_key_and_constructor_fail_without_secrets(self):
        for content in (b"short", b"long" * 20):
            self.key_path.write_bytes(content)
            with self.assertRaises(runtime.VerifiedLiveConfigurationError):
                runtime.build_verified_live_dependencies(self.env)
        self.key_path.unlink()
        self.key_path.symlink_to(Path(self.directory.name) / "elsewhere")
        with self.assertRaises(runtime.VerifiedLiveConfigurationError):
            runtime.build_verified_live_dependencies(self.env)
        self.key_path.unlink()
        self.key_path.write_bytes(bytes(range(32)))
        with self.assertRaises(runtime.VerifiedLiveConfigurationError) as error:
            runtime.build_verified_live_dependencies(dict(self.env,
                ATLAS_SPORTS_POLICY_ORIGIN="https://user:password@bad.example"))
        self.assertNotIn("password", str(error.exception))


if __name__ == "__main__":
    unittest.main()
