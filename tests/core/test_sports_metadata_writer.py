import copy
from datetime import date
from email.message import Message
from http.server import ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'modules/sports/src'))
sys.path.insert(0, str(ROOT))
from providers.metadata_broker import MetadataBroker, MetadataUnavailable, ESPNDayTransport, BoundedESPNTransport
from providers.metadata_client import MetadataWriterClient
from providers.metadata_service import parse_snapshot, query_metadata, snapshot_document
from providers.metadata_store import MetadataStore
from providers.espn_metadata import LEAGUE_UIDS
import private_api

STAMP = 1792108800.0  # 2026-10-16T00:00:00Z
DAY = date(2026, 10, 18)
ROUTE = 'football/nfl'


class MetadataWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        fixtures = ROOT / 'tests/fixtures/sports'
        self.games = json.loads((fixtures / 'espn-metadata-20261016.json').read_text())['samples']
        self.directories = json.loads((fixtures / 'espn-team-directories-20261016.json').read_text())['samples']
        self.directory = next(row['payload'] for row in self.directories if row['route'] == ROUTE)
        self.now = STAMP
        self.calls = []
        outer = self
        class Transport:
            def __call__(self, route, day):
                outer.calls.append(('day', route, day))
                if isinstance(outer.failure, Exception):
                    raise outer.failure
                return {'leagues': [{'uid': LEAGUE_UIDS[route]}], 'events': []}
            def fetch_teams(self, route):
                outer.calls.append(('teams', route))
                if isinstance(outer.failure, Exception):
                    raise outer.failure
                return copy.deepcopy(outer.directory)
        self.failure = None
        self.broker = MetadataBroker(MetadataStore(Path(self.tmp.name) / 'metadata.sqlite'),
            transport=Transport(), clock=lambda: self.now, directory_ttl=5)

    def roundtrip(self, snapshot, **arguments):
        return parse_snapshot(json.loads(json.dumps(snapshot_document(snapshot))), **arguments)

    def test_directory_and_day_share_budget(self):
        self.broker.hourly_budget = 1
        directory = self.broker.fetch_teams(ROUTE)
        self.assertEqual(len(directory.teams), 32)
        with self.assertRaises(MetadataUnavailable) as caught:
            self.broker.fetch_day(ROUTE, DAY)
        self.assertEqual(caught.exception.category, 'request-budget')
        self.assertEqual(len(self.calls), 1)

    def test_directory_cache_keeps_original_observation(self):
        first = self.broker.fetch_teams(ROUTE)
        self.now += 2
        second = self.broker.fetch_teams(ROUTE)
        self.assertTrue(second.cache_hit)
        self.assertEqual(first.observed_at, second.observed_at)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(second, self.roundtrip(second, kind='teams', route=ROUTE))

    def test_directory_failure_is_not_empty_and_respects_backoff(self):
        self.failure = MetadataUnavailable('network')
        for _ in range(2):
            with self.assertRaises(MetadataUnavailable):
                self.broker.fetch_teams(ROUTE)
        self.assertEqual(len(self.calls), 1)

    def test_directory_429_blocks_uncached_day_but_not_cached_directory(self):
        self.broker.fetch_teams(ROUTE)
        self.failure = MetadataUnavailable('rate-limit', http_status=429, retry_after=120)
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day('basketball/nba', DAY)
        self.assertTrue(self.broker.fetch_teams(ROUTE).cache_hit)
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day(ROUTE, DAY)
        self.assertEqual(len(self.calls), 2)

    def test_bad_directory_cannot_overwrite_previous_success(self):
        first = self.broker.fetch_teams(ROUTE)
        self.now += 6
        self.directory = {}
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_teams(ROUTE)
        with self.broker.store.connection() as connection:
            stamp = connection.execute("SELECT observed FROM metadata_cache WHERE day='@teams'").fetchone()[0]
        self.assertEqual(stamp, first.observed_at)

    def test_all_captured_events_roundtrip_with_card_and_bouts(self):
        from providers.metadata_broker import MetadataSnapshot
        from providers.espn_metadata import parse_scoreboard
        for row in self.games:
            route = row['route']
            events = parse_scoreboard(route, row['payload'])
            snapshot = MetadataSnapshot(route, DAY.isoformat(), events, STAMP, STAMP+60, False)
            with self.subTest(route=route):
                self.assertEqual(snapshot, self.roundtrip(snapshot, kind='day', route=route, day=DAY))

    def test_bad_or_duplicate_query_never_constructs_state(self):
        def forbidden():
            self.fail('Invalid query reached broker construction')
        for query in ({'route':[ROUTE], 'day':['2026-10-18','2026-10-19']},
                      {'route':['../secret'], 'day':['2026-10-18']},
                      {'route':[ROUTE], 'day':['20261018']},
                      {'route':[ROUTE], 'day':['2026-10-18'], 'extra':['1']}):
            with self.subTest(query=query), self.assertRaises(ValueError):
                query_metadata('/internal/v1/metadata/day', query, broker_factory=forbidden)

    def test_missing_day_cannot_become_a_directory_request(self):
        with self.assertRaises(ValueError):
            self.broker.fetch_day(ROUTE, None)
        self.assertEqual(self.calls, [])

    def test_day_outside_horizon_fails_without_network(self):
        with self.assertRaises(ValueError):
            self.broker.fetch_day(ROUTE, date(2027,1,1))
        self.assertEqual(self.calls, [])

    def test_snapshot_identity_age_unknown_fields_and_stale_are_rejected(self):
        document = json.loads(json.dumps(snapshot_document(self.broker.fetch_day(ROUTE, DAY))))
        for change in ({'route':'basketball/nba'}, {'requested_day':'2026-10-19'},
                       {'observed_at':float('nan')}, {'expires_at':STAMP-1},
                       {'stale':True}, {'cache_hit':1}, {'stream_url':'hidden'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                parse_snapshot(dict(document, **change), kind='day', route=ROUTE, day=DAY)

    def start_server(self, *, enabled=True):
        patches = [patch.dict(os.environ, {
            'ATLAS_SPORTS_WRITER_TOKEN':'test-only-credential',
            'ATLAS_SPORTS_METADATA_STATE_DIR': self.tmp.name if enabled else '',
        }), patch('providers.metadata_service._configured_broker', return_value=self.broker)]
        for item in patches:
            item.start(); self.addCleanup(item.stop)
        server = ThreadingHTTPServer(('127.0.0.1', 0), private_api.Handler)
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
        thread.start()
        def close():
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        self.addCleanup(close)
        self.url = 'http://127.0.0.1:' + str(server.server_port)
        return MetadataWriterClient(self.url, 'test-only-credential', clock=lambda: self.now)

    def test_authenticated_http_empty_day_and_team_directory(self):
        client = self.start_server()
        day = client.fetch_day(ROUTE, DAY)
        self.assertEqual(day.events, ())
        self.assertEqual(day.outcome, 'empty')
        directory = client.fetch_teams(ROUTE)
        self.assertEqual(len(directory.teams), 32)
        self.assertTrue(client.fetch_teams(ROUTE).cache_hit)
        self.assertEqual(len(self.calls), 2)

    def test_client_rejects_snapshot_expiring_during_delivery(self):
        client = self.start_server()
        client.clock = lambda: self.now + 3601
        with self.assertRaises(MetadataUnavailable) as caught:
            client.fetch_day(ROUTE, DAY)
        self.assertEqual(caught.exception.category, 'writer-snapshot-age')

    def test_unauthorized_http_cannot_consume_budget(self):
        self.start_server()
        bad = MetadataWriterClient(self.url, 'incorrect')
        with self.assertRaises(MetadataUnavailable) as caught:
            bad.fetch_day(ROUTE, DAY)
        self.assertEqual(caught.exception.http_status, 401)
        self.assertEqual(self.calls, [])

    def test_disabled_http_does_not_construct_state(self):
        client = self.start_server(enabled=False)
        with self.assertRaises(MetadataUnavailable) as caught:
            client.fetch_day(ROUTE, DAY)
        self.assertEqual(caught.exception.http_status, 503)
        self.assertEqual(self.calls, [])

    def test_http_invalid_query_is_400(self):
        self.start_server()
        request = urllib.request.Request(self.url+'/internal/v1/metadata/day?route=football%2Fnfl&day=bad',
            headers={'Authorization':'Bearer test-only-credential'})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=2)
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(self.calls, [])

    def test_http_failure_remains_failure_without_raw_exception(self):
        client = self.start_server()
        self.failure = MetadataUnavailable('network')
        with self.assertRaises(MetadataUnavailable) as caught:
            client.fetch_day(ROUTE, DAY)
        self.assertEqual(str(caught.exception), 'Independent Sports metadata is unavailable: writer-unavailable')
        self.assertEqual(len(self.calls), 1)

    def test_client_rejects_credentials_in_url_and_arbitrary_paths(self):
        for url in ('http://user:secret@writer:8003', 'http://writer:8003/other',
                    'https://writer/?secret=1', 'file:///tmp/file'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                MetadataWriterClient(url, 'credential')

    def test_directory_transport_uses_fixed_host_and_bounded_team_endpoint(self):
        outer = self
        class Response(io.BytesIO):
            status = 200
            headers = Message()
        class Opener:
            def open(self, request, timeout):
                outer.assertEqual(request.full_url, 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams?limit=1000')
                outer.assertEqual(timeout, 8)
                result = Response(json.dumps(outer.directory).encode())
                result.headers['Content-Type'] = 'application/json'
                return result
        teams = ESPNDayTransport(opener=Opener()).fetch_teams(ROUTE)
        self.assertEqual(teams, self.directory)

    def test_directory_subprocess_uses_same_deadline(self):
        outer = self
        class Result:
            returncode = 0
        def runner(arguments, **kwargs):
            outer.assertEqual(kwargs['timeout'], 8)
            outer.assertEqual(json.loads(kwargs['input']), {'route':ROUTE, 'kind':'teams'})
            result = Result()
            result.stdout = json.dumps({'outcome':'success', 'payload':outer.directory}).encode()
            return result
        self.assertEqual(BoundedESPNTransport(runner=runner).fetch_teams(ROUTE), self.directory)

if __name__ == '__main__':
    unittest.main()
