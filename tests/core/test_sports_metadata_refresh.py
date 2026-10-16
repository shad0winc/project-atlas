from dataclasses import replace
from datetime import date,datetime,timezone
from http.server import ThreadingHTTPServer
import json
import os
import signal
import subprocess
import time
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'modules/sports/src'));sys.path.insert(0,str(ROOT))
from providers.metadata_refresh import (
    RefreshPolicyError,parse_refresh_policy,load_refresh_policy,
    next_refresh_job,MetadataRefreshWorker,start_configured_refresh,
)
from providers.metadata_broker import MetadataBroker,MetadataUnavailable
from providers.metadata_store import MetadataStore
from providers.espn_metadata import LEAGUE_UIDS,ROUTES
from providers import metadata_service
import private_api

STAMP=datetime(2026,10,16,tzinfo=timezone.utc).timestamp()
ROUTE='football/nfl'


def document(**changes):
    value={'version':1,'enabled':True,'routes':[ROUTE],'hourly_budget':96,
           'current_ttl':60,'past_ttl':3600,'future_ttl':3600,'directory_ttl':3600,
           'tick_seconds':1,'generation':'offline-test'}
    value.update(changes);return value


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.now=STAMP;self.calls=[];self.failure=None
        self.policy=parse_refresh_policy(document())
        source=json.loads((ROOT/'tests/fixtures/sports/espn-team-directories-20261016.json').read_text())
        self.directories={row['route']:row['payload'] for row in source['samples']}
        self.directory=self.directories[ROUTE]
        outer=self
        class Transport:
            def __call__(self,route,day):
                outer.calls.append(('day',route,day))
                if outer.failure:raise outer.failure
                return {'leagues':[{'uid':LEAGUE_UIDS[route]}],'events':[]}
            def fetch_teams(self,route):
                outer.calls.append(('teams',route))
                if outer.failure:raise outer.failure
                return outer.directories[route]
        self.broker=MetadataBroker(MetadataStore(self.root/'metadata.sqlite'),
            transport=Transport(),clock=lambda:self.now,**dict(self.policy.broker_settings))
        self.worker=MetadataRefreshWorker(lambda:self.policy,lambda policy:self.broker,clock=lambda:self.now)

    def write_policy(self,data=None):
        path=self.root/'refresh.json';path.write_text(json.dumps(document() if data is None else data));path.chmod(0o600)
        return path

    def run_once(self):
        def wait(delay):
            self.delay=delay;self.worker.stop_event.set();return True
        with patch.object(self.worker.stop_event,'wait',side_effect=wait):self.worker._run()

    def test_disabled_missing_and_empty_configuration_start_no_worker(self):
        with patch.dict(os.environ,{'ATLAS_SPORTS_METADATA_REFRESH_FILE':''}),patch.object(metadata_service,'configured_broker') as factory:
            self.assertIsNone(start_configured_refresh());factory.assert_not_called()
        self.assertIsNone(load_refresh_policy(self.root/'missing.json'))
        self.assertIsNone(parse_refresh_policy({'version':1,'enabled':False}))

    def test_enabled_policy_has_explicit_scope_and_stable_fingerprint(self):
        self.assertEqual(load_refresh_policy(self.write_policy()),self.policy)
        self.assertEqual(parse_refresh_policy(document()).fingerprint,self.policy.fingerprint)
        self.assertNotEqual(parse_refresh_policy(document(generation='next')).fingerprint,self.policy.fingerprint)

    def test_all_six_routes_need_a_budget_matching_the_declared_cadence(self):
        with self.assertRaises(RefreshPolicyError):parse_refresh_policy(document(routes=list(ROUTES)))
        policy=parse_refresh_policy(document(routes=list(ROUTES),hourly_budget=480))
        self.assertEqual(len(policy.routes),6)

    def test_invalid_limits_unknown_fields_and_duplicate_routes_rejected(self):
        for changes in ({'hourly_budget':True},{'tick_seconds':0},{'current_ttl':0},
                        {'past_ttl':60},{'routes':[ROUTE,ROUTE]},{'routes':['other']},
                        {'routes':[]},{'unknown':1},{'generation':'../bad'}):
            with self.subTest(changes=changes),self.assertRaises(RefreshPolicyError):
                parse_refresh_policy(document(**changes))

    def test_disabled_policy_cannot_hide_active_fields(self):
        with self.assertRaises(RefreshPolicyError):parse_refresh_policy(document(enabled=False))

    def test_symlink_fifo_unsafe_permissions_and_duplicate_json_rejected(self):
        path=self.write_policy();link=self.root/'link.json';link.symlink_to(path)
        with self.assertRaises(RefreshPolicyError):load_refresh_policy(link)
        path.chmod(0o666)
        with self.assertRaises(RefreshPolicyError):load_refresh_policy(path)
        path.chmod(0o600);path.write_text('{"version":1,"enabled":false,"enabled":true}')
        with self.assertRaises(RefreshPolicyError):load_refresh_policy(path)
        fifo=self.root/'fifo';os.mkfifo(fifo,0o600)
        with self.assertRaises(RefreshPolicyError):load_refresh_policy(fifo)

    def test_oversized_and_relative_policy_paths_rejected(self):
        path=self.write_policy();path.write_bytes(b' '*16385)
        with self.assertRaises(RefreshPolicyError):load_refresh_policy(path)
        with self.assertRaises(RefreshPolicyError):load_refresh_policy('relative.json')

    def test_cold_planning_is_cache_only_and_prioritizes_today(self):
        job=next_refresh_job(self.broker,self.policy,self.now)
        self.assertEqual(job.day,date(2026,10,16));self.assertEqual(self.calls,[])

    def test_each_tick_admits_at_most_one_upstream_request(self):
        self.worker.tick();self.assertEqual(len(self.calls),1)
        self.worker.tick();self.assertEqual(len(self.calls),2)
        self.assertEqual(self.calls[1][0],'teams')

    def test_full_nfl_warmup_covers_nine_dates_and_one_directory(self):
        for _ in range(10):self.worker.tick()
        self.assertEqual(len(self.calls),10)
        self.assertEqual(len({row[2] for row in self.calls if row[0]=='day'}),9)
        before=self.worker.status()['last_provider_success_at']
        self.now+=1;self.worker.tick()
        self.assertEqual(len(self.calls),10)
        self.assertEqual(self.worker.status()['state'],'waiting')
        self.assertEqual(self.worker.status()['last_provider_success_at'],before)

    def test_all_six_routes_warm_without_directory_requests_for_ufc(self):
        self.policy=parse_refresh_policy(document(routes=list(ROUTES),hourly_budget=480))
        for _ in range(59):self.worker.tick()
        self.assertEqual(len(self.calls),59)
        self.assertEqual(sum(row[0]=='teams' for row in self.calls),5)
        self.assertIsNone(next_refresh_job(self.broker,self.policy,self.now))
        self.worker.tick();self.assertEqual(len(self.calls),59)

    def test_current_past_and_future_ttls_are_distinct(self):
        for day,ttl in ((date(2026,10,15),3600),(date(2026,10,16),60),(date(2026,10,17),3600)):
            snapshot=self.broker.fetch_day(ROUTE,day)
            self.assertEqual(snapshot.expires_at-snapshot.observed_at,ttl)

    def test_cache_hit_race_does_not_become_new_provider_success(self):
        snapshot=self.broker.fetch_day(ROUTE,date(2026,10,16))
        self.now+=1
        with patch('providers.metadata_refresh.next_refresh_job',return_value=type('Job',(),{'route':ROUTE,'day':date(2026,10,16)})()):
            self.worker.tick()
        self.assertEqual(self.worker.status()['state'],'cache-hit')
        self.assertIsNone(self.worker.status()['last_provider_success_at'])
        self.assertEqual(len(self.calls),1)

    def test_disable_or_invalid_policy_cannot_reach_the_broker(self):
        self.worker.policy_loader=lambda:None
        with patch.object(self.worker,'broker_factory') as factory:self.worker.tick();factory.assert_not_called()
        self.worker.policy_loader=lambda:(_ for _ in ()).throw(RefreshPolicyError('invalid'))
        self.run_once()
        self.assertEqual(self.worker.status()['last_failure_category'],'configuration')
        self.assertEqual(self.calls,[])

    def test_429_is_persisted_and_worker_waits_without_claiming_success(self):
        self.failure=MetadataUnavailable('rate-limit',http_status=429,retry_after=120)
        self.run_once()
        self.assertEqual(self.delay,120)
        self.assertEqual(self.worker.status()['last_failure_category'],'rate-limit')
        self.assertIsNone(self.worker.status()['last_provider_success_at'])
        self.assertIsNone(next_refresh_job(self.broker,self.policy,self.now))
        self.assertEqual(len(self.calls),1)

    def test_budget_exhaustion_does_not_open_another_upstream_request(self):
        self.broker.hourly_budget=1
        self.worker.tick();self.run_once()
        self.assertEqual(self.worker.status()['last_failure_category'],'request-budget')
        self.assertEqual(len(self.calls),1)

    def test_network_failure_does_not_publish_empty_or_renew_success(self):
        self.failure=MetadataUnavailable('network',retry_after=15)
        self.run_once()
        self.assertEqual(self.worker.status()['last_failure_category'],'network')
        self.assertIsNone(self.worker.status()['last_provider_success_at'])
        _,rows=self.broker.read_days(ROUTE,[date(2026,10,16)])
        self.assertEqual(rows[0].status,'missing')
        self.assertGreater(rows[0].retry_after_seconds,0)

    def test_ufc_scope_does_not_request_a_team_directory(self):
        self.policy=parse_refresh_policy(document(routes=['mma/ufc']))
        for _ in range(9):self.worker.tick()
        self.assertEqual(len(self.calls),9)
        self.assertTrue(all(row[0]=='day' for row in self.calls))

    def test_shutdown_flag_prevents_admission(self):
        self.worker.close();self.worker.tick();self.assertEqual(self.calls,[])

    def test_stop_during_cache_planning_prevents_the_selected_request(self):
        original=self.broker.read_days
        def read(*args):
            result=original(*args);self.worker.stop_event.set();return result
        with patch.object(self.broker,'read_days',side_effect=read):self.worker.tick()
        self.assertEqual(self.calls,[])

    def test_real_thread_stops_promptly_while_waiting(self):
        seen=threading.Event()
        original=self.worker.tick
        def tick():
            result=original();seen.set();return result
        with patch.object(self.worker,'tick',side_effect=tick):
            self.worker.start();self.assertTrue(seen.wait(2));self.assertTrue(self.worker.close(timeout=2))
        self.assertFalse(self.worker.status()['running'])
        self.assertEqual(self.worker.status()['state'],'stopped')
        with self.assertRaises(RuntimeError):self.worker.start()

    def test_service_uses_one_policy_for_shared_broker_settings(self):
        path=self.write_policy()
        with patch.dict(os.environ,{'ATLAS_SPORTS_METADATA_STATE_DIR':str(self.root),
                                   'ATLAS_SPORTS_METADATA_REFRESH_FILE':str(path)}),\
             patch.object(metadata_service,'_configured_broker',return_value=self.broker) as factory:
            self.assertIs(metadata_service.configured_broker(),self.broker)
            factory.assert_called_once_with(str(self.root),self.policy.broker_settings)
        path.write_text('{"version":1,"enabled":false}')
        with patch.dict(os.environ,{'ATLAS_SPORTS_METADATA_STATE_DIR':str(self.root),
                                   'ATLAS_SPORTS_METADATA_REFRESH_FILE':str(path)}),\
             patch.object(metadata_service,'_configured_broker') as factory:
            with self.assertRaises(MetadataUnavailable):metadata_service.configured_broker()
            factory.assert_not_called()

    def test_writer_lifecycle_closes_refresh_on_interrupt_and_clears_status(self):
        events=[]
        class Server:
            def serve_forever(self):events.append('serve');raise KeyboardInterrupt()
            def server_close(self):events.append('server-close')
        class Worker:
            def close(self,timeout):events.append(('worker-close',timeout));return True
        result=private_api._serve_with_metadata(Server(),lambda:Worker(),install_signals=False)
        self.assertEqual(result,0)
        self.assertEqual(events,['serve',('worker-close',25),'server-close'])
        self.assertIsNone(private_api._metadata_refresher)

    def test_failed_startup_still_closes_the_server(self):
        closed=[]
        class Server:
            def server_close(self):closed.append(True)
        def fail():raise RefreshPolicyError('invalid')
        with self.assertRaises(RefreshPolicyError):private_api._serve_with_metadata(Server(),fail,install_signals=False)
        self.assertEqual(closed,[True])

    def test_shutdown_timeout_does_not_pretend_clean_exit(self):
        closed=[]
        class Server:
            def serve_forever(self):pass
            def server_close(self):closed.append(True)
        class Worker:
            def close(self,timeout):return False
        with self.assertRaises(RuntimeError):private_api._serve_with_metadata(Server(),lambda:Worker(),install_signals=False)
        self.assertEqual(closed,[True]);self.assertIsNone(private_api._metadata_refresher)

    def test_real_sigterm_joins_inflight_refresh_and_closes_server(self):
        ready=self.root/'ready';closed=self.root/'closed'
        code=r"""
import sys,time
from pathlib import Path
from datetime import datetime,timezone
from providers.metadata_store import MetadataStore
from providers.metadata_broker import MetadataBroker
from providers.metadata_refresh import parse_refresh_policy,MetadataRefreshWorker
from providers.espn_metadata import LEAGUE_UIDS
from private_api import _serve_with_metadata
root=Path(sys.argv[1]);ready=root/'ready';closed=root/'closed'
stamp=datetime(2026,10,16,tzinfo=timezone.utc).timestamp()
policy=parse_refresh_policy({'version':1,'enabled':True,'routes':['football/nfl'],
 'hourly_budget':96,'current_ttl':60,'past_ttl':3600,'future_ttl':3600,
 'directory_ttl':3600,'tick_seconds':1,'generation':'subprocess-test'})
def fetch(route,day):
 ready.write_text('started');time.sleep(.25)
 return {'leagues':[{'uid':LEAGUE_UIDS[route]}],'events':[]}
broker=MetadataBroker(MetadataStore(root/'child.sqlite'),transport=fetch,clock=lambda:stamp,**dict(policy.broker_settings))
class Server:
 def serve_forever(self):
  while True:time.sleep(1)
 def server_close(self):closed.write_text('closed')
raise SystemExit(_serve_with_metadata(Server(),lambda:MetadataRefreshWorker(lambda:policy,lambda p:broker,clock=lambda:stamp).start()))
"""
        environment=dict(os.environ,PYTHONPATH=str(ROOT/'modules/sports/src')+os.pathsep+str(ROOT),PYTHONDONTWRITEBYTECODE='1')
        child=subprocess.Popen([sys.executable,'-B','-c',code,str(self.root)],env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+3
            while not ready.exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(ready.exists())
            child.send_signal(signal.SIGTERM)
            _,stderr=child.communicate(timeout=3)
            self.assertEqual(child.returncode,0,stderr.decode())
            self.assertEqual(closed.read_text(),'closed')
        finally:
            if child.poll() is None:child.kill();child.communicate()

    def test_private_status_requires_auth_and_does_not_initialize_metadata(self):
        with patch.dict(os.environ,{'ATLAS_SPORTS_WRITER_TOKEN':'test-only'}),\
             patch.object(metadata_service,'configured_broker') as factory:
            server=ThreadingHTTPServer(('127.0.0.1',0),private_api.Handler)
            thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.01),daemon=True);thread.start()
            url='http://127.0.0.1:'+str(server.server_port)+'/internal/v1/metadata/refresh-status'
            try:
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(url,timeout=2)
                self.assertEqual(error.exception.code,401)
                request=urllib.request.Request(url,headers={'Authorization':'Bearer test-only'})
                with urllib.request.urlopen(request,timeout=2) as response:data=json.load(response)
                self.assertEqual(data,{'version':1,'state':'disabled','running':False})
                factory.assert_not_called()
            finally:server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':unittest.main()
