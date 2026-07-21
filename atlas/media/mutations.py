"""Provider-neutral media mutation dispatch for Project Atlas."""

from __future__ import annotations

from enum import Enum

from atlas.media.capabilities import (
    ProviderCapabilities,
    ProviderCapability,
)
from atlas.media.provider import (
    MediaProvider,
    ProviderMutationResult,
    ProviderOperation,
)


class MediaMutationDispatchError(RuntimeError):
    """Raised when a media mutation cannot be dispatched safely."""


class MediaMutationMode(str, Enum):
    """Provider-layer media mutation modes."""

    PREVIEW = "preview"
    LIVE = "live"


class MediaMutationDispatcher:
    """Dispatch validated media mutations to provider implementations.

    Preview mutations may be dispatched to provider preview methods. Live
    provider mutations remain disabled until Atlas introduces all required
    authorization and safety gates.
    """

    def validate(
        self,
        *,
        provider: MediaProvider,
        operation: ProviderOperation | str,
        mode: MediaMutationMode | str = MediaMutationMode.PREVIEW,
    ) -> None:
        """Validate that a provider can perform a mutation."""

        normalized_operation = self._operation(operation)
        normalized_mode = self._mode(mode)

        provider_name = self._provider_name(provider)
        capabilities = self._provider_capabilities(provider)

        if capabilities.provider != provider_name:
            raise MediaMutationDispatchError(
                "provider capabilities do not match provider name"
            )

        self._resolve_method(
            provider=provider,
            provider_name=provider_name,
            capabilities=capabilities,
            operation=normalized_operation,
            mode=normalized_mode,
        )

    def execute(
        self,
        *,
        provider: MediaProvider,
        operation: ProviderOperation | str,
        item_id: str,
        mode: MediaMutationMode | str = MediaMutationMode.PREVIEW,
    ) -> ProviderMutationResult:
        """Dispatch one normalized provider mutation."""

        normalized_operation = self._operation(operation)
        normalized_mode = self._mode(mode)
        normalized_item_id = self._required_text(
            item_id,
            "item_id",
        )

        provider_name = self._provider_name(provider)
        capabilities = self._provider_capabilities(provider)

        if capabilities.provider != provider_name:
            raise MediaMutationDispatchError(
                "provider capabilities do not match provider name"
            )

        mutation_method = self._resolve_method(
            provider=provider,
            provider_name=provider_name,
            capabilities=capabilities,
            operation=normalized_operation,
            mode=normalized_mode,
        )

        result = mutation_method(normalized_item_id)

        self._validate_result(
            result=result,
            provider_name=provider_name,
            operation=normalized_operation,
            item_id=normalized_item_id,
        )

        return result

    @staticmethod
    def _resolve_method(
        *,
        provider: MediaProvider,
        provider_name: str,
        capabilities: ProviderCapabilities,
        operation: ProviderOperation,
        mode: MediaMutationMode,
    ):
        """Return the provider method for a supported mutation."""

        if mode is MediaMutationMode.LIVE:
            raise MediaMutationDispatchError(
                "live provider mutations are not enabled"
            )

        if operation is ProviderOperation.DELETE:
            if not capabilities.supports(
                ProviderCapability.PREVIEW_DELETE,
            ):
                raise MediaMutationDispatchError(
                    f"{provider_name} does not support delete previews"
                )

            preview_delete_item = getattr(
                provider,
                "preview_delete_item",
                None,
            )

            if not callable(preview_delete_item):
                raise MediaMutationDispatchError(
                    "provider declares delete preview support "
                    "but does not implement preview_delete_item"
                )

            return preview_delete_item

        raise MediaMutationDispatchError(
            "unsupported provider mutation: "
            f"{operation.value}"
        )

    @staticmethod
    def _validate_result(
        *,
        result: ProviderMutationResult,
        provider_name: str,
        operation: ProviderOperation,
        item_id: str,
    ) -> None:
        """Validate a provider mutation result."""

        if not isinstance(result, ProviderMutationResult):
            raise MediaMutationDispatchError(
                "provider mutation must return "
                "ProviderMutationResult"
            )

        if result.provider != provider_name:
            raise MediaMutationDispatchError(
                "provider mutation result provider does not "
                "match provider"
            )

        if result.item_id != item_id:
            raise MediaMutationDispatchError(
                "provider mutation result item_id does not "
                "match request"
            )

        if result.operation is not operation:
            raise MediaMutationDispatchError(
                "provider mutation result operation does not "
                "match request"
            )

        if not result.success:
            raise MediaMutationDispatchError(
                result.message
            )

    @staticmethod
    def _provider_name(
        provider: MediaProvider,
    ) -> str:
        """Return the provider's normalized name."""

        name = getattr(
            provider,
            "name",
            None,
        )

        return MediaMutationDispatcher._required_text(
            name,
            "provider name",
        ).lower()

    @staticmethod
    def _provider_capabilities(
        provider: MediaProvider,
    ) -> ProviderCapabilities:
        """Return and validate provider capabilities."""

        get_capabilities = getattr(
            provider,
            "get_capabilities",
            None,
        )

        if not callable(get_capabilities):
            raise MediaMutationDispatchError(
                "provider must implement get_capabilities"
            )

        capabilities = get_capabilities()

        if not isinstance(
            capabilities,
            ProviderCapabilities,
        ):
            raise MediaMutationDispatchError(
                "provider must return ProviderCapabilities"
            )

        return capabilities

    @staticmethod
    def _operation(
        operation: ProviderOperation | str,
    ) -> ProviderOperation:
        """Return a normalized provider operation."""

        try:
            return (
                operation
                if isinstance(operation, ProviderOperation)
                else ProviderOperation(operation)
            )
        except (TypeError, ValueError) as exc:
            raise MediaMutationDispatchError(
                f"invalid provider operation: {operation}"
            ) from exc

    @staticmethod
    def _mode(
        mode: MediaMutationMode | str,
    ) -> MediaMutationMode:
        """Return a normalized media mutation mode."""

        try:
            return (
                mode
                if isinstance(mode, MediaMutationMode)
                else MediaMutationMode(mode)
            )
        except (TypeError, ValueError) as exc:
            raise MediaMutationDispatchError(
                f"invalid media mutation mode: {mode}"
            ) from exc

    @staticmethod
    def _required_text(
        value: object,
        field_name: str,
    ) -> str:
        """Return a stripped, non-empty string."""

        if not isinstance(value, str) or not value.strip():
            raise MediaMutationDispatchError(
                f"{field_name} is required"
            )

        return value.strip()
