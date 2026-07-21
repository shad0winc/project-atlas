"""Tests for provider-neutral media mutation dispatch."""

from __future__ import annotations

import unittest

from atlas.media import (
    MediaMutationDispatcher,
    MediaMutationDispatchError,
    ProviderCapabilities,
    ProviderCapability,
    ProviderMutationResult,
    ProviderOperation,
)


EXECUTED_AT = "2026-07-21T20:00:00Z"


def make_capabilities(
    *,
    provider: str = "jellyfin",
    preview_delete: bool = True,
) -> ProviderCapabilities:
    capabilities = (
        frozenset(
            {
                ProviderCapability.PREVIEW_DELETE,
            }
        )
        if preview_delete
        else frozenset()
    )

    return ProviderCapabilities(
        provider=provider,
        capabilities=capabilities,
        supports_batch_listing=False,
        supports_batch_preview=False,
        max_batch_size=None,
    )


def make_result(
    *,
    provider: str = "jellyfin",
    item_id: str = "movie-1",
    operation: ProviderOperation = ProviderOperation.DELETE,
) -> ProviderMutationResult:
    return ProviderMutationResult(
        provider=provider,
        operation=operation,
        item_id=item_id,
        success=True,
        message="Delete preview succeeded",
        executed_at=EXECUTED_AT,
    )


class RecordingPreviewProvider:
    """Minimal provider double for mutation dispatch tests."""

    name = "jellyfin"

    def __init__(
        self,
        *,
        capabilities: ProviderCapabilities | None = None,
        result: object | None = None,
    ) -> None:
        self._capabilities = (
            capabilities
            if capabilities is not None
            else make_capabilities()
        )
        self._result = (
            result
            if result is not None
            else make_result()
        )
        self.requests: list[str] = []

    def get_capabilities(
        self,
    ) -> ProviderCapabilities:
        return self._capabilities

    def preview_delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        self.requests.append(item_id)
        return self._result  # type: ignore[return-value]


class MediaMutationDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dispatcher = MediaMutationDispatcher()

    def test_dispatches_delete_preview(
        self,
    ) -> None:
        provider = RecordingPreviewProvider()

        result = self.dispatcher.execute(
            provider=provider,
            operation=ProviderOperation.DELETE,
            item_id=" movie-1 ",
            preview=True,
        )

        self.assertEqual(
            provider.requests,
            ["movie-1"],
        )
        self.assertEqual(
            result,
            make_result(),
        )

    def test_accepts_string_operation(
        self,
    ) -> None:
        provider = RecordingPreviewProvider()

        result = self.dispatcher.execute(
            provider=provider,
            operation="delete",
            item_id="movie-1",
        )

        self.assertIs(
            result.operation,
            ProviderOperation.DELETE,
        )

    def test_rejects_real_mutations(
        self,
    ) -> None:
        provider = RecordingPreviewProvider()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "real provider mutations are not enabled",
        ):
            self.dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
                preview=False,
            )

        self.assertEqual(
            provider.requests,
            [],
        )

    def test_rejects_missing_preview_capability(
        self,
    ) -> None:
        provider = RecordingPreviewProvider(
            capabilities=make_capabilities(
                preview_delete=False,
            ),
        )

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "jellyfin does not support delete previews",
        ):
            self.dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
            )

        self.assertEqual(
            provider.requests,
            [],
        )

    def test_rejects_declared_preview_without_method(
        self,
    ) -> None:
        class MissingPreviewProvider:
            name = "jellyfin"

            def get_capabilities(
                self,
            ) -> ProviderCapabilities:
                return make_capabilities()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "declares delete preview support "
            "but does not implement preview_delete_item",
        ):
            self.dispatcher.execute(
                provider=MissingPreviewProvider(),
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
            )

    def test_rejects_missing_capability_method(
        self,
    ) -> None:
        class MissingCapabilitiesProvider:
            name = "jellyfin"

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                raise AssertionError(
                    "preview must not be called"
                )

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "provider must implement get_capabilities",
        ):
            self.dispatcher.execute(
                provider=MissingCapabilitiesProvider(),
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
            )

    def test_rejects_invalid_capability_contract(
        self,
    ) -> None:
        class InvalidCapabilitiesProvider:
            name = "jellyfin"

            def get_capabilities(self):
                return object()

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                raise AssertionError(
                    "preview must not be called"
                )

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "provider must return ProviderCapabilities",
        ):
            self.dispatcher.execute(
                provider=InvalidCapabilitiesProvider(),
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
            )

    def test_rejects_capability_provider_mismatch(
        self,
    ) -> None:
        provider = RecordingPreviewProvider(
            capabilities=make_capabilities(
                provider="emby",
            ),
        )

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "provider capabilities do not match provider name",
        ):
            self.dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
            )

    def test_rejects_invalid_result_type(
        self,
    ) -> None:
        provider = RecordingPreviewProvider(
            result=object(),
        )

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "provider mutation must return "
            "ProviderMutationResult",
        ):
            self.dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
            )

    def test_rejects_result_provider_mismatch(
        self,
    ) -> None:
        provider = RecordingPreviewProvider(
            result=make_result(
                provider="emby",
            ),
        )

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "result provider does not match provider",
        ):
            self.dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
            )

    def test_rejects_result_item_mismatch(
        self,
    ) -> None:
        provider = RecordingPreviewProvider(
            result=make_result(
                item_id="movie-2",
            ),
        )

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "result item_id does not match request",
        ):
            self.dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
            )

    def test_rejects_invalid_operation(
        self,
    ) -> None:
        provider = RecordingPreviewProvider()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "invalid provider operation",
        ):
            self.dispatcher.execute(
                provider=provider,
                operation="restore",
                item_id="movie-1",
            )

        self.assertEqual(
            provider.requests,
            [],
        )

    def test_rejects_invalid_preview_flag(
        self,
    ) -> None:
        provider = RecordingPreviewProvider()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "preview must be a boolean",
        ):
            self.dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id="movie-1",
                preview=1,  # type: ignore[arg-type]
            )

    def test_rejects_empty_item_id(
        self,
    ) -> None:
        provider = RecordingPreviewProvider()

        with self.assertRaisesRegex(
            MediaMutationDispatchError,
            "item_id is required",
        ):
            self.dispatcher.execute(
                provider=provider,
                operation=ProviderOperation.DELETE,
                item_id=" ",
            )


if __name__ == "__main__":
    unittest.main()
