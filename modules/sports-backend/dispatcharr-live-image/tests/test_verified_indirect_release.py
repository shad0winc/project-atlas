"""Unexpected setup and viewer cleanup cannot consume a live owner slot."""

import ast
import logging
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def isolated_method(path, name):
    tree = ast.parse(path.read_text(), filename=str(path))
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == name)
    module = ast.Module(body=[ast.ClassDef(name="Subject", bases=[], keywords=[],
        body=[method], decorator_list=[])], type_ignores=[])
    ast.fix_missing_locations(module)
    scope = {"logger": logging.getLogger(__name__)}
    exec(compile(module, str(path), "exec"), scope)
    return scope["Subject"]


class Redis:
    def exists(self, key):
        return key == "atlas:reservation:v1:live:channel:channel"

    def get(self, key):
        raise AssertionError("legacy per-stream alias was inspected")


class IndirectReleaseTests(unittest.TestCase):
    def test_bound_setup_failure_uses_only_verified_stop(self):
        subject = isolated_method(
            ROOT / "apps/proxy/live_proxy/server.py", "_cleanup_failed_init")()
        subject._verified_live_selections = {"channel": object()}
        calls = []
        subject.stop_channel = lambda channel: calls.append(channel) or False
        self.assertIsNone(subject._cleanup_failed_init("channel"))
        self.assertEqual(calls, ["channel"])

    def test_viewer_model_release_refuses_live_alias(self):
        # Imports in the isolated method resolve to these existing staged
        # package modules only after a Django runtime; replace the import
        # statements with narrow static stubs for this lifecycle check.
        path = ROOT / "apps/channels/models.py"
        tree = ast.parse(path.read_text(), filename=str(path))
        channel_node = next(node for node in tree.body
                            if isinstance(node, ast.ClassDef)
                            and node.name == "Channel")
        method = next(node for node in channel_node.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "release_stream")
        method.body = [node for node in method.body
                       if not (isinstance(node, ast.ImportFrom)
                               and node.module == "apps.m3u.connection_pool")]
        module = ast.Module(body=[ast.ClassDef(name="Channel", bases=[], keywords=[],
            body=[method], decorator_list=[])], type_ignores=[])
        ast.fix_missing_locations(module)
        scope = {"RedisClient": type("Client", (), {"get_client": staticmethod(Redis)}),
                 "_require_legacy_counter_mode": lambda client: None}
        exec(compile(module, str(path), "exec"), scope)
        channel = scope["Channel"]()
        channel.uuid = "channel"
        self.assertFalse(channel.release_stream())

    def test_channel_selection_refuses_second_legacy_slot(self):
        path = ROOT / "apps/channels/models.py"
        tree = ast.parse(path.read_text(), filename=str(path))
        channel_node = next(node for node in tree.body
                            if isinstance(node, ast.ClassDef)
                            and node.name == "Channel")
        method = next(node for node in channel_node.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "get_stream")
        method.body = [node for node in method.body
                       if not (isinstance(node, ast.ImportFrom)
                               and node.module == "apps.m3u.connection_pool")]
        module = ast.Module(body=[ast.ClassDef(name="Channel", bases=[], keywords=[],
            body=[method], decorator_list=[])], type_ignores=[])
        ast.fix_missing_locations(module)
        scope = {"RedisClient": type("Client", (), {"get_client": staticmethod(Redis)}),
                 "_require_legacy_counter_mode": lambda client: None}
        exec(compile(module, str(path), "exec"), scope)
        channel = scope["Channel"]()
        channel.uuid = "channel"
        stream, profile, reason, reserved = channel.get_stream()
        self.assertIsNone(stream)
        self.assertIsNone(profile)
        self.assertFalse(reserved)
        self.assertEqual(reason, "Verified channel requires owner attestation")

    def test_legacy_profile_switch_refuses_live_alias(self):
        path = ROOT / "apps/channels/models.py"
        tree = ast.parse(path.read_text(), filename=str(path))
        channel_node = next(node for node in tree.body
                            if isinstance(node, ast.ClassDef)
                            and node.name == "Channel")
        method = next(node for node in channel_node.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "update_stream_profile")
        method.body = [node for node in method.body
                       if not (isinstance(node, ast.ImportFrom)
                               and node.module == "apps.m3u.connection_pool")]
        module = ast.Module(body=[ast.ClassDef(name="Channel", bases=[], keywords=[],
            body=[method], decorator_list=[])], type_ignores=[])
        ast.fix_missing_locations(module)
        scope = {"RedisClient": type("Client", (), {"get_client": staticmethod(Redis)}),
                 "_require_legacy_counter_mode": lambda client: None}
        exec(compile(module, str(path), "exec"), scope)
        channel = scope["Channel"]()
        channel.uuid = "channel"
        self.assertFalse(channel.update_stream_profile(44))


if __name__ == "__main__":
    unittest.main()
