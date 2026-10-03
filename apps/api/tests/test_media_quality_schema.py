import unittest
from atlas.media import MediaItem
from atlas_api.schemas.media_catalog import MediaCatalogItemResponse
from atlas_api.schemas.playback import PlaybackEpisodeResponse

class QualitySchemaTest(unittest.TestCase):
    def test_catalog_discloses_only_safe_dimensions(self):
        response=MediaCatalogItemResponse.from_domain(MediaItem("jellyfin","id","movie","Fixture",
            {"video_width":3840,"video_height":1600,"path":"/private/media"}))
        self.assertEqual((response.video_width,response.video_height),(3840,1600))
        self.assertNotIn("path",response.model_dump())
    def test_invalid_dimensions_remain_unknown(self):
        for width,height in [(True,720),(1920,None),(0,1080)]:
            response=MediaCatalogItemResponse.from_domain(MediaItem("jellyfin","id","movie","Fixture",
                {"video_width":width,"video_height":height}))
            self.assertIsNone(response.video_width)
            self.assertIsNone(response.video_height)
    def test_episode_dimensions_are_optional_and_independent(self):
        first=PlaybackEpisodeResponse(id="one",title="First",video_width=640,video_height=480)
        other=PlaybackEpisodeResponse(id="two",title="Second")
        self.assertEqual(first.video_height,480)
        self.assertIsNone(other.video_height)
