"""Real provider/cache regressions with a fake clock and no external HTTP."""
from pathlib import Path
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from providers import thesportsdb as provider_module


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value


class ColdScheduleTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'SPORTS_SHARED_METADATA_CACHE_ENABLED': '1', 'SPORTS_THESPORTSDB_API_KEY': 'fixture'})
        self.env.start()
        self.budget = patch.object(provider_module, '_PROVIDER_BUDGET_FILE', Path(self.folder.name) / 'budget.json')
        self.budget.start()
        provider_module._reset_request_budget_for_tests()
        self.clock = Clock()
        self.time = patch.object(provider_module.time, 'time', side_effect=self.clock)
        self.time.start()

    def tearDown(self):
        self.time.stop()
        self.budget.stop()
        self.env.stop()
        self.folder.cleanup()

    def schedule(self, leagues, attempts, wait_limit, deadline):
        waited = 0
        for attempt in range(attempts):
            try:
                return provider_module.TheSportsDBProvider().fetch_games(
                    league_ids=leagues, date_value='2026-10-31', days_ahead=7)
            except provider_module.SportsProviderRateLimitError as error:
                seconds = error.retry_after_seconds
                if attempt == attempts - 1 or waited + seconds > wait_limit or self.clock.value - 1000 + seconds >= deadline:
                    raise
                waited += seconds
                self.clock.value += seconds

    def test_original_three_attempt_window_fails_two_cold_leagues_without_upstream_429(self):
        with patch.object(provider_module.urllib.request, 'urlopen', side_effect=lambda *_a, **_k: io.StringIO('{"events":[]}')) as fetch:
            with self.assertRaises(provider_module.SportsProviderRateLimitError):
                self.schedule(['4391', '4387'], 3, 20, 30)
        self.assertEqual(fetch.call_count, 12)

    def test_two_cold_leagues_complete_without_duplicate_fetches_or_quota_increase(self):
        with patch.object(provider_module.urllib.request, 'urlopen', side_effect=lambda *_a, **_k: io.StringIO('{"events":[]}')) as fetch:
            self.assertEqual(self.schedule(['4391', '4387'], 12, 90, 120), [])
        self.assertEqual(fetch.call_count, 16)
        self.assertEqual(self.clock.value, 1030)

    def test_three_cold_leagues_respect_twenty_per_minute(self):
        stamps = []
        def response(*_a, **_k):
            stamps.append(self.clock.value)
            self.assertLess(sum(0 <= self.clock.value - t < 60 for t in stamps[:-1]), 20)
            self.assertLess(sum(0 <= self.clock.value - t < 10 for t in stamps[:-1]), 4)
            return io.StringIO('{"events":[]}')
        with patch.object(provider_module.urllib.request, 'urlopen', side_effect=response):
            self.assertEqual(self.schedule(['4391', '4387', '4424'], 12, 90, 120), [])
        self.assertEqual(len(stamps), 24)
        self.assertEqual(self.clock.value, 1060)

    def test_aliases_reuse_one_validated_league_lookup(self):
        payload = {'leagues': [{'idLeague': '4479', 'strLeague': 'NCAA Division 1 Football', 'strSport': 'American Football'}]}
        with patch.object(provider_module.urllib.request, 'urlopen', side_effect=lambda *_a, **_k: io.StringIO(json.dumps(payload))) as fetch:
            for query in ('NCAA', 'NCAAF', 'college football', 'NCAA football', 'NCAA Division 1 Football'):
                rows = provider_module.TheSportsDBProvider().search_leagues(query)
                self.assertEqual(rows[0]['id'], '4479')
                self.assertEqual(rows[0]['sport'], 'American Football')
        self.assertEqual(fetch.call_count, 1)
        self.assertIn('lookupleague.php?id=4479', fetch.call_args.args[0].full_url)

    def test_alias_lookup_never_accepts_another_sport_or_identity(self):
        for league in ({'idLeague': '4479', 'strSport': 'Basketball', 'strLeague': 'Wrong'},
                       {'idLeague': '4391', 'strSport': 'American Football', 'strLeague': 'Wrong'}):
            with self.subTest(league=league), patch.object(provider_module.TheSportsDBProvider, 'request_json', return_value={'leagues': [league]}):
                with self.assertRaises(RuntimeError):
                    provider_module.TheSportsDBProvider().search_leagues('NCAA')

    def test_unconfigured_or_empty_league_is_not_fabricated(self):
        with patch.object(provider_module.TheSportsDBProvider, 'request_json', return_value={'leagues': None}):
            self.assertEqual(provider_module.TheSportsDBProvider().search_leagues('college football'), [])

    def test_other_league_queries_preserve_existing_transport(self):
        with patch.object(provider_module.TheSportsDBProvider, 'request_json', return_value={'teams': []}) as request:
            self.assertEqual(provider_module.TheSportsDBProvider().search_leagues('MLB'), [])
        request.assert_called_once_with('search_all_teams.php', {'l': 'MLB'})


if __name__ == '__main__':
    unittest.main()
