"""Offline behavior and fresh-process tests; never contact a provider."""
from __future__ import annotations

import io
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'modules/sports/src'
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
from providers import thesportsdb as provider


class ProviderRequestBudgetTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.budget = Path(self.directory.name) / 'budget.json'
        self.scope = patch.object(provider, '_PROVIDER_BUDGET_FILE', self.budget)
        self.scope.start()
        self.addCleanup(self.scope.stop)
        provider._reset_request_budget_for_tests()
        self.addCleanup(provider._reset_request_budget_for_tests)
        self.client = provider.TheSportsDBProvider()

    def document(self):
        return json.loads(self.budget.read_bytes())

    def write(self, deadline=0, epochs=None):
        self.budget.write_text(json.dumps({
            'provider': 'thesportsdb', 'retry_until_epoch': deadline,
            'request_epochs': [] if epochs is None else epochs,
        }))

    def fake_response(self, *args, **kwargs):
        return io.BytesIO(b'{"events":[],"results":[]}')

    def child(self, source):
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
               'PYTHONPATH': str(SOURCE),
               'SPORTS_PROVIDER_REQUEST_BUDGET_FILE': str(self.budget)}
        return subprocess.Popen([sys.executable, '-B', '-c', source], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_rolling_window_and_exact_expiry(self):
        with patch.object(provider.time, 'time', return_value=1000):
            for _ in range(20):
                provider._reserve_shared_request()
            with self.assertRaises(provider.SportsProviderRateLimitError) as caught:
                provider._reserve_shared_request()
            self.assertEqual(caught.exception.retry_after_seconds, 60)
        with patch.object(provider.time, 'time', return_value=1059.9):
            with self.assertRaises(provider.SportsProviderRateLimitError) as caught:
                provider._reserve_shared_request()
            self.assertEqual(caught.exception.retry_after_seconds, 1)
        with patch.object(provider.time, 'time', return_value=1060):
            provider._reserve_shared_request()
        self.assertEqual(self.document()['request_epochs'], [1060])

    def test_fourteen_day_discovery_completes_across_budget_windows(self):
        self.client.discovery_days_ahead = 14
        events = [str(index) for index in range(21)]
        with patch.object(provider.urllib.request, 'urlopen',
                          side_effect=self.fake_response) as upstream:
            with patch.object(provider.time, 'time', return_value=1000):
                with self.assertRaises(provider.SportsProviderRateLimitError):
                    self.client.fetch_games(league_ids=['fixture-league'],
                                            tracked_event_ids=events)
            self.assertEqual(upstream.call_count, 20)
            with patch.object(provider.time, 'time', return_value=1060):
                self.assertEqual(self.client.fetch_games(
                    league_ids=['fixture-league'], tracked_event_ids=events), [])
            self.assertEqual(upstream.call_count, 36)
        self.assertEqual(self.client.discovery_days_ahead, 14)

    def test_cached_response_needs_no_new_admission_even_during_cooldown(self):
        with patch.object(provider.urllib.request, 'urlopen',
                          side_effect=self.fake_response) as upstream:
            self.client.request_json('eventsday.php', {'d': 'fixture'})
            provider._write_shared_rate_limit_until(provider.time.time() + 3600)
            snapshot = self.budget.read_bytes()
            result = self.client.request_json('eventsday.php', {'d': 'fixture'})
            self.assertEqual(result, {'events': [], 'results': []})
            self.assertEqual(upstream.call_count, 1)
            self.assertEqual(self.budget.read_bytes(), snapshot)

    def test_legacy_cooldown_is_not_reset_by_upgrade(self):
        self.budget.write_text(json.dumps({
            'provider': 'thesportsdb', 'retry_until_epoch': 2000,
        }))
        snapshot = self.budget.read_bytes()
        with patch.object(provider.time, 'time', return_value=1000):
            with self.assertRaises(provider.SportsProviderRateLimitError):
                provider._reserve_shared_request()
        self.assertEqual(self.budget.read_bytes(), snapshot)
        with patch.object(provider.time, 'time', return_value=2000):
            provider._reserve_shared_request()
        self.assertEqual(self.document()['request_epochs'], [2000])

    def test_429_preserves_full_deadline_and_charges_failed_request(self):
        failure = urllib.error.HTTPError(
            'https://fixture.invalid/', 429, 'limited', {'Retry-After': '3600'}, None)
        with patch.object(provider.time, 'time', return_value=1000):
            with patch.object(provider.urllib.request, 'urlopen', side_effect=failure) as upstream:
                with self.assertRaises(provider.SportsProviderRateLimitError) as caught:
                    self.client.request_json('eventsday.php', {'d': 'fixture'})
                self.assertEqual(caught.exception.retry_after_seconds, 3600)
                self.assertEqual(upstream.call_count, 1)
            self.assertEqual(self.document()['retry_until_epoch'], 4600)
            self.assertEqual(self.document()['request_epochs'], [1000])
            self.assertEqual(provider._shared_retry_after_seconds(), 300)
        provider._reset_request_budget_for_tests()
        with patch.object(provider.time, 'time', return_value=1301):
            with patch.object(provider.urllib.request, 'urlopen') as upstream:
                with self.assertRaises(provider.SportsProviderRateLimitError):
                    self.client.request_json('eventsday.php', {'d': 'fixture'})
                upstream.assert_not_called()

    def test_retry_after_date_and_fractional_remaining_time(self):
        failure = urllib.error.HTTPError('https://fixture.invalid/', 429, 'limited',
            {'Retry-After': 'Thu, 01 Jan 2099 00:00:00 GMT'}, None)
        self.assertGreater(provider._retry_after_seconds(failure), 300)
        failure.headers = {'Retry-After': 'Thu, 01 Jan 2026 00:00:02 GMT'}
        with patch.object(provider, 'datetime') as clock:
            clock.now.return_value = datetime(2026, 1, 1, 0, 0, 0, 100000,
                                              tzinfo=timezone.utc)
            self.assertEqual(provider._retry_after_seconds(failure), 2)
        self.write(deadline=1000.2)
        self.assertEqual(provider._shared_retry_after_seconds(1000), 1)

    def test_network_failure_is_not_refunded(self):
        with patch.object(provider.urllib.request, 'urlopen',
                          side_effect=urllib.error.URLError('fixture')):
            with self.assertRaises(RuntimeError):
                self.client.request_json('eventsday.php', {'d': 'fixture'})
        self.assertEqual(len(self.document()['request_epochs']), 1)

    def test_cooldown_extension_preserves_admissions_and_never_shortens_deadline(self):
        self.write(deadline=2000, epochs=[1000, 1001])
        provider._write_shared_rate_limit_until(1500)
        self.assertEqual(self.document()['retry_until_epoch'], 2000)
        self.assertEqual(self.document()['request_epochs'], [1000, 1001])
        provider._write_shared_rate_limit_until(3000)
        self.assertEqual(self.document()['retry_until_epoch'], 3000)

    def test_concurrent_processes_share_twenty_slots(self):
        source = '''from providers.thesportsdb import _reserve_shared_request, SportsProviderRateLimitError
try:
    _reserve_shared_request()
except SportsProviderRateLimitError:
    raise SystemExit(2)
'''
        children = [self.child(source) for _ in range(40)]
        try:
            codes = []
            for child in children:
                out, error = child.communicate(timeout=30)
                self.assertEqual(error, b'')
                self.assertEqual(out, b'')
                codes.append(child.returncode)
            self.assertEqual(codes.count(0), 20)
            self.assertEqual(codes.count(2), 20)
            self.assertEqual(len(self.document()['request_epochs']), 20)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.communicate()

    def test_process_death_after_admission_remains_charged(self):
        child = self.child('from providers.thesportsdb import _reserve_shared_request; '
                           'import os; _reserve_shared_request(); os._exit(23)')
        out, error = child.communicate(timeout=30)
        self.assertEqual((child.returncode, out, error), (23, b'', b''))
        self.assertEqual(len(self.document()['request_epochs']), 1)
        provider._reserve_shared_request()
        self.assertEqual(len(self.document()['request_epochs']), 2)

    def test_invalid_existing_state_refuses_upstream_without_repair(self):
        invalid = [b'{', b'[]', b'{}', b'\xff',
                   b'{"provider":"thesportsdb","retry_until_epoch":1,"retry_until_epoch":0}',
                   b'{"provider":"thesportsdb","retry_until_epoch":true}', b'{"provider":"other","retry_until_epoch":0}',
                   b'{"provider":"thesportsdb","retry_until_epoch":NaN}',
                   b'{"provider":"thesportsdb","retry_until_epoch":-1}',
                   b'{"provider":"thesportsdb","retry_until_epoch":0,"request_epochs":[true]}',
                   b'{"provider":"thesportsdb","retry_until_epoch":0,"request_epochs":[NaN]}']
        for raw in invalid:
            with self.subTest(raw=raw):
                self.budget.write_bytes(raw)
                with patch.object(provider.urllib.request, 'urlopen') as upstream:
                    with self.assertRaises(RuntimeError):
                        self.client.request_json('eventsday.php', {'d': 'fixture'})
                    upstream.assert_not_called()
                self.assertEqual(self.budget.read_bytes(), raw)

    def test_symlink_or_hardlink_state_refuses_upstream(self):
        target = self.budget.with_name('target')
        target.write_text('{}')
        for link in ('symlink', 'hardlink'):
            with self.subTest(link=link):
                if link == 'symlink':
                    self.budget.symlink_to(target)
                else:
                    os.link(target, self.budget)
                try:
                    with patch.object(provider.urllib.request, 'urlopen') as upstream:
                        with self.assertRaises((OSError, RuntimeError)):
                            self.client.request_json('eventsday.php', {'d': 'fixture'})
                        upstream.assert_not_called()
                    self.assertEqual(target.read_text(), '{}')
                finally:
                    self.budget.unlink()

    def test_symlink_lock_is_refused(self):
        target = self.budget.with_name('target')
        target.write_text('fixture')
        self.budget.with_name('budget.json.lock').symlink_to(target)
        with patch.object(provider.urllib.request, 'urlopen') as upstream:
            with self.assertRaises(OSError):
                self.client.request_json('eventsday.php', {'d': 'fixture'})
            upstream.assert_not_called()
        self.assertEqual(target.read_text(), 'fixture')

    def test_file_sync_failure_prevents_http_and_cleans_partial(self):
        self.write()
        old = self.budget.read_bytes()
        with patch.object(provider.os, 'fsync', side_effect=OSError('fixture')):
            with patch.object(provider.urllib.request, 'urlopen') as upstream:
                with self.assertRaises(OSError):
                    self.client.request_json('eventsday.php', {'d': 'fixture'})
                upstream.assert_not_called()
        self.assertEqual(self.budget.read_bytes(), old)
        self.assertEqual(list(self.budget.parent.glob('budget.json.tmp.*')), [])

    def test_directory_sync_failure_prevents_http_but_keeps_charge(self):
        calls = []
        original = os.fsync
        def sync(descriptor):
            calls.append(descriptor)
            if len(calls) == 2:
                raise OSError('fixture')
            return original(descriptor)
        with patch.object(provider.os, 'fsync', side_effect=sync):
            with patch.object(provider.urllib.request, 'urlopen') as upstream:
                with self.assertRaises(OSError):
                    self.client.request_json('eventsday.php', {'d': 'fixture'})
                upstream.assert_not_called()
        self.assertEqual(len(self.document()['request_epochs']), 1)

    def test_cooldown_race_is_rechecked_under_admission_lock(self):
        self.write(deadline=provider.time.time() + 120)
        with patch.object(provider, '_shared_retry_after_seconds', return_value=0):
            with patch.object(provider.urllib.request, 'urlopen') as upstream:
                with self.assertRaises(provider.SportsProviderRateLimitError):
                    self.client.request_json('eventsday.php', {'d': 'fixture'})
                upstream.assert_not_called()
        self.assertEqual(self.document()['request_epochs'], [])

    def test_excessive_or_oversized_state_refuses_admission(self):
        for epochs in ([1000] * 21, ['invalid']):
            with self.subTest(epochs=len(epochs)):
                self.write(epochs=epochs)
                with self.assertRaises(RuntimeError):
                    provider._reserve_shared_request()
        self.budget.write_bytes(b' ' * 16385)
        with self.assertRaises(RuntimeError):
            provider._reserve_shared_request()

    def test_clock_reversal_does_not_drop_future_reservations(self):
        self.write(epochs=[1000] * 20)
        with patch.object(provider.time, 'time', return_value=900):
            with self.assertRaises(provider.SportsProviderRateLimitError):
                provider._reserve_shared_request()
        self.assertEqual(self.document()['request_epochs'], [1000] * 20)


if __name__ == '__main__':
    unittest.main()
