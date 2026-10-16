"""Interactive schedule discovery must not change background provider budgets."""

import unittest
from unittest.mock import patch
from types import SimpleNamespace



class SportsUpcomingScheduleTests(unittest.TestCase):
    def setUp(self):
        from providers.thesportsdb import TheSportsDBProvider

        self.provider = TheSportsDBProvider()
        self.provider.discovery_days_ahead = 1

    def test_interactive_window_covers_every_day_and_retains_full_sunday_slate(self):
        calls = []

        def fetch_day(date_value, league_id):
            calls.append((date_value, league_id))
            if date_value != "2026-10-18":
                return []
            return [
                {"idEvent": str(index), "strTimestamp": "2026-10-18T17:00:00Z"}
                for index in range(14)
            ]

        with patch.object(self.provider, "fetch_day_events", side_effect=fetch_day):
            events = self.provider.fetch_games(
                league_ids=["4391"], date_value="2026-10-15", days_ahead=7,
            )
        self.assertEqual(len(events), 14)
        self.assertEqual(len(calls), 8)
        self.assertEqual(calls[0], ("2026-10-15", "4391"))
        self.assertEqual(calls[-1], ("2026-10-22", "4391"))
        self.assertEqual(self.provider.discovery_days_ahead, 1)

    def test_background_discovery_retains_configured_horizon(self):
        with patch.object(self.provider, "fetch_day_events", return_value=[]) as fetch:
            self.provider.fetch_games(league_ids=["4391"], date_value="2026-10-15")
        self.assertEqual(fetch.call_count, 2)

    def test_invalid_horizon_is_rejected_before_any_provider_request(self):
        for value in (-1, 8, True, "7", 7.0):
            with self.subTest(value=value):
                with patch.object(self.provider, "request_json") as request:
                    with self.assertRaises(ValueError):
                        self.provider.fetch_games(league_ids=["4391"], days_ahead=value)
                    request.assert_not_called()

    def test_private_route_requests_a_week_only_for_scoped_schedule_queries(self):
        from private_api import Handler

        for query, expected in (("&league_id=4391", 7), ("&team_id=team", 7),
                                ("&event_id=game", None), ("", None)):
            with self.subTest(query=query):
                calls = []
                provider = SimpleNamespace(
                    name="thesportsdb",
                    fetch_games=lambda **kwargs: calls.append(kwargs) or [],
                )
                handler = object.__new__(Handler)
                handler.path = "/internal/v1/events?user_id=owner&provider=thesportsdb" + query
                handler._require_auth = lambda: True
                handler._user_subscriptions = lambda user_id: []
                responses = []
                handler._json = lambda status, payload: responses.append((status, payload))
                with patch("private_api._provider", return_value=provider):
                    handler.do_GET()
                self.assertEqual(int(responses[0][0]), 200)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].get("days_ahead"), expected)


if __name__ == "__main__":
    unittest.main()
