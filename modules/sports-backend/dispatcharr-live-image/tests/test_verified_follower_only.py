"""A verified follower may attach local readers without starting an upstream."""

import ast
import types
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "apps/proxy/live_proxy/server.py"
tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
method = next(node for node in ast.walk(tree)
              if isinstance(node, ast.FunctionDef)
              and node.name == "initialize_channel")
isolated = ast.Module(body=[ast.ClassDef(name="Server", bases=[], keywords=[],
    body=[method], decorator_list=[])], type_ignores=[])
ast.fix_missing_locations(isolated)


class Buffer:
    def __init__(self, *, channel_id, redis_client):
        self.channel_id = channel_id
        self.redis_client = redis_client


class Manager:
    def __init__(self, *, channel_id, redis_client, worker_id):
        self.channel_id = channel_id
        self.worker_id = worker_id


namespace = {
    "StreamBuffer": Buffer, "ClientManager": Manager,
    "RedisClient": types.SimpleNamespace(get_buffer=lambda: "buffer"),
    "close_old_connections": lambda: None,
}
exec(compile(isolated, str(SOURCE), "exec"), namespace)
Server = namespace["Server"]


def fixture(*, alias=True, owner="other-worker"):
    server = Server()
    server.redis_client = types.SimpleNamespace(exists=lambda key: alias)
    server.worker_id = "this-worker"
    server.stream_buffers = {}
    server.client_managers = {}
    server.get_channel_owner = lambda channel: owner
    server.try_acquire_ownership = lambda channel: (_ for _ in ()).throw(
        AssertionError("follower attempted ownership"))
    return server


class VerifiedFollowerTests(unittest.TestCase):
    def test_remote_owner_with_alias_attaches_only_local_reader(self):
        server = fixture()
        self.assertTrue(server.initialize_channel(None, 17,
                        verified_follower_only=True))
        self.assertEqual(server.stream_buffers[17].redis_client, "buffer")
        self.assertEqual(server.client_managers[17].worker_id, "this-worker")

    def test_missing_alias_or_remote_owner_refuses_attach(self):
        for server in (fixture(alias=False), fixture(owner=None),
                       fixture(owner="this-worker")):
            self.assertFalse(server.initialize_channel(None, 17,
                             verified_follower_only=True))
            self.assertEqual(server.stream_buffers, {})
            self.assertEqual(server.client_managers, {})

    def test_follower_rejects_owner_selection(self):
        server = fixture()
        self.assertFalse(server.initialize_channel(None, 17,
                         verified_follower_only=True,
                         verified_selection=object()))
        self.assertEqual(server.stream_buffers, {})


if __name__ == "__main__":
    unittest.main()
