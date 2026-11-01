from pathlib import Path
import ast, copy, importlib.util, io, json, os, sys, tempfile, types, unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'modules/sports/src'));sys.path.insert(0,str(ROOT))
import curated_live_events as c
import feed

class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,1,18,tzinfo=timezone.utc)
        self.follow={'provider':'espn','type':'team','id':'football-nfl-5','enabled':True}
        self.event=dict(provider='espn',provider_event_id='football-nfl-401873027',provider_league_id='football/nfl',
            home_team_id='football-nfl-23',away_team_id='football-nfl-5',start_at='2026-11-01T18:00:00Z',
            status='scheduled',name='Cleveland Browns at Pittsburgh Steelers',sport='American football',league='NFL',
            metadata_observed_at='2026-11-01T17:59:00Z',metadata_expires_at='2026-11-01T18:04:00Z')
        self.schedule=dict(provider='espn',provider_league_id='football/nfl',status='ready',events=[self.event])
        self.directory=dict(provider='espn',provider_league_id='football/nfl',status='ready',
            observed_at='2026-11-01T17:30:00Z',expires_at='2026-11-01T18:30:00Z',
            teams=[{'id':'football-nfl-23','name':'Pittsburgh Steelers'},{'id':'football-nfl-5','name':'Cleveland Browns'}])
    def project(self):
        return c.project_events(self.schedule,self.directory,[self.follow],route='football/nfl',now=self.now)
    def test_exact_follow_projects_event_and_names(self):
        row=self.project()[0];self.assertEqual(row['provider_event_id'],self.event['provider_event_id'])
        self.assertEqual(row['home_team'],'Pittsburgh Steelers');self.assertFalse(row['record'])
    def test_start_time_does_not_infer_live(self):
        self.now+=timedelta(minutes=1);self.assertEqual(self.project()[0]['lifecycle_state'],'scheduled')
    def test_provider_live_status_is_preserved(self):
        self.event['status']='live';self.assertEqual(self.project()[0]['lifecycle_state'],'live')
    def test_terminal_and_unknown_statuses_excluded(self):
        for status in ('final','cancelled','postponed','unknown'):
            self.event['status']=status;self.assertEqual(self.project(),[])
    def test_stale_or_future_observation_excluded(self):
        for observed,expires in (('2026-11-01T17:00:00Z','2026-11-01T18:04:00Z'),
                                ('2026-11-01T18:01:00Z','2026-11-01T18:04:00Z'),
                                ('2026-11-01T17:59:00Z','2026-11-01T18:00:00Z')):
            self.event.update(metadata_observed_at=observed,metadata_expires_at=expires)
            self.assertEqual(self.project(),[])
    def test_wrong_provider_follow_does_not_alias_same_team(self):
        self.follow['provider']='thesportsdb';self.assertEqual(self.project(),[])
    def test_event_and_league_follow_match_exact_ids(self):
        for kind,identity in (('event',self.event['provider_event_id']),('league','football/nfl')):
            self.follow.update(type=kind,id=identity);self.assertEqual(len(self.project()),1)
    def test_duplicate_event_is_refused(self):
        self.schedule['events'].append(dict(self.event))
        with self.assertRaises(c.CuratedLiveUnavailable):self.project()
    def test_wrong_directory_route_is_refused(self):
        self.directory['provider_league_id']='basketball/nba'
        with self.assertRaises(c.CuratedLiveUnavailable):self.project()
    def test_missing_participant_is_refused(self):
        self.directory['teams'].pop()
        with self.assertRaises(c.CuratedLiveUnavailable):self.project()
    def test_far_future_event_excluded(self):
        self.event['start_at']='2026-11-01T21:00:00Z';self.assertEqual(self.project(),[])
    def test_expired_team_directory_is_refused(self):
        self.directory['expires_at']='2026-11-01T17:59:00Z'
        with self.assertRaises(c.CuratedLiveUnavailable):self.project()
    def test_disabled_feature_never_reads_writer(self):
        client=types.SimpleNamespace(get=lambda *a: self.fail('unexpected request'))
        self.assertEqual(c.load_curated_live_events(environ={},client=client),[])
    def test_no_espn_follows_never_constructs_client(self):
        with patch.object(c,'CacheClient',side_effect=AssertionError('unexpected request')):
            self.assertEqual(c.load_curated_live_events(environ={'ATLAS_SPORTS_CURATED_LIVE_ENABLED':'1'},subscriptions=[]),[])
    def test_unsupported_college_follow_never_constructs_client(self):
        with patch.object(c,'CacheClient',side_effect=AssertionError('unexpected request')):
            self.assertEqual(c.load_curated_live_events(environ={'ATLAS_SPORTS_CURATED_LIVE_ENABLED':'1'},
                subscriptions=[{'provider':'espn','type':'league','id':'football/college-football'}]),[])
    def test_loader_reads_only_followed_route(self):
        seen=[]
        def get(kind,query):
            seen.append((kind,query));return self.directory if kind=='teams' else self.schedule
        rows=c.load_curated_live_events(environ={'ATLAS_SPORTS_CURATED_LIVE_ENABLED':'1'},subscriptions=[self.follow],
            now=self.now,client=types.SimpleNamespace(get=get))
        self.assertEqual(len(rows),1);self.assertEqual(len(seen),2)
        self.assertTrue(all(query['competition']=='nfl' for _,query in seen))
    def test_cache_failure_is_not_authoritative_empty(self):
        self.schedule['status']='unavailable'
        with self.assertRaises(c.CuratedLiveUnavailable):self.project()
    def test_same_names_with_other_provider_remain_distinct(self):
        legacy=dict(self.event,provider='thesportsdb',provider_event_id='2475422')
        self.assertEqual(len(c.merge_event_games([legacy],self.project())),2)
    def test_duplicate_identity_is_refused(self):
        rows=self.project()
        with self.assertRaises(c.CuratedLiveUnavailable):c.merge_event_games(rows,rows)
    def test_feed_requires_live_source_authorization(self):
        from live_sources import LiveSource,LiveSourceCatalog
        rows=self.project();empty=LiveSourceCatalog(())
        self.assertEqual(feed.catalog_feed_games(rows,empty),[])
        source=LiveSource(source_id='espn-'+self.event['provider_event_id'],name=self.event['name'],
            stream_url='http://atlas-dispatcharr:9191/proxy/ts/stream/test',provider='espn',
            provider_event_id=self.event['provider_event_id'])
        mapped=feed.catalog_feed_games(rows,LiveSourceCatalog((source,)))
        self.assertEqual(len(mapped),1);self.assertEqual(mapped[0]['_atlas_channel_id'],source.atlas_channel_id)
    def test_feed_rebuild_retains_curated_event_across_two_cycles(self):
        from live_sources import LiveSource,LiveSourceCatalog
        source=LiveSource(source_id='espn-'+self.event['provider_event_id'],name=self.event['name'],
            stream_url='http://atlas-dispatcharr:9191/proxy/ts/stream/test',provider='espn',provider_event_id=self.event['provider_event_id'])
        with tempfile.TemporaryDirectory() as d,patch.object(feed,'OUTPUT_DIR',Path(d)),\
             patch.object(feed,'M3U_FILE',Path(d)/'sports.m3u'),patch.object(feed,'XMLTV_FILE',Path(d)/'sports.xml'),\
             patch.object(feed,'load_games',return_value={}),patch.object(feed,'load_live_source_catalog',return_value=LiveSourceCatalog((source,))),\
             patch('builtins.print'):
            for _ in range(2):
                _,ids=feed.generate_feed_snapshot(curated_games=self.project())
                self.assertIn(source.atlas_channel_id,ids)
                self.assertIn(source.atlas_channel_id,(Path(d)/'sports.m3u').read_text())

