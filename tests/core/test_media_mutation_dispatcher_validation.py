"""Tests for media mutation dispatcher preflight validation."""

from __future__ import annotations

import unittest

from atlas.media import (
    MediaMutationDispatcher,
    MediaMutationDispatchError,
    MediaMutationMode,
    ProviderCapabilities,
    ProviderCapability,
    ProviderMutationResult,
    ProviderOperation,
)


class PreviewProvider:
    """Provider double with safe delete-preview support."""

    name = "jellyfin"

    def __init__(self) -> None:
        self.requests: list[str] = []

    def get_capabilities(
        self,
    ) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider="jellyfin",
            capabilities=frozenset(
                {
                    ProviderCapability.PREVIEW_DELETE,
                }
            ),
        )

    def preview_delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        self.requests.append(item_id)

        return ProviderMutationResult(
            provider="jellyfin",
            operation=ProviderOperation.DELETE,
            item_id=item_id,
            success=True,
            message="Delete preview succeeded",
            executed_at="2026-07-21T20:00:00Z",
        )


class MediaMutationDispatcherValidationTests(
    unittest.TestCase
):
    def test_validation_does_not_execute_provider_method(
        self,
    ) -> None:
        provider = PreviewProvider()
        dispatcher = MediaMutationDispatcher()

        dispatcher.validate(
            provider=provider,
            operation=ProviderOperation.DELETE,
            mode=MediaMutationMode.PREVIEW,
        )

        self.assertEqual(
            provider.requests,
            [],
        )

    def test_validation_accepts_string_operation(
        self,
    ) -> None:
        dispatcher = MediaMutationDispatcher()

        dispatcher.validate(
            provider=PreviewProvider(),
            operation="delete",
            mode=MediaMutationMode.PREVIEW,
        )

    def test_validation_rejects_live_mutations(
        self,
    ) -> None:
        dispatcher = MediaMutationDispatcher()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "live provider mutations are not enabled",
        ):
            dispatcher.validate(
                provider=PreviewProvider(),
                operation=ProviderOperation.DELETE,
                mode=MediaMutationMode.LIVE,
            )

    def test_unsuccessful_result_is_rejected(
        self,
    ) -> None:
        class FailedPreviewProvider(PreviewProvider):
            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                return ProviderMutationResult(
                    provider="jellyfin",
                    operation=ProviderOperation.DELETE,
                    item_id=item_id,
                    success=False,
                    message="Provider rejected preview",
                    executed_at="2026-07-21T20:00:00Z",
                )

        dispatcher = MediaMutationDispatcher()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "Provider rejected preview",
        ):
            dispatcher.execute(
                provider=FailedPreviewProvider(),
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
                mode=MediaMutationMode.PREVIEW,
            )


if __name__ == "__main__":
    unittest.main()
