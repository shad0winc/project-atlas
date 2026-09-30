from __future__ import annotations

import unittest

from live_source_resolver import (
    DispatcharrStreamCandidate,
    LiveSourceMatchKind,
    TeamRole,
    resolve_live_source_content,
)
from source_lifecycle import SportsSource


def source(account_id: int) -> SportsSource:
    return SportsSource.from_mapping({
        "source_id": f"account-{account_id}",
        "display_name": f"Account {account_id}",
        "provider_id": "fixture", "provider_display_name": "Fixture",
        "account_display_name": str(account_id),
        "kind": "licensed_subscription", "enabled": True,
        "priority": account_id, "max_connections": 3,
        "backend_reference": f"dispatcharr:m3u:{account_id}",
    })


def event(home: str, away: str) -> dict[str, object]:
    return {
        "provider": "thesportsdb", "provider_event_id": "fixture-game",
        "name": f"{home} vs {away}", "sport": "Baseball", "league": "MLB",
        "home_team": home, "away_team": away,
        "start_at": "2026-09-30T00:00:00+00:00",
    }


def stream(identifier: int, name: str, account: int = 2, *, stale=False):
    return DispatcharrStreamCandidate(
        identifier, name, account, group_name="AM | USA MLB", is_stale=stale,
    )


class MLBResolverTests(unittest.TestCase):
    def test_reported_games_resolve_distinct_persistent_team_channels(self):
        candidates = [
            stream(352, "US| MLB: NEW YORK YANKEES"),
            stream(344, "US| MLB: HOUSTON ASTROS"),
            stream(339, "US| MLB: CHICAGO WHITE SOX"),
            stream(337, "US| MLB: BOSTON RED SOX"),
            stream(320, "MLB LIVE 08 : Rockies x White Sox start:2026-09-27 00:10:00"),
            stream(1747, "MLB NEW YORK YANKEES HD", 4),
            stream(1739, "MLB HOUSTON ASTROS HD", 4),
            stream(1734, "MLB CHICAGO WHITE SOX HD", 4),
            stream(1732, "MLB BOSTON RED SOX HD", 4),
        ]
        for home, away, expected, second_account in (
            ("New York Yankees", "Boston Red Sox", [352, 337], [1747, 1732]),
            ("Houston Astros", "Chicago White Sox", [344, 339], [1739, 1734]),
        ):
            with self.subTest(home=home, away=away):
                result = resolve_live_source_content(
                    event=event(home, away), streams=candidates, sources=[source(2), source(4)],
                )
                self.assertIsNotNone(result)
                self.assertEqual(LiveSourceMatchKind.TEAM_FALLBACK, result.match_kind)
                self.assertEqual(expected, [s.stream_id for s in result.matches[0].streams])
                self.assertEqual([TeamRole.HOME, TeamRole.AWAY],
                                 [s.team_role for s in result.matches[0].streams])
                self.assertEqual(("account-2", "account-4"), result.resource_source_ids)
                self.assertEqual(second_account,
                                 [s.stream_id for s in result.matches[1].streams])

    def test_short_multiword_nicknames_work_without_matching_the_other_sox(self):
        result = resolve_live_source_content(
            event=event("Boston Red Sox", "Chicago White Sox"), sources=[source(2)],
            streams=[stream(1, "MLB RED SOX HD"), stream(2, "MLB WHITE SOX HD")],
        )
        self.assertIsNotNone(result)
        self.assertEqual(LiveSourceMatchKind.TEAM_FALLBACK, result.match_kind)
        self.assertEqual([1, 2], [s.stream_id for s in result.matches[0].streams])

    def test_single_wrong_sox_channel_cannot_be_an_exact_event(self):
        self.assertIsNone(resolve_live_source_content(
            event=event("Boston Red Sox", "Chicago White Sox"), sources=[source(2)],
            streams=[stream(1, "MLB WHITE SOX HD")],
        ))

    def test_other_multiword_mlb_nickname_is_not_reduced_to_last_word(self):
        result = resolve_live_source_content(
            event=event("Toronto Blue Jays", "Boston Red Sox"), sources=[source(2)],
            streams=[stream(1, "MLB BLUE JAYS HD"), stream(2, "MLB RED SOX HD"),
                     stream(3, "MLB OTHER JAYS HD")],
        )
        self.assertIsNotNone(result)
        self.assertEqual([1, 2], [s.stream_id for s in result.matches[0].streams])

    def test_exact_current_event_still_wins_over_team_fallback(self):
        result = resolve_live_source_content(
            event=event("Boston Red Sox", "Chicago White Sox"), sources=[source(2)],
            streams=[stream(1, "MLB RED SOX HD"), stream(2, "MLB WHITE SOX HD"),
                     stream(3, "MLB Red Sox vs White Sox 2026-09-29")],
        )
        self.assertIsNotNone(result)
        self.assertEqual(LiveSourceMatchKind.EXACT_EVENT, result.match_kind)
        self.assertEqual([3], [s.stream_id for s in result.matches[0].streams])

    def test_old_exact_event_does_not_override_persistent_channels(self):
        result = resolve_live_source_content(
            event=event("Boston Red Sox", "Chicago White Sox"), sources=[source(2)],
            streams=[stream(1, "MLB RED SOX HD"), stream(2, "MLB WHITE SOX HD"),
                     stream(3, "MLB Red Sox vs White Sox 2026-09-20")],
        )
        self.assertIsNotNone(result)
        self.assertEqual(LiveSourceMatchKind.TEAM_FALLBACK, result.match_kind)

    def test_generic_sox_is_not_sufficient_team_evidence(self):
        self.assertIsNone(resolve_live_source_content(
            event=event("Boston Red Sox", "New York Yankees"), sources=[source(2)],
            streams=[stream(1, "MLB SOX HD"), stream(2, "MLB YANKEES HD")],
        ))


if __name__ == "__main__":
    unittest.main()
