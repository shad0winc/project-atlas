"""No raw TS batch reaches a viewer before its generation-bound join."""

import ast
import time
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / (
    "apps/proxy/live_proxy/output/ts/generator.py")
tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
              and node.name == "_stream_data_generator")
isolated = ast.Module(body=[ast.ClassDef(name="Generator", bases=[], keywords=[],
    body=[method], decorator_list=[])], type_ignores=[])
ast.fix_missing_locations(isolated)


class Logger:
    def error(self, *args):
        pass


scope = {"logger": Logger(), "time": time}
exec(compile(isolated, str(SOURCE), "exec"), scope)


class Buffer:
    _verified_reader_authority = object()
    index = 9

    def __init__(self, batches):
        self.batches = iter(batches)

    def get_indexed_chunks_for_active_generation(self, **kwargs):
        return next(self.batches)


def viewer(batches, join):
    obj = scope["Generator"]()
    obj.buffer = Buffer(batches)
    obj.local_index = 0
    obj.channel_id = "synthetic-channel"
    obj.empty_reads = 0
    obj.consecutive_empty = 0
    obj._verified_join_attestation = join
    obj._check_resources = lambda: True
    obj._process_chunks = lambda chunks, index: iter(chunks)
    return obj


class ViewerDeliveryTests(unittest.TestCase):
    def test_original_index_attested_before_any_media(self):
        observed = []
        obj = viewer([[(7, b"MEDIA")]],
                     lambda index: observed.append(index) or True)
        self.assertEqual(next(obj._stream_data_generator()), b"MEDIA")
        self.assertEqual(observed, [7])

    def test_rejected_or_failed_join_delivers_no_media(self):
        for join in (lambda index: False,
                     lambda index: (_ for _ in ()).throw(ValueError("synthetic"))):
            with self.subTest(join=join):
                obj = viewer([[(7, b"MEDIA")]], join)
                self.assertEqual(list(obj._stream_data_generator()), [])

    def test_replacement_between_batches_stops_before_second_media(self):
        observed = []
        obj = viewer([[(7, b"FIRST")], [(9, b"REPLACEMENT")]],
                     lambda index: observed.append(index) or index == 7)
        self.assertEqual(list(obj._stream_data_generator()), [b"FIRST"])
        self.assertEqual(observed, [7, 9])


if __name__ == "__main__":
    unittest.main()
