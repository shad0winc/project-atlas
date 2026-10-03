"""Episode neighbors must follow authoritative series ordering, not arithmetic."""
import unittest
from types import SimpleNamespace
from atlas.media import MediaProviderError
from atlas_api.services.playback import PlaybackService

class Provider:
    def __init__(self):
        self.ids = ["e1", "e3", "s2e1"]
        self.fail = False
    def get_item(self, item_id):
        return SimpleNamespace(title="Episode", media_type="tv", metadata={"jellyfin_type": "Episode"})
    def get_retention_context(self, item_id):
        if self.fail: raise MediaProviderError("Parent mismatch")
        return {"item_type": "episode", "series_id": "verified-series"}
    def list_series_episodes(self, series_id):
        assert series_id == "verified-series"
        return tuple({"id": identity} for identity in self.ids)
    def get_playback_info(self, item_id, **kwargs):
        return {"tracks": (), "duration_ticks": 100, "can_seek": True, "stream_path": "/videos/episode/master.m3u8"}

class EpisodeControlsTest(unittest.TestCase):
    def setUp(self):
        self.provider = Provider()
        self.service = PlaybackService(self.provider, jellyfin_public_url="https://jellyfin.example.test")
    def session(self, item):
        return self.service.resolve_library_session(provider="jellyfin", item_id=item, jellyfin_user_id="a"*32)
    def test_first_skips_missing_episode(self):
        s=self.session("e1")
        self.assertEqual((s.series_id,s.previous_target_id,s.next_target_id),("verified-series",None,"e3"))
    def test_exact_episode_has_previous_and_next_across_seasons(self):
        s=self.session("e3")
        self.assertEqual((s.previous_target_id,s.next_target_id),("e1","s2e1"))
    def test_last_stops(self):
        self.assertIsNone(self.session("s2e1").next_target_id)
    def test_duplicate_inventory_does_not_offer_navigation(self):
        self.provider.ids=["e1","e1"]
        s=self.session("e1")
        self.assertTrue(s.available); self.assertIsNone(s.series_id); self.assertIsNone(s.next_target_id)
    def test_missing_membership_does_not_choose_foreign_neighbor(self):
        s=self.session("foreign")
        self.assertTrue(s.available); self.assertIsNone(s.series_id)
    def test_unverifiable_parent_preserves_playback_without_navigation(self):
        self.provider.fail=True
        s=self.session("e1")
        self.assertTrue(s.available); self.assertIsNone(s.series_id)

class EpisodeInventoryQueryTest(unittest.TestCase):
    def test_inventory_excludes_missing_and_virtual_items(self):
        from unittest.mock import patch
        from urllib.parse import parse_qs, urlsplit
        from atlas.media.jellyfin import JellyfinProvider
        with patch.object(JellyfinProvider, "_get_json", return_value={"Items": []}) as request:
            JellyfinProvider(base_url="https://jellyfin.example.test", api_key="fixture").list_series_episodes("series")
        query=parse_qs(urlsplit(request.call_args.args[0]).query)
        self.assertEqual(query["IsMissing"], ["false"])
        self.assertEqual(query["ExcludeLocationTypes"], ["Virtual"])
        self.assertEqual(query["ParentId"], ["series"])
