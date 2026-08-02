"""Provider-agnostic media-request orchestration for Project Atlas."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
import re

from .models import (
    MediaRequest,
    MediaRequestStatus,
)
from .provider import (
    MediaRequestProvider,
    MediaRequestProviderError,
    MediaRequestProviderOperationError,
    ProviderStatusResult,
    ProviderSubmissionResult,
)
from .repository import (
    JsonMediaRequestRepository,
    MediaRequestRepositoryError,
)


_PROVIDER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)

_ALLOWED_TRANSITIONS: dict[
    MediaRequestStatus,
    frozenset[MediaRequestStatus],
] = {
    MediaRequestStatus.PENDING: frozenset(
        {
            MediaRequestStatus.PENDING,
            MediaRequestStatus.APPROVED,
            MediaRequestStatus.SEARCHING,
            MediaRequestStatus.DOWNLOADING,
            MediaRequestStatus.IMPORTING,
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.REJECTED,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }
    ),
    MediaRequestStatus.APPROVED: frozenset(
        {
            MediaRequestStatus.APPROVED,
            MediaRequestStatus.SEARCHING,
            MediaRequestStatus.DOWNLOADING,
            MediaRequestStatus.IMPORTING,
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.REJECTED,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }
    ),
    MediaRequestStatus.SEARCHING: frozenset(
        {
            MediaRequestStatus.SEARCHING,
            MediaRequestStatus.DOWNLOADING,
            MediaRequestStatus.IMPORTING,
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }
    ),
    MediaRequestStatus.DOWNLOADING: frozenset(
        {
            MediaRequestStatus.DOWNLOADING,
            MediaRequestStatus.IMPORTING,
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }
    ),
    MediaRequestStatus.IMPORTING: frozenset(
        {
            MediaRequestStatus.IMPORTING,
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }
    ),
    MediaRequestStatus.AVAILABLE: frozenset(
        {
            MediaRequestStatus.AVAILABLE,
        }
    ),
    MediaRequestStatus.REJECTED: frozenset(
        {
            MediaRequestStatus.REJECTED,
        }
    ),
    MediaRequestStatus.FAILED: frozenset(
        {
            MediaRequestStatus.FAILED,
        }
    ),
    MediaRequestStatus.CANCELLED: frozenset(
        {
            MediaRequestStatus.CANCELLED,
        }
    ),
}


class MediaRequestServiceError(RuntimeError):
    """Raised when media-request orchestration cannot complete safely."""


class MediaRequestService:
    """Coordinate media-request models, persistence, and providers."""

    def __init__(
        self,
        repository: JsonMediaRequestRepository,
        providers: Iterable[MediaRequestProvider],
    ) -> None:
        if not isinstance(repository, JsonMediaRequestRepository):
            raise MediaRequestServiceError(
                "repository must be a JsonMediaRequestRepository",
            )

        provider_map: dict[str, MediaRequestProvider] = {}

        try:
            provider_values = tuple(providers)
        except TypeError as exc:
            raise MediaRequestServiceError(
                "providers must be an iterable of MediaRequestProvider objects",
            ) from exc

        if not provider_values:
            raise MediaRequestServiceError(
                "at least one media-request provider is required",
            )

        for index, provider in enumerate(provider_values):
            if not isinstance(provider, MediaRequestProvider):
                raise MediaRequestServiceError(
                    f"providers[{index}] must be a MediaRequestProvider",
                )

            name = _normalize_provider_name(provider.name)

            if name in provider_map:
                raise MediaRequestServiceError(
                    f"duplicate media-request provider: {name}",
                )

            provider_map[name] = provider

        self.repository = repository
        self._providers = provider_map

    @property
    def provider_names(self) -> tuple[str, ...]:
        """Return registered provider names in deterministic order."""

        return tuple(sorted(self._providers))

    def create_request(self, request: MediaRequest) -> MediaRequest:
        """Validate and persist a new unsubmitted Atlas request."""

        if not isinstance(request, MediaRequest):
            raise MediaRequestServiceError(
                "request must be a MediaRequest",
            )

        if request.status is not MediaRequestStatus.PENDING:
            raise MediaRequestServiceError(
                "new media requests must have pending status",
            )

        if request.provider_request_id is not None:
            raise MediaRequestServiceError(
                "new media requests must not have provider_request_id",
            )

        provider = self._provider_for(request.provider)
        capabilities = self._capabilities(provider)

        if not capabilities.supports_submission:
            raise MediaRequestServiceError(
                f"provider does not support submission: {request.provider}",
            )

        if not capabilities.supports(request.media_type):
            raise MediaRequestServiceError(
                "provider does not support media type: "
                f"{request.provider}:{request.media_type.value}",
            )

        try:
            return self.repository.save(request)
        except MediaRequestRepositoryError as exc:
            raise MediaRequestServiceError(
                f"unable to persist media request: {request.request_id}",
            ) from exc

    def submit_request(self, request_id: object) -> MediaRequest:
        """Submit one persisted request to its configured provider."""

        request = self.get_request(request_id)

        if request.provider_request_id is not None:
            raise MediaRequestServiceError(
                f"media request is already submitted: {request.request_id}",
            )

        if request.status is not MediaRequestStatus.PENDING:
            raise MediaRequestServiceError(
                "only pending media requests may be submitted",
            )

        provider = self._provider_for(request.provider)
        capabilities = self._capabilities(provider)

        if not capabilities.supports_submission:
            raise MediaRequestServiceError(
                f"provider does not support submission: {request.provider}",
            )

        if not capabilities.supports(request.media_type):
            raise MediaRequestServiceError(
                "provider does not support media type: "
                f"{request.provider}:{request.media_type.value}",
            )

        try:
            result = provider.submit(request)
        except (
            MediaRequestProviderError,
            MediaRequestProviderOperationError,
        ) as exc:
            raise MediaRequestServiceError(
                f"provider submission failed: {request.provider}",
            ) from exc

        if not isinstance(result, ProviderSubmissionResult):
            raise MediaRequestServiceError(
                "provider submit() must return ProviderSubmissionResult",
            )

        self._validate_provider_result(
            request,
            result.provider,
            result.provider_request_id,
        )
        self._validate_transition(request.status, result.status)

        updated = replace(
            request,
            provider_request_id=result.provider_request_id,
            status=result.status,
            updated_at=result.updated_at,
            available_at=None,
        )

        return self._replace(updated)

    def refresh_request(self, request_id: object) -> MediaRequest:
        """Refresh one submitted request from provider status."""

        request = self.get_request(request_id)

        if request.provider_request_id is None:
            raise MediaRequestServiceError(
                f"media request is not submitted: {request.request_id}",
            )

        provider = self._provider_for(request.provider)
        capabilities = self._capabilities(provider)

        if not capabilities.supports_status:
            raise MediaRequestServiceError(
                f"provider does not support status: {request.provider}",
            )

        try:
            result = provider.get_status(
                request.provider_request_id,
            )
        except (
            MediaRequestProviderError,
            MediaRequestProviderOperationError,
        ) as exc:
            raise MediaRequestServiceError(
                f"provider status refresh failed: {request.provider}",
            ) from exc

        return self._apply_status_result(request, result)

    def cancel_request(self, request_id: object) -> MediaRequest:
        """Cancel one active provider-side request."""

        request = self.get_request(request_id)

        if request.provider_request_id is None:
            raise MediaRequestServiceError(
                f"media request is not submitted: {request.request_id}",
            )

        if request.terminal:
            raise MediaRequestServiceError(
                f"terminal media request cannot be cancelled: "
                f"{request.request_id}",
            )

        provider = self._provider_for(request.provider)
        capabilities = self._capabilities(provider)

        if not capabilities.supports_cancellation:
            raise MediaRequestServiceError(
                f"provider does not support cancellation: "
                f"{request.provider}",
            )

        try:
            result = provider.cancel(
                request.provider_request_id,
            )
        except (
            MediaRequestProviderError,
            MediaRequestProviderOperationError,
        ) as exc:
            raise MediaRequestServiceError(
                f"provider cancellation failed: {request.provider}",
            ) from exc

        if not isinstance(result, ProviderStatusResult):
            raise MediaRequestServiceError(
                "provider cancel() must return ProviderStatusResult",
            )

        if result.status is not MediaRequestStatus.CANCELLED:
            raise MediaRequestServiceError(
                "provider cancellation must return cancelled status",
            )

        return self._apply_status_result(request, result)

    def get_request(self, request_id: object) -> MediaRequest:
        """Return one request through the repository boundary."""

        try:
            return self.repository.get(request_id)
        except MediaRequestRepositoryError as exc:
            raise MediaRequestServiceError(
                f"unable to read media request: {request_id}",
            ) from exc

    def list_requests(self) -> tuple[MediaRequest, ...]:
        """Return all requests in repository-defined order."""

        try:
            return self.repository.list()
        except MediaRequestRepositoryError as exc:
            raise MediaRequestServiceError(
                "unable to list media requests",
            ) from exc

    def list_user_requests(
        self,
        user_id: object,
    ) -> tuple[MediaRequest, ...]:
        """Return requests owned by one Atlas user."""

        try:
            return self.repository.list_by_user(user_id)
        except MediaRequestRepositoryError as exc:
            raise MediaRequestServiceError(
                f"unable to list media requests for user: {user_id}",
            ) from exc

    def find_provider_request(
        self,
        provider: object,
        provider_request_id: object,
    ) -> MediaRequest | None:
        """Find one request by provider-side identity."""

        try:
            return self.repository.find_by_provider_request(
                provider,
                provider_request_id,
            )
        except MediaRequestRepositoryError as exc:
            raise MediaRequestServiceError(
                "unable to find provider media request",
            ) from exc

    def _provider_for(
        self,
        provider_name: object,
    ) -> MediaRequestProvider:
        normalized = _normalize_provider_name(provider_name)
        provider = self._providers.get(normalized)

        if provider is None:
            raise MediaRequestServiceError(
                f"media-request provider is not registered: {normalized}",
            )

        return provider

    @staticmethod
    def _capabilities(provider: MediaRequestProvider):
        try:
            capabilities = provider.capabilities()
        except (
            MediaRequestProviderError,
            MediaRequestProviderOperationError,
        ) as exc:
            raise MediaRequestServiceError(
                f"unable to read provider capabilities: {provider.name}",
            ) from exc

        return capabilities

    def _apply_status_result(
        self,
        request: MediaRequest,
        result: object,
    ) -> MediaRequest:
        if not isinstance(result, ProviderStatusResult):
            raise MediaRequestServiceError(
                "provider status operation must return ProviderStatusResult",
            )

        if request.provider_request_id is None:
            raise MediaRequestServiceError(
                f"media request is not submitted: {request.request_id}",
            )

        self._validate_provider_result(
            request,
            result.provider,
            result.provider_request_id,
        )
        self._validate_transition(request.status, result.status)

        updated = replace(
            request,
            status=result.status,
            updated_at=result.updated_at,
            available_at=result.available_at,
        )

        return self._replace(updated)

    def _replace(self, request: MediaRequest) -> MediaRequest:
        try:
            return self.repository.replace(request)
        except MediaRequestRepositoryError as exc:
            raise MediaRequestServiceError(
                f"unable to update media request: {request.request_id}",
            ) from exc

    @staticmethod
    def _validate_provider_result(
        request: MediaRequest,
        provider: str,
        provider_request_id: str,
    ) -> None:
        normalized_provider = _normalize_provider_name(provider)

        if normalized_provider != request.provider:
            raise MediaRequestServiceError(
                "provider result does not match request provider",
            )

        if (
            request.provider_request_id is not None
            and provider_request_id != request.provider_request_id
        ):
            raise MediaRequestServiceError(
                "provider result request identity does not match",
            )

    @staticmethod
    def _validate_transition(
        current: MediaRequestStatus,
        target: MediaRequestStatus,
    ) -> None:
        allowed = _ALLOWED_TRANSITIONS[current]

        if target not in allowed:
            raise MediaRequestServiceError(
                "invalid media-request status transition: "
                f"{current.value}->{target.value}",
            )


def _normalize_provider_name(value: object) -> str:
    if not isinstance(value, str):
        raise MediaRequestServiceError(
            "provider name must be text",
        )

    normalized = value.strip().lower().replace(" ", "-")

    if (
        not normalized
        or not _PROVIDER_PATTERN.fullmatch(normalized)
    ):
        raise MediaRequestServiceError(
            "provider name is invalid",
        )

    return normalized
