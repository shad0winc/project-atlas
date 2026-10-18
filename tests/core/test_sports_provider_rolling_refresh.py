"""Offline renewal regressions: complete coverage, true ages and shared limits."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'modules/sports/src'))
from providers import thesportsdb as module
from atlas.sports_provider_snapshot_health import provider_snapshot_usable
spec = importlib.util.spec_from_file_location(
    '_rolling_fixtures', Path(__file__).with_name('test_sports_provider_refresh_progress.py'))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class RollingRefreshTests(unittest.TestCase):
    setUp = fixtures.RefreshProgressTests.setUp
    upstream = fixtures.RefreshProgressTests.upstream
    attempt = fixtures.RefreshProgressTests.attempt

    def complete(self):
        for elapsed in (0, 120, 240, 360):
            self.clock = 1000000 + elapsed
            client = module.TheSportsDBProvider()
            try:
                games = client.fetch_games_resumable(**self.args)
            except module.SportsProviderRateLimitError:
                continue
            return client, games
        self.fail('Cold snapshot did not complete')

    def test_slow_provider_stays_bounded_through_many_full_renewals(self):
        """38 calls, 2 seconds per HTTP, 180-second upstream cooldowns."""
        def upstream(request, **kwargs):
            self.calls.append((self.clock, request.full_url))
            self.clock += 2
            if len(self.calls) % 11 == 0:
                raise urllib.error.HTTPError(
                    'https://offline.invalid', 429, 'limited', {'Retry-After': '180'}, None)
            return io.BytesIO(b'{"events":[],"results":[]}')
        completions = set()
        covered = 0
        with patch.object(module.urllib.request, 'urlopen', side_effect=upstream):
            for _ in range(120):
                client = module.TheSportsDBProvider()
                try:
                    client.fetch_games_resumable(**self.args)
                except module.SportsProviderRateLimitError:
                    self.assertFalse(completions, 'Coverage was lost after first completion')
                else:
                    row = {'status': 'healthy', 'last_success_at': client.last_refresh_completed_at,
                           'refresh_snapshot': client.last_refresh_snapshot, 'refresh_state': 'deferred'}
                    self.assertTrue(provider_snapshot_usable(
                        row, datetime.fromtimestamp(self.clock, timezone.utc)))
                    self.assertEqual(row['refresh_snapshot']['completed_request_count'], 38)
                    complete = next(iter(module._REFRESH_COMPLETE.values()))
                    self.assertEqual(len(complete['responses']), 38)
                    self.assertEqual(set(complete['responses']), set(complete['observations']))
                    self.assertLessEqual(self.clock - min(complete['observations'].values()), 900)
                    completions.add(client.last_refresh_completed_at)
                    covered += 1
                self.clock += 30
        self.assertGreaterEqual(len(completions), 4)
        self.assertGreaterEqual(covered, 70)
        for index, (stamp, _) in enumerate(self.calls):
            self.assertLessEqual(sum(0 <= stamp - prior < 60
                for prior, _ in self.calls[:index+1]), 20)
            if (index + 1) % 11 == 0 and index + 1 < len(self.calls):
                self.assertGreaterEqual(self.calls[index+1][0] - stamp, 182)

    def test_renewal_chooses_oldest_before_fixed_endpoint_order(self):
        self.complete()
        complete = next(iter(module._REFRESH_COMPLETE.values()))
        key = min(complete['observations'], key=lambda key: (complete['observations'][key], key))
        expected_endpoint, expected_parameters = key
        self.clock += 120
        client = module.TheSportsDBProvider()
        calls = []
        def defer(endpoint, parameters):
            calls.append((endpoint, tuple(sorted(parameters.items()))))
            raise module.SportsProviderRateLimitError(120)
        client.request_json = defer
        client.fetch_games_resumable(**self.args)
        self.assertEqual(calls, [(expected_endpoint, expected_parameters)])

    def test_some_renewed_responses_do_not_renew_completion_timestamp(self):
        first, _ = self.complete()
        old = copy.deepcopy(next(iter(module._REFRESH_COMPLETE.values())))
        self.clock += 120
        client = module.TheSportsDBProvider()
        client.fetch_games_resumable(**self.args)
        new = next(iter(module._REFRESH_COMPLETE.values()))
        self.assertEqual(client.last_refresh_completed_at, first.last_refresh_completed_at)
        self.assertTrue(any(new['observations'][key] > value
                            for key, value in old['observations'].items()))
        self.assertTrue(any(new['observations'][key] == value
                            for key, value in old['observations'].items()))
        self.assertEqual(new['oldest'], min(new['observations'].values()))
        self.assertEqual(new['metadata']['oldest_response_age_seconds'],
                         round(new['completed_monotonic'] - new['oldest'], 3))

    def test_no_observations_renewed_during_cooldown(self):
        first, _ = self.complete()
        self.clock += 30
        before = copy.deepcopy(module._REFRESH_COMPLETE)
        module._write_shared_rate_limit_until(self.clock + 120)
        client = module.TheSportsDBProvider()
        client.fetch_games_resumable(**self.args)
        self.assertEqual(module._REFRESH_COMPLETE, before)
        self.assertEqual(client.last_refresh_completed_at, first.last_refresh_completed_at)
        self.assertIsNotNone(client.last_refresh_deferred)

    def test_unknown_error_discards_coverage(self):
        self.complete()
        self.clock += 120
        self.failure = RuntimeError('offline unknown failure')
        with self.assertRaises(RuntimeError):
            self.attempt()
        self.assertFalse(module._REFRESH_COMPLETE)

    def test_total_size_charges_provider_responses_too(self):
        self.complete()
        complete = next(iter(module._REFRESH_COMPLETE.values()))
        encoded_games = len(json.dumps(complete['games']).encode())
        self.assertGreater(complete['bytes'], encoded_games)
        self.assertEqual(complete['bytes'], module.TheSportsDBProvider._complete_storage_bytes(
            complete['games'], complete['responses'], complete['observations']))

    def test_renewal_memory_overflow_discards_snapshot(self):
        self.complete()
        self.clock += 120
        client = module.TheSportsDBProvider()
        module._RESPONSE_CACHE.clear()
        client.request_json = lambda endpoint, parameters: {'events': [], 'large': 'x'*5000}
        with patch.object(module, '_REFRESH_COMPLETE_MAX_BYTES', 4000):
            with self.assertRaisesRegex(RuntimeError, 'memory bound'):
                client.fetch_games_resumable(**self.args)
        self.assertFalse(module._REFRESH_COMPLETE)

    def test_reassembly_must_cover_exact_original_plan(self):
        self.complete()
        self.clock += 120
        client = module.TheSportsDBProvider()
        def changed_plan(*args, **kwargs):
            return []
        with patch.object(module.TheSportsDBProvider, 'fetch_games', changed_plan):
            with self.assertRaisesRegex(RuntimeError, 'coverage changed'):
                client.fetch_games_resumable(**self.args)
        self.assertFalse(module._REFRESH_COMPLETE)

    def test_expired_coverage_cannot_survive_permanent_deferral(self):
        self.complete()
        self.clock = 1000901
        self.limit_every = 1
        with self.assertRaises(module.SportsProviderRateLimitError):
            self.attempt()
        self.assertFalse(module._REFRESH_COMPLETE)

    def test_normal_cache_expiry_is_not_extended_by_renewal(self):
        self.complete()
        before = {key: row[0] for key, row in module._RESPONSE_CACHE.items()}
        self.clock += 30
        module._write_shared_rate_limit_until(self.clock + 120)
        calls = len(self.calls)
        self.attempt()
        self.assertEqual(len(self.calls), calls)
        for key, row in module._RESPONSE_CACHE.items():
            self.assertEqual(row[0], before[key])

    def test_populated_reassembly_keeps_all_games_and_isolates_mutation(self):
        import urllib.parse
        upstream = self.upstream
        def populated(request, **kwargs):
            response = upstream(request, **kwargs)
            if 'lookupevent.php?' in request.full_url:
                identity = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)['id'][0]
                return io.BytesIO(json.dumps({'events': [{
                    'idEvent': identity, 'strEvent': 'Observed ' + str(self.clock),
                    'dateEvent': '2026-10-18', 'strTime': '12:00:00',
                }]}).encode())
            return response
        with patch.object(module.urllib.request, 'urlopen', side_effect=populated):
            first, games = self.complete()
            self.assertEqual(len(games), 21)
            original = copy.deepcopy(games)
            seen_updated = False
            for _ in range(12):
                self.clock += 30
                client = module.TheSportsDBProvider()
                returned = client.fetch_games_resumable(**self.args)
                self.assertEqual({item['id'] for item in returned}, {item['id'] for item in original})
                if returned != original:
                    seen_updated = True
                returned.clear()
                self.assertEqual(len(next(iter(module._REFRESH_COMPLETE.values()))['games']), 21)
            self.assertTrue(seen_updated)

    def test_epoch_regression_cannot_renew_coverage(self):
        self.complete()
        self.clock += 120
        with patch.object(module.time, 'time', return_value=999999):
            try:
                self.attempt()
            except (RuntimeError, module.SportsProviderRateLimitError):
                pass
        self.assertFalse(module._REFRESH_COMPLETE)


if __name__ == '__main__':
    unittest.main()
