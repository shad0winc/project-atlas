"""Keep HEAD side-effect free while preserving the reviewed GET handler."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / 'apps/proxy/live_proxy/views.py'


def stream_function(path):
    return next(node for node in ast.parse(path.read_bytes()).body
                if isinstance(node, ast.FunctionDef) and node.name == 'stream_ts')


class Response(dict):
    def __init__(self, content=(), *, content_type=None, status=200):
        super().__init__()
        self.content = content
        self.status_code = status
        if content_type:
            self['Content-Type'] = content_type


class HeadCompatibilityTests(unittest.TestCase):
    def handler(self, network=True):
        node = stream_function(VIEW)
        node.decorator_list = []
        self.network = Mock(return_value=network)
        self.lookup = Mock()
        self.proxy = Mock()
        self.proxy.get_instance.side_effect = AssertionError('allocation forbidden')
        scope = dict(network_access_allowed=self.network, get_stream_object=self.lookup,
                     ProxyServer=self.proxy, JsonResponse=Response, StreamingHttpResponse=Response)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(VIEW), 'exec'), scope)
        return scope['stream_ts']

    def test_methods_include_get_and_head(self):
        decorator = stream_function(VIEW).decorator_list[0]
        self.assertEqual(ast.unparse(decorator.func), 'api_view')
        self.assertEqual(ast.literal_eval(decorator.args[0]), ['GET', 'HEAD'])

    def test_head_resolves_identity_without_proxy_or_content_length(self):
        response = self.handler()(SimpleNamespace(method='HEAD'), 'channel')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'video/mp2t')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(tuple(response.content), ())
        self.assertNotIn('Content-Length', response)
        self.network.assert_called_once()
        self.lookup.assert_called_once_with('channel')
        self.proxy.get_instance.assert_not_called()

    def test_denied_head_never_looks_up_or_allocates(self):
        response = self.handler(False)(SimpleNamespace(method='HEAD'), 'channel')
        self.assertEqual(response.status_code, 403)
        self.lookup.assert_not_called()
        self.proxy.get_instance.assert_not_called()

    def test_missing_head_identity_never_allocates(self):
        handler = self.handler()
        self.lookup.side_effect = LookupError('missing channel')
        with self.assertRaises(LookupError):
            handler(SimpleNamespace(method='HEAD'), 'channel')
        self.proxy.get_instance.assert_not_called()

    def test_get_still_enters_reviewed_proxy_handler(self):
        with self.assertRaisesRegex(AssertionError, 'allocation forbidden'):
            self.handler()(SimpleNamespace(method='GET'), 'channel')
        self.lookup.assert_not_called()
        self.proxy.get_instance.assert_called_once()

    def test_get_body_identical_to_historical_overlay(self):
        before = stream_function(ROOT / 'tests/fixtures/stream_ts_before_head.py')
        after = stream_function(VIEW)
        before.decorator_list = after.decorator_list = []
        self.assertIsInstance(after.body[1], ast.If)
        self.assertEqual(ast.unparse(after.body[1].test), "request.method == 'HEAD'")
        del after.body[1]
        self.assertEqual(ast.dump(before), ast.dump(after))

    def test_image_build_runs_actual_framework_contract(self):
        dockerfile = (ROOT / 'Dockerfile').read_text()
        self.assertIn('python -B /tmp/atlas-dispatcharr-test-stream-head.py', dockerfile)
        self.assertIn('COPY tests/fixtures/stream_ts_before_head.py', dockerfile)
        self.assertIn('verified-live-head-compatibility-v1', dockerfile)
        self.assertIn('sha256:e764cd3fb3a4b14e0c96eeb830cce645b44ef0a2494838e21462c71dde5abeb4', dockerfile)

    def test_manifest_binds_final_view_and_pre_head_fixture(self):
        manifest = json.loads((ROOT / 'manifest.json').read_bytes())
        self.assertEqual(hashlib.sha256(VIEW.read_bytes()).hexdigest(),
                         manifest['overlay_files']['apps/proxy/live_proxy/views.py'])
        self.assertEqual(hashlib.sha256((ROOT / 'tests/fixtures/stream_ts_before_head.py').read_bytes()).hexdigest(),
                         manifest['reconciliation']['pre_head_stream_ts_sha256'])


if __name__ == '__main__':
    unittest.main()
