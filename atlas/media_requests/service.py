"""Provider-agnostic media-request orchestration for Project Atlas."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
import re
from typing import Any, Callable

from .events import (
    MediaRequestEvent,
    MediaRequestEventType,
    event_type_for_status,
)
from .models import (
    MediaRequest,
    MediaRequestStatus,
)
from .provider import (
    MediaRequestProvider,
    MediaRequestProviderError,
    MediaRequestProviderOperationError,
    ProviderEventContext,
    ProviderStatusResult,
    ProviderSubmissionResult,
)
from .repository import (
    JsonMediaRequestRepository,
    MediaRequestRepositoryConflictError,
    MediaRequestRepositoryError,
)


EventPublisher = Callable[[str, Mapping[str, Any]], None]
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
            MediaRequestStatus.SUBMITTING,
            MediaRequestStatus.APPROVED,
            MediaRequestStatus.SEARCHING,
            MediaRequestStatus.DOWNLOADING,
            MediaRequestStatus.IMPORTING,
            MediaRequestStatus.CANCELLING,
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.REJECTED,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }
    ),
    MediaRequestStatus.SUBMITTING: frozenset(
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
            MediaRequestStatus.CANCELLING,
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
            MediaRequestStatus.CANCELLING,
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }
    ),
    MediaRequestStatus.DOWNLOADING: frozenset(
        {
            MediaRequestStatus.DOWNLOADING,
            MediaRequestStatus.IMPORTING,
            MediaRequestStatus.CANCELLING,
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }
    ),
    MediaRequestStatus.IMPORTING: frozenset(
        {
            MediaRequestStatus.IMPORTING,
            MediaRequestStatus.CANCELLING,
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }
    ),
    MediaRequestStatus.CANCELLING: frozenset(
        {
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


_RECOVERY_REQUIRED_STATUSES = frozenset(
    {
        MediaRequestStatus.SUBMITTING,
        MediaRequestStatus.CANCELLING,
    }
)


class MediaRequestServiceError(RuntimeError):
    """Raised when media-request orchestration cannot complete safely."""


class MediaRequestServiceConflictError(
    MediaRequestServiceError
):
    """Raised when an active request already owns the provider target."""


class MediaRequestService:
    """Coordinate media-request models, persistence, and providers."""

    def __init__(
        self,
        repository: JsonMediaRequestRepository,
        providers: Iterable[MediaRequestProvider],
        *,
        event_publisher: EventPublisher | None = None,
        clock: Clock = _utc_now,
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

        if event_publisher is not None and not callable(event_publisher):
            raise MediaRequestServiceError(
                "event_publisher must be callable or null",
            )

        if not callable(clock):
            raise MediaRequestServiceError(
                "clock must be callable",
            )

        self.repository = repository
        self._providers = provider_map
        self._event_publisher = event_publisher
        self._clock = clock
        self._publication_errors: list[str] = []

    @property
    def provider_names(self) -> tuple[str, ...]:
        """Return registered provider names in deterministic order."""

        return tuple(sorted(self._providers))

    @property
    def publication_errors(self) -> tuple[str, ...]:
        """Return captured best-effort event publication failures."""

        return tuple(self._publication_errors)

    def clear_publication_errors(self) -> None:
        """Clear captured event publication failures."""

        self._publication_errors.clear()

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

        self._validate_submission(
            provider,
            request,
        )

        try:
            persisted = (
                self.repository.save_if_no_active_conflict(
                    request
                )
            )
        except MediaRequestRepositoryConflictError as exc:
            raise MediaRequestServiceConflictError(
                "active media request conflicts with provider target"
            ) from exc
        except MediaRequestRepositoryError as exc:
            raise MediaRequestServiceError(
                f"unable to persist media request: {request.request_id}",
            ) from exc

        self._publish(
            MediaRequestEventType.CREATED,
            persisted,
        )

        return persisted

    def submit_request(self, request_id: object) -> MediaRequest:
        """Submit one persisted request to its configured provider."""

        request = self.get_request(request_id)

        if request.status in _RECOVERY_REQUIRED_STATUSES:
            raise MediaRequestServiceError(
                f"media request requires reconciliation: {request.request_id}",
            )

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

        self._validate_submission(
            provider,
            request,
        )

        self._validate_transition(
            request.status,
            MediaRequestStatus.SUBMITTING,
        )
        intent = self._replace(
            replace(
                request,
                status=MediaRequestStatus.SUBMITTING,
            )
        )

        try:
            result = provider.submit(intent)
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
            intent,
            result.provider,
            result.provider_request_id,
        )
        self._validate_transition(intent.status, result.status)

        updated = replace(
            intent,
            provider_request_id=result.provider_request_id,
            status=result.status,
            updated_at=result.updated_at,
            available_at=None,
        )

        persisted = self._replace(updated)

        self._publish(
            MediaRequestEventType.SUBMITTED,
            persisted,
            context=result.context,
        )
        self._publish(
            event_type_for_status(persisted.status),
            persisted,
            context=result.context,
        )

        return persisted

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

        updated = self._apply_status_result(request, result)

        if updated.status is not request.status:
            self._publish(
                event_type_for_status(updated.status),
                updated,
                context=result.context,
            )

        return updated

    def cancel_request(self, request_id: object) -> MediaRequest:
        """Cancel one active provider-side request."""

        request = self.get_request(request_id)

        if request.status in _RECOVERY_REQUIRED_STATUSES:
            raise MediaRequestServiceError(
                f"media request requires reconciliation: {request.request_id}",
            )

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

        self._validate_transition(
            request.status,
            MediaRequestStatus.CANCELLING,
        )
        intent = self._replace(
            replace(
                request,
                status=MediaRequestStatus.CANCELLING,
            )
        )

        try:
            result = provider.cancel(
                intent.provider_request_id,
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

        updated = self._apply_status_result(intent, result)

        self._publish(
            MediaRequestEventType.CANCELLED,
            updated,
            context=result.context,
        )

        return updated

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

    def list_recovery_required_requests(
        self,
    ) -> tuple[MediaRequest, ...]:
        """Return requests whose external mutation outcome is ambiguous."""

        try:
            requests = self.repository.list()
        except MediaRequestRepositoryError as exc:
            raise MediaRequestServiceError(
                "unable to list media requests requiring reconciliation",
            ) from exc

        return tuple(
            request
            for request in requests
            if request.status in _RECOVERY_REQUIRED_STATUSES
        )

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

    def _publish(
        self,
        event_type: MediaRequestEventType,
        request: MediaRequest,
        *,
        context: ProviderEventContext | None = None,
    ) -> None:
        if self._event_publisher is None:
            return

        try:
            event = MediaRequestEvent.from_request(
                event_type,
                request,
                occurred_at=self._occurred_at(),
                context=context,
            )
            self._event_publisher(
                event.name,
                event.to_payload(),
            )
        except Exception as exc:
            self._publication_errors.append(
                f"{event_type.value}: {exc}",
            )

    def _occurred_at(self) -> datetime:
        value = self._clock()

        if not isinstance(value, datetime):
            raise MediaRequestServiceError(
                "clock must return a datetime",
            )

        if value.tzinfo is None or value.utcoffset() is None:
            raise MediaRequestServiceError(
                "clock must return a timezone-aware datetime",
            )

        return value.astimezone(timezone.utc)

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

    @staticmethod
    def _validate_submission(
        provider: MediaRequestProvider,
        request: MediaRequest,
    ) -> None:
        try:
            result = provider.validate_submission(
                request
            )
        except (
            MediaRequestProviderError,
            MediaRequestProviderOperationError,
        ) as exc:
            raise MediaRequestServiceError(
                "provider submission preflight failed: "
                f"{provider.name}",
            ) from exc

        if result is not None:
            raise MediaRequestServiceError(
                "provider validate_submission() must return null",
            )

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
