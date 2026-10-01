from __future__ import annotations

import unittest

from live_source_resolver import (
    DispatcharrStreamCandidate, LiveSourceMatchKind,
    _looks_event_specific, resolve_live_source_content,
)
from source_lifecycle import SportsSource


def source(account):
    return SportsSource.from_mapping({
        'source_id': f'account-{account}', 'display_name': f'Account {account}',
        'provider_id': 'fixture', 'provider_display_name': 'Fixture',
        'account_display_name': str(account), 'kind': 'licensed_subscription',
        'enabled': True, 'priority': account, 'max_connections': 3,
        'backend_reference': f'dispatcharr:m3u:{account}',
    })


def event():
    return {
        'provider': 'thesportsdb', 'provider_event_id': '2475422',
        'name': 'Cleveland Browns vs Pittsburgh Steelers',
        'sport': 'American Football', 'league': 'NFL',
        'home_team': 'Cleveland Browns', 'away_team': 'Pittsburgh Steelers',
        'start_at': '2026-10-02T00:15:00+00:00',
    }


def stream(identifier, name, account=5, stale=False):
    return DispatcharrStreamCandidate(
        identifier, name, account, group_name='|NA| USA NFL', is_stale=stale,
    )


def inventory(account=5):
    return [
        stream(2142 + account * 10000, 'NFL CBS BROWNS CLEVLAND OH', account),
        stream(2157 + account * 10000, 'NFL CBS STEELERS PITTSBURGH PA', account),
        stream(2123 + account * 10000, 'NFL  | 03 - 1pm Panthers at Browns', account),
        stream(2128 + account * 10000, 'NFL  | 08 - 1pm Bengals at Steelers', account),
    ]


class NumberedNFLSlotTests(unittest.TestCase):
    def test_reported_slots_are_event_specific(self):
        for row in inventory()[2:]:
            with self.subTest(name=row.name):
                self.assertTrue(_looks_event_specific(row))

    def test_spacing_case_and_kickoff_minutes(self):
        for name in (
            'NFL|08-1PM Bengals at Steelers',
            'US | NFL | 03 - 1:00 pm Panthers at Browns',
            'NFL | 12 - 8:15PM Browns vs. Steelers',
        ):
            with self.subTest(name=name):
                self.assertTrue(_looks_event_specific(stream(1, name)))

    def test_persistent_and_incomplete_names_are_not_reclassified(self):
        for name in (
            'NFL CBS STEELERS PITTSBURGH PA', 'NFL CBS BROWNS CLEVLAND OH',
            'US| NFL: STEELERS HD', 'NFL | 08 HD',
            'NFL | 03 - Browns', 'NFL | 03 - 1pm Browns',
        ):
            with self.subTest(name=name):
                self.assertFalse(_looks_event_specific(stream(1, name)))

    def test_both_accounts_resolve_only_persistent_team_channels(self):
        result = resolve_live_source_content(
            event=event(), sources=[source(5), source(6)],
            streams=inventory(5) + inventory(6),
        )
        self.assertIsNotNone(result)
        self.assertEqual(LiveSourceMatchKind.TEAM_FALLBACK, result.match_kind)
        self.assertEqual(('account-5', 'account-6'), result.resource_source_ids)
        for match, account in zip(result.matches, (5, 6)):
            self.assertEqual([2142 + account * 10000, 2157 + account * 10000],
                             [row.stream_id for row in match.streams])

    def test_unrelated_slots_alone_cannot_qualify(self):
        self.assertIsNone(resolve_live_source_content(
            event=event(), sources=[source(5)], streams=inventory()[2:],
        ))

    def test_duplicate_persistent_channels_still_fail_closed(self):
        self.assertIsNone(resolve_live_source_content(
            event=event(), sources=[source(5)], streams=inventory() + [
                stream(999, 'NFL BROWNS HD')],
        ))

    def test_stale_team_channel_still_fails_closed(self):
        rows = inventory()
        rows[0] = stream(rows[0].stream_id, rows[0].name, stale=True)
        self.assertIsNone(resolve_live_source_content(
            event=event(), sources=[source(5)], streams=rows,
        ))

    def test_exact_matchup_retains_priority(self):
        exact = stream(999, 'NFL | 12 - 8:15pm Browns at Steelers')
        result = resolve_live_source_content(
            event=event(), sources=[source(5)], streams=inventory() + [exact],
        )
        self.assertIsNotNone(result)
        self.assertEqual(LiveSourceMatchKind.EXACT_EVENT, result.match_kind)
        self.assertEqual([999], [row.stream_id for row in result.matches[0].streams])
