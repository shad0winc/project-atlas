"""HEAD must preserve access checks and never select an upstream or a viewer."""
import ast
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
PATCHER = ROOT / 'modules/sports-backend/dispatcharr/apply_patch.py'
spec = importlib.util.spec_from_file_location('atlas_dispatcharr_head_patch', PATCHER)
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)
FIXTURE = (patcher.METHOD_ANCHOR + '''(request, channel_id, user=None, force_output_format=None):
    if not network_access_allowed(request, "STREAMS"):
        return JsonResponse({"error": "Forbidden"}, status=403)

''' + patcher.BODY_ANCHOR + '''
    return ProxyServer.get_instance()
''').encode()

class Response(dict):
    def __init__(self, content=(), *, content_type=None, status=200):
        super().__init__()
        self.content = content
        self.status_code = status
        if content_type:
            self['Content-Type'] = content_type

class HeadPatch(unittest.TestCase):
    def patched(self):
        return patcher.patched_source(FIXTURE, expected_sha256=hashlib.sha256(FIXTURE).hexdigest())

    def handler(self, network=True):
        node = next(n for n in ast.parse(self.patched()).body if isinstance(n, ast.FunctionDef))
        node.decorator_list = []
        self.lookup = Mock()
        self.network = Mock(return_value=network)
        self.proxy = Mock()
        self.proxy.get_instance.side_effect = AssertionError('upstream forbidden')
        scope = {'network_access_allowed': self.network, 'get_stream_object': self.lookup,
                 'JsonResponse': Response, 'StreamingHttpResponse': Response,
                 'ProxyServer': self.proxy}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'head_fixture.py', 'exec'), scope)
        return scope['stream_ts']

    def test_default_hash_guard_rejects_other_upstream(self):
        with self.assertRaisesRegex(ValueError, 'checksum'):
            patcher.patched_source(FIXTURE)

    def test_changed_anchors_fail_closed(self):
        raw = FIXTURE.replace(b'@api_view(["GET"])', b'@api_view(["POST"])')
        with self.assertRaisesRegex(ValueError, 'anchors'):
            patcher.patched_source(raw, expected_sha256=hashlib.sha256(raw).hexdigest())

    def test_head_never_initializes_proxy(self):
        response = self.handler()(SimpleNamespace(method='HEAD'), 'channel')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'video/mp2t')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(tuple(response.content), ())
        self.assertNotIn('Content-Length', response)
        self.lookup.assert_called_once_with('channel')
        self.proxy.get_instance.assert_not_called()

    def test_denied_network_never_looks_up_or_allocates(self):
        response = self.handler(False)(SimpleNamespace(method='HEAD'), 'channel')
        self.assertEqual(response.status_code, 403)
        self.lookup.assert_not_called()
        self.proxy.get_instance.assert_not_called()

    def test_missing_identity_never_allocates(self):
        handler = self.handler()
        self.lookup.side_effect = LookupError('missing identity')
        with self.assertRaises(LookupError):
            handler(SimpleNamespace(method='HEAD'), 'channel')
        self.proxy.get_instance.assert_not_called()

    def test_get_behavior_preserved(self):
        before = next(n for n in ast.parse(FIXTURE).body if isinstance(n, ast.FunctionDef))
        after = next(n for n in ast.parse(self.patched()).body if isinstance(n, ast.FunctionDef))
        before.decorator_list = after.decorator_list = []
        del after.body[1]
        self.assertEqual(ast.dump(before), ast.dump(after))
        with self.assertRaisesRegex(AssertionError, 'upstream forbidden'):
            self.handler()(SimpleNamespace(method='GET'), 'channel')

    def test_build_runs_framework_contract(self):
        text = (PATCHER.parent / 'Dockerfile').read_text()
        self.assertIn('python -B /tmp/atlas-dispatcharr-test-stream-head.py', text)
        self.assertIn('head-compatibility-v1', text)
        self.assertIn('sha256:e764cd3fb3a4b14e0c96eeb830cce645b44ef0a2494838e21462c71dde5abeb4', text)

if __name__ == '__main__':
    unittest.main()
