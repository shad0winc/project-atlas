import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]

class DirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,str(ROOT/'modules/sports/src'))
        global parse_team_directory, search_directory, encode_entity_id, decode_entity_id, MetadataError
        from providers.espn_directory import parse_team_directory, search_directory, encode_entity_id, decode_entity_id, MetadataError
        cls.fixture=json.loads((ROOT/'tests/fixtures/sports/espn-team-directories-20261016.json').read_text())
        cls.data={row['route']:row['payload'] for row in cls.fixture['samples']}

    def test_all_five_attested_directories(self):
        sizes=[]
        for row in self.fixture['samples']:
            with self.subTest(route=row['route']):
                teams=parse_team_directory(row['route'],row['payload'])
                self.assertEqual(len(teams),row['team_count'])
                self.assertEqual(len({t.identity for t in teams}),len(teams))
                sizes.append(len(teams))
        self.assertEqual(sizes,[32,30,30,32,20])
        self.assertEqual(sum(sizes),144)

    def test_directory_includes_teams_absent_from_captured_sunday_games(self):
        teams=parse_team_directory('football/nfl',self.data['football/nfl'])
        names={t.name for t in teams}
        self.assertIn('Seattle Seahawks',names)
        self.assertIn('Denver Broncos',names)
        self.assertEqual(search_directory(teams,'seahawks')[0].name,'Seattle Seahawks')

    def test_abbreviation_search_is_case_insensitive(self):
        teams=parse_team_directory('basketball/nba',self.data['basketball/nba'])
        self.assertEqual(search_directory(teams,'lal')[0].name,'Los Angeles Lakers')

    def test_initial_empty_query_does_not_dump_the_directory(self):
        teams=parse_team_directory('football/nfl',self.data['football/nfl'])
        self.assertEqual(search_directory(teams,' '),())

    def test_ids_round_trip_and_remain_separate_across_sports(self):
        self.assertNotEqual(encode_entity_id('football/nfl','1'),encode_entity_id('basketball/nba','1'))
        self.assertEqual(decode_entity_id(encode_entity_id('soccer/eng.1','349')),('soccer/eng.1','349'))

    def test_unscoped_ids_and_paths_are_not_accepted(self):
        for identity in ('1','../1','football-nfl-1/summary','football-nfl-',None):
            with self.subTest(identity=identity),self.assertRaises(MetadataError):
                decode_entity_id(identity)

    def test_mismatched_response_league_is_failure(self):
        with self.assertRaises(MetadataError):
            parse_team_directory('basketball/nba',self.data['football/nfl'])

    def test_conflicting_team_id_is_failure(self):
        data=copy.deepcopy(self.data['football/nfl'])
        rows=data['sports'][0]['leagues'][0]['teams']
        other=copy.deepcopy(rows[0]);other['team']['displayName']='Wrong Team'
        rows.append(other)
        with self.assertRaises(MetadataError):parse_team_directory('football/nfl',data)

    def test_ufc_is_not_treated_as_a_team_directory(self):
        with self.assertRaises(MetadataError):parse_team_directory('mma/ufc',{})

    def test_missing_directory_is_failure_not_empty_success(self):
        for data in ({},{'sports':[]},None):
            with self.subTest(data=data),self.assertRaises(MetadataError):
                parse_team_directory('football/nfl',data)
