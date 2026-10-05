"""Protect guide-owned state and bound the newly isolated candidate scores."""
from copy import deepcopy
import json
import unittest
from atlas.media_requests.providers.native_policy_plan import INSTANCES, MODES, NativePolicyPlanError, build_native_policy_plan

def snapshot():
    qualities = [{'id': 1, 'name': 'WEBDL-720p', 'resolution': 720}, {'id': 2, 'name': 'WEBDL-1080p', 'resolution': 1080}, {'id': 3, 'name': 'WEBDL-2160p', 'resolution': 2160}, {'id': 4, 'name': 'DVD', 'resolution': 480}, {'id': 5, 'name': 'Raw-HD', 'resolution': 1080}, {'id': 0, 'name': 'Unknown', 'resolution': 0}]
    names_scores = [('Release tier', 1000), ('Soft downgrade', -51), ('Unsafe source', -10000), ('Language: Not Original', -10000), ('Dubs Only', -10000), ('Anime Dual Audio', 2000), ('Unused', 0)]
    formats = [{'id': index, 'name': name, 'specifications': [{'name': 'Test', 'implementation': 'ReleaseTitleSpecification', 'required': True, 'negate': False, 'fields': [{'name': 'value', 'value': 'PublicFixture'}]}]} for index, (name, _) in enumerate(names_scores, 1)]
    profile = {'id': 7, 'name': 'Guide-owned profile', 'items': [{'quality': quality, 'allowed': quality['resolution'] == 1080} for quality in qualities], 'formatItems': [{'format': index, 'name': name, 'score': score} for index, (name, score) in enumerate(names_scores, 1)]}
    return {'schema_version': 1, 'instances': {name: deepcopy({'active_profile_id': 7, 'proper_repack_policy': 'preferAndUpgrade', 'profiles': [profile], 'custom_formats': formats}) for name in INSTANCES}}

