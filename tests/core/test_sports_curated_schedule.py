import copy
import ast
from http import HTTPStatus
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import urllib.parse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'modules/sports/src'))
from providers.curated_schedule import CuratedSchedules, SnapshotReader, configured_curated_schedules
from providers.espn_metadata import LEAGUE_UIDS

START = '2026-10-18T00:00:00-04:00'
END = '2026-10-19T00:00:00-04:00'
ROUTE = 'football/nfl'


class CuratedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.path = self.root / 'metadata.sqlite'
        self.now = datetime(2026, 10, 16, tzinfo=timezone.utc).timestamp()
        db = sqlite3.connect(self.path)
        db.executescript('''CREATE TABLE metadata_schema(version INTEGER); INSERT INTO metadata_schema VALUES(1);
            CREATE TABLE metadata_cache(route TEXT,day TEXT,payload TEXT,observed REAL,expires REAL,PRIMARY KEY(route,day));
            CREATE TABLE metadata_holds(key TEXT PRIMARY KEY,until_stamp REAL);''')
        db.close()
        self.path.chmod(0o600)
        self.reader = SnapshotReader(self.root, clock=lambda: self.now)
        self.service = CuratedSchedules(enabled=True, routes=(ROUTE,), reader=self.reader, clock=lambda: self.now)
        status = {'type': {'name': 'STATUS_SCHEDULED', 'state': 'pre', 'completed': False}}
        self.nfl = {'leagues': [{'uid': LEAGUE_UIDS[ROUTE]}], 'events': []}
        for number in range(12):
            stamp = '2026-10-19T00:20:00Z' if number == 11 else '2026-10-18T17:00:00Z'
            event_id = str(401000000 + number)
            self.nfl['events'].append({'id': event_id, 'name': 'Synthetic game ' + str(number), 'status': copy.deepcopy(status),
                'competitions': [{'id': event_id, 'timeValid': True, 'date': stamp, 'status': copy.deepcopy(status),
                    'competitors': [{'id': str(number * 2 + side + 1), 'homeAway': 'home' if side == 0 else 'away',
                        'team': {'id': str(number * 2 + side + 1), 'displayName': 'Fixture team ' + str(number * 2 + side + 1)}} for side in range(2)]}]})
        self.teams = {'sports': [{'uid': 's:20', 'leagues': [{'uid': LEAGUE_UIDS[ROUTE],
            'teams': [{'team': {'id': str(number), 'uid': LEAGUE_UIDS[ROUTE] + '~t:' + str(number),
                'displayName': 'Fixture team %02d' % number, 'abbreviation': 'T%02d' % number}} for number in range(1, 33)]}]}]}

    def put(self, day, payload, *, observed=None, expires=None):
        observed = self.now if observed is None else observed
        expires = observed + 60 if expires is None else expires
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT OR REPLACE INTO metadata_cache VALUES (?,?,?,?,?)', (ROUTE, day, json.dumps(payload), observed, expires))

    def empty(self):
        return {'leagues': [{'uid': LEAGUE_UIDS[ROUTE]}], 'events': []}

    def fill(self, payload=None):
        for day in ('2026-10-17', '2026-10-18', '2026-10-19'):
            self.put(day, (self.nfl if payload is None else payload) if day == '2026-10-18' else self.empty())

    def test_disabled_default_does_not_open_or_create_cache(self):
        with patch.dict(os.environ, {'ATLAS_SPORTS_CURATED_BROWSE_ENABLED': '0'}), patch.object(SnapshotReader, 'snapshot', side_effect=AssertionError('must not open')):
            service = configured_curated_schedules()
            service.clock = lambda: self.now
            self.assertFalse(service.catalog()['enabled'])
            self.assertEqual(service.schedule('nfl', START, END)['status'], 'disabled')

    def test_catalog_is_curated_and_separates_configuration_from_freshness(self):
        result = self.service.catalog()
        nfl = next(row for row in result['competitions'] if row['id'] == 'nfl')
        self.assertEqual(nfl['status'], 'configured')
        self.assertEqual(nfl['provider_league_id'], ROUTE)
        self.assertEqual(next(row for row in result['competitions'] if row['id'] == 'college-football')['status'], 'unsupported')
        self.assertFalse(next(row for row in result['competitions'] if row['id'] == 'ufc')['team_directory_supported'])

    def test_cold_cache_is_preparing_and_never_calls_transport(self):
        before = self.path.read_bytes()
        with patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')):
            result = self.service.schedule('nfl', START, END)
            self.assertEqual(result['status'], 'preparing')
            self.assertFalse(result['coverage_complete'])
            self.assertEqual(result['events'], [])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual({p.name for p in self.root.iterdir()}, {'metadata.sqlite'})

    def test_missing_database_remains_missing(self):
        self.path.unlink()
        self.assertEqual(self.service.schedule('nfl', START, END)['status'], 'preparing')
        self.assertFalse(self.path.exists())

    def test_checked_empty_is_distinct_from_missing(self):
        self.fill(self.empty())
        result = self.service.schedule('nfl', START, END)
        self.assertEqual(result['status'], 'ready')
        self.assertTrue(result['coverage_complete'])
        self.assertFalse(result['provider_completeness_proven'])
        self.assertEqual(result['events'], [])

    def test_complete_window_uses_synthetic_games_and_aware_local_day(self):
        self.fill()
        result = self.service.schedule('nfl', START, END)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(len(result['events']), 12)
        self.assertEqual(result['required_buckets'], 3)
        self.assertEqual(result['fresh_buckets'], 3)
        self.assertIn('2026-10-19T00:20:00Z', {event['start_at'] for event in result['events']})
        self.assertTrue(all(event['provider'] == 'espn' and event['provider_league_id'] == ROUTE for event in result['events']))

    def test_missing_bucket_preserves_observed_rows_as_partial(self):
        self.put('2026-10-18', self.nfl)
        result = self.service.schedule('nfl', START, END)
        self.assertEqual(result['status'], 'partial')
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(len(result['events']), 12)

    def test_stale_snapshot_keeps_original_age(self):
        self.fill()
        self.now += 61
        result = self.service.schedule('nfl', START, END)
        self.assertEqual(result['status'], 'stale')
        self.assertFalse(result['coverage_complete'])
        self.assertLess(datetime.fromisoformat(result['events'][0]['metadata_expires_at'].replace('Z', '+00:00')).timestamp(), self.now)

    def test_invalid_source_identity_is_unavailable_not_empty_success(self):
        payload = self.empty()
        payload['leagues'][0]['uid'] = LEAGUE_UIDS['basketball/nba']
        self.fill(payload)
        result = self.service.schedule('nfl', START, END)
        self.assertEqual(result['status'], 'unavailable')
        self.assertFalse(result['coverage_complete'])

    def test_newer_cancellation_supersedes_older_schedule(self):
        self.fill()
        revised = copy.deepcopy(self.nfl)
        revised['events'][0]['status'] = {'type': {'name': 'STATUS_CANCELED', 'state': 'pre', 'completed': False}}
        self.now += 1
        self.put('2026-10-19', revised)
        result = self.service.schedule('nfl', START, END)
        event_id = revised['events'][0]['id']
        row = next(row for row in result['events'] if row['provider_event_id'] == 'football-nfl-' + event_id)
        self.assertEqual(row['status'], 'cancelled')

    def test_conflicting_latest_revision_is_partial(self):
        self.fill()
        revised = copy.deepcopy(self.nfl)
        revised['events'][0]['name'] = 'Conflicting title'
        self.put('2026-10-19', revised)
        result = self.service.schedule('nfl', START, END)
        self.assertEqual(result['status'], 'partial')
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(len(result['events']), 11)

    def test_teams_are_typed_source_scoped_and_alphabetical(self):
        self.put('@teams', self.teams)
        result = self.service.teams('nfl')
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(len(result['teams']), 32)
        self.assertTrue(all(row['id'].startswith('football-nfl-') for row in result['teams']))
        self.assertEqual([row['name'] for row in result['teams']], sorted(row['name'] for row in result['teams']))

    def test_missing_team_directory_is_preparing(self):
        self.assertEqual(self.service.teams('nfl')['status'], 'preparing')

    def test_ufc_does_not_offer_team_follows(self):
        self.assertEqual(self.service.teams('ufc')['status'], 'unsupported')

    def test_unknown_competition_and_unbounded_dates_refused(self):
        for key, start, end in (('../nfl', START, END), ('college-football', START, END), ('nfl', START, '2026-10-28T00:00:00Z'), ('nfl', '2026-10-18', END)):
            with self.subTest(key=key, end=end), self.assertRaises(ValueError):
                self.service.schedule(key, start, end)

    def test_database_symlink_is_unavailable(self):
        real = self.path.with_name('saved.sqlite')
        self.path.rename(real)
        self.path.symlink_to(real)
        self.assertEqual(self.service.schedule('nfl', START, END)['status'], 'unavailable')

    def test_cooldown_is_observed_without_retry_or_mutation(self):
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO metadata_holds VALUES (?,?)', ('espn:cooldown', self.now + 120))
        result = self.service.schedule('nfl', START, END)
        self.assertEqual(result['retry_after_seconds'], 120)
        self.assertEqual(result['status'], 'preparing')

    def test_future_observation_is_not_accepted(self):
        self.put('2026-10-18', self.nfl, observed=self.now + 1)
        self.assertEqual(self.service.schedule('nfl', START, END)['status'], 'unavailable')

    def request(self, path, *, authenticated=True):
        tree = ast.parse((ROOT / 'modules/sports/src/private_api.py').read_text())
        handler = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Handler')
        method = next(node for node in handler.body if isinstance(node, ast.FunctionDef) and node.name == 'do_GET')
        namespace = {'urllib': urllib, 'HTTPStatus': HTTPStatus}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'actual-private-handler', 'exec'), namespace)
        class Fixture:
            def __init__(self):
                self.path = path
            def _require_auth(self):
                if not authenticated:
                    self.status = 401
                return authenticated
            def _json(self, status, document):
                self.status, self.document = int(status), document
            def _backend_unavailable(self):
                self.status = 503
        Fixture.do_GET = namespace['do_GET']
        request = Fixture()
        with patch('providers.curated_schedule.configured_curated_schedules', return_value=self.service):
            request.do_GET()
        return request

    def test_actual_handler_requires_private_authentication(self):
        request = self.request('/internal/v1/curated/catalog', authenticated=False)
        self.assertEqual(request.status, 401)

    def test_actual_handler_serves_catalog_without_fetch(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')):
            request = self.request('/internal/v1/curated/catalog')
        self.assertEqual(request.status, 200)
        self.assertEqual(len(request.document['competitions']), 8)

    def test_actual_handler_rejects_duplicate_or_unexpected_queries(self):
        for path in ('catalog?refresh=1', 'teams?competition=nfl&competition=nba', 'schedule?competition=nfl'):
            with self.subTest(path=path):
                self.assertEqual(self.request('/internal/v1/curated/' + path).status, 400)

    def test_actual_handler_returns_preparing_not_provider_error_on_cold_cache(self):
        query = urllib.parse.urlencode({'competition': 'nfl', 'start_at': START, 'end_at': END})
        request = self.request('/internal/v1/curated/schedule?' + query)
        self.assertEqual(request.status, 200)
        self.assertEqual(request.document['status'], 'preparing')

    def test_actual_handler_rejects_unknown_competition(self):
        self.assertEqual(self.request('/internal/v1/curated/teams?competition=unknown').status, 400)


if __name__ == '__main__':
    unittest.main()
