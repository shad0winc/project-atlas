"""Tests for provider-layer media mutation modes."""

from __future__ import annotations

import unittest

from atlas.media.capabilities import (
    ProviderCapabilities,
    ProviderCapability,
)
from atlas.media.mutations import (
    MediaMutationDispatcher,
    MediaMutationDispatchError,
    MediaMutationMode,
)
from atlas.media.provider import (
    ProviderMutationResult,
    ProviderOperation,
)


class ModeProvider:
    """Provider recording whether its preview method was invoked."""

    name = "mode-provider"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=self.name,
            capabilities=frozenset(
                {
                    ProviderCapability.PREVIEW_DELETE,
                }
            ),
            supports_batch_preview=False,
        )

    def preview_delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        self.calls.append(item_id)

        return ProviderMutationResult(
            provider=self.name,
            operation=ProviderOperation.DELETE,
            item_id=item_id,
            success=True,
            message="Preview succeeded",
            executed_at="2026-07-21T20:00:00Z",
        )


class MediaMutationModeTests(unittest.TestCase):
    """Tests for normalized mutation-mode dispatch."""

    def test_preview_mode_dispatches_preview_method(self) -> None:
        provider = ModeProvider()
        dispatcher = MediaMutationDispatcher()

        result = dispatcher.execute(
            provider=provider,
            operation=ProviderOperation.DELETE,
            item_id="movie-1",
            mode=MediaMutationMode.PREVIEW,
        )

        self.assertTrue(result.success)
        self.assertEqual(provider.calls, ["movie-1"])

    def test_preview_string_is_accepted(self) -> None:
        provider = ModeProvider()
        dispatcher = MediaMutationDispatcher()

        dispatcher.validate(
            provider=provider,
            operation=ProviderOperation.DELETE,
            mode="preview",
        )

        self.assertEqual(provider.calls, [])

    def test_live_mode_is_rejected_during_validation(self) -> None:
        provider = ModeProvider()
        dispatcher = MediaMutationDispatcher()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "live provider mutations are not enabled",
        ):
            dispatcher.validate(
                provider=provider,
                operation=ProviderOperation.DELETE,
                mode=MediaMutationMode.LIVE,
            )

        self.assertEqual(provider.calls, [])

    def test_live_mode_is_rejected_without_execution(self) -> None:
        provider = ModeProvider()
        dispatcher = MediaMutationDispatcher()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "live provider mutations are not enabled",
        ):
            dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
                mode=MediaMutationMode.LIVE,
            )

        self.assertEqual(provider.calls, [])

    def test_invalid_mode_is_rejected(self) -> None:
        provider = ModeProvider()
        dispatcher = MediaMutationDispatcher()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "invalid media mutation mode",
        ):
            dispatcher.validate(
                provider=provider,
                operation=ProviderOperation.DELETE,
                mode="invalid",
            )


if __name__ == "__main__":
    unittest.main()
