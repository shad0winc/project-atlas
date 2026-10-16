import copy
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'modules/sports/src'))
sys.path.insert(0, str(ROOT))
from providers.espn_metadata import ROUTES, LEAGUE_UIDS
from providers.espn_directory import encode_entity_id
from providers.metadata_store import MetadataStore
from providers.metadata_broker import MetadataBroker, MetadataUnavailable
from providers.metadata_discovery import MetadataDiscoveryProvider, configured_discovery_provider
import private_api
import subscriptions

NFL = 'football/nfl'
STAMP = datetime(2026,10,16,tzinfo=timezone.utc).timestamp()


class MetadataDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = STAMP
        fixtures = ROOT / 'tests/fixtures/sports'
        self.samples = {row['route']: row for row in json.loads((fixtures / 'espn-metadata-20261016.json').read_text())['samples']}
        self.directories = {row['route']: row['payload'] for row in json.loads((fixtures / 'espn-team-directories-20261016.json').read_text())['samples']}
        self.transport = Mock(side_effect=AssertionError('Discovery must not fetch upstream'))
        self.store = MetadataStore(Path(self.temp.name) / 'metadata.sqlite')
        self.broker = MetadataBroker(self.store, transport=self.transport, clock=lambda: self.now)
        self.provider = MetadataDiscoveryProvider(self.broker, (NFL,))

    def put(self, route, day, payload, observed=None, expires=None):
        with self.store.locked(), self.store.connection() as db:
            db.execute('INSERT OR REPLACE INTO metadata_cache VALUES (?,?,?,?,?)',
                       (route, day, json.dumps(payload), self.now if observed is None else observed,
                        self.now+60 if expires is None else expires))

    def warm(self, routes=(NFL,)):
        today = datetime.fromtimestamp(self.now, timezone.utc).date()
        for route in routes:
            sample = self.samples[route]
            sample_day = datetime.strptime(sample['dates'][:8], '%Y%m%d').date()
            for offset in range(-1,8):
                day = today + timedelta(days=offset)
                payload = sample['payload'] if day == sample_day else {'leagues':[{'uid':LEAGUE_UIDS[route]}], 'events':[]}
                self.put(route, day.isoformat(), payload)
            if route in self.directories:
                self.put(route, '@teams', self.directories[route])

    def assert_no_upstream_or_aliases(self):
        self.transport.assert_not_called()
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM metadata_attempts').fetchone(), (0,))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM metadata_aliases').fetchone(), (0,))

    def test_sunday_twelve_games_and_monday_utc_preserve_source_ids(self):
        self.warm()
        events = self.provider.fetch_games(league_ids=[NFL], days_ahead=7)
        self.assertEqual(len(events),12)
        self.assertTrue(all(event['provider']=='espn' and event['provider_event_id'].startswith('football-nfl-') for event in events))
        self.assertEqual(next(e for e in events if e['provider_event_id'].endswith('-401873007'))['start_at'], '2026-10-19T00:20:00Z')
        self.assertEqual({e['provider_league_id'] for e in events},{NFL})
        self.assert_no_upstream_or_aliases()

    def test_all_six_routes_are_fixture_backed_and_ufc_remains_one_card(self):
        self.warm(tuple(ROUTES))
        provider = MetadataDiscoveryProvider(self.broker, tuple(ROUTES))
        events = provider.fetch_games()
        self.assertEqual(len(events),34)
        ufc = [event for event in events if event['provider_league_id']=='mma/ufc']
        self.assertEqual(len(ufc),1)
        self.assertIsNone(ufc[0]['home_team_id'])
        self.assertIsNone(ufc[0]['away_team_id'])
        self.assert_no_upstream_or_aliases()

    def test_team_and_event_filters_keep_provider_namespace(self):
        self.warm()
        event = self.provider.fetch_games()[0]
        self.assertEqual(self.provider.fetch_games(event_ids=[event['provider_event_id']]),[event])
        self.assertIn(event,self.provider.fetch_games(team_ids=[event['home_team_id']]))
        self.assertEqual(self.provider.fetch_event(event['provider_event_id']),event)
        self.assertEqual(self.provider.fetch_games(event_ids=[encode_entity_id(NFL,'999999')]),[])
        with self.assertRaises(ValueError):
            self.provider.fetch_games(event_ids=['401872996'])
        with self.assertRaises(ValueError):
            self.provider.fetch_games(league_ids=['4391'])

    def test_team_directory_and_league_discovery_are_scoped(self):
        self.warm()
        rows = self.provider.search_teams('rams')
        self.assertEqual(len(rows),1)
        self.assertEqual(self.provider.fetch_team(rows[0]['id']),rows[0])
        self.assertEqual(self.provider.search_leagues('NFL'),[self.provider.fetch_league(NFL)])
        self.assertEqual(self.provider.search_leagues('Wrestling'),[])
        self.assert_no_upstream_or_aliases()

    def test_fighters_are_not_teams(self):
        provider = MetadataDiscoveryProvider(self.broker, ('mma/ufc',))
        self.assertEqual(provider.search_teams('fighter'),[])
        with self.assertRaises(ValueError):
            provider.fetch_team(encode_entity_id('mma/ufc','1'))

    def test_blank_queries_do_not_touch_cache(self):
        with patch.object(self.broker,'read_days',side_effect=AssertionError), patch.object(self.broker,'read_teams',side_effect=AssertionError):
            self.assertEqual(self.provider.search_events(' '),[])
            self.assertEqual(self.provider.search_teams(''),[])
            self.assertEqual(self.provider.search_leagues(''),[])

    def test_missing_cache_is_unavailable_not_empty(self):
        with self.assertRaises(MetadataUnavailable):self.provider.fetch_games()
        with self.assertRaises(MetadataUnavailable):self.provider.search_teams('rams')
        self.assert_no_upstream_or_aliases()

    def test_expired_cache_is_unavailable_and_observation_is_not_renewed(self):
        self.warm()
        before = self.provider.fetch_games()[0]['metadata_observed_at']
        self.now += 60
        with self.assertRaises(MetadataUnavailable):self.provider.fetch_games()
        with self.assertRaises(MetadataUnavailable):self.provider.search_teams('rams')
        self.assertEqual(before,'2026-10-16T00:00:00Z')
        self.assert_no_upstream_or_aliases()

    def test_missing_one_future_bucket_does_not_claim_empty_schedule(self):
        self.warm()
        with self.store.connection() as db:
            db.execute('DELETE FROM metadata_cache WHERE day=?',('2026-10-23',))
        with self.assertRaises(MetadataUnavailable):self.provider.fetch_games()

    def test_fresh_empty_schedule_is_successfully_empty(self):
        self.warm()
        self.put(NFL,'2026-10-18',{'leagues':[{'uid':LEAGUE_UIDS[NFL]}],'events':[]})
        self.assertEqual(self.provider.fetch_games(),[])
        self.assert_no_upstream_or_aliases()

    def test_newer_cancellation_wins_before_search_filtering(self):
        self.warm()
        old = self.samples[NFL]['payload']
        newer = copy.deepcopy(old)
        event = newer['events'][0]
        state = {'type':{'name':'STATUS_CANCELED','state':'pre','completed':False}}
        event['status'] = state
        event['competitions'][0]['status'] = state
        self.put(NFL,'2026-10-17',old,observed=self.now-10)
        self.put(NFL,'2026-10-18',newer)
        self.assertEqual(len(self.provider.search_events('NFL')),11)
        self.assertEqual(self.provider.fetch_event(encode_entity_id(NFL,event['id']))['status'],'cancelled')

    def test_conflicting_latest_identity_is_unavailable(self):
        self.warm()
        conflicting = copy.deepcopy(self.samples[NFL]['payload'])
        conflicting['events'][0]['name'] += ' conflict'
        self.put(NFL,'2026-10-17',conflicting)
        with self.assertRaises(MetadataUnavailable):self.provider.fetch_games()

    def test_unknown_event_time_is_unavailable_instead_of_invented(self):
        self.warm()
        changed = copy.deepcopy(self.samples[NFL]['payload'])
        changed['events'][0]['competitions'][0]['timeValid'] = False
        self.put(NFL, '2026-10-18', changed)
        with self.assertRaises(MetadataUnavailable):self.provider.fetch_games()

    def test_live_status_comes_from_provider_flags_and_expires(self):
        self.now = datetime(2026,10,18,14,tzinfo=timezone.utc).timestamp()
        self.warm()
        changed = copy.deepcopy(self.samples[NFL]['payload'])
        state = {'type':{'name':'STATUS_IN_PROGRESS','state':'in','completed':False}}
        changed['events'][0]['status'] = state
        changed['events'][0]['competitions'][0]['status'] = state
        self.put(NFL, '2026-10-18', changed)
        event = self.provider.search_events('Texans')[0]
        self.assertEqual(event['status'], 'live')
        self.assertEqual(event['metadata_expires_at'], '2026-10-18T14:01:00Z')
        self.now += 60
        with self.assertRaises(MetadataUnavailable):self.provider.search_events('Texans')

    def test_unconfigured_routes_and_oversized_queries_are_rejected(self):
        with self.assertRaises(ValueError):self.provider.fetch_league('mma/ufc')
        with self.assertRaises(ValueError):self.provider.search_events('x'*129)
        with self.assertRaises(ValueError):self.provider.fetch_games(event_ids=['football-nfl-1']*65)
        with self.assertRaises(ValueError):MetadataDiscoveryProvider(self.broker, ('wrestling/wwe',))
        self.assert_no_upstream_or_aliases()

    def test_observation_and_expiry_are_returned_without_playback_fields(self):
        self.warm()
        event = self.provider.fetch_games()[0]
        self.assertEqual(event['metadata_observed_at'],'2026-10-16T00:00:00Z')
        self.assertEqual(event['metadata_expires_at'],'2026-10-16T00:01:00Z')
        self.assertFalse({'stream_url','atlas_channel_id','credentials'} & set(event))

    def test_disabled_factory_does_not_construct_broker(self):
        with patch('providers.metadata_refresh.load_refresh_policy',return_value=None), patch('providers.metadata_service.configured_broker') as factory:
            with self.assertRaises(MetadataUnavailable):configured_discovery_provider()
            factory.assert_not_called()

    def test_background_registry_is_unchanged(self):
        from providers.registry import available_providers
        self.assertNotIn('espn',[provider.name for provider in available_providers()])

    def serve(self):
        for item in (patch.dict(os.environ,{'ATLAS_SPORTS_WRITER_TOKEN':'test-only'}),
                     patch('providers.metadata_discovery.configured_discovery_provider',return_value=self.provider),
                     patch.object(private_api,'load_subscriptions',return_value=[])):
            item.start();self.addCleanup(item.stop)
        server = ThreadingHTTPServer(('127.0.0.1',0),private_api.Handler)
        thread = threading.Thread(target=lambda:server.serve_forever(poll_interval=.01),daemon=True)
        thread.start()
        def close():server.shutdown();server.server_close();thread.join(timeout=2)
        self.addCleanup(close)
        return 'http://127.0.0.1:'+str(server.server_port)

    def request(self,url,path,body=None,token='test-only',method=None):
        request = urllib.request.Request(url+path, data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method=method)
        try:
            with urllib.request.urlopen(request,timeout=3) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as response:
            with response:return response.code,json.load(response)

    def test_private_http_search_and_filtered_events_use_cache_only(self):
        self.warm();url=self.serve()
        code,body=self.request(url,'/internal/v1/search/teams?provider=espn&query=rams')
        self.assertEqual(code,200);self.assertEqual(len(body['teams']),1)
        code,body=self.request(url,'/internal/v1/events?provider=espn&user_id=owner&league_id=football%2Fnfl')
        self.assertEqual(code,200);self.assertEqual(len(body['events']),12)
        self.assertIn('metadata_expires_at',body['events'][0])
        self.assert_no_upstream_or_aliases()

    def test_private_http_auth_runs_before_provider_resolution(self):
        url=self.serve()
        with patch('providers.metadata_discovery.configured_discovery_provider') as factory:
            code,_=self.request(url,'/internal/v1/search/teams?provider=espn&query=rams',token='wrong')
            self.assertEqual(code,401);factory.assert_not_called()

    def test_private_http_failure_is_503_without_empty_success(self):
        url=self.serve()
        code,body=self.request(url,'/internal/v1/events?provider=espn&user_id=owner&league_id=football%2Fnfl')
        self.assertEqual(code,503);self.assertNotIn('events',body)

    def test_private_follow_preserves_event_team_and_league_ids(self):
        self.warm();url=self.serve()
        event=self.provider.fetch_games()[0]
        team=self.provider.search_teams('rams')[0]
        for kind,target in [('event',event['provider_event_id']),('team',team['id']),('league',NFL)]:
            with self.subTest(kind=kind), patch.object(private_api,'create_subscription',return_value=({'type':kind,'provider':'espn','id':target,'user':'owner'},True)) as create:
                code,body=self.request(url,'/internal/v1/subscriptions',{'type':kind,'provider':'espn','provider_id':target,'user_id':'owner'})
                self.assertEqual(code,200);self.assertEqual(body['subscription']['id'],target)
                self.assertEqual(create.call_args.args[:3],(kind,'espn',target))
        self.assert_no_upstream_or_aliases()

    def test_metadata_recording_enable_is_rejected_but_disable_allowed(self):
        row={'subscription_id':'saved','type':'event','provider':'espn','id':encode_entity_id(NFL,'1'),'name':'Game','user':'owner','enabled':True,'record':False}
        with patch.object(subscriptions,'load_subscriptions',return_value=[row]),patch.object(subscriptions,'write_subscriptions') as write:
            with self.assertRaises(ValueError):subscriptions.update_subscription_recording('saved','owner',True)
            write.assert_not_called()
            self.assertIsNone(subscriptions.update_subscription_recording('saved','other',True))
            self.assertFalse(subscriptions.update_subscription_recording('saved','owner',False)['record'])
            write.assert_called_once()


if __name__=='__main__':unittest.main()
