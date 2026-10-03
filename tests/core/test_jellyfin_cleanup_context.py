"""Read-only Jellyfin hierarchy and separate cleanup inventory contracts."""
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from atlas.media.jellyfin import JellyfinProvider
from atlas.media.provider import MediaProviderError

class JellyfinCleanupContext(unittest.TestCase):
    def setUp(self):
        self.provider=JellyfinProvider('http://unused', 'test')
    def context(self, *rows):
        with patch.object(JellyfinProvider, '_get_json', side_effect=[{'Items': [row]} for row in rows]) as read:
            result=self.provider.get_retention_context('episode')
        self.assertEqual(read.call_count, len(rows))
        return result
    def test_episode_parent_verified(self):
        result=self.context({'Id':'episode', 'Type':'Episode', 'SeriesId':'series'}, {'Id':'series', 'Type':'Series'})
        self.assertEqual(result, {'item_type':'episode', 'series_id':'series'})
    def test_invalid_hierarchy_rejected(self):
        for row, parent in (
            ({'Id':'wrong', 'Type':'Episode', 'SeriesId':'series'}, None),
            ({'Id':'episode', 'Type':'Episode'}, None),
            ({'Id':'episode', 'Type':'Episode', 'SeriesId':'episode'}, None),
            ({'Id':'episode', 'Type':'Episode', 'SeriesId':'series'}, {'Id':'series', 'Type':'Movie'}),
            ({'Id':'episode', 'Type':'Episode', 'SeriesId':'series'}, {'Id':'other', 'Type':'Series'}),
            ({'Id':'episode', 'Type':'LiveTvChannel'}, None),
        ):
            with self.subTest(row=row, parent=parent), self.assertRaises(MediaProviderError):
                self.context(*([row, parent] if parent else [row]))
    def test_parent_lookup_failure_propagates(self):
        with patch.object(JellyfinProvider, '_get_json', side_effect=[
            {'Items':[{'Id':'episode', 'Type':'Episode', 'SeriesId':'series'}]},
            MediaProviderError('unavailable'),
        ]), self.assertRaises(MediaProviderError):
            self.provider.get_retention_context('episode')
    def test_empty_or_ambiguous_identity_rejected(self):
        for rows in ([], [{}], [{'Id':'episode','Type':'Movie'}]*2):
            with self.subTest(rows=rows), patch.object(JellyfinProvider, '_get_json', return_value={'Items':rows}), self.assertRaises(MediaProviderError):
                self.provider.get_retention_context('episode')
    def test_movie_context_does_not_need_parent(self):
        self.assertEqual(self.context({'Id':'episode','Type':'Movie'}), {'item_type':'movie'})
    def test_inventory_and_catalog_queries_remain_separate(self):
        for method, kwargs, types in (
            ('list_media_item_ids', {}, 'Movie,Series'),
            ('list_cleanup_item_ids', {}, 'Movie'),
            ('list_cleanup_item_ids', {'include_episodes':True}, 'Movie,Episode'),
        ):
            with self.subTest(method=method, kwargs=kwargs), patch.object(JellyfinProvider, '_get_json', return_value={'Items':[], 'TotalRecordCount':0}) as read:
                self.assertEqual(getattr(self.provider, method)(**kwargs), ())
                query=parse_qs(urlsplit(read.call_args.args[0]).query)
                self.assertEqual(query['IncludeItemTypes'], [types])
    def test_cleanup_pagination_and_duplicate_checks(self):
        pages=[
            {'Items':[{'Id':'first','Type':'Episode'}], 'TotalRecordCount':2},
            {'Items':[{'Id':'second','Type':'Movie'}], 'TotalRecordCount':2},
        ]
        with patch.object(JellyfinProvider, '_get_json', side_effect=pages):
            self.assertEqual(self.provider.list_cleanup_item_ids(page_size=1, include_episodes=True), ('first','second'))
        for payload in (
            {'Items':[], 'TotalRecordCount':1},
            {'Items':[{'Id':'series','Type':'Series'}], 'TotalRecordCount':1},
            {'Items':[{'Id':'a','Type':'Movie'}]*2, 'TotalRecordCount':2},
            {'Items':[{'Id':'a','Type':'Movie'}], 'TotalRecordCount':0},
        ):
            with self.subTest(payload=payload), patch.object(JellyfinProvider, '_get_json', return_value=payload), self.assertRaises(MediaProviderError):
                self.provider.list_cleanup_item_ids(include_episodes=True)
    def test_inventory_gate_requires_boolean(self):
        with self.assertRaises(MediaProviderError):
            self.provider.list_cleanup_item_ids(include_episodes='true')

if __name__=='__main__':
    unittest.main()
