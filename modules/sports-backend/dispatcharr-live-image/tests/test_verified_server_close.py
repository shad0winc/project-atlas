"""Close-gated ledger release from the staged owning server method."""

import ast
import sys
import threading
import types
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / (
    "apps/proxy/live_proxy/server.py"
)
tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
method = next(node for node in ast.walk(tree)
              if isinstance(node, ast.FunctionDef)
              and node.name == "_close_verified_upstream_and_release")
isolated = ast.Module(body=[ast.ClassDef(name="Server", bases=[], keywords=[],
    body=[method], decorator_list=[])], type_ignores=[])
ast.fix_missing_locations(isolated)
namespace = {"threading": threading}
exec(compile(isolated, str(SOURCE), "exec"), namespace)
Server = namespace["Server"]


class FakeThread:
    def __init__(self, exits=True):
        self.alive = True
        self.exits = exits

    def is_alive(self):
        return self.alive

    def join(self, timeout):
        if self.exits:
            self.alive = False


def fixture(*, closes=True, exits=True, cleans=True):
    server = Server()
    server.redis_client = object()
    server._verified_live_selections = {
        "channel-a": types.SimpleNamespace(
            owner_lease="worker|lease", stream_id=11,
            spec=object(), token="reservation-token")}
    server._verified_live_start_attempted = {"channel-a"}
    server._owner_lease_values = {"channel-a": "worker|lease"}
    server.am_i_owner = lambda _channel: True
    server._local_stop_locks = {}
    server._get_local_stop_lock = lambda channel: server._local_stop_locks.setdefault(
        channel, threading.Lock())
    manager = types.SimpleNamespace(
        current_stream_id=11, _verified_generation_required=True,
        _legacy_owner_identity="worker|lease",
        _verified_grant_token="grant-token", _verified_grant_epoch=4,
        _verified_generation_id="4-fresh", http_reader=object(),
        socket=object(), transcode_process=None,
    )
    def stop():
        if closes:
            manager.http_reader = None
            manager.socket = None
        return closes
    manager.stop_verified_http_upstream = stop
    server.stream_managers = {"channel-a": manager}
    server._live_stream_managers = {}
    thread = FakeThread(exits)
    server._get_stream_thread = lambda _channel: thread
    server._clean_verified_media_keys = (
        lambda *args, **kwargs: cleans)
    return server


class CloseTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.parents = {
            name: sys.modules.get(name) for name in ("apps", "apps.m3u")
        }
        for name in self.parents:
            sys.modules.setdefault(name, types.ModuleType(name))
        module = types.ModuleType("apps.m3u.reservation_ledger")
        module.mark_live_upstream_closed = (
            lambda *args, **kwargs: self.calls.append("ack") or True)
        module.release_active_live_channel = (
            lambda *args, **kwargs: self.calls.append("release") or True)
        self.original = sys.modules.get(module.__name__)
        sys.modules[module.__name__] = module

    def tearDown(self):
        key = "apps.m3u.reservation_ledger"
        if self.original is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = self.original
        for name, original in self.parents.items():
            if original is None:
                sys.modules.pop(name, None)

    def test_close_then_ack_then_release(self):
        server = fixture()
        self.assertTrue(server._close_verified_upstream_and_release("channel-a"))
        self.assertEqual(self.calls, ["ack", "release"])
        self.assertNotIn("channel-a", server._verified_live_selections)

    def test_unclosed_socket_or_live_thread_keeps_capacity(self):
        self.assertFalse(fixture(closes=False)._close_verified_upstream_and_release(
            "channel-a"))
        self.assertFalse(fixture(exits=False)._close_verified_upstream_and_release(
            "channel-a"))
        self.assertEqual(self.calls, [])

    def test_media_cleanup_failure_retains_reservation(self):
        server = fixture(cleans=False)
        self.assertFalse(server._close_verified_upstream_and_release("channel-a"))
        self.assertEqual(self.calls, ["ack"])
        self.assertIn("channel-a", server._verified_live_selections)

    def test_replaced_owner_keeps_capacity(self):
        server = fixture()
        server._owner_lease_values["channel-a"] = "replacement"
        self.assertFalse(server._close_verified_upstream_and_release("channel-a"))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
