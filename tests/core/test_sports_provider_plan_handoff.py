"""Offline regressions for tracked-ID handoff with exact bounded coverage."""
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
    '_handoff_fixtures', Path(__file__).with_name('test_sports_provider_refresh_progress.py'))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class PlanHandoffTests(unittest.TestCase):
    setUp = fixtures.RefreshProgressTests.setUp
    upstream = fixtures.RefreshProgressTests.upstream
    attempt = fixtures.RefreshProgressTests.attempt

    def complete(self):
        for elapsed in (0, 120, 240, 360):
            self.clock = 1000000 + elapsed
            client = module.TheSportsDBProvider()
            try:
                result = client.fetch_games_resumable(**self.args)
            except module.SportsProviderRateLimitError:
                continue
            return client, result
        self.fail('No cold completion')

    def contract(self):
        return {**self.args, 'tracked_event_ids': self.args['tracked_event_ids'][1:]}

    def covered(self, client):
        row = {'status': 'healthy', 'refresh_state': 'deferred',
               'last_success_at': client.last_refresh_completed_at,
               'refresh_snapshot': client.last_refresh_snapshot}
        self.assertTrue(provider_snapshot_usable(
            row, datetime.fromtimestamp(self.clock, timezone.utc)))

    def test_contraction_during_cooldown_needs_no_http(self):
        first, _ = self.complete()
        self.clock += 30
        module._write_shared_rate_limit_until(self.clock + 120)
        calls = len(self.calls)
        client = module.TheSportsDBProvider()
        client.fetch_games_resumable(**self.contract())
        self.covered(client)
        self.assertEqual(client.last_refresh_snapshot['completed_request_count'], 37)
        self.assertEqual(client.last_refresh_completed_at, first.last_refresh_completed_at)
        self.assertEqual(len(self.calls), calls)

    def test_handoff_preserves_original_observations(self):
        self.complete()
        original = copy.deepcopy(next(iter(module._REFRESH_COMPLETE.values())))
        self.clock += 30
        module._write_shared_rate_limit_until(self.clock + 120)
        self.attempt(args=self.contract())
        adopted = list(module._REFRESH_COMPLETE.values())[-1]
        self.assertEqual(len(adopted['responses']), 37)
        for key, observed in adopted['observations'].items():
            self.assertEqual(observed, original['observations'][key])
        self.assertEqual(adopted['oldest'], min(adopted['observations'].values()))

    def test_added_request_cannot_be_claimed_covered_during_cooldown(self):
        self.complete()
        self.clock += 30
        module._write_shared_rate_limit_until(self.clock + 120)
        client = module.TheSportsDBProvider()
        args = {**self.args, 'tracked_event_ids': self.args['tracked_event_ids'] + ['new-event']}
        with self.assertRaises(module.SportsProviderRateLimitError):
            client.fetch_games_resumable(**args)
        self.assertIsNone(client.last_refresh_snapshot)
        entry = next(iter(module._REFRESH_PROGRESS.values()))
        self.assertEqual(len(entry['responses']), 38)
        self.assertNotIn(module._cache_key('lookupevent.php', {'id': 'new-event'}), entry['responses'])

    def test_addition_fetches_only_missing_request_before_completion(self):
        self.complete()
        self.clock += 30
        module._write_shared_rate_limit_until(self.clock + 120)
        args = {**self.args, 'tracked_event_ids': self.args['tracked_event_ids'] + ['new-event']}
        with self.assertRaises(module.SportsProviderRateLimitError):
            self.attempt(args=args)
        calls = len(self.calls)
        self.clock += 120
        self.limit_every = 0
        client = module.TheSportsDBProvider()
        client.fetch_games_resumable(**args)
        self.covered(client)
        self.assertEqual(client.last_refresh_snapshot['completed_request_count'], 39)
        self.assertEqual(len(self.calls) - calls, 1)

    def test_scope_change_does_not_seed_tracked_handoff(self):
        for field, value in (
            ('team_ids', ['different-team']), ('event_ids', ['different-event']),
            ('league_ids', ['different-league']), ('date_value', '2026-10-19'),
            ('days_ahead', 7),
        ):
            with self.subTest(field=field):
                module._reset_request_budget_for_tests()
                module._PROVIDER_BUDGET_FILE.unlink(missing_ok=True)
                self.calls.clear()
                self.complete()
                self.clock += 30
                module._write_shared_rate_limit_until(self.clock + 120)
                with self.assertRaises(module.SportsProviderRateLimitError):
                    self.attempt(args={**self.contract(), field: value})
                # No pre-seeded 37-response checkpoint from a different scope.
                self.assertTrue(all(len(item['responses']) < 37
                                    for item in module._REFRESH_PROGRESS.values()))

    def test_credential_change_does_not_seed_handoff(self):
        self.complete()
        self.clock += 30
        module._write_shared_rate_limit_until(self.clock + 120)
        client = module.TheSportsDBProvider()
        client.api_key = 'different-key'
        with self.assertRaises(module.SportsProviderRateLimitError):
            client.fetch_games_resumable(**self.contract())
        self.assertTrue(all(len(item['responses']) < 37
                            for item in module._REFRESH_PROGRESS.values()))

    def test_expired_observations_cannot_seed_handoff(self):
        self.complete()
        self.clock = 1000901
        module._write_shared_rate_limit_until(self.clock + 120)
        with self.assertRaises(module.SportsProviderRateLimitError):
            self.attempt(args=self.contract())
        self.assertFalse(module._REFRESH_COMPLETE)

    def test_clock_regression_cannot_seed_handoff(self):
        self.complete()
        self.clock = 1000359
        try:
            self.attempt(args=self.contract())
        except (RuntimeError, module.SportsProviderRateLimitError):
            pass
        self.assertFalse(module._REFRESH_COMPLETE)

    def test_total_complete_cache_remains_bounded(self):
        self.complete()
        for count in range(1, 12):
            self.clock += 1
            module._write_shared_rate_limit_until(self.clock + 120)
            self.attempt(args={**self.args, 'tracked_event_ids': self.args['tracked_event_ids'][count:]})
            self.assertLessEqual(len(module._REFRESH_COMPLETE), 8)
            self.assertLessEqual(sum(item['bytes'] for item in module._REFRESH_COMPLETE.values()),
                                 module._REFRESH_COMPLETE_MAX_BYTES)

    def test_changed_actual_request_coverage_is_rejected(self):
        self.complete()
        self.clock += 30
        module._write_shared_rate_limit_until(self.clock + 120)
        original = module.TheSportsDBProvider.fetch_games
        calls = 0
        def changed(client, **arguments):
            nonlocal calls
            calls += 1
            if calls == 2:
                return []
            return original(client, **arguments)
        with patch.object(module.TheSportsDBProvider, 'fetch_games', changed):
            with self.assertRaisesRegex(RuntimeError, 'coverage changed'):
                self.attempt(args=self.contract())

    def test_contraction_does_not_publish_removed_lookup_payload(self):
        import urllib.parse
        upstream = self.upstream
        def populated(request, **kwargs):
            result = upstream(request, **kwargs)
            if 'lookupevent.php?' in request.full_url:
                identity = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)['id'][0]
                return io.BytesIO(json.dumps({'events': [{
                    'idEvent': identity, 'strEvent': 'Fixture',
                    'dateEvent': '2026-10-18', 'strTime': '12:00:00',
                }]}).encode())
            return result
        with patch.object(module.urllib.request, 'urlopen', side_effect=populated):
            _, before = self.complete()
            self.assertEqual(len(before), 21)
            self.clock += 30
            module._write_shared_rate_limit_until(self.clock + 120)
            client = module.TheSportsDBProvider()
            games = client.fetch_games_resumable(**self.contract())
            self.assertEqual(len(games), 20)
            self.assertFalse(any(game['provider_event_id'] == '0' for game in games))
            self.covered(client)
            games.clear()
            self.assertEqual(len(list(module._REFRESH_COMPLETE.values())[-1]['games']), 20)

    def test_slow_provider_survives_contraction_and_restore(self):
        def upstream(request, **kwargs):
            self.calls.append((self.clock, request.full_url))
            self.clock += 2
            if len(self.calls) % 11 == 0:
                raise urllib.error.HTTPError(
                    'https://offline.invalid', 429, 'limited', {'Retry-After': '180'}, None)
            return io.BytesIO(b'{"events":[],"results":[]}')
        first = False
        complete_times = set()
        with patch.object(module.urllib.request, 'urlopen', side_effect=upstream):
            for index in range(120):
                args = self.contract() if 50 <= index < 53 or 70 <= index < 73 else self.args
                client = module.TheSportsDBProvider()
                try:
                    client.fetch_games_resumable(**args)
                except module.SportsProviderRateLimitError:
                    self.assertFalse(first, 'Tracked-plan transition lost full covered data')
                else:
                    first = True
                    self.covered(client)
                    expected = 37 if args is not self.args else 38
                    self.assertEqual(client.last_refresh_snapshot['completed_request_count'], expected)
                    complete_times.add(client.last_refresh_completed_at)
                self.clock += 30
        self.assertGreaterEqual(len(complete_times), 4)

    def test_handoff_expiry_during_normalization_is_rejected(self):
        self.complete()
        self.clock += 30
        original = module.TheSportsDBProvider.fetch_games
        calls = 0
        def slow(client, **arguments):
            nonlocal calls
            calls += 1
            games = original(client, **arguments)
            if calls == 2:
                self.clock += 901
            return games
        client = module.TheSportsDBProvider()
        with patch.object(module.TheSportsDBProvider, 'fetch_games', slow):
            with self.assertRaisesRegex(RuntimeError, 'expired or clock invalid'):
                client.fetch_games_resumable(**self.contract())
        self.assertIsNone(client.last_refresh_snapshot)

    def test_handoff_uses_newest_actual_observation_from_compatible_donors(self):
        self.complete()
        self.clock += 120
        self.attempt()
        self.clock += 30
        module._write_shared_rate_limit_until(self.clock + 120)
        self.attempt(args=self.contract())
        before = copy.deepcopy(module._REFRESH_COMPLETE)
        args = {**self.args, 'tracked_event_ids': self.args['tracked_event_ids'][2:]}
        self.clock += 1
        self.attempt(args=args)
        adopted = list(module._REFRESH_COMPLETE.values())[-1]
        for key, observed in adopted['observations'].items():
            self.assertEqual(observed, max(
                donor['observations'][key] for donor in before.values()
                if key in donor['observations']))


if __name__ == '__main__':
    unittest.main()
