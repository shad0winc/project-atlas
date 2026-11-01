from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'modules/sports/src'))
from providers.espn_metadata import LEAGUE_UIDS, parse_scoreboard
from providers.metadata_broker import MetadataBroker, MetadataUnavailable
from providers.metadata_store import MetadataStore
from providers.curated_schedule import SnapshotReader
from providers.metadata_refresh import parse_refresh_policy, next_refresh_job
from providers.metadata_freshness import scoreboard_expiry

ROUTE = 'basketball/nba'
DAY = date(2026, 10, 31)
NOW = datetime(2026, 11, 1, 0, 12, tzinfo=timezone.utc).timestamp()


def payload(status='STATUS_SCHEDULED', stamp='2026-11-01T00:00:00Z'):
    state = {'type': {'name': status, 'state': 'in' if status == 'STATUS_IN_PROGRESS' else 'post' if status == 'STATUS_FINAL' else 'pre',
                      'completed': status == 'STATUS_FINAL'}}
    return {'leagues': [{'uid': LEAGUE_UIDS[ROUTE]}], 'events': [{
        'id': '401909900', 'name': 'Synthetic Cavaliers at Bucks', 'status': state,
        'competitions': [{'id': '401909900', 'date': stamp, 'timeValid': True, 'status': state,
            'competitors': [{'id': str(i), 'homeAway': side, 'team': {'id': str(i), 'displayName': side}}
                            for i, side in ((5, 'away'), (15, 'home'))]}]}]}


class ActiveScoreboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = MetadataStore(self.root / 'metadata.sqlite')
        self.now = NOW
        self.calls = []
        self.failure = None

        def transport(route, day):
            self.calls.append((route, day))
            if self.failure:
                raise self.failure
            return payload('STATUS_IN_PROGRESS')
        self.broker = MetadataBroker(self.store, clock=lambda: self.now, transport=transport,
            current_ttl=300, past_ttl=3600, future_ttl=3600, hourly_budget=180)

    def seed(self, *, document=None, observed=None, day=DAY):
        with self.store.connection() as db:
            stamp = NOW - 660 if observed is None else observed
            db.execute('INSERT OR REPLACE INTO metadata_cache VALUES (?,?,?,?,?)',
                (ROUTE, day.isoformat(), json.dumps(payload() if document is None else document), stamp, stamp + 3600))

    def test_started_game_does_not_get_hour_long_freshness_after_utc_midnight(self):
        self.seed()
        _, rows = self.broker.read_days(ROUTE, (DAY,))
        self.assertEqual(rows[0].status, 'stale')
        self.assertEqual(rows[0].snapshot.expires_at, NOW - 360)
        self.assertEqual(rows[0].snapshot.events[0].status, 'scheduled')
        self.assertEqual(self.calls, [])

    def test_read_only_curated_reader_agrees_without_rewriting_cache(self):
        self.seed()
        before = self.store.path.read_bytes()
        reader = SnapshotReader(self.root, clock=lambda: NOW, current_ttl=300)
        with reader.snapshot() as (db, now):
            row = reader.bucket(db, ROUTE, DAY.isoformat(), now)
        self.assertEqual(row.status, 'stale')
        self.assertEqual(row.snapshot.expires_at, NOW - 360)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_background_fetch_replaces_effectively_expired_old_hour_ttl(self):
        self.seed()
        result = self.broker.fetch_day(ROUTE, DAY)
        self.assertFalse(result.cache_hit)
        self.assertEqual(result.events[0].status, 'live')
        self.assertEqual(result.expires_at, NOW + 300)
        self.assertEqual(len(self.calls), 1)

    def test_repeat_fetch_is_cached_without_renewing_observation(self):
        first = self.broker.fetch_day(ROUTE, DAY)
        self.now += 10
        second = self.broker.fetch_day(ROUTE, DAY)
        self.assertTrue(second.cache_hit)
        self.assertEqual(first.observed_at, second.observed_at)
        self.assertEqual(len(self.calls), 1)

    def test_global_cooldown_still_prevents_fetch(self):
        self.seed()
        with self.store.connection() as db:
            db.execute('INSERT INTO metadata_holds VALUES (?,?)', ('espn:cooldown', NOW + 120))
        with self.assertRaises(MetadataUnavailable) as caught:
            self.broker.fetch_day(ROUTE, DAY)
        self.assertEqual(caught.exception.retry_after, 120)
        self.assertEqual(self.calls, [])

    def test_shared_hourly_budget_is_not_bypassed(self):
        self.seed()
        self.broker.hourly_budget = 1
        with self.store.connection() as db:
            db.execute('INSERT INTO metadata_attempts VALUES (?)', (NOW - 1,))
        with self.assertRaises(MetadataUnavailable) as caught:
            self.broker.fetch_day(ROUTE, DAY)
        self.assertEqual(caught.exception.category, 'request-budget')
        self.assertEqual(self.calls, [])

    def test_failed_refresh_preserves_old_rows_and_ages(self):
        self.seed()
        self.failure = MetadataUnavailable('network')
        with self.assertRaises(MetadataUnavailable):
            self.broker.fetch_day(ROUTE, DAY)
        _, rows = self.broker.read_days(ROUTE, (DAY,))
        self.assertEqual(rows[0].snapshot.observed_at, NOW - 660)
        self.assertEqual(rows[0].status, 'stale')

    def test_future_bucket_promoted_to_current_does_not_keep_old_future_ttl(self):
        document = {'leagues': [{'uid': LEAGUE_UIDS[ROUTE]}], 'events': []}
        self.seed(document=document, day=date(2026, 11, 1))
        _, rows = self.broker.read_days(ROUTE, (date(2026, 11, 1),))
        self.assertEqual(rows[0].status, 'stale')

    def test_final_and_distant_future_rows_keep_declared_lifetimes(self):
        for document in (payload('STATUS_FINAL'), payload(stamp='2026-11-04T00:00:00Z')):
            events = parse_scoreboard(ROUTE, document)
            self.assertEqual(scoreboard_expiry(DAY.isoformat(), events, NOW - 660, NOW + 2940, NOW, 300), NOW + 2940)

    def test_live_previous_day_job_precedes_cold_future_warmup(self):
        self.seed(document=payload('STATUS_IN_PROGRESS'))
        self.seed(document={'leagues': [{'uid': LEAGUE_UIDS[ROUTE]}], 'events': []},
                  observed=NOW, day=date(2026, 11, 1))
        policy = parse_refresh_policy({'version': 1, 'enabled': True, 'routes': [ROUTE],
            'hourly_budget': 180, 'current_ttl': 300, 'past_ttl': 3600, 'future_ttl': 3600,
            'directory_ttl': 3600, 'tick_seconds': 15, 'generation': 'active-fixture'})
        job = next_refresh_job(self.broker, policy, NOW)
        self.assertEqual(job.day, DAY)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
