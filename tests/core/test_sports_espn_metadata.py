import copy
from datetime import datetime
from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]

def samples():
    import json, hashlib
    path = ROOT / "tests/fixtures/sports/espn-metadata-20261016.json"
    fixture = json.loads(path.read_text())
    assert fixture["source_archive_sha256"] == "12f6d2e257041b41ec8596b5a9e17c717f3f1ba0f21fb2358b3ff2839a03ef4b"
    for row in fixture["samples"]:
        encoded = json.dumps(row["payload"], sort_keys=True, separators=(",", ":")).encode()
        assert hashlib.sha256(encoded).hexdigest() == row["projection_sha256"]
        assert len(row["payload"]["events"]) == row["event_count"]
        yield row, row["payload"]

class ESPNMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "modules/sports/src"))
        global MetadataError, parse_scoreboard
        from providers.espn_metadata import MetadataError, parse_scoreboard
        cls.data = {row['file']: (row, data) for row, data in samples()}

    def nfl(self):
        return copy.deepcopy(self.data['nfl.json'][1])

    def test_all_six_captured_responses(self):
        total = 0
        for row, raw in self.data.values():
            with self.subTest(route=row['route']):
                events = parse_scoreboard(row['route'], raw)
                self.assertEqual(len(events), row['event_count'])
                self.assertEqual(len({e.identity for e in events}), len(events))
                self.assertTrue(all(e.provider == 'espn' for e in events))
                self.assertTrue(all(e.status == 'scheduled' for e in events))
                total += len(events)
        self.assertEqual(total, 34)

    def test_sunday_night_remains_monday_utc(self):
        events = parse_scoreboard('football/nfl', self.nfl())
        game = next(e for e in events if e.provider_event_id == '401873007')
        self.assertEqual(game.start_at, '2026-10-19T00:20:00Z')

    def test_ufc_is_one_card_with_thirteen_bouts(self):
        raw = self.data['ufc.json'][1]
        events = parse_scoreboard('mma/ufc', raw)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, 'fight_card')
        self.assertEqual(events[0].timing_kind, 'card_start')
        self.assertEqual(len(events[0].competitions), 13)
        self.assertEqual(len({c.start_at for c in events[0].competitions}), 2)
        self.assertTrue(all(p.side is None and p.kind == 'athlete'
                            for c in events[0].competitions for p in c.participants))

    def test_fighters_not_home_and_away_teams(self):
        with self.assertRaises(MetadataError):
            parse_scoreboard('football/nfl', self.data['ufc.json'][1])

    def test_empty_success_valid(self):
        data = copy.deepcopy(self.data['epl.json'][1])
        data['events'] = []
        self.assertEqual(parse_scoreboard('soccer/eng.1', data), ())

    def test_missing_events_is_failure(self):
        for value in ({}, {'events': None}, {'error': 'unavailable'}, [], None):
            with self.subTest(value=value), self.assertRaises(MetadataError):
                parse_scoreboard('football/nfl', value)

    def test_unknown_route_rejected(self):
        with self.assertRaises(MetadataError):
            parse_scoreboard('mma/pfl', {'events': []})

    def test_missing_event_id_fails_entire_response(self):
        data = self.nfl()
        del data['events'][-1]['id']
        with self.assertRaises(MetadataError):
            parse_scoreboard('football/nfl', data)

    def test_identical_duplicate_collapses(self):
        data = self.nfl()
        data['events'].append(copy.deepcopy(data['events'][0]))
        self.assertEqual(len(parse_scoreboard('football/nfl', data)), 12)

    def test_conflicting_duplicate_rejected(self):
        data = self.nfl()
        other = copy.deepcopy(data['events'][0])
        other['date'] = '2026-10-19T12:00Z'
        other['competitions'][0]['date'] = other['date']
        data['events'].append(other)
        with self.assertRaises(MetadataError):
            parse_scoreboard('football/nfl', data)

    def test_naive_dates_rejected(self):
        data = self.nfl()
        data['events'][0]['competitions'][0]['date'] = '2026-10-18T13:30:00'
        with self.assertRaises(MetadataError):
            parse_scoreboard('football/nfl', data)

    def test_unverified_time_not_reported(self):
        data = self.nfl()
        data['events'][0]['competitions'][0]['timeValid'] = False
        self.assertIsNone(parse_scoreboard('football/nfl', data)[0].start_at)

    def test_missing_time_validity_rejected(self):
        data = self.nfl()
        del data['events'][0]['competitions'][0]['timeValid']
        with self.assertRaises(MetadataError):
            parse_scoreboard('football/nfl', data)

    def test_delayed_cancelled_and_unknown_not_scheduled(self):
        for name, expected in (
            ('STATUS_POSTPONED', 'postponed'), ('STATUS_DELAYED', 'postponed'),
            ('STATUS_CANCELED', 'cancelled'), ('STATUS_UNRECOGNIZED', 'unknown'),
        ):
            with self.subTest(name=name):
                data = self.nfl()
                data['events'][0]['status']['type']['name'] = name
                self.assertEqual(parse_scoreboard('football/nfl', data)[0].status, expected)

    def test_live_and_final_require_consistent_flags(self):
        for name, state, completed, expected in (
            ('STATUS_IN_PROGRESS', 'in', False, 'live'),
            ('STATUS_FINAL', 'post', True, 'final'),
            ('STATUS_FINAL', 'pre', False, 'unknown'),
            ('STATUS_SCHEDULED', 'pre', True, 'unknown'),
        ):
            with self.subTest(name=name, completed=completed):
                data = self.nfl()
                data['events'][0]['status']['type'] = dict(
                    name=name, state=state, completed=completed)
                self.assertEqual(parse_scoreboard('football/nfl', data)[0].status, expected)

    def test_provider_ids_scoped_by_route(self):
        one = parse_scoreboard('football/nfl', self.nfl())[0]
        other = replace(one, route='basketball/nba')
        self.assertNotEqual(one.identity, other.identity)

    def test_mismatched_response_league_rejected(self):
        with self.assertRaises(MetadataError):
            parse_scoreboard('basketball/nba', self.nfl())

    def test_missing_response_league_rejected(self):
        data = self.nfl()
        del data['leagues']
        with self.assertRaises(MetadataError):
            parse_scoreboard('football/nfl', data)

    def test_participant_identity_mismatch_rejected(self):
        data = self.nfl()
        data['events'][0]['competitions'][0]['competitors'][0]['team']['id'] = '9999'
        with self.assertRaises(MetadataError):
            parse_scoreboard('football/nfl', data)

    def test_repeated_home_side_rejected(self):
        data = self.nfl()
        for participant in data['events'][0]['competitions'][0]['competitors']:
            participant['homeAway'] = 'home'
        with self.assertRaises(MetadataError):
            parse_scoreboard('football/nfl', data)

    def test_oversized_event_count_rejected(self):
        data = self.nfl()
        data['events'] = data['events'][:1] * 501
        with self.assertRaises(MetadataError):
            parse_scoreboard('football/nfl', data)

if __name__ == '__main__':
    unittest.main()
