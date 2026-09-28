"""Exercise the staged HTTP reader's strict close receipt without networking."""

import ast
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / (
    "apps/proxy/live_proxy/input/http_streamer.py"
)
tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
method = next(node for node in ast.walk(tree)
              if isinstance(node, ast.FunctionDef)
              and node.name == "stop_verified")
isolated = ast.Module(body=[ast.ClassDef(name="Reader", bases=[], keywords=[],
    body=[method], decorator_list=[])], type_ignores=[])
ast.fix_missing_locations(isolated)
namespace = {}
exec(compile(isolated, str(SOURCE), "exec"), namespace)
Reader = namespace["Reader"]


class Closable:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = 0

    def close(self):
        self.calls += 1
        if self.fail:
            raise OSError("synthetic close failure")


class Thread:
    def __init__(self, *, exits):
        self.exits = exits
        self.alive = True
        self.joined = False

    def is_alive(self):
        return self.alive

    def join(self, timeout):
        self.joined = True
        if self.exits:
            self.alive = False


def reader(*, close_fails=False, exits=True):
    obj = Reader()
    obj.running = True
    obj.response = Closable(fail=close_fails)
    obj.session = Closable()
    obj.pipe_write = None
    obj.thread = Thread(exits=exits)
    return obj


class CloseTests(unittest.TestCase):
    def test_closed_response_session_and_joined_reader_receipt(self):
        obj = reader()
        self.assertTrue(obj.stop_verified(timeout=0.1))
        self.assertFalse(obj.running)
        self.assertIsNone(obj.response)
        self.assertIsNone(obj.session)
        self.assertTrue(obj.thread.joined)

    def test_close_exception_or_live_thread_refuses_receipt(self):
        self.assertFalse(reader(close_fails=True).stop_verified(timeout=0.1))
        self.assertFalse(reader(exits=False).stop_verified(timeout=0.1))

    def test_missing_reader_or_open_pipe_refuses_receipt(self):
        obj = reader()
        obj.thread = None
        self.assertFalse(obj.stop_verified(timeout=0.1))
        obj = reader()
        obj.pipe_write = 99
        self.assertFalse(obj.stop_verified(timeout=0.1))


if __name__ == "__main__":
    unittest.main()
