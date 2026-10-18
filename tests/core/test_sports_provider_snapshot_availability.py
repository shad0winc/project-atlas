"""Offline bounded snapshot and health freshness regressions."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import importlib.util
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'modules/sports/src'))
from providers import thesportsdb as module
from atlas.sports_provider_snapshot_health import provider_snapshot_usable
spec=importlib.util.spec_from_file_location('_fixtures',Path(__file__).with_name('test_sports_provider_refresh_progress.py'))
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)

class SnapshotAvailabilityTests(unittest.TestCase):
    setUp=fixtures.RefreshProgressTests.setUp
    upstream=fixtures.RefreshProgressTests.upstream
    attempt=fixtures.RefreshProgressTests.attempt
    worker_context=fixtures.RefreshProgressTests.worker_context
    def complete(self):
        for elapsed in (0,120,240,360):
            self.clock=1000000+elapsed;client=module.TheSportsDBProvider()
            try: games=client.fetch_games_resumable(**self.args)
            except module.SportsProviderRateLimitError: continue
            self.assertIsNone(client.last_refresh_deferred);return client,games
        self.fail('No complete snapshot')
    def test_complete_data_and_timestamp_survive_deferral(self):
        first,games=self.complete();self.clock+=30;client=module.TheSportsDBProvider()
        self.assertEqual(client.fetch_games_resumable(**self.args),games)
        self.assertEqual(client.last_refresh_completed_at,first.last_refresh_completed_at)
        self.assertEqual(client.last_refresh_snapshot,first.last_refresh_snapshot)
        self.assertEqual(client.last_refresh_deferred['reason'],'rate-limit')
        self.assertTrue(next(iter(module._REFRESH_COMPLETE.values()))["responses"])
    def test_unknown_failure_invalidates_complete_snapshot(self):
        self.complete();self.clock+=30;self.failure=RuntimeError('offline failure')
        with self.assertRaises(RuntimeError):self.attempt()
        self.assertFalse(module._REFRESH_COMPLETE)
    def test_expired_snapshot_cannot_cover_deferral(self):
        self.complete();self.clock=1000901;self.limit_every=0
        with self.assertRaises(module.SportsProviderRateLimitError):self.attempt()
        self.assertFalse(module._REFRESH_COMPLETE)
    def test_new_target_cannot_reuse_prior_snapshot(self):
        self.complete();self.clock+=30
        with self.assertRaises(module.SportsProviderRateLimitError):self.attempt(args={**self.args,'team_ids':['different']})
    def test_worker_preserves_actual_completion_time(self):
        import worker
        self.complete();self.clock+=30
        with self.worker_context(worker,lambda:[module.TheSportsDBProvider()]):result=worker.run_provider_pipeline()
        row=result['provider_health']['thesportsdb']
        self.assertEqual(row['status'],'healthy');self.assertEqual(row['refresh_state'],'deferred')
        self.assertEqual(result['degraded_count'],0)
        self.assertEqual(datetime.fromisoformat(row['last_success_at']).timestamp(),1000360)
        self.assertTrue(provider_snapshot_usable(row,datetime.fromtimestamp(self.clock,timezone.utc)))
    def test_repeated_deferrals_do_not_renew_completion(self):
        first,_=self.complete()
        for elapsed in (390,420,450):
            self.clock=1000000+elapsed;client=module.TheSportsDBProvider();client.fetch_games_resumable(**self.args)
            self.assertIsNotNone(client.last_refresh_deferred)
            self.assertEqual(client.last_refresh_completed_at,first.last_refresh_completed_at)
    def test_second_completion_advances_timestamp(self):
        first,_=self.complete()
        for elapsed in range(390,901,30):
            self.clock=1000000+elapsed;client=module.TheSportsDBProvider()
            try:client.fetch_games_resumable(**self.args)
            except module.SportsProviderRateLimitError:continue
            if client.last_refresh_completed_at > first.last_refresh_completed_at:
                return
        self.fail('Following refresh did not complete')

    def test_populated_snapshot_is_reused_without_exposing_mutation(self):
        import io, json, urllib.parse
        from unittest.mock import patch
        upstream=self.upstream
        def populated(request,**kwargs):
            response=upstream(request,**kwargs)
            if 'lookupevent.php?' in request.full_url:
                identity=urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)['id'][0]
                return io.BytesIO(json.dumps({'events':[{'idEvent':identity,'strEvent':'Fixture','dateEvent':'2026-10-18','strTime':'12:00:00'}]}).encode())
            return response
        with patch.object(module.urllib.request,'urlopen',side_effect=populated):
            _,games=self.complete();self.assertEqual(len(games),21)
            original=copy.deepcopy(games);games[0]['name']='caller mutation';self.clock+=30
            returned=self.attempt();self.assertEqual(returned,original)
            returned.clear();self.clock+=30;self.assertEqual(self.attempt(),original)

    def test_complete_snapshot_storage_respects_total_memory_bound(self):
        from unittest.mock import patch
        self.complete()
        with patch.object(module,'_REFRESH_COMPLETE_MAX_BYTES',3):
            for team in ('another','third'):
                self.clock+=120;self.limit_every=0
                for _ in range(3):
                    try:self.attempt(args={**self.args,'team_ids':[team]});break
                    except module.SportsProviderRateLimitError:self.clock+=60
                self.assertLessEqual(sum(item['bytes'] for item in module._REFRESH_COMPLETE.values()),3)

    def test_clock_regression_discards_complete_coverage(self):
        self.complete();self.clock=1000359
        try:self.attempt()
        except Exception:pass
        self.assertFalse(module._REFRESH_COMPLETE)

class SnapshotHealthTests(unittest.TestCase):
    def row(self):return {'status':'healthy','last_success_at':'2026-10-18T17:00:00+00:00','refresh_state':'deferred','refresh_snapshot':{'version':1,'maximum_age_seconds':900,'oldest_response_age_seconds':479,'completed_request_count':38}}
    def test_combined_age_expires_at_original_bound(self):
        self.assertTrue(provider_snapshot_usable(self.row(),datetime.fromisoformat('2026-10-18T17:07:01+00:00')))
        self.assertFalse(provider_snapshot_usable(self.row(),datetime.fromisoformat('2026-10-18T17:07:02+00:00')))
    def test_future_and_naive_times_refused(self):
        row=self.row();self.assertFalse(provider_snapshot_usable(row,datetime.fromisoformat('2026-10-18T16:59:59+00:00')))
        row['last_success_at']='2026-10-18T17:00:00';self.assertFalse(provider_snapshot_usable(row))
    def test_invalid_contracts_refused(self):
        for field,value in [('version',True),('maximum_age_seconds',901),('completed_request_count',False),('oldest_response_age_seconds',float('nan')),('oldest_response_age_seconds',-1)]:
            with self.subTest(field=field):
                row=self.row();row['refresh_snapshot'][field]=value;self.assertFalse(provider_snapshot_usable(row))
    def test_missing_deferred_metadata_refused(self):
        row=self.row();del row['refresh_snapshot'];self.assertFalse(provider_snapshot_usable(row))
    def test_legacy_provider_behavior_retained(self):
        self.assertTrue(provider_snapshot_usable({'status':'healthy'}));self.assertFalse(provider_snapshot_usable({'status':'degraded'}))

    def test_controller_health_rejects_expired_snapshot(self):
        import health
        from unittest.mock import patch
        from datetime import timedelta
        row=self.row();row['last_success_at']=(datetime.now(timezone.utc)-timedelta(seconds=422)).isoformat()
        with patch.object(health,'load_json_object',return_value={'thesportsdb':row}):
            self.assertEqual(health.provider_health()['status'],'degraded')
        row['last_success_at']=datetime.now(timezone.utc).isoformat()
        with patch.object(health,'load_json_object',return_value={'thesportsdb':row}):
            self.assertEqual(health.provider_health()['status'],'healthy')

    def test_native_module_health_uses_same_freshness_bound(self):
        import tempfile,json
        from datetime import timedelta
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('_snapshot_module_health',ROOT/'modules/sports/scripts/health.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);heartbeat=root/'heartbeat';heartbeat.write_text('fixture')
            report=root/'providers.json'
            def path(value):return heartbeat if str(value).endswith('controller-heartbeat') else report
            for age,expected in ((0,'healthy'),(422,'critical')):
                row=self.row();row['last_success_at']=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat()
                report.write_text(json.dumps({'thesportsdb':row}))
                with patch.object(mod,'Path',side_effect=path),patch.object(mod,'container_state',side_effect=lambda name,field:'true' if 'Running' in field else 'healthy'),patch.object(mod,'endpoint_reachable',return_value=True),patch('builtins.print') as output:
                    self.assertEqual(mod.main(),0)
                checks=json.loads(output.call_args.args[0])['checks']
                self.assertEqual(next(item for item in checks if item['name']=='Provider Health')['status'],expected)

if __name__=='__main__':unittest.main()
