"""Offline progress tests: private files, synthetic HTTP, no production access."""
from contextlib import ExitStack
from datetime import datetime, timezone
import copy
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'modules/sports/src'
sys.path.insert(0, str(SOURCE)) if str(SOURCE) not in sys.path else None
from providers import thesportsdb as module


class RefreshProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        # The worker omits date_value; keep its default aligned with this fixture's
        # explicit discovery date, independently of the calendar on the test host.
        class FixtureDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                value = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
                return value.replace(tzinfo=None) if tz is None else value.astimezone(tz)
        self.stack.enter_context(patch.object(module, 'datetime', FixtureDatetime))
        self.clock = 1000000.
        self.calls = []
        self.limit_every = 11
        self.failure = None
        self.stack.enter_context(patch.dict(os.environ, {
            'SPORTS_THESPORTSDB_API_KEY': 'fixture-key', 'SPORTS_DISCOVERY_DAYS_AHEAD': '14'}))
        self.stack.enter_context(patch.object(module, '_PROVIDER_BUDGET_FILE', Path(self.temp.name) / 'budget.json'))
        self.stack.enter_context(patch.object(module.time, 'time', side_effect=lambda: self.clock))
        self.stack.enter_context(patch.object(module.time, 'monotonic', side_effect=lambda: self.clock))
        self.stack.enter_context(patch.object(module.urllib.request, 'urlopen', side_effect=self.upstream))
        module._reset_request_budget_for_tests()
        self.addCleanup(module._reset_request_budget_for_tests)
        self.args = dict(tracked_event_ids=[str(i) for i in range(17)],
                         event_ids=[str(i) for i in range(17, 21)],
                         team_ids=['team'], league_ids=['league'], date_value='2026-10-18')

    def upstream(self, request, **kwargs):
        self.calls.append((self.clock, request.full_url))
        if self.failure is not None: raise self.failure
        if self.limit_every and len(self.calls) % self.limit_every == 0:
            raise urllib.error.HTTPError('https://offline.invalid', 429, 'limited', {'Retry-After': '120'}, None)
        return io.BytesIO(b'{"events":[],"results":[]}')

    def attempt(self, resumable=True, args=None):
        client = module.TheSportsDBProvider()  # A new instance every worker cycle.
        method = client.fetch_games_resumable if resumable else client.fetch_games
        return method(**(self.args if args is None else args))

    def test_original_path_reproduces_30_minute_starvation(self):
        for elapsed in range(0, 1801, 30):
            self.clock = 1000000 + elapsed
            with self.assertRaises(module.SportsProviderRateLimitError): self.attempt(False)
        self.assertEqual(len(self.calls), 176)

    def test_new_instances_complete_38_requests_at_360_seconds(self):
        completed = None
        for elapsed in range(0, 901, 30):
            self.clock = 1000000 + elapsed
            try:
                self.assertEqual(self.attempt(), [])
                completed = elapsed
                break
            except module.SportsProviderRateLimitError: pass
        self.assertEqual(completed, 360)
        self.assertEqual(len(self.calls), 41)
        self.assertFalse(module._REFRESH_PROGRESS)
        successes = [url for index, (_, url) in enumerate(self.calls, 1) if index % 11]
        self.assertEqual(len(set(successes)), 38)
        self.assertEqual(module.TheSportsDBProvider().discovery_days_ahead, 14)

    def test_checkpoint_does_not_extend_normal_cache_expiry(self):
        with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
        key = next(iter(module._RESPONSE_CACHE))
        expiry = module._RESPONSE_CACHE[key][0]
        for elapsed in (120, 240):
            self.clock = 1000000 + elapsed
            with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
        self.clock = 1000360
        self.attempt()
        self.assertEqual(module._RESPONSE_CACHE[key][0], expiry)
        self.assertLess(expiry, self.clock)

    def test_interactive_requests_do_not_consume_checkpoint(self):
        with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
        before = copy.deepcopy(module._REFRESH_PROGRESS)
        self.clock += 360
        module.TheSportsDBProvider().request_json('eventslast.php', {'id': 'team'})
        self.assertEqual(module._REFRESH_PROGRESS, before)
        self.assertEqual(len(self.calls), 12)

    def test_cooldown_preserves_progress_and_makes_no_requests(self):
        with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
        before = copy.deepcopy(module._REFRESH_PROGRESS)
        budget = module._PROVIDER_BUDGET_FILE.read_bytes()
        self.clock += 30
        with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
        self.assertEqual(len(self.calls), 11)
        self.assertEqual(module._PROVIDER_BUDGET_FILE.read_bytes(), budget)
        self.assertEqual(module._REFRESH_PROGRESS, before)

    def test_expiry_discards_progress_and_fetches_fresh(self):
        with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
        self.clock += 901
        self.limit_every = 0
        before = len(self.calls)
        with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
        self.assertEqual(len(self.calls) - before, 20)
        self.assertEqual(next(iter(module._REFRESH_PROGRESS.values()))['oldest'], self.clock)

    def test_original_cached_observation_age_is_retained(self):
        self.limit_every = 0
        module.TheSportsDBProvider().request_json('eventslast.php', {'id': 'team'})
        self.clock += 250
        client = module.TheSportsDBProvider()
        original = client.request_json
        def defer(endpoint, parameters):
            if endpoint == 'eventsnext.php': raise module.SportsProviderRateLimitError(120)
            return original(endpoint, parameters)
        client.request_json = defer
        with self.assertRaises(module.SportsProviderRateLimitError): client.fetch_games_resumable(**self.args)
        self.assertEqual(next(iter(module._REFRESH_PROGRESS.values()))['oldest'], 1000000)

    def test_clock_regression_discards_progress(self):
        with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
        self.clock -= 1
        with self.assertRaisesRegex(RuntimeError, 'cache clock is invalid'): self.attempt()
        self.assertFalse(module._REFRESH_PROGRESS)

    def test_identity_changes_do_not_reuse_checkpoint(self):
        for change in ('target', 'credential', 'day'):
            with self.subTest(change=change):
                module._reset_request_budget_for_tests()
                module._PROVIDER_BUDGET_FILE.unlink(missing_ok=True)
                self.calls.clear()
                with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
                self.clock += 120
                client = module.TheSportsDBProvider()
                args = copy.deepcopy(self.args)
                if change == 'target': args['team_ids'] = ['other-team']
                if change == 'credential': client.api_key = 'other-key'
                if change == 'day': args['date_value'] = '2026-10-19'
                with self.assertRaises(module.SportsProviderRateLimitError): client.fetch_games_resumable(**args)
                self.assertEqual(len(module._REFRESH_PROGRESS), 2)
                self.assertEqual(len(self.calls), 22)

    def test_unknown_failure_discards_checkpoint(self):
        with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
        self.clock += 120
        self.failure = urllib.error.HTTPError('https://offline.invalid', 401, 'refused', {}, None)
        with self.assertRaisesRegex(RuntimeError, 'HTTP 401'): self.attempt()
        self.assertFalse(module._REFRESH_PROGRESS)

    def test_expiry_during_request_refuses_publication(self):
        self.limit_every = 0
        original = self.upstream
        def slow(*args, **kwargs):
            response = original(*args, **kwargs)
            self.clock += 901
            return response
        with patch.object(module.urllib.request, 'urlopen', side_effect=slow):
            with self.assertRaisesRegex(RuntimeError, 'checkpoint expired'): self.attempt()
        self.assertFalse(module._REFRESH_PROGRESS)

    def test_memory_and_request_bounds_refuse_partial_result(self):
        for bound, value, message in (
            ('_REFRESH_MAX_REQUESTS', 2, 'request bound'), ('_REFRESH_MAX_BYTES', 1, 'memory bound'),
        ):
            with self.subTest(bound=bound):
                module._reset_request_budget_for_tests()
                with patch.object(module, bound, value):
                    with self.assertRaisesRegex(RuntimeError, message): self.attempt()
                self.assertFalse(module._REFRESH_PROGRESS)

    def test_plan_count_is_bounded(self):
        with patch.object(module.TheSportsDBProvider, 'request_json', side_effect=module.SportsProviderRateLimitError(60)):
            for i in range(12):
                with self.assertRaises(module.SportsProviderRateLimitError):
                    self.attempt(args={**self.args, 'team_ids': [str(i)]})
        self.assertEqual(len(module._REFRESH_PROGRESS), 8)

    def test_original_instance_request_method_unchanged(self):
        client = module.TheSportsDBProvider()
        original = client.request_json
        with self.assertRaises(module.SportsProviderRateLimitError): client.fetch_games_resumable(**self.args)
        self.assertEqual(client.request_json, original)
        self.assertNotIn('request_json', client.__dict__)

    def test_no_checkpoint_file_is_published(self):
        with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
        self.assertEqual({p.name for p in Path(self.temp.name).iterdir()}, {'budget.json', 'budget.json.lock'})

    def worker_context(self, worker, providers, targets=None):
        stack = ExitStack()
        stack.enter_context(patch.object(worker, 'enabled_providers', side_effect=providers))
        stack.enter_context(patch.object(worker, 'load_state', return_value={}))
        stack.enter_context(patch.object(worker, 'load_provider_health', return_value={}))
        stack.enter_context(patch.object(worker, 'active_subscriptions', return_value=[]))
        stack.enter_context(patch.object(worker, 'tracked_event_ids', return_value=self.args['tracked_event_ids']))
        stack.enter_context(patch.object(worker, 'provider_discovery_targets', return_value=targets or {
            'events': self.args['event_ids'], 'teams': self.args['team_ids'], 'leagues': self.args['league_ids']}))
        stack.enter_context(patch.object(worker, 'resolve_subscribed_games', side_effect=lambda games, _: games))
        stack.enter_context(patch('builtins.print'))
        return stack

    def test_worker_new_instances_stay_degraded_until_complete(self):
        if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
        import worker
        with self.worker_context(worker, lambda: [module.TheSportsDBProvider()]):
            for elapsed in (0, 120, 240, 360):
                self.clock = 1000000 + elapsed
                result = worker.run_provider_pipeline()
                self.assertEqual(result['provider_health']['thesportsdb']['status'],
                                 'healthy' if elapsed == 360 else 'degraded')
                self.assertEqual(result['degraded_count'], int(elapsed != 360))
                if elapsed != 360:
                    self.assertEqual(result['provider_games'], [])
                    self.assertNotIn('refresh_snapshot', result['provider_health']['thesportsdb'])
                else:
                    self.assertEqual(result['provider_health']['thesportsdb']['refresh_snapshot']['oldest_response_age_seconds'], 360)


    def test_actual_event_payloads_publish_only_when_full_snapshot_finishes(self):
        import urllib.parse
        original = self.upstream
        def populated(request, **kwargs):
            response = original(request, **kwargs)
            if 'lookupevent.php?' in request.full_url:
                identity = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)['id'][0]
                import json
                return io.BytesIO(json.dumps({'events': [{
                    'idEvent': identity, 'strEvent': 'Fixture event',
                    'dateEvent': '2026-10-18', 'strTime': '12:00:00',
                }]}).encode())
            return response
        with patch.object(module.urllib.request, 'urlopen', side_effect=populated):
            for elapsed in (0, 120, 240):
                self.clock = 1000000 + elapsed
                with self.assertRaises(module.SportsProviderRateLimitError): self.attempt()
            self.clock = 1000360
            client = module.TheSportsDBProvider()
            games = client.fetch_games_resumable(**self.args)
            self.assertEqual({game['id'] for game in games}, {'thesportsdb-' + str(i) for i in range(21)})
            self.assertEqual(client.last_refresh_snapshot, {
                'version': 1, 'oldest_response_age_seconds': 360.0,
                'maximum_age_seconds': 900, 'completed_request_count': 38})

    def test_concurrent_same_plan_does_not_duplicate_completed_work(self):
        from concurrent.futures import ThreadPoolExecutor
        self.limit_every = 0
        def attempt():
            try: return self.attempt()
            except module.SportsProviderRateLimitError: return 'deferred'
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(lambda _: attempt(), range(4))), ['deferred'] * 4)
        self.assertEqual(len(self.calls), 20)
        self.clock += 60
        self.assertEqual(self.attempt(), [])
        self.assertEqual(len(self.calls), 38)
        self.assertEqual(len({url for _, url in self.calls}), 38)

    def test_worker_falls_back_for_other_providers(self):
        if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
        import worker
        class Other:
            name = 'other'
            def fetch_games(self, **kwargs): return []
        with self.worker_context(worker, lambda: [Other()]):
            result = worker.run_provider_pipeline()
            self.assertEqual(result['provider_health']['other']['status'], 'healthy')


if __name__ == '__main__': unittest.main()
