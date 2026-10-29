"""Deterministic provider coordination checks; no external HTTP requests."""
from pathlib import Path
import ast
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
from providers.shared_request_cache import (
    SharedRequestCache, SharedRequestDeferred, SharedResponseUnavailable,
    MAX_ENTRIES, MAX_TOTAL_BYTES,
)

class Clock:
    def __init__(self): self.value = 1000.0
    def __call__(self): return self.value

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name) / 'shared'
        self.clock = Clock()
        self.cache = SharedRequestCache(self.root, 'private-key', clock=self.clock)
        self.calls = 0
    def tearDown(self): self.folder.cleanup()
    def fetch(self):
        self.calls += 1
        return {'events': [{'id': 1}]}
    def get(self, query='NBA', *, background=False, fetch=None, ttl=60, cache=None):
        return (cache or self.cache).get_or_fetch('search.php', {'q': query}, ttl=ttl,
            background=background, fetch=fetch or self.fetch)

    def test_reload_and_new_instances_reuse_one_response_without_renewing_age(self):
        first = self.get()
        self.clock.value += 30
        other = SharedRequestCache(self.root, 'private-key', clock=self.clock)
        second = self.get(cache=other)
        self.assertEqual(first, second)
        self.assertEqual(first.observed_at, 1000)
        self.assertEqual(self.calls, 1)
    def test_expiry_requires_new_fetch(self):
        self.get(); self.clock.value += 60
        self.assertEqual(self.get().observed_at, 1060)
        self.assertEqual(self.calls, 2)
    def test_parameter_order_does_not_duplicate_fetch(self):
        call = lambda p: self.cache.get_or_fetch('teams', p, ttl=60, background=False, fetch=self.fetch)
        call({'a': 'x', 'b': 'y'}); call({'b': 'y', 'a': 'x'})
        self.assertEqual(self.calls, 1)
    def test_cache_partitions_credentials_and_endpoints(self):
        self.get()
        other = SharedRequestCache(self.root, 'other-key', clock=self.clock)
        self.get(cache=other)
        self.cache.get_or_fetch('different.php', {'q': 'NBA'}, ttl=60, background=False, fetch=self.fetch)
        self.assertEqual(self.calls, 3)
    def test_background_cannot_consume_reserved_interactive_capacity(self):
        for i in range(12):
            self.clock.value = 1000+i*4
            self.get(str(i), background=True)
        self.clock.value = 1048
        with self.assertRaises(SharedRequestDeferred): self.get('background-13', background=True)
        self.get('interactive', background=False)
        self.assertEqual(self.calls, 13)
    def test_global_total_limit_is_not_raised(self):
        for i in range(20):
            self.clock.value = 1000+i*3
            self.get(str(i))
        self.clock.value = 1058
        with self.assertRaises(SharedRequestDeferred): self.get('request-21')
        self.assertEqual(self.calls, 20)
    def test_bursts_are_deferred_without_http(self):
        for i in range(4): self.get(str(i))
        with self.assertRaises(SharedRequestDeferred) as context: self.get('fifth')
        self.assertEqual(context.exception.retry_after_seconds, 10)
        self.assertEqual(self.calls, 4)
    def test_cache_hit_during_full_budget_uses_no_admission(self):
        for i in range(4): self.get(str(i))
        self.get('0')
        self.assertEqual(self.calls, 4)
    def test_failed_http_is_charged_and_has_short_negative_cache(self):
        def fail():
            self.calls += 1
            raise RuntimeError('private upstream details')
        with self.assertRaises(RuntimeError): self.get(fetch=fail)
        with self.assertRaises(SharedResponseUnavailable): self.get()
        self.assertEqual(self.calls, 1)
        with self.cache.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM admissions').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM cache').fetchone()[0], 0)
            self.assertNotIn('private upstream details', str(db.execute('SELECT * FROM failures').fetchall()))
    def test_failed_response_is_retried_only_after_backoff(self):
        with self.assertRaises(RuntimeError): self.get(fetch=lambda: (_ for _ in ()).throw(RuntimeError()))
        self.clock.value += 15
        self.get()
        self.assertEqual(self.calls, 1)
    def test_slow_response_is_not_published_as_fresh(self):
        def slow():
            self.clock.value += 61
            return {'events': []}
        with self.assertRaises(SharedResponseUnavailable): self.get(fetch=slow)
        with self.cache.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM cache').fetchone()[0], 0)
    def test_clock_regression_refuses_even_cached_data(self):
        self.get(); self.clock.value = 999
        with self.assertRaises(SharedResponseUnavailable): self.get()
    def test_invalid_or_excessive_payload_is_not_cached(self):
        for payload in ([], {'value': float('nan')}, {'value': 'x'*(1024*1024)}):
            with self.subTest(payload_type=type(payload).__name__):
                self.clock.value += 16
                with self.assertRaises(ValueError): self.get(fetch=lambda: payload)
    def test_cached_return_is_not_shared_mutable_memory(self):
        first = self.get(); first.payload['events'].clear()
        self.assertEqual(len(self.get().payload['events']), 1)
    def test_cache_is_bounded_and_expired_rows_are_removed(self):
        with self.cache.connect() as db:
            for i in range(MAX_ENTRIES+2):
                db.execute('INSERT INTO cache VALUES (?,?,?,?,?)', (str(i), '{}', 999, 300, 40000))
        self.get()
        with self.cache.connect() as db:
            count,total = db.execute('SELECT count(*),sum(bytes) FROM cache').fetchone()
        self.assertLessEqual(count, MAX_ENTRIES)
        self.assertLessEqual(total, MAX_TOTAL_BYTES)
    def test_unsafe_directory_and_database_symlink_refuse(self):
        self.root.chmod(0o755)
        with self.assertRaises(ValueError): self.get()
        self.root.chmod(0o700)
        linkroot = Path(self.folder.name) / 'other'; linkroot.mkdir(mode=0o700)
        (linkroot/'cache.sqlite').symlink_to(self.cache.database)
        with self.assertRaises(OSError): SharedRequestCache(linkroot, 'key')
    def test_directory_replacement_is_detected(self):
        self.root.rename(self.root.with_name('saved'))
        self.root.mkdir(mode=0o700)
        with self.assertRaises(ValueError): self.get()
    def test_cross_process_inflight_request_is_not_duplicated(self):
        marker = Path(self.folder.name)/'started'
        release = Path(self.folder.name)/'release'
        child = '''import json,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from providers.shared_request_cache import SharedRequestCache,SharedRequestDeferred
cache=SharedRequestCache(sys.argv[2], 'private-key',clock=lambda:1000)
def fetch():
 Path(sys.argv[3]).write_text('started')
 until=time.monotonic()+10
 while not Path(sys.argv[4]).exists() and time.monotonic()<until:time.sleep(0.01)
 assert Path(sys.argv[4]).exists()
 return {'events':[]}
try:
 reply=cache.get_or_fetch('search.php',{'q':'NBA'},ttl=60,background=False,fetch=fetch)
 print('cached-or-fetched')
except SharedRequestDeferred: print('deferred')
'''
        args=[sys.executable,'-I','-S','-B','-c',child,str(SRC),str(self.root),str(marker),str(release)]
        first=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            until=time.monotonic()+5
            while not marker.exists() and time.monotonic()<until: time.sleep(0.01)
            self.assertTrue(marker.exists())
            second=subprocess.run(args,capture_output=True,timeout=5)
            self.assertEqual(second.returncode,0,second.stderr.decode())
            self.assertEqual(second.stdout.strip(),b'deferred')
            release.write_text('release')
            stdout,stderr=first.communicate(timeout=5)
            self.assertEqual(first.returncode,0,stderr.decode())
            self.assertEqual(stdout.strip(),b'cached-or-fetched')
            with self.cache.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM admissions').fetchone()[0],1)
        finally:
            if first.poll() is None: first.kill();first.wait()

