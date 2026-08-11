"""Self-scoped application service for Atlas media requests."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Callable
import uuid

from atlas.media_requests import (
    JsonMediaRequestRepository,
    MediaRequest,
    MediaRequestError,
    MediaRequestProviderError,
    MediaRequestRepositoryError,
    MediaRequestService,
    MediaRequestServiceConflictError,
    MediaRequestServiceError,
    MediaRequestStatus,
    default_jellyseerr_media_request_provider,
)

from atlas_api.events import RuntimeEventJournalPublisher


DEFAULT_REQUESTS_ROOT = Path(
    "/mnt/storage/configs/atlas/runtime/requests"
)

REQUEST_PROVIDER = "jellyseerr"

RequestIDFactory = Callable[[], str]

_RECOVERY_REQUIRED_STATUSES = frozenset(
    {
        MediaRequestStatus.SUBMITTING,
        MediaRequestStatus.CANCELLING,
    }
)


class MediaRequestsAPIError(RuntimeError):
    """Base failure for the HTTP-facing Request application boundary."""


class MediaRequestNotFoundError(MediaRequestsAPIError):
    """Raised when a caller-visible request does not exist."""


class MediaRequestValidationError(MediaRequestsAPIError):
    """Raised when a supported request payload is invalid."""


class MediaRequestConflictError(MediaRequestsAPIError):
    """Raised when the current lifecycle prevents the requested action."""


class MediaRequestReconciliationRequiredError(
    MediaRequestConflictError
):
    """Raised when an external mutation outcome is ambiguous."""


class MediaRequestsUnavailableError(MediaRequestsAPIError):
    """Raised when Request state or its provider is unavailable."""


def _new_request_id() -> str:
    """Return one opaque Atlas-owned request identifier."""

    return f"req_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class MediaRequestsAPIService:
    """Authenticated, self-scoped media-request application boundary."""

    repository: JsonMediaRequestRepository
    requests: MediaRequestService
    request_id_factory: RequestIDFactory = _new_request_id

    def list_for_user(
        self,
        user_id: str,
    ) -> tuple[MediaRequest, ...]:
        """Return only requests owned by the authenticated user."""

        try:
            return self.requests.list_user_requests(
                user_id
            )
        except MediaRequestServiceError as error:
            raise MediaRequestsUnavailableError(
                "Media requests are unavailable."
            ) from error

    def create_for_user(
        self,
        user_id: str,
        *,
        media_type: str,
        provider_media_id: str,
        title: str,
        year: int | None = None,
        season_number: int | None = None,
    ) -> MediaRequest:
        """Create and submit one request owned by the authenticated user."""

        try:
            request = MediaRequest(
                request_id=self.request_id_factory(),
                user_id=user_id,
                media_type=media_type,
                provider=REQUEST_PROVIDER,
                provider_media_id=provider_media_id,
                title=title,
                year=year,
                season_number=season_number,
            )
        except (
            MediaRequestError,
            TypeError,
            ValueError,
        ) as error:
            raise MediaRequestValidationError(
                "Media request is invalid."
            ) from error

        # Jellyseerr requires a numeric TMDB identifier. Validate that
        # deterministic provider input before Core persists SUBMITTING
        # mutation intent; otherwise a caller input error could be
        # misclassified as an outcome-ambiguous provider mutation.
        if (
            request.provider == REQUEST_PROVIDER
            and (
                not request.provider_media_id.isdigit()
                or int(
                    request.provider_media_id
                ) <= 0
            )
        ):
            raise MediaRequestValidationError(
                "Jellyseerr media identifier must be a positive numeric identifier."
            )

        try:
            self.requests.create_request(
                request
            )
        except MediaRequestServiceConflictError as error:
            raise MediaRequestConflictError(
                "Media request conflicts with existing state."
            ) from error
        except MediaRequestServiceError as error:
            message = str(error)

            if (
                "provider is not registered" in message
                or "provider does not support media type" in message
                or "provider does not support submission" in message
            ):
                raise MediaRequestValidationError(
                    "Media request is not supported."
                ) from error

            raise MediaRequestsUnavailableError(
                "Media request could not be created."
            ) from error

        try:
            return self.requests.submit_request(
                request.request_id
            )
        except MediaRequestServiceError as error:
            # create_request() has already durably committed an Atlas
            # request at this point. The HTTP caller must never repeat
            # the original POST merely because submission did not
            # complete normally: that could create a second local
            # request, and Atlas may also be unable to prove whether
            # the external provider mutation occurred.
            raise MediaRequestReconciliationRequiredError(
                "Media request submission requires reconciliation."
            ) from error

    def cancel_for_user(
        self,
        user_id: str,
        request_id: str,
    ) -> MediaRequest:
        """Cancel only an active request owned by the authenticated user."""

        request = self._owned_request(
            user_id,
            request_id,
        )

        if request.status in _RECOVERY_REQUIRED_STATUSES:
            raise MediaRequestReconciliationRequiredError(
                "Media request requires reconciliation."
            )

        if request.provider_request_id is None:
            raise MediaRequestConflictError(
                "Media request has not been submitted."
            )

        if request.terminal:
            raise MediaRequestConflictError(
                "Terminal media request cannot be cancelled."
            )

        try:
            return self.requests.cancel_request(
                request.request_id
            )
        except MediaRequestServiceError as error:
            message = str(error)

            # This capability failure occurs before Core persists
            # CANCELLING intent or calls the provider.
            if "provider does not support cancellation" in message:
                raise MediaRequestConflictError(
                    "Media request provider does not support cancellation."
                ) from error

            # For every other failure after the API has accepted the
            # caller-owned cancellation operation, fail closed. Atlas
            # must not invite a retry when it cannot prove whether
            # provider-side cancellation occurred.
            raise MediaRequestReconciliationRequiredError(
                "Media request cancellation requires reconciliation."
            ) from error

    def _owned_request(
        self,
        user_id: str,
        request_id: str,
    ) -> MediaRequest:
        try:
            request = self.repository.get(
                request_id
            )
        except MediaRequestRepositoryError as error:
            message = str(error)

            if (
                message.startswith(
                    "media request not found:"
                )
                or message == "request_id is invalid"
                or message == "request_id is required"
                or message
                == "request_id must be text or an integer"
            ):
                raise MediaRequestNotFoundError(
                    "Media request was not found."
                ) from error

            raise MediaRequestsUnavailableError(
                "Media requests are unavailable."
            ) from error

        # Do not distinguish another user's request from an unknown one.
        if request.user_id != user_id:
            raise MediaRequestNotFoundError(
                "Media request was not found."
            )

        return request

def build_default_media_requests_api_service(
) -> MediaRequestsAPIService:
    """Build the process-default media-request API service."""

    root_value = os.getenv(
        "ATLAS_REQUESTS_DIR",
        str(DEFAULT_REQUESTS_ROOT),
    ).strip()

    if not root_value:
        raise MediaRequestsUnavailableError(
            "ATLAS_REQUESTS_DIR is required."
        )

    repository = JsonMediaRequestRepository(
        root_value
    )

    try:
        provider = (
            default_jellyseerr_media_request_provider()
        )
        service = MediaRequestService(
            repository,
            (provider,),
            event_publisher=(
                RuntimeEventJournalPublisher
                .from_environment()
                .publish
            ),
        )
    except (
        MediaRequestProviderError,
        MediaRequestServiceError,
        OSError,
        ValueError,
    ) as error:
        raise MediaRequestsUnavailableError(
            "Media request provider is unavailable."
        ) from error

    return MediaRequestsAPIService(
        repository=repository,
        requests=service,
    )
