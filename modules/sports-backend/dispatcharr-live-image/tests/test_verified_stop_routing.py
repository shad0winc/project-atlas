"""Ensure a failed verified close never reaches legacy cleanup or slot release."""

import ast
import logging
import time
import types
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "apps/proxy/live_proxy/server.py"
tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
method = next(node for node in ast.walk(tree)
              if isinstance(node, ast.FunctionDef) and node.name == "stop_channel")
isolated = ast.Module(body=[ast.ClassDef(name="Server", bases=[], keywords=[],
    body=[method], decorator_list=[])], type_ignores=[])
ast.fix_missing_locations(isolated)


class Keys:
    @staticmethod
    def channel_stopping(channel):
        return f"stopping:{channel}"


class Redis:
    def exists(self, key):
        return False

    def setex(self, key, ttl, value):
        pass


namespace = {"time": time, "RedisKeys": Keys, "logger": logging.getLogger(__name__)}
exec(compile(isolated, str(SOURCE), "exec"), namespace)
Server = namespace["Server"]


def fixture(*, receipt):
    server = Server()
    calls = []
    server.redis_client = Redis()
    server.worker_id = "worker"
    server._stopping_channels = set()
    server._stopping_since = {}
    server._verified_live_selections = {"channel": object()}
    server._owner_lease_values = {"channel": "worker|lease"}
    server.stream_managers = {"channel": object()}
    server._live_stream_managers = {}
    server.am_i_owner = lambda channel: True
    server._collect_channel_stop_event_data = lambda channel: None

    def record(label, value=None):
        calls.append(label)
        return value

    server._signal_upstream_shutdown = lambda channel: record("signal")
    server._close_verified_upstream_and_release = (
        lambda channel: record("close", receipt))
    server._release_verified_generation = lambda channel: record("revoke", True)
    server.release_ownership = lambda channel: record("owner_release")
    server._stop_local_stream_activity = lambda channel: record("local_stop")
    server._spawn_channel_stop_event = lambda data: record("event")
    server._clean_redis_keys = lambda channel: record("legacy_cleanup")
    return server, calls


class StopRoutingTests(unittest.TestCase):
    def test_failed_close_retains_owner_and_avoids_legacy_cleanup(self):
        server, calls = fixture(receipt=False)
        self.assertFalse(server.stop_channel("channel"))
        self.assertEqual(calls, ["signal", "close"])
        self.assertIn("channel", server._verified_live_selections)

    def test_success_closes_before_releasing_owner(self):
        server, calls = fixture(receipt=True)
        self.assertTrue(server.stop_channel("channel"))
        self.assertEqual(calls, ["signal", "close", "revoke",
                                 "owner_release", "local_stop", "event"])


if __name__ == "__main__":
    unittest.main()