class NativePolicyPlanTests(unittest.TestCase):

    def test_plan_is_deterministic_and_does_not_mutate_or_alias_input(self):
        source = snapshot()
        original = deepcopy(source)
        first = build_native_policy_plan(source)
        assert first == build_native_policy_plan(source)
        assert source == original
        first['instances']['radarr']['new_custom_formats'][0]['payload']['specifications'][0]['fields'][0]['value'] = 'Changed'
        assert source == original

    def test_existing_guide_formats_and_profiles_are_never_update_targets(self):
        source = snapshot()
        plan = build_native_policy_plan(source)
        for name, row in plan['instances'].items():
            assert row['preserved_profile_ids'] == [7]
            assert row['preserved_format_ids'] == list(range(1, 8))
            assert set(row['new_profiles']) == set(MODES)
            names = {entry['payload']['name'] for entry in row['new_custom_formats']}
            assert len(names) == len(row['new_custom_formats'])
            assert all((item.startswith('[Atlas v1]') for item in names))
            assert not names.intersection((item['name'] for item in source['instances'][name]['custom_formats']))
            assert all(('id' not in entry['payload'] for entry in row['new_custom_formats']))
            for profile in row['new_profiles'].values():
                assert 'id' not in profile
                assert set(profile['custom_format_scores']) == {entry['key'] for entry in row['new_custom_formats']}
                assert not {'base:4', 'base:5', 'base:6', 'base:7'}.intersection(profile['custom_format_scores'])
        assert plan['ownership_contract']['existing_profile_new_format_rows'].startswith('new zero-score')

    def test_bounds_cannot_rescue_a_hard_rejected_release(self):
        row = build_native_policy_plan(snapshot())['instances']['radarr']
        bounds = row['score_bounds']
        assert bounds['maximum_positive_score'] + bounds['hard_rejection_score'] < 0
        for profile in row['new_profiles'].values():
            assert profile['custom_format_scores']['base:3'] == bounds['hard_rejection_score']
            assert profile['minimum_format_score'] == 0

    def test_english_priority_dominates_resolution_and_all_baseline_tie_scores(self):
        row = build_native_policy_plan(snapshot())['instances']['sonarr']
        bounds = row['score_bounds']
        lowest_english = bounds['english_bonus'] - bounds['base_soft_penalty_sum']
        highest_other = 3 * bounds['resolution_step'] + bounds['base_positive_sum']
        assert lowest_english > highest_other
        assert bounds['resolution_step'] - bounds['base_soft_penalty_sum'] > bounds['base_positive_sum']
        assert row['new_profiles']['original_subbed']['custom_format_scores']['english_candidate'] == 0

    def test_native_candidate_hint_is_required_and_not_readiness_proof(self):
        row = build_native_policy_plan(snapshot())['instances']['radarr']
        definition = next((item for item in row['new_custom_formats'] if item['key'] == 'english_candidate'))
        assert {spec['implementation'] for spec in definition['payload']['specifications']} == {'LanguageSpecification', 'ReleaseTitleSpecification'}
        assert all((spec['required'] for spec in definition['payload']['specifications']))
        profile = row['new_profiles']['english_required']
        assert profile['custom_format_scores']['missing_english_hint'] < 0
        assert profile['custom_format_scores']['not_english'] < 0
        original = row['new_profiles']['original_subbed']
        assert original['custom_format_scores']['not_original'] < 0
        assert original['full_english_subtitles_required_at_readiness']

    def test_sd_fallback_requires_explicit_opt_in_and_is_anime_only(self):
        default = build_native_policy_plan(snapshot())
        opted = build_native_policy_plan(snapshot(), allow_anime_sd=True)
        for name in INSTANCES:

            def resolutions(plan):
                return {q['resolution'] for q in plan['instances'][name]['new_profiles']['english_preferred']['quality_equality_group']['qualities']}
            assert resolutions(default) == {720, 1080, 2160}
            assert resolutions(opted) == ({480, 720, 1080, 2160} if 'anime' in name else {720, 1080, 2160})
            assert all((q['name'] not in {'Raw-HD', 'Unknown'} for q in opted['instances'][name]['new_profiles']['english_preferred']['quality_equality_group']['qualities']))

    def test_global_proper_policy_and_activation_gates_remain_explicit(self):
        plan = build_native_policy_plan(snapshot())
        assert not plan['activation_allowed'] and (not plan['native_ids_allocated'])
        assert not plan['ownership_contract']['pruning_proof_verified']
        assert 'instance_wide_proper_repack_impact' in plan['release_gates_preserved']
        assert 'retention' in plan['release_gates_preserved']
        assert 'release_reset' in plan['release_gates_preserved']
        assert all((row['required_instance_proper_repack_policy'] == 'doNotPrefer' for row in plan['instances'].values()))

    def test_incomplete_or_conflicting_inventory_is_rejected_without_data_in_error(self):
        for case in ['missing_instance', 'duplicate_profile', 'duplicate_format', 'missing_score', 'dangling_score', 'wrong_score_name', 'bool_id', 'quality_identity_conflict', 'owned_name_collision', 'overflow']:
            with self.subTest(case=case):
                source = snapshot()
                row = source['instances']['radarr']
                if case == 'missing_instance':
                    del source['instances']['sonarr']
                elif case == 'duplicate_profile':
                    row['profiles'].append(deepcopy(row['profiles'][0]))
                elif case == 'duplicate_format':
                    row['custom_formats'].append(deepcopy(row['custom_formats'][0]))
                elif case == 'missing_score':
                    row['profiles'][0]['formatItems'].pop()
                elif case == 'dangling_score':
                    row['profiles'][0]['formatItems'][0]['format'] = 99
                elif case == 'wrong_score_name':
                    row['profiles'][0]['formatItems'][0]['name'] = 'private-marker'
                elif case == 'bool_id':
                    row['custom_formats'][0]['id'] = True
                elif case == 'quality_identity_conflict':
                    item = deepcopy(row['profiles'][0]['items'][0])
                    item['quality']['name'] = 'private-marker'
                    row['profiles'][0]['items'].append(item)
                elif case == 'owned_name_collision':
                    row['profiles'][0]['name'] = '[Atlas v1] private-marker'
                elif case == 'overflow':
                    row['profiles'][0]['formatItems'][0]['score'] = 2147483647
                with self.assertRaises(NativePolicyPlanError) as error:
                    build_native_policy_plan(source)
                assert 'private-marker' not in str(error.exception)

    def test_bad_snapshot_is_rejected(self):
        for value in [None, [], {'schema_version': 2}, {'schema_version': True}]:
            with self.subTest(value=value):
                with self.assertRaises(NativePolicyPlanError):
                    build_native_policy_plan(value)
