"""A failed setup rolls back only when the producer was never attempted."""

import ast
import sys
import types
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "apps/proxy/live_proxy/server.py"
tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
              and node.name == "rollback_unstarted_verified_selection")
module = ast.Module(body=[ast.ClassDef(name="Server", bases=[], keywords=[],
    body=[method], decorator_list=[])], type_ignores=[])
ast.fix_missing_locations(module)


class Selection:
    channel_id = "channel"
    owner_lease = "worker|lease"

    def __init__(self):
        self.calls = 0

    def rollback_pending(self, client):
        self.calls += 1
        return True


class Redis:
    def __init__(self, grant=False):
        self.grant = grant

    def exists(self, key):
        return self.grant


class Authority:
    @staticmethod
    def _keys(channel):
        return ("grant", "epoch", "generation")


scope = {"GenerationAuthority": Authority,
         "__name__": "apps.proxy.live_proxy.server",
         "__package__": "apps.proxy.live_proxy"}
exec(compile(module, str(SOURCE), "exec"), scope)


class PendingRollbackTests(unittest.TestCase):
    def setUp(self):
        self.original = {name: sys.modules.get(name) for name in
                         ("apps", "apps.proxy", "apps.proxy.live_proxy",
                          "apps.proxy.live_proxy.verified_selection")}
        for name in self.original:
            sys.modules.setdefault(name, types.ModuleType(name))
        sys.modules["apps.proxy.live_proxy.verified_selection"].VerifiedLiveSelection = Selection
        self.server_module = sys.modules.get("apps.proxy.live_proxy.server")
        sys.modules["apps.proxy.live_proxy.server"] = types.ModuleType(
            "apps.proxy.live_proxy.server")

    def tearDown(self):
        if self.server_module is None:
            sys.modules.pop("apps.proxy.live_proxy.server", None)
        else:
            sys.modules["apps.proxy.live_proxy.server"] = self.server_module
        for name, original in self.original.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def fixture(self, *, attempted=False, manager=False, grant=False):
        obj = scope["Server"]()
        selection = Selection()
        obj._owner_lease_values = {"channel": "worker|lease"}
        obj._verified_live_start_attempted = {"channel"} if attempted else set()
        obj._verified_live_selections = {"channel": selection}
        obj.stream_managers = {"channel": object()} if manager else {}
        obj._live_stream_managers = {}
        obj._get_stream_thread = lambda channel: None
        obj.am_i_owner = lambda channel: True
        obj.redis_client = Redis(grant)
        obj.release_ownership = lambda channel, signal_stopping: None
        return obj, selection

    def test_unstarted_pending_selection_uses_exact_token_rollback(self):
        obj, selection = self.fixture()
        self.assertTrue(obj.rollback_unstarted_verified_selection(selection))
        self.assertEqual(selection.calls, 1)
        self.assertNotIn("channel", obj._verified_live_selections)

    def test_attempted_start_manager_or_grant_retain_capacity(self):
        for kwargs in ({"attempted": True}, {"manager": True},
                       {"grant": True}):
            with self.subTest(kwargs=kwargs):
                obj, selection = self.fixture(**kwargs)
                self.assertFalse(obj.rollback_unstarted_verified_selection(selection))
                self.assertEqual(selection.calls, 0)
                self.assertIn("channel", obj._verified_live_selections)


if __name__ == "__main__":
    unittest.main()
