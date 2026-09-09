"""Tests for the Atlas live-delete provider foundation."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from atlas.media.capabilities import (
    ProviderCapabilities,
    ProviderCapability,
)
from atlas.media.jellyfin import JellyfinProvider
from atlas.media.mutations import (
    MediaMutationDispatcher,
    MediaMutationDispatchError,
    MediaMutationMode,
)
from atlas.media.provider import (
    ProviderMutationResult,
    ProviderOperation,
)


EXECUTED_AT = "2026-09-09T20:00:00Z"


class LiveDeleteProvider:
    """Provider exposing one controlled live-delete method."""

    name = "live-delete-provider"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=self.name,
            capabilities=frozenset(
                {
                    ProviderCapability.DELETE,
                }
            ),
        )

    def delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        self.calls.append(item_id)

        return ProviderMutationResult(
            provider=self.name,
            operation=ProviderOperation.DELETE,
            item_id=item_id,
            success=True,
            message="Deleted",
            executed_at=EXECUTED_AT,
        )


class MissingDeleteCapabilityProvider(LiveDeleteProvider):
    """Provider implementing delete without declaring capability."""

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=self.name,
            capabilities=frozenset(),
        )


class DeclaredDeleteWithoutMethodProvider:
    """Provider declaring DELETE without implementing delete_item."""

    name = "declared-delete-provider"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=self.name,
            capabilities=frozenset(
                {
                    ProviderCapability.DELETE,
                }
            ),
        )


class MismatchedDeleteResultProvider(LiveDeleteProvider):
    """Provider returning the wrong item identity."""

    def delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        self.calls.append(item_id)

        return ProviderMutationResult(
            provider=self.name,
            operation=ProviderOperation.DELETE,
            item_id="different-item",
            success=True,
            message="Deleted",
            executed_at=EXECUTED_AT,
        )


class MediaMutationLiveDeleteTests(unittest.TestCase):
    """Validate provider-neutral live-delete dispatch."""

    def test_live_delete_validation_succeeds(self) -> None:
        provider = LiveDeleteProvider()
        dispatcher = MediaMutationDispatcher()

        dispatcher.validate(
            provider=provider,
            operation=ProviderOperation.DELETE,
            mode=MediaMutationMode.LIVE,
        )

        self.assertEqual(provider.calls, [])

    def test_live_delete_executes_exactly_once(self) -> None:
        provider = LiveDeleteProvider()
        dispatcher = MediaMutationDispatcher()

        result = dispatcher.execute(
            provider=provider,
            operation=ProviderOperation.DELETE,
            item_id="movie-1",
            mode=MediaMutationMode.LIVE,
        )

        self.assertTrue(result.success)
        self.assertEqual(provider.calls, ["movie-1"])
        self.assertEqual(result.item_id, "movie-1")

    def test_live_delete_requires_delete_capability(self) -> None:
        provider = MissingDeleteCapabilityProvider()
        dispatcher = MediaMutationDispatcher()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "does not support live delete",
        ):
            dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
                mode=MediaMutationMode.LIVE,
            )

        self.assertEqual(provider.calls, [])

    def test_live_delete_requires_delete_method(self) -> None:
        provider = DeclaredDeleteWithoutMethodProvider()
        dispatcher = MediaMutationDispatcher()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "does not implement delete_item",
        ):
            dispatcher.validate(
                provider=provider,
                operation=ProviderOperation.DELETE,
                mode=MediaMutationMode.LIVE,
            )

    def test_live_delete_preserves_result_identity_validation(
        self,
    ) -> None:
        provider = MismatchedDeleteResultProvider()
        dispatcher = MediaMutationDispatcher()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "item_id does not match request",
        ):
            dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
                mode=MediaMutationMode.LIVE,
            )

        self.assertEqual(provider.calls, ["movie-1"])


class JellyfinLiveDeleteTests(unittest.TestCase):
    """Validate Jellyfin's provider-level delete implementation."""

    def _provider(self) -> JellyfinProvider:
        return JellyfinProvider(
            "http://jellyfin.test",
            "test-api-key",
        )

    def test_jellyfin_advertises_delete_capability(self) -> None:
        provider = self._provider()
        capabilities = provider.get_capabilities()

        self.assertTrue(
            capabilities.supports(
                ProviderCapability.DELETE,
            )
        )
        self.assertTrue(
            capabilities.supports(
                ProviderCapability.PREVIEW_DELETE,
            )
        )

    def test_jellyfin_delete_verifies_then_uses_delete_request(
        self,
    ) -> None:
        provider = self._provider()

        with (
            patch.object(
                JellyfinProvider,
                "get_item",
                return_value=object(),
            ) as get_item,
            patch.object(
                JellyfinProvider,
                "_request_json",
                return_value=None,
            ) as request_json,
        ):
            result = provider.delete_item("movie 1")

        get_item.assert_called_once_with("movie 1")
        request_json.assert_called_once_with(
            "/Items/movie%201",
            method="DELETE",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.provider, "jellyfin")
        self.assertIs(
            result.operation,
            ProviderOperation.DELETE,
        )
        self.assertEqual(result.item_id, "movie 1")
        self.assertEqual(result.message, "Deleted")

    def test_preview_method_remains_available(self) -> None:
        provider = self._provider()

        self.assertTrue(
            callable(provider.preview_delete_item)
        )


if __name__ == "__main__":
    unittest.main()
