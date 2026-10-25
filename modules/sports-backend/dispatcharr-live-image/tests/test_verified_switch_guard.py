"""Verified owners cannot enter the legacy reconnect/failover paths."""

import ast
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / (
    "apps/proxy/live_proxy/input/manager.py")
tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
methods = [node for node in ast.walk(tree)
           if isinstance(node, ast.FunctionDef)
           and node.name in {"update_url", "_try_next_stream"}]
isolated = ast.Module(body=[ast.ClassDef(name="Manager", bases=[], keywords=[],
    body=methods, decorator_list=[])], type_ignores=[])
ast.fix_missing_locations(isolated)
scope = {}
exec(compile(isolated, str(SOURCE), "exec"), scope)


class SwitchGuardTests(unittest.TestCase):
    def test_verified_owner_rejects_reconnect_and_failover_before_url_use(self):
        manager = scope["Manager"]()
        manager._verified_generation_required = True
        self.assertFalse(manager.update_url("synthetic-target", 8, 9))
        self.assertFalse(manager._try_next_stream())


if __name__ == "__main__":
    unittest.main()
