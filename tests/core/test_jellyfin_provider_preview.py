"""Tests for Jellyfin deletion preview behavior."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from unittest.mock import patch

from atlas.media import (
    JellyfinProvider,
    MediaItem,
    MediaProviderError,
    ProviderMutationResult,
    ProviderOperation,
)


EXECUTED_AT = datetime(
    2026,
    7,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_provider(
    *,
    clock=lambda: EXECUTED_AT,
) -> JellyfinProvider:
    """Create a deterministic Jellyfin provider."""

    return JellyfinProvider(
        base_url="http://jellyfin.test",
        api_key="test-key",
        clock=clock,
    )


class JellyfinProviderPreviewTests(unittest.TestCase):
    """Tests for JellyfinProvider.preview_delete_item."""

    def test_preview_delete_item_returns_successful_result(
        self,
    ) -> None:
        provider = make_provider()

        item = MediaItem(
            provider="jellyfin",
            item_id="movie-1",
            media_type="movie",
            title="Example Movie",
        )

        with patch.object(
            JellyfinProvider,
            "get_item",
            return_value=item,
        ) as get_item:
            result = provider.preview_delete_item(
                " movie-1 "
            )

        self.assertIsInstance(
            result,
            ProviderMutationResult,
        )
        self.assertEqual(result.provider, "jellyfin")
        self.assertEqual(result.item_id, "movie-1")
        self.assertIs(
            result.operation,
            ProviderOperation.DELETE,
        )
        self.assertTrue(result.success)
        self.assertEqual(
            result.message,
            "Preview verified",
        )
        self.assertEqual(
            result.executed_at,
            "2026-07-20T12:00:00Z",
        )

        get_item.assert_called_once_with("movie-1")

    def test_preview_delete_item_normalizes_missing_item(
        self,
    ) -> None:
        provider = make_provider()

        error = HTTPError(
            url="http://jellyfin.test/Items/missing-1",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

        with patch(
            "atlas.media.jellyfin.urlopen",
            side_effect=error,
        ):
            result = provider.preview_delete_item(
                "missing-1"
            )

        self.assertFalse(result.success)
        self.assertEqual(result.item_id, "missing-1")
        self.assertEqual(
            result.message,
            "Item not found",
        )
        self.assertIs(
            result.operation,
            ProviderOperation.DELETE,
        )

    def test_preview_delete_item_preserves_provider_failures(
        self,
    ) -> None:
        provider = make_provider()

        with patch.object(
            JellyfinProvider,
            "get_item",
            side_effect=MediaProviderError(
                "Jellyfin is unreachable"
            ),
        ):
            with self.assertRaisesRegex(
                MediaProviderError,
                "Jellyfin is unreachable",
            ):
                provider.preview_delete_item(
                    "movie-1"
                )

    def test_preview_delete_item_normalizes_clock_to_utc(
        self,
    ) -> None:
        eastern = timezone(timedelta(hours=-4))

        provider = make_provider(
            clock=lambda: datetime(
                2026,
                7,
                20,
                8,
                0,
                tzinfo=eastern,
            )
        )

        item = MediaItem(
            provider="jellyfin",
            item_id="movie-1",
            media_type="movie",
            title="Example Movie",
        )

        with patch.object(
            JellyfinProvider,
            "get_item",
            return_value=item,
        ):
            result = provider.preview_delete_item(
                "movie-1"
            )

        self.assertEqual(
            result.executed_at,
            "2026-07-20T12:00:00Z",
        )

    def test_preview_delete_item_rejects_invalid_clock(
        self,
    ) -> None:
        provider = make_provider(
            clock=lambda: "2026-07-20T12:00:00Z"
        )

        item = MediaItem(
            provider="jellyfin",
            item_id="movie-1",
            media_type="movie",
            title="Example Movie",
        )

        with patch.object(
            JellyfinProvider,
            "get_item",
            return_value=item,
        ):
            with self.assertRaisesRegex(
                MediaProviderError,
                "clock must return a datetime",
            ):
                provider.preview_delete_item(
                    "movie-1"
                )

    def test_preview_delete_item_rejects_naive_clock(
        self,
    ) -> None:
        provider = make_provider(
            clock=lambda: datetime(
                2026,
                7,
                20,
                12,
                0,
            )
        )

        item = MediaItem(
            provider="jellyfin",
            item_id="movie-1",
            media_type="movie",
            title="Example Movie",
        )

        with patch.object(
            JellyfinProvider,
            "get_item",
            return_value=item,
        ):
            with self.assertRaisesRegex(
                MediaProviderError,
                "timezone-aware datetime",
            ):
                provider.preview_delete_item(
                    "movie-1"
                )


if __name__ == "__main__":
    unittest.main()
