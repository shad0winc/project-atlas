"""Select only browser-safe versions advertised for the current viewer and item."""

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from atlas.media.jellyfin import JellyfinProvider
from atlas.media.provider import MediaProviderError


def source(version_id: str, width: int, height: int) -> dict:
    return {
        "Id": version_id,
        "Name": "/private/library/file.mkv",
        "SupportsTranscoding": True,
        "TranscodingUrl": "/Videos/movie/master.m3u8?PlaySessionId=fixture",
        "MediaStreams": [{"Type": "Video", "Width": width, "Height": height}],
    }


class JellyfinPlaybackVersionsTest(unittest.TestCase):
    def setUp(self):
        self.provider = JellyfinProvider("http://jellyfin.invalid", "fixture-key")
        self.high = source("version-4k", 3840, 2160)
        self.low = source("version-hd", 1920, 1080)
        self.catalog = {"MediaSources": [self.high, self.low]}

    def test_lists_safe_dimensions_for_both_versions(self):
        with patch.object(JellyfinProvider, "_request_json", return_value=self.catalog):
            playback = self.provider.get_playback_info("movie", user_id="viewer")

        self.assertEqual(playback["versions"], (
            {"id": "version-4k", "width": 3840, "height": 2160},
            {"id": "version-hd", "width": 1920, "height": 1080},
        ))
        self.assertEqual(playback["selected_version_id"], "version-4k")

    def test_reopens_selected_version_with_its_caption_index(self):
        with patch.object(JellyfinProvider, "_request_json", side_effect=[
            self.catalog, {"MediaSources": [self.low]},
        ]) as request:
            playback = self.provider.get_playback_info(
                "movie", user_id="viewer", selected_version_id="version-hd", subtitle_stream_index=3
            )

        path = parse_qs(urlsplit(playback["stream_path"]).query)
        self.assertEqual(path["MediaSourceId"], ["version-hd"])
        self.assertEqual(playback["video_height"], 1080)
        self.assertEqual(playback["selected_version_id"], "version-hd")
        selected = request.call_args.kwargs["payload"]
        self.assertEqual(selected["UserId"], "viewer")
        self.assertEqual(selected["MediaSourceId"], "version-hd")
        self.assertEqual(selected["SubtitleStreamIndex"], 3)

    def test_rejects_unknown_and_ambiguous_versions_before_negotiation(self):
        catalog = {"MediaSources": [self.high, self.low, self.low]}
        for version in ("other-item-version", "version-hd"):
            with self.subTest(version=version), patch.object(
                JellyfinProvider, "_request_json", return_value=catalog
            ) as request:
                with self.assertRaises(MediaProviderError):
                    self.provider.get_playback_info("movie", user_id="viewer", selected_version_id=version)
                request.assert_called_once()

    def test_rejects_a_stream_url_for_a_different_version(self):
        incorrect = {**self.low, "TranscodingUrl": "/Videos/movie/master.m3u8?MediaSourceId=version-4k"}
        with patch.object(JellyfinProvider, "_request_json", side_effect=[
            self.catalog, {"MediaSources": [incorrect]},
        ]), self.assertRaisesRegex(MediaProviderError, "version identity"):
            self.provider.get_playback_info("movie", user_id="viewer", selected_version_id="version-hd")

    def test_single_copy_has_no_version_picker_metadata(self):
        with patch.object(JellyfinProvider, "_request_json", return_value={"MediaSources": [self.high]}):
            playback = self.provider.get_playback_info("movie", user_id="viewer")

        self.assertNotIn("versions", playback)
        self.assertNotIn("selected_version_id", playback)
