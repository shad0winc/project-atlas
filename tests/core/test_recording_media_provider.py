"""Tests for the safe recording media provider."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from atlas.media import (
    MediaItem,
    MediaProviderError,
    ProviderOperation,
    RecordingMediaProvider,
)
from atlas.media.capabilities import (
    ProviderCapability,
)


FIXED_TIME = datetime(
    2026,
    7,
    20,
    18,
    30,
    tzinfo=timezone.utc,
)


def _item(
    *,
    provider: str = "jellyfin",
    item_id: str = "movie-123",
) -> MediaItem:
    return MediaItem(
        provider=provider,
        item_id=item_id,
        media_type="movie",
        title="Example Movie",
    )


class RecordingMediaProviderTests(unittest.TestCase):
    def test_provider_name_is_normalized(self) -> None:
        provider = RecordingMediaProvider(
            "  Jellyfin  ",
        )

        self.assertEqual(provider.name, "jellyfin")

    def test_capabilities_match_safe_provider_behavior(self) -> None:
        provider = RecordingMediaProvider(
            "  Jellyfin  ",
        )

        capabilities = provider.get_capabilities()

        self.assertEqual(
            capabilities.provider,
            "jellyfin",
        )
        self.assertEqual(
            capabilities.capabilities,
            frozenset(
                {
                    ProviderCapability.LIST_MEDIA,
                    ProviderCapability.PREVIEW_DELETE,
                }
            ),
        )
        self.assertFalse(
            capabilities.supports_batch_listing
        )
        self.assertFalse(
            capabilities.supports_batch_preview
        )
        self.assertIsNone(
            capabilities.max_batch_size
        )
        self.assertFalse(
            capabilities.supports(
                ProviderCapability.DELETE
            )
        )

    def test_list_media_item_ids_returns_seeded_ids(self) -> None:
        first = _item(item_id="movie-1")
        second = _item(item_id="movie-2")

        provider = RecordingMediaProvider(
            "jellyfin",
            items={
                first.item_id: first,
                second.item_id: second,
            },
        )

        self.assertEqual(
            provider.list_media_item_ids(),
            (
                "movie-1",
                "movie-2",
            ),
        )

    def test_list_media_item_ids_accepts_page_size(self) -> None:
        item = _item()

        provider = RecordingMediaProvider(
            "jellyfin",
            items={item.item_id: item},
        )

        self.assertEqual(
            provider.list_media_item_ids(
                page_size=1,
            ),
            ("movie-123",),
        )

    def test_list_media_item_ids_validates_page_size(
        self,
    ) -> None:
        provider = RecordingMediaProvider(
            "jellyfin",
        )

        for page_size in (
            0,
            -1,
            True,
            1.5,
            "200",
            None,
        ):
            with self.subTest(page_size=page_size):
                with self.assertRaisesRegex(
                    MediaProviderError,
                    "page_size must be a positive integer",
                ):
                    provider.list_media_item_ids(
                        page_size=page_size,  # type: ignore[arg-type]
                    )

    def test_get_item_returns_seeded_item(self) -> None:
        item = _item()
        provider = RecordingMediaProvider(
            "jellyfin",
            items={item.item_id: item},
        )

        self.assertIs(
            provider.get_item("movie-123"),
            item,
        )

    def test_get_item_rejects_unknown_item(self) -> None:
        provider = RecordingMediaProvider(
            "jellyfin",
        )

        with self.assertRaisesRegex(
            MediaProviderError,
            "media item not found",
        ):
            provider.get_item("missing")

    def test_seeded_item_provider_must_match(self) -> None:
        item = _item(provider="plex")

        with self.assertRaisesRegex(
            MediaProviderError,
            "provider does not match",
        ):
            RecordingMediaProvider(
                "jellyfin",
                items={item.item_id: item},
            )

    def test_seeded_item_id_must_match_mapping_key(self) -> None:
        item = _item(item_id="movie-123")

        with self.assertRaisesRegex(
            MediaProviderError,
            "ID does not match",
        ):
            RecordingMediaProvider(
                "jellyfin",
                items={"different-id": item},
            )

    def test_preview_delete_item_records_safe_result(self) -> None:
        provider = RecordingMediaProvider(
            "jellyfin",
            clock=lambda: FIXED_TIME,
        )

        result = provider.preview_delete_item(
            "  movie-123  ",
        )

        self.assertEqual(result.provider, "jellyfin")
        self.assertIs(
            result.operation,
            ProviderOperation.DELETE,
        )
        self.assertEqual(result.item_id, "movie-123")
        self.assertTrue(result.success)
        self.assertEqual(
            result.executed_at,
            "2026-07-20T18:30:00Z",
        )
        self.assertIn(
            "no media was modified",
            result.message,
        )
        self.assertEqual(
            provider.requests,
            (result,),
        )

    def test_delete_previews_preserve_execution_order(self) -> None:
        provider = RecordingMediaProvider(
            "jellyfin",
            clock=lambda: FIXED_TIME,
        )

        first = provider.preview_delete_item("movie-1")
        second = provider.preview_delete_item("movie-2")

        self.assertEqual(
            provider.requests,
            (
                first,
                second,
            ),
        )

    def test_requests_returns_immutable_snapshot(self) -> None:
        provider = RecordingMediaProvider(
            "jellyfin",
            clock=lambda: FIXED_TIME,
        )

        provider.preview_delete_item("movie-123")
        requests = provider.requests

        self.assertIsInstance(requests, tuple)

        with self.assertRaises(AttributeError):
            requests.append("invalid")  # type: ignore[attr-defined]

    def test_provider_name_is_required(self) -> None:
        for name in ("", "   ", None):
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    MediaProviderError,
                    "provider name is required",
                ):
                    RecordingMediaProvider(
                        name,  # type: ignore[arg-type]
                    )

    def test_clock_must_return_datetime(self) -> None:
        provider = RecordingMediaProvider(
            "jellyfin",
            clock=lambda: "invalid",  # type: ignore[return-value]
        )

        with self.assertRaisesRegex(
            MediaProviderError,
            "clock must return a datetime",
        ):
            provider.preview_delete_item("movie-123")

    def test_clock_must_return_timezone_aware_datetime(self) -> None:
        provider = RecordingMediaProvider(
            "jellyfin",
            clock=lambda: datetime(
                2026,
                7,
                20,
                18,
                30,
            ),
        )

        with self.assertRaisesRegex(
            MediaProviderError,
            "timezone-aware datetime",
        ):
            provider.preview_delete_item("movie-123")


if __name__ == "__main__":
    unittest.main()
