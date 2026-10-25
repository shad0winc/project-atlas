"""Actual DRF method dispatch with all upstream operations fenced by sentinels."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

from django.conf import settings
if not settings.configured:
    settings.configure(
        SECRET_KEY='atlas-isolated-head-contract-test',
        INSTALLED_APPS=[], ALLOWED_HOSTS=['testserver'],
        REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES': [],
                        'UNAUTHENTICATED_USER': None},
    )
import django
django.setup()
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.middleware.common import CommonMiddleware
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory, force_authenticate

ROOT = Path(__file__).resolve().parent

def function(path):
    return next(n for n in ast.parse(path.read_bytes()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'stream_ts')

class HeadContract(unittest.TestCase):
    def setUp(self):
        self.network = Mock(return_value=True)
        self.lookup = Mock(return_value=object())
        self.proxy = Mock()
        self.proxy.get_instance.side_effect = AssertionError('Upstream initialization forbidden')
        scope = {'__name__': 'isolated_head_contract', 'api_view': api_view,
                 'permission_classes': permission_classes, 'AllowAny': AllowAny,
                 'network_access_allowed': self.network, 'get_stream_object': self.lookup,
                 'StreamingHttpResponse': StreamingHttpResponse,
                 'JsonResponse': JsonResponse, 'ProxyServer': self.proxy}
        exec(compile(ast.Module(body=[function(Path('/app/apps/proxy/live_proxy/views.py'))], type_ignores=[]),
                     'verified_stream_ts.py', 'exec'), scope)
        self.view = scope['stream_ts']
        self.requests = APIRequestFactory()

    def test_head_existing_resource_has_no_allocation_or_length(self):
        response = self.view(self.requests.head('/proxy/ts/stream/test'), channel_id='test')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'video/mp2t')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotIn('Content-Length', response)
        self.assertTrue(response.streaming)
        self.assertEqual(b''.join(response.streaming_content), b'')
        self.network.assert_called_once()
        self.lookup.assert_called_once_with('test')
        self.proxy.get_instance.assert_not_called()

    def test_common_middleware_keeps_live_length_unspecified(self):
        request = self.requests.head('/proxy/ts/stream/test')
        response = self.view(request, channel_id='test')
        middleware = CommonMiddleware(lambda request: response)
        response = middleware.process_response(request, response)
        self.assertNotIn('Content-Length', response)
        self.assertEqual(response.status_code, 200)
        self.proxy.get_instance.assert_not_called()

    def test_options_advertises_head_without_allocation(self):
        response = self.view(self.requests.options('/proxy/ts/stream/test'), channel_id='test')
        self.assertEqual(response.status_code, 200)
        self.assertIn('HEAD', response['Allow'])
        self.network.assert_not_called()
        self.lookup.assert_not_called()
        self.proxy.get_instance.assert_not_called()

    def test_head_preserves_network_denial_without_lookup(self):
        self.network.return_value = False
        response = self.view(self.requests.head('/proxy/ts/stream/test'), channel_id='test')
        self.assertEqual(response.status_code, 403)
        self.lookup.assert_not_called()
        self.proxy.get_instance.assert_not_called()

    def test_missing_identity_returns_404_without_allocation(self):
        self.lookup.side_effect = Http404
        response = self.view(self.requests.head('/proxy/ts/stream/test'), channel_id='test')
        self.assertEqual(response.status_code, 404)
        self.proxy.get_instance.assert_not_called()

    def test_post_remains_rejected(self):
        response = self.view(self.requests.post('/proxy/ts/stream/test'), channel_id='test')
        self.assertEqual(response.status_code, 405)
        self.network.assert_not_called()
        self.lookup.assert_not_called()
        self.proxy.get_instance.assert_not_called()

    def test_get_body_preserved(self):
        before = function(ROOT/'atlas-dispatcharr-views.before.py')
        after = function(Path('/app/apps/proxy/live_proxy/views.py'))
        before.decorator_list = after.decorator_list = []
        head = after.body[1]
        self.assertIsInstance(head, ast.If)
        self.assertEqual(ast.unparse(head.test), "request.method == 'HEAD'")
        del after.body[1]
        self.assertEqual(ast.dump(before), ast.dump(after))

    def test_get_still_enters_original_handler(self):
        request = self.requests.get('/proxy/ts/stream/test')
        force_authenticate(request, user=SimpleNamespace(is_authenticated=False))
        with self.assertRaisesRegex(AssertionError, 'Upstream initialization forbidden'):
            self.view(request, channel_id='test')
        self.proxy.get_instance.assert_called_once()
        self.lookup.assert_not_called()

if __name__ == '__main__':
    unittest.main(verbosity=2)
