"""Provider-neutral media mutation dispatch for Project Atlas."""

from __future__ import annotations

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


class MediaMutationDispatcher:
    """Dispatch validated media mutations to provider implementations.

    The initial dispatcher supports safe delete previews only. Real provider
    mutations remain disabled until Atlas introduces an explicitly controlled
    execution mode.
    """

    def validate(
        self,
        *,
        provider: MediaProvider,
        operation: ProviderOperation | str,
        preview: bool = True,
    ) -> None:
        """Validate that a provider can perform a mutation."""

        normalized_operation = self._operation(operation)

        if not isinstance(preview, bool):
            raise MediaMutationDispatchError(
                "preview must be a boolean"
            )

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
            preview=preview,
        )

    def execute(
        self,
        *,
        provider: MediaProvider,
        operation: ProviderOperation | str,
        item_id: str,
        preview: bool = True,
    ) -> ProviderMutationResult:
        """Dispatch one normalized provider mutation."""

        normalized_operation = self._operation(operation)
        normalized_item_id = self._required_text(
            item_id,
            "item_id",
        )

        if not isinstance(preview, bool):
            raise MediaMutationDispatchError(
                "preview must be a boolean"
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
            preview=preview,
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
        preview: bool,
    ):
        """Return the provider method for a supported mutation."""

        if (
            operation is ProviderOperation.DELETE
            and preview
        ):
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

        if not preview:
            raise MediaMutationDispatchError(
                "real provider mutations are not enabled"
            )

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