class TransportTests(unittest.TestCase):
    def test_external_origin_and_url_credentials_refused(self):
        for url in ('https://espn.com','http://user:secret@atlas-sports-writer:8003','http://atlas-sports-writer:8003/private'):
            with self.assertRaises(c.CuratedLiveUnavailable):c.CacheClient(url,'token')
    def test_get_only_cache_endpoint_and_bounded_response(self):
        requests=[]
        class Response(io.BytesIO):
            status=200
        def opener(request,**kwargs):
            requests.append(request);return Response(b'{"ok":true}')
        client=c.CacheClient('http://atlas-sports-writer:8003','secret',opener=opener)
        self.assertEqual(client.get('teams',{'competition':'nfl'}),{'ok':True})
        self.assertEqual(requests[0].method,'GET');self.assertIn('/internal/v1/curated/teams?',requests[0].full_url)
        with self.assertRaises(c.CuratedLiveUnavailable):client.get('refresh',{})
    def test_request_budget_refuses_eleventh_read(self):
        class Response(io.BytesIO):status=200
        client=c.CacheClient('http://atlas-sports-writer:8003','secret',opener=lambda *a,**kw:Response(b'{}'))
        for _ in range(10):client.get('teams',{})
        with self.assertRaises(c.CuratedLiveUnavailable):client.get('teams',{})
    def test_transport_exception_does_not_export_credentials(self):
        def opener(*a,**kw):raise RuntimeError('secret-token-url')
        client=c.CacheClient('http://atlas-sports-writer:8003','secret',opener=opener)
        with self.assertRaises(c.CuratedLiveUnavailable) as result:client.get('teams',{})
        self.assertNotIn('secret',str(result.exception))
    def test_stream_inventory_fetched_once_per_account_per_cycle(self):
        calls=[]
        class Backend:
            def list_streams(self,*,account_id):calls.append(account_id);return [account_id]
            def create_channel(self):return 'existing mutation boundary'
        client=c.ImportedStreamSnapshot(Backend())
        self.assertEqual(client.list_streams(account_id=1),(1,));client.list_streams(account_id=1)
        client.list_streams(account_id=2);self.assertEqual(calls,[1,2]);self.assertEqual(client.create_channel(),'existing mutation boundary')

