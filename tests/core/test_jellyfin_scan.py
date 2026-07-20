"""Tests for Jellyfin cleanup-scan enumeration."""

from __future__ import annotations

import unittest
from unittest.mock import call, patch

from atlas.media.jellyfin import JellyfinProvider
from atlas.media.provider import MediaProviderError


class JellyfinScanTests(unittest.TestCase):
    """Validate Jellyfin media item enumeration."""

    def setUp(self) -> None:
        self.provider = JellyfinProvider(
            base_url="http://jellyfin:8096",
            api_key="test-key",
        )

    def test_lists_paginated_movie_and_series_ids(
        self,
    ) -> None:
        responses = [
            {
                "Items": [
                    {
                        "Id": "MOVIE-1",
                        "Type": "Movie",
                    },
                    {
                        "Id": "SERIES-1",
                        "Type": "Series",
                    },
                ],
                "TotalRecordCount": 3,
            },
            {
                "Items": [
                    {
                        "Id": "MOVIE-2",
                        "Type": "Movie",
                    },
                ],
                "TotalRecordCount": 3,
            },
        ]

        with patch.object(
            JellyfinProvider,
            "_get_json",
            side_effect=responses,
        ) as get_json:
            item_ids = self.provider.list_media_item_ids(
                page_size=2
            )

        self.assertEqual(
            item_ids,
            (
                "MOVIE-1",
                "SERIES-1",
                "MOVIE-2",
            ),
        )
        self.assertEqual(
            get_json.call_args_list,
            [
                call(
                    "/Items?"
                    "Recursive=true&"
                    "IncludeItemTypes=Movie%2CSeries&"
                    "StartIndex=0&"
                    "Limit=2"
                ),
                call(
                    "/Items?"
                    "Recursive=true&"
                    "IncludeItemTypes=Movie%2CSeries&"
                    "StartIndex=2&"
                    "Limit=2"
                ),
            ],
        )

    def test_empty_library_returns_empty_tuple(
        self,
    ) -> None:
        with patch.object(
            JellyfinProvider,
            "_get_json",
            return_value={
                "Items": [],
                "TotalRecordCount": 0,
            },
        ):
            item_ids = (
                self.provider.list_media_item_ids()
            )

        self.assertEqual(item_ids, ())

    def test_rejects_invalid_page_size(self) -> None:
        invalid_values = (
            0,
            -1,
            True,
            1.5,
            "200",
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(
                    MediaProviderError
                ):
                    self.provider.list_media_item_ids(
                        page_size=value,  # type: ignore[arg-type]
                    )

    def test_rejects_invalid_list_response(
        self,
    ) -> None:
        invalid_responses = (
            [],
            {
                "Items": "invalid",
                "TotalRecordCount": 1,
            },
            {
                "Items": [],
                "TotalRecordCount": "zero",
            },
            {
                "Items": [],
                "TotalRecordCount": -1,
            },
        )

        for response in invalid_responses:
            with self.subTest(response=response):
                with patch.object(
                    JellyfinProvider,
                    "_get_json",
                    return_value=response,
                ):
                    with self.assertRaises(
                        MediaProviderError
                    ):
                        self.provider.list_media_item_ids()

    def test_rejects_invalid_item_entry(
        self,
    ) -> None:
        invalid_entries = (
            "invalid",
            {},
            {"Id": ""},
            {"Id": 123},
        )

        for entry in invalid_entries:
            with self.subTest(entry=entry):
                with patch.object(
                    JellyfinProvider,
                    "_get_json",
                    return_value={
                        "Items": [entry],
                        "TotalRecordCount": 1,
                    },
                ):
                    with self.assertRaises(
                        MediaProviderError
                    ):
                        self.provider.list_media_item_ids()

    def test_rejects_duplicate_item_ids(
        self,
    ) -> None:
        with patch.object(
            JellyfinProvider,
            "_get_json",
            return_value={
                "Items": [
                    {"Id": "MOVIE-1"},
                    {"Id": "movie-1"},
                ],
                "TotalRecordCount": 2,
            },
        ):
            with self.assertRaisesRegex(
                MediaProviderError,
                "duplicate item ID",
            ):
                self.provider.list_media_item_ids()


if __name__ == "__main__":
    unittest.main()