class ProviderTests(unittest.TestCase):
    def setUp(self):
        from providers import thesportsdb
        self.provider_module=thesportsdb
        self.folder=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'SPORTS_SHARED_METADATA_CACHE_ENABLED':'1','SPORTS_THESPORTSDB_API_KEY':'test-key'})
        self.env.start()
        self.budget=patch.object(thesportsdb,'_PROVIDER_BUDGET_FILE',Path(self.folder.name)/'budget.json');self.budget.start()
        thesportsdb._reset_request_budget_for_tests()
    def tearDown(self):
        self.budget.stop();self.env.stop();self.folder.cleanup()
    def test_provider_instances_reuse_one_upstream_search(self):
        response=lambda *_args,**_kwargs:io.StringIO(json.dumps({'teams':[]}))
        with patch.object(self.provider_module.urllib.request,'urlopen',side_effect=response) as fetch:
            self.provider_module.TheSportsDBProvider().search_leagues('NBA')
            self.provider_module._RESPONSE_CACHE.clear()
            self.provider_module.TheSportsDBProvider().search_leagues('NBA')
        self.assertEqual(fetch.call_count,1)
    def test_cold_miss_honors_original_provider_cooldown(self):
        self.provider_module._write_shared_rate_limit_until(time.time()+120)
        with patch.object(self.provider_module.urllib.request,'urlopen') as fetch:
            with self.assertRaises(self.provider_module.SportsProviderRateLimitError):
                self.provider_module.TheSportsDBProvider().search_leagues('NBA')
        fetch.assert_not_called()
    def test_background_context_is_reset_after_failure(self):
        provider=self.provider_module.TheSportsDBProvider()
        def fail(*args,**kwargs):
            self.assertTrue(self.provider_module._BACKGROUND_FETCH.get())
            raise RuntimeError('fixture')
        with patch.object(provider,'_fetch_games_resumable',side_effect=fail):
            with self.assertRaises(RuntimeError):provider.fetch_games_resumable()
        self.assertFalse(self.provider_module._BACKGROUND_FETCH.get())
    def test_feature_is_default_off(self):
        with patch.dict(os.environ,{'SPORTS_SHARED_METADATA_CACHE_ENABLED':'0'}):
            provider=self.provider_module.TheSportsDBProvider()
            with patch.object(provider,'_request_json_local',return_value={'teams':[]}) as local:
                provider.search_leagues('NBA')
                local.assert_called_once()
        self.assertFalse((Path(self.folder.name)/'provider-request-coordination').exists())