class ControllerIntegrationTests(unittest.TestCase):
    def test_disabled_feature_preserves_zero_argument_feed_and_skips_follow_read(self):
        tree=ast.parse((ROOT/'modules/sports/src/worker.py').read_text())
        fn=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='run_operations_pipeline')
        calls=[]
        no_op=lambda *args,**kwargs:None
        def snapshot():calls.append('legacy-feed');return 0,()
        def fail_follow_read():self.fail('disabled integration must not read follows')
        namespace=dict(Any=object,os=types.SimpleNamespace(getenv=lambda *args:'0'),
            prune_unmanaged_games=no_op,process_games=lambda *a,**kw:{},
            load_curated_live_events=lambda **kw:c.load_curated_live_events(**kw,environ={}),
            active_subscriptions=fail_follow_read,PREGAME_WINDOW_MINUTES=60,
            merge_event_games=c.merge_event_games,run_live_source_provisioning_pipeline=no_op,
            generate_feed_snapshot=snapshot,refresh_jellyfin_live_tv=no_op,
            converge_jellyfin_live_tv_bindings=no_op,write_provider_health=no_op,
            publish_provider_health_event=no_op,write_heartbeat=no_op,
            write_health_report=lambda:{'status':'healthy'},
            recording_counts=lambda recordings:dict(pending=0,active=0,completed=0),print=no_op)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'reviewed_worker.py','exec'),namespace)
        result=dict(previous_games={},subscribed_previous_games={},provider_games=[],
            provider_health={},subscribed_games=[],degraded_count=0)
        self.assertEqual(namespace['run_operations_pipeline'](result,{}),0)
        self.assertEqual(calls,['legacy-feed'])
    def test_one_snapshot_reaches_provisioning_and_feed_in_same_cycle(self):
        tree=ast.parse((ROOT/'modules/sports/src/worker.py').read_text())
        fn=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='run_operations_pipeline')
        module=ast.Module(body=[fn],type_ignores=[])
        projected=[{'provider':'espn','provider_event_id':'football-nfl-401873027'}]
        captured={}
        def provision(games):captured['provision']=games
        def snapshot(*,curated_games):captured['feed']=curated_games;return 0,()
        no_op=lambda *args,**kwargs:None
        namespace=dict(Any=object,os=types.SimpleNamespace(getenv=lambda *args:'1'),prune_unmanaged_games=no_op,process_games=lambda *a,**kw:{},
            load_curated_live_events=lambda **kw:projected,active_subscriptions=lambda:[],
            PREGAME_WINDOW_MINUTES=60,merge_event_games=c.merge_event_games,
            run_live_source_provisioning_pipeline=provision,generate_feed_snapshot=snapshot,
            refresh_jellyfin_live_tv=no_op,converge_jellyfin_live_tv_bindings=no_op,
            write_provider_health=no_op,publish_provider_health_event=no_op,write_heartbeat=no_op,
            write_health_report=lambda:{'status':'healthy'},
            recording_counts=lambda recordings:dict(pending=0,active=0,completed=0),print=no_op)
        exec(compile(module,'reviewed_worker.py','exec'),namespace)
        provider_result=dict(previous_games={},subscribed_previous_games={},provider_games=[],
            provider_health={},subscribed_games=[],degraded_count=0)
        self.assertEqual(namespace['run_operations_pipeline'](provider_result,{}),0)
        self.assertEqual(captured['provision'],projected);self.assertIs(captured['feed'],projected)
    def test_recording_planning_still_uses_legacy_subscribed_games(self):
        tree=ast.parse((ROOT/'modules/sports/src/worker.py').read_text())
        fn=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='run_cycle')
        calls=[node for node in ast.walk(fn) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
               and node.func.id=='run_recording_pipeline']
        self.assertEqual(len(calls),1)
        self.assertEqual(ast.unparse(calls[0].args[0]),"provider_result['subscribed_games']")

if __name__=='__main__':unittest.main()
