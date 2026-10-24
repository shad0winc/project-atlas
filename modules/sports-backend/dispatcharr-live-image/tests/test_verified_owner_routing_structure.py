"""Check that the staged owner branch cannot call legacy allocation."""

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWS = ast.parse((ROOT / "apps/proxy/live_proxy/views.py").read_text())
SERVER = ast.parse((ROOT / "apps/proxy/live_proxy/server.py").read_text())


def called(node, name):
    return any(isinstance(child, ast.Call)
               and isinstance(child.func, ast.Name)
               and child.func.id == name for child in ast.walk(node))


class OwnerRoutingStructureTests(unittest.TestCase):
    def test_verified_owner_branch_never_calls_legacy_allocator(self):
        stream_ts = next(node for node in VIEWS.body
                         if isinstance(node, ast.FunctionDef)
                         and node.name == "stream_ts")
        branches = [node for node in ast.walk(stream_ts)
                    if isinstance(node, ast.If)
                    and ast.unparse(node.test) == "owner_mode == 'verified'"
                    and node.orelse]
        self.assertEqual(len(branches), 1)
        branch = branches[0]
        self.assertTrue(any(called(node, "generate_verified_stream_url")
                            for node in branch.body))
        self.assertFalse(any(called(node, "generate_stream_url")
                             for node in branch.body))
        self.assertTrue(any(called(node, "generate_stream_url")
                            for node in branch.orelse))
        self.assertFalse(any(isinstance(node, ast.Attribute)
                             and node.attr == "release_stream"
                             for arm in branch.body for node in ast.walk(arm)))

    def test_verified_follower_cannot_start_an_upstream(self):
        stream_ts = next(node for node in VIEWS.body
                         if isinstance(node, ast.FunctionDef)
                         and node.name == "stream_ts")
        calls = [node for node in ast.walk(stream_ts)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "initialize_channel"
                 and isinstance(node.func.value, ast.Name)
                 and node.func.value.id == "proxy_server"]
        self.assertEqual(len(calls), 1)
        keyword = next(item for item in calls[0].keywords
                       if item.arg == "verified_follower_only")
        self.assertEqual(ast.unparse(keyword.value), "owner_mode == 'verified'")

        server = next(node for node in SERVER.body
                      if isinstance(node, ast.ClassDef)
                      and node.name == "ProxyServer")
        initialize = next(node for node in server.body
                          if isinstance(node, ast.FunctionDef)
                          and node.name == "initialize_channel")
        first_try = initialize.body[1]
        self.assertIsInstance(first_try, ast.Try)
        first_branch = first_try.body[0]
        self.assertEqual(ast.unparse(first_branch.test), "verified_follower_only")
        self.assertTrue(any(isinstance(node, ast.Return)
                            for node in ast.walk(first_branch)))
        self.assertFalse(any(isinstance(node, ast.Attribute)
                             and node.attr == "try_acquire_ownership"
                             for node in ast.walk(first_branch)))


if __name__ == "__main__":
    unittest.main()
