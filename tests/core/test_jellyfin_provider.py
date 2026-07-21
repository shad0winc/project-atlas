from __future__ import annotations
import io, json, unittest
from unittest.mock import patch
from urllib.error import HTTPError
from atlas.media.capabilities import ProviderCapability
from atlas.media.jellyfin import JellyfinProvider
from atlas.media.provider import MediaProviderError

class Response:
    def __init__(self, value): self.value=value
    def __enter__(self): return self
    def __exit__(self,*_): return False
    def read(self): return json.dumps(self.value).encode()

class JellyfinProviderTests(unittest.TestCase):
    def test_capability_contract(self):
        provider = JellyfinProvider(
            "http://jellyfin:8096",
            "secret",
        )

        capabilities = provider.get_capabilities()

        self.assertEqual(
            capabilities.provider,
            "jellyfin",
        )
        self.assertTrue(
            capabilities.supports(
                ProviderCapability.LIST_MEDIA
            )
        )
        self.assertTrue(
            capabilities.supports(
                ProviderCapability.PREVIEW_DELETE
            )
        )
        self.assertFalse(
            capabilities.supports(
                ProviderCapability.DELETE
            )
        )
        self.assertTrue(
            capabilities.supports_batch_listing
        )
        self.assertFalse(
            capabilities.supports_batch_preview
        )
        self.assertEqual(
            capabilities.max_batch_size,
            200,
        )

    def test_normalizes_movie_metadata_and_library(self):
        responses=[Response({"Name":"The Matrix","Type":"Movie","ProductionYear":1999,"Path":"/media/Movies/The Matrix.mkv"}),Response([{"Name":"Movies","Type":"CollectionFolder"}])]
        with patch("atlas.media.jellyfin.urlopen",side_effect=responses) as request:
            item=JellyfinProvider("http://jellyfin:8096","secret").get_item("abc")
        self.assertEqual("movie",item.media_type); self.assertEqual("Movies",item.metadata["library"]); self.assertEqual(2,request.call_count)
        self.assertEqual("secret",request.call_args_list[0].args[0].headers["X-emby-token"])
    def test_series_maps_to_tv_and_ancestor_failure_is_nonfatal(self):
        error=HTTPError("url",500,"bad",{},io.BytesIO())
        with patch("atlas.media.jellyfin.urlopen",side_effect=[Response({"Name":"Show","Type":"Series"}),error]):
            item=JellyfinProvider("http://jellyfin:8096","secret").get_item("series")
        self.assertEqual("tv",item.media_type); self.assertNotIn("library",item.metadata)
    def test_missing_key_and_not_found_are_clear(self):
        with self.assertRaisesRegex(MediaProviderError,"API_KEY"):
            JellyfinProvider("http://jellyfin:8096","").get_item("abc")
        error=HTTPError("url",404,"missing",{},io.BytesIO())
        with patch("atlas.media.jellyfin.urlopen",side_effect=error):
            with self.assertRaisesRegex(MediaProviderError,"not found"):
                JellyfinProvider("http://jellyfin:8096","secret").get_item("abc")
    def test_get_user_returns_normalized_identity(self):
        with patch(
            "atlas.media.jellyfin.urlopen",
            return_value=Response(
                {
                    "Id": "e29fdc8501124a5d8a1f40653e487407",
                    "Name": "admin",
                }
            ),
        ) as request:
            user = JellyfinProvider(
                "http://jellyfin:8096",
                "secret",
            ).get_user("e29fdc8501124a5d8a1f40653e487407")

        self.assertEqual(
            {
                "id": "e29fdc8501124a5d8a1f40653e487407",
                "name": "admin",
            },
            user,
        )
        requested_url = request.call_args.args[0].full_url
        self.assertEqual(
            "http://jellyfin:8096/Users/e29fdc8501124a5d8a1f40653e487407",
            requested_url,
        )

    def test_get_user_rejects_invalid_response(self):
        with patch(
            "atlas.media.jellyfin.urlopen",
            return_value=Response([]),
        ):
            with self.assertRaisesRegex(
                MediaProviderError,
                "invalid user response",
            ):
                JellyfinProvider(
                    "http://jellyfin:8096",
                    "secret",
                ).get_user("e29fdc8501124a5d8a1f40653e487407")

    def test_get_user_rejects_mismatched_identity(self):
        with patch(
            "atlas.media.jellyfin.urlopen",
            return_value=Response(
                {
                    "Id": "e2146f344e124798ae00ce396d329072",
                    "Name": "root",
                }
            ),
        ):
            with self.assertRaisesRegex(
                MediaProviderError,
                "mismatched user response",
            ):
                JellyfinProvider(
                    "http://jellyfin:8096",
                    "secret",
                ).get_user("e29fdc8501124a5d8a1f40653e487407")
