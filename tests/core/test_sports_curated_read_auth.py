"""Exercise credential separation without importing writer processes or provider code."""
from pathlib import Path
import ast
import hmac
import os
import sys
import types
import unittest
import urllib.parse
from http import HTTPStatus
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'modules/sports/src'))
import curated_live_events as curated

tree = ast.parse((ROOT / 'modules/sports/src/private_api.py').read_text())
handler = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Handler')
methods = [node for node in handler.body if isinstance(node, ast.FunctionDef)
           and node.name in ('_authorized', '_curated_read_authorized', '_require_auth', 'do_GET', 'do_POST')]
namespace = dict(os=os, hmac=hmac, urllib=urllib, HTTPStatus=HTTPStatus)
exec(compile(ast.Module(body=methods, type_ignores=[]), 'writer_auth_boundary.py', 'exec'), namespace)


class Fixture:
    _authorized = namespace['_authorized']
    _curated_read_authorized = namespace['_curated_read_authorized']
    _require_auth = namespace['_require_auth']
    do_GET = namespace['do_GET']
    do_POST = namespace['do_POST']

    def __init__(self, method, path, token):
        self.command = method
        self.path = path
        self.headers = {'Authorization': 'Bearer ' + token}
        self.responses = []

    def _json(self, status, body):
        self.responses.append((status, body))

    def _read_payload(self):
        raise AssertionError('Unauthorized request reached payload or mutation work')

    def _backend_unavailable(self):
        self._json(HTTPStatus.SERVICE_UNAVAILABLE, {})


class CuratedReadAuthTests(unittest.TestCase):
    def setUp(self):
        self.reader = 'reader-' + 'r' * 40
        self.writer = 'writer-' + 'w' * 40
        self.policy = 'policy-' + 'p' * 40
        self.context = patch.dict(os.environ, {
            'ATLAS_SPORTS_CURATED_READ_TOKEN': self.reader,
            'ATLAS_SPORTS_WRITER_TOKEN': self.writer,
            'ATLAS_SPORTS_LIVE_POLICY_TOKEN': self.policy,
        }, clear=True)
        self.context.start()
        self.addCleanup(self.context.stop)

    def test_reader_can_only_read_the_two_cache_routes(self):
        for path in ('/internal/v1/curated/teams?competition=nfl',
                     '/internal/v1/curated/schedule?competition=nfl&start_at=x&end_at=y'):
            with self.subTest(path=path):
                f = Fixture('GET', path, self.reader)
                self.assertTrue(f._require_auth())
                self.assertFalse(f._authorized())

    def test_reader_cannot_authorize_any_mutation_method(self):
        for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'):
            for path in ('/internal/v1/curated/teams', '/internal/v1/curated/schedule',
                         '/internal/v1/providers/accounts', '/internal/v1/live-sources'):
                with self.subTest(method=method, path=path):
                    f = Fixture(method, path, self.reader)
                    self.assertFalse(f._require_auth())
                    self.assertEqual(f.responses[0][0], HTTPStatus.UNAUTHORIZED)

    def test_actual_get_dispatch_accepts_scoped_token_for_cache_only(self):
        service = types.SimpleNamespace(teams=lambda competition: {'teams': [], 'status': 'ready'})
        with patch('providers.curated_schedule.configured_curated_schedules', return_value=service):
            f = Fixture('GET', '/internal/v1/curated/teams?competition=nfl', self.reader)
            f.do_GET()
        self.assertEqual(f.responses, [(HTTPStatus.OK, {'teams': [], 'status': 'ready'})])

    def test_actual_post_dispatch_denies_reader_before_parsing_payload(self):
        for path in ('/internal/v1/events/request', '/internal/v1/subscriptions',
                     '/internal/v1/live-tv/bindings', '/internal/v1/live-sources', '/internal/v1/sources'):
            with self.subTest(path=path):
                f = Fixture('POST', path, self.reader)
                f.do_POST()
                self.assertEqual(f.responses[0][0], HTTPStatus.UNAUTHORIZED)

    def test_other_get_routes_and_near_match_paths_are_denied(self):
        for path in ('/internal/v1/curated/catalog', '/internal/v1/live-sources',
                     '/internal/v1/metadata/refresh-status', '/internal/v1/providers/accounts',
                     '/internal/v1/curated/teams/', '/internal/v1/curated/teams/../schedule',
                     '/internal/v1/curated/%74eams'):
            with self.subTest(path=path):
                self.assertFalse(Fixture('GET', path, self.reader)._require_auth())

    def test_missing_short_wrong_and_aliased_reader_tokens_fail_closed(self):
        for configured in ('', 'short', self.writer, self.policy):
            with self.subTest(configured_kind=len(configured)), patch.dict(
                    os.environ, {'ATLAS_SPORTS_CURATED_READ_TOKEN': configured}):
                f = Fixture('GET', '/internal/v1/curated/teams', configured)
                self.assertFalse(f._curated_read_authorized())
                if configured != self.writer:
                    self.assertFalse(f._require_auth())
        self.assertFalse(Fixture('GET', '/internal/v1/curated/teams', 'wrong')._require_auth())

    def test_existing_writer_authorization_is_unchanged(self):
        for method in ('GET', 'POST', 'PATCH', 'DELETE'):
            self.assertTrue(Fixture(method, '/internal/v1/live-sources', self.writer)._require_auth())

    def test_live_policy_token_does_not_authorize_curated_cache(self):
        self.assertFalse(Fixture('GET', '/internal/v1/curated/teams', self.policy)._require_auth())

    def test_cache_client_uses_scoped_token(self):
        class StopAfterToken(Exception):
            pass
        def capture(url, token):
            self.assertEqual(token, self.reader)
            raise StopAfterToken()
        with patch.object(curated, 'CacheClient', side_effect=capture):
            with self.assertRaises(StopAfterToken):
                curated.load_curated_live_events(subscriptions=[{
                    'provider':'espn', 'type':'league', 'id':'football/nfl', 'enabled':True,
                }], environ=dict(os.environ, ATLAS_SPORTS_CURATED_LIVE_ENABLED='1'))

    def test_cache_client_does_not_fall_back_to_writer_token(self):
        env = dict(os.environ, ATLAS_SPORTS_CURATED_LIVE_ENABLED='1')
        env.pop('ATLAS_SPORTS_CURATED_READ_TOKEN')
        with self.assertRaises(curated.CuratedLiveUnavailable):
            curated.load_curated_live_events(subscriptions=[{
                'provider':'espn', 'type':'league', 'id':'football/nfl', 'enabled':True,
            }], environ=env)


if __name__ == '__main__':
    unittest.main()