class PrivateEventsTests(unittest.TestCase):
    def invoke(self, failure=None):
        # Execute the actual selected handler methods, without importing the
        # application's production stores or starting a server/provider.
        import urllib.parse
        from http import HTTPStatus
        tree=ast.parse((SRC/'private_api.py').read_text())
        handler=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Handler')
        methods=[n for n in handler.body if isinstance(n,ast.FunctionDef)
                 and n.name in {'do_GET','_backend_unavailable','_provider_rate_limited'}]
        class Provider:
            name='thesportsdb'
            def fetch_games(self,**kwargs):
                if failure is not None:raise failure
                return []
        namespace={'urllib':urllib,'HTTPStatus':HTTPStatus,'json':json,'_provider':lambda _:Provider()}
        exec(compile(ast.Module(body=methods,type_ignores=[]),str(SRC/'private_api.py'),'exec'),namespace)
        class Fixture:
            path='/internal/v1/events?provider=thesportsdb&user_id=fixture&league_id=4391'
            def __init__(self):self.headers={};self.wfile=io.BytesIO();self.payload=None
            def _require_auth(self):return True
            def _user_subscriptions(self,_):return []
            def _json(self,status,payload):self.status=status;self.payload=payload
            def send_response(self,status):self.status=status
            def send_header(self,key,value):self.headers[key]=value
            def end_headers(self):pass
        for name in ('do_GET','_backend_unavailable','_provider_rate_limited'):
            setattr(Fixture,name,namespace[name])
        fixture=Fixture();fixture.do_GET();return fixture
    def test_actual_private_events_handler_preserves_throttle(self):
        from providers.thesportsdb import SportsProviderRateLimitError
        result=self.invoke(SportsProviderRateLimitError(55))
        self.assertEqual(result.status,429)
        self.assertEqual(result.headers['Retry-After'],'55')
        self.assertEqual(json.loads(result.wfile.getvalue())['code'],'sports_provider_rate_limited')
    def test_other_provider_error_still_returns_generic_503(self):
        result=self.invoke(RuntimeError('private sensitive details'))
        self.assertEqual(result.status,503)
        self.assertNotIn('private sensitive details',json.dumps(result.payload))
    def test_successful_empty_events_remain_200(self):
        result=self.invoke()
        self.assertEqual(result.status,200)
        self.assertEqual(result.payload,{'events':[]})

if __name__ == '__main__': unittest.main()
