from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from atlas.media.jellyfin import JellyfinProvider
from atlas.media.provider import MediaProviderError


class Response:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.value).encode()


class JellyfinLiveTvChannelTests(unittest.TestCase):
    def provider(self) -> JellyfinProvider:
        return JellyfinProvider(
            "http://jellyfin:8096",
            "secret",
        )

    def test_returns_empty_channel_list(self) -> None:
        with patch(
            "atlas.media.jellyfin.urlopen",
            return_value=Response(
                {
                    "Items": [],
                    "TotalRecordCount": 0,
                }
            ),
        ) as request:
            channels = self.provider().list_live_tv_channels()

        self.assertEqual((), channels)
        self.assertEqual(
            "http://jellyfin:8096/LiveTv/Channels?StartIndex=0&Limit=200",
            request.call_args.args[0].full_url,
        )
        self.assertEqual(
            "secret",
            request.call_args.args[0].headers["X-emby-token"],
        )

    def test_returns_only_safe_normalized_channel_identity(self) -> None:
        with patch(
            "atlas.media.jellyfin.urlopen",
            return_value=Response(
                {
                    "Items": [
                        {
                            "Id": "channel-1",
                            "Name": "NFL RedZone",
                            "Number": "100",
                            "Type": "TvChannel",
                            "Path": "https://secret.invalid/live.m3u8",
                            "MediaSources": [
                                {
                                    "Path": "https://secret.invalid/source.m3u8"
                                }
                            ],
                            "ChannelId": "internal-tuner-id",
                        },
                        {
                            "Id": "channel-2",
                            "Name": "Atlas Sports",
                            "Number": None,
                            "Type": "LiveTvChannel",
                        },
                    ],
                    "TotalRecordCount": 2,
                }
            ),
        ):
            channels = self.provider().list_live_tv_channels()

        self.assertEqual(
            (
                {
                    "item_id": "channel-1",
                    "name": "NFL RedZone",
                    "channel_number": "100",
                    "type": "TvChannel",
                },
                {
                    "item_id": "channel-2",
                    "name": "Atlas Sports",
                    "channel_number": None,
                    "type": "LiveTvChannel",
                },
            ),
            channels,
        )

        serialized = json.dumps(channels)
        self.assertNotIn("secret.invalid", serialized)
        self.assertNotIn("MediaSources", serialized)
        self.assertNotIn("ChannelId", serialized)
        self.assertNotIn("Path", serialized)

    def test_paginates_live_tv_channels(self) -> None:
        responses = [
            Response(
                {
                    "Items": [
                        {
                            "Id": "channel-1",
                            "Name": "One",
                            "Number": "1",
                            "Type": "TvChannel",
                        }
                    ],
                    "TotalRecordCount": 2,
                }
            ),
            Response(
                {
                    "Items": [
                        {
                            "Id": "channel-2",
                            "Name": "Two",
                            "Number": "2",
                            "Type": "TvChannel",
                        }
                    ],
                    "TotalRecordCount": 2,
                }
            ),
        ]

        with patch(
            "atlas.media.jellyfin.urlopen",
            side_effect=responses,
        ) as request:
            channels = self.provider().list_live_tv_channels(
                page_size=1
            )

        self.assertEqual(
            ("channel-1", "channel-2"),
            tuple(channel["item_id"] for channel in channels),
        )
        self.assertEqual(2, request.call_count)
        self.assertEqual(
            "http://jellyfin:8096/LiveTv/Channels?StartIndex=0&Limit=1",
            request.call_args_list[0].args[0].full_url,
        )
        self.assertEqual(
            "http://jellyfin:8096/LiveTv/Channels?StartIndex=1&Limit=1",
            request.call_args_list[1].args[0].full_url,
        )

    def test_rejects_duplicate_ids_case_insensitively(self) -> None:
        with patch(
            "atlas.media.jellyfin.urlopen",
            return_value=Response(
                {
                    "Items": [
                        {
                            "Id": "CHANNEL-1",
                            "Name": "One",
                            "Type": "TvChannel",
                        },
                        {
                            "Id": "channel-1",
                            "Name": "Duplicate",
                            "Type": "TvChannel",
                        },
                    ],
                    "TotalRecordCount": 2,
                }
            ),
        ):
            with self.assertRaisesRegex(
                MediaProviderError,
                "duplicate Jellyfin Live TV channel ID",
            ):
                self.provider().list_live_tv_channels()

    def test_rejects_malformed_root_and_list_shapes(self) -> None:
        invalid = (
            [],
            {"Items": "invalid", "TotalRecordCount": 0},
            {"Items": [], "TotalRecordCount": "zero"},
            {"Items": [], "TotalRecordCount": -1},
        )

        for payload in invalid:
            with self.subTest(payload=payload):
                with patch(
                    "atlas.media.jellyfin.urlopen",
                    return_value=Response(payload),
                ):
                    with self.assertRaises(MediaProviderError):
                        self.provider().list_live_tv_channels()

    def test_rejects_invalid_channel_entries(self) -> None:
        invalid_entries = (
            "invalid",
            {},
            {
                "Id": "",
                "Name": "No ID",
                "Type": "TvChannel",
            },
            {
                "Id": "channel-1",
                "Name": "",
                "Type": "TvChannel",
            },
            {
                "Id": "channel-1",
                "Name": "Movie",
                "Type": "Movie",
            },
            {
                "Id": "channel-1",
                "Name": "Channel",
                "Type": "TvChannel",
                "Number": 12,
            },
        )

        for entry in invalid_entries:
            with self.subTest(entry=entry):
                with patch(
                    "atlas.media.jellyfin.urlopen",
                    return_value=Response(
                        {
                            "Items": [entry],
                            "TotalRecordCount": 1,
                        }
                    ),
                ):
                    with self.assertRaises(MediaProviderError):
                        self.provider().list_live_tv_channels()

    def test_rejects_invalid_page_size(self) -> None:
        for value in (True, 0, -1, 1.5, "200"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    MediaProviderError,
                    "page_size must be a positive integer",
                ):
                    self.provider().list_live_tv_channels(
                        page_size=value,  # type: ignore[arg-type]
                    )

    def test_rejects_pagination_stall(self) -> None:
        with patch(
            "atlas.media.jellyfin.urlopen",
            return_value=Response(
                {
                    "Items": [],
                    "TotalRecordCount": 1,
                }
            ),
        ):
            with self.assertRaisesRegex(
                MediaProviderError,
                "pagination stalled",
            ):
                self.provider().list_live_tv_channels()


if __name__ == "__main__":
    unittest.main()
