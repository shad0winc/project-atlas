import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from email.message import Message
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
STAMP = datetime(2026, 10, 16, tzinfo=timezone.utc).timestamp()
DAY = date(2026, 10, 18)


def load_dependencies():
    sys.path.insert(0, str(ROOT / 'modules/sports/src'))
    global MetadataBroker, MetadataUnavailable, ESPNDayTransport, retry_after_seconds
    global MetadataStore, MetadataStoreError, LEAGUE_UIDS
    from providers.metadata_broker import MetadataBroker, MetadataUnavailable, ESPNDayTransport, retry_after_seconds
    from providers.metadata_store import MetadataStore, MetadataStoreError
    from providers.espn_metadata import LEAGUE_UIDS


def empty(route='football/nfl'):
    return {'leagues': [{'uid': LEAGUE_UIDS[route]}], 'events': []}


def process_fetch(path, counter, queue, crash=False):
    load_dependencies()
    def fetch(route, day):
        with counter.get_lock():
            counter.value += 1
        if crash:
            os._exit(17)
        time.sleep(.05)
        return empty(route)
    broker = MetadataBroker(MetadataStore(path), clock=lambda: STAMP, transport=fetch)
    result = broker.fetch_day('football/nfl', DAY)
    queue.put(result.outcome)


class BrokerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dependencies()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'metadata.sqlite'
        self.store = MetadataStore(self.path)
        self.now = STAMP
        self.calls = []
        self.payload = empty()
        def fetch(route, day):
            self.calls.append((route, day))
            if isinstance(self.payload, BaseException):
                raise self.payload
            return copy.deepcopy(self.payload)
        self.fetch = fetch
        self.broker = MetadataBroker(self.store, clock=lambda: self.now,
                                     transport=fetch, future_ttl=10)

    def test_successful_empty_is_cached_with_original_observation_time(self):
        first = self.broker.fetch_day('football/nfl', DAY)
        self.now += 3
        second = self.broker.fetch_day('football/nfl', DAY)
        self.assertEqual(first.outcome, 'empty')
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(second.observed_at, first.observed_at)
        self.assertEqual(len(self.calls), 1)

    def test_malformed_response_is_failure_not_empty_success(self):
        self.payload = {}
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day('football/nfl', DAY)
        self.assertIsNone(self.broker.peek_stale('football/nfl', DAY))

    def test_failed_refresh_preserves_explicit_last_known_snapshot(self):
        first = self.broker.fetch_day('football/nfl', DAY)
        self.now += 11
        self.payload = MetadataUnavailable('network')
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day('football/nfl', DAY)
        stale = self.broker.peek_stale('football/nfl', DAY)
        self.assertTrue(stale.stale)
        self.assertEqual(stale.observed_at, first.observed_at)
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day('football/nfl', DAY)
        self.assertEqual(len(self.calls), 2)

    def test_rate_limit_cooldown_is_shared_across_routes_and_instances(self):
        self.payload = MetadataUnavailable('rate-limit', http_status=429, retry_after=120)
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day('football/nfl', DAY)
        other = MetadataBroker(MetadataStore(self.path), clock=lambda: self.now, transport=self.fetch)
        with self.assertRaises(MetadataUnavailable) as caught:
            other.fetch_day('basketball/nba', DAY)
        self.assertEqual(caught.exception.retry_after, 120)
        self.assertEqual(len(self.calls), 1)

    def test_current_cache_can_be_read_during_provider_cooldown(self):
        self.broker.fetch_day('football/nfl', DAY)
        self.payload = MetadataUnavailable('rate-limit', http_status=429, retry_after=120)
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day('basketball/nba', DAY)
        self.assertTrue(self.broker.fetch_day('football/nfl', DAY).cache_hit)

    def test_cooldown_starts_after_failure_response(self):
        def slow_failure(route, day):
            self.now += 8
            raise MetadataUnavailable('rate-limit', http_status=429, retry_after=120)
        self.broker.transport = slow_failure
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day('football/nfl', DAY)
        with self.assertRaises(MetadataUnavailable) as caught:
            self.broker.fetch_day('basketball/nba', DAY)
        self.assertEqual(caught.exception.retry_after, 120)

    def test_attempt_budget_survives_broker_recreation(self):
        self.broker.hourly_budget = 1
        self.broker.fetch_day('football/nfl', DAY)
        other = MetadataBroker(MetadataStore(self.path), hourly_budget=1,
                               clock=lambda: self.now, transport=self.fetch)
        with self.assertRaises(MetadataUnavailable) as caught:
            other.fetch_day('hockey/nhl', DAY)
        self.assertEqual(caught.exception.category, 'request-budget')
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(other.fetch_day('football/nfl', DAY).cache_hit)

    def test_failed_attempt_consumes_budget(self):
        self.broker.hourly_budget = 1
        self.payload = MetadataUnavailable('network')
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day('football/nfl', DAY)
        with self.assertRaises(MetadataUnavailable) as caught:
            self.broker.fetch_day('hockey/nhl', DAY)
        self.assertEqual(caught.exception.category, 'request-budget')

    def test_budget_recovers_after_rolling_hour(self):
        self.broker.hourly_budget = 1
        self.broker.fetch_day('football/nfl', DAY)
        self.now += 3601
        self.payload = empty('hockey/nhl')
        self.assertFalse(self.broker.fetch_day('hockey/nhl', DAY).cache_hit)

    def test_thread_single_flight(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.broker.fetch_day('football/nfl', DAY), range(4)))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(sum(not row.cache_hit for row in results), 1)

    def test_process_single_flight(self):
        ctx = multiprocessing.get_context('fork')
        counter, queue = ctx.Value('i', 0), ctx.Queue()
        processes = [ctx.Process(target=process_fetch, args=(self.path, counter, queue)) for _ in range(3)]
        for process in processes:
            process.start()
        try:
            for process in processes:
                process.join(5)
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(counter.value, 1)
            self.assertEqual([queue.get(timeout=2) for _ in processes], ['empty'] * 3)
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(2)
            queue.close()

    def test_real_process_crash_leaves_attempt_and_unknown_outcome_hold(self):
        ctx = multiprocessing.get_context('fork')
        counter, queue = ctx.Value('i', 0), ctx.Queue()
        process = ctx.Process(target=process_fetch, args=(self.path, counter, queue, True))
        process.start()
        process.join(5)
        try:
            self.assertEqual(process.exitcode, 17)
            with self.assertRaises(MetadataUnavailable) as caught:
                self.broker.fetch_day('football/nfl', DAY)
            self.assertEqual(caught.exception.category, 'cooldown-or-unknown-outcome')
            self.assertFalse(self.calls)
            with self.store.connection() as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM metadata_attempts').fetchone()[0], 1)
            self.now += 31
            self.assertEqual(self.broker.fetch_day('football/nfl', DAY).outcome, 'empty')
        finally:
            if process.is_alive():
                process.terminate()
                process.join(2)
            queue.close()

    def test_invalid_route_and_horizon_make_no_requests(self):
        for route, day in [('mma/pfl', DAY), ('football/nfl', date(2026, 10, 24)), ('football/nfl', date(2026, 10, 14))]:
            with self.subTest(route=route, day=day), self.assertRaises(ValueError):
                self.broker.fetch_day(route, day)
        self.assertFalse(self.calls)

    def test_clock_regression_does_not_refresh_freshness(self):
        self.broker.fetch_day('football/nfl', DAY)
        self.now -= 1
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day('football/nfl', DAY)
        self.assertEqual(len(self.calls), 1)

    def test_last_known_read_has_age_limit(self):
        self.broker.fetch_day('football/nfl', DAY)
        self.now += 11
        self.assertIsNone(self.broker.peek_stale('football/nfl', DAY, max_age=10))
        self.assertTrue(self.broker.peek_stale('football/nfl', DAY).stale)

    def test_private_directory_and_file_contract(self):
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.path.chmod(0o640)
        with self.assertRaises(MetadataStoreError):
            MetadataStore(self.path)
        self.path.chmod(0o600)
        link = self.path.with_name('link.sqlite')
        link.symlink_to(self.path)
        with self.assertRaises(OSError):
            MetadataStore(link)

    def test_shared_directory_rejected_without_permission_changes(self):
        parent = Path(self.tmp.name) / 'shared'
        parent.mkdir(mode=0o770)
        parent.chmod(0o770)
        with self.assertRaises(MetadataStoreError):
            MetadataStore(parent/'state.sqlite')
        self.assertEqual(parent.stat().st_mode & 0o777, 0o770)

    def test_future_schema_rejected(self):
        with self.store.connection() as connection:
            connection.execute('UPDATE metadata_schema SET version=2')
        with self.assertRaises(MetadataStoreError):
            MetadataStore(self.path)


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dependencies()

    def opener(self, raw=None, error=None, content_type='application/json'):
        headers = Message()
        headers['Content-Type'] = content_type
        response = io.BytesIO(json.dumps(empty()).encode() if raw is None else raw)
        response.status, response.headers = 200, headers
        class Opener:
            calls = []
            def open(self, request, timeout):
                self.calls.append((request.full_url, timeout))
                if error:
                    raise error
                return response
        return Opener()

    def test_transport_uses_single_day_fixed_route_and_bounded_timeout(self):
        opener = self.opener()
        self.assertEqual(ESPNDayTransport(opener=opener)('football/nfl', DAY)['events'], [])
        self.assertEqual(opener.calls, [('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261018', 8)])

    def test_invalid_json_missing_events_and_content_type_are_failures(self):
        for raw, content in [(b'<html>oops</html>', 'application/json'), (b'{}', 'application/json'), (b'{}','text/html'), (b'{"events":[],"events":[]}', 'application/json')]:
            with self.subTest(raw=raw), self.assertRaises(MetadataUnavailable):
                ESPNDayTransport(opener=self.opener(raw, content_type=content))('football/nfl', DAY)

    def test_oversize_response_rejected(self):
        with self.assertRaises(MetadataUnavailable) as caught:
            ESPNDayTransport(opener=self.opener(b' '*4_000_001))('football/nfl', DAY)
        self.assertEqual(caught.exception.category, 'response-budget')

    def test_rate_limit_retains_http_status_and_retry_after(self):
        headers = Message()
        headers['Retry-After'] = '120'
        error = urllib.error.HTTPError('https://private.invalid/?secret=redact', 429, 'hidden', headers, None)
        with self.assertRaises(MetadataUnavailable) as caught:
            ESPNDayTransport(opener=self.opener(error=error))('football/nfl', DAY)
        self.assertEqual(caught.exception.http_status, 429)
        self.assertEqual(caught.exception.retry_after, 120)
        self.assertNotIn('secret', str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_http_redirect_is_failure_without_another_request(self):
        error = urllib.error.HTTPError('https://private.invalid', 302, 'hidden', Message(), None)
        opener = self.opener(error=error)
        with self.assertRaises(MetadataUnavailable) as caught:
            ESPNDayTransport(opener=opener)('football/nfl', DAY)
        self.assertEqual(caught.exception.http_status, 302)
        self.assertEqual(len(opener.calls), 1)

    def test_retry_after_date_and_invalid_values_are_bounded(self):
        self.assertEqual(retry_after_seconds('Fri, 16 Oct 2026 00:02:00 GMT', STAMP), 120)
        for value in (None, 'NaN', 'infinity', 'garbage'):
            with self.subTest(value=value):
                self.assertEqual(retry_after_seconds(value, STAMP), 60)
        self.assertEqual(retry_after_seconds('99999', STAMP), 3600)
        self.assertEqual(retry_after_seconds('-1', STAMP), 1)


class DeadlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dependencies()
        global BoundedESPNTransport
        from providers.metadata_broker import BoundedESPNTransport

    def test_worker_receipt_is_validated_before_returning_payload(self):
        import subprocess
        calls = []
        def run(arguments, **kwargs):
            calls.append((arguments, kwargs))
            return subprocess.CompletedProcess(arguments, 0, json.dumps({'outcome':'success','payload':empty()}).encode(), b'')
        result = BoundedESPNTransport(runner=run)('football/nfl',DAY)
        self.assertEqual(result['events'], [])
        self.assertEqual(calls[0][1]['timeout'], 8)
        self.assertEqual(json.loads(calls[0][1]['input']), {'route':'football/nfl','day':'2026-10-18'})

    def test_real_stalled_fetch_process_is_killed_by_deadline(self):
        import subprocess
        def stalled(arguments, **kwargs):
            return subprocess.run([sys.executable,'-B','-c','import time; time.sleep(60)'],
                capture_output=True, timeout=kwargs['timeout'])
        started = time.monotonic()
        with self.assertRaises(MetadataUnavailable) as caught:
            BoundedESPNTransport(deadline_seconds=.15, runner=stalled)('football/nfl',DAY)
        self.assertEqual(caught.exception.category,'deadline')
        self.assertLess(time.monotonic()-started, 3)

    def test_worker_failure_cannot_be_mistaken_for_empty_schedule(self):
        import subprocess
        for body in (b'{}', b'not-json', b'{"outcome":"success","payload":{}}'):
            with self.subTest(body=body), self.assertRaises(MetadataUnavailable):
                BoundedESPNTransport(runner=lambda *a, **k: subprocess.CompletedProcess(a,0,body,b''))('football/nfl',DAY)

    def test_worker_errors_are_sanitized(self):
        import subprocess
        def failed(*a,**k):
            return subprocess.CompletedProcess(a,1,b'',b'private credentials must not escape')
        with self.assertRaises(MetadataUnavailable) as caught:
            BoundedESPNTransport(runner=failed)('football/nfl',DAY)
        self.assertNotIn('credentials',str(caught.exception))


    def test_real_child_entry_point_serializes_success(self):
        import subprocess
        def fixture_worker(arguments, **kwargs):
            script = ('from providers import metadata_broker as m; '
                      'm.ESPNDayTransport=lambda:lambda route,day:' + repr(empty()) + '; m._fetch_worker()')
            return subprocess.run([*arguments[:-1], script], **kwargs)
        snapshot = BoundedESPNTransport(runner=fixture_worker)('football/nfl', DAY)
        self.assertEqual(snapshot['events'], [])

    def test_real_child_entry_point_preserves_rate_limit_receipt(self):
        import subprocess
        def fixture_worker(arguments, **kwargs):
            script = ("from providers import metadata_broker as m\n"
                      "def fail(route,day):\n"
                      "    raise m.MetadataUnavailable('rate-limit',retry_after=120,http_status=429)\n"
                      "m.ESPNDayTransport=lambda:fail\n"
                      "m._fetch_worker()\n")
            return subprocess.run([*arguments[:-1], script], **kwargs)
        with self.assertRaises(MetadataUnavailable) as caught:
            BoundedESPNTransport(runner=fixture_worker)('football/nfl', DAY)
        self.assertEqual(caught.exception.http_status,429)
        self.assertEqual(caught.exception.retry_after,120)

if __name__ == '__main__':
    unittest.main()
