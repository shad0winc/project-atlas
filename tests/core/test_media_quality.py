import unittest
from atlas.media.quality import video_dimensions

class QualityTest(unittest.TestCase):
    def test_source_dimensions_ignore_embedded_art_and_audio(self):
        streams = [{"Type":"EmbeddedImage","Width":400,"Height":562},
                   {"Type":"Video","Codec":"mjpeg","Width":400,"Height":562},
                   {"Type":"Audio","Width":3840,"Height":2160},
                   {"Type":"Video","Codec":"h264","Width":1920,"Height":800}]
        self.assertEqual(video_dimensions({"MediaStreams":streams}), {"video_width":1920,"video_height":800})
    def test_invalid_or_missing_dimensions_are_unknown(self):
        for width,height in [(True,720),(1920,None),(1920,0),("1920",1080),(100000,1080)]:
            self.assertEqual(video_dimensions({"MediaStreams":[{"Type":"Video","Width":width,"Height":height}]}), {})
        self.assertEqual(video_dimensions({}), {})
    def test_provider_includes_actual_episode_and_movie_dimensions_only(self):
        from atlas.media.jellyfin import JellyfinProvider
        class Provider(JellyfinProvider):
            def _get_json(self, path):
                return {"Items":[{"Id":"id","Name":"Fixture","Type":self.kind,
                    "MediaStreams":[{"Type":"Video","Codec":"hevc","Width":3840,"Height":2160}]}]}
            def _library_name(self, item_id): return None
        provider=Provider(base_url="http://fixture",api_key="fixture")
        for kind in ("Movie","Episode"):
            provider.kind=kind
            self.assertEqual(provider.get_item("id").metadata["video_width"],3840)
        provider.kind="Series"
        self.assertNotIn("video_width",provider.get_item("id").metadata)
